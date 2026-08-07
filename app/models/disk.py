"""Storage domain entities."""

from dataclasses import dataclass, field
from enum import StrEnum


class Rotation(StrEnum):
    """Media technology reported by the kernel."""

    SOLID_STATE = "SSD"
    ROTATIONAL = "HDD"
    UNKNOWN = "Unknown"


@dataclass(slots=True)
class Partition:
    """A partition discovered below a physical disk."""

    name: str
    filesystem: str = "Unknown"
    mount_point: str = "Not mounted"
    capacity: str = "Unknown"


@dataclass(slots=True)
class Disk:
    """All storage metadata exposed by the v0.1 domain model."""

    name: str
    vendor: str = "Unknown"
    model: str = "Unknown"
    serial: str = "Not available"
    firmware: str = "Not available"
    capacity: str = "Unknown"
    transport: str = "Unknown"
    filesystem: str = "Unknown"
    mount_point: str = "Not mounted"
    rotation: Rotation = Rotation.UNKNOWN
    temperature: str = "Not available"
    smart_status: str = "Not checked"
    benchmark_results: dict[str, str] = field(default_factory=dict)
    partitions: list[Partition] = field(default_factory=list)

    @property
    def device_path(self) -> str:
        """Return the Linux device path."""
        return f"/dev/{self.name}"

    @property
    def device_type(self) -> str:
        """Return a concise media type for the table."""
        return self.rotation.value if self.rotation is not Rotation.UNKNOWN else "Storage"
