"""
Base Cloud & Hypervisor Provider Interface.
Defines abstract contracts for multi-cloud adapters, hardware capability mapping, and cloud-init generation.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from app.models.schemas import NodeSpec, StorageVolumeSpec, ProvisioningRequest, PreflightCheckResult, LinuxDistro


class BaseProvider(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def validate_credentials(self) -> Dict[str, Any]:
        """Validate presence and validity of cloud/hypervisor credentials and endpoint connectivity."""
        pass

    @abstractmethod
    def map_instance_flavor(self, vcpu: int, ram_gb: int) -> str:
        """Map generic compute requests to native provider instance types (e.g. t3.xlarge, Standard_D4s_v5)."""
        pass

    @abstractmethod
    def generate_terraform_vars(self, request: ProvisioningRequest, run_dir: str) -> Dict[str, Any]:
        """Generate provider-specific Terraform variables for HCL module execution."""
        pass

    @abstractmethod
    def generate_cloud_init(self, node: NodeSpec, target_type: str) -> str:
        """Generate multi-distribution cloud-init user-data script for node bootstrapping."""
        pass

    @abstractmethod
    def simulate_node_provision(self, node: NodeSpec, job_id: str, index: int) -> Dict[str, Any]:
        """Generate realistic mock infrastructure attributes (IP, instance ID, MAC) for test environments."""
        pass

    def default_cloud_init_header(self, node: NodeSpec) -> str:
        """Base cloud-init header with hostname configuration."""
        return f"""#cloud-config
hostname: {node.name}
fqdn: {node.name}.infra.local
manage_etc_hosts: true
package_update: true
package_upgrade: false
"""


def get_common_k8s_bootstrap(node: NodeSpec, distro: LinuxDistro) -> str:
    """Multi-distribution Kubernetes prerequisites & kubeadm join template."""
    pkg_mgr = "apt-get" if distro in [LinuxDistro.UBUNTU_22_04, LinuxDistro.DEBIAN_12] else "dnf"
    join_command = ""
    if node.k8s_master_endpoint and node.k8s_join_token:
        join_command = f"kubeadm join {node.k8s_master_endpoint} --token {node.k8s_join_token} --discovery-token-unsafe-skip-ca-verification"

    return f"""
# --- Kubernetes Node Setup ({distro.value}) ---
mkdir -p /etc/modules-load.d /etc/sysctl.d
cat <<'EOF' > /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF
modprobe overlay
modprobe br_netfilter

cat <<'EOF' > /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sysctl --system

# Container runtime (containerd) setup
if command -v {pkg_mgr} >/dev/null 2>&1; then
    {pkg_mgr} install -y containerd curl iptables socat
    mkdir -p /etc/containerd
    containerd config default > /etc/containerd/config.toml
    sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
    systemctl restart containerd
    systemctl enable containerd
fi

# Execute join if token supplied
{join_command}
"""
