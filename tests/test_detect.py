"""Tests for the operating-system storage adapter."""

import json
import subprocess

import pytest

from app.models.disk import Rotation
from app.services.detect import DetectionError, LsblkDetectionService


def completed(payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["lsblk"], 0, json.dumps(payload), "")


def test_detect_parses_supported_disk_and_partitions() -> None:
    payload = {
        "blockdevices": [
            {
                "name": "nvme0n1",
                "type": "disk",
                "size": "1000000000",
                "model": "Test NVMe",
                "vendor": "Acme",
                "tran": "nvme",
                "rota": False,
                "children": [
                    {
                        "name": "nvme0n1p1",
                        "fstype": "ext4",
                        "mountpoint": "/data",
                        "size": "500000000",
                    }
                ],
            }
        ],
    }
    service = LsblkDetectionService(runner=lambda *args, **kwargs: completed(payload))
    disk = service.detect()[0]
    assert disk.model == "Test NVMe"
    assert disk.rotation is Rotation.SOLID_STATE
    assert disk.filesystem == "ext4"
    assert disk.partitions[0].mount_point == "/data"


def test_detect_filters_virtual_devices() -> None:
    names = ["sda", "loop0", "ram0", "zram0", "dm-0"]
    payload = {"blockdevices": [{"name": name, "type": "disk", "rota": True} for name in names]}
    service = LsblkDetectionService(runner=lambda *args, **kwargs: completed(payload))
    assert [disk.name for disk in service.detect()] == ["sda"]


def test_detect_wraps_subprocess_errors() -> None:
    def failing_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("lsblk")

    with pytest.raises(DetectionError, match="Unable to read storage devices"):
        LsblkDetectionService(runner=failing_runner).detect()
