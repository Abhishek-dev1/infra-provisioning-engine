"""
Node and Storage Volume Repository.
Manages database records for virtual machines, Kubernetes nodes, and storage volume attachments.
"""
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from app.core.database import db


class NodeRepository:
    def create_node(
        self,
        node_id: str,
        job_id: str,
        name: str,
        provider: str,
        node_type: str,
        cpu_cores: int,
        ram_gb: int,
        disk_gb: int,
        os_distro: str,
        cluster_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        private_ip: Optional[str] = None,
        status: str = "PROVISIONING",
        health_status: str = "UNKNOWN"
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        with db.transaction() as cursor:
            cursor.execute("""
            INSERT INTO nodes (
                id, job_id, name, provider, node_type, ip_address, private_ip,
                status, cpu_cores, ram_gb, disk_gb, os_distro, cluster_id,
                health_status, health_metrics_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?);
            """, (
                node_id, job_id, name, provider, node_type, ip_address, private_ip,
                status, cpu_cores, ram_gb, disk_gb, os_distro, cluster_id,
                health_status, now, now
            ))
        return self.get_node(node_id)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        row = db.fetch_one("SELECT * FROM nodes WHERE id = ?;", (node_id,))
        if not row:
            return None
        return self._deserialize_node(row)

    def list_nodes(
        self,
        job_id: Optional[str] = None,
        provider: Optional[str] = None,
        cluster_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM nodes WHERE 1=1"
        params: List[Any] = []
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        if cluster_id:
            query += " AND cluster_id = ?"
            params.append(cluster_id)
        query += " ORDER BY created_at ASC;"

        rows = db.fetch_all(query, tuple(params))
        return [self._deserialize_node(r) for r in rows]

    def update_node_network(self, node_id: str, ip_address: str, private_ip: str) -> None:
        now = datetime.utcnow().isoformat()
        with db.transaction() as cursor:
            cursor.execute("""
            UPDATE nodes
            SET ip_address = ?, private_ip = ?, updated_at = ?
            WHERE id = ?;
            """, (ip_address, private_ip, now, node_id))

    def update_node_status(self, node_id: str, status: str) -> None:
        now = datetime.utcnow().isoformat()
        with db.transaction() as cursor:
            cursor.execute("""
            UPDATE nodes
            SET status = ?, updated_at = ?
            WHERE id = ?;
            """, (status, now, node_id))

    def update_node_health(
        self,
        node_id: str,
        health_status: str,
        metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        now = datetime.utcnow().isoformat()
        metrics_json = json.dumps(metrics) if metrics else None
        with db.transaction() as cursor:
            cursor.execute("""
            UPDATE nodes
            SET health_status = ?, health_metrics_json = ?, updated_at = ?
            WHERE id = ?;
            """, (health_status, metrics_json, now, node_id))

    # --- Storage Volume Operations ---

    def create_storage_volume(
        self,
        volume_id: str,
        node_id: str,
        job_id: str,
        volume_type: str,
        size_gb: int,
        mount_point: str,
        device_name: str,
        iops: int = 3000,
        attachment_status: str = "PENDING"
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        with db.transaction() as cursor:
            cursor.execute("""
            INSERT INTO storage_volumes (
                id, node_id, job_id, volume_type, size_gb, mount_point,
                device_name, iops, attachment_status, verification_details_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?);
            """, (
                volume_id, node_id, job_id, volume_type, size_gb, mount_point,
                device_name, iops, attachment_status, now
            ))
        return self.get_storage_volume(volume_id)

    def get_storage_volume(self, volume_id: str) -> Optional[Dict[str, Any]]:
        row = db.fetch_one("SELECT * FROM storage_volumes WHERE id = ?;", (volume_id,))
        if not row:
            return None
        return self._deserialize_volume(row)

    def list_node_storage_volumes(self, node_id: str) -> List[Dict[str, Any]]:
        rows = db.fetch_all("SELECT * FROM storage_volumes WHERE node_id = ?;", (node_id,))
        return [self._deserialize_volume(r) for r in rows]

    def update_volume_status(
        self,
        volume_id: str,
        status: str,
        verification_details: Optional[Dict[str, Any]] = None
    ) -> None:
        details_json = json.dumps(verification_details) if verification_details else None
        with db.transaction() as cursor:
            cursor.execute("""
            UPDATE storage_volumes
            SET attachment_status = ?, verification_details_json = ?
            WHERE id = ?;
            """, (status, details_json, volume_id))

    def _deserialize_node(self, row: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(row)
        data["health_metrics"] = (
            json.loads(data["health_metrics_json"])
            if data.get("health_metrics_json")
            else None
        )
        return data

    def _deserialize_volume(self, row: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(row)
        data["verification_details"] = (
            json.loads(data["verification_details_json"])
            if data.get("verification_details_json")
            else None
        )
        return data


node_repo = NodeRepository()
