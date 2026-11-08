"""
Infrastructure Provider & Quota API Endpoints.
Exposes multi-cloud health, API capabilities, and real-time quota consumption metrics.
"""
from typing import List, Dict, Any
from fastapi import APIRouter
from app.providers import list_supported_providers
from app.repositories.quota_repository import quota_repo

router = APIRouter(prefix="/providers", tags=["Infrastructure Providers"])


@router.get("", response_model=List[Dict[str, Any]])
def get_providers():
    """List all supported cloud (AWS, Azure, GCP) and virtualization (VMware, KVM) providers."""
    return list_supported_providers()


@router.get("/quotas", response_model=List[Dict[str, Any]])
def get_provider_quotas():
    """Get active resource quota utilization, limits, and capacity margins across providers."""
    return quota_repo.list_quotas()
