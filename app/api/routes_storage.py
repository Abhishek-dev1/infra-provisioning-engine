"""
Storage Volume Verification REST API Endpoints.
Allows manual or automated validation of block/NFS storage attachments and I/O health.
"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import StorageVerificationRequest, StorageVerificationResult, StorageVolumeSpec
from app.repositories.node_repository import node_repo
from app.services.storage_service import storage_service

router = APIRouter(prefix="/storage", tags=["Storage Verification"])


@router.post("/verify", response_model=StorageVerificationResult)
def verify_storage_volume(req: StorageVerificationRequest):
    """Run simulated cryptographic I/O latency verification on a target storage volume."""
    vol = node_repo.get_storage_volume(req.volume_id)
    if not vol:
        raise HTTPException(status_code=404, detail=f"Storage volume '{req.volume_id}' not found")

    spec = StorageVolumeSpec(
        name=vol["id"],
        volume_type=vol["volume_type"],
        size_gb=req.expected_size_gb,
        mount_point=req.mount_point,
        device_name=vol.get("device_name"),
        iops=vol.get("iops", 3000),
        filesystem=req.filesystem_type
    )

    result = storage_service.verify_volume_attachment(
        node_id=req.node_id,
        volume_id=req.volume_id,
        volume_spec=spec
    )
    return result


@router.get("/volumes/{volume_id}")
def get_volume_details(volume_id: str):
    """Retrieve database record and verification state of a storage volume."""
    vol = node_repo.get_storage_volume(volume_id)
    if not vol:
        raise HTTPException(status_code=404, detail=f"Storage volume '{volume_id}' not found")
    return vol
