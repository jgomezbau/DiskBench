"""Physical disk detection using lsblk JSON output."""

import json
import logging
import subprocess
from collections.abc import Callable
from typing import Any

import psutil

from app.config import AppConfig
from app.models.disk import Disk, Partition, Rotation

LOGGER = logging.getLogger(__name__)
Runner = Callable[..., subprocess.CompletedProcess[str]]


class DetectionError(RuntimeError):
    """Raised when block-device metadata cannot be obtained or parsed."""


class LsblkDetectionService:
    """Translate the operating system representation into domain objects."""

    excluded_prefixes = ("loop", "ram", "zram", "dm-")

    def __init__(self, config: AppConfig | None = None, runner: Runner = subprocess.run) -> None:
        self.config = config or AppConfig()
        self.runner = runner

    def detect(self) -> list[Disk]:
        """Return physical disks, excluding virtual block devices."""
        command = [
            self.config.lsblk_binary,
            "--json",
            "--bytes",
            "--output",
            "NAME,SIZE,MODEL,VENDOR,SERIAL,REV,TRAN,TYPE,FSTYPE,MOUNTPOINT,ROTA",
        ]
        try:
            result = self.runner(command, capture_output=True, text=True, check=True)
            payload = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            LOGGER.exception("lsblk detection failed")
            raise DetectionError(f"Unable to read storage devices: {exc}") from exc
        return [
            self._parse_disk(item)
            for item in payload.get("blockdevices", [])
            if self._is_physical(item)
        ]

    def _is_physical(self, item: dict[str, Any]) -> bool:
        name = str(item.get("name") or "")
        return item.get("type") == "disk" and not name.startswith(self.excluded_prefixes)

    def _parse_disk(self, item: dict[str, Any]) -> Disk:
        partitions = [self._parse_partition(child) for child in item.get("children", [])]
        filesystems = [part.filesystem for part in partitions if part.filesystem != "Unknown"]
        mounts = [part.mount_point for part in partitions if part.mount_point != "Not mounted"]
        rota = item.get("rota")
        rotation = Rotation.ROTATIONAL if rota is True or rota == 1 else Rotation.SOLID_STATE
        name = self._value(item.get("name"), "Unknown")
        return Disk(
            name=name,
            vendor=self._value(item.get("vendor")),
            model=self._value(item.get("model")),
            serial=self._value(item.get("serial"), "Not available"),
            firmware=self._value(item.get("rev"), "Not available"),
            capacity=self._format_bytes(item.get("size")),
            transport=self._transport(item.get("tran")),
            filesystem=filesystems[0] if filesystems else "Unknown",
            mount_point=mounts[0] if mounts else "Not mounted",
            rotation=rotation,
            temperature=self._temperature(),
            partitions=partitions,
        )

    def _parse_partition(self, item: dict[str, Any]) -> Partition:
        return Partition(
            name=self._value(item.get("name"), "Unknown"),
            filesystem=self._value(item.get("fstype")),
            mount_point=self._value(item.get("mountpoint"), "Not mounted"),
            capacity=self._format_bytes(item.get("size")),
        )

    @staticmethod
    def _value(value: Any, default: str = "Unknown") -> str:
        return str(value).strip() if value not in (None, "") else default

    @staticmethod
    def _transport(value: Any) -> str:
        return str(value).upper() if value else "Unknown"

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

    @staticmethod
    def _temperature() -> str:
        """Use psutil when available, while keeping detection best-effort."""
        try:
            sensors = psutil.sensors_temperatures()
        except (AttributeError, OSError):
            return "Not available"
        for entries in sensors.values():
            for entry in entries:
                if entry.current:
                    return f"{entry.current:.0f} °C"
        return "Not available"
