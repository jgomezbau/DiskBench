"""Main dashboard screen."""

import logging

from textual.app import ComposeResult
from textual.containers import Container
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Label

from app.services.detect import DetectionError, LsblkDetectionService
from app.ui.dialogs import DiskDetailsDialog
from app.ui.footer import FooterBar
from app.ui.header import HeaderBar
from app.ui.widgets import EmptyState, StorageTable

LOGGER = logging.getLogger(__name__)


class HomeScreen(Screen[None]):
    """Inventory dashboard and keyboard interaction boundary."""

    def __init__(self, detector: LsblkDetectionService) -> None:
        super().__init__()
        self.detector = detector

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        yield Container(
            Label("PHYSICAL STORAGE", classes="section-title"),
            Label("Select a device to inspect its metadata", classes="section-caption"),
            self._content(),
            id="content",
        )
        yield FooterBar()

    def _content(self) -> StorageTable | EmptyState:
        try:
            disks = self.detector.detect()
        except DetectionError as exc:
            LOGGER.error("Storage detection failed: %s", exc)
            return EmptyState(f"Unable to detect storage devices: {exc}", id="empty-state")
        return (
            StorageTable(disks, id="storage-table")
            if disks
            else EmptyState("No physical storage devices detected", id="empty-state")
        )

    def on_key(self, event: Key) -> None:
        key = event.key
        tables = self.query("#storage-table")
        if not tables:
            return
        table = tables.first(StorageTable)
        if key == "space":
            table.toggle_current()
            event.stop()
        elif key == "ctrl+a":
            table.select_all()
            event.stop()
        elif key == "ctrl+d":
            table.clear_selection()
            event.stop()
        elif key == "enter" and 0 <= table.cursor_row < len(table.disks):
            self.app.push_screen(DiskDetailsDialog(table.disks[table.cursor_row]))
            event.stop()
