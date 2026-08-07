"""SMART hardware inspection through smartctl JSON output."""

import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.config import AppConfig
from app.models.disk import HealthStatus

LOGGER = logging.getLogger(__name__)
Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(slots=True)
class SmartResult:
    """Normalized data returned by one SMART query."""

    supported: bool | None = None
    enabled: bool | None = None
    health: HealthStatus = HealthStatus.UNKNOWN
    temperature: str = "--"
    power_on_hours: str = "--"
    power_cycles: str = "--"
    nvme_data: dict[str, str] | None = None
    model: str = "--"
    serial: str = "--"
    firmware: str = "--"


class SmartService:
    """Own every smartctl invocation and cache its normalized result."""

    def __init__(
        self,
        config: AppConfig | None = None,
        runner: Runner = subprocess.run,
    ) -> None:
        self.config = config or AppConfig()
        self.runner = runner
        self._cache: dict[str, SmartResult] = {}

    def inspect(self, device: str, force_refresh: bool = False) -> SmartResult:
        """Inspect a device, returning cached data unless a refresh is requested."""
        if not force_refresh and device in self._cache:
            LOGGER.debug("SMART cache hit for %s", device)
            return self._cache[device]

        command = [self.config.smartctl_binary, "--json", "--all", f"/dev/{device}"]
        LOGGER.info("Querying SMART data: %s", " ".join(command))
        try:
            result = self.runner(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            LOGGER.warning("smartctl unavailable for %s: %s", device, exc)
            normalized = SmartResult()
            self._cache[device] = normalized
            return normalized

        try:
            payload = json.loads(result.stdout or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except json.JSONDecodeError as exc:
            LOGGER.warning("Invalid smartctl JSON for %s: %s", device, exc)
            payload = {}

        normalized = self._normalize(payload)
        self._cache[device] = normalized
        if result.returncode not in (0, 1):
            LOGGER.warning("smartctl returned %s for %s", result.returncode, device)
        return normalized

    def clear_cache(self) -> None:
        """Discard all cached SMART responses."""
        self._cache.clear()

    def _normalize(self, payload: dict[str, Any]) -> SmartResult:
        smart_support = self._mapping(payload.get("smart_support"))
        smart_status = self._mapping(payload.get("smart_status"))
        temperature = self._temperature(payload)
        power_on = self._mapping(payload.get("power_on_time")).get("hours")
        power_cycles = payload.get("power_cycle_count")
        nvme_log = self._mapping(payload.get("nvme_smart_health_information_log"))
        passed = smart_status.get("passed")
        critical_warning = self._integer(nvme_log.get("critical_warning"))
        health = (
            HealthStatus.HEALTHY
            if passed is True
            else HealthStatus.CRITICAL if passed is False else HealthStatus.UNKNOWN
        )
        if health is HealthStatus.UNKNOWN and critical_warning > 0:
            health = HealthStatus.WARNING
        return SmartResult(
            supported=smart_support.get("available"),
            enabled=smart_support.get("enabled"),
            health=health,
            temperature=temperature,
            power_on_hours=self._display(power_on, " h"),
            power_cycles=self._display(power_cycles),
            nvme_data=(
                {
                    "critical_warnings": self._display(nvme_log.get("critical_warning")),
                    "percentage_used": self._display(nvme_log.get("percentage_used"), "%"),
                    "media_errors": self._display(nvme_log.get("media_errors")),
                    "unsafe_shutdowns": self._display(nvme_log.get("unsafe_shutdowns")),
                    "available_spare": self._display(nvme_log.get("available_spare"), "%"),
                }
                if nvme_log
                else None
            ),
            model=self._first(payload, "model_name", "model_family"),
            serial=self._first(payload, "serial_number"),
            firmware=self._first(payload, "firmware_version"),
        )

    @staticmethod
    def _temperature(payload: dict[str, Any]) -> str:
        temperature = SmartService._mapping(payload.get("temperature"))
        nvme_log = SmartService._mapping(payload.get("nvme_smart_health_information_log"))
        candidates = [
            temperature.get("current"),
            nvme_log.get("temperature"),
        ]
        for value in candidates:
            if value not in (None, ""):
                return f"{value} °C"
        return "--"

    @staticmethod
    def _first(payload: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return str(value)
        return "--"

    @staticmethod
    def _mapping(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _display(value: Any, suffix: str = "") -> str:
        return f"{value}{suffix}" if value not in (None, "") else "--"

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
