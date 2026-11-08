"""
Integration tests for FastAPI RESTful endpoints using TestClient.
"""
import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

# Disable background thread execution during synchronous API testing
settings.ENABLE_BACKGROUND_WORKER = False


class TestAPIRoutes(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_root_endpoint(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ONLINE")
        self.assertIn("capabilities", data)

    def test_health_probes(self):
        res_live = self.client.get("/health/live")
        self.assertEqual(res_live.status_code, 200)
        self.assertEqual(res_live.json()["status"], "ok")

        res_ready = self.client.get("/health/ready")
        self.assertEqual(res_ready.status_code, 200)
        self.assertEqual(res_ready.json()["status"], "ready")

        res_metrics = self.client.get("/metrics")
        self.assertEqual(res_metrics.status_code, 200)
        self.assertIn("uptime_seconds", res_metrics.json())

    def test_providers_endpoints(self):
        res = self.client.get("/api/v1/providers")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 5)

        res_quotas = self.client.get("/api/v1/providers/quotas")
        self.assertEqual(res_quotas.status_code, 200)
        self.assertTrue(len(res_quotas.json()) >= 5)

    def test_preflight_check_endpoint(self):
        payload = {
            "job_name": "api-preflight-job",
            "provider": "aws",
            "region_or_datacenter": "us-east-1",
            "target_type": "k8s_node",
            "nodes": [
                {
                    "name": "worker-api-1",
                    "vcpu": 2,
                    "ram_gb": 4,
                    "disk_gb": 40,
                    "os_distro": "ubuntu-22.04",
                    "node_type": "k8s_worker",
                    "storage_volumes": [
                        {
                            "name": "v1",
                            "volume_type": "aws_ebs",
                            "size_gb": 50,
                            "mount_point": "/data",
                            "iops": 3000,
                            "filesystem": "ext4"
                        }
                    ]
                }
            ],
            "environment": "test",
            "preflight_check": True,
            "verify_storage": True
        }
        res = self.client.post("/api/v1/preflight/check", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["passed"])
        self.assertIn("checks", data)

    def test_provision_job_flow(self):
        payload = {
            "job_name": "api-provision-run",
            "provider": "kvm",
            "region_or_datacenter": "local-datacenter",
            "target_type": "standalone_vm",
            "nodes": [
                {
                    "name": "kvm-vm-1",
                    "vcpu": 2,
                    "ram_gb": 4,
                    "disk_gb": 30,
                    "os_distro": "rhel-9",
                    "node_type": "standalone_vm",
                    "storage_volumes": []
                }
            ],
            "environment": "test",
            "preflight_check": True,
            "verify_storage": False
        }
        # 1. POST /api/v1/provision (202 Accepted)
        res = self.client.post("/api/v1/provision", json=payload)
        self.assertEqual(res.status_code, 202)
        job_data = res.json()
        job_id = job_data["id"]
        self.assertTrue(job_id.startswith("job-"))

        # 2. GET /api/v1/provision/{job_id}
        res_get = self.client.get(f"/api/v1/provision/{job_id}")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["id"], job_id)

        # 3. GET /api/v1/provision
        res_list = self.client.get("/api/v1/provision")
        self.assertEqual(res_list.status_code, 200)
        self.assertTrue(any(j["id"] == job_id for j in res_list.json()))

        # 4. DELETE /api/v1/provision/{job_id}
        res_del = self.client.delete(f"/api/v1/provision/{job_id}")
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.json()["success"])

    def test_job_not_found_returns_404(self):
        res = self.client.get("/api/v1/provision/non-existent-job-id")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
