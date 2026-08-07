"""Benchmark history persistence."""

import json
import logging
import sqlite3
from dataclasses import asdict
from pathlib import Path

from app.models.benchmark import DiskBenchmarkResults

LOGGER = logging.getLogger(__name__)


class HistoryStore:
    """Persist benchmark results as JSON snapshots and SQLite records."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory if directory is not None else Path("history")
        self.database_path = self.directory / "diskbench.db"
        self.directory.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save(self, results: DiskBenchmarkResults) -> Path:
        """Save one run to both JSON and SQLite."""
        payload = self._payload(results)
        filename = (
            f"{results.completed_at.replace(':', '').replace('+', '_')}"
            f"-{results.disk_name}.json"
        )
        json_path = self.directory / filename
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "INSERT INTO benchmark_runs "
                "(completed_at, disk, model, serial, capacity, results_json, overall_score) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    results.completed_at,
                    results.disk_name,
                    results.model,
                    results.serial,
                    results.capacity,
                    json.dumps(payload["results"]),
                    results.overall_score,
                ),
            )
        LOGGER.info("Saved benchmark history for %s to %s", results.disk_name, json_path)
        return json_path

    def list_runs(self) -> list[dict[str, object]]:
        """Return previous runs newest first."""
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT id, completed_at, disk, model, serial, capacity, "
                "results_json, overall_score "
                "FROM benchmark_runs ORDER BY completed_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def _initialize(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS benchmark_runs ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, completed_at TEXT NOT NULL, "
                "disk TEXT NOT NULL, model TEXT NOT NULL, serial TEXT NOT NULL, "
                "capacity TEXT NOT NULL, results_json TEXT NOT NULL, overall_score REAL NOT NULL)"
            )

    @staticmethod
    def _payload(results: DiskBenchmarkResults) -> dict[str, object]:
        return {
            "completed_at": results.completed_at,
            "disk": results.disk_name,
            "model": results.model,
            "serial": results.serial,
            "capacity": results.capacity,
            "overall_score": results.overall_score,
            "results": [asdict(result) for result in results.results],
        }
