"""Benchmark queue and progress screen."""

import json
import logging
import sqlite3
import time
from dataclasses import asdict
from functools import partial
from threading import Event

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Button, DataTable, Label, ProgressBar

from app.models.benchmark import BenchmarkResult, BenchmarkTest, DiskBenchmarkResults
from app.models.disk import Disk
from app.services.benchmark import BenchmarkError, FioBenchmarkService
from app.services.export import HistoryExporter
from app.services.history import HistoryStore
from app.services.report import ReportGenerator
from app.services.scoring import BenchmarkAnalysisService
from app.ui.footer import FooterBar
from app.ui.header import HeaderBar
from app.ui.results import BenchmarkDetailScreen
from app.utils.charts import result_charts

LOGGER = logging.getLogger(__name__)


class BenchmarkScreen(Screen[None]):
    """Run selected disks sequentially in a background worker."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("p", "pause_resume", "Pause/Resume"),
        ("x", "skip", "Skip"),
        ("t", "retry", "Retry"),
        ("q", "back", "Back"),
    ]

    def __init__(
        self,
        disks: list[Disk],
        benchmark_service: FioBenchmarkService,
        history_store: HistoryStore,
    ) -> None:
        super().__init__()
        self.disks = disks
        self.benchmark_service = benchmark_service
        self.history_store = history_store
        self.cancel_event = Event()
        self.pause_event = Event()
        self.pause_event.set()
        self.skip_event = Event()
        self.retry_event = Event()
        self.completed_results: list[DiskBenchmarkResults] = []
        self.started_at = 0.0
        self.queue_started = False

    def compose(self) -> ComposeResult:
        yield HeaderBar("Home > Benchmark")
        yield Container(
            Label("BENCHMARK ENGINE", classes="section-title"),
            Label("Temporary files only · sequential disk queue", classes="section-caption"),
            Label("Preparing benchmark queue", id="benchmark-current"),
            Label("Remaining disks: --", id="benchmark-remaining"),
            ProgressBar(total=100, show_eta=False, id="benchmark-progress"),
            Label("Elapsed: --   Estimated remaining: --", id="benchmark-timing"),
            Label("Current metrics: --", id="benchmark-metrics"),
            Label("Live chart: --", id="benchmark-chart"),
            Container(
                Button("Pause [P]", id="pause-benchmark"),
                Button("Skip [X]", id="skip-benchmark"),
                Button("Retry [T]", id="retry-benchmark"),
                Button("Cancel benchmark [ESC]", id="cancel-benchmark"),
                id="benchmark-actions",
            ),
            id="benchmark-content",
        )
        yield FooterBar("ESC Cancel   Q Back")

    def on_mount(self) -> None:
        """Start the queue after the progress screen has rendered."""
        self.started_at = time.monotonic()
        if not self.benchmark_service.is_available():
            message = (
                f"fio is not installed or unavailable: {self.benchmark_service.config.fio_binary}"
            )
            LOGGER.warning(message)
            self._show_message(message)
            self.query_one("#cancel-benchmark", Button).label = "Close [ESC]"
            return
        LOGGER.info("Benchmark queue started for %d disk(s)", len(self.disks))
        self.queue_started = True
        self.run_worker(self._run_queue, name="benchmark-queue", exclusive=True, thread=True)

    def _run_queue(self) -> None:
        total = len(self.disks)
        disk_index = 0
        while disk_index < total:
            self.pause_event.wait()
            if self.cancel_event.is_set():
                break
            disk = self.disks[disk_index]
            if self.skip_event.is_set():
                self.skip_event.clear()
                disk_index += 1
                continue
            try:
                results = self.benchmark_service.benchmark_disk(
                    disk,
                    progress=partial(self._progress, disk_index, total, disk.name),
                    cancel_event=self.cancel_event,
                )
            except BenchmarkError as exc:
                LOGGER.warning("Benchmark refused for %s: %s", disk.name, exc)
                results = self._failed_results(disk, str(exc))
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Unexpected benchmark failure for %s", disk.name)
                results = self._failed_results(disk, f"Unexpected failure: {exc}")

            if self.retry_event.is_set() and not self.cancel_event.is_set():
                self.retry_event.clear()
                continue
            if self.skip_event.is_set():
                self.skip_event.clear()
                disk_index += 1
                continue

            self.completed_results.append(results)
            try:
                self.history_store.save(results)
            except (OSError, ValueError, sqlite3.Error) as exc:
                LOGGER.exception("Unable to save benchmark history for %s", disk.name)
                self.app.call_from_thread(self._show_message, f"History save failed: {exc}")
            disk_index += 1

        self.app.call_from_thread(self._finish, self.cancel_event.is_set())

    def _progress(
        self,
        disk_index: int,
        disk_count: int,
        disk_name: str,
        operation: str,
        completed_tests: int,
        total_tests: int,
        result: BenchmarkResult | None,
    ) -> None:
        overall = (
            ((disk_index * total_tests) + completed_tests)
            / max(
                disk_count * total_tests,
                1,
            )
            * 100
        )
        self.app.call_from_thread(
            self._render_progress,
            overall,
            disk_name,
            operation,
            completed_tests,
            total_tests,
            result,
        )

    def _render_progress(
        self,
        overall: float,
        disk_name: str,
        operation: str,
        completed_tests: int,
        total_tests: int,
        result: BenchmarkResult | None,
    ) -> None:
        self.query_one("#benchmark-progress", ProgressBar).update(progress=overall)
        self.query_one("#benchmark-current", Label).update(f"{disk_name} · {operation}")
        remaining = max(len(self.disks) - len(self.completed_results) - 1, 0)
        self.query_one("#benchmark-remaining", Label).update(
            f"Remaining disks: {remaining} · Completed {completed_tests}/{total_tests}"
        )
        elapsed = time.monotonic() - self.started_at
        estimate = "--" if overall <= 0 else f"{elapsed * (100 / overall - 1):.0f}s"
        self.query_one("#benchmark-timing", Label).update(
            f"Elapsed: {elapsed:.0f}s   Estimated remaining: {estimate}"
        )
        metrics = "Current metrics: --"
        if result is not None and result.success:
            metrics = f"Latency: {result.latency_ms:.2f} ms · IOPS: {result.iops:.0f}"
        self.query_one("#benchmark-metrics", Label).update(metrics)
        if result is not None:
            if result.success:
                throughput = f"{result.throughput_mib_per_second:.1f} MiB/s"
                self.query_one("#benchmark-current", Label).update(
                    f"{disk_name} · {operation} · {throughput} · {result.iops:.0f} IOPS"
                )
                self.query_one("#benchmark-chart", Label).update(
                    result_charts([(operation, result.throughput_mib_per_second, 3500, "MiB/s")])
                )
            else:
                self.query_one("#benchmark-current", Label).update(
                    f"{disk_name} · {operation} · {result.error}"
                )

    def _finish(self, cancelled: bool) -> None:
        """Open the result screen after the worker has stopped."""
        self.queue_started = False
        if cancelled:
            LOGGER.info("Benchmark queue cancelled")
            self.app.pop_screen()
            return
        else:
            LOGGER.info("Benchmark queue completed")
        self.app.push_screen(BenchmarkResultsScreen(self.completed_results, self.history_store))

    def _show_message(self, message: str) -> None:
        self.query_one("#benchmark-current", Label).update(message)

    @staticmethod
    def _failed_results(disk: Disk, message: str) -> DiskBenchmarkResults:
        return DiskBenchmarkResults(
            disk_name=disk.name,
            model=disk.model,
            serial=disk.serial,
            capacity=disk.capacity,
            interface=disk.interface,
            results=[BenchmarkResult(test=test, error=message) for test in BenchmarkTest],
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-benchmark":
            self.action_cancel()
        elif event.button.id == "pause-benchmark":
            self.action_pause_resume()
        elif event.button.id == "skip-benchmark":
            self.action_skip()
        elif event.button.id == "retry-benchmark":
            self.action_retry()

    def action_cancel(self) -> None:
        """Request cancellation without interrupting a running fio process."""
        if not self.queue_started:
            self.app.pop_screen()
            return
        LOGGER.info("Benchmark cancellation requested")
        self.cancel_event.set()
        self.pause_event.set()

    def action_back(self) -> None:
        """Cancel safely and return to the previous screen."""
        self.action_cancel()

    def action_pause_resume(self) -> None:
        """Pause or resume at the next safe workload boundary."""
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.query_one("#pause-benchmark", Button).label = "Resume [P]"
        else:
            self.pause_event.set()
            self.query_one("#pause-benchmark", Button).label = "Pause [P]"

    def action_skip(self) -> None:
        """Skip the current disk at the next safe queue boundary."""
        self.skip_event.set()

    def action_retry(self) -> None:
        """Retry the current disk after the active operation completes."""
        self.retry_event.set()


class BenchmarkResultsScreen(Screen[None]):
    """Display completed benchmark results and export shortcuts."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("e", "export", "Export"),
        ("h", "history", "History"),
        ("enter", "details", "Details"),
        ("q", "back", "Back"),
    ]

    def __init__(
        self,
        results: list[DiskBenchmarkResults],
        history_store: HistoryStore,
    ) -> None:
        super().__init__()
        self.results = results
        self.history_store = history_store
        self.row_results: list[tuple[DiskBenchmarkResults, BenchmarkResult]] = []

    def compose(self) -> ComposeResult:
        yield HeaderBar("Home > Benchmark > Results")
        yield Container(
            Label("BENCHMARK RESULTS", classes="section-title"),
            Label("E exports CSV, JSON, Markdown, HTML and PDF", classes="section-caption"),
            DataTable(id="results-table"),
            Label("", id="results-summary"),
            Label(self._charts(), id="results-charts"),
            Label("", id="export-message"),
            id="results-content",
        )
        yield FooterBar("ESC Back   Q Back   E Export   H History   ENTER Details")

    def on_mount(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.add_columns(
            "DISK",
            "MODEL",
            "CAPACITY",
            "INTERFACE",
            "DATE",
            "RUN DURATION",
            "TEST",
            "THROUGHPUT",
            "IOPS",
            "LATENCY",
            "TEST DURATION",
            "SCORE",
        )
        for result in self.results:
            for item in result.results:
                self.row_results.append((result, item))
                table.add_row(
                    result.disk_name,
                    result.model,
                    result.capacity,
                    result.interface,
                    result.completed_at,
                    f"{result.duration_seconds:.1f} s",
                    item.test.value,
                    self._throughput(item),
                    f"{item.iops:.0f}",
                    f"{item.latency_ms:.2f} ms" if item.success else "--",
                    f"{item.duration_seconds:.1f} s" if item.success else "--",
                    f"{result.overall_score:.1f}",
                )
        if self.results:
            analysis = BenchmarkAnalysisService().analyze(
                [item for result in self.results for item in result.results]
            )
            self.query_one("#results-summary", Label).update(
                f"Best: {analysis.best_metric} · Worst: {analysis.worst_metric} · "
                f"Average: {analysis.average_throughput_mib:.1f} MiB/s · "
                f"{analysis.average_iops:.0f} IOPS\nRecommendation: {analysis.recommendation}"
            )

    def _charts(self) -> str:
        if not self.results:
            return "No benchmark data"
        result = self.results[0]
        by_test = {item.test: item for item in result.results if item.success}
        return result_charts(
            [
                (
                    test.value,
                    by_test[test].throughput_mib_per_second if test in by_test else 0,
                    3500 if "Sequential" in test.value else 1000,
                    "MiB/s",
                )
                for test in by_test
            ]
        )

    @staticmethod
    def _throughput(result: BenchmarkResult | None) -> str:
        if result is None or not result.success:
            return result.error if result is not None and result.error else "Error"
        return f"{result.throughput_mib_per_second:.1f} MiB/s"

    def action_export(self) -> None:
        """Export the in-memory result set in every supported report format."""
        records = [
            {
                "disk": result.disk_name,
                "model": result.model,
                "serial": result.serial,
                "capacity": result.capacity,
                "interface": result.interface,
                "completed_at": result.completed_at,
                "duration_seconds": result.duration_seconds,
                "overall_score": result.overall_score,
                "results_json": json.dumps([asdict(item) for item in result.results]),
            }
            for result in self.results
        ]
        directory = self.history_store.output_directory
        destinations = [
            HistoryExporter.export(records, directory, file_format)
            for file_format in ("json", "csv", "md", "html")
        ]
        destinations.extend(
            ReportGenerator().generate_pdf(
                result,
                directory / f"diskbench-report-{result.disk_name}.pdf",
                self.history_store.list_runs(),
            )
            for result in self.results
        )
        LOGGER.info("Exported benchmark results to %s", directory)
        self.query_one("#export-message", Label).update(
            f"Exported {len(destinations)} reports to {directory}"
        )

    def action_history(self) -> None:
        from app.ui.history import HistoryScreen

        self.app.push_screen(HistoryScreen(self.history_store))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_details(self) -> None:
        """Open the selected workload's complete metric view."""
        table = self.query_one("#results-table", DataTable)
        if 0 <= table.cursor_row < len(self.row_results):
            result, item = self.row_results[table.cursor_row]
            self.app.push_screen(BenchmarkDetailScreen(result, item))
