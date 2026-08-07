# Changelog

All notable changes to DiskBench are documented here.

## [0.7.1] - 2026-08-07

### Fixed

- Refresh disk and mount metadata immediately before each benchmark.
- Select the largest writable supported filesystem without ever using a raw block device.
- Reopen persisted runs through the same Results Dashboard used by live benchmarks.
- Complete screen-specific navigation, shortcuts and breadcrumbs.

## [0.7.0] - 2026-08-07

### Added

- Quick, Standard, Extended and Custom benchmark profiles.
- Configurable fio parameters, queue controls, live metrics and workload analysis.
- History session names, notes, favorites and deletion.

### Safety

- Free-space validation now covers the configured benchmark file size.

## [0.6.0] - 2026-08-07

### Added

- Results dashboard with hardware, interface, date, duration and workload metrics.
- Isolated 0–100 DiskBench Score based on throughput, random performance, IOPS and latency.
- History filters for disk, date, model and device.
- Detailed stored-result view, comparison statuses, absolute/percentage deltas and trend charts.
- PDF reports generated with ReportLab, alongside CSV, JSON, Markdown and HTML exports.
- Persistent JSON settings for benchmark size, iterations, output path, retention and theme.
- History retention enforcement and backward-compatible SQLite schema migration.
- Integration tests covering score, comparison, settings, PDF generation and the dashboard flow.

## [0.5.0] - 2026-08-07

### Added

- Safe `fio` benchmark engine for sequential and random 4K read/write tests.
- Sequential multi-disk benchmark queue with cancellation and background workers.
- Live progress, throughput, IOPS, elapsed time and estimated remaining time.
- Per-disk result screen with latency, duration and overall throughput score.
- JSON and SQLite history persistence under `history/`.
- JSON, CSV, Markdown and HTML report export.
- History screen and previous-run comparison for the same device.
- Known-issue register and release roadmap.
- Friendly `fio` dependency checks and benchmark lifecycle logging.

### Safety

- Benchmarks require a mounted filesystem and a free-space threshold.
- Workloads use temporary files and clean them up after each disk.
- No benchmark opens a whole block device or overwrites an existing file.

## [0.4.0] - 2026-08-07

### Added

- Complete hardware inspection data flow from detection models to the details dialog.
- Interface and partition-table metadata in the disk model and details view.
- JSON filesystem and UUID fallback through `blkid`.
- Injectable SMART and NVMe command runners for deterministic service testing.
- Robust handling of malformed JSON and whitespace-only hardware fields.

## [0.3.0] - 2026-08-07

### Added

- Hardware discovery from lsblk JSON, sysfs, udevadm, smartctl, and nvme-cli.
- Dedicated cached `SmartService` and `NvmeService` integrations.
- SMART health, temperature, power-on hours, power cycles, and NVMe controller data.
- Background hardware inspection workers with graceful missing-tool handling.
- Grouped General, Storage, Filesystem, SMART, Health, NVMe, and Partition Table details.
- SSD, HDD, NVMe, eMMC, SD, USB, and optical-device classification.

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
