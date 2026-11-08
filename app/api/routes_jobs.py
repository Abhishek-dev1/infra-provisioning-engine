"""
Provisioning Jobs REST API Endpoints.
Provides async submission, lifecycle polling, listing, and teardown operations.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query
from app.models.schemas import ProvisioningRequest, JobResponse, JobStatus, NodeResponse
from app.repositories.job_repository import job_repo
from app.repositories.node_repository import node_repo
from app.services.orchestrator import orchestrator

router = APIRouter(prefix="/provision", tags=["Provisioning Jobs"])


def build_job_response(job: dict) -> JobResponse:
    nodes_rows = node_repo.list_nodes(job_id=job["id"])
    nodes = [
        NodeResponse(
            id=n["id"],
            job_id=n["job_id"],
            name=n["name"],
            provider=n["provider"],
            node_type=n["node_type"],
            ip_address=n.get("ip_address"),
            private_ip=n.get("private_ip"),
            status=n["status"],
            cpu_cores=n["cpu_cores"],
            ram_gb=n["ram_gb"],
            disk_gb=n["disk_gb"],
            os_distro=n["os_distro"],
            cluster_id=n.get("cluster_id"),
            health_status=n["health_status"],
            health_metrics=n.get("health_metrics"),
            created_at=n["created_at"],
            updated_at=n["updated_at"]
        )
        for n in nodes_rows
    ]

    preflight = job.get("preflight_results")
    preflight_passed = preflight.get("passed") if preflight else None

    return JobResponse(
        id=job["id"],
        name=job["name"],
        provider=job["provider"],
        target_type=job["target_type"],
        status=JobStatus(job["status"]),
        nodes_count=len(job.get("spec", {}).get("nodes", [])),
        preflight_passed=preflight_passed,
        preflight_results=preflight,
        storage_verification=job.get("storage_verification"),
        terraform_state=job.get("terraform_state"),
        error_message=job.get("error_message"),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        nodes=nodes
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_provisioning_job(request: ProvisioningRequest):
    """
    Submit a multi-cloud or virtualized infrastructure provisioning request.
    Executes pre-flight checks, Terraform IaC, storage verification, and node registration.
    """
    job = orchestrator.submit_job(request)
    return build_job_response(job)


@router.get("/{job_id}", response_model=JobResponse)
def get_provisioning_job(job_id: str):
    """Retrieve status, telemetry, preflight report, and nodes for a specific job."""
    job = job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return build_job_response(job)


@router.get("", response_model=List[JobResponse])
def list_provisioning_jobs(
    status: Optional[str] = Query(None, description="Filter by status (e.g. COMPLETED, FAILED)"),
    provider: Optional[str] = Query(None, description="Filter by provider (aws, azure, gcp, vmware, kvm)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List historical and active provisioning jobs with optional filtering."""
    jobs = job_repo.list_jobs(status=status, provider=provider, limit=limit, offset=offset)
    return [build_job_response(j) for j in jobs]


@router.delete("/{job_id}")
def terminate_provisioning_job(job_id: str):
    """De-provision and tear down infrastructure resources, releasing reserved quotas."""
    job = job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    res = orchestrator.terminate_job(job_id)
    return res
