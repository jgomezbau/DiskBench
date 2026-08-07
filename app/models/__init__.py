"""Domain models."""

from app.models.benchmark import (
    BENCHMARK_SPECS,
    BenchmarkResult,
    BenchmarkSpec,
    BenchmarkTest,
    DiskBenchmarkResults,
)
from app.models.disk import Disk, HealthStatus, NvmeInfo, Partition, Rotation

__all__ = [
    "BENCHMARK_SPECS",
    "BenchmarkResult",
    "BenchmarkSpec",
    "BenchmarkTest",
    "Disk",
    "DiskBenchmarkResults",
    "HealthStatus",
    "NvmeInfo",
    "Partition",
    "Rotation",
]
