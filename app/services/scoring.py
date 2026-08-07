"""Transparent benchmark scoring and metric comparison."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.models.benchmark import BenchmarkResult, BenchmarkTest


class ComparisonStatus(StrEnum):
    """Direction of a metric change."""

    IMPROVED = "Improved"
    DECLINED = "Declined"
    UNCHANGED = "Unchanged"


@dataclass(frozen=True, slots=True)
class MetricComparison:
    """Absolute and relative change between two benchmark metrics."""

    metric: str
    previous: float
    current: float
    absolute_difference: float
    percentage_difference: float | None
    status: ComparisonStatus


@dataclass(frozen=True, slots=True)
class BenchmarkAnalysis:
    """Human-readable summary derived from successful workload results."""

    best_metric: str
    worst_metric: str
    average_throughput_mib: float
    average_iops: float
    recommendation: str


class ScoreCalculator:
    """Calculate a reproducible 0–100 score from benchmark results."""

    sequential_baseline_mib = 3500.0
    random_baseline_mib = 1000.0
    iops_baseline = 200_000.0
    latency_ceiling_ms = 10.0

    def calculate(self, results: list[BenchmarkResult]) -> float:
        """Return a weighted score using only successful measurements."""
        successful = [result for result in results if result.success]
        if not successful:
            return 0.0
        sequential = self._average(
            (
                result
                for result in successful
                if result.test in {BenchmarkTest.SEQUENTIAL_READ, BenchmarkTest.SEQUENTIAL_WRITE}
            ),
            lambda result: result.throughput_mib_per_second / self.sequential_baseline_mib,
        )
        random = self._average(
            (
                result
                for result in successful
                if result.test in {BenchmarkTest.RANDOM_READ_4K, BenchmarkTest.RANDOM_WRITE_4K}
            ),
            lambda result: result.throughput_mib_per_second / self.random_baseline_mib,
        )
        iops = self._average(successful, lambda result: result.iops / self.iops_baseline)
        latency = self._average(
            successful,
            lambda result: max(0.0, 1.0 - result.latency_ms / self.latency_ceiling_ms),
        )
        score = (sequential * 35.0) + (random * 35.0) + (iops * 20.0) + (latency * 10.0)
        return round(max(0.0, min(score, 100.0)), 2)

    @staticmethod
    def _average(
        results: Iterable[BenchmarkResult],
        transform: Callable[[BenchmarkResult], float],
    ) -> float:
        values = [min(1.0, max(0.0, transform(result))) for result in results]
        return sum(values) / len(values) if values else 0.0


class ComparisonService:
    """Compare benchmark metrics and classify their direction."""

    def compare(self, metric: str, previous: float, current: float) -> MetricComparison:
        """Compare a metric, treating changes under 0.1% as unchanged."""
        difference = current - previous
        percentage = None if previous == 0 else difference / previous * 100
        if abs(difference) <= max(abs(previous) * 0.001, 0.0001):
            status = ComparisonStatus.UNCHANGED
        elif difference > 0:
            status = ComparisonStatus.IMPROVED
        else:
            status = ComparisonStatus.DECLINED
        return MetricComparison(metric, previous, current, difference, percentage, status)


class BenchmarkAnalysisService:
    """Summarize measurements without coupling analysis to Textual."""

    def analyze(self, results: list[BenchmarkResult]) -> BenchmarkAnalysis:
        """Return best/worst workloads, averages and a practical recommendation."""
        successful = [result for result in results if result.success]
        if not successful:
            return BenchmarkAnalysis("--", "--", 0.0, 0.0, "No successful measurements")
        best = max(successful, key=lambda result: result.throughput_mib_per_second)
        worst = min(successful, key=lambda result: result.throughput_mib_per_second)
        average_throughput = sum(result.throughput_mib_per_second for result in successful) / len(
            successful
        )
        average_iops = sum(result.iops for result in successful) / len(successful)
        if best.throughput_mib_per_second >= 1000:
            recommendation = "Excellent throughput; compare queue depth for saturation."
        elif worst.latency_ms > 10:
            recommendation = "High latency detected; inspect health and background load."
        else:
            recommendation = "Review the detailed workload results before tuning storage."
        return BenchmarkAnalysis(
            best_metric=best.workload_name or best.test.value,
            worst_metric=worst.workload_name or worst.test.value,
            average_throughput_mib=average_throughput,
            average_iops=average_iops,
            recommendation=recommendation,
        )
