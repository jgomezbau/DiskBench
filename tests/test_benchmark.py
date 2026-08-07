"""Tests for safe benchmark execution and history persistence."""

import json
import subprocess
from pathlib import Path

import pytest

from app.config import AppConfig
from app.models.benchmark import BenchmarkTest, DiskBenchmarkResults
from app.models.disk import Disk
from app.services.benchmark import BenchmarkError, FioBenchmarkService
from app.services.export import HistoryExporter
from app.services.history import HistoryStore


def _fio_process(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
    payload = {
        "jobs": [
            {
                "read": {
                    "bw_bytes": 104857600,
                    "iops": 25600,
                    "lat_ns": {"mean": 250000},
                    "runtime": 5000,
                },
                "write": {
                    "bw_bytes": 52428800,
                    "iops": 12800,
                    "lat_ns": {"mean": 500000},
                    "runtime": 5000,
                },
            }
        ]
    }
    return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")


def test_benchmark_uses_and_removes_a_temporary_file(tmp_path: Path) -> None:
    config = AppConfig(
        benchmark_file_size_bytes=4096,
        benchmark_minimum_free_space_bytes=1,
    )
    disk = Disk(
        name="sda",
        model="Test SSD",
        capacity="100 GB",
        mount_point=str(tmp_path),
    )

    results = FioBenchmarkService(config, runner=_fio_process).benchmark_disk(disk)

    assert [result.test for result in results.results] == list(BenchmarkTest)
    assert all(result.success for result in results.results)
    assert list(tmp_path.iterdir()) == []


def test_benchmark_requires_a_mounted_filesystem() -> None:
    disk = Disk(name="sda", model="Test SSD")

    with pytest.raises(BenchmarkError, match="no mounted filesystem"):
        FioBenchmarkService().benchmark_disk(disk)


def test_history_saves_and_exports_all_formats(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history")
    results = DiskBenchmarkResults(
        disk_name="sda",
        model="Test SSD",
        serial="SERIAL",
        capacity="100 GB",
    )
    store.save(results)
    records = store.list_runs()

    assert records[0]["disk"] == "sda"
    for file_format in ("json", "csv", "md", "html"):
        destination = HistoryExporter.export(records, store.directory, file_format)
        assert destination.exists()
