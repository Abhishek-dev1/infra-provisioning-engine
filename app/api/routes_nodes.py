"""
Managed Nodes & Virtual Machines API Endpoints.
Provides inspection, telemetry reporting, and health status monitoring for hybrid nodes.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import NodeResponse, NodeHealthStatus
from app.repositories.node_repository import node_repo

router = APIRouter(prefix="/nodes", tags=["Managed Compute Nodes"])


@router.get("", response_model=List[NodeResponse])
def list_nodes(
    job_id: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    cluster_id: Optional[str] = Query(None)
):
    """List managed Kubernetes nodes and virtual machines with optional filtering."""
    rows = node_repo.list_nodes(job_id=job_id, provider=provider, cluster_id=cluster_id)
    return [
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
        for n in rows
    ]


@router.get("/{node_id}", response_model=NodeResponse)
def get_node(node_id: str):
    """Retrieve details, storage volumes, and telemetry for a specific node."""
    node = node_repo.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return NodeResponse(
        id=node["id"],
        job_id=node["job_id"],
        name=node["name"],
        provider=node["provider"],
        node_type=node["node_type"],
        ip_address=node.get("ip_address"),
        private_ip=node.get("private_ip"),
        status=node["status"],
        cpu_cores=node["cpu_cores"],
        ram_gb=node["ram_gb"],
        disk_gb=node["disk_gb"],
        os_distro=node["os_distro"],
        cluster_id=node.get("cluster_id"),
        health_status=node["health_status"],
        health_metrics=node.get("health_metrics"),
        created_at=node["created_at"],
        updated_at=node["updated_at"]
    )


@router.get("/{node_id}/storage")
def get_node_storage_volumes(node_id: str):
    """List all attached storage volumes and verification status for a node."""
    node = node_repo.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return node_repo.list_node_storage_volumes(node_id)
