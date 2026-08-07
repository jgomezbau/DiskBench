"""Benchmark history, filters, details and comparison screens."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label

from app.models.benchmark import DiskBenchmarkResults
from app.services.export import HistoryExporter
from app.services.history import HistoryFilter, HistoryStore
from app.services.report import ReportGenerator
from app.services.scoring import ComparisonService, MetricComparison
from app.ui.footer import FooterBar
from app.ui.header import HeaderBar
from app.ui.results import BenchmarkDetailScreen
from app.utils.charts import result_charts


class HistoryScreen(Screen[None]):
    """Display and filter persisted benchmark executions."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("e", "export", "Export"),
        ("c", "compare", "Compare"),
        ("enter", "details", "Details"),
        ("q", "back", "Back"),
        ("n", "rename", "Rename"),
        ("f", "favorite", "Favorite"),
        ("delete", "delete", "Delete"),
    ]

    def __init__(self, store: HistoryStore) -> None:
        super().__init__()
        self.store = store
        self.records: list[dict[str, object]] = []

    def compose(self) -> ComposeResult:
        yield HeaderBar("Home > History")
        yield Container(
            Label("BENCHMARK HISTORY", classes="section-title"),
            Label(
                "Filter by disk, date, model or device · ENTER details · C compare",
                classes="section-caption",
            ),
            Horizontal(
                Input(placeholder="Disk", id="filter-disk"),
                Input(placeholder="Date", id="filter-date"),
                Input(placeholder="Model", id="filter-model"),
                Input(placeholder="Device", id="filter-device"),
                Button("Apply", variant="primary", id="apply-filters"),
                id="history-filters",
            ),
            DataTable(id="history-table"),
            Horizontal(
                Input(placeholder="Session name", id="session-name"),
                Input(placeholder="Notes", id="session-notes"),
                Button("Save metadata", id="save-metadata"),
                id="history-metadata",
            ),
            Label(self._trend_chart(), id="history-chart"),
            Label("", id="history-message"),
            id="history-content",
        )
        yield FooterBar(
            "ENTER Open   ESC Back   Q Back   E Export   C Compare   DEL Delete   F Favorite"
        )

    def on_mount(self) -> None:
        self._render_records(self.store.list_runs())

    def _render_records(self, records: list[dict[str, object]]) -> None:
        self.records = records
        table = self.query_one("#history-table", DataTable)
        table.clear(columns=True)
        table.add_columns("DATE", "DISK", "MODEL", "SERIAL", "CAPACITY", "SCORE", "FAV")
        for record in records:
            table.add_row(
                str(record.get("completed_at", "--")),
                str(record.get("disk", "--")),
                str(record.get("model", "--")),
                str(record.get("serial", "--")),
                str(record.get("capacity", "--")),
                f"{self._score(record.get('overall_score', 0)):.2f}",
                "★" if record.get("favorite") else "",
            )
        self.query_one("#history-chart", Label).update(self._trend_chart())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply-filters":
            self._apply_filters()
        elif event.button.id == "save-metadata":
            self.action_save_metadata()

    def _apply_filters(self) -> None:
        values = {
            field_id: self.query_one(f"#filter-{field_id}", Input).value
            for field_id in ("disk", "date", "model", "device")
        }
        self._render_records(self.store.list_runs(HistoryFilter(**values)))

    def action_export(self) -> None:
        for file_format in ("json", "csv", "md", "html"):
            HistoryExporter.export(self.records, self.store.output_directory, file_format)
        if self.records:
            result = self.store.to_results(self.records[0])
            ReportGenerator().generate_pdf(
                result,
                self.store.output_directory / f"diskbench-report-{result.disk_name}.pdf",
                self.records,
            )
        self.query_one("#history-message", Label).update(
            f"Exported reports to {self.store.output_directory}"
        )

    def action_compare(self) -> None:
        if not self.records:
            return
        table = self.query_one("#history-table", DataTable)
        record = self.records[table.cursor_row]
        previous = next(
            (
                candidate
                for candidate in self.store.list_runs()
                if candidate.get("disk") == record.get("disk")
                and candidate.get("id") != record.get("id")
                and str(candidate.get("completed_at", "")) < str(record.get("completed_at", ""))
            ),
            None,
        )
        if previous is None:
            self.query_one("#history-message", Label).update(
                "No previous run exists for the selected disk"
            )
            return
        self.app.push_screen(
            HistoryComparisonScreen(
                self.store.to_results(record),
                self.store.to_results(previous),
                self.store,
            )
        )

    def action_details(self) -> None:
        if not self.records:
            return
        table = self.query_one("#history-table", DataTable)
        result = self.store.to_results(self.records[table.cursor_row])
        if result.results:
            self.app.push_screen(BenchmarkDetailScreen(result, result.results[0]))

    def _selected_record(self) -> dict[str, object] | None:
        if not self.records:
            return None
        row = self.query_one("#history-table", DataTable).cursor_row
        return self.records[row] if 0 <= row < len(self.records) else None

    def action_rename(self) -> None:
        """Focus the session name editor for the selected run."""
        record = self._selected_record()
        if record is not None:
            self.query_one("#session-name", Input).value = str(record.get("session_name", ""))
            self.query_one("#session-name", Input).focus()

    def action_save_metadata(self) -> None:
        """Persist the selected run's name and notes."""
        record = self._selected_record()
        record_id = self._record_id(record)
        if record is None or record_id is None:
            return
        name = self.query_one("#session-name", Input).value
        notes = self.query_one("#session-notes", Input).value
        self.store.update_metadata(record_id, name, notes, bool(record.get("favorite")))
        self._render_records(self.store.list_runs())
        self.query_one("#history-message", Label).update("Session metadata saved")

    def action_favorite(self) -> None:
        """Toggle the selected run's favorite marker."""
        record = self._selected_record()
        record_id = self._record_id(record)
        if record is None or record_id is None:
            return
        self.store.update_metadata(
            record_id,
            str(record.get("session_name", "")),
            str(record.get("notes", "")),
            not bool(record.get("favorite")),
        )
        self._render_records(self.store.list_runs())

    def action_delete(self) -> None:
        """Delete the selected history run."""
        record = self._selected_record()
        record_id = self._record_id(record)
        if record is None or record_id is None:
            return
        self.store.delete_run(record_id)
        self._render_records(self.store.list_runs())

    @staticmethod
    def _record_id(record: dict[str, object] | None) -> int | None:
        if record is None:
            return None
        value = record.get("id")
        return value if isinstance(value, int) else None

    def _trend_chart(self) -> str:
        if not self.records:
            return "No benchmark history"
        return result_charts(
            (
                f"{record.get('disk', '--')} {record.get('completed_at', '--')}",
                self._score(record.get("overall_score", 0)),
                100,
                "points",
            )
            for record in self.records[:6]
        )

    def action_back(self) -> None:
        self.app.pop_screen()

    @staticmethod
    def _score(value: object) -> float:
        if isinstance(value, (int, float, str)):
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0


class HistoryComparisonScreen(Screen[None]):
    """Compare two benchmark runs and show direction, delta and trend charts."""

    BINDINGS = [("escape", "back", "Back"), ("q", "back", "Back"), ("p", "report", "PDF")]

    def __init__(
        self,
        current: DiskBenchmarkResults,
        previous: DiskBenchmarkResults,
        store: HistoryStore,
    ) -> None:
        super().__init__()
        self.current = current
        self.previous = previous
        self.store = store
        self.comparisons: list[MetricComparison] = []

    def compose(self) -> ComposeResult:
        yield HeaderBar("Home > History > Benchmark Details")
        yield Container(
            Label("BENCHMARK COMPARISON", classes="section-title"),
            Label(f"{self.current.disk_name} · current vs previous", classes="section-caption"),
            DataTable(id="comparison-table"),
            Label(self._trend_chart(), id="comparison-chart"),
            Label("P generates a PDF comparison report", id="comparison-message"),
            id="comparison-content",
        )
        yield FooterBar("ESC Back   Q Back   P PDF")

    def on_mount(self) -> None:
        service = ComparisonService()
        self.comparisons = [
            service.compare(
                "Overall Score", self.previous.overall_score, self.current.overall_score
            )
        ]
        previous_by_test = {result.test: result for result in self.previous.results}
        for result in self.current.results:
            previous = previous_by_test.get(result.test)
            if previous is not None:
                for metric, previous_value, current_value in (
                    (
                        f"{result.test.value} throughput",
                        previous.throughput_mib_per_second,
                        result.throughput_mib_per_second,
                    ),
                    (f"{result.test.value} IOPS", previous.iops, result.iops),
                    (
                        f"{result.test.value} latency",
                        previous.latency_ms,
                        result.latency_ms,
                    ),
                ):
                    self.comparisons.append(service.compare(metric, previous_value, current_value))
        table = self.query_one("#comparison-table", DataTable)
        table.add_columns("METRIC", "PREVIOUS", "CURRENT", "ABSOLUTE", "%", "STATUS")
        for comparison in self.comparisons:
            table.add_row(
                comparison.metric,
                f"{comparison.previous:.2f}",
                f"{comparison.current:.2f}",
                f"{comparison.absolute_difference:+.2f}",
                (
                    "--"
                    if comparison.percentage_difference is None
                    else f"{comparison.percentage_difference:+.2f}%"
                ),
                comparison.status.value,
            )

    def action_report(self) -> None:
        destination = (
            self.store.output_directory / f"diskbench-comparison-{self.current.disk_name}.pdf"
        )
        ReportGenerator().generate_pdf(
            self.current,
            destination,
            self.store.list_runs(),
            self.comparisons,
        )
        self.query_one("#comparison-message", Label).update(f"Generated {destination}")

    def _trend_chart(self) -> str:
        return result_charts(
            [
                ("Previous Score", self.previous.overall_score, 100, "points"),
                ("Current Score", self.current.overall_score, 100, "points"),
            ]
        )

    def action_back(self) -> None:
        self.app.pop_screen()
