"""Tests for safe benchmark mountpoint resolution."""

from pathlib import Path

import pytest

from app.models.disk import Disk, Partition
from app.services.mount import MountResolutionError, MountResolver


def test_resolver_skips_boot_and_uses_writable_disk_directory(tmp_path: Path) -> None:
    disk = Disk(
        name="nvme0n1",
        mount_point="Not mounted",
        partitions=[
            Partition("nvme0n1p1", filesystem="vfat", mount_point="/boot/efi"),
            Partition("nvme0n1p2", filesystem="ext4", mount_point=str(tmp_path)),
        ],
    )

    assert MountResolver().resolve(disk) == tmp_path


def test_resolver_rejects_non_filesystems() -> None:
    disk = Disk(
        name="sda",
        mount_point="Not mounted",
        partitions=[Partition("sda1", filesystem="iso9660", mount_point="/tmp")],
    )

    with pytest.raises(MountResolutionError, match="This device is not mounted"):
        MountResolver().resolve(disk)


def test_resolver_refreshes_disk_before_selecting_mount(tmp_path: Path) -> None:
    fresh_directory = tmp_path / "fresh"
    fresh_directory.mkdir()
    stale = Disk(name="sdc", mount_point="/boot")
    fresh = Disk(
        name="sdc",
        mount_point="Not mounted",
        partitions=[Partition("sdc1", filesystem="ntfs", mount_point=str(fresh_directory))],
    )

    class Detector:
        def detect(self) -> list[Disk]:
            return [fresh]

    assert MountResolver(detector=Detector()).resolve(stale) == fresh_directory
