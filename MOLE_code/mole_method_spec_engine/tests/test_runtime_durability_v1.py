from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mole_runtime_durability_v1 import atomic_write_json, backup_sqlite_database, create_support_bundle, latest_matching_path, write_recovery_snapshot


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

    def test_latest_matching_path_returns_newest_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = write_recovery_snapshot({"n": 1}, root, label="wizard_session", keep=5)
            second = write_recovery_snapshot({"n": 2}, root, label="wizard_session", keep=5)
            latest = latest_matching_path(root, "wizard_session__*.json")
            self.assertEqual(latest, second)
            self.assertNotEqual(first, second)

    def test_support_bundle_copies_manifest_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.json"
            source.write_text(json.dumps({"ok": True}), encoding="utf-8")
            zip_path = create_support_bundle(
                root / "bundles",
                label="runner_support",
                manifest={"app": "runner"},
                artifacts={"config": source, "missing": root / "missing.txt"},
                keep=2,
            )
            self.assertTrue(zip_path.exists())
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = set(zf.namelist())
                self.assertIn("support_bundle_manifest.json", names)
                self.assertIn("config.json", names)
                manifest = json.loads(zf.read("support_bundle_manifest.json").decode("utf-8"))
            self.assertEqual(manifest["app"], "runner")
            self.assertTrue(manifest["artifacts"]["config"]["copied"])
            self.assertFalse(manifest["artifacts"]["missing"]["copied"])


if __name__ == "__main__":
    unittest.main()
