"""Textual composition root."""

from textual.app import App

from app.config import AppConfig
from app.services.detect import LsblkDetectionService
from app.ui.home import HomeScreen
from app.utils.logger import configure_logging


class DiskBenchApp(App[None]):
    """DiskBench terminal application."""

    TITLE = "DiskBench"
    CSS_PATH = "ui/theme.tcss"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
        configure_logging(self.config.log_directory)
        super().__init__()

    def on_mount(self) -> None:
        """Push the dashboard once the app has a running event loop."""
        detector = LsblkDetectionService(self.config)
        self.push_screen(HomeScreen(detector))
