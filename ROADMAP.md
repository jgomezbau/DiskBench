# DiskBench Roadmap

DiskBench is developed in small, reviewable releases. The roadmap describes
direction, not a promise of dates.

## v0.5 — Benchmark Engine

- Run safe `fio` workloads against temporary files on mounted filesystems.
- Queue selected disks sequentially with cancellable background workers.
- Show throughput, IOPS, latency, duration and estimated completion.
- Persist JSON snapshots and SQLite history under `history/`.
- Export history as JSON, CSV, Markdown and HTML.
- Compare a run with the previous run for the same device.

## v0.6 — Results Dashboard

- Present benchmark results with hardware context and a reproducible score.
- Filter history and inspect benchmark evolution with terminal charts.
- Compare metrics with absolute and percentage differences.
- Export portable CSV, JSON, Markdown, HTML and PDF reports.
- Persist user benchmark and history settings as JSON.

## v0.7 — Professional Benchmark Engine

- Add benchmark profiles and configurable fio parameters.
- Add measured live metrics, charts, queue controls and history metadata.

## v0.8 — Benchmark Reliability

- Improve workload calibration and progress estimation.
- Add stronger device identity matching across reconnects.
- Add interrupted-run recovery tests.
- Expand platform and filesystem compatibility documentation.

## v0.9 — Hardware and UX quality

- Resolve BUG-0001, BUG-0002 and BUG-0003.
- Add richer SMART attribute presentation and vendor-specific diagnostics.
- Improve details validation with representative real-device fixtures.

## v1.0 — Stable release

- Stabilize service interfaces and configuration.
- Publish a packaged command-line entry point.
- Complete accessibility, portability, documentation and release checks.
