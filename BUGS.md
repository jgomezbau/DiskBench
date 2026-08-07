# DiskBench Known Issues

This register tracks reproducible issues that are intentionally outside the
current release scope. Entries are reviewed before each release and are not a
substitute for security advisories.

| ID | Severity | Status | Target | Summary |
| --- | --- | --- | --- | --- |
| BUG-0001 | Medium | Open | v0.8 | The details dialog can omit fields when a device exposes metadata through a source that is not available to the active inspection path. |
| BUG-0002 | Medium | Open | v0.8 | SMART support detection can report `Not Supported` on devices whose bridge or permissions require additional probing. |
| BUG-0003 | Low | Open | v0.8 | Automated validation of the hardware details dialog needs a broader fixture matrix for optional and missing properties. |

## Reporting a bug

Please include the DiskBench version, distribution and kernel version, device
class, command availability (`lsblk`, `smartctl`, `nvme`), and a redacted log
excerpt. Never attach serial numbers or other sensitive hardware identifiers
unless they are necessary for reproducing the issue.
