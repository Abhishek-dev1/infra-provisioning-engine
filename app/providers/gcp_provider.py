"""
GCP Cloud Provider Adapter.
Implements Google Compute Engine (GCE), Persistent Disks (PD), and GKE hybrid node provisioning.
"""
import os
import hashlib
from typing import Dict, Any, List
from app.models.schemas import NodeSpec, ProvisioningRequest, LinuxDistro
from app.providers.base import BaseProvider, get_common_k8s_bootstrap


class GCPProvider(BaseProvider):
    def __init__(self):
        super().__init__("gcp")

    def validate_credentials(self) -> Dict[str, Any]:
        return {
            "provider": "gcp",
            "connected": True,
            "auth_method": "Service Account Key / Google Application Credentials",
            "default_region": "us-central1",
            "supported_services": ["Compute Engine", "Persistent Disks (pd-ssd/pd-balanced)", "GKE Nodes", "VPC"],
            "api_health": "UP"
        }

    def map_instance_flavor(self, vcpu: int, ram_gb: int) -> str:
        """Map CPU and Memory to GCP GCE machine types."""
        if vcpu <= 2 and ram_gb <= 4:
            return "e2-medium"
        elif vcpu <= 2 and ram_gb <= 8:
            return "e2-standard-2"
        elif vcpu <= 4 and ram_gb <= 16:
            return "e2-standard-4"
        elif vcpu <= 8 and ram_gb <= 32:
            return "e2-standard-8"
        elif vcpu <= 16 and ram_gb <= 64:
            return "n2-standard-16"
        else:
            return "c2-standard-30"

    def get_image_family(self, distro: LinuxDistro) -> str:
        family_map = {
            LinuxDistro.UBUNTU_22_04: "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts",
            LinuxDistro.RHEL_9: "projects/rhel-cloud/global/images/family/rhel-9",
            LinuxDistro.DEBIAN_12: "projects/debian-cloud/global/images/family/debian-12",
            LinuxDistro.ROCKY_9: "projects/rocky-linux-cloud/global/images/family/rocky-linux-9",
        }
        return family_map.get(distro, "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts")

    def generate_terraform_vars(self, request: ProvisioningRequest, run_dir: str) -> Dict[str, Any]:
        nodes_payload = []
        for idx, node in enumerate(request.nodes):
            machine_type = self.map_instance_flavor(node.vcpu, node.ram_gb)
            image = self.get_image_family(node.os_distro)
            attached_disks = [
                {
                    "name": f"{node.name}-pd-{v_idx}",
                    "size_gb": v.size_gb,
                    "type": "pd-ssd",
                    "device_name": v.device_name or f"google-{node.name}-pd-{v_idx}"
                }
                for v_idx, v in enumerate(node.storage_volumes)
            ]
            nodes_payload.append({
                "name": node.name,
                "machine_type": machine_type,
                "boot_image": image,
                "boot_disk_size_gb": node.disk_gb,
                "attached_disks": attached_disks,
                "metadata_startup_script": self.generate_cloud_init(node, request.target_type.value)
            })

        project_id = os.getenv("GCP_PROJECT", "multicloud-infra-prod")
        vars_dict = {
            "gcp_project": project_id,
            "gcp_region": request.region_or_datacenter or "us-central1",
            "gcp_zone": f"{request.region_or_datacenter or 'us-central1'}-a",
            "environment": request.environment,
            "job_name": request.job_name,
            "nodes": nodes_payload,
            "labels": {
                "environment": request.environment,
                "managed_by": "infra-provisioning-engine"
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

runcmd:
"""
        for idx, vol in enumerate(node.storage_volumes):
            dev = vol.device_name or f"/dev/disk/by-id/google-{node.name}-pd-{idx}"
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
        h = hashlib.md5(f"gcp-{job_id}-{node.name}-{index}".encode()).hexdigest()
        gce_id = f"projects/multicloud-infra-prod/zones/us-central1-a/instances/{node.name}"
        private_ip = f"10.128.{5 + index}.{20 + index}"
        public_ip = f"34.120.{10 + index}.{75 + index}"
        machine_type = self.map_instance_flavor(node.vcpu, node.ram_gb)

        simulated_disks = []
        for v_idx, v in enumerate(node.storage_volumes):
            simulated_disks.append({
                "disk_name": f"{node.name}-pd-{v_idx}",
                "device_name": v.device_name or f"/dev/disk/by-id/google-{node.name}-pd-{v_idx}",
                "size_gb": v.size_gb,
                "mount_point": v.mount_point,
                "state": "attached"
            })

        return {
            "instance_id": gce_id,
            "provider": "gcp",
            "machine_type": machine_type,
            "private_ip": private_ip,
            "public_ip": public_ip,
            "zone": "us-central1-a",
            "state": "RUNNING",
            "volumes": simulated_disks
        }
