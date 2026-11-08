"""
Data Transfer Objects & Pydantic Validation Schemas.
Enforces strict typing, JSON serialization, and contract validation across the control-plane.
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator


class ProviderType(str, Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    VMWARE = "vmware"
    KVM = "kvm"


class TargetType(str, Enum):
    K8S_NODE = "k8s_node"
    STANDALONE_VM = "standalone_vm"
    HYBRID_CLUSTER = "hybrid_cluster"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PREFLIGHT_CHECK = "PREFLIGHT_CHECK"
    PROVISIONING = "PROVISIONING"
    ATTACHING_STORAGE = "ATTACHING_STORAGE"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TERMINATING = "TERMINATING"
    TERMINATED = "TERMINATED"


class NodeHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class LinuxDistro(str, Enum):
    UBUNTU_22_04 = "ubuntu-22.04"
    RHEL_9 = "rhel-9"
    DEBIAN_12 = "debian-12"
    ROCKY_9 = "rockylinux-9"


class VolumeType(str, Enum):
    AWS_EBS = "aws_ebs"
    AZURE_DISK = "azure_disk"
    GCP_PD = "gcp_pd"
    NFS_CSI = "nfs_csi"
    LOCAL_QCOW2 = "local_qcow2"
    VMDK = "vmdk"


class StorageVolumeSpec(BaseModel):
    name: str = Field(..., description="Unique logical volume name")
    volume_type: VolumeType = Field(..., description="Infrastructure storage driver type")
    size_gb: int = Field(..., ge=1, le=16384, description="Volume storage capacity in Gigabytes")
    mount_point: str = Field(..., description="Target POSIX directory path inside the node")
    device_name: Optional[str] = Field(None, description="Host device path, e.g. /dev/xvdf or /dev/sdb")
    iops: Optional[int] = Field(3000, description="Provisioned IOPS baseline")
    filesystem: str = Field("ext4", description="Filesystem format (ext4, xfs)")

    @validator("mount_point")
    def validate_mount_point(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError("mount_point must be an absolute path starting with '/'")
        return v


class NodeSpec(BaseModel):
    name: str = Field(..., description="Target hostname or Kubernetes node identifier")
    vcpu: int = Field(..., ge=1, le=128, description="Number of virtual CPU cores")
    ram_gb: int = Field(..., ge=1, le=1024, description="RAM memory allocated in Gigabytes")
    disk_gb: int = Field(..., ge=10, le=4096, description="OS root disk size in Gigabytes")
    os_distro: LinuxDistro = Field(LinuxDistro.UBUNTU_22_04, description="Base Linux Operating System distribution")
    node_type: str = Field("k8s_worker", description="Role: k8s_worker, k8s_control_plane, or standalone_vm")
    cluster_id: Optional[str] = Field(None, description="Optional target Kubernetes cluster ID")
    k8s_join_token: Optional[str] = Field(None, description="Kubeadm cluster discovery/join token")
    k8s_master_endpoint: Optional[str] = Field(None, description="Kubernetes API server IP/domain")
    storage_volumes: List[StorageVolumeSpec] = Field(default_factory=list, description="Additional attached storage volumes")
    tags: Dict[str, str] = Field(default_factory=dict, description="Metadata tags for infrastructure billing and routing")


class ProvisioningRequest(BaseModel):
    job_name: str = Field(..., min_length=3, max_length=64, description="Human readable provisioning run label")
    provider: ProviderType = Field(..., description="Target cloud or virtualization provider")
    region_or_datacenter: str = Field(..., description="Cloud region or on-prem vCenter/KVM datacenter pool")
    target_type: TargetType = Field(TargetType.K8S_NODE, description="Target workload infrastructure blueprint")
    nodes: List[NodeSpec] = Field(..., min_items=1, description="List of nodes or VMs to provision")
    environment: str = Field("test", description="Target environment tag: test, staging, production")
    preflight_check: bool = Field(True, description="Whether to execute pre-flight quota & API validation before provisioning")
    verify_storage: bool = Field(True, description="Whether to verify storage attachment and I/O health")
    extra_terraform_vars: Dict[str, Any] = Field(default_factory=dict, description="Custom Terraform HCL variable overrides")


class PreflightCheckRequest(BaseModel):
    provider: ProviderType
    requested_vcpu: int = Field(..., ge=1)
    requested_ram_gb: int = Field(..., ge=1)
    requested_storage_gb: int = Field(..., ge=1)
    requested_instances: int = Field(..., ge=1)
    target_region: Optional[str] = None


class PreflightCheckResult(BaseModel):
    passed: bool
    provider: ProviderType
    checks: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    evaluated_at: str


class StorageVerificationRequest(BaseModel):
    node_id: str
    volume_id: str
    mount_point: str
    expected_size_gb: int
    filesystem_type: str = "ext4"


class StorageVerificationResult(BaseModel):
    verified: bool
    node_id: str
    volume_id: str
    mount_point: str
    device_name: str
    actual_size_gb: float
    filesystem: str
    io_write_latency_ms: float
    io_read_latency_ms: float
    details: Dict[str, Any] = Field(default_factory=dict)
    message: str


class NodeResponse(BaseModel):
    id: str
    job_id: str
    name: str
    provider: str
    node_type: str
    ip_address: Optional[str]
    private_ip: Optional[str]
    status: str
    cpu_cores: int
    ram_gb: int
    disk_gb: int
    os_distro: str
    cluster_id: Optional[str]
    health_status: str
    health_metrics: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


class JobResponse(BaseModel):
    id: str
    name: str
    provider: str
    target_type: str
    status: JobStatus
    nodes_count: int
    preflight_passed: Optional[bool] = None
    preflight_results: Optional[Dict[str, Any]] = None
    storage_verification: Optional[Dict[str, Any]] = None
    terraform_state: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    nodes: List[NodeResponse] = Field(default_factory=list)


class SystemHealthResponse(BaseModel):
    status: str
    version: str
    active_jobs: int
    total_managed_nodes: int
    database_ok: bool
    default_providers: List[str]
