"""
Azure Cloud Provider Adapter.
Implements Azure Virtual Machines, Managed Disks, and AKS hybrid worker nodes.
"""
import hashlib
from typing import Dict, Any, List
from app.models.schemas import NodeSpec, ProvisioningRequest, LinuxDistro
from app.providers.base import BaseProvider, get_common_k8s_bootstrap


class AzureProvider(BaseProvider):
    def __init__(self):
        super().__init__("azure")

    def validate_credentials(self) -> Dict[str, Any]:
        return {
            "provider": "azure",
            "connected": True,
            "auth_method": "Service Principal / Managed Identity",
            "default_region": "eastus",
            "supported_services": ["Virtual Machines", "Azure Managed Disks", "AKS Nodes", "Virtual Networks"],
            "api_health": "UP"
        }

    def map_instance_flavor(self, vcpu: int, ram_gb: int) -> str:
        """Map CPU and Memory to Azure VM sizes."""
        if vcpu <= 2 and ram_gb <= 4:
            return "Standard_B2s"
        elif vcpu <= 2 and ram_gb <= 8:
            return "Standard_D2s_v5"
        elif vcpu <= 4 and ram_gb <= 16:
            return "Standard_D4s_v5"
        elif vcpu <= 8 and ram_gb <= 32:
            return "Standard_D8s_v5"
        elif vcpu <= 16 and ram_gb <= 64:
            return "Standard_D16s_v5"
        else:
            return "Standard_E32s_v5"

    def get_image_urn(self, distro: LinuxDistro) -> str:
        urn_map = {
            LinuxDistro.UBUNTU_22_04: "Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest",
            LinuxDistro.RHEL_9: "RedHat:RHEL:9-lvm-gen2:latest",
            LinuxDistro.DEBIAN_12: "Debian:debian-12:12-gen2:latest",
            LinuxDistro.ROCKY_9: "erockyenterprisesoftwarefoundationinc1653071250513:rockylinux-9:rockylinux-9:latest",
        }
        return urn_map.get(distro, "Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest")

    def generate_terraform_vars(self, request: ProvisioningRequest, run_dir: str) -> Dict[str, Any]:
        nodes_payload = []
        for idx, node in enumerate(request.nodes):
            vm_size = self.map_instance_flavor(node.vcpu, node.ram_gb)
            image_urn = self.get_image_urn(node.os_distro)
            data_disks = [
                {
                    "name": f"{node.name}-disk-{v_idx}",
                    "lun": v_idx,
                    "disk_size_gb": v.size_gb,
                    "caching": "ReadWrite",
                    "storage_account_type": "Premium_LRS"
                }
                for v_idx, v in enumerate(node.storage_volumes)
            ]
            nodes_payload.append({
                "name": node.name,
                "vm_size": vm_size,
                "image_urn": image_urn,
                "os_disk_size_gb": node.disk_gb,
                "data_disks": data_disks,
                "custom_data": self.generate_cloud_init(node, request.target_type.value)
            })

        vars_dict = {
            "azure_location": request.region_or_datacenter or "eastus",
            "environment": request.environment,
            "job_name": request.job_name,
            "resource_group_name": f"rg-{request.job_name}-{request.environment}",
            "nodes": nodes_payload,
            "tags": {
                "Environment": request.environment,
                "ManagedBy": "MultiCloudProvisioner"
            }
        }
        vars_dict.update(request.extra_terraform_vars)
        return vars_dict

    def generate_cloud_init(self, node: NodeSpec, target_type: str) -> str:
        script = self.default_cloud_init_header(node)
        script += """
packages:
  - curl
  - jq
  - xfsprogs
  - parted

runcmd:
"""
        for idx, vol in enumerate(node.storage_volumes):
            dev = vol.device_name or f"/dev/sd{chr(ord('c') + idx)}"
            script += f"""
  - mkdir -p {vol.mount_point}
  - test -b {dev} && (mkfs.{vol.filesystem} -F {dev} || true)
  - echo "{dev} {vol.mount_point} {vol.filesystem} defaults,nofail 0 2" >> /etc/fstab
  - mount -a
"""
        if "k8s" in target_type or "k8s" in node.node_type:
            script += get_common_k8s_bootstrap(node, node.os_distro)

        return script

    def simulate_node_provision(self, node: NodeSpec, job_id: str, index: int) -> Dict[str, Any]:
        h = hashlib.md5(f"azure-{job_id}-{node.name}-{index}".encode()).hexdigest()
        vm_id = f"/subscriptions/0000-0000/resourceGroups/rg-infra/providers/Microsoft.Compute/virtualMachines/{node.name}"
        private_ip = f"10.1.{10 + index}.{50 + index}"
        public_ip = f"20.42.{15 + index}.{100 + index}"
        vm_size = self.map_instance_flavor(node.vcpu, node.ram_gb)

        simulated_disks = []
        for v_idx, v in enumerate(node.storage_volumes):
            simulated_disks.append({
                "disk_name": f"{node.name}-data-{v_idx}",
                "lun": v_idx,
                "device_name": v.device_name or f"/dev/sd{chr(ord('c') + v_idx)}",
                "size_gb": v.size_gb,
                "mount_point": v.mount_point,
                "state": "attached"
            })

        return {
            "vm_id": vm_id,
            "provider": "azure",
            "vm_size": vm_size,
            "private_ip": private_ip,
            "public_ip": public_ip,
            "location": "eastus",
            "state": "running",
            "volumes": simulated_disks
        }
