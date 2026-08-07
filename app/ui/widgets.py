"""Reusable inventory widgets."""

from collections.abc import Iterable
from typing import Any

from rich.text import Text, TextType
from textual.widgets import DataTable, Label

from app.models.disk import Disk, HealthStatus


class StorageTable(DataTable[TextType]):
    """A selectable table of detected physical disks."""

    def __init__(
        self,
        disks: Iterable[Disk],
        selected: Iterable[str] | None = None,
        cursor_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.disks = list(disks)
        self.selected: set[str] = set(selected or ()) & {disk.name for disk in self.disks}
        self.cursor_name = cursor_name
        self.cursor_type = "row"

    def on_mount(self) -> None:
        self.add_column("", width=5, key="selected")
        self.add_column("DEVICE", key="device")
        self.add_column("TYPE", key="type")
        self.add_column("MODEL", key="model")
        self.add_column("CAPACITY", key="capacity")
        self.add_column("FILESYSTEM", key="filesystem")
        self.add_column("MOUNT POINT", key="mount_point")
        self.add_column("TRANSPORT", key="transport")
        self.add_column("STATUS", key="status")
        for disk in self.disks:
            self.add_row(*self._row(disk), key=disk.name)
        self._restore_cursor()
        self.focus()

    def reload_disks(self, disks: Iterable[Disk]) -> None:
        """Replace rows while preserving selected devices and cursor where possible."""
        current_name = (
            self.disks[self.cursor_row].name if self.disks and self.cursor_row >= 0 else None
        )
        self.disks = list(disks)
        self.selected.intersection_update(disk.name for disk in self.disks)
        self.clear()
        for disk in self.disks:
            self.add_row(*self._row(disk), key=disk.name)
        self.cursor_name = current_name
        self._restore_cursor()
        self.focus()

    def update_disk(self, disk: Disk) -> None:
        """Refresh one row after background hardware inspection."""
        if disk.name not in {current.name for current in self.disks}:
            return
        for column, value in zip(
            (
                "selected",
                "device",
                "type",
                "model",
                "capacity",
                "filesystem",
                "mount_point",
                "transport",
                "status",
            ),
            self._row(disk),
            strict=True,
        ):
            self.update_cell(disk.name, column, value)

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

    def _row(self, disk: Disk) -> tuple[TextType, ...]:
        return (
            self._checkbox(disk),
            disk.name,
            disk.device_type,
            disk.model,
            disk.capacity,
            disk.filesystem,
            disk.mount_point,
            disk.transport,
            self._status(disk),
        )

    def _checkbox(self, disk: Disk) -> Text:
        """Return a fixed-width Rich checkbox that cannot disappear on update."""
        checked = disk.name in self.selected
        return Text("☑" if checked else "☐", style="bold #83d6c5" if checked else "#8290a5")

    @staticmethod
    def _status(disk: Disk) -> Text:
        """Render the current health state with a visible color indicator."""
        if disk.smart_overall_health is HealthStatus.CRITICAL:
            return Text("● Error", style="bold #e06c75")
        if disk.smart_overall_health is HealthStatus.HEALTHY:
            return Text("● OK", style="bold #98c379")
        if disk.smart_overall_health is HealthStatus.WARNING:
            return Text("● Warning", style="bold #e5c07b")
        return Text("● Unknown", style="bold #e5c07b")

    def _restore_cursor(self) -> None:
        """Restore the previous row when it still exists."""
        if not self.disks:
            return
        if self.cursor_name:
            for index, disk in enumerate(self.disks):
                if disk.name == self.cursor_name:
                    self.move_cursor(row=index)
                    return
        self.move_cursor(row=0)


class EmptyState(Label):
    """Message shown when discovery returns no usable disks."""
