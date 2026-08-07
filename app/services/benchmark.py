"""Safe fio benchmark execution."""

import json
import logging
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Any

from app.config import AppConfig
from app.models.benchmark import (
    BENCHMARK_SPECS,
    BenchmarkResult,
    BenchmarkSpec,
    DiskBenchmarkResults,
)
from app.models.disk import Disk

LOGGER = logging.getLogger(__name__)
Runner = Callable[..., subprocess.CompletedProcess[str]]
ProgressCallback = Callable[[str, int, int, BenchmarkResult | None], None]


class BenchmarkError(RuntimeError):
    """Raised for a safe, user-actionable benchmark failure."""


class FioBenchmarkService:
    """Execute fio workloads against temporary files only."""

    def __init__(
        self,
        config: AppConfig | None = None,
        runner: Runner = subprocess.run,
    ) -> None:
        self.config = config or AppConfig()
        self.runner = runner

    def benchmark_disk(
        self,
        disk: Disk,
        progress: ProgressCallback | None = None,
        cancel_event: Event | None = None,
    ) -> DiskBenchmarkResults:
        """Run all supported tests sequentially for one mounted disk."""
        mount_point = self._mount_point(disk)
        self._verify_space(mount_point)
        results = DiskBenchmarkResults(
            disk_name=disk.name,
            model=disk.model,
            serial=disk.serial,
            capacity=disk.capacity,
        )

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=".diskbench-",
                suffix=".fio",
                dir=mount_point,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)

            total = len(BENCHMARK_SPECS)
            for index, spec in enumerate(BENCHMARK_SPECS, start=1):
                if cancel_event is not None and cancel_event.is_set():
                    raise BenchmarkError("Benchmark cancelled by user")
                if progress is not None:
                    progress(spec.test.value, index - 1, total, None)
                result = self._run_test(temporary_path, spec)
                results.results.append(result)
                if progress is not None:
                    progress(spec.test.value, index, total, result)
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError as exc:
                    LOGGER.warning(
                        "Unable to remove temporary benchmark file %s: %s",
                        temporary_path,
                        exc,
                    )

        return results

    def _run_test(self, filename: Path, spec: BenchmarkSpec) -> BenchmarkResult:
        command = [
            self.config.fio_binary,
            "--name=diskbench",
            f"--filename={filename}",
            f"--rw={spec.read_write}",
            f"--bs={spec.block_size}",
            f"--size={self.config.benchmark_file_size_bytes}",
            "--direct=1",
            "--ioengine=libaio",
            "--iodepth=16",
            "--numjobs=1",
            "--group_reporting=1",
            "--output-format=json",
            f"--runtime={self.config.benchmark_runtime_seconds}",
            "--time_based=1",
        ]
        LOGGER.info("Running fio workload: %s", " ".join(command))
        try:
            completed = self.runner(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            LOGGER.warning("fio unavailable: %s", exc)
            return BenchmarkResult(test=spec.test, error=str(exc))

        if completed.returncode != 0:
            error = completed.stderr.strip() or f"fio exited with {completed.returncode}"
            LOGGER.warning("fio workload failed: %s", error)
            return BenchmarkResult(test=spec.test, error=error)

        try:
            payload = json.loads(completed.stdout or "{}")
            return self._parse_result(spec, payload)
        except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            LOGGER.warning("Invalid fio JSON for %s: %s", spec.test, exc)
            return BenchmarkResult(test=spec.test, error=f"Invalid fio output: {exc}")

    @staticmethod
    def _parse_result(spec: BenchmarkSpec, payload: dict[str, Any]) -> BenchmarkResult:
        jobs = payload.get("jobs", [])
        if not jobs or not isinstance(jobs[0], dict):
            raise ValueError("fio output did not contain a job")
        direction = jobs[0].get("read" if spec.read_write in {"read", "randread"} else "write")
        if not isinstance(direction, dict):
            raise ValueError("fio output did not contain direction data")
        latency = direction.get("lat_ns", {}).get("mean", 0)
        return BenchmarkResult(
            test=spec.test,
            throughput_bytes_per_second=float(direction.get("bw_bytes", 0)),
            iops=float(direction.get("iops", 0)),
            latency_ms=float(latency) / 1_000_000,
            duration_seconds=float(direction.get("runtime", 0)) / 1000,
            success=True,
        )

    def _verify_space(self, mount_point: Path) -> None:
        usage = shutil.disk_usage(mount_point)
        if usage.free < self.config.benchmark_minimum_free_space_bytes:
            raise BenchmarkError(
                f"Insufficient free space on {mount_point}: {usage.free} bytes available"
            )

    @staticmethod
    def _mount_point(disk: Disk) -> Path:
        if disk.mount_point in {"", "Unknown", "Not mounted", "--"}:
            raise BenchmarkError(f"{disk.name} has no mounted filesystem")
        path = Path(disk.mount_point)
        if not path.is_dir():
            raise BenchmarkError(f"Mount point does not exist: {path}")
        return path
