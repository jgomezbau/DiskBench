"""Immutable runtime configuration."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Settings shared by the composition root and services."""

    application_name: str = "DiskBench"
    version: str = "v0.3"
    lsblk_binary: str = "lsblk"
    smartctl_binary: str = "smartctl"
    nvme_binary: str = "nvme"
    log_directory: Path = Path.home() / ".local" / "state" / "diskbench"
