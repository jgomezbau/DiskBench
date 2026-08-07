"""Reusable inventory widgets."""

from collections.abc import Iterable
from typing import Any

from textual.widgets import DataTable, Label

from app.models.disk import Disk


class StorageTable(DataTable[str]):
    """A selectable table of detected physical disks."""

    def __init__(self, disks: Iterable[Disk], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.disks = list(disks)
        self.selected: set[str] = set()
        self.cursor_type = "row"

    def on_mount(self) -> None:
        self.add_column("", key="selected")
        self.add_columns(
            "DEVICE",
            "TYPE",
            "MODEL",
            "CAPACITY",
            "FILESYSTEM",
            "MOUNT POINT",
            "TRANSPORT",
            "STATUS",
        )
        for disk in self.disks:
            self.add_row(*self._row(disk), key=disk.name)
        self.focus()

    def toggle_current(self) -> None:
        if not self.disks or self.cursor_row < 0:
            return
        disk = self.disks[self.cursor_row]
        if disk.name in self.selected:
            self.selected.remove(disk.name)
        else:
            self.selected.add(disk.name)
        self.update_cell(disk.name, "selected", self._checkbox(disk))

    def select_all(self) -> None:
        self.selected = {disk.name for disk in self.disks}
        for disk in self.disks:
            self.update_cell(disk.name, "selected", self._checkbox(disk))

    def clear_selection(self) -> None:
        self.selected.clear()
        for disk in self.disks:
            self.update_cell(disk.name, "selected", self._checkbox(disk))

    def _row(self, disk: Disk) -> tuple[str, ...]:
        return (
            self._checkbox(disk),
            disk.name,
            disk.device_type,
            disk.model,
            disk.capacity,
            disk.filesystem,
            disk.mount_point,
            disk.transport,
            "READY",
        )

    def _checkbox(self, disk: Disk) -> str:
        return "[x]" if disk.name in self.selected else "[ ]"


class EmptyState(Label):
    """Message shown when discovery returns no usable disks."""
