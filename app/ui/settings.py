"""Persistent application settings dialog."""

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from app.config import AppConfig
from app.ui.footer import FooterBar

LOGGER = logging.getLogger(__name__)


class SettingsDialog(ModalScreen[None]):
    """Edit benchmark, storage and presentation settings."""

    BINDINGS = [("escape", "close", "Close"), ("q", "close", "Back")]

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield Container(
            Label("DISKBENCH SETTINGS", id="settings-title"),
            VerticalScroll(
                self._field(
                    "Benchmark file size (bytes)",
                    "file-size",
                    str(self.config.benchmark_file_size_bytes),
                ),
                self._field("Iterations", "iterations", str(self.config.benchmark_iterations)),
                self._field(
                    "Benchmark runtime (seconds)",
                    "runtime",
                    str(self.config.benchmark_runtime_seconds),
                ),
                self._field(
                    "Profile (Quick/Standard/Extended/Custom)",
                    "profile",
                    self.config.benchmark_profile,
                ),
                self._field("Block size", "block-size", self.config.benchmark_block_size),
                self._field("Queue depth", "queue-depth", str(self.config.benchmark_queue_depth)),
                self._field("Jobs", "jobs", str(self.config.benchmark_num_jobs)),
                self._field(
                    "Direct I/O (true/false)",
                    "direct-io",
                    str(self.config.benchmark_direct_io).lower(),
                ),
                self._field(
                    "Async I/O (true/false)",
                    "async-io",
                    str(self.config.benchmark_async_io).lower(),
                ),
                self._field(
                    "Verify data (true/false)", "verify", str(self.config.benchmark_verify).lower()
                ),
                self._field("Output directory", "output", str(self.config.output_directory)),
                self._field("History directory", "history", str(self.config.history_directory)),
                self._field("History retention", "retention", str(self.config.history_retention)),
                self._field("Theme (dark/light)", "theme", self.config.theme),
            ),
            Label("Settings are persisted as JSON and used after restart", id="settings-hint"),
            FooterBar("ESC Back   Q Back   TAB Next option   ENTER Save"),
            Horizontal(
                Button("Save", variant="primary", id="save-settings"),
                Button("Cancel [ESC]", id="cancel-settings"),
                id="settings-actions",
            ),
            Label("", id="settings-message"),
            id="settings-dialog",
        )

    @staticmethod
    def _field(label: str, field_id: str, value: str) -> Container:
        return Container(
            Label(label, classes="settings-label"),
            Input(value=value, id=f"settings-{field_id}"),
            classes="settings-field",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-settings":
            self._save()
        elif event.button.id == "cancel-settings":
            self.action_close()

    def _save(self) -> None:
        try:
            file_size = self._positive_int("file-size")
            iterations = self._positive_int("iterations")
            runtime = self._positive_int("runtime")
            queue_depth = self._positive_int("queue-depth")
            jobs = self._positive_int("jobs")
            profile = self._profile()
            block_size = self._non_empty("block-size")
            direct_io = self._boolean("direct-io")
            async_io = self._boolean("async-io")
            verify = self._boolean("verify")
            retention = self._positive_int("retention")
            output = self._path("output")
            history = self._path("history")
            theme = self._theme()
        except ValueError as exc:
            self.query_one("#settings-message", Label).update(str(exc))
            return

        updated = replace(
            self.config,
            benchmark_file_size_bytes=file_size,
            benchmark_iterations=iterations,
            benchmark_runtime_seconds=runtime,
            benchmark_profile=profile,
            benchmark_block_size=block_size,
            benchmark_queue_depth=queue_depth,
            benchmark_num_jobs=jobs,
            benchmark_direct_io=direct_io,
            benchmark_async_io=async_io,
            benchmark_verify=verify,
            output_directory=output,
            history_directory=history,
            history_retention=retention,
            theme=theme,
        )
        try:
            updated.save()
        except OSError as exc:
            LOGGER.exception("Unable to save settings")
            self.query_one("#settings-message", Label).update(f"Unable to save settings: {exc}")
            return
        application = cast(Any, self.app)
        application.config = updated
        application.remove_class("theme-light")
        if theme == "light":
            application.add_class("theme-light")
        self.app.notify("Settings saved; restart DiskBench to apply all changes")
        self.dismiss()

    def _positive_int(self, field_id: str) -> int:
        raw = self.query_one(f"#settings-{field_id}", Input).value.strip()
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{field_id} must be a positive integer") from exc
        if value <= 0:
            raise ValueError(f"{field_id} must be a positive integer")
        return value

    def _path(self, field_id: str) -> Path:
        raw = self.query_one(f"#settings-{field_id}", Input).value.strip()
        if not raw:
            raise ValueError(f"{field_id} directory cannot be empty")
        return Path(raw).expanduser()

    def _theme(self) -> str:
        theme = self.query_one("#settings-theme", Input).value.strip().lower()
        if theme not in {"dark", "light"}:
            raise ValueError("theme must be dark or light")
        return theme

    def _profile(self) -> str:
        value = self._non_empty("profile").title()
        if value not in {"Quick", "Standard", "Extended", "Custom"}:
            raise ValueError("profile must be Quick, Standard, Extended or Custom")
        return value

    def _non_empty(self, field_id: str) -> str:
        value = self.query_one(f"#settings-{field_id}", Input).value.strip()
        if not value:
            raise ValueError(f"{field_id} cannot be empty")
        return value

    def _boolean(self, field_id: str) -> bool:
        value = self._non_empty(field_id).lower()
        if value in {"true", "yes", "1", "on"}:
            return True
        if value in {"false", "no", "0", "off"}:
            return False
        raise ValueError(f"{field_id} must be true or false")

    def action_close(self) -> None:
        """Close without changing persisted settings."""
        self.dismiss()
