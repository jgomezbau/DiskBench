"""Persistent runtime configuration."""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Settings shared by the composition root and services."""

    application_name: str = "DiskBench"
    version: str = "v0.6"
    lsblk_binary: str = "lsblk"
    blkid_binary: str = "blkid"
    smartctl_binary: str = "smartctl"
    nvme_binary: str = "nvme"
    fio_binary: str = "fio"
    benchmark_file_size_bytes: int = 1024 * 1024 * 1024
    benchmark_minimum_free_space_bytes: int = 1200 * 1024 * 1024
    benchmark_runtime_seconds: int = 5
    benchmark_iterations: int = 1
    history_directory: Path = Path("history")
    output_directory: Path = Path("history")
    history_retention: int = 100
    theme: str = "dark"
    log_directory: Path = Path.home() / ".local" / "state" / "diskbench"
    settings_path: Path = field(
        default_factory=lambda: Path.home() / ".config" / "diskbench" / "settings.json"
    )

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        """Load user settings from JSON, falling back safely to defaults."""
        settings_path = path or cls().settings_path
        defaults = cls(settings_path=settings_path)
        try:
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            if settings_path.exists():
                LOGGER.warning("Unable to load settings from %s: %s", settings_path, exc)
            return defaults
        if not isinstance(payload, dict):
            LOGGER.warning("Ignoring non-object settings file: %s", settings_path)
            return defaults
        return cls(
            **{
                **asdict(defaults),
                **cls._coerce_settings(payload),
                "settings_path": settings_path,
            }
        )

    def save(self, path: Path | None = None) -> None:
        """Persist user-configurable values as readable JSON."""
        settings_path = path or self.settings_path
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "benchmark_file_size_bytes": self.benchmark_file_size_bytes,
            "benchmark_runtime_seconds": self.benchmark_runtime_seconds,
            "benchmark_iterations": self.benchmark_iterations,
            "output_directory": str(self.output_directory),
            "history_directory": str(self.history_directory),
            "history_retention": self.history_retention,
            "theme": self.theme,
        }
        settings_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        LOGGER.info("Saved settings to %s", settings_path)

    @staticmethod
    def _coerce_settings(payload: dict[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for field_name in (
            "benchmark_file_size_bytes",
            "benchmark_runtime_seconds",
            "benchmark_iterations",
            "history_retention",
        ):
            value = payload.get(field_name)
            if isinstance(value, int) and value > 0:
                values[field_name] = value
        for field_name in ("history_directory", "output_directory"):
            value = payload.get(field_name)
            if isinstance(value, str) and value.strip():
                values[field_name] = Path(value)
        theme = payload.get("theme")
        if theme in {"dark", "light"}:
            values["theme"] = theme
        return values
