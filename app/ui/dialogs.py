"""Grouped device detail modal."""

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from app.models.disk import Disk, NvmeInfo
from app.ui.footer import FooterBar
from app.ui.widgets import StorageTable


class BenchmarkProfileDialog(ModalScreen[str | None]):
    """Choose an existing benchmark profile before opening the queue."""

    BINDINGS = [("escape", "close", "Close"), ("q", "close", "Back")]

    def __init__(self, current_profile: str = "Standard") -> None:
        super().__init__()
        self.current_profile = current_profile

    def compose(self) -> ComposeResult:
        profiles = ("Quick", "Standard", "Extended", "Custom")
        yield Container(
            Label("SELECT BENCHMARK PROFILE", id="profile-dialog-title"),
            Label("Choose a workload profile to start the selected disk queue."),
            *(
                Button(
                    f"{profile}{'  (current)' if profile == self.current_profile else ''}",
                    id=f"profile-{profile.lower()}",
                    variant="primary" if profile == self.current_profile else "default",
                )
                for profile in profiles
            ),
            Label("ESC Cancel", id="profile-dialog-shortcut"),
            FooterBar("ESC Back   Q Back   ENTER Select   TAB Next option"),
            id="profile-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("profile-"):
            self.dismiss(event.button.id.removeprefix("profile-").title())

    def action_close(self) -> None:
        """Return to Home without starting a benchmark."""
        self.dismiss(None)


class DetailValue(Label):
    """Label exposing a plain-text value for tests and live updates."""

    @property
    def text(self) -> str:
        """Return the currently rendered value as plain text."""
        value = self.renderable
        return value.plain if isinstance(value, Text) else str(value)

    def set_value(self, value: str) -> None:
        """Update the value while preserving Rich styling."""
        self.update(Text(value, style="#d8dee9"))


class DiskDetailsDialog(ModalScreen[None]):
    """Show hardware, filesystem, SMART, health, NVMe, and partition data."""

    BINDINGS = [("escape", "close", "Close"), ("q", "close", "Back")]

    def __init__(self, disk: Disk, focus_target: StorageTable) -> None:
        super().__init__()
        self.disk = disk
        self.focus_target = focus_target
        self.vendor = DetailValue(Text(self._display(disk.vendor), style="#d8dee9"))
        self.model = DetailValue(Text(self._display(disk.model), style="#d8dee9"))
        self.filesystem = DetailValue(Text(self._display(disk.filesystem), style="#d8dee9"))
        self.mount_point = DetailValue(Text(self._display(disk.mount_point), style="#d8dee9"))
        self._live_values: dict[str, DetailValue] = {
            "Vendor": self.vendor,
            "Model": self.model,
            "Filesystem": self.filesystem,
            "Mount point": self.mount_point,
        }

    def compose(self) -> ComposeResult:
        yield Container(
            Label(f"DEVICE DETAILS  /  {self.disk.device_path}", id="dialog-title"),
            VerticalScroll(*self._sections()),
            Label("ESC Back", id="dialog-shortcut"),
            FooterBar("ESC Back   Q Back"),
            Button("Close  [ESC]", variant="primary", id="close-dialog"),
            id="details-dialog",
        )

    def _sections(self) -> list[Container]:
        sections: list[tuple[str, list[tuple[str, str | DetailValue]]]] = [
            (
                "GENERAL",
                [
                    ("Device", self.disk.device_path),
                    ("Device type", self.disk.device_type),
                    ("Vendor", self.vendor),
                    ("Model", self.model),
                    ("Serial number", self.disk.serial_number),
                    ("Firmware version", self.disk.firmware_version),
                    ("Bus", self.disk.bus),
                    ("Interface", self.disk.interface),
                    ("Transport", self.disk.transport),
                    ("Removable", self._boolean(self.disk.removable)),
                ],
            ),
            (
                "STORAGE",
                [
                    ("Capacity", self.disk.capacity),
                    ("Logical sector", self.disk.logical_sector_size),
                    ("Physical sector", self.disk.physical_sector_size),
                    ("Rotational", self._boolean(self.disk.rotational)),
                    ("TRIM support", self.disk.trim_support),
                    ("Partition table", self.disk.partition_table),
                ],
            ),
            (
                "FILESYSTEM",
                [
                    ("Filesystem", self.filesystem),
                    ("Mount point", self.mount_point),
                    ("UUID", self.disk.uuid),
                ],
            ),
            (
                "SMART",
                [
                    ("Supported", self._boolean(self.disk.smart_supported)),
                    ("Enabled", self._boolean(self.disk.smart_enabled)),
                    ("Overall health", self.disk.smart_overall_health.value),
                    ("Temperature", self.disk.temperature),
                    ("Power-on hours", self.disk.power_on_hours),
                    ("Power cycles", self.disk.power_cycles),
                ],
            ),
            (
                "HEALTH",
                [("Status", self.disk.smart_overall_health.value)],
            ),
        ]
        nvme = self.disk.nvme or NvmeInfo()
        sections.append(
            (
                "NVMe",
                [
                    ("PCIe generation", nvme.pcie_generation),
                    ("PCIe width", nvme.pcie_width),
                    ("NVMe version", nvme.nvme_version),
                    ("Namespace count", nvme.namespace_count),
                    ("Controller model", nvme.controller_model),
                    ("Controller ID", nvme.controller_id),
                    ("Critical warnings", nvme.critical_warnings),
                    ("Percentage used", nvme.percentage_used),
                    ("Media errors", nvme.media_errors),
                    ("Unsafe shutdowns", nvme.unsafe_shutdowns),
                    ("Available spare", nvme.available_spare),
                ],
            )
        )
        sections.append(
            (
                "PARTITION TABLE",
                [
                    (
                        partition.name,
                        f"{partition.filesystem}  {partition.mount_point}  {partition.uuid}",
                    )
                    for partition in self.disk.partitions
                ]
                or [("Partitions", "None detected")],
            )
        )
        return [self._section(title, values) for title, values in sections]

    def _section(self, title: str, values: list[tuple[str, str | DetailValue]]) -> Container:
        return Container(
            Label(title, classes="detail-section-title"),
            *(
                Horizontal(
                    Label(Text(key, style="bold #83d6c5"), classes="detail-key"),
                    self._value_widget(key, value),
                    classes="detail-row",
                )
                for key, value in values
            ),
            classes="detail-section",
        )

    @staticmethod
    def _boolean(value: bool | None) -> str:
        if value is None:
            return "Unknown"
        return "Yes" if value else "No"

    @staticmethod
    def _display(value: str) -> str:
        normalized = value.strip()
        return normalized if normalized else "--"

    def _value_widget(self, key: str, value: str | DetailValue) -> DetailValue:
        if isinstance(value, DetailValue):
            return value
        if key not in self._live_values:
            self._live_values[key] = DetailValue(Text(value, style="#d8dee9"))
        return self._live_values[key]

    def update_disk(self, disk: Disk) -> None:
        """Refresh fields already visible while the dialog remains open."""
        self.disk = disk
        values = {
            "Vendor": disk.vendor,
            "Model": disk.model,
            "Serial number": disk.serial_number,
            "Firmware version": disk.firmware_version,
            "Interface": disk.interface,
            "Transport": disk.transport,
            "Removable": self._boolean(disk.removable),
            "Capacity": disk.capacity,
            "Logical sector": disk.logical_sector_size,
            "Physical sector": disk.physical_sector_size,
            "Rotational": self._boolean(disk.rotational),
            "TRIM support": disk.trim_support,
            "Partition table": disk.partition_table,
            "Filesystem": disk.filesystem,
            "Mount point": disk.mount_point,
            "UUID": disk.uuid,
            "Supported": self._boolean(disk.smart_supported),
            "Enabled": self._boolean(disk.smart_enabled),
            "Overall health": disk.smart_overall_health.value,
            "Status": disk.smart_overall_health.value,
            "Temperature": disk.temperature,
            "Power-on hours": disk.power_on_hours,
            "Power cycles": disk.power_cycles,
        }
        nvme = disk.nvme or NvmeInfo()
        values.update(
            {
                "PCIe generation": nvme.pcie_generation,
                "PCIe width": nvme.pcie_width,
                "NVMe version": nvme.nvme_version,
                "Namespace count": nvme.namespace_count,
                "Controller model": nvme.controller_model,
                "Controller ID": nvme.controller_id,
                "Critical warnings": nvme.critical_warnings,
                "Percentage used": nvme.percentage_used,
                "Media errors": nvme.media_errors,
                "Unsafe shutdowns": nvme.unsafe_shutdowns,
                "Available spare": nvme.available_spare,
            }
        )
        for key, value in values.items():
            self._value_widget(key, value).set_value(self._display(value))

    def action_close(self) -> None:
        """Close the modal and return focus to the previously selected row."""
        self.dismiss()
        self.focus_target.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-dialog":
            self.action_close()
