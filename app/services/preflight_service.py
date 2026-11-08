"""
Pre-Flight Quota & Validation Engine.
Performs automated pre-flight quota calculations, capacity guardrails, regional API checks,
and network IP availability verification prior to launching provisioning jobs.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from app.config import settings
from app.models.schemas import ProvisioningRequest, PreflightCheckResult, ProviderType
from app.repositories.quota_repository import quota_repo
from app.repositories.audit_repository import audit_repo
from app.providers import get_provider


class PreflightService:
    def evaluate_request(
        self,
        request: ProvisioningRequest,
        reserve_quota: bool = True
    ) -> PreflightCheckResult:
        """
        Evaluate full provisioning request against capacity limits and provider constraints.
        If reserve_quota=True and validation passes, reserves resource units in the database.
        """
        now = datetime.utcnow().isoformat()
        provider_str = request.provider.value
        provider = get_provider(request.provider)

        total_vcpu = sum(n.vcpu for n in request.nodes)
        total_ram_gb = sum(n.ram_gb for n in request.nodes)
        total_storage_gb = sum(
            n.disk_gb + sum(v.size_gb for v in n.storage_volumes)
            for n in request.nodes
        )
        total_instances = len(request.nodes)

        checks: Dict[str, Any] = {}
        warnings: List[str] = []
        errors: List[str] = []

        # 1. System Request Ceiling Limits
        if total_vcpu > settings.DEFAULT_MAX_VCPU_PER_REQUEST:
            errors.append(f"Request vCPU ({total_vcpu}) exceeds single-request ceiling ({settings.DEFAULT_MAX_VCPU_PER_REQUEST}).")
        if total_ram_gb > settings.DEFAULT_MAX_RAM_GB_PER_REQUEST:
            errors.append(f"Request RAM ({total_ram_gb}GB) exceeds single-request ceiling ({settings.DEFAULT_MAX_RAM_GB_PER_REQUEST}GB).")
        if total_storage_gb > settings.DEFAULT_MAX_STORAGE_GB_PER_REQUEST:
            errors.append(f"Request Storage ({total_storage_gb}GB) exceeds single-request ceiling ({settings.DEFAULT_MAX_STORAGE_GB_PER_REQUEST}GB).")
        if total_instances > settings.DEFAULT_MAX_NODES_PER_REQUEST:
            errors.append(f"Request node count ({total_instances}) exceeds single-request ceiling ({settings.DEFAULT_MAX_NODES_PER_REQUEST}).")

        # 2. Provider Quota Evaluation
        quota = quota_repo.get_quota(provider_str)
        if not quota:
            errors.append(f"No quota tracking record exists for provider '{provider_str}'.")
            checks["quota_available"] = False
        else:
            avail_vcpu = quota["max_vcpu"] - quota["used_vcpu"]
            avail_ram = quota["max_ram_gb"] - quota["used_ram_gb"]
            avail_storage = quota["max_storage_gb"] - quota["used_storage_gb"]
            avail_instances = quota["max_instances"] - quota["used_instances"]

            checks["vcpu"] = {
                "requested": total_vcpu,
                "available": avail_vcpu,
                "current_used": quota["used_vcpu"],
                "limit": quota["max_vcpu"],
                "passed": total_vcpu <= avail_vcpu
            }
            if total_vcpu > avail_vcpu:
                errors.append(f"Insufficient vCPU quota on {provider_str.upper()}: requested {total_vcpu}, available {avail_vcpu}/{quota['max_vcpu']}.")
            elif avail_vcpu - total_vcpu < (quota["max_vcpu"] * 0.15):
                warnings.append(f"vCPU consumption approaching ceiling (>85% capacity).")

            checks["ram_gb"] = {
                "requested": total_ram_gb,
                "available": avail_ram,
                "current_used": quota["used_ram_gb"],
                "limit": quota["max_ram_gb"],
                "passed": total_ram_gb <= avail_ram
            }
            if total_ram_gb > avail_ram:
                errors.append(f"Insufficient RAM quota on {provider_str.upper()}: requested {total_ram_gb}GB, available {avail_ram}GB/{quota['max_ram_gb']}GB.")

            checks["storage_gb"] = {
                "requested": total_storage_gb,
                "available": avail_storage,
                "current_used": quota["used_storage_gb"],
                "limit": quota["max_storage_gb"],
                "passed": total_storage_gb <= avail_storage
            }
            if total_storage_gb > avail_storage:
                errors.append(f"Insufficient Storage quota on {provider_str.upper()}: requested {total_storage_gb}GB, available {avail_storage}GB/{quota['max_storage_gb']}GB.")

            checks["instances"] = {
                "requested": total_instances,
                "available": avail_instances,
                "current_used": quota["used_instances"],
                "limit": quota["max_instances"],
                "passed": total_instances <= avail_instances
            }
            if total_instances > avail_instances:
                errors.append(f"Insufficient Instance quota on {provider_str.upper()}: requested {total_instances}, available {avail_instances}/{quota['max_instances']}.")

        # 3. Cloud / Hypervisor Endpoint Connectivity Check
        cred_check = provider.validate_credentials()
        checks["provider_endpoint"] = cred_check
        if cred_check.get("api_health") != "UP":
            errors.append(f"Provider API endpoint check failed for {provider_str}: {cred_check}")

        # 4. Storage Architecture & Device Mapping Pre-Flight
        storage_check_ok = True
        for node in request.nodes:
            mount_points_seen = set()
            for vol in node.storage_volumes:
                if vol.mount_point in mount_points_seen:
                    errors.append(f"Duplicate mount_point '{vol.mount_point}' defined on node '{node.name}'.")
                    storage_check_ok = False
                mount_points_seen.add(vol.mount_point)
                if vol.size_gb < 1:
                    errors.append(f"Volume '{vol.name}' size must be >= 1GB.")
                    storage_check_ok = False
        checks["storage_mapping_valid"] = storage_check_ok

        # 5. Network Subnet IP Capacity Pre-Flight
        # Standard test / dev subnet provides ~250 IPs; ensure node count fits comfortably
        checks["network_capacity"] = {
            "estimated_ips_required": total_instances + 2,  # Gateway + DNS overhead
            "subnet_pool_capacity": 250,
            "passed": total_instances <= 240
        }

        passed = len(errors) == 0

        # Atomic reservation if passed and requested
        if passed and reserve_quota:
            ok, reserve_err = quota_repo.check_and_reserve(
                provider_str,
                vcpu=total_vcpu,
                ram_gb=total_ram_gb,
                storage_gb=total_storage_gb,
                instances=total_instances
            )
            if not ok:
                passed = False
                errors.append(reserve_err or "Failed to reserve provider quota atomically.")
            else:
                checks["quota_reserved"] = True

        audit_repo.log_event(
            event_type="PREFLIGHT_CHECK",
            severity="INFO" if passed else "WARNING",
            message=f"Preflight check evaluated for {request.job_name} ({provider_str}): passed={passed}",
            payload={
                "job_name": request.job_name,
                "passed": passed,
                "errors_count": len(errors),
                "warnings_count": len(warnings)
            }
        )

        return PreflightCheckResult(
            passed=passed,
            provider=request.provider,
            checks=checks,
            warnings=warnings,
            errors=errors,
            evaluated_at=now
        )


preflight_service = PreflightService()
