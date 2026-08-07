# DiskBench

DiskBench is a Linux-first terminal application for professional storage inspection and safe disk benchmarking. `v0.5` adds a controlled `fio` benchmark engine while retaining the read-only hardware inventory workflow.

## Installation

Python 3.12+, `lsblk` from util-linux, and a Linux system are required. `smartmontools` and `nvme-cli` are optional system packages.

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

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| Up / Down | Navigate the table |
| Space | Select or deselect the current device |
| Enter | Open device details |
| Ctrl+A | Select all |
| Ctrl+D | Clear selection |
| B | Run fio benchmark for selected/current device |
| H | Open benchmark history |
| R | Refresh inventory and hardware inspection |
| Q | Quit |
| Escape | Cancel benchmark, or go back/close the active dialog |

## Roadmap

- `v0.1-alpha`: architecture, physical-device detection, inventory table, selection, and details.
- `v0.2`: refresh, selection preservation, and background hardware enrichment.
- `v0.3`: SMART health, temperatures, NVMe metadata, storage classification, and grouped hardware details.
- `v0.4`: complete hardware inspection data flow, filesystem fallbacks, interface and partition-table metadata, and testable SMART/NVMe services.
- `v0.5`: safe fio benchmarks, historical results, comparison views, and report export.
- `v1.0`: stable plugin boundaries, packaging, complete test coverage, and release documentation.

## License

MIT. See [LICENSE](LICENSE).
