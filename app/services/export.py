"""Benchmark history export formats."""

import csv
import json
from io import StringIO
from pathlib import Path


class HistoryExporter:
    """Export history records to common portable formats."""

    @staticmethod
    def export(records: list[dict[str, object]], directory: Path, fmt: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"benchmark-history.{fmt}"
        if fmt == "json":
            destination.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
        elif fmt == "csv":
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=records[0].keys() if records else ["disk"])
            writer.writeheader()
            writer.writerows(records)
            destination.write_text(output.getvalue(), encoding="utf-8")
        elif fmt == "md":
            destination.write_text(HistoryExporter._markdown(records), encoding="utf-8")
        elif fmt == "html":
            destination.write_text(HistoryExporter._html(records), encoding="utf-8")
        else:
            raise ValueError(f"Unsupported export format: {fmt}")
        return destination

    @staticmethod
    def _markdown(records: list[dict[str, object]]) -> str:
        lines = [
            "# DiskBench Benchmark History",
            "",
            "| Date | Disk | Model | Score |",
            "| --- | --- | --- | ---: |",
        ]
        lines.extend(
            f"| {record.get('completed_at', '--')} | {record.get('disk', '--')} | "
            f"{record.get('model', '--')} | {record.get('overall_score', 0)} |"
            for record in records
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _html(records: list[dict[str, object]]) -> str:
        rows = "".join(
            f"<tr><td>{record.get('completed_at', '--')}</td><td>{record.get('disk', '--')}</td>"
            f"<td>{record.get('model', '--')}</td><td>{record.get('overall_score', 0)}</td></tr>"
            for record in records
        )
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>DiskBench Benchmark History</title></head><body>"
            "<h1>DiskBench Benchmark History</h1>"
            "<table><tr><th>Date</th><th>Disk</th><th>Model</th><th>Score</th></tr>"
            f"{rows}</table></body></html>"
        )
