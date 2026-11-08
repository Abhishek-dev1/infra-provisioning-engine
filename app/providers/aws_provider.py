"""
AWS Cloud Provider Adapter.
Implements AWS EC2, EBS, and EKS worker node provisioning, Terraform variable generation, and bootstrap scripting.
"""
import hashlib
from typing import Dict, Any, List
from app.models.schemas import NodeSpec, ProvisioningRequest, LinuxDistro
from app.providers.base import BaseProvider, get_common_k8s_bootstrap


class AWSProvider(BaseProvider):
    def __init__(self):
        super().__init__("aws")

    def validate_credentials(self) -> Dict[str, Any]:
        return {
            "provider": "aws",
            "connected": True,
            "auth_method": "IAM Role / Environment Keys",
            "default_region": "us-east-1",
            "supported_services": ["EC2", "EBS (gp3/io2)", "EKS NodeGroups", "VPC"],
            "api_health": "UP"
        }

    def map_instance_flavor(self, vcpu: int, ram_gb: int) -> str:
        """Map CPU and Memory to standard AWS EC2 instance types."""
        if vcpu <= 2 and ram_gb <= 4:
            return "t3.medium"
        elif vcpu <= 2 and ram_gb <= 8:
            return "t3.large"
        elif vcpu <= 4 and ram_gb <= 16:
            return "t3.xlarge"
        elif vcpu <= 8 and ram_gb <= 32:
            return "m5.2xlarge"
        elif vcpu <= 16 and ram_gb <= 64:
            return "m5.4xlarge"
        else:
            return "c5.9xlarge"

    def get_ami_for_distro(self, distro: LinuxDistro, region: str) -> str:
        ami_map = {
            LinuxDistro.UBUNTU_22_04: "ami-0c7217cdde317cfec",  # Canonical Ubuntu 22.04 LTS
            LinuxDistro.RHEL_9: "ami-0fe630eb857a6ec83",        # Red Hat Enterprise Linux 9
            LinuxDistro.DEBIAN_12: "ami-058bd2d568351da34",     # Debian 12 (Bookworm)
            LinuxDistro.ROCKY_9: "ami-0e86e20dae9224db8",       # Rocky Linux 9
        }
        return ami_map.get(distro, "ami-0c7217cdde317cfec")

    def generate_terraform_vars(self, request: ProvisioningRequest, run_dir: str) -> Dict[str, Any]:
        nodes_payload = []
        for idx, node in enumerate(request.nodes):
            instance_type = self.map_instance_flavor(node.vcpu, node.ram_gb)
            ami = self.get_ami_for_distro(node.os_distro, request.region_or_datacenter)
            volumes = [
                {
                    "device_name": v.device_name or f"/dev/sd{chr(ord('f') + v_idx)}",
                    "volume_size": v.size_gb,
                    "volume_type": "gp3",
                    "iops": v.iops or 3000,
                    "mount_point": v.mount_point
                }
                for v_idx, v in enumerate(node.storage_volumes)
            ]
            nodes_payload.append({
                "name": node.name,
                "instance_type": instance_type,
                "ami": ami,
                "root_disk_size": node.disk_gb,
                "volumes": volumes,
                "user_data": self.generate_cloud_init(node, request.target_type.value)
            })

        vars_dict = {
            "aws_region": request.region_or_datacenter,
            "environment": request.environment,
            "job_name": request.job_name,
            "nodes": nodes_payload,
            "tags": {
                "ManagedBy": "MultiCloudProvisioner",
                "Environment": request.environment,
                "Job": request.job_name
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
  - nvme-cli
  - xfsprogs
  - e2fsprogs

runcmd:
"""
        # Storage formatting commands
        for idx, vol in enumerate(node.storage_volumes):
            dev = vol.device_name or f"/dev/nvme{idx+1}n1"
            script += f"""
  # Prepare EBS storage {vol.name} on {vol.mount_point}
  - mkdir -p {vol.mount_point}
  - test -b {dev} && (mkfs.{vol.filesystem} -F {dev} || true)
  - echo "{dev} {vol.mount_point} {vol.filesystem} defaults,nofail 0 2" >> /etc/fstab
  - mount -a
"""
        if "k8s" in target_type or "k8s" in node.node_type:
            script += get_common_k8s_bootstrap(node, node.os_distro)

        return script

    def simulate_node_provision(self, node: NodeSpec, job_id: str, index: int) -> Dict[str, Any]:
        h = hashlib.md5(f"aws-{job_id}-{node.name}-{index}".encode()).hexdigest()
        instance_id = f"i-{h[:17]}"
        subnet_octet = (10 + index) % 250
        private_ip = f"10.0.{subnet_octet}.{15 + index}"
        public_ip = f"54.210.{subnet_octet}.{20 + index}"
        instance_type = self.map_instance_flavor(node.vcpu, node.ram_gb)

        simulated_volumes = []
        for v_idx, v in enumerate(node.storage_volumes):
            vol_hash = hashlib.md5(f"vol-{job_id}-{node.name}-{v_idx}".encode()).hexdigest()
            simulated_volumes.append({
                "volume_id": f"vol-{vol_hash[:17]}",
                "device_name": v.device_name or f"/dev/nvme{v_idx+1}n1",
                "size_gb": v.size_gb,
                "mount_point": v.mount_point,
                "state": "attached"
            })

        return {
            "instance_id": instance_id,
            "provider": "aws",
            "instance_type": instance_type,
            "private_ip": private_ip,
            "public_ip": public_ip,
            "availability_zone": "us-east-1a",
            "state": "running",
            "volumes": simulated_volumes
        }
