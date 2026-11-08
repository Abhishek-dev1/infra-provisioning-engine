"""
VMware vSphere/ESXi & vCenter Provider Adapter.
Automates enterprise virtualized VM lifecycle, dvSwitch portgroups, datastore provisioning, and VMDK attachments.
"""
import os
import hashlib
from typing import Dict, Any, List
from app.models.schemas import NodeSpec, ProvisioningRequest, LinuxDistro
from app.providers.base import BaseProvider, get_common_k8s_bootstrap


class VMwareProvider(BaseProvider):
    def __init__(self):
        super().__init__("vmware")

    def validate_credentials(self) -> Dict[str, Any]:
        vcenter_server = os.getenv("VSPHERE_SERVER", "vcenter.infra.internal")
        return {
            "provider": "vmware",
            "connected": True,
            "vcenter_server": vcenter_server,
            "datacenter": "Datacenter-Enterprise",
            "cluster": "Compute-Cluster-01",
            "supported_services": [
                "vSphere VM Lifecycle",
                "VMDK on VMFS/NFS Datastores",
                "Distributed Virtual Switch (dvSwitch)",
                "Guest Customization Spec"
            ],
            "api_health": "UP"
        }

    def map_instance_flavor(self, vcpu: int, ram_gb: int) -> str:
        """VMware supports custom vCPU & Memory sizing directly."""
        return f"{vcpu}vCPU-{ram_gb}GB-RAM"

    def get_template_name(self, distro: LinuxDistro) -> str:
        template_map = {
            LinuxDistro.UBUNTU_22_04: "templates/ubuntu-22.04-golden-image",
            LinuxDistro.RHEL_9: "templates/rhel-9-enterprise-base",
            LinuxDistro.DEBIAN_12: "templates/debian-12-hardened",
            LinuxDistro.ROCKY_9: "templates/rocky-9-minimal",
        }
        return template_map.get(distro, "templates/ubuntu-22.04-golden-image")

    def generate_terraform_vars(self, request: ProvisioningRequest, run_dir: str) -> Dict[str, Any]:
        datacenter = request.region_or_datacenter or "Datacenter-Enterprise"
        nodes_payload = []
        for idx, node in enumerate(request.nodes):
            template = self.get_template_name(node.os_distro)
            extra_disks = [
                {
                    "label": f"disk_{v_idx+1}",
                    "size": v.size_gb,
                    "unit_number": v_idx + 1,
                    "datastore": "vsanDatastore",
                    "eagerly_scrub": False,
                    "thin_provisioned": True
                }
                for v_idx, v in enumerate(node.storage_volumes)
            ]
            nodes_payload.append({
                "name": node.name,
                "num_cpus": node.vcpu,
                "memory": node.ram_gb * 1024,  # MB in vSphere
                "guest_id": "other4xLinux64Guest",
                "template": template,
                "root_disk_size": node.disk_gb,
                "extra_disks": extra_disks,
                "cloud_init": self.generate_cloud_init(node, request.target_type.value)
            })

        vars_dict = {
            "vsphere_server": os.getenv("VSPHERE_SERVER", "vcenter.infra.internal"),
            "vsphere_datacenter": datacenter,
            "vsphere_cluster": "Compute-Cluster-01",
            "vsphere_datastore": "vsanDatastore",
            "vsphere_network": "dvPortGroup-Workloads-VLAN100",
            "job_name": request.job_name,
            "nodes": nodes_payload
        }
        vars_dict.update(request.extra_terraform_vars)
        return vars_dict

    def generate_cloud_init(self, node: NodeSpec, target_type: str) -> str:
        script = self.default_cloud_init_header(node)
        script += """
packages:
  - open-vm-tools
  - curl
  - xfsprogs

runcmd:
  - systemctl start open-vm-tools
"""
        for idx, vol in enumerate(node.storage_volumes):
            dev = vol.device_name or f"/dev/sd{chr(ord('b') + idx)}"
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
        h = hashlib.md5(f"vmware-{job_id}-{node.name}-{index}".encode()).hexdigest()
        moref_id = f"vm-{int(h[:5], 16) % 9000 + 1000}"
        private_ip = f"172.16.20.{100 + index}"
        mac_addr = f"00:50:56:{h[:2]}:{h[2:4]}:{h[4:6]}"

        simulated_vmdks = []
        for v_idx, v in enumerate(node.storage_volumes):
            simulated_vmdks.append({
                "vmdk_path": f"[vsanDatastore] {node.name}/{node.name}_{v_idx+1}.vmdk",
                "scsi_controller": f"0:{v_idx+1}",
                "device_name": v.device_name or f"/dev/sd{chr(ord('b') + v_idx)}",
                "size_gb": v.size_gb,
                "mount_point": v.mount_point,
                "state": "attached"
            })

        return {
            "vcenter_moref": moref_id,
            "provider": "vmware",
            "guest_os": node.os_distro.value,
            "vcpu": node.vcpu,
            "ram_mb": node.ram_gb * 1024,
            "private_ip": private_ip,
            "public_ip": None,
            "mac_address": mac_addr,
            "esxi_host": f"esxi-node-0{(index % 4) + 1}.infra.internal",
            "state": "POWERED_ON",
            "volumes": simulated_vmdks
        }
