"""Immutable runtime configuration."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Settings shared by the composition root and services."""

    application_name: str = "DiskBench"
    version: str = "v0.5"
    lsblk_binary: str = "lsblk"
    blkid_binary: str = "blkid"
    smartctl_binary: str = "smartctl"
    nvme_binary: str = "nvme"
    fio_binary: str = "fio"
    benchmark_file_size_bytes: int = 1024 * 1024 * 1024
    benchmark_minimum_free_space_bytes: int = 1200 * 1024 * 1024
    benchmark_runtime_seconds: int = 5
    history_directory: Path = Path("history")
    log_directory: Path = Path.home() / ".local" / "state" / "diskbench"
