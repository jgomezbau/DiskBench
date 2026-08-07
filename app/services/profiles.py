"""Benchmark profile selection and workload construction."""

from app.config import AppConfig
from app.models.benchmark import (
    BENCHMARK_SPECS,
    BenchmarkProfile,
    BenchmarkSpec,
    BenchmarkTest,
)


class BenchmarkProfileService:
    """Build immutable fio workload lists from user-facing profiles."""

    def workloads(self, config: AppConfig) -> tuple[BenchmarkSpec, ...]:
        """Return the workload sequence configured for the active profile."""
        profile = self._profile(config.benchmark_profile)
        if profile is BenchmarkProfile.QUICK:
            return tuple(spec for spec in BENCHMARK_SPECS[:2])
        if profile is BenchmarkProfile.EXTENDED:
            return self._extended(config)
        return self._standard_or_custom(config)

    @staticmethod
    def _profile(value: str) -> BenchmarkProfile:
        try:
            return BenchmarkProfile(value.title())
        except ValueError:
            return BenchmarkProfile.STANDARD

    @staticmethod
    def _standard_or_custom(config: AppConfig) -> tuple[BenchmarkSpec, ...]:
        if BenchmarkProfileService._profile(config.benchmark_profile) is BenchmarkProfile.STANDARD:
            return tuple(
                BenchmarkSpec(
                    spec.test,
                    spec.read_write,
                    spec.block_size,
                    config.benchmark_queue_depth,
                    config.benchmark_num_jobs,
                )
                for spec in BENCHMARK_SPECS
            )
        return tuple(
            BenchmarkSpec(
                test,
                (
                    "read"
                    if test in {BenchmarkTest.SEQUENTIAL_READ, BenchmarkTest.RANDOM_READ_4K}
                    else "write"
                ),
                config.benchmark_block_size,
                config.benchmark_queue_depth,
                config.benchmark_num_jobs,
                "Custom",
            )
            for test in BenchmarkTest
        )

    @staticmethod
    def _extended(config: AppConfig) -> tuple[BenchmarkSpec, ...]:
        specs: list[BenchmarkSpec] = []
        for queue_depth in (1, config.benchmark_queue_depth, 32):
            for spec in BENCHMARK_SPECS:
                specs.append(
                    BenchmarkSpec(
                        spec.test,
                        spec.read_write,
                        spec.block_size,
                        queue_depth,
                        config.benchmark_num_jobs,
                        f"{spec.test.value} QD{queue_depth}",
                    )
                )
        return tuple(specs)
