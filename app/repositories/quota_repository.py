"""
Provider Quota Repository.
Handles atomic reservation, verification, and release of compute, memory, and storage limits.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from app.core.database import db


class QuotaRepository:
    def get_quota(self, provider: str) -> Optional[Dict[str, Any]]:
        return db.fetch_one("SELECT * FROM provider_quotas WHERE provider = ?;", (provider.lower(),))

    def list_quotas(self) -> List[Dict[str, Any]]:
        return db.fetch_all("SELECT * FROM provider_quotas ORDER BY provider ASC;")

    def check_and_reserve(
        self,
        provider: str,
        vcpu: int,
        ram_gb: int,
        storage_gb: int,
        instances: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Atomically verify that requested capacity fits within provider ceilings,
        and increment current consumption counters.
        """
        provider_key = provider.lower()
        now = datetime.utcnow().isoformat()
        with db.transaction() as cursor:
            cursor.execute("SELECT * FROM provider_quotas WHERE provider = ?;", (provider_key,))
            q = cursor.fetchone()
            if not q:
                return False, f"Provider '{provider}' is not configured in quota limits."

            # Calculate prospective totals
            new_vcpu = q["used_vcpu"] + vcpu
            new_ram = q["used_ram_gb"] + ram_gb
            new_storage = q["used_storage_gb"] + storage_gb
            new_instances = q["used_instances"] + instances

            if new_vcpu > q["max_vcpu"]:
                return False, f"Quota Exceeded: vCPU request ({vcpu}) brings usage to {new_vcpu}/{q['max_vcpu']}."
            if new_ram > q["max_ram_gb"]:
                return False, f"Quota Exceeded: RAM request ({ram_gb}GB) brings usage to {new_ram}/{q['max_ram_gb']}GB."
            if new_storage > q["max_storage_gb"]:
                return False, f"Quota Exceeded: Storage request ({storage_gb}GB) brings usage to {new_storage}/{q['max_storage_gb']}GB."
            if new_instances > q["max_instances"]:
                return False, f"Quota Exceeded: Instance count ({instances}) brings usage to {new_instances}/{q['max_instances']}."

            cursor.execute("""
            UPDATE provider_quotas
            SET used_vcpu = ?, used_ram_gb = ?, used_storage_gb = ?, used_instances = ?, updated_at = ?
            WHERE provider = ?;
            """, (new_vcpu, new_ram, new_storage, new_instances, now, provider_key))

            return True, None

    def release_quota(
        self,
        provider: str,
        vcpu: int,
        ram_gb: int,
        storage_gb: int,
        instances: int
    ) -> None:
        """Release allocated quota upon job cancellation, failure, or teardown."""
        provider_key = provider.lower()
        now = datetime.utcnow().isoformat()
        with db.transaction() as cursor:
            cursor.execute("SELECT * FROM provider_quotas WHERE provider = ?;", (provider_key,))
            q = cursor.fetchone()
            if not q:
                return

            new_vcpu = max(0, q["used_vcpu"] - vcpu)
            new_ram = max(0, q["used_ram_gb"] - ram_gb)
            new_storage = max(0, q["used_storage_gb"] - storage_gb)
            new_instances = max(0, q["used_instances"] - instances)

            cursor.execute("""
            UPDATE provider_quotas
            SET used_vcpu = ?, used_ram_gb = ?, used_storage_gb = ?, used_instances = ?, updated_at = ?
            WHERE provider = ?;
            """, (new_vcpu, new_ram, new_storage, new_instances, now, provider_key))


quota_repo = QuotaRepository()
