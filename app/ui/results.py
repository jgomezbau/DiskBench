"""Detailed benchmark result screen."""

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Label

from app.models.benchmark import BenchmarkResult, DiskBenchmarkResults
from app.ui.footer import FooterBar
from app.ui.header import HeaderBar
from app.utils.charts import result_charts


class BenchmarkDetailScreen(Screen[None]):
    """Show every collected metric for one benchmark workload."""

    BINDINGS = [("escape", "back", "Back")]

    def __init__(self, disk_results: DiskBenchmarkResults, result: BenchmarkResult) -> None:
        super().__init__()
        self.disk_results = disk_results
        self.result = result

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        yield Container(
            Label("BENCHMARK DETAIL", classes="section-title"),
            Label(
                f"{self.disk_results.disk_name} · {self.disk_results.model}",
                classes="section-caption",
            ),
            VerticalScroll(
                *self._metric_labels(),
                Label(f"DiskBench Score: {self.disk_results.overall_score:.2f}/100"),
                Label(self._charts(), id="benchmark-charts"),
            ),
            id="benchmark-detail-content",
        )
        yield FooterBar()

    def _charts(self) -> str:
        return result_charts(
            [
                (
                    self.result.test.value,
                    self.result.throughput_mib_per_second,
                    3500 if "Sequential" in self.result.test.value else 1000,
                    "MiB/s",
                )
            ]
        )

    def _metric_labels(self) -> list[Label]:
        labels: list[Label] = []
        for result in self.disk_results.results:
            labels.extend(
                [
                    Label(f"Test: {result.test.value}"),
                    Label(f"Throughput: {result.throughput_mib_per_second:.2f} MiB/s"),
                    Label(f"IOPS: {result.iops:.2f}"),
                    Label(f"Latency: {result.latency_ms:.2f} ms"),
                    Label(f"Duration: {result.duration_seconds:.2f} s"),
                    Label(f"Status: {'OK' if result.success else result.error}"),
                    Label(""),
                ]
            )
        return labels

    def action_back(self) -> None:
        self.app.pop_screen()
