"""
Unit tests for Pydantic models, validation rules, and schema contracts.
"""
import unittest
from pydantic import ValidationError
from app.models.schemas import (
    ProvisioningRequest,
    NodeSpec,
    StorageVolumeSpec,
    ProviderType,
    TargetType,
    VolumeType,
    LinuxDistro
)


class TestSchemas(unittest.TestCase):
    def test_valid_node_and_volume_spec(self):
        vol = StorageVolumeSpec(
            name="data-vol",
            volume_type=VolumeType.AWS_EBS,
            size_gb=100,
            mount_point="/mnt/data",
            iops=3000
        )
        self.assertEqual(vol.mount_point, "/mnt/data")
        self.assertEqual(vol.size_gb, 100)

        node = NodeSpec(
            name="k8s-worker-01",
            vcpu=4,
            ram_gb=16,
            disk_gb=100,
            os_distro=LinuxDistro.UBUNTU_22_04,
            storage_volumes=[vol]
        )
        self.assertEqual(node.name, "k8s-worker-01")
        self.assertEqual(len(node.storage_volumes), 1)

    def test_invalid_mount_point_fails_validation(self):
        with self.assertRaises(ValidationError):
            StorageVolumeSpec(
                name="bad-vol",
                volume_type=VolumeType.AWS_EBS,
                size_gb=50,
                mount_point="relative/path"  # Must start with /
            )

    def test_invalid_vcpu_range_fails_validation(self):
        with self.assertRaises(ValidationError):
            NodeSpec(
                name="bad-node",
                vcpu=0,  # ge=1
                ram_gb=16,
                disk_gb=50
            )

    def test_valid_provisioning_request(self):
        req = ProvisioningRequest(
            job_name="k8s-hybrid-pool",
            provider=ProviderType.AWS,
            region_or_datacenter="us-east-1",
            target_type=TargetType.K8S_NODE,
            nodes=[
                NodeSpec(name="worker-1", vcpu=2, ram_gb=8, disk_gb=50),
                NodeSpec(name="worker-2", vcpu=4, ram_gb=16, disk_gb=80)
            ]
        )
        self.assertEqual(len(req.nodes), 2)
        self.assertEqual(req.provider, ProviderType.AWS)


if __name__ == "__main__":
    unittest.main()
