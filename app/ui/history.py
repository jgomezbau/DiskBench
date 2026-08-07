"""Benchmark history and comparison screen."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Label

from app.services.export import HistoryExporter
from app.services.history import HistoryStore
from app.ui.footer import FooterBar
from app.ui.header import HeaderBar


class HistoryScreen(Screen[None]):
    """Display persisted benchmark executions."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("e", "export", "Export"),
        ("c", "compare", "Compare"),
    ]

    def __init__(self, store: HistoryStore) -> None:
        super().__init__()
        self.store = store
        self.records = store.list_runs()

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        yield Container(
            Label("BENCHMARK HISTORY", classes="section-title"),
            Label("E export · C compare selected history entries", classes="section-caption"),
            DataTable(id="history-table"),
            Label("", id="history-message"),
            id="history-content",
        )
        yield FooterBar()

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("DATE", "DISK", "MODEL", "SERIAL", "CAPACITY", "SCORE")
        for record in self.records:
            table.add_row(
                str(record.get("completed_at", "--")),
                str(record.get("disk", "--")),
                str(record.get("model", "--")),
                str(record.get("serial", "--")),
                str(record.get("capacity", "--")),
                f"{self._score(record.get('overall_score', 0)):.1f}",
            )

    def action_export(self) -> None:
        for file_format in ("json", "csv", "md", "html"):
            HistoryExporter.export(self.records, self.store.directory, file_format)
        self.query_one("#history-message", Label).update(
            f"Exported reports to {self.store.directory}"
        )

    def action_compare(self) -> None:
        table = self.query_one("#history-table", DataTable)
        if not self.records:
            return
        record = self.records[table.cursor_row]
        previous = next(
            (
                candidate
                for candidate in self.records[table.cursor_row + 1 :]
                if candidate.get("disk") == record.get("disk")
            ),
            None,
        )
        if previous is None:
            self.query_one("#history-message", Label).update(
                "No previous run exists for the selected disk"
            )
            return
        self.app.push_screen(HistoryComparisonScreen(record, previous))

    def action_back(self) -> None:
        self.app.pop_screen()

    @staticmethod
    def _score(value: object) -> float:
        score = HistoryComparisonScreen._to_float(value)
        return score if score is not None else 0.0


class HistoryComparisonScreen(Screen[None]):
    """Compare a selected run with the previous run for the same disk."""

    BINDINGS = [("escape", "back", "Back")]

    def __init__(self, current: dict[str, object], previous: dict[str, object]) -> None:
        super().__init__()
        self.current = current
        self.previous = previous

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        yield Container(
            Label("BENCHMARK COMPARISON", classes="section-title"),
            Label(str(self.current.get("disk", "--")), classes="section-caption"),
            DataTable(id="comparison-table"),
            id="comparison-content",
        )
        yield FooterBar()

    def on_mount(self) -> None:
        table = self.query_one("#comparison-table", DataTable)
        table.add_columns("METRIC", "PREVIOUS", "CURRENT", "CHANGE")
        for key in ("completed_at", "model", "serial", "capacity", "overall_score"):
            previous = self.previous.get(key, "--")
            current = self.current.get(key, "--")
            change = self._change(previous, current) if key == "overall_score" else "--"
            table.add_row(key.replace("_", " ").title(), str(previous), str(current), change)

    @staticmethod
    def _change(previous: object, current: object) -> str:
        old = HistoryComparisonScreen._to_float(previous)
        new = HistoryComparisonScreen._to_float(current)
        if old is None or new is None:
            return "--"
        if old == 0:
            return "--"
        return f"{((new - old) / old) * 100:+.1f}%"

    @staticmethod
    def _to_float(value: object) -> float | None:
        if isinstance(value, (int, float, str)):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    def action_back(self) -> None:
        self.app.pop_screen()
