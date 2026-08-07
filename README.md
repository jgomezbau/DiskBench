# DiskBench

DiskBench is a Linux-first terminal application for professional storage inspection and safe disk benchmarking. `v0.7` adds configurable workload profiles, queue controls, live metrics, analysis and history metadata to the controlled `fio` benchmark engine.

## Installation

Python 3.12+, `lsblk` from util-linux, and a Linux system are required. The
Python dependencies include Textual, Rich, psutil and ReportLab. `fio` is
required for benchmark execution; `smartmontools` and `nvme-cli` are optional
system packages.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python diskbench.py
```

For development tooling:

```bash
pip install -r requirements-dev.txt
pytest
ruff check .
black --check .
mypy app
```

## Architecture

`diskbench.py` is a thin launcher. `app/app.py` is the composition root and injects `LsblkDetectionService` into `HomeScreen`. `app/models` contains framework-independent dataclasses and enums. `app/services/detect.py` owns all `lsblk` JSON parsing and filtering, while `app/ui` contains Textual screens and widgets. Logging and presentation helpers live under `app/utils`.

The service accepts an injectable subprocess runner, which makes detection deterministic in tests and keeps operating-system concerns outside the UI. Slow SMART and NVMe queries run in Textual background workers, so the first inventory render is not blocked.

## Supported devices

## Hardware detection

Detection uses `lsblk --json` for the initial inventory, `blkid --output json` for filesystem fallbacks, `/sys/block` for rotational and discard capabilities, and `udevadm` for bus, interface, vendor, and model fallbacks. Virtual `loop`, `ram`, `zram`, and `dm-` devices are ignored. NVMe, SATA SSD, USB SSD, USB HDD, mechanical HDD, eMMC, SD cards, USB flash drives, and optical drives receive distinct classifications when the kernel exposes enough metadata.

## SMART and NVMe

`SmartService` is the only component that invokes `smartctl`. It requests JSON, normalizes health, temperature, SMART support, power-on hours, power cycles, and NVMe health counters, and caches results per device. The cache is invalidated by `R` refresh.

`NvmeService` requests controller data with `nvme id-ctrl --output-format=json` and supplements it with PCIe link information from sysfs. Missing binaries, unsupported USB bridges, permission errors, non-zero SMART status codes, and malformed responses are logged and displayed as `Not Supported` or `--` without terminating the UI.

## Benchmarking and history

Press `B` on the home screen to benchmark the selected device, or the current
row when nothing is selected. DiskBench runs four `fio` workloads sequentially:
sequential read, sequential write, random read 4K and random write 4K. Tests
use a temporary file on a mounted filesystem, verify free space first, and
remove the file in a cleanup block. Disk devices are never opened directly.

`MountResolver` selects a writable directory on the selected disk, preferring
`/home`, `/`, `/run/media`, `/media` and `/mnt`. It rejects boot, optical,
squashfs, swap, tmpfs and read-only filesystems; raw block-device paths are
never passed to `fio`.

Benchmark work runs in a Textual background worker. The progress screen shows
the active disk, test, throughput, IOPS, elapsed time and estimated remaining
time. Results are saved as JSON and in SQLite under `history/`; `E` exports
JSON, CSV, Markdown and HTML reports. `H` opens history and `C` compares a run
with the previous run for that disk.

`fio` is required only for benchmark execution. `smartctl`, `nvme-cli`,
`lsblk`, `udevadm` and `blkid` are queried opportunistically according to
their availability and permissions. DiskBench verifies `fio` before starting
the worker and keeps the benchmark screen available with a friendly diagnostic
when it is not installed. Benchmark starts, completion, cancellation, errors
and exports are written to the application log.

## Results dashboard

When a benchmark completes, DiskBench opens a results dashboard containing
hardware identity, interface, date, duration, each workload's throughput,
latency and IOPS, plus a reproducible 0–100 DiskBench Score. The scoring
weights sequential throughput, random throughput, IOPS and latency; SMART
health is deliberately reserved for a future scoring revision.

`H` opens history. History can be filtered by disk, date, model and device.
`ENTER` opens a stored result, `C` compares it with the previous run, and the
comparison shows improved, declined or unchanged metrics with absolute and
percentage differences. Compact Unicode charts visualize throughput and score
trends. `E` exports CSV, JSON, Markdown, HTML and PDF reports.

`S` opens persistent settings for benchmark file size, iterations, runtime,
output directory, history retention and theme. Settings are stored as JSON in
`~/.config/diskbench/settings.json` and loaded on the next start.

## v0.7 benchmark engine

Quick, Standard, Extended and Custom profiles configure workload sequences. Custom additionally controls block size, queue depth and job count. Direct I/O, synchronous or asynchronous I/O, verification, runtime, iterations and file size are persisted in the settings file. The sequential queue runs in a background worker: `P` pauses safely, `T` retries, `X` skips and `Escape` cancels. The screen reports measured throughput, IOPS, latency, elapsed time, queue position and an ASCII chart.

Before execution DiskBench verifies `fio`, the mounted filesystem, writability and free space at least as large as the benchmark file. Temporary files are removed in cleanup. History supports SQLite/JSON persistence, session names, notes, favorites and deletion.

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| Up / Down | Navigate the table |
| Space | Select or deselect the current device |
| Enter | Open device details |
| Ctrl+A | Select all |
| Ctrl+D | Clear selection |
| B | Run fio benchmark for selected/current device |
| P | Pause or resume the benchmark queue |
| T | Retry the current disk |
| X | Skip the current disk |
| H | Open benchmark history |
| S | Open settings |
| E | Export results or history |
| C | Compare selected history run |
| R | Refresh inventory and hardware inspection |
| Q | Quit |
| Escape | Cancel benchmark, or go back/close the active dialog |

## Roadmap

- `v0.1-alpha`: architecture, physical-device detection, inventory table, selection, and details.
- `v0.2`: refresh, selection preservation, and background hardware enrichment.
- `v0.3`: SMART health, temperatures, NVMe metadata, storage classification, and grouped hardware details.
- `v0.4`: complete hardware inspection data flow, filesystem fallbacks, interface and partition-table metadata, and testable SMART/NVMe services.
- `v0.5`: safe fio benchmarks, historical results, comparison views, and report export.
- `v0.6`: results dashboard, score calculation, filters, trend charts, PDF reports, and persistent settings.
- `v0.7`: professional profiles, configurable fio parameters, queue controls, live metrics, analysis, and history metadata.
- `v1.0`: stable plugin boundaries, packaging, complete test coverage, and release documentation.

## License

MIT. See [LICENSE](LICENSE).
