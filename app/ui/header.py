"""Dashboard header widget."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label


class HeaderBar(Horizontal):
    """Branding and release information."""

    def compose(self) -> ComposeResult:
        yield Label("DISKBENCH", id="brand")
        yield Label(" STORAGE ANALYSIS  /  v0.1-alpha", id="release")
