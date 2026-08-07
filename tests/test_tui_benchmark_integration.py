"""End-to-end UI integration for starting a benchmark from Home."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from textual.app import App, ComposeResult

from app.config import AppConfig
from app.models.disk import Disk
from app.services.benchmark import FioBenchmarkService
from app.services.history import HistoryStore
from app.services.nvme import NvmeService
from app.services.smart import SmartService
from app.ui.benchmark import BenchmarkResultsScreen, BenchmarkScreen
from app.ui.dialogs import BenchmarkProfileDialog
from app.ui.home import HomeScreen


class StaticDetector:
    """Deterministic detector used to exercise the real Home screen."""

    def __init__(self, mount_point: Path) -> None:
        self.mount_point = mount_point

    def detect(self) -> list[Disk]:
        return [Disk(name="sda", model="Integration SSD", mount_point=str(self.mount_point))]


def _fio_runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
    payload = {
        "jobs": [
            {
                "read": {"bw_bytes": 1048576, "iops": 100, "lat_ns": {"mean": 1000}},
                "write": {"bw_bytes": 1048576, "iops": 100, "lat_ns": {"mean": 1000}},
            }
        ]
    }
    return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")


def test_home_benchmark_flow_reaches_results_and_sqlite(tmp_path: Path) -> None:
    config = AppConfig(
        fio_binary=sys.executable,
        benchmark_file_size_bytes=4096,
        benchmark_minimum_free_space_bytes=1,
        history_directory=tmp_path / "history",
        output_directory=tmp_path / "output",
    )
    history = HistoryStore(config.history_directory, output_directory=config.output_directory)
    service = FioBenchmarkService(config, runner=_fio_runner)

    class IntegrationApp(App[None]):
        def compose(self) -> ComposeResult:
            yield HomeScreen(
                StaticDetector(tmp_path),
                SmartService(config),
                NvmeService(config),
                service,
                history,
                config,
            )

    async def exercise() -> None:
        app = IntegrationApp()
        async with app.run_test() as pilot:
            await pilot.press("space")
            await pilot.press("b")
            await pilot.pause()
            assert isinstance(app.screen, BenchmarkProfileDialog)
            await pilot.press("q")
            await pilot.pause()
            assert app.screen.query_one(HomeScreen)

            await pilot.press("b")
            await pilot.pause()
            assert isinstance(app.screen, BenchmarkProfileDialog)
            await pilot.click("#profile-quick")
            for _ in range(30):
                await pilot.pause()
                if isinstance(app.screen, BenchmarkResultsScreen):
                    break
            assert isinstance(app.screen, BenchmarkResultsScreen)
            assert app.screen.query_one("#results-table").row_count == 2
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, BenchmarkScreen)
            await pilot.press("q")
            await pilot.pause()
            assert app.screen.query_one(HomeScreen)
            await pilot.press("q")
            await pilot.pause()
            assert not app.is_running

    asyncio.run(exercise())
    records = history.list_runs()
    assert len(records) == 1
    assert history.database_path.exists()
