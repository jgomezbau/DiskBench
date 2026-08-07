"""Dashboard shortcut footer."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label


class FooterBar(Horizontal):
    """Keyboard guidance for the current screen."""

    def __init__(self, shortcuts: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.shortcuts = shortcuts

    def compose(self) -> ComposeResult:
        yield Label(self.shortcuts, id="shortcuts")
