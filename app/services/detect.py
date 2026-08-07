"""Fast physical storage discovery using lsblk and kernel metadata."""

import json
import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.config import AppConfig
from app.models.disk import Disk, Partition, Rotation

LOGGER = logging.getLogger(__name__)
Runner = Callable[..., subprocess.CompletedProcess[str]]


class DetectionError(RuntimeError):
    """Raised when block-device metadata cannot be obtained or parsed."""


class LsblkDetectionService:
    """Translate lsblk JSON and sysfs metadata into domain objects."""

    excluded_prefixes = ("loop", "ram", "zram", "dm-")

    def __init__(
        self,
        config: AppConfig | None = None,
        runner: Runner = subprocess.run,
        sysfs_root: Path = Path("/sys/block"),
    ) -> None:
        self.config = config or AppConfig()
        self.runner = runner
        self.sysfs_root = sysfs_root

    def detect(self) -> list[Disk]:
        """Return physical disks and optical drives, excluding virtual devices."""
        command = [
            self.config.lsblk_binary,
            "--json",
            "--bytes",
            "--output",
            "NAME,SIZE,MODEL,VENDOR,SERIAL,REV,TRAN,TYPE,FSTYPE,MOUNTPOINT,"
            "ROTA,RM,LOG-SEC,PHY-SEC,UUID,DISC-GRAN,PARTTYPE,PARTTYPENAME,PTTYPE",
        ]
        LOGGER.info("Querying block devices: %s", " ".join(command))
        try:
            result = self.runner(command, capture_output=True, text=True, check=True)
            payload = json.loads(result.stdout)
            if not isinstance(payload, dict):
                raise ValueError("lsblk JSON root is not an object")
        except (
            OSError,
            ValueError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
        ) as exc:
            LOGGER.exception("lsblk detection failed")
            raise DetectionError(f"Unable to read storage devices: {exc}") from exc

        return [
            self._parse_disk(item)
            for item in payload.get("blockdevices", [])
            if self._is_physical(item)
        ]

    def _is_physical(self, item: dict[str, Any]) -> bool:
        name = str(item.get("name") or "")
        return item.get("type") in {"disk", "rom"} and not name.startswith(self.excluded_prefixes)

    def _parse_disk(self, item: dict[str, Any]) -> Disk:
        name = self._value(item.get("name"), "Unknown")
        properties = self._udev_properties(name)
        partitions = [self._parse_partition(child) for child in item.get("children", [])]
        filesystems = [part.filesystem for part in partitions if part.filesystem != "Unknown"]
        mounts = [part.mount_point for part in partitions if part.mount_point != "Not mounted"]
        rotational = self._rotational(name, item.get("rota"))
        transport = self._transport(item.get("tran"), properties)
        bus = self._bus(name, transport, properties)
        interface = self._interface(name, transport, properties)
        trim_support = "Supported" if self._integer(item.get("disc-gran")) > 0 else "Unknown"
        blkid_data = self._blkid_metadata(name) if not item.get("uuid") else {}

        return Disk(
            name=name,
            block_type=self._value(item.get("type"), "disk"),
            vendor=self._value(item.get("vendor"), properties.get("ID_VENDOR", "Unknown")),
            model=self._value(item.get("model"), properties.get("ID_MODEL", "Unknown")),
            serial=self._value(
                item.get("serial"),
                properties.get("ID_SERIAL_SHORT", "Not available"),
            ),
            firmware=self._value(item.get("rev"), "Not available"),
            capacity=self._format_bytes(item.get("size")),
            logical_sector_size=self._sector_size(item.get("log-sec")),
            physical_sector_size=self._sector_size(item.get("phy-sec")),
            bus=bus,
            transport=transport,
            filesystem=filesystems[0] if filesystems else "Unknown",
            mount_point=mounts[0] if mounts else "Not mounted",
            uuid=self._value(item.get("uuid"), blkid_data.get("UUID", "--")),
            partition_table=self._value(
                item.get("pttype"),
                item.get("parttypename", "--"),
            ),
            interface=interface,
            rotation=(
                Rotation.ROTATIONAL
                if rotational is True
                else Rotation.SOLID_STATE if rotational is False else Rotation.UNKNOWN
            ),
            rotational=rotational,
            removable=self._boolean(item.get("rm")),
            trim_support=trim_support,
            partitions=partitions,
        )

    def _parse_partition(self, item: dict[str, Any]) -> Partition:
        partition_name = self._value(item.get("name"), "Unknown")
        needs_blkid = not item.get("fstype") or not item.get("uuid")
        blkid_data = self._blkid_metadata(partition_name) if needs_blkid else {}
        return Partition(
            name=partition_name,
            filesystem=self._value(
                item.get("fstype"),
                blkid_data.get("TYPE", "Unknown"),
            ),
            mount_point=self._value(item.get("mountpoint"), "Not mounted"),
            capacity=self._format_bytes(item.get("size")),
            uuid=self._value(item.get("uuid"), blkid_data.get("UUID", "--")),
            partition_table=self._value(
                item.get("parttypename"),
                item.get("parttype", "--"),
            ),
        )

    def _rotational(self, name: str, fallback: Any) -> bool | None:
        value = self._sysfs_value(name, "queue/rotational")
        if value in {"0", "1"}:
            return value == "1"
        return self._boolean(fallback)

    def _udev_properties(self, name: str) -> dict[str, str]:
        command = [
            "udevadm",
            "info",
            "--query=property",
            "--name",
            f"/dev/{name}",
        ]
        LOGGER.info("Querying udev metadata: %s", " ".join(command))
        try:
            result = self.runner(command, capture_output=True, text=True, check=False)
        except OSError as exc:
            LOGGER.warning("udevadm unavailable for %s: %s", name, exc)
            return {}
        return {
            key: value
            for line in result.stdout.splitlines()
            if "=" in line
            for key, value in [line.split("=", 1)]
        }

    def _blkid_metadata(self, name: str) -> dict[str, str]:
        """Read JSON filesystem metadata when lsblk does not expose it."""
        command = [self.config.blkid_binary, "--output", "json", f"/dev/{name}"]
        LOGGER.info("Querying filesystem metadata: %s", " ".join(command))
        try:
            result = self.runner(command, capture_output=True, text=True, check=False)
            payload = json.loads(result.stdout or "{}")
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("blkid unavailable for %s: %s", name, exc)
            return {}
        if not isinstance(payload, dict):
            return {}
        devices = payload.get("blockdevices", [])
        return devices[0] if devices and isinstance(devices[0], dict) else {}

    def _sysfs_value(self, name: str, relative_path: str) -> str:
        path = self.sysfs_root / name / relative_path
        LOGGER.info("Querying sysfs metadata: %s", path)
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    @staticmethod
    def _bus(name: str, transport: str, properties: dict[str, str]) -> str:
        if name.startswith("nvme"):
            return "PCIe"
        if name.startswith("mmcblk"):
            return "MMC"
        if properties.get("ID_BUS"):
            return properties["ID_BUS"].upper()
        return transport

    @staticmethod
    def _interface(name: str, transport: str, properties: dict[str, str]) -> str:
        if name.startswith("nvme"):
            return "PCIe"
        if properties.get("ID_ATA_BUS"):
            return properties["ID_ATA_BUS"].upper()
        return transport

    @staticmethod
    def _transport(value: Any, properties: dict[str, str]) -> str:
        if value:
            normalized = str(value).strip()
            if normalized:
                return normalized.upper()
        if properties.get("ID_BUS"):
            return properties["ID_BUS"].strip().upper() or "Unknown"
        return "Unknown"

    @staticmethod
    def _value(value: Any, default: str = "Unknown") -> str:
        if value not in (None, ""):
            normalized = str(value).strip()
            if normalized:
                return normalized
        return default

    @staticmethod
    def _boolean(value: Any) -> bool | None:
        if value in (True, 1, "1", "true", "True"):
            return True
        if value in (False, 0, "0", "false", "False"):
            return False
        return None

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _sector_size(cls, value: Any) -> str:
        return f"{cls._integer(value)} B" if cls._integer(value) else "--"

    @staticmethod
    def _format_bytes(value: Any) -> str:
        try:
            amount = float(value)
        except (TypeError, ValueError):
            return "Unknown"
        units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
        index = 0
        while amount >= 1024 and index < len(units) - 1:
            amount /= 1024
            index += 1
        return f"{amount:.0f} {units[index]}" if index == 0 else f"{amount:.1f} {units[index]}"
