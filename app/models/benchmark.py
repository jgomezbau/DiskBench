"""Benchmark domain models."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class BenchmarkTest(StrEnum):
    """Supported fio workloads."""

    SEQUENTIAL_READ = "Sequential Read"
    SEQUENTIAL_WRITE = "Sequential Write"
    RANDOM_READ_4K = "Random Read 4K"
    RANDOM_WRITE_4K = "Random Write 4K"


class BenchmarkProfile(StrEnum):
    """Available workload collections."""

    QUICK = "Quick"
    STANDARD = "Standard"
    EXTENDED = "Extended"
    CUSTOM = "Custom"


@dataclass(frozen=True, slots=True)
class BenchmarkSpec:
    """fio parameters for one workload."""

    test: BenchmarkTest
    read_write: str
    block_size: str
    queue_depth: int = 16
    num_jobs: int = 1
    label: str = ""


BENCHMARK_SPECS: tuple[BenchmarkSpec, ...] = (
    BenchmarkSpec(BenchmarkTest.SEQUENTIAL_READ, "read", "1M"),
    BenchmarkSpec(BenchmarkTest.SEQUENTIAL_WRITE, "write", "1M"),
    BenchmarkSpec(BenchmarkTest.RANDOM_READ_4K, "randread", "4k"),
    BenchmarkSpec(BenchmarkTest.RANDOM_WRITE_4K, "randwrite", "4k"),
)


@dataclass(slots=True)
class BenchmarkResult:
    """Result for one fio workload."""

    test: BenchmarkTest
    throughput_bytes_per_second: float = 0.0
    iops: float = 0.0
    latency_ms: float = 0.0
    duration_seconds: float = 0.0
    success: bool = False
    error: str = ""
    workload_name: str = ""

    @property
    def throughput_mib_per_second(self) -> float:
        """Return throughput in a user-facing unit."""
        return self.throughput_bytes_per_second / (1024 * 1024)


@dataclass(slots=True)
class DiskBenchmarkResults:
    """All workloads executed for one disk."""

    disk_name: str
    model: str
    serial: str
    capacity: str
    interface: str = "--"
    completed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    duration_seconds: float = 0.0
    score: float = 0.0
    session_name: str = ""
    notes: str = ""
    favorite: bool = False
    results: list[BenchmarkResult] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """Return the score calculated by the scoring service."""
        return self.score
