"""Presentation formatting helpers."""

from app.models.disk import Disk


def filesystem_summary(disk: Disk) -> str:
    """Return the filesystem value used in the table."""
    return disk.filesystem


def mount_summary(disk: Disk) -> str:
    """Return the mount-point value used in the table."""
    return disk.mount_point
