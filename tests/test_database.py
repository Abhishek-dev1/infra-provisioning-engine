"""
Unit tests for SQLite database operations, transactions, and schema persistence.
"""
import os
import tempfile
import unittest
from app.core.database import Database


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db = Database(db_path=self.temp_db.name)

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            os.remove(self.temp_db.name)

    def test_schema_initialization(self):
        tables = self.db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        table_names = [t["name"] for t in tables]
        self.assertIn("provisioning_jobs", table_names)
        self.assertIn("nodes", table_names)
        self.assertIn("storage_volumes", table_names)
        self.assertIn("provider_quotas", table_names)
        self.assertIn("audit_events", table_names)

    def test_seeded_quotas(self):
        quotas = self.db.fetch_all("SELECT * FROM provider_quotas;")
        providers = {q["provider"] for q in quotas}
        self.assertEqual(providers, {"aws", "azure", "gcp", "vmware", "kvm"})

    def test_transaction_commit_and_rollback(self):
        # 1. Successful transaction
        with self.db.transaction() as cursor:
            cursor.execute("""
            INSERT INTO audit_events (job_id, event_type, severity, message, timestamp)
            VALUES ('job-1', 'TEST', 'INFO', 'Committed event', '2026-01-01T00:00:00');
            """)

        row = self.db.fetch_one("SELECT * FROM audit_events WHERE job_id = 'job-1';")
        self.assertIsNotNone(row)
        self.assertEqual(row["message"], "Committed event")

        # 2. Rolled back transaction
        try:
            with self.db.transaction() as cursor:
                cursor.execute("""
                INSERT INTO audit_events (job_id, event_type, severity, message, timestamp)
                VALUES ('job-2', 'TEST', 'INFO', 'Failed event', '2026-01-01T00:00:00');
                """)
                raise RuntimeError("Simulated failure inside transaction")
        except RuntimeError:
            pass

        row_fail = self.db.fetch_one("SELECT * FROM audit_events WHERE job_id = 'job-2';")
        self.assertIsNone(row_fail)


if __name__ == "__main__":
    unittest.main()
