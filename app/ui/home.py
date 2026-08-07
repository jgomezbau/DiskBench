"""Main dashboard screen."""

import logging
from dataclasses import replace
from functools import partial

from textual.app import ComposeResult
from textual.containers import Container
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Label

from app.config import AppConfig
from app.models.disk import Disk
from app.services.benchmark import FioBenchmarkService
from app.services.detect import DetectionError, LsblkDetectionService
from app.services.history import HistoryStore
from app.services.nvme import NvmeService
from app.services.smart import SmartService
from app.ui.benchmark import BenchmarkScreen
from app.ui.dialogs import BenchmarkProfileDialog, DiskDetailsDialog
from app.ui.footer import FooterBar
from app.ui.header import HeaderBar
from app.ui.history import HistoryScreen
from app.ui.settings import SettingsDialog
from app.ui.widgets import EmptyState, StorageTable

LOGGER = logging.getLogger(__name__)


class HomeScreen(Screen[None]):
    """Inventory dashboard and keyboard interaction boundary."""

    def __init__(
        self,
        detector: LsblkDetectionService,
        smart_service: SmartService | None = None,
        nvme_service: NvmeService | None = None,
        benchmark_service: FioBenchmarkService | None = None,
        history_store: HistoryStore | None = None,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__()
        self.detector = detector
        self.config = config or AppConfig()
        self.smart_service = smart_service or SmartService()
        self.nvme_service = nvme_service or NvmeService()
        self.benchmark_service = benchmark_service or FioBenchmarkService()
        self.history_store = history_store or HistoryStore(
            self.config.history_directory,
            self.config.history_retention,
            self.config.output_directory,
        )

    def on_mount(self) -> None:
        """Start slow hardware queries after the first table render."""
        self._start_inspection()

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        yield Container(
            Label("PHYSICAL STORAGE", classes="section-title"),
            Label("Select a device to inspect its metadata", classes="section-caption"),
            Label(
                "SPACE Select   ENTER Details   B Benchmark   H History   E Export   "
                "S Settings   R Refresh   Q Quit",
                id="home-actions",
            ),
            Container(self._content(), id="table-host"),
            id="content",
        )
        yield FooterBar()

    def _content(self) -> StorageTable | EmptyState:
        return self._build_content(self._detect())

    def _detect(self) -> list[Disk]:
        """Run detection and convert failures into an empty result for the UI."""
        try:
            return self.detector.detect()
        except DetectionError as exc:
            LOGGER.error("Storage detection failed: %s", exc)
            return []

    def _start_inspection(self) -> None:
        """Inspect current disks in a worker without blocking Textual."""
        tables = self.query("#storage-table")
        if not tables:
            return
        table = tables.first(StorageTable)
        self.run_worker(
            partial(self._inspect_disks, list(table.disks)),
            name="hardware-inspection",
            exclusive=True,
            thread=True,
        )

    def _inspect_disks(self, disks: list[Disk]) -> None:
        """Enrich disks and publish each result back to the UI thread."""
        for disk in disks:
            smart = self.smart_service.inspect(disk.name)
            disk.temperature = smart.temperature
            disk.power_on_hours = smart.power_on_hours
            disk.power_cycles = smart.power_cycles
            disk.smart_supported = smart.supported
            disk.smart_enabled = smart.enabled
            disk.smart_overall_health = smart.health
            if smart.model != "--" and disk.model == "Unknown":
                disk.model = smart.model
            if smart.serial != "--":
                disk.serial = smart.serial
            if smart.firmware != "--":
                disk.firmware = smart.firmware

            nvme = self.nvme_service.inspect(disk.name)
            if nvme is not None:
                disk.nvme = nvme.info
                if nvme.model != "--":
                    disk.model = nvme.model
                if nvme.serial != "--":
                    disk.serial = nvme.serial
                if nvme.firmware != "--":
                    disk.firmware = nvme.firmware
                self._merge_nvme_smart(disk, smart.nvme_data)

            self.app.call_from_thread(self._apply_inspection, disk)

    @staticmethod
    def _merge_nvme_smart(disk: Disk, values: dict[str, str] | None) -> None:
        """Merge NVMe health counters returned by smartctl."""
        if disk.nvme is None or values is None:
            return
        disk.nvme.critical_warnings = values["critical_warnings"]
        disk.nvme.percentage_used = values["percentage_used"]
        disk.nvme.media_errors = values["media_errors"]
        disk.nvme.unsafe_shutdowns = values["unsafe_shutdowns"]
        disk.nvme.available_spare = values["available_spare"]

    def _apply_inspection(self, disk: Disk) -> None:
        """Update the matching row on the Textual event loop."""
        tables = self.query("#storage-table")
        if tables:
            tables.first(StorageTable).update_disk(disk)
        if (
            isinstance(self.app.screen, DiskDetailsDialog)
            and self.app.screen.disk.name == disk.name
        ):
            self.app.screen.update_disk(disk)

    @staticmethod
    def _build_content(disks: list[Disk]) -> StorageTable | EmptyState:
        """Build the appropriate inventory widget for a disk collection."""
        return (
            StorageTable(disks, id="storage-table")
            if disks
            else EmptyState("No physical storage devices detected", id="empty-state")
        )

    async def action_refresh(self) -> None:
        """Re-scan disks and update the mounted inventory."""
        self.smart_service.clear_cache()
        self.nvme_service.clear_cache()
        disks = self._detect()
        tables = self.query("#storage-table")
        if tables:
            table = tables.first(StorageTable)
            if disks:
                table.reload_disks(disks)
                self._start_inspection()
                return
        host = self.query_one("#table-host", Container)
        await host.remove_children()
        await host.mount(self._build_content(disks))
        self._start_inspection()

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
            self.app.push_screen(
                DiskDetailsDialog(table.disks[table.cursor_row], focus_target=table)
            )
            event.stop()
        elif key == "b":
            selected = [disk for disk in table.disks if disk.name in table.selected]
            if selected:
                self.app.push_screen(
                    BenchmarkProfileDialog(self.config.benchmark_profile),
                    callback=partial(self._start_benchmark, selected),
                )
            else:
                self.app.notify("No disk selected.", severity="warning")
            event.stop()
        elif key == "h":
            self.app.push_screen(HistoryScreen(self.history_store))
            event.stop()
        elif key == "s":
            self.app.push_screen(SettingsDialog(self.config))
            event.stop()
        elif key == "e":
            self.app.push_screen(HistoryScreen(self.history_store))
            event.stop()

    def _start_benchmark(self, disks: list[Disk], profile: str | None) -> None:
        """Apply the chosen profile and open the existing benchmark queue."""
        if profile is None:
            return
        self.config = replace(self.config, benchmark_profile=profile)
        self.benchmark_service.config = self.config
        self.app.push_screen(BenchmarkScreen(disks, self.benchmark_service, self.history_store))
