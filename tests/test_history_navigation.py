"""Verify persisted runs reopen through the live results dashboard."""

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult

from app.models.benchmark import BenchmarkResult, BenchmarkTest, DiskBenchmarkResults
from app.services.history import HistoryStore
from app.ui.benchmark import BenchmarkResultsScreen
from app.ui.history import HistoryScreen


def test_history_enter_opens_results_dashboard(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history")
    store.save(
        DiskBenchmarkResults(
            disk_name="sda",
            model="History SSD",
            serial="SERIAL",
            capacity="100 GB",
            results=[
                BenchmarkResult(
                    BenchmarkTest.SEQUENTIAL_READ,
                    throughput_bytes_per_second=1024 * 1024,
                    success=True,
                )
            ],
        )
    )

    class HistoryApp(App[None]):
        def compose(self) -> ComposeResult:
            yield from ()

        def on_mount(self) -> None:
            self.push_screen(HistoryScreen(store))

    async def exercise() -> None:
        app = HistoryApp()
        async with app.run_test() as pilot:
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, BenchmarkResultsScreen)
            assert app.screen.query_one("#results-table").row_count == 1
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, HistoryScreen)

    asyncio.run(exercise())
