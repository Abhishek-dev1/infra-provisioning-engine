"""
Integration tests for the Provisioning Control-Plane Orchestrator lifecycle.
"""
import unittest
from app.models.schemas import (
    ProvisioningRequest,
    NodeSpec,
    StorageVolumeSpec,
    ProviderType,
    TargetType,
    VolumeType,
    JobStatus
)
from app.repositories.job_repository import job_repo
from app.repositories.node_repository import node_repo
from app.repositories.quota_repository import quota_repo
from app.services.orchestrator import orchestrator


class TestOrchestrator(unittest.TestCase):
    def test_full_provisioning_and_teardown_lifecycle(self):
        req = ProvisioningRequest(
            job_name="orchestrator-full-run",
            provider=ProviderType.AWS,
            region_or_datacenter="us-east-1",
            target_type=TargetType.K8S_NODE,
            nodes=[
                NodeSpec(
                    name="k8s-hybrid-worker-1",
                    vcpu=2,
                    ram_gb=8,
                    disk_gb=40,
                    storage_volumes=[
                        StorageVolumeSpec(
                            name="ebs-fast-01",
                            volume_type=VolumeType.AWS_EBS,
                            size_gb=50,
                            mount_point="/mnt/k8s-storage",
                            iops=3000
                        )
                    ]
                )
            ],
            preflight_check=True,
            verify_storage=True
        )

        job_id = "test-orch-job-01"
        job_repo.create_job(
            job_id=job_id,
            name=req.job_name,
            provider=req.provider.value,
            target_type=req.target_type.value,
            spec=req.dict()
        )

        # Process job through synchronous method to verify all states
        orchestrator.process_job(job_id, req)

        updated_job = job_repo.get_job(job_id)
        self.assertEqual(updated_job["status"], JobStatus.COMPLETED.value)
        self.assertIsNotNone(updated_job["preflight_results"])
        self.assertTrue(updated_job["preflight_results"]["passed"])
        self.assertIsNotNone(updated_job["storage_verification"])
        self.assertIsNotNone(updated_job["terraform_state"])

        # Check nodes created in DB
        nodes = node_repo.list_nodes(job_id=job_id)
        self.assertEqual(len(nodes), 1)
        node = nodes[0]
        self.assertEqual(node["name"], "k8s-hybrid-worker-1")
        self.assertEqual(node["health_status"], "HEALTHY")
        self.assertIsNotNone(node["health_metrics"])

        # Check storage volume created and verified
        volumes = node_repo.list_node_storage_volumes(node["id"])
        self.assertEqual(len(volumes), 1)
        vol = volumes[0]
        self.assertEqual(vol["attachment_status"], "VERIFIED")
        self.assertIsNotNone(vol["verification_details"])

        # Test teardown
        term_res = orchestrator.terminate_job(job_id)
        self.assertTrue(term_res["success"])
        job_after_term = job_repo.get_job(job_id)
        self.assertEqual(job_after_term["status"], JobStatus.TERMINATED.value)


if __name__ == "__main__":
    unittest.main()
