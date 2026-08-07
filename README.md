# DiskBench

DiskBench is a Linux-first terminal application for professional storage inspection and, in future releases, safe disk benchmarking. `v0.3` provides read-only hardware discovery; benchmark execution is deliberately not part of this release.

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

Detection uses `lsblk --json` for the initial inventory, `/sys/block` for rotational and discard capabilities, and `udevadm` for bus and vendor fallbacks. Virtual `loop`, `ram`, `zram`, and `dm-` devices are ignored. NVMe, SATA SSD, USB SSD, USB HDD, mechanical HDD, eMMC, SD cards, USB flash drives, and optical drives receive distinct classifications when the kernel exposes enough metadata.

## SMART and NVMe

`SmartService` is the only component that invokes `smartctl`. It requests JSON, normalizes health, temperature, SMART support, power-on hours, power cycles, and NVMe health counters, and caches results per device. The cache is invalidated by `R` refresh.

`NvmeService` requests controller data with `nvme id-ctrl --output-format=json` and supplements it with PCIe link information from sysfs. Missing binaries, unsupported USB bridges, permission errors, non-zero SMART status codes, and malformed responses are logged and displayed as `Unknown` or `--` without terminating the UI.

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| Up / Down | Navigate the table |
| Space | Select or deselect the current device |
| Enter | Open device details |
| Ctrl+A | Select all |
| Ctrl+D | Clear selection |
| Q | Quit |
| Escape | Close the details dialog |

## Roadmap

- `v0.1-alpha`: architecture, physical-device detection, inventory table, selection, and details.
- `v0.2`: refresh, selection preservation, and background hardware enrichment.
- `v0.3`: SMART health, temperatures, NVMe metadata, storage classification, and grouped hardware details.
- `v0.4`: historical results, comparison views, and report export.
- `v1.0`: stable plugin boundaries, packaging, complete test coverage, and release documentation.

## License

MIT. See [LICENSE](LICENSE).
