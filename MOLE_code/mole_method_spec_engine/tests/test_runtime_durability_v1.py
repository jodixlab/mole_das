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

import mole_runtime_durability_v1 as durability
from mole_runtime_durability_v1 import atomic_write_json, backup_sqlite_database, create_support_bundle, evaluate_runtime_package_status, latest_matching_path, load_latest_health_summary, load_recent_health_history, record_health_journal, write_recovery_snapshot


class RuntimeDurabilityTests(unittest.TestCase):
    def test_package_status_current_for_installed_verified_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            install_root = root / "installed"
            runtime_root = install_root / "runtime"
            (runtime_root / "config").mkdir(parents=True, exist_ok=True)
            acceptance_path = install_root / "PACKAGED_ACCEPTANCE_SUMMARY.json"
            install_manifest_path = install_root / "mole_install_manifest_v1.json"

            install_manifest_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_install_manifest_v1",
                        "install_root": str(install_root),
                        "runtime_root": str(runtime_root),
                        "bundle_label": "MOLE_DAS_2026_04_23_v3",
                    }
                ),
                encoding="utf-8",
            )
            acceptance_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_packaged_acceptance_v1",
                        "status": "PASS",
                        "package_label": "MOLE_DAS_2026_04_23_v3",
                        "generated_at": "2026-04-23T18:37:43Z",
                    }
                ),
                encoding="utf-8",
            )

            original = durability.load_uninstall_registration
            durability.load_uninstall_registration = lambda: {
                "install_location": str(install_root),
                "display_version": "MOLE_DAS_2026_04_23_v3",
            }
            try:
                result = evaluate_runtime_package_status(
                    current_runtime_root=runtime_root,
                    current_build_identity={
                        "bundle_label": "MOLE_DAS_2026_04_23_v3",
                        "built_at": "2026-04-23T18:26:02Z",
                        "runtime_root": str(runtime_root),
                    },
                    current_acceptance_summary_path=acceptance_path,
                )
            finally:
                durability.load_uninstall_registration = original

            self.assertEqual(result["package_status"], "CURRENT")
            self.assertEqual(result["install_root_path"], str(install_root.resolve()))
            self.assertEqual(result["local_accepted_package_marker_path"], str(acceptance_path.resolve()))

    def test_package_status_current_for_installed_runtime_without_registry_entry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            install_root = root / "installed"
            runtime_root = install_root / "runtime"
            (runtime_root / "config").mkdir(parents=True, exist_ok=True)
            acceptance_path = install_root / "PACKAGED_ACCEPTANCE_SUMMARY.json"
            install_manifest_path = install_root / "mole_install_manifest_v1.json"

            install_manifest_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_install_manifest_v1",
                        "install_root": str(install_root),
                        "runtime_root": str(runtime_root),
                        "bundle_label": "MOLE_DAS_2026_04_23_v4",
                    }
                ),
                encoding="utf-8",
            )
            acceptance_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_packaged_acceptance_v1",
                        "status": "PASS",
                        "package_label": "MOLE_DAS_2026_04_23_v4",
                        "generated_at": "2026-04-23T19:21:17Z",
                    }
                ),
                encoding="utf-8",
            )

            original = durability.load_uninstall_registration
            durability.load_uninstall_registration = lambda: {}
            try:
                result = evaluate_runtime_package_status(
                    current_runtime_root=runtime_root,
                    current_build_identity={
                        "bundle_label": "MOLE_DAS_2026_04_23_v4",
                        "built_at": "2026-04-23T19:07:12Z",
                        "runtime_root": str(runtime_root),
                    },
                    current_acceptance_summary_path=acceptance_path,
                )
            finally:
                durability.load_uninstall_registration = original

            self.assertEqual(result["package_status"], "CURRENT")
            self.assertEqual(result["install_root_path"], str(install_root.resolve()))
            self.assertEqual(result["uninstall_registry_install_location"], "")

    def test_package_status_portable_when_no_install_root_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runtime_root = root / "portable" / "runtime"
            runtime_root.mkdir(parents=True, exist_ok=True)
            acceptance_path = root / "portable" / "PACKAGED_ACCEPTANCE_SUMMARY.json"
            acceptance_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_packaged_acceptance_v1",
                        "status": "PASS",
                        "package_label": "MOLE_DAS_2026_04_23_v3",
                    }
                ),
                encoding="utf-8",
            )

            original = durability.load_uninstall_registration
            durability.load_uninstall_registration = lambda: {}
            try:
                result = evaluate_runtime_package_status(
                    current_runtime_root=runtime_root,
                    current_build_identity={
                        "bundle_label": "MOLE_DAS_2026_04_23_v3",
                        "built_at": "2026-04-23T18:26:02Z",
                        "runtime_root": str(runtime_root),
                    },
                    current_acceptance_summary_path=acceptance_path,
                )
            finally:
                durability.load_uninstall_registration = original

            self.assertEqual(result["package_status"], "PORTABLE")

    def test_package_status_stale_for_older_portable_against_installed_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            install_root = root / "installed"
            install_runtime_root = install_root / "runtime"
            portable_root = root / "portable"
            portable_runtime_root = portable_root / "runtime"
            install_runtime_root.mkdir(parents=True, exist_ok=True)
            portable_runtime_root.mkdir(parents=True, exist_ok=True)

            (install_root / "mole_install_manifest_v1.json").write_text(
                json.dumps(
                    {
                        "schema": "mole_install_manifest_v1",
                        "install_root": str(install_root),
                        "runtime_root": str(install_runtime_root),
                        "bundle_label": "MOLE_DAS_2026_04_23_v5",
                    }
                ),
                encoding="utf-8",
            )
            (install_root / "PACKAGED_ACCEPTANCE_SUMMARY.json").write_text(
                json.dumps(
                    {
                        "schema": "mole_packaged_acceptance_v1",
                        "status": "PASS",
                        "package_label": "MOLE_DAS_2026_04_23_v5",
                    }
                ),
                encoding="utf-8",
            )
            (install_runtime_root / "config").mkdir(parents=True, exist_ok=True)
            (install_runtime_root / "config" / "mole_build_identity_v1.json").write_text(
                json.dumps(
                    {
                        "schema": "mole_build_identity_v1",
                        "bundle_label": "MOLE_DAS_2026_04_23_v5",
                        "built_at": "2026-04-23T20:00:00Z",
                        "runtime_root": str(install_runtime_root),
                    }
                ),
                encoding="utf-8",
            )
            current_acceptance_path = portable_root / "PACKAGED_ACCEPTANCE_SUMMARY.json"
            current_acceptance_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_packaged_acceptance_v1",
                        "status": "PASS",
                        "package_label": "MOLE_DAS_2026_04_23_v3",
                    }
                ),
                encoding="utf-8",
            )

            original = durability.load_uninstall_registration
            durability.load_uninstall_registration = lambda: {
                "install_location": str(install_root),
                "display_version": "MOLE_DAS_2026_04_23_v5",
            }
            try:
                result = evaluate_runtime_package_status(
                    current_runtime_root=portable_runtime_root,
                    current_build_identity={
                        "bundle_label": "MOLE_DAS_2026_04_23_v3",
                        "built_at": "2026-04-23T18:26:02Z",
                        "runtime_root": str(portable_runtime_root),
                    },
                    current_acceptance_summary_path=current_acceptance_path,
                )
            finally:
                durability.load_uninstall_registration = original

            self.assertEqual(result["package_status"], "STALE")

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

    def test_health_journal_updates_latest_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = record_health_journal(root / "journal", label="runner", event="START", payload={"state": "RUNNING"}, keep_lines=3)
            self.assertTrue(paths["latest"].exists())
            self.assertTrue(paths["history"].exists())
            latest = json.loads(paths["latest"].read_text(encoding="utf-8"))
            self.assertEqual(latest["state"], "RUNNING")
            self.assertEqual(latest["last_event"], "START")
            record_health_journal(root / "journal", label="runner", event="STOP", payload={"state": "STOPPED"}, keep_lines=3)
            history_lines = paths["history"].read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(history_lines), 2)
            self.assertEqual(json.loads(history_lines[-1])["event"], "STOP")
            latest = load_latest_health_summary(root / "journal", label="runner")
            self.assertEqual(latest["state"], "STOPPED")
            self.assertEqual(latest["last_event"], "STOP")
            recent = load_recent_health_history(root / "journal", label="runner", limit=1)
            self.assertEqual(len(recent), 1)
            self.assertEqual(recent[0]["event"], "STOP")


if __name__ == "__main__":
    unittest.main()
