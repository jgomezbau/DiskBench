"""Compact ASCII charts for terminal result screens."""

from collections.abc import Iterable


def metric_chart(title: str, value: float, maximum: float, unit: str) -> str:
    """Render one bounded horizontal bar with a readable numeric value."""
    width = 28
    ratio = 0.0 if maximum <= 0 else min(max(value / maximum, 0.0), 1.0)
    filled = max(1 if value > 0 else 0, round(width * ratio))
    return f"{title}\n{'█' * filled}{'░' * (width - filled)}\n{value:.2f} {unit}"


def result_charts(values: Iterable[tuple[str, float, float, str]]) -> str:
    """Render a group of benchmark metrics separated by blank lines."""
    return "\n\n".join(
        metric_chart(title, value, maximum, unit) for title, value, maximum, unit in values
    )
