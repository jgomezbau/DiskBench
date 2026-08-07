"""Professional PDF benchmark report generation."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.benchmark import DiskBenchmarkResults

if TYPE_CHECKING:
    from app.services.scoring import MetricComparison

LOGGER = logging.getLogger(__name__)


class ReportGenerator:
    """Create a self-contained PDF report for a benchmark run."""

    def generate_pdf(
        self,
        results: DiskBenchmarkResults,
        destination: Path,
        history: list[dict[str, object]] | None = None,
        comparison: list["MetricComparison"] | None = None,
    ) -> Path:
        """Write hardware, benchmark, score, history and comparison sections."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        styles = getSampleStyleSheet()
        story: list[Flowable] = [
            Paragraph("DiskBench Report", styles["Title"]),
            Paragraph(
                f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
                styles["Normal"],
            ),
            Spacer(1, 8 * mm),
            Paragraph("Hardware", styles["Heading2"]),
            self._table(
                [
                    ["Disk", results.disk_name],
                    ["Model", results.model],
                    ["Serial", results.serial],
                    ["Capacity", results.capacity],
                    ["Interface", results.interface],
                    ["Completed", results.completed_at],
                ]
            ),
            Spacer(1, 5 * mm),
            Paragraph("Benchmark", styles["Heading2"]),
            self._benchmark_table(results),
            Spacer(1, 5 * mm),
            Paragraph(
                f"Overall DiskBench Score: {results.overall_score:.2f}/100", styles["Heading2"]
            ),
        ]
        if history:
            story.extend(
                [
                    Spacer(1, 5 * mm),
                    Paragraph("History", styles["Heading2"]),
                    self._history_table(history),
                ]
            )
        if comparison:
            story.extend(
                [
                    Spacer(1, 5 * mm),
                    Paragraph("Comparison", styles["Heading2"]),
                    self._comparison_table(comparison),
                ]
            )
        document = SimpleDocTemplate(
            str(destination), pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm
        )
        document.build(story)
        LOGGER.info("Generated PDF report at %s", destination)
        return destination

    @staticmethod
    def _table(rows: list[list[str]]) -> Table:
        table = Table(rows, colWidths=[45 * mm, 125 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#d9e2f3")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return table

    def _benchmark_table(self, results: DiskBenchmarkResults) -> Table:
        rows = [["Test", "Throughput", "IOPS", "Latency", "Duration", "Status"]]
        rows.extend(
            [
                [
                    result.test.value,
                    f"{result.throughput_mib_per_second:.2f} MiB/s",
                    f"{result.iops:.0f}",
                    f"{result.latency_ms:.2f} ms",
                    f"{result.duration_seconds:.2f} s",
                    "OK" if result.success else result.error,
                ]
                for result in results.results
            ]
        )
        return self._data_table(rows)

    @staticmethod
    def _history_table(history: list[dict[str, object]]) -> Table:
        rows = [["Date", "Disk", "Model", "Score"]]
        rows.extend(
            [
                str(item.get("completed_at", "--")),
                str(item.get("disk", "--")),
                str(item.get("model", "--")),
                str(item.get("overall_score", "0")),
            ]
            for item in history
        )
        return ReportGenerator._data_table(rows)

    @staticmethod
    def _comparison_table(comparison: list["MetricComparison"]) -> Table:
        rows = [["Metric", "Previous", "Current", "Difference", "Status"]]
        rows.extend(
            [
                item.metric,
                f"{item.previous:.2f}",
                f"{item.current:.2f}",
                (
                    f"{item.absolute_difference:+.2f} ({item.percentage_difference:+.2f}%)"
                    if item.percentage_difference is not None
                    else f"{item.absolute_difference:+.2f}"
                ),
                item.status.value,
            ]
            for item in comparison
        )
        return ReportGenerator._data_table(rows)

    @staticmethod
    def _data_table(rows: list[list[str]]) -> Table:
        table = Table(rows, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243b53")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table
