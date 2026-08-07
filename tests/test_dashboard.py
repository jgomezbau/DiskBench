"""Tests for the v0.6 results dashboard services."""

import json
from pathlib import Path

from app.config import AppConfig
from app.models.benchmark import BenchmarkResult, BenchmarkTest, DiskBenchmarkResults
from app.services.history import HistoryFilter, HistoryStore
from app.services.report import ReportGenerator
from app.services.scoring import ComparisonService, ComparisonStatus, ScoreCalculator


def _results(speed: float, score: float = 0.0) -> DiskBenchmarkResults:
    return DiskBenchmarkResults(
        disk_name="nvme0n1",
        model="Example NVMe",
        serial="SERIAL",
        capacity="1 TB",
        interface="NVMe",
        score=score,
        results=[
            BenchmarkResult(
                BenchmarkTest.SEQUENTIAL_READ, speed * 1024 * 1024, 100_000, 0.2, 1, True
            ),
            BenchmarkResult(
                BenchmarkTest.SEQUENTIAL_WRITE, speed * 1024 * 1024, 90_000, 0.3, 1, True
            ),
            BenchmarkResult(
                BenchmarkTest.RANDOM_READ_4K, speed * 1024 * 1024, 80_000, 0.4, 1, True
            ),
            BenchmarkResult(
                BenchmarkTest.RANDOM_WRITE_4K, speed * 1024 * 1024, 70_000, 0.5, 1, True
            ),
        ],
    )


def test_score_is_bounded_and_rewards_faster_storage() -> None:
    calculator = ScoreCalculator()

    slower = calculator.calculate(_results(100).results)
    faster = calculator.calculate(_results(1000).results)

    assert 0 <= slower <= 100
    assert 0 <= faster <= 100
    assert faster > slower


def test_comparison_classifies_improvement_decline_and_stability() -> None:
    service = ComparisonService()

    assert service.compare("score", 50, 60).status is ComparisonStatus.IMPROVED
    assert service.compare("score", 60, 50).status is ComparisonStatus.DECLINED
    assert service.compare("score", 50, 50.01).status is ComparisonStatus.UNCHANGED
    assert service.compare("score", 50, 60).absolute_difference == 10
    assert service.compare("score", 50, 60).percentage_difference == 20


def test_settings_round_trip_json(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    config = AppConfig(
        settings_path=settings_path,
        benchmark_file_size_bytes=4096,
        benchmark_iterations=3,
        output_directory=tmp_path / "reports",
        history_directory=tmp_path / "history",
        history_retention=7,
        theme="light",
    )

    config.save()
    loaded = AppConfig.load(settings_path)

    assert json.loads(settings_path.read_text(encoding="utf-8"))["theme"] == "light"
    assert loaded.benchmark_file_size_bytes == 4096
    assert loaded.benchmark_iterations == 3
    assert loaded.output_directory == tmp_path / "reports"
    assert loaded.history_retention == 7
    assert loaded.theme == "light"


def test_history_filters_and_pdf_report(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history")
    result = _results(500, score=72.5)
    store.save(result)
    records = store.list_runs(HistoryFilter(model="Example NVMe", device="nvme0n1"))

    assert len(records) == 1
    restored = store.to_results(records[0])
    assert restored.interface == "NVMe"
    assert restored.overall_score == 72.5
    destination = ReportGenerator().generate_pdf(restored, tmp_path / "report.pdf", records)
    assert destination.exists()
    assert destination.stat().st_size > 0


def test_history_retention_removes_old_runs(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history", retention=1)
    store.save(_results(100, score=10))
    store.save(_results(200, score=20))

    records = store.list_runs()

    assert len(records) == 1
    assert records[0]["overall_score"] == 20
