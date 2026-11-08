"""
Unit tests for the Pre-Flight Quota & Validation Engine.
"""
import unittest
from app.models.schemas import (
    ProvisioningRequest,
    NodeSpec,
    StorageVolumeSpec,
    ProviderType,
    TargetType,
    VolumeType,
    LinuxDistro
)
from app.services.preflight_service import preflight_service


class TestPreflight(unittest.TestCase):
    def test_preflight_passes_for_valid_request(self):
        req = ProvisioningRequest(
            job_name="preflight-valid-job",
            provider=ProviderType.AWS,
            region_or_datacenter="us-east-1",
            target_type=TargetType.K8S_NODE,
            nodes=[
                NodeSpec(
                    name="worker-01",
                    vcpu=2,
                    ram_gb=8,
                    disk_gb=40,
                    storage_volumes=[
                        StorageVolumeSpec(
                            name="vol1",
                            volume_type=VolumeType.AWS_EBS,
                            size_gb=50,
                            mount_point="/data"
                        )
                    ]
                )
            ]
        )
        res = preflight_service.evaluate_request(req, reserve_quota=False)
        self.assertTrue(res.passed)
        self.assertEqual(len(res.errors), 0)
        self.assertIn("vcpu", res.checks)
        self.assertIn("ram_gb", res.checks)
        self.assertIn("storage_gb", res.checks)

    def test_preflight_fails_on_excessive_vcpu_quota(self):
        req = ProvisioningRequest(
            job_name="excessive-quota-job",
            provider=ProviderType.AWS,
            region_or_datacenter="us-east-1",
            target_type=TargetType.K8S_NODE,
            nodes=[
                NodeSpec(name=f"worker-{i}", vcpu=16, ram_gb=64, disk_gb=100)
                for i in range(10)  # 160 vCPUs, exceeds max request limit (64)
            ]
        )
        res = preflight_service.evaluate_request(req, reserve_quota=False)
        self.assertFalse(res.passed)
        self.assertTrue(any("vCPU" in err for err in res.errors))

    def test_preflight_fails_on_duplicate_mount_points(self):
        req = ProvisioningRequest(
            job_name="duplicate-mount-job",
            provider=ProviderType.AWS,
            region_or_datacenter="us-east-1",
            target_type=TargetType.K8S_NODE,
            nodes=[
                NodeSpec(
                    name="worker-dup",
                    vcpu=2,
                    ram_gb=4,
                    disk_gb=20,
                    storage_volumes=[
                        StorageVolumeSpec(name="v1", volume_type=VolumeType.AWS_EBS, size_gb=20, mount_point="/var/log"),
                        StorageVolumeSpec(name="v2", volume_type=VolumeType.AWS_EBS, size_gb=30, mount_point="/var/log")
                    ]
                )
            ]
        )
        res = preflight_service.evaluate_request(req, reserve_quota=False)
        self.assertFalse(res.passed)
        self.assertTrue(any("Duplicate mount_point" in err for err in res.errors))


if __name__ == "__main__":
    unittest.main()
