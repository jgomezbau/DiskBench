"""Immutable runtime configuration."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Settings shared by the composition root and services."""

    application_name: str = "DiskBench"
    version: str = "v0.1-alpha"
    lsblk_binary: str = "lsblk"
    log_directory: Path = Path.home() / ".local" / "state" / "diskbench"
