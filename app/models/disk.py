"""Storage domain entities."""

from dataclasses import dataclass, field
from enum import StrEnum


class Rotation(StrEnum):
    """Media technology reported by the kernel."""

    SOLID_STATE = "SSD"
    ROTATIONAL = "HDD"
    UNKNOWN = "Unknown"


class HealthStatus(StrEnum):
    """Normalized device health state used by the presentation layer."""

    HEALTHY = "Healthy"
    WARNING = "Warning"
    CRITICAL = "Critical"
    UNKNOWN = "Unknown"


@dataclass(slots=True)
class NvmeInfo:
    """Controller and health metadata specific to NVMe devices."""

    pcie_generation: str = "--"
    pcie_width: str = "--"
    nvme_version: str = "--"
    namespace_count: str = "--"
    controller_model: str = "--"
    controller_id: str = "--"
    critical_warnings: str = "--"
    percentage_used: str = "--"
    media_errors: str = "--"
    unsafe_shutdowns: str = "--"
    available_spare: str = "--"


@dataclass(slots=True)
class Partition:
    """A partition discovered below a physical disk."""

    name: str
    filesystem: str = "Unknown"
    mount_point: str = "Not mounted"
    capacity: str = "Unknown"
    uuid: str = "--"
    partition_table: str = "--"


@dataclass(slots=True)
class Disk:
    """Hardware and filesystem metadata for one physical storage device."""

    name: str
    block_type: str = "disk"
    vendor: str = "Unknown"
    model: str = "Unknown"
    serial: str = "Not available"
    firmware: str = "Not available"
    capacity: str = "Unknown"
    transport: str = "Unknown"
    filesystem: str = "Unknown"
    mount_point: str = "Not mounted"
    rotation: Rotation = Rotation.UNKNOWN
    logical_sector_size: str = "--"
    physical_sector_size: str = "--"
    bus: str = "Unknown"
    interface: str = "Unknown"
    uuid: str = "--"
    partition_table: str = "--"
    rotational: bool | None = None
    removable: bool | None = None
    trim_support: str = "Unknown"
    temperature: str = "--"
    power_on_hours: str = "--"
    power_cycles: str = "--"
    smart_supported: bool | None = None
    smart_enabled: bool | None = None
    smart_overall_health: HealthStatus = HealthStatus.UNKNOWN
    benchmark_results: dict[str, str] = field(default_factory=dict)
    partitions: list[Partition] = field(default_factory=list)
    nvme: NvmeInfo | None = None

    @property
    def device_path(self) -> str:
        """Return the Linux device path."""
        return f"/dev/{self.name}"

    @property
    def device_type(self) -> str:
        """Return a user-facing hardware classification."""
        if self.block_type == "rom":
            return "Optical Drive"
        if self.name.startswith("nvme"):
            return "SSD NVMe"
        if self.rotation is Rotation.ROTATIONAL:
            return "HDD"
        if self.rotation is Rotation.SOLID_STATE and self.transport == "USB":
            return "SSD USB"
        if self.rotation is Rotation.SOLID_STATE:
            return "SSD SATA"
        if self.bus == "MMC":
            return "eMMC"
        if self.bus == "SD":
            return "SD Card"
        if self.transport == "USB":
            return "USB Flash Drive"
        return "Unknown"

    @property
    def serial_number(self) -> str:
        """Return the serial number using the public hardware terminology."""
        return self.serial

    @property
    def firmware_version(self) -> str:
        """Return the firmware version using the public hardware terminology."""
        return self.firmware
