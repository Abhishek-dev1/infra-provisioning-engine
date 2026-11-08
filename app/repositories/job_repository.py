"""
Job Repository Module.
Handles persistence and lifecycle state tracking for provisioning workflows in SQLite.
"""
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from app.core.database import db
from app.models.schemas import JobStatus


class JobRepository:
    def create_job(
        self,
        job_id: str,
        name: str,
        provider: str,
        target_type: str,
        spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        with db.transaction() as cursor:
            cursor.execute("""
            INSERT INTO provisioning_jobs (
                id, name, provider, target_type, status, spec_json,
                preflight_results_json, storage_verification_json, terraform_state_json,
                error_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?);
            """, (
                job_id,
                name,
                provider,
                target_type,
                JobStatus.PENDING.value,
                json.dumps(spec),
                now,
                now
            ))
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        row = db.fetch_one("SELECT * FROM provisioning_jobs WHERE id = ?;", (job_id,))
        if not row:
            return None
        return self._deserialize_job(row)

    def list_jobs(
        self,
        status: Optional[str] = None,
        provider: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM provisioning_jobs WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        rows = db.fetch_all(query, tuple(params))
        return [self._deserialize_job(r) for r in rows]

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None
    ) -> None:
        now = datetime.utcnow().isoformat()
        with db.transaction() as cursor:
            if error_message is not None:
                cursor.execute("""
                UPDATE provisioning_jobs
                SET status = ?, error_message = ?, updated_at = ?
                WHERE id = ?;
                """, (status.value, error_message, now, job_id))
            else:
                cursor.execute("""
                UPDATE provisioning_jobs
                SET status = ?, updated_at = ?
                WHERE id = ?;
                """, (status.value, now, job_id))

    def update_job_preflight(self, job_id: str, results: Dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        with db.transaction() as cursor:
            cursor.execute("""
            UPDATE provisioning_jobs
            SET preflight_results_json = ?, updated_at = ?
            WHERE id = ?;
            """, (json.dumps(results), now, job_id))

    def update_job_storage_verification(self, job_id: str, results: Dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        with db.transaction() as cursor:
            cursor.execute("""
            UPDATE provisioning_jobs
            SET storage_verification_json = ?, updated_at = ?
            WHERE id = ?;
            """, (json.dumps(results), now, job_id))

    def update_job_terraform_state(self, job_id: str, tf_state: Dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        with db.transaction() as cursor:
            cursor.execute("""
            UPDATE provisioning_jobs
            SET terraform_state_json = ?, updated_at = ?
            WHERE id = ?;
            """, (json.dumps(tf_state), now, job_id))

    def delete_job(self, job_id: str) -> bool:
        with db.transaction() as cursor:
            cursor.execute("DELETE FROM provisioning_jobs WHERE id = ?;", (job_id,))
            return cursor.rowcount > 0

    def _deserialize_job(self, row: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(row)
        data["spec"] = json.loads(data["spec_json"]) if data.get("spec_json") else {}
        data["preflight_results"] = json.loads(data["preflight_results_json"]) if data.get("preflight_results_json") else None
        data["storage_verification"] = json.loads(data["storage_verification_json"]) if data.get("storage_verification_json") else None
        data["terraform_state"] = json.loads(data["terraform_state_json"]) if data.get("terraform_state_json") else None
        return data


job_repo = JobRepository()
