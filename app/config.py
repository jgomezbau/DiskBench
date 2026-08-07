"""Immutable runtime configuration."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Settings shared by the composition root and services."""

    application_name: str = "DiskBench"
    version: str = "v0.4"
    lsblk_binary: str = "lsblk"
    blkid_binary: str = "blkid"
    smartctl_binary: str = "smartctl"
    nvme_binary: str = "nvme"
    log_directory: Path = Path.home() / ".local" / "state" / "diskbench"
