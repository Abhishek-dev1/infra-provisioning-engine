"""
Pre-Flight Quota & Validation API Endpoints.
Allows operators and CI/CD pipelines to validate quotas and cloud connectivity prior to execution.
"""
from fastapi import APIRouter, status
from app.models.schemas import ProvisioningRequest, PreflightCheckResult
from app.services.preflight_service import preflight_service

router = APIRouter(prefix="/preflight", tags=["Pre-Flight Quota Engine"])


@router.post("/check", response_model=PreflightCheckResult)
def run_preflight_check(request: ProvisioningRequest):
    """
    Simulate pre-flight validation against provider capacity limits,
    without creating infrastructure or reserving quota.
    """
    result = preflight_service.evaluate_request(request, reserve_quota=False)
    return result
