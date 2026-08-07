"""Coverage for v0.7 profiles, settings and history metadata."""

from pathlib import Path

from app.config import AppConfig
from app.models.benchmark import BenchmarkProfile, DiskBenchmarkResults
from app.services.history import HistoryStore
from app.services.profiles import BenchmarkProfileService


def test_profiles_have_expected_workload_counts() -> None:
    service = BenchmarkProfileService()
    assert len(service.workloads(AppConfig(benchmark_profile=BenchmarkProfile.QUICK))) == 2
    assert len(service.workloads(AppConfig(benchmark_profile=BenchmarkProfile.STANDARD))) == 4
    assert len(service.workloads(AppConfig(benchmark_profile=BenchmarkProfile.EXTENDED))) == 12


def test_custom_profile_propagates_fio_parameters() -> None:
    config = AppConfig(
        benchmark_profile="Custom",
        benchmark_block_size="64k",
        benchmark_queue_depth=8,
        benchmark_num_jobs=2,
    )
    workloads = BenchmarkProfileService().workloads(config)
    assert len(workloads) == 4
    assert all(workload.block_size == "64k" for workload in workloads)
    assert all(workload.queue_depth == 8 for workload in workloads)
    assert all(workload.num_jobs == 2 for workload in workloads)


def test_history_metadata_can_be_updated_and_deleted(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history")
    snapshot = store.save(DiskBenchmarkResults("sda", "Test SSD", "--", "100 GB"))
    record = store.list_runs()[0]

    assert snapshot.exists()
    assert store.update_metadata(int(record["id"]), "Lab run", "baseline", True)
    updated = store.list_runs()[0]
    assert updated["session_name"] == "Lab run"
    assert updated["notes"] == "baseline"
    assert updated["favorite"] == 1
    assert store.delete_run(int(record["id"]))
    assert store.list_runs() == []
    assert not snapshot.exists()
