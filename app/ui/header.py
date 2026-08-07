"""Dashboard header widget."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label


class HeaderBar(Horizontal):
    """Branding and release information."""

    def __init__(self, location: str = "Home", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.location = location

    def compose(self) -> ComposeResult:
        yield Label("DISKBENCH", id="brand")
        yield Label(" PROFESSIONAL BENCHMARK ENGINE  /  v0.7", id="release")
        yield Label(f" {self.location}", id="breadcrumb")
