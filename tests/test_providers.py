"""
Unit tests for Cloud (AWS, Azure, GCP) and Hypervisor (VMware, KVM) provider adapters.
"""
import unittest
from app.models.schemas import NodeSpec, StorageVolumeSpec, LinuxDistro, VolumeType
from app.providers import get_provider, list_supported_providers
from app.providers.aws_provider import AWSProvider
from app.providers.azure_provider import AzureProvider
from app.providers.gcp_provider import GCPProvider
from app.providers.vmware_provider import VMwareProvider
from app.providers.kvm_provider import KVMProvider


class TestProviders(unittest.TestCase):
    def test_list_supported_providers(self):
        providers = list_supported_providers()
        self.assertEqual(len(providers), 5)
        names = {p["provider"] for p in providers}
        self.assertEqual(names, {"aws", "azure", "gcp", "vmware", "kvm"})

    def test_aws_provider(self):
        aws = get_provider("aws")
        self.assertIsInstance(aws, AWSProvider)
        flavor = aws.map_instance_flavor(4, 16)
        self.assertEqual(flavor, "t3.xlarge")

        node = NodeSpec(
            name="aws-node-1",
            vcpu=4,
            ram_gb=16,
            disk_gb=100,
            os_distro=LinuxDistro.UBUNTU_22_04,
            storage_volumes=[
                StorageVolumeSpec(name="v1", volume_type=VolumeType.AWS_EBS, size_gb=50, mount_point="/data")
            ]
        )
        cloud_init = aws.generate_cloud_init(node, "k8s_node")
        self.assertIn("aws-node-1", cloud_init)
        self.assertIn("/data", cloud_init)

        mock = aws.simulate_node_provision(node, "job-1", 0)
        self.assertTrue(mock["instance_id"].startswith("i-"))
        self.assertIn("private_ip", mock)

    def test_azure_provider(self):
        azure = get_provider("azure")
        self.assertIsInstance(azure, AzureProvider)
        flavor = azure.map_instance_flavor(8, 32)
        self.assertEqual(flavor, "Standard_D8s_v5")

    def test_gcp_provider(self):
        gcp = get_provider("gcp")
        self.assertIsInstance(gcp, GCPProvider)
        flavor = gcp.map_instance_flavor(4, 16)
        self.assertEqual(flavor, "e2-standard-4")

    def test_vmware_provider(self):
        vmware = get_provider("vmware")
        self.assertIsInstance(vmware, VMwareProvider)
        creds = vmware.validate_credentials()
        self.assertEqual(creds["vcenter_server"], "vcenter.infra.internal")

        node = NodeSpec(name="vm-prod-01", vcpu=8, ram_gb=32, disk_gb=120)
        mock = vmware.simulate_node_provision(node, "job-2", 0)
        self.assertTrue(mock["vcenter_moref"].startswith("vm-"))
        self.assertTrue(mock["mac_address"].startswith("00:50:56"))

    def test_kvm_provider(self):
        kvm = get_provider("kvm")
        self.assertIsInstance(kvm, KVMProvider)
        creds = kvm.validate_credentials()
        self.assertEqual(creds["hypervisor_uri"], "qemu:///system")

        node = NodeSpec(name="kvm-node-01", vcpu=4, ram_gb=16, disk_gb=80)
        mock = kvm.simulate_node_provision(node, "job-3", 0)
        self.assertIn("domain_uuid", mock)
        self.assertEqual(mock["bridge"], "virbr0")


if __name__ == "__main__":
    unittest.main()
