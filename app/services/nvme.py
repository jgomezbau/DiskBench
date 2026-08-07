"""NVMe controller inspection through nvme-cli and sysfs."""

import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import AppConfig
from app.models.disk import NvmeInfo

LOGGER = logging.getLogger(__name__)
Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(slots=True)
class NvmeResult:
    """Normalized NVMe controller data."""

    info: NvmeInfo
    model: str = "--"
    serial: str = "--"
    firmware: str = "--"


class NvmeService:
    """Own nvme-cli calls and cache controller metadata."""

    def __init__(
        self,
        config: AppConfig | None = None,
        runner: Runner = subprocess.run,
    ) -> None:
        self.config = config or AppConfig()
        self.runner = runner
        self._cache: dict[str, NvmeResult] = {}

    def inspect(self, device: str, force_refresh: bool = False) -> NvmeResult | None:
        """Inspect an NVMe namespace and return None for non-NVMe devices."""
        if not device.startswith("nvme"):
            return None
        if not force_refresh and device in self._cache:
            LOGGER.debug("NVMe cache hit for %s", device)
            return self._cache[device]

        controller = device.split("n", 1)[0]
        command = [
            self.config.nvme_binary,
            "id-ctrl",
            "--output-format=json",
            f"/dev/{controller}",
        ]
        LOGGER.info("Querying NVMe controller: %s", " ".join(command))
        try:
            result = self.runner(command, capture_output=True, text=True, check=False)
            payload = json.loads(result.stdout or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("NVMe query unavailable for %s: %s", device, exc)
            normalized = NvmeResult(info=self._sysfs_info(controller))
            self._cache[device] = normalized
            return normalized

        info = self._normalize(payload, controller)
        normalized = NvmeResult(
            info=info,
            model=self._value(payload, "mn"),
            serial=self._value(payload, "sn"),
            firmware=self._value(payload, "fr"),
        )
        self._cache[device] = normalized
        return normalized

    def clear_cache(self) -> None:
        """Discard all cached NVMe responses."""
        self._cache.clear()

    def _normalize(self, payload: dict[str, Any], controller: str) -> NvmeInfo:
        fallback = self._sysfs_info(controller)
        return NvmeInfo(
            pcie_generation=fallback.pcie_generation,
            pcie_width=fallback.pcie_width,
            nvme_version=self._display(payload.get("ver")),
            namespace_count=self._display(payload.get("nn")),
            controller_model=self._value(payload, "mn"),
            controller_id=self._display(payload.get("cntlid")),
        )

    @staticmethod
    def _sysfs_info(controller: str) -> NvmeInfo:
        root = Path("/sys/class/nvme") / controller / "device"
        generation = NvmeService._read_sysfs(root / "current_link_speed")
        width = NvmeService._read_sysfs(root / "current_link_width")
        return NvmeInfo(
            pcie_generation=generation or "--",
            pcie_width=width or "--",
        )

    @staticmethod
    def _read_sysfs(path: Path) -> str:
        LOGGER.info("Querying NVMe sysfs metadata: %s", path)
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    @staticmethod
    def _value(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        return str(value).strip() if value not in (None, "") else "--"

    @staticmethod
    def _display(value: Any) -> str:
        return str(value) if value not in (None, "") else "--"
