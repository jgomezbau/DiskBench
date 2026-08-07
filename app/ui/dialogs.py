"""Device detail modal."""

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from app.models.disk import Disk


class DiskDetailsDialog(ModalScreen[None]):
    """Show every field in the Disk model."""

    def __init__(self, disk: Disk) -> None:
        super().__init__()
        self.disk = disk

    def compose(self) -> ComposeResult:
        yield Container(
            Label(f"DEVICE DETAILS  /  {self.disk.device_path}", id="dialog-title"),
            VerticalScroll(*self._labels()),
            Button("Close  [ESC]", id="close-dialog"),
            id="details-dialog",
        )

    def _labels(self) -> list[Label]:
        values = {
            "Device name": self.disk.name,
            "Device path": self.disk.device_path,
            "Vendor": self.disk.vendor,
            "Model": self.disk.model,
            "Serial": self.disk.serial,
            "Firmware": self.disk.firmware,
            "Capacity": self.disk.capacity,
            "Transport": self.disk.transport,
            "Filesystem": self.disk.filesystem,
            "Mount point": self.disk.mount_point,
            "Rotation": self.disk.rotation.value,
            "Temperature": self.disk.temperature,
            "SMART status": self.disk.smart_status,
            "Benchmark results": (
                str(self.disk.benchmark_results) if self.disk.benchmark_results else "Not available"
            ),
            "Partitions": str(len(self.disk.partitions)),
        }
        return [Label(f"{key:<20} {value}", classes="detail-line") for key, value in values.items()]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-dialog":
            self.dismiss()
