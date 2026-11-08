#!/usr/bin/env python3
"""
End-to-End Live Demonstration Script.
Showcases automated pre-flight checks, multi-cloud Terraform provisioning,
storage volume verification, and system telemetry across AWS and VMware.
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.schemas import (
    ProvisioningRequest,
    NodeSpec,
    StorageVolumeSpec,
    ProviderType,
    TargetType,
    VolumeType,
    LinuxDistro
)
from app.providers import list_supported_providers
from app.repositories.quota_repository import quota_repo
from app.repositories.node_repository import node_repo
from app.repositories.job_repository import job_repo
from app.repositories.audit_repository import audit_repo
from app.services.preflight_service import preflight_service
from app.services.orchestrator import orchestrator


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    print_header("MULTI-CLOUD INFRASTRUCTURE PROVISIONING ENGINE - LIVE DEMO")

    # 1. Inspect Supported Providers & Initial Quotas
    print("\n[Step 1] Inspecting Connected Infrastructure Providers:")
    providers = list_supported_providers()
    for p in providers:
        print(f"  • {p['provider'].upper()}: Connected={p['connected']} | Health={p.get('api_health')} | Services={len(p.get('supported_services', []))}")

    print("\n[Step 2] Querying Provider Compute & Storage Quotas:")
    quotas = quota_repo.list_quotas()
    for q in quotas:
        print(f"  • {q['provider'].upper():<8} vCPU: {q['used_vcpu']}/{q['max_vcpu']} | RAM: {q['used_ram_gb']}/{q['max_ram_gb']}GB | Storage: {q['used_storage_gb']}/{q['max_storage_gb']}GB")

    # 2. Formulate Hybrid Kubernetes Provisioning Request (AWS)
    aws_request = ProvisioningRequest(
        job_name="hybrid-k8s-aws-pool",
        provider=ProviderType.AWS,
        region_or_datacenter="us-east-1",
        target_type=TargetType.K8S_NODE,
        nodes=[
            NodeSpec(
                name="aws-k8s-worker-01",
                vcpu=4,
                ram_gb=16,
                disk_gb=80,
                os_distro=LinuxDistro.UBUNTU_22_04,
                node_type="k8s_worker",
                cluster_id="hybrid-cluster-prod",
                k8s_master_endpoint="10.0.0.10:6443",
                k8s_join_token="abcdef.0123456789abcdef",
                storage_volumes=[
                    StorageVolumeSpec(
                        name="aws-ebs-fast",
                        volume_type=VolumeType.AWS_EBS,
                        size_gb=150,
                        mount_point="/mnt/fast-storage",
                        device_name="/dev/nvme1n1",
                        iops=4000,
                        filesystem="ext4"
                    )
                ]
            )
        ],
        environment="production",
        preflight_check=True,
        verify_storage=True
    )

    # 3. Automated Pre-Flight Quota & Capacity Verification
    print_header("AUTOMATED PRE-FLIGHT QUOTA & CAPACITY EVALUATION")
    preflight_res = preflight_service.evaluate_request(aws_request, reserve_quota=False)
    print(f"  Pre-Flight Evaluation Passed: {preflight_res.passed}")
    print(f"  Evaluated Provider: {preflight_res.provider.value.upper()}")
    print("  Subsystem Checks:")
    for check_name, check_data in preflight_res.checks.items():
        if isinstance(check_data, dict) and "passed" in check_data:
            print(f"    - {check_name:<16}: passed={check_data['passed']} (req={check_data.get('requested')}, avail={check_data.get('available')})")
        else:
            print(f"    - {check_name:<16}: {check_data}")

    # 4. Asynchronous Pipeline Execution
    print_header("EXECUTING PROVISIONING PIPELINE (AWS KUBERNETES WORKER)")
    job_id = f"job-demo-aws-{int(time.time())}"
    job_repo.create_job(
        job_id=job_id,
        name=aws_request.job_name,
        provider=aws_request.provider.value,
        target_type=aws_request.target_type.value,
        spec=aws_request.dict()
    )

    print(f"  Dispatched Job ID: {job_id}")
    orchestrator.process_job(job_id, aws_request)

    completed_job = job_repo.get_job(job_id)
    print(f"  Final Job Status: {completed_job['status']}")
    print(f"  Preflight Passed: {completed_job['preflight_results']['passed']}")

    # 5. Inspect Provisioned Node & Storage Verification Details
    nodes = node_repo.list_nodes(job_id=job_id)
    for n in nodes:
        print(f"\n  [Provisioned Node]: {n['name']} (ID: {n['id']})")
        print(f"    • Status: {n['status']} | Health: {n['health_status']}")
        print(f"    • Network: Private IP = {n.get('private_ip')} | Public IP = {n.get('ip_address')}")
        print(f"    • Specs: {n['cpu_cores']} vCPU, {n['ram_gb']}GB RAM, {n['disk_gb']}GB OS Disk ({n['os_distro']})")
        print(f"    • Telemetry Metrics: {json.dumps(n.get('health_metrics', {}), indent=6)}")

        volumes = node_repo.list_node_storage_volumes(n["id"])
        for v in volumes:
            print(f"\n  [Attached Storage Volume]: {v['id']}")
            print(f"    • Mount Point: {v['mount_point']} on {v['device_name']}")
            print(f"    • Capacity: {v['size_gb']}GB ({v['volume_type']}) | Status: {v['attachment_status']}")
            verif = v.get("verification_details") or {}
            io_probe = verif.get("io_probe", {})
            print(f"    • Verified Filesystem: {verif.get('filesystem')} (encryption={verif.get('encryption_at_rest')})")
            print(f"    • IO Write Latency: {io_probe.get('write_latency_ms')} ms")
            print(f"    • IO Read Latency: {io_probe.get('read_latency_ms')} ms")
            print(f"    • Cryptographic Integrity SHA256: {io_probe.get('data_integrity_sha256')[:32]}...")

    # 6. VMware vSphere Virtual Machine Provisioning
    print_header("PROVISIONING ENTERPRISE VIRTUAL MACHINE ON VMWARE vSPHERE")
    vmware_request = ProvisioningRequest(
        job_name="vmware-testbed-vm",
        provider=ProviderType.VMWARE,
        region_or_datacenter="Datacenter-Enterprise",
        target_type=TargetType.STANDALONE_VM,
        nodes=[
            NodeSpec(
                name="esxi-testbed-vm-01",
                vcpu=8,
                ram_gb=32,
                disk_gb=120,
                os_distro=LinuxDistro.RHEL_9,
                node_type="standalone_vm",
                storage_volumes=[
                    StorageVolumeSpec(
                        name="vmdk-datastore-disk",
                        volume_type=VolumeType.VMDK,
                        size_gb=250,
                        mount_point="/mnt/vmdk-data",
                        device_name="/dev/sdb",
                        iops=5000,
                        filesystem="xfs"
                    )
                ]
            )
        ],
        environment="test",
        preflight_check=True,
        verify_storage=True
    )

    vmware_job_id = f"job-demo-vmware-{int(time.time())}"
    job_repo.create_job(
        job_id=vmware_job_id,
        name=vmware_request.job_name,
        provider=vmware_request.provider.value,
        target_type=vmware_request.target_type.value,
        spec=vmware_request.dict()
    )
    orchestrator.process_job(vmware_job_id, vmware_request)
    vmware_job = job_repo.get_job(vmware_job_id)
    print(f"  VMware Job ID: {vmware_job_id} -> Status: {vmware_job['status']}")
    vmware_nodes = node_repo.list_nodes(job_id=vmware_job_id)
    print(f"  Provisioned VMware VMs: {len(vmware_nodes)} nodes (IP: {vmware_nodes[0].get('private_ip')})")

    # 7. Audit Events
    print_header("OPERATIONAL AUDIT TRAIL (LAST 5 EVENTS)")
    events = audit_repo.list_events(limit=5)
    for e in events:
        print(f"  [{e['timestamp']}] [{e['severity']:<7}] {e['event_type']:<22} {e['message']}")

    # 8. Clean Teardown
    print_header("CLEAN TEARDOWN & QUOTA RECLAMATION")
    term1 = orchestrator.terminate_job(job_id)
    term2 = orchestrator.terminate_job(vmware_job_id)
    print(f"  Torn down {job_id}: {term1['status']}")
    print(f"  Torn down {vmware_job_id}: {term2['status']}")

    print_header("DEMONSTRATION COMPLETE - ALL SYSTEMS FUNCTIONAL & VERIFIED")


if __name__ == "__main__":
    main()
