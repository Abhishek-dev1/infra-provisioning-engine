"""
Unit tests for Terraform IaC workspace management, configuration generation, and execution.
"""
import json
import unittest
from pathlib import Path
from app.models.schemas import ProvisioningRequest, NodeSpec, ProviderType, TargetType
from app.services.terraform_service import terraform_service


class TestTerraformService(unittest.TestCase):
    def test_prepare_workspace_and_execute_apply(self):
        req = ProvisioningRequest(
            job_name="tf-test-job",
            provider=ProviderType.AWS,
            region_or_datacenter="us-east-1",
            target_type=TargetType.K8S_NODE,
            nodes=[
                NodeSpec(name="k8s-node-1", vcpu=2, ram_gb=4, disk_gb=30),
                NodeSpec(name="k8s-node-2", vcpu=4, ram_gb=8, disk_gb=50)
            ]
        )
        job_id = "test-tf-exec-01"
        run_dir = terraform_service.prepare_workspace(job_id, req)
        self.assertTrue(run_dir.exists())

        # Check terraform.tfvars.json exists and is valid JSON
        tfvars_path = run_dir / "terraform.tfvars.json"
        self.assertTrue(tfvars_path.exists())
        with open(tfvars_path, "r", encoding="utf-8") as f:
            tfvars = json.load(f)
            self.assertEqual(tfvars["job_name"], "tf-test-job")
            self.assertEqual(len(tfvars["nodes"]), 2)

        # Check main.tf copied or generated
        self.assertTrue((run_dir / "main.tf").exists())

        # Test simulated apply
        res = terraform_service.execute_apply(job_id, req)
        self.assertTrue(res["success"])
        self.assertEqual(res["stage"], "completed")
        self.assertEqual(len(res["nodes_data"]), 2)
        self.assertTrue((run_dir / "terraform.tfstate").exists())

        # Test execute destroy
        dest_res = terraform_service.execute_destroy(job_id, "aws")
        self.assertTrue(dest_res["success"])


if __name__ == "__main__":
    unittest.main()
