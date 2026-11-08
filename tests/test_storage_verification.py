"""
Unit tests for the Storage Volume Attachment & Verification Subsystem.
"""
import unittest
import uuid
from app.models.schemas import StorageVolumeSpec, VolumeType
from app.repositories.node_repository import node_repo
from app.repositories.job_repository import job_repo
from app.services.storage_service import storage_service


class TestStorageVerification(unittest.TestCase):
    def setUp(self):
        unique_suffix = uuid.uuid4().hex[:8]
        self.job_id = f"test-job-storage-{unique_suffix}"
        self.node_id = f"test-node-storage-{unique_suffix}"
        self.volume_id = f"vol-storage-test-{unique_suffix}"

        self.job = job_repo.create_job(
            job_id=self.job_id,
            name="storage-test-run",
            provider="aws",
            target_type="k8s_node",
            spec={}
        )
        self.node = node_repo.create_node(
            node_id=self.node_id,
            job_id=self.job_id,
            name="worker-storage-01",
            provider="aws",
            node_type="k8s_worker",
            cpu_cores=4,
            ram_gb=16,
            disk_gb=100,
            os_distro="ubuntu-22.04"
        )
        self.volume = node_repo.create_storage_volume(
            volume_id=self.volume_id,
            node_id=self.node_id,
            job_id=self.job_id,
            volume_type="aws_ebs",
            size_gb=100,
            mount_point="/mnt/ebs_fast",
            device_name="/dev/nvme1n1",
            iops=3000
        )

    def test_verify_volume_attachment_success(self):
        spec = StorageVolumeSpec(
            name="test-vol",
            volume_type=VolumeType.AWS_EBS,
            size_gb=100,
            mount_point="/mnt/ebs_fast",
            device_name="/dev/nvme1n1",
            iops=3000
        )
        result = storage_service.verify_volume_attachment(
            node_id=self.node_id,
            volume_id=self.volume_id,
            volume_spec=spec
        )
        self.assertTrue(result.verified)
        self.assertEqual(result.mount_point, "/mnt/ebs_fast")
        self.assertGreater(result.actual_size_gb, 90.0)
        self.assertGreater(result.io_write_latency_ms, 0)
        self.assertGreater(result.io_read_latency_ms, 0)
        self.assertIn("encryption_at_rest", result.details)

        # Check DB updated
        vol_db = node_repo.get_storage_volume(self.volume_id)
        self.assertEqual(vol_db["attachment_status"], "VERIFIED")
        self.assertIsNotNone(vol_db["verification_details"])

    def test_verify_all_node_volumes(self):
        report = storage_service.verify_all_node_volumes(self.node_id, self.job_id)
        self.assertEqual(report["node_id"], self.node_id)
        self.assertEqual(report["total_volumes"], 1)
        self.assertTrue(report["all_verified"])


if __name__ == "__main__":
    unittest.main()
