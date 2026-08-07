"""Dashboard shortcut footer."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label


class FooterBar(Horizontal):
    """Keyboard guidance for the current screen."""

    def compose(self) -> ComposeResult:
        yield Label(
            "↑↓ Navigate   SPACE Select   ENTER Details   CTRL+A All   "
            "CTRL+D Clear   B Benchmark   H History   S Settings   E Export   C Compare   "
            "R Refresh   Q Quit   ESC Back",
            id="shortcuts",
        )
