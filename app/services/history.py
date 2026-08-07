"""Benchmark history persistence."""

import json
import logging
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from app.models.benchmark import BenchmarkResult, BenchmarkTest, DiskBenchmarkResults
from app.services.scoring import ScoreCalculator

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HistoryFilter:
    """Optional case-insensitive history filters."""

    disk: str = ""
    date: str = ""
    model: str = ""
    device: str = ""


class HistoryStore:
    """Persist benchmark results as JSON snapshots and SQLite records."""

    def __init__(
        self,
        directory: Path | None = None,
        retention: int = 100,
        output_directory: Path | None = None,
    ) -> None:
        self.directory = directory if directory is not None else Path("history")
        self.output_directory = output_directory or self.directory
        self.retention = max(1, retention)
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
                "(completed_at, disk, model, serial, capacity, results_json, overall_score, "
                "interface, duration_seconds, snapshot_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    results.completed_at,
                    results.disk_name,
                    results.model,
                    results.serial,
                    results.capacity,
                    json.dumps(payload["results"]),
                    results.overall_score,
                    results.interface,
                    results.duration_seconds,
                    str(json_path),
                ),
            )
        self._enforce_retention()
        LOGGER.info("Saved benchmark history for %s to %s", results.disk_name, json_path)
        return json_path

    def list_runs(self, filters: HistoryFilter | None = None) -> list[dict[str, object]]:
        """Return previous runs newest first, optionally filtered."""
        filters = filters or HistoryFilter()
        conditions: list[str] = []
        parameters: list[str] = []
        for column, value in (
            ("disk", filters.disk),
            ("completed_at", filters.date),
            ("model", filters.model),
        ):
            if value.strip():
                conditions.append(f"LOWER({column}) LIKE LOWER(?)")
                parameters.append(f"%{value.strip()}%")
        if filters.device.strip():
            conditions.append("(LOWER(disk) LIKE LOWER(?) OR LOWER('/dev/' || disk) LIKE LOWER(?))")
            device = f"%{filters.device.strip()}%"
            parameters.extend((device, device))
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT id, completed_at, disk, model, serial, capacity, results_json, "
                "overall_score, interface, duration_seconds, snapshot_path "
                f"FROM benchmark_runs{where} ORDER BY completed_at DESC",
                parameters,
            ).fetchall()
        records = [dict(row) for row in rows]
        for record in records:
            self._normalize_score(record)
        return records

    def get_run(self, run_id: int) -> dict[str, object] | None:
        """Return one persisted run by its stable database identifier."""
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT id, completed_at, disk, model, serial, capacity, results_json, "
                "overall_score, interface, duration_seconds, snapshot_path "
                "FROM benchmark_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        record = dict(row) if row is not None else None
        if record is not None:
            self._normalize_score(record)
        return record

    @staticmethod
    def to_results(record: dict[str, object]) -> DiskBenchmarkResults:
        """Deserialize a SQLite history row into the domain model."""
        raw_results = json.loads(str(record.get("results_json", "[]")))
        results = [
            BenchmarkResult(
                test=BenchmarkTest(str(item["test"])),
                throughput_bytes_per_second=float(item.get("throughput_bytes_per_second", 0)),
                iops=float(item.get("iops", 0)),
                latency_ms=float(item.get("latency_ms", 0)),
                duration_seconds=float(item.get("duration_seconds", 0)),
                success=bool(item.get("success", False)),
                error=str(item.get("error", "")),
            )
            for item in raw_results
            if isinstance(item, dict)
        ]
        score = HistoryStore._as_float(record.get("overall_score", 0))
        if score > 100:
            score = ScoreCalculator().calculate(results)
        return DiskBenchmarkResults(
            disk_name=str(record.get("disk", "--")),
            model=str(record.get("model", "--")),
            serial=str(record.get("serial", "--")),
            capacity=str(record.get("capacity", "--")),
            interface=str(record.get("interface", "--")),
            completed_at=str(record.get("completed_at", "--")),
            duration_seconds=HistoryStore._as_float(record.get("duration_seconds", 0)),
            score=score,
            results=results,
        )

    @staticmethod
    def _as_float(value: object) -> float:
        if isinstance(value, (int, float, str)):
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0

    @staticmethod
    def _normalize_score(record: dict[str, object]) -> None:
        """Convert v0.5 throughput averages to the v0.6 score scale."""
        score = HistoryStore._as_float(record.get("overall_score", 0))
        if score > 100:
            record["overall_score"] = ScoreCalculator().calculate(
                HistoryStore.to_results(record).results
            )

    def _initialize(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS benchmark_runs ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, completed_at TEXT NOT NULL, "
                "disk TEXT NOT NULL, model TEXT NOT NULL, serial TEXT NOT NULL, "
                "capacity TEXT NOT NULL, results_json TEXT NOT NULL, overall_score REAL NOT NULL, "
                "interface TEXT NOT NULL DEFAULT '--', duration_seconds REAL NOT NULL DEFAULT 0, "
                "snapshot_path TEXT NOT NULL DEFAULT '')"
            )
            columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(benchmark_runs)")
            }
            for definition in (
                ("interface", "TEXT NOT NULL DEFAULT '--'"),
                ("duration_seconds", "REAL NOT NULL DEFAULT 0"),
                ("snapshot_path", "TEXT NOT NULL DEFAULT ''"),
            ):
                if definition[0] not in columns:
                    connection.execute(
                        f"ALTER TABLE benchmark_runs ADD COLUMN {definition[0]} {definition[1]}"
                    )

    def _enforce_retention(self) -> None:
        """Remove old database rows and their JSON snapshots."""
        with sqlite3.connect(self.database_path) as connection:
            old_rows = connection.execute(
                "SELECT id, snapshot_path FROM benchmark_runs ORDER BY completed_at DESC "
                "LIMIT -1 OFFSET ?",
                (self.retention,),
            ).fetchall()
            for _, snapshot_path in old_rows:
                if snapshot_path:
                    try:
                        Path(snapshot_path).unlink(missing_ok=True)
                    except OSError as exc:
                        LOGGER.warning(
                            "Unable to remove old history snapshot %s: %s", snapshot_path, exc
                        )
            connection.execute(
                "DELETE FROM benchmark_runs WHERE id IN ("
                "SELECT id FROM benchmark_runs ORDER BY completed_at DESC LIMIT -1 OFFSET ?)",
                (self.retention,),
            )

    @staticmethod
    def _payload(results: DiskBenchmarkResults) -> dict[str, object]:
        return {
            "completed_at": results.completed_at,
            "disk": results.disk_name,
            "model": results.model,
            "serial": results.serial,
            "capacity": results.capacity,
            "interface": results.interface,
            "duration_seconds": results.duration_seconds,
            "overall_score": results.overall_score,
            "results": [asdict(result) for result in results.results],
        }
