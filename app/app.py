"""Textual composition root."""

from textual.app import App

from app.config import AppConfig
from app.services.benchmark import FioBenchmarkService
from app.services.detect import LsblkDetectionService
from app.services.history import HistoryStore
from app.services.mount import MountResolver
from app.services.nvme import NvmeService
from app.services.smart import SmartService
from app.ui.home import HomeScreen
from app.utils.logger import configure_logging


class DiskBenchApp(App[None]):
    """DiskBench terminal application."""

    TITLE = "DiskBench"
    CSS_PATH = "ui/theme.tcss"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.load()
        configure_logging(self.config.log_directory)
        super().__init__()
        if self.config.theme == "light":
            self.add_class("theme-light")

    def on_mount(self) -> None:
        """Push the dashboard once the app has a running event loop."""
        detector = LsblkDetectionService(self.config)
        benchmark_service = FioBenchmarkService(self.config, mount_resolver=MountResolver(detector))
        history_store = HistoryStore(
            self.config.history_directory,
            self.config.history_retention,
            self.config.output_directory,
        )
        self.push_screen(
            HomeScreen(
                detector,
                SmartService(self.config),
                NvmeService(self.config),
                benchmark_service,
                history_store,
                self.config,
            )
        )
