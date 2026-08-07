"""Grouped device detail modal."""

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from app.models.disk import Disk
from app.ui.widgets import StorageTable


class DiskDetailsDialog(ModalScreen[None]):
    """Show hardware, filesystem, SMART, health, NVMe, and partition data."""

    BINDINGS = [("escape", "close", "Close")]

    def __init__(self, disk: Disk, focus_target: StorageTable) -> None:
        super().__init__()
        self.disk = disk
        self.focus_target = focus_target

    def compose(self) -> ComposeResult:
        yield Container(
            Label(f"DEVICE DETAILS  /  {self.disk.device_path}", id="dialog-title"),
            VerticalScroll(*self._sections()),
            Label("ESC Back", id="dialog-shortcut"),
            Button("Close  [ESC]", variant="primary", id="close-dialog"),
            id="details-dialog",
        )

    def _sections(self) -> list[Container]:
        sections = [
            (
                "GENERAL",
                [
                    ("Device", self.disk.device_path),
                    ("Device type", self.disk.device_type),
                    ("Vendor", self.disk.vendor),
                    ("Model", self.disk.model),
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
                    ("Filesystem", self.disk.filesystem),
                    ("Mount point", self.disk.mount_point),
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
        if self.disk.nvme is not None:
            sections.append(
                (
                    "NVMe",
                    [
                        ("PCIe generation", self.disk.nvme.pcie_generation),
                        ("PCIe width", self.disk.nvme.pcie_width),
                        ("NVMe version", self.disk.nvme.nvme_version),
                        ("Namespace count", self.disk.nvme.namespace_count),
                        ("Controller model", self.disk.nvme.controller_model),
                        ("Controller ID", self.disk.nvme.controller_id),
                        ("Critical warnings", self.disk.nvme.critical_warnings),
                        ("Percentage used", self.disk.nvme.percentage_used),
                        ("Media errors", self.disk.nvme.media_errors),
                        ("Unsafe shutdowns", self.disk.nvme.unsafe_shutdowns),
                        ("Available spare", self.disk.nvme.available_spare),
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

    @staticmethod
    def _section(title: str, values: list[tuple[str, str]]) -> Container:
        return Container(
            Label(title, classes="detail-section-title"),
            *(
                Horizontal(
                    Label(Text(key, style="bold #83d6c5"), classes="detail-key"),
                    Label(Text(value, style="#d8dee9"), classes="detail-value"),
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

    def action_close(self) -> None:
        """Close the modal and return focus to the previously selected row."""
        self.dismiss()
        self.focus_target.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-dialog":
            self.action_close()
