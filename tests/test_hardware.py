"""Tests for SMART, NVMe, and detection fallbacks."""

import json
import subprocess
from pathlib import Path

from app.models.disk import Disk, HealthStatus
from app.services.detect import LsblkDetectionService
from app.services.nvme import NvmeService
from app.services.smart import SmartService
from app.ui.dialogs import DiskDetailsDialog
from app.ui.widgets import StorageTable


def process(
    command: list[str], payload: object, returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, json.dumps(payload), "")


def test_detection_uses_sysfs_and_blkid_fallbacks(tmp_path: Path) -> None:
    rotational_path = tmp_path / "sda" / "queue"
    rotational_path.mkdir(parents=True)
    (rotational_path / "rotational").write_text("0", encoding="utf-8")

    lsblk_payload = {
        "blockdevices": [
            {
                "name": "sda",
                "type": "disk",
                "size": "1000000",
                "model": " ",
                "tran": " ",
                "children": [{"name": "sda1", "fstype": "", "uuid": ""}],
            }
        ]
    }

    def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if command[0] == "lsblk":
            return process(command, lsblk_payload)
        if command[0] == "udevadm":
            return subprocess.CompletedProcess(
                command,
                0,
                "ID_VENDOR=Acme\nID_MODEL=Fallback SSD\nID_BUS=ata\n",
                "",
            )
        return process(command, {"blockdevices": [{"TYPE": "ext4", "UUID": "abc"}]})

    detect_service = LsblkDetectionService(runner=runner, sysfs_root=tmp_path)
    disks = detect_service.get_disks()
    disk = disks[0]
    assert disk.model == "Fallback SSD"
    assert len(disk.model) > 0
    assert disk.size > 0
    assert disk.health is not None
    assert disk.interface == "ATA"
    assert disk.rotational is False
    assert disk.partitions[0].filesystem == "ext4"
    assert disk.partitions[0].uuid == "abc"


def test_smart_service_normalizes_and_caches_health() -> None:
    calls = 0
    payload = {
        "smart_support": {"available": True, "enabled": True},
        "smart_status": {"passed": True},
        "temperature": {"current": 42},
        "power_on_time": {"hours": 123},
        "power_cycle_count": 7,
    }

    def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return process(command, payload)

    service = SmartService(runner=runner)
    first = service.inspect("sda")
    second = service.inspect("sda")

    assert first is second
    assert calls == 1
    assert first.health is HealthStatus.HEALTHY
    assert first.temperature == "42 °C"
    assert first.power_on_hours == "123 h"


def test_smart_service_reports_unavailable_as_not_supported() -> None:
    def missing_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("smartctl")

    result = SmartService(runner=missing_runner).inspect("nvme0n1")

    assert result.health is HealthStatus.NOT_SUPPORTED


def test_nvme_service_reads_json_controller_data() -> None:
    payload = {
        "mn": "Example NVMe",
        "sn": "NVME-123",
        "fr": "1.0",
        "ver": "1.4",
        "nn": 1,
        "cntlid": 3,
    }

    service = NvmeService(runner=lambda command, **kwargs: process(command, payload))
    result = service.inspect("nvme0n1")

    assert result is not None
    assert result.model == "Example NVMe"
    assert result.serial == "NVME-123"
    assert result.info.nvme_version == "1.4"
    assert result.info.namespace_count == "1"
    assert result.info.controller_id == "3"


def test_details_dialog_exposes_populated_values() -> None:
    disk = Disk(
        name="nvme0n1",
        vendor="Samsung",
        model="Samsung NVMe",
        filesystem="ext4",
        mount_point="/",
    )
    dialog = DiskDetailsDialog(disk, focus_target=StorageTable([]))

    assert dialog.vendor.text != ""
    assert dialog.model.text != ""
    assert dialog.filesystem.text != ""
