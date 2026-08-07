# DiskBench

DiskBench is a Linux-first terminal application for storage inventory and, in future releases, safe disk benchmarking. `v0.1-alpha` provides a read-only physical-device dashboard; benchmark execution is deliberately not part of this release.

## Installation

Python 3.12+ and `lsblk` from util-linux are required.

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

The service accepts an injectable subprocess runner, which makes detection deterministic in tests and keeps operating-system concerns outside the UI.

## Supported devices

The detector includes physical `disk` devices such as NVMe, SATA, USB, MMC, SD, and USB flash storage. It ignores `loop`, `ram`, `zram`, and `dm-` devices.

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
- `v0.2`: benchmark runner interfaces and safe read-only baseline measurements.
- `v0.3`: SMART health, temperatures, USB topology, and refresh.
- `v0.4`: historical results, comparison views, and report export.
- `v1.0`: stable plugin boundaries, packaging, complete test coverage, and release documentation.

## License

MIT. See [LICENSE](LICENSE).
