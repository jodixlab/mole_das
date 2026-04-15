from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mole_runtime_durability_v1 import atomic_write_json, backup_sqlite_database, write_recovery_snapshot


class RuntimeDurabilityTests(unittest.TestCase):
    def test_recovery_snapshot_rotates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            snapshot_dir = root / "snapshots"
            for idx in range(3):
                write_recovery_snapshot({"n": idx}, snapshot_dir, label="runner_session", keep=2)
            snaps = sorted(snapshot_dir.glob("runner_session__*.json"))
            self.assertEqual(len(snaps), 2)
            payloads = [json.loads(path.read_text(encoding="utf-8"))["n"] for path in snaps]
            self.assertEqual(payloads, [1, 2])

    def test_atomic_write_json_replaces_target(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            atomic_write_json(path, {"status": "new"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], "new")

    def test_sqlite_backup_creates_valid_copy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "source.sqlite"
            con = sqlite3.connect(str(db_path))
            try:
                con.execute("create table sample (id integer primary key, name text)")
                con.execute("insert into sample(name) values ('alpha')")
                con.commit()
            finally:
                con.close()

            backup = backup_sqlite_database(db_path, root / "backups", label="master_db", keep=2)
            self.assertIsNotNone(backup)
            self.assertTrue(Path(backup).exists())

            verify = sqlite3.connect(str(backup))
            try:
                row = verify.execute("select name from sample").fetchone()
            finally:
                verify.close()
            self.assertEqual(row[0], "alpha")


if __name__ == "__main__":
    unittest.main()
