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
