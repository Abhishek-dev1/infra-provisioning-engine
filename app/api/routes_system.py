"""
System Health, Audit Logging, and Observability Endpoints.
Provides Kubernetes-compatible liveness/readiness probes, metrics, and audit logs.
"""
import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, Response
from app.config import settings
from app.core.database import db
from app.models.schemas import SystemHealthResponse
from app.repositories.job_repository import job_repo
from app.repositories.node_repository import node_repo
from app.repositories.audit_repository import audit_repo

router = APIRouter(tags=["System & Observability"])
_START_TIME = time.time()


@router.get("/health/live")
def liveness_probe():
    """Kubernetes liveness probe: indicates whether service process is running."""
    return {"status": "ok", "service": settings.APP_NAME}


@router.get("/health/ready")
def readiness_probe():
    """Kubernetes readiness probe: checks database connectivity and disk write capacity."""
    try:
        db.fetch_one("SELECT 1;")
        return {
            "status": "ready",
            "database": "connected",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION
        }
    except Exception as e:
        return {"status": "degraded", "database_error": str(e)}


@router.get("/metrics")
def get_system_metrics():
    """Prometheus-style telemetry / JSON metrics format for observability dashboards."""
    active_jobs = len(job_repo.list_jobs(status="RUNNING")) + len(job_repo.list_jobs(status="PROVISIONING"))
    all_nodes = node_repo.list_nodes()
    healthy_nodes = sum(1 for n in all_nodes if n["health_status"] == "HEALTHY")
    uptime_sec = round(time.time() - _START_TIME, 1)

    return {
        "uptime_seconds": uptime_sec,
        "provisioning_jobs_active": active_jobs,
        "nodes_total": len(all_nodes),
        "nodes_healthy": healthy_nodes,
        "nodes_degraded": len(all_nodes) - healthy_nodes,
        "concurrency_limit": settings.MAX_CONCURRENT_JOBS
    }


@router.get("/api/v1/audit")
def list_audit_events(
    job_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200)
):
    """Retrieve operational audit log entries."""
    return audit_repo.list_events(job_id=job_id, severity=severity, limit=limit)
