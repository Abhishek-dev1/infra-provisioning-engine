"""
KVM / QEMU / libvirt Hypervisor Provider Adapter.
Automates Linux host virtualization, qcow2 storage pools, virtio disk attachments, and bridge networks.
"""
import hashlib
from typing import Dict, Any, List
from app.models.schemas import NodeSpec, ProvisioningRequest, LinuxDistro
from app.providers.base import BaseProvider, get_common_k8s_bootstrap


class KVMProvider(BaseProvider):
    def __init__(self):
        super().__init__("kvm")

    def validate_credentials(self) -> Dict[str, Any]:
        return {
            "provider": "kvm",
            "connected": True,
            "hypervisor_uri": "qemu:///system",
            "hypervisor_version": "QEMU 7.2.0 / libvirt 9.0.0",
            "supported_services": [
                "KVM Virtual Machines",
                "qcow2 Volume Pools",
                "VirtIO Block Storage",
                "Linux Bridge (br0) & NAT Networks"
            ],
            "api_health": "UP"
        }

    def map_instance_flavor(self, vcpu: int, ram_gb: int) -> str:
        """KVM custom core/memory specification."""
        return f"{vcpu}vCPU-{ram_gb}GB-RAM"

    def get_base_image_path(self, distro: LinuxDistro) -> str:
        image_map = {
            LinuxDistro.UBUNTU_22_04: "/var/lib/libvirt/images/ubuntu-22.04-server-cloudimg-amd64.qcow2",
            LinuxDistro.RHEL_9: "/var/lib/libvirt/images/rhel-base-9.2-x86_64-kvm.qcow2",
            LinuxDistro.DEBIAN_12: "/var/lib/libvirt/images/debian-12-generic-amd64.qcow2",
            LinuxDistro.ROCKY_9: "/var/lib/libvirt/images/Rocky-9-GenericCloud-Base.qcow2",
        }
        return image_map.get(distro, "/var/lib/libvirt/images/ubuntu-22.04-server-cloudimg-amd64.qcow2")

    def generate_terraform_vars(self, request: ProvisioningRequest, run_dir: str) -> Dict[str, Any]:
        nodes_payload = []
        for idx, node in enumerate(request.nodes):
            base_image = self.get_base_image_path(node.os_distro)
            extra_disks = [
                {
                    "name": f"{node.name}-vol-{v_idx}",
                    "size_gb": v.size_gb,
                    "target_dev": v.device_name or f"vd{chr(ord('b') + v_idx)}",
                    "pool": "default"
                }
                for v_idx, v in enumerate(node.storage_volumes)
            ]
            nodes_payload.append({
                "name": node.name,
                "vcpu": node.vcpu,
                "memory_mb": node.ram_gb * 1024,
                "base_image": base_image,
                "root_disk_gb": node.disk_gb,
                "extra_disks": extra_disks,
                "cloud_init": self.generate_cloud_init(node, request.target_type.value)
            })

        vars_dict = {
            "libvirt_uri": "qemu:///system",
            "storage_pool": "default",
            "network_name": "virbr0",
            "job_name": request.job_name,
            "nodes": nodes_payload
        }
        vars_dict.update(request.extra_terraform_vars)
        return vars_dict

    def generate_cloud_init(self, node: NodeSpec, target_type: str) -> str:
        script = self.default_cloud_init_header(node)
        script += """
packages:
  - qemu-guest-agent
  - curl
  - xfsprogs

runcmd:
  - systemctl start qemu-guest-agent
  - systemctl enable qemu-guest-agent
"""
        for idx, vol in enumerate(node.storage_volumes):
            dev = vol.device_name or f"/dev/vd{chr(ord('b') + idx)}"
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
        h = hashlib.md5(f"kvm-{job_id}-{node.name}-{index}".encode()).hexdigest()
        uuid = f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"
        private_ip = f"192.168.122.{50 + index}"
        mac_addr = f"52:54:00:{h[:2]}:{h[2:4]}:{h[4:6]}"

        simulated_qcow2 = []
        for v_idx, v in enumerate(node.storage_volumes):
            simulated_qcow2.append({
                "disk_name": f"{node.name}-vol-{v_idx}.qcow2",
                "target_dev": v.device_name or f"/dev/vd{chr(ord('b') + v_idx)}",
                "size_gb": v.size_gb,
                "mount_point": v.mount_point,
                "state": "attached"
            })

        return {
            "domain_uuid": uuid,
            "provider": "kvm",
            "vcpu": node.vcpu,
            "memory_mb": node.ram_gb * 1024,
            "private_ip": private_ip,
            "public_ip": None,
            "mac_address": mac_addr,
            "bridge": "virbr0",
            "state": "RUNNING",
            "volumes": simulated_qcow2
        }
