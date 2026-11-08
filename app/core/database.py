"""
SQLite Database Engine & Schema Management.
Provides thread-safe connections, transaction management, and automatic schema initialization.
"""
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Any, Dict, List, Optional
from app.config import settings

_local = threading.local()


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> Dict[str, Any]:
    """Convert SQLite row tuples to dictionaries."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DB_PATH
        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Get or initialize thread-local SQLite connection with foreign keys and dict factory."""
        if not hasattr(_local, "connection") or _local.connection is None:
            conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0,
                isolation_level=None  # Enable autocommit mode / manual transactions
            )
            conn.row_factory = dict_factory
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")  # High-concurrency WAL mode
            conn.execute("PRAGMA synchronous = NORMAL;")
            _local.connection = conn
        return _local.connection

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for atomic database transactions."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE;")
        try:
            yield cursor
            cursor.execute("COMMIT;")
        except Exception:
            cursor.execute("ROLLBACK;")
            raise
        finally:
            cursor.close()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query directly using thread-local connection."""
        conn = self.get_connection()
        return conn.execute(query, params)

    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all matching rows as dictionaries."""
        cursor = self.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch single matching row as a dictionary or None."""
        cursor = self.execute(query, params)
        row = cursor.fetchone()
        cursor.close()
        return row

    def init_schema(self) -> None:
        """Initialize database schema tables and seed baseline provider quota definitions."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        with conn:
            # 1. Provisioning Jobs Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS provisioning_jobs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                target_type TEXT NOT NULL,
                status TEXT NOT NULL,
                spec_json TEXT NOT NULL,
                preflight_results_json TEXT,
                storage_verification_json TEXT,
                terraform_state_json TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 2. Managed Nodes & Virtual Machines Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                node_type TEXT NOT NULL,
                ip_address TEXT,
                private_ip TEXT,
                status TEXT NOT NULL,
                cpu_cores INTEGER NOT NULL,
                ram_gb INTEGER NOT NULL,
                disk_gb INTEGER NOT NULL,
                os_distro TEXT NOT NULL,
                cluster_id TEXT,
                health_status TEXT NOT NULL,
                health_metrics_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES provisioning_jobs(id) ON DELETE CASCADE
            );
            """)

            # 3. Storage Volumes & Attachments Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS storage_volumes (
                id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                volume_type TEXT NOT NULL,
                size_gb INTEGER NOT NULL,
                mount_point TEXT NOT NULL,
                device_name TEXT NOT NULL,
                iops INTEGER DEFAULT 3000,
                attachment_status TEXT NOT NULL,
                verification_details_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (job_id) REFERENCES provisioning_jobs(id) ON DELETE CASCADE
            );
            """)

            # 4. Provider Quotas Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_quotas (
                provider TEXT PRIMARY KEY,
                max_vcpu INTEGER NOT NULL,
                used_vcpu INTEGER NOT NULL DEFAULT 0,
                max_ram_gb INTEGER NOT NULL,
                used_ram_gb INTEGER NOT NULL DEFAULT 0,
                max_storage_gb INTEGER NOT NULL,
                used_storage_gb INTEGER NOT NULL DEFAULT 0,
                max_instances INTEGER NOT NULL,
                used_instances INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """)

            # 5. Audit Events Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                payload_json TEXT,
                timestamp TEXT NOT NULL
            );
            """)

            # Seed default quotas if table is empty
            cursor = conn.execute("SELECT COUNT(*) AS count FROM provider_quotas;")
            if cursor.fetchone()[0] == 0:
                now = datetime.utcnow().isoformat()
                default_quotas = [
                    ("aws", 256, 32, 1024, 128, 10000, 1200, 50, 6, now),
                    ("azure", 256, 16, 1024, 64, 10000, 800, 50, 4, now),
                    ("gcp", 256, 24, 1024, 96, 10000, 1500, 50, 5, now),
                    ("vmware", 512, 128, 2048, 512, 25000, 4500, 100, 18, now),
                    ("kvm", 128, 48, 512, 192, 5000, 1600, 30, 10, now),
                ]
                conn.executemany("""
                INSERT INTO provider_quotas (
                    provider, max_vcpu, used_vcpu, max_ram_gb, used_ram_gb,
                    max_storage_gb, used_storage_gb, max_instances, used_instances, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, default_quotas)
        conn.close()


# Global database instance
db = Database()
