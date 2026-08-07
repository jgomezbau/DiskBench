"""Safe fio benchmark execution."""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Any

from app.config import AppConfig
from app.models.benchmark import (
    BenchmarkResult,
    BenchmarkSpec,
    DiskBenchmarkResults,
)
from app.models.disk import Disk
from app.services.mount import MountResolutionError, MountResolver
from app.services.profiles import BenchmarkProfileService
from app.services.scoring import ScoreCalculator

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
        scorer: ScoreCalculator | None = None,
        profile_service: BenchmarkProfileService | None = None,
        mount_resolver: MountResolver | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.runner = runner
        self.scorer = scorer or ScoreCalculator()
        self.profile_service = profile_service or BenchmarkProfileService()
        self.mount_resolver = mount_resolver or MountResolver()

    def is_available(self) -> bool:
        """Return whether the configured fio executable is available."""
        return shutil.which(self.config.fio_binary) is not None

    def benchmark_disk(
        self,
        disk: Disk,
        progress: ProgressCallback | None = None,
        cancel_event: Event | None = None,
    ) -> DiskBenchmarkResults:
        """Run all supported tests sequentially for one mounted disk."""
        try:
            mount_point = self.mount_resolver.resolve(disk)
        except MountResolutionError as exc:
            raise BenchmarkError(str(exc)) from exc
        self._verify_space(mount_point)
        self._ensure_available()
        LOGGER.info("Benchmark started for %s", disk.name)
        results = DiskBenchmarkResults(
            disk_name=disk.name,
            model=disk.model,
            serial=disk.serial,
            capacity=disk.capacity,
            interface=disk.interface,
        )

        temporary_path: Path | None = None
        started_at = time.monotonic()
        try:
            try:
                with tempfile.NamedTemporaryFile(
                    prefix=".diskbench-",
                    suffix=".fio",
                    dir=mount_point,
                    delete=False,
                ) as temporary_file:
                    temporary_path = Path(temporary_file.name)
            except OSError as exc:
                raise BenchmarkError(
                    f"Unable to create benchmark file on filesystem {mount_point}: {exc}"
                ) from exc

            filesystem, available = self.mount_resolver.describe(mount_point)
            LOGGER.info(
                "Benchmark context: directory=%s filesystem=%s available_bytes=%d "
                "temporary_file=%s",
                mount_point,
                filesystem,
                available,
                temporary_path,
            )
            if progress is not None:
                progress(
                    f"Directory {mount_point} · Filesystem {filesystem} · "
                    f"Available {available} bytes · File {temporary_path}",
                    0,
                    1,
                    None,
                )

            iterations = max(1, self.config.benchmark_iterations)
            specs = self.profile_service.workloads(self.config)
            total = len(specs) * iterations
            completed = 0
            for spec in specs:
                samples: list[BenchmarkResult] = []
                for iteration in range(1, iterations + 1):
                    if cancel_event is not None and cancel_event.is_set():
                        LOGGER.info("Benchmark cancelled for %s", disk.name)
                        raise BenchmarkError("Benchmark cancelled by user")
                    operation = f"{spec.test.value} ({iteration}/{iterations})"
                    if progress is not None:
                        progress(operation, completed, total, None)
                    sample = self._run_test(temporary_path, spec)
                    samples.append(sample)
                    completed += 1
                    result = self._aggregate(spec, samples)
                    if progress is not None:
                        progress(operation, completed, total, result)
                results.results.append(self._aggregate(spec, samples))
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

        results.duration_seconds = time.monotonic() - started_at
        results.score = self.scorer.calculate(results.results)
        LOGGER.info("Benchmark completed for %s with score %.2f", disk.name, results.score)
        return results

    @staticmethod
    def _aggregate(spec: BenchmarkSpec, samples: list[BenchmarkResult]) -> BenchmarkResult:
        """Average repeated measurements while preserving failures."""
        if not samples or not all(sample.success for sample in samples):
            errors = "; ".join(sample.error for sample in samples if sample.error)
            return BenchmarkResult(
                test=spec.test,
                error=errors or "Benchmark failed",
                workload_name=spec.label,
            )
        count = len(samples)
        return BenchmarkResult(
            test=spec.test,
            throughput_bytes_per_second=sum(
                sample.throughput_bytes_per_second for sample in samples
            )
            / count,
            iops=sum(sample.iops for sample in samples) / count,
            latency_ms=sum(sample.latency_ms for sample in samples) / count,
            duration_seconds=sum(sample.duration_seconds for sample in samples),
            success=True,
            workload_name=spec.label,
        )

    def _run_test(self, filename: Path, spec: BenchmarkSpec) -> BenchmarkResult:
        command = [
            self.config.fio_binary,
            "--name=diskbench",
            f"--filename={filename}",
            f"--rw={spec.read_write}",
            f"--bs={spec.block_size}",
            f"--size={self.config.benchmark_file_size_bytes}",
            f"--direct={int(self.config.benchmark_direct_io)}",
            f"--ioengine={'libaio' if self.config.benchmark_async_io else 'sync'}",
            f"--iodepth={spec.queue_depth}",
            f"--numjobs={spec.num_jobs}",
            "--group_reporting=1",
            "--output-format=json",
            f"--runtime={self.config.benchmark_runtime_seconds}",
            "--time_based=1",
        ]
        if self.config.benchmark_verify:
            command.extend(("--verify=crc32c", "--do_verify=1"))
        LOGGER.info(
            "Running fio workload: filesystem=%s benchmark_file=%s command=%s",
            filename.parent,
            filename,
            " ".join(command),
        )
        try:
            completed = self._invoke(command)
        except OSError as exc:
            error = self._error_message(filename, f"Unable to execute fio: {exc}")
            LOGGER.warning(error)
            return BenchmarkResult(test=spec.test, error=error, workload_name=spec.label)

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            LOGGER.warning("fio stderr: %s", stderr or "<empty>")
            LOGGER.debug("fio stdout: %s", completed.stdout.strip() or "<empty>")
            if self._direct_io_unsupported(stderr, self.config.benchmark_direct_io):
                fallback = [
                    "--direct=0" if argument == "--direct=1" else argument for argument in command
                ]
                LOGGER.warning("Direct I/O failed for %s; retrying with buffered I/O", filename)
                try:
                    completed = self._invoke(fallback)
                except OSError as exc:
                    completed = subprocess.CompletedProcess(fallback, 1, "", str(exc))
            if completed.returncode != 0:
                error = completed.stderr.strip() or f"fio exited with {completed.returncode}"
                error = self._error_message(filename, error)
                LOGGER.warning("fio workload failed: %s", error)
                return BenchmarkResult(test=spec.test, error=error, workload_name=spec.label)

        try:
            LOGGER.debug("fio stdout: %s", completed.stdout.strip() or "<empty>")
            LOGGER.debug("fio stderr: %s", completed.stderr.strip() or "<empty>")
            payload = json.loads(completed.stdout or "{}")
            return self._parse_result(spec, payload)
        except (json.JSONDecodeError, TypeError, ValueError, KeyError, AttributeError) as exc:
            LOGGER.warning("Invalid fio JSON for %s: %s", spec.test, exc)
            return BenchmarkResult(
                test=spec.test,
                error=self._error_message(filename, f"Invalid fio output: {exc}"),
                workload_name=spec.label,
            )

    def _invoke(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        """Execute fio with captured streams for diagnostics and parsing."""
        return self.runner(command, capture_output=True, text=True, check=False)

    @staticmethod
    def _direct_io_unsupported(error: str, direct_io: bool) -> bool:
        """Identify errors where buffered I/O is a safe compatibility fallback."""
        if not direct_io:
            return False
        normalized = error.lower()
        return any(
            marker in normalized
            for marker in (
                "direct=",
                "o_direct",
                "direct io",
                "direct i/o",
                "operation not supported",
                "invalid argument",
            )
        )

    @staticmethod
    def _error_message(filename: Path, error: str) -> str:
        """Include the exact execution context in a user-facing error."""
        return f"{error} (filesystem={filename.parent}, benchmark_file={filename})"

    @staticmethod
    def _parse_result(spec: BenchmarkSpec, payload: dict[str, Any]) -> BenchmarkResult:
        if not isinstance(payload, dict):
            raise ValueError("fio output root was not an object")
        jobs = payload.get("jobs", [])
        if not jobs or not isinstance(jobs[0], dict):
            raise ValueError("fio output did not contain a job")
        direction = jobs[0].get("read" if spec.read_write in {"read", "randread"} else "write")
        if not isinstance(direction, dict):
            raise ValueError("fio output did not contain direction data")
        latency_data = direction.get("lat_ns", {})
        if not isinstance(latency_data, dict):
            raise ValueError("fio output latency data was invalid")
        latency = latency_data.get("mean", 0)
        return BenchmarkResult(
            test=spec.test,
            throughput_bytes_per_second=float(direction.get("bw_bytes", 0)),
            iops=float(direction.get("iops", 0)),
            latency_ms=float(latency) / 1_000_000,
            duration_seconds=float(direction.get("runtime", 0)) / 1000,
            success=True,
            workload_name=spec.label,
        )

    def _verify_space(self, mount_point: Path) -> None:
        usage = shutil.disk_usage(mount_point)
        required = max(
            self.config.benchmark_minimum_free_space_bytes,
            self.config.benchmark_file_size_bytes,
        )
        if usage.free < required:
            raise BenchmarkError(
                f"Insufficient free space on {mount_point}: {usage.free} bytes available"
            )
        if not os.access(mount_point, os.W_OK):
            raise BenchmarkError(f"Mount point is not writable: {mount_point}")
        try:
            file_size_bits = int(os.pathconf(mount_point, "PC_FILESIZEBITS"))
        except (OSError, ValueError):
            file_size_bits = 63
        if self.config.benchmark_file_size_bytes.bit_length() > file_size_bits:
            raise BenchmarkError(f"Benchmark file is too large for filesystem: {mount_point}")

    def _ensure_available(self) -> None:
        if not self.is_available():
            raise BenchmarkError(f"fio is not installed or unavailable: {self.config.fio_binary}")
