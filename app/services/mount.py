"""Resolve safe writable filesystems for file-backed benchmarks."""

import json
import logging
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

import psutil

from app.models.disk import Disk

LOGGER = logging.getLogger(__name__)


class MountResolutionError(RuntimeError):
    """Raised when a disk has no suitable writable filesystem."""


class DiskDetector(Protocol):
    """Minimal detector contract required for a fresh mount resolution."""

    def detect(self) -> list[Disk]:
        """Return the current physical disk inventory."""


@dataclass(frozen=True, slots=True)
class MountCandidate:
    """A filesystem candidate associated with a detected disk."""

    path: Path
    filesystem: str
    options: str = ""
    partition: str = "--"


class MountResolver:
    """Select the highest-priority writable mountpoint for a disk."""

    _priority = ("/home", "/", "/run/media", "/media", "/mnt")
    _rejected_filesystems = {"iso9660", "squashfs", "tmpfs", "swap"}
    _rejected_mounts = (Path("/boot"), Path("/boot/efi"))
    _placeholders = {"", "--", "Unknown", "Not mounted"}

    def __init__(
        self,
        detector: DiskDetector | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.detector = detector
        self.runner = runner

    def resolve(self, disk: Disk) -> Path:
        """Return a writable mountpoint or raise a user-facing resolution error."""
        LOGGER.debug(
            "Selected disk: device=/dev/%s parent=-- partitions=%s filesystem=%s " "mountpoint=%s",
            disk.name,
            [partition.name for partition in disk.partitions],
            disk.filesystem,
            disk.mount_point,
        )
        current_disk = self._current_disk(disk)
        mount_info = self._mount_info()
        candidates = self._candidates(current_disk, mount_info)
        mount_options = {record["target"]: record["options"] for record in mount_info}
        viable: list[MountCandidate] = []
        for candidate in candidates:
            if not self._is_viable(candidate, mount_options):
                continue
            writable_path = self._writable_path(candidate.path)
            if writable_path is not None:
                LOGGER.debug(
                    "Writable candidate: device=/dev/%s partition=%s filesystem=%s "
                    "mountpoint=%s writable=%s free_bytes=%d",
                    current_disk.name,
                    candidate.partition,
                    candidate.filesystem,
                    candidate.path,
                    writable_path,
                    self._available(writable_path),
                )
                viable.append(replace(candidate, path=writable_path))
        if not viable:
            LOGGER.warning("No writable mountpoint found for %s", disk.name)
            raise MountResolutionError("This device is not mounted.")
        selected = max(
            viable,
            key=lambda candidate: (
                self._available(candidate.path),
                self._priority_score(candidate.path),
            ),
        )
        LOGGER.info(
            "Selected benchmark mountpoint: disk=%s partition=%s path=%s filesystem=%s "
            "free_bytes=%d",
            current_disk.name,
            selected.partition,
            selected.path,
            selected.filesystem,
            self._available(selected.path),
        )
        return selected.path

    def describe(self, path: Path) -> tuple[str, int]:
        """Return filesystem type and available bytes for a resolved path."""
        filesystem = "Unknown"
        matching_mounts = [
            partition
            for partition in self._mount_info()
            if self._is_within(path, Path(partition["target"]))
        ]
        if matching_mounts:
            partition = max(matching_mounts, key=lambda item: len(item["target"]))
            filesystem = partition["fstype"] or filesystem
        available = self._available(path)
        return filesystem, available

    def _current_disk(self, disk: Disk) -> Disk:
        """Refresh the selected disk immediately before resolving its mount."""
        if self.detector is None:
            return disk
        try:
            current = next(
                (item for item in self.detector.detect() if item.name == disk.name), None
            )
        except (OSError, RuntimeError, ValueError) as exc:
            LOGGER.warning("Unable to refresh selected disk %s: %s", disk.name, exc)
            raise MountResolutionError("Unable to refresh this device.") from exc
        if current is None:
            LOGGER.warning("Selected disk disappeared before benchmark: %s", disk.name)
            raise MountResolutionError("This device is not mounted.")
        LOGGER.debug(
            "Current selected disk: device=/dev/%s partitions=%s filesystem=%s mountpoint=%s",
            current.name,
            [partition.name for partition in current.partitions],
            current.filesystem,
            current.mount_point,
        )
        return current

    def _candidates(
        self, disk: Disk, mount_info: list[dict[str, str]] | None = None
    ) -> list[MountCandidate]:
        candidates: dict[tuple[str, str], MountCandidate] = {}
        for partition in disk.partitions:
            self._add_candidate(
                candidates,
                MountCandidate(
                    Path(partition.mount_point), partition.filesystem, partition=partition.name
                ),
            )
        partition_mountpoints = {
            partition.mount_point
            for partition in disk.partitions
            if partition.mount_point not in self._placeholders
        }
        if disk.mount_point not in partition_mountpoints:
            self._add_candidate(
                candidates,
                MountCandidate(Path(disk.mount_point), disk.filesystem, partition=disk.name),
            )
        else:
            LOGGER.debug(
                "Ignoring parent mount candidate: device=/dev/%s mountpoint=%s "
                "reason=partition owns mountpoint",
                disk.name,
                disk.mount_point,
            )
        known_mounts = {
            partition.name: partition.mount_point
            for partition in disk.partitions
            if partition.mount_point not in self._placeholders
        }
        if disk.mount_point not in self._placeholders:
            known_mounts[disk.name] = disk.mount_point
        for record in mount_info or []:
            source = record["source"]
            partition_name = self._matching_partition(source, disk)
            if partition_name is None:
                continue
            if partition_name in known_mounts:
                LOGGER.debug(
                    "Ignoring duplicate mount record: partition=%s lsblk_mountpoint=%s "
                    "findmnt_mountpoint=%s",
                    partition_name,
                    known_mounts[partition_name],
                    record["target"],
                )
                continue
            candidate = MountCandidate(
                Path(record["target"]),
                record["fstype"] or "Unknown",
                record["options"],
                partition_name,
            )
            LOGGER.debug(
                "Discovered mounted partition: device=/dev/%s source=%s filesystem=%s "
                "mountpoint=%s options=%s",
                disk.name,
                source,
                candidate.filesystem,
                candidate.path,
                candidate.options,
            )
            self._add_candidate(candidates, candidate)
        return list(candidates.values())

    def _add_candidate(
        self, candidates: dict[tuple[str, str], MountCandidate], candidate: MountCandidate
    ) -> None:
        if str(candidate.path) in self._placeholders:
            return
        key = (str(candidate.path), candidate.partition)
        candidates[key] = candidate
        LOGGER.debug(
            "Mount candidate: partition=%s filesystem=%s mountpoint=%s options=%s",
            candidate.partition,
            candidate.filesystem,
            candidate.path,
            candidate.options or "--",
        )

    @staticmethod
    def _matching_partition(source: str, disk: Disk) -> str | None:
        """Match a findmnt source to the selected disk or one of its partitions."""
        normalized_source = source.removeprefix("/dev/")
        names = {disk.name, *(partition.name for partition in disk.partitions)}
        if normalized_source in names:
            return normalized_source
        for partition in disk.partitions:
            if partition.uuid and partition.uuid != "--":
                if normalized_source == f"UUID={partition.uuid}":
                    return partition.name
                if normalized_source.endswith(f"/{partition.uuid}"):
                    return partition.name
        return None

    def _is_viable(self, candidate: MountCandidate, mount_options: dict[str, str]) -> bool:
        path = candidate.path
        filesystem = candidate.filesystem.lower().strip()
        if filesystem in self._rejected_filesystems:
            LOGGER.debug(
                "Rejected mount candidate: partition=%s mountpoint=%s reason=filesystem:%s",
                candidate.partition,
                path,
                filesystem,
            )
            return False
        if self._is_rejected_mount(path):
            LOGGER.debug(
                "Rejected mount candidate: partition=%s mountpoint=%s reason=protected path",
                candidate.partition,
                path,
            )
            return False
        if not path.is_dir():
            LOGGER.debug(
                "Rejected mount candidate: partition=%s mountpoint=%s reason=not a directory",
                candidate.partition,
                path,
            )
            return False
        options = candidate.options or mount_options.get(str(path), "")
        if "ro" in {option.strip().lower() for option in options.split(",")}:
            LOGGER.debug(
                "Rejected mount candidate: partition=%s mountpoint=%s reason=read-only options=%s",
                candidate.partition,
                path,
                options,
            )
            return False
        return True

    def _writable_path(self, mountpoint: Path) -> Path | None:
        """Find a writable directory without crossing the selected filesystem."""
        try:
            mount_device = mountpoint.stat().st_dev
        except OSError as exc:
            LOGGER.debug("Rejected mountpoint=%s reason=stat failed: %s", mountpoint, exc)
            return None
        if os.access(mountpoint, os.W_OK):
            LOGGER.debug("Writable mountpoint=%s", mountpoint)
            return mountpoint

        home = Path.home()
        if (
            self._is_within(home, mountpoint)
            and self._same_device(home, mount_device)
            and os.access(home, os.W_OK)
        ):
            LOGGER.debug("Using writable home directory=%s for mountpoint=%s", home, mountpoint)
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
                LOGGER.debug("Using writable child=%s for mountpoint=%s", child, mountpoint)
                return child
            LOGGER.debug("Rejected child directory=%s for mountpoint=%s", child, mountpoint)
        LOGGER.debug("Rejected mountpoint=%s reason=no writable directory", mountpoint)
        return None

    @staticmethod
    def _same_device(path: Path, device: int) -> bool:
        try:
            return path.stat().st_dev == device
        except OSError:
            return False

    def _mount_options(self) -> dict[str, str]:
        return {partition["target"]: partition["options"] for partition in self._mount_info()}

    def _mount_info(self) -> list[dict[str, str]]:
        command = [
            "findmnt",
            "--json",
            "--output",
            "TARGET,FSTYPE,OPTIONS,SOURCE",
        ]
        LOGGER.debug("Querying mount information: %s", " ".join(command))
        try:
            result = self.runner(command, capture_output=True, text=True, check=False)
            payload = json.loads(result.stdout or "{}")
            records = self._flatten_mounts(payload.get("filesystems", []))
            if records:
                LOGGER.debug("Mount information records=%d", len(records))
                for record in records:
                    LOGGER.debug(
                        "Mount record: source=%s target=%s filesystem=%s options=%s",
                        record["source"],
                        record["target"],
                        record["fstype"],
                        record["options"],
                    )
                return records
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            LOGGER.warning("findmnt unavailable or invalid: %s", exc)
        try:
            records = [
                {
                    "target": partition.mountpoint,
                    "fstype": partition.fstype,
                    "options": partition.opts,
                    "source": partition.device,
                }
                for partition in psutil.disk_partitions(all=True)
            ]
            LOGGER.debug("Mount information fallback records=%d", len(records))
            return records
        except OSError as exc:
            LOGGER.warning("Unable to inspect mounted filesystems: %s", exc)
            return []

    @classmethod
    def _flatten_mounts(cls, values: object) -> list[dict[str, str]]:
        if not isinstance(values, list):
            return []
        records: list[dict[str, str]] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            records.append(
                {
                    "target": str(value.get("target", "")),
                    "fstype": str(value.get("fstype", "")),
                    "options": str(value.get("options", "")),
                    "source": str(value.get("source", "")),
                }
            )
            records.extend(cls._flatten_mounts(value.get("children", [])))
        return [record for record in records if record["target"]]

    def _priority_score(self, path: Path) -> tuple[int, int, str]:
        normalized = str(path)
        for index, prefix in enumerate(self._priority):
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                return -index, -len(normalized), normalized
        return -len(self._priority), -len(normalized), normalized

    @staticmethod
    def _available(path: Path) -> int:
        try:
            stats = os.statvfs(path)
            return stats.f_bavail * stats.f_frsize
        except OSError:
            return 0

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
