"""Resolve safe writable filesystems for file-backed benchmarks."""

import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import psutil

from app.models.disk import Disk

LOGGER = logging.getLogger(__name__)


class MountResolutionError(RuntimeError):
    """Raised when a disk has no suitable writable filesystem."""


@dataclass(frozen=True, slots=True)
class MountCandidate:
    """A filesystem candidate associated with a detected disk."""

    path: Path
    filesystem: str
    options: str = ""


class MountResolver:
    """Select the highest-priority writable mountpoint for a disk."""

    _priority = ("/home", "/", "/run/media", "/media", "/mnt")
    _rejected_filesystems = {"iso9660", "squashfs", "tmpfs", "swap"}
    _rejected_mounts = (Path("/boot"), Path("/boot/efi"))
    _placeholders = {"", "--", "Unknown", "Not mounted"}

    def resolve(self, disk: Disk) -> Path:
        """Return a writable mountpoint or raise a user-facing resolution error."""
        candidates = self._candidates(disk)
        mount_options = self._mount_options()
        viable: list[MountCandidate] = []
        for candidate in candidates:
            if not self._is_viable(candidate, mount_options):
                continue
            writable_path = self._writable_path(candidate.path)
            if writable_path is not None:
                viable.append(replace(candidate, path=writable_path))
        if not viable:
            LOGGER.warning("No writable mountpoint found for %s", disk.name)
            raise MountResolutionError("This device is not mounted.")
        selected = min(viable, key=lambda candidate: self._sort_key(candidate.path))
        LOGGER.info(
            "Selected benchmark mountpoint: disk=%s path=%s filesystem=%s",
            disk.name,
            selected.path,
            selected.filesystem,
        )
        return selected.path

    def describe(self, path: Path) -> tuple[str, int]:
        """Return filesystem type and available bytes for a resolved path."""
        filesystem = "Unknown"
        matching_mounts = [
            partition
            for partition in self._mount_info()
            if self._is_within(path, Path(partition.mountpoint))
        ]
        if matching_mounts:
            partition = max(matching_mounts, key=lambda item: len(item.mountpoint))
            filesystem = partition.fstype or filesystem
        try:
            available = os.statvfs(path).f_bavail * os.statvfs(path).f_frsize
        except OSError:
            available = 0
        return filesystem, available

    def _candidates(self, disk: Disk) -> list[MountCandidate]:
        candidates: list[MountCandidate] = []
        for partition in disk.partitions:
            candidates.append(MountCandidate(Path(partition.mount_point), partition.filesystem))
        candidates.append(MountCandidate(Path(disk.mount_point), disk.filesystem))
        unique: dict[str, MountCandidate] = {}
        for candidate in candidates:
            if str(candidate.path) not in self._placeholders:
                unique[str(candidate.path)] = candidate
        return list(unique.values())

    def _is_viable(self, candidate: MountCandidate, mount_options: dict[str, str]) -> bool:
        path = candidate.path
        filesystem = candidate.filesystem.lower().strip()
        if filesystem in self._rejected_filesystems or self._is_rejected_mount(path):
            return False
        if not path.is_dir():
            return False
        options = candidate.options or mount_options.get(str(path), "")
        return "ro" not in {option.strip().lower() for option in options.split(",")}

    def _writable_path(self, mountpoint: Path) -> Path | None:
        """Find a writable directory without crossing the selected filesystem."""
        try:
            mount_device = mountpoint.stat().st_dev
        except OSError:
            return None
        if os.access(mountpoint, os.W_OK):
            return mountpoint

        home = Path.home()
        if (
            self._is_within(home, mountpoint)
            and self._same_device(home, mount_device)
            and os.access(home, os.W_OK)
        ):
            return home

        try:
            children = sorted(mountpoint.iterdir(), key=lambda child: child.name.lower())
        except OSError as exc:
            LOGGER.warning("Unable to inspect writable directories below %s: %s", mountpoint, exc)
            return None
        for child in children:
            if (
                child.is_dir()
                and self._same_device(child, mount_device)
                and os.access(child, os.W_OK)
            ):
                return child
        return None

    @staticmethod
    def _same_device(path: Path, device: int) -> bool:
        try:
            return path.stat().st_dev == device
        except OSError:
            return False

    def _mount_options(self) -> dict[str, str]:
        return {partition.mountpoint: partition.opts for partition in self._mount_info()}

    @staticmethod
    def _mount_info() -> list[Any]:
        try:
            return psutil.disk_partitions(all=True)
        except OSError as exc:
            LOGGER.warning("Unable to inspect mounted filesystems: %s", exc)
            return []

    def _sort_key(self, path: Path) -> tuple[int, int, str]:
        normalized = str(path)
        for index, prefix in enumerate(self._priority):
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                return index, len(normalized), normalized
        return len(self._priority), len(normalized), normalized

    def _is_rejected_mount(self, path: Path) -> bool:
        return any(self._same_path(path, rejected) for rejected in self._rejected_mounts)

    @staticmethod
    def _same_path(left: Path, right: Path) -> bool:
        try:
            return left.resolve() == right.resolve()
        except OSError:
            return left == right

    @staticmethod
    def _is_within(path: Path, parent: Path) -> bool:
        try:
            path.resolve().relative_to(parent.resolve())
            return True
        except (OSError, ValueError):
            return False
