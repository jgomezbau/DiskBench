# Changelog

All notable changes to DiskBench are documented here.

## [0.1.0-alpha] - 2026-08-07

### Added

- Textual dark-theme dashboard with header, inventory table, footer, and details modal.
- Injectable `lsblk --json --bytes` detection service for physical storage devices.
- NVMe, SATA, USB, MMC, SD, USB flash, and rotational-media classification through transport and rotation metadata.
- Filtering for loop, ram, zram, and device-mapper disks.
- `Disk` and `Partition` dataclasses with enum-backed rotation state.
- Keyboard navigation, per-device selection, select-all, clear-selection, and quit actions.
- Structured logging under `~/.local/state/diskbench/diskbench.log`.
- Ruff, Black, mypy, and pytest configuration.
- Basic unit tests for JSON parsing, filtering, formatting, and error handling.

### Not included

Benchmark execution, SMART polling, temperature discovery tied to a device, persistence, and report export are reserved for later releases.
