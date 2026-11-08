"""
Audit Event Repository.
Maintains tamper-evident operational logs for infrastructure changes, approvals, and failures.
"""
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from app.core.database import db


class AuditRepository:
    def log_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        job_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        payload_json = json.dumps(payload) if payload else None
        with db.transaction() as cursor:
            cursor.execute("""
            INSERT INTO audit_events (
                job_id, event_type, severity, message, payload_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?);
            """, (job_id, event_type, severity, message, payload_json, now))
            event_id = cursor.lastrowid

        return {
            "id": event_id,
            "job_id": job_id,
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "payload": payload,
            "timestamp": now
        }

    def list_events(
        self,
        job_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: List[Any] = []
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        if severity:
            query += " AND severity = ?"
            params.append(severity.upper())
        query += " ORDER BY id DESC LIMIT ?;"
        params.append(limit)

        rows = db.fetch_all(query, tuple(params))
        events = []
        for r in rows:
            item = dict(r)
            item["payload"] = json.loads(item["payload_json"]) if item.get("payload_json") else None
            events.append(item)
        return events


audit_repo = AuditRepository()
