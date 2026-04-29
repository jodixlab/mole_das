from __future__ import annotations

import hashlib
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
from mole_runtime_durability_v1 import atomic_write_json, backup_sqlite_database, create_support_bundle, evaluate_runtime_action_policy, evaluate_runtime_package_status, latest_matching_path, load_latest_health_summary, load_recent_health_history, record_health_journal, resolve_runtime_storage_layout, resolve_runtime_storage_layout_from_root, verify_verified_release_reference, write_recovery_snapshot


class RuntimeDurabilityTests(unittest.TestCase):
    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest().upper()

    def test_packaged_runtime_layout_uses_external_data_root_and_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            install_root = Path(td) / "MOLE_DAS_2026_04_28_v5"
            runtime_root = install_root / "runtime"
            code_root = runtime_root / "MOLE_code"
            seed_root = runtime_root / "mole_das_data"
            (code_root).mkdir(parents=True, exist_ok=True)
            (seed_root / "configs").mkdir(parents=True, exist_ok=True)
            (seed_root / "db").mkdir(parents=True, exist_ok=True)
            (seed_root / "rule_packs").mkdir(parents=True, exist_ok=True)
            (seed_root / "configs" / "mole_session_2026_03_31_1209.json").write_text("{}", encoding="utf-8")
            (seed_root / "configs" / "mole_config.json").write_text("{}", encoding="utf-8")
            (seed_root / "db" / "mole_master.sqlite").write_text("seed-db", encoding="utf-8")
            (seed_root / "rule_packs" / "sample_rule.json").write_text("{}", encoding="utf-8")

            layout = resolve_runtime_storage_layout(code_root, env_mode="PRODUCTION", seed_if_missing=True)

            self.assertTrue(layout["packaged_layout"])
            self.assertEqual(Path(layout["data_root"]), (install_root / "data").resolve())
            self.assertTrue((install_root / "data" / "configs" / "mole_session_2026_03_31_1209.json").exists())
            self.assertFalse((install_root / "data" / "configs" / "mole_config.json").exists())
            self.assertTrue((install_root / "data" / "db" / "mole_master.sqlite").exists())
            self.assertTrue((install_root / "data" / "rule_packs" / "sample_rule.json").exists())
            manifest_path = install_root / "data" / "data_root_manifest_v1.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema"], durability.DATA_ROOT_MANIFEST_SCHEMA)
            self.assertEqual(manifest["data_schema_version"], durability.DATA_ROOT_SCHEMA_VERSION)
            self.assertEqual(Path(manifest["data_root"]), (install_root / "data").resolve())

    def test_packaged_runtime_migrates_legacy_mutable_payload_out_of_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            install_root = Path(td) / "MOLE_DAS_2026_04_28_v5"
            runtime_root = install_root / "runtime"
            code_root = runtime_root / "MOLE_code"
            seed_root = runtime_root / "mole_das_data"
            (code_root).mkdir(parents=True, exist_ok=True)
            (seed_root / "configs").mkdir(parents=True, exist_ok=True)
            (seed_root / "db").mkdir(parents=True, exist_ok=True)
            (seed_root / "rule_packs").mkdir(parents=True, exist_ok=True)
            (seed_root / "logs").mkdir(parents=True, exist_ok=True)
            (seed_root / "exports").mkdir(parents=True, exist_ok=True)
            (seed_root / "configs" / "mole_session_2026_03_31_1209.json").write_text("{}", encoding="utf-8")
            (seed_root / "db" / "mole_master.sqlite").write_text("seed-db", encoding="utf-8")
            (seed_root / "logs" / "legacy_runtime.log").write_text("legacy", encoding="utf-8")
            (seed_root / "exports" / "legacy_report.txt").write_text("legacy-report", encoding="utf-8")

            layout = resolve_runtime_storage_layout(code_root, env_mode="PRODUCTION", seed_if_missing=True)

            self.assertFalse((seed_root / "logs" / "legacy_runtime.log").exists())
            self.assertFalse((seed_root / "exports" / "legacy_report.txt").exists())
            self.assertTrue((install_root / "data" / "logs" / "legacy_runtime.log").exists())
            self.assertTrue((install_root / "data" / "exports" / "legacy_report.txt").exists())
            manifest = json.loads((install_root / "data" / "data_root_manifest_v1.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["migration"]["performed"])
            self.assertIn("logs", manifest["migration"]["migrated_labels"])
            self.assertTrue(Path(manifest["migration"]["backup_path"]).exists())

    def test_packaged_runtime_manifest_preserves_migration_state_across_repeat_seed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            install_root = Path(td) / "MOLE_DAS_2026_04_28_v5"
            runtime_root = install_root / "runtime"
            code_root = runtime_root / "MOLE_code"
            seed_root = runtime_root / "mole_das_data"
            (code_root).mkdir(parents=True, exist_ok=True)
            (seed_root / "configs").mkdir(parents=True, exist_ok=True)
            (seed_root / "db").mkdir(parents=True, exist_ok=True)
            (seed_root / "logs").mkdir(parents=True, exist_ok=True)
            (seed_root / "configs" / "mole_session_2026_03_31_1209.json").write_text("{}", encoding="utf-8")
            (seed_root / "db" / "mole_master.sqlite").write_text("seed-db", encoding="utf-8")
            (seed_root / "logs" / "legacy_runtime.log").write_text("legacy", encoding="utf-8")

            resolve_runtime_storage_layout(code_root, env_mode="PRODUCTION", seed_if_missing=True)
            resolve_runtime_storage_layout(code_root, env_mode="PRODUCTION", seed_if_missing=True)

            manifest = json.loads((install_root / "data" / "data_root_manifest_v1.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["migration"]["performed"])
            self.assertIn("logs", manifest["migration"]["migrated_labels"])
            self.assertTrue(Path(manifest["migration"]["backup_path"]).exists())

    def test_dev_runtime_layout_keeps_internal_data_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "repo"
            code_root = repo_root / "MOLE_code"
            (code_root).mkdir(parents=True, exist_ok=True)
            layout = resolve_runtime_storage_layout_from_root(repo_root, env_mode="PRODUCTION", seed_if_missing=False)
            self.assertFalse(layout["packaged_layout"])
            self.assertEqual(Path(layout["data_root"]), (repo_root / "mole_das_data").resolve())

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

    def test_package_status_stale_against_verified_release_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            channel_root = root / "executables"
            current_root = channel_root / "MOLE_DAS_2026_04_27_v1"
            verified_root = channel_root / "MOLE_DAS_2026_04_27_v2"
            current_runtime_root = current_root / "runtime"
            verified_runtime_root = verified_root / "runtime"
            (current_runtime_root / "config").mkdir(parents=True, exist_ok=True)
            (verified_runtime_root / "config").mkdir(parents=True, exist_ok=True)

            current_acceptance_path = current_root / "PACKAGED_ACCEPTANCE_SUMMARY.json"
            current_acceptance_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_packaged_acceptance_v1",
                        "status": "PASS",
                        "package_label": "MOLE_DAS_2026_04_27_v1",
                    }
                ),
                encoding="utf-8",
            )
            verified_acceptance_json = verified_root / "PACKAGED_ACCEPTANCE_SUMMARY.json"
            verified_acceptance_json.write_text(
                json.dumps(
                    {
                        "schema": "mole_packaged_acceptance_v1",
                        "status": "PASS",
                        "package_label": "MOLE_DAS_2026_04_27_v2",
                        "generated_at": "2026-04-27T18:45:00Z",
                    }
                ),
                encoding="utf-8",
            )
            verified_acceptance_txt = verified_root / "PACKAGED_ACCEPTANCE_SUMMARY.txt"
            verified_acceptance_txt.write_text("status=PASS\n", encoding="utf-8")
            verified_script = verified_root / "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
            verified_script.write_text("Write-Host 'install'\n", encoding="utf-8")
            verified_identity = verified_runtime_root / "config" / "mole_build_identity_v1.json"
            verified_identity.write_text(
                json.dumps(
                    {
                        "schema": "mole_build_identity_v1",
                        "bundle_label": "MOLE_DAS_2026_04_27_v2",
                        "built_at": "2026-04-27T18:40:00Z",
                        "runtime_root": str(verified_runtime_root),
                    }
                ),
                encoding="utf-8",
            )
            manifest_path = channel_root / "latest_verified_release_v1.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_latest_verified_release_v1",
                        "manifest_kind": "release_channel",
                        "channel_name": "LOCAL_VERIFIED",
                        "generated_at": "2026-04-27T18:46:00Z",
                        "package_root": "MOLE_DAS_2026_04_27_v2",
                        "package_label": "MOLE_DAS_2026_04_27_v2",
                        "git_commit": "abc1234",
                        "git_branch": "codex/report-context-phase1",
                        "built_at": "2026-04-27T18:40:00Z",
                        "acceptance_status": "PASS",
                        "acceptance_summary_path": "PACKAGED_ACCEPTANCE_SUMMARY.txt",
                        "acceptance_summary_json_path": "PACKAGED_ACCEPTANCE_SUMMARY.json",
                        "installer_script_path": "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1",
                        "build_identity_path": "runtime\\config\\mole_build_identity_v1.json",
                    }
                ),
                encoding="utf-8",
            )

            original = durability.load_uninstall_registration
            durability.load_uninstall_registration = lambda: {}
            try:
                result = evaluate_runtime_package_status(
                    current_runtime_root=current_runtime_root,
                    current_build_identity={
                        "bundle_label": "MOLE_DAS_2026_04_27_v1",
                        "built_at": "2026-04-27T18:30:00Z",
                        "runtime_root": str(current_runtime_root),
                    },
                    current_acceptance_summary_path=current_acceptance_path,
                )
            finally:
                durability.load_uninstall_registration = original

            self.assertEqual(result["package_status"], "STALE")
            self.assertEqual(result["verified_release_manifest_path"], str(manifest_path.resolve()))
            self.assertEqual(result["verified_release_package_label"], "MOLE_DAS_2026_04_27_v2")
            self.assertEqual(result["verified_release_installer_script_path"], str(verified_script.resolve()))

    def test_package_status_uses_current_bundle_verified_release_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            current_root = root / "portable"
            current_runtime_root = current_root / "runtime"
            (current_runtime_root / "config").mkdir(parents=True, exist_ok=True)

            current_acceptance_path = current_root / "PACKAGED_ACCEPTANCE_SUMMARY.json"
            current_acceptance_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_packaged_acceptance_v1",
                        "status": "PASS",
                        "package_label": "MOLE_DAS_2026_04_27_v3",
                        "generated_at": "2026-04-27T19:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            current_acceptance_txt = current_root / "PACKAGED_ACCEPTANCE_SUMMARY.txt"
            current_acceptance_txt.write_text("status=PASS\n", encoding="utf-8")
            current_script = current_root / "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
            current_script.write_text("Write-Host 'install'\n", encoding="utf-8")
            current_identity = current_runtime_root / "config" / "mole_build_identity_v1.json"
            current_identity.write_text(
                json.dumps(
                    {
                        "schema": "mole_build_identity_v1",
                        "bundle_label": "MOLE_DAS_2026_04_27_v3",
                        "built_at": "2026-04-27T18:55:00Z",
                        "runtime_root": str(current_runtime_root),
                    }
                ),
                encoding="utf-8",
            )
            manifest_path = current_root / "latest_verified_release_v1.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_latest_verified_release_v1",
                        "manifest_kind": "package_root",
                        "channel_name": "LOCAL_VERIFIED",
                        "generated_at": "2026-04-27T19:01:00Z",
                        "package_root": ".",
                        "package_label": "MOLE_DAS_2026_04_27_v3",
                        "git_commit": "def5678",
                        "git_branch": "codex/report-context-phase1",
                        "built_at": "2026-04-27T18:55:00Z",
                        "acceptance_status": "PASS",
                        "acceptance_summary_path": "PACKAGED_ACCEPTANCE_SUMMARY.txt",
                        "acceptance_summary_json_path": "PACKAGED_ACCEPTANCE_SUMMARY.json",
                        "installer_script_path": "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1",
                        "build_identity_path": "runtime\\config\\mole_build_identity_v1.json",
                    }
                ),
                encoding="utf-8",
            )

            original = durability.load_uninstall_registration
            durability.load_uninstall_registration = lambda: {}
            try:
                result = evaluate_runtime_package_status(
                    current_runtime_root=current_runtime_root,
                    current_build_identity={
                        "bundle_label": "MOLE_DAS_2026_04_27_v3",
                        "built_at": "2026-04-27T18:55:00Z",
                        "runtime_root": str(current_runtime_root),
                    },
                    current_acceptance_summary_path=current_acceptance_path,
                )
            finally:
                durability.load_uninstall_registration = original

            self.assertEqual(result["package_status"], "PORTABLE")
            self.assertEqual(result["verified_release_manifest_path"], str(manifest_path.resolve()))
            self.assertEqual(result["verified_release_manifest_kind"], "package_root")
            self.assertEqual(result["verified_release_package_label"], "MOLE_DAS_2026_04_27_v3")
            self.assertEqual(result["verified_release_installer_script_path"], str(current_script.resolve()))

    def test_verify_verified_release_reference_install_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            package_root = root / "MOLE_DAS_2026_04_27_v7"
            runtime_root = package_root / "runtime"
            code_root = runtime_root / "MOLE_code"
            config_root = runtime_root / "config"
            code_root.mkdir(parents=True, exist_ok=True)
            config_root.mkdir(parents=True, exist_ok=True)

            bundle_label = "MOLE_DAS_2026_04_27_v7"
            build_identity_path = config_root / "mole_build_identity_v1.json"
            build_identity_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_build_identity_v1",
                        "bundle_label": bundle_label,
                        "built_at": "2026-04-27T20:30:00Z",
                        "runtime_root": str(runtime_root),
                    }
                ),
                encoding="utf-8",
            )
            acceptance_json_path = package_root / "PACKAGED_ACCEPTANCE_SUMMARY.json"
            acceptance_json_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_packaged_acceptance_v1",
                        "status": "PASS",
                        "package_label": bundle_label,
                        "generated_at": "2026-04-27T20:31:00Z",
                    }
                ),
                encoding="utf-8",
            )
            acceptance_txt_path = package_root / "PACKAGED_ACCEPTANCE_SUMMARY.txt"
            acceptance_txt_path.write_text("status=PASS\n", encoding="utf-8")
            version_audit_json = package_root / "PACKAGE_VERSION_AUDIT.json"
            version_audit_json.write_text(
                json.dumps(
                    {
                        "schema": "mole_package_version_audit_v1",
                        "status": "PASS",
                        "expected_bundle_label": bundle_label,
                    }
                ),
                encoding="utf-8",
            )
            version_audit_txt = package_root / "PACKAGE_VERSION_AUDIT.txt"
            version_audit_txt.write_text(f"Bundle label: {bundle_label}\nStatus: PASS\n", encoding="utf-8")
            launcher_path = package_root / "LAUNCH_MOLE_DAS_EXE.bat"
            launcher_path.write_text("@echo off\r\n", encoding="utf-8")
            installer_script = package_root / "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
            installer_script.write_text("Write-Host 'install'\n", encoding="utf-8")
            wizard_exe = code_root / "MOLE_DAS_Wizard.exe"
            wizard_exe.write_bytes(b"wizard-binary")
            runner_exe = code_root / "MOLE_DAQ_Runner.exe"
            runner_exe.write_bytes(b"runner-binary")
            script_runner_exe = code_root / "MOLE_ScriptRunner.exe"
            script_runner_exe.write_bytes(b"script-runner-binary")
            manifest_path = package_root / "latest_verified_release_v1.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_latest_verified_release_v1",
                        "manifest_kind": "package_root",
                        "channel_name": "LOCAL_VERIFIED",
                        "generated_at": "2026-04-27T20:32:00Z",
                        "package_root": ".",
                        "package_label": bundle_label,
                        "git_commit": "6781524",
                        "git_branch": "codex/report-context-phase1",
                        "built_at": "2026-04-27T20:30:00Z",
                        "acceptance_status": "PASS",
                        "acceptance_summary_path": "PACKAGED_ACCEPTANCE_SUMMARY.txt",
                        "acceptance_summary_json_path": "PACKAGED_ACCEPTANCE_SUMMARY.json",
                        "installer_script_path": "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1",
                        "version_audit_json_path": "PACKAGE_VERSION_AUDIT.json",
                        "version_audit_txt_path": "PACKAGE_VERSION_AUDIT.txt",
                        "launcher_path": "LAUNCH_MOLE_DAS_EXE.bat",
                        "wizard_exe_path": "runtime\\MOLE_code\\MOLE_DAS_Wizard.exe",
                        "runner_exe_path": "runtime\\MOLE_code\\MOLE_DAQ_Runner.exe",
                        "script_runner_exe_path": "runtime\\MOLE_code\\MOLE_ScriptRunner.exe",
                        "build_identity_path": "runtime\\config\\mole_build_identity_v1.json",
                        "hashes": {
                            "build_identity_sha256": self._sha256(build_identity_path),
                            "acceptance_summary_txt_sha256": self._sha256(acceptance_txt_path),
                            "acceptance_summary_json_sha256": self._sha256(acceptance_json_path),
                            "installer_script_sha256": self._sha256(installer_script),
                            "launcher_batch_sha256": self._sha256(launcher_path),
                            "wizard_exe_sha256": self._sha256(wizard_exe),
                            "runner_exe_sha256": self._sha256(runner_exe),
                            "script_runner_exe_sha256": self._sha256(script_runner_exe),
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = verify_verified_release_reference(
                {"verified_release_manifest_path": str(manifest_path)},
                purpose="INSTALL",
                target="WIZARD",
            )

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["package_label"], bundle_label)

    def test_verify_verified_release_reference_relaunch_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            install_root = root / "install_root"
            runtime_root = install_root / "runtime"
            code_root = runtime_root / "MOLE_code"
            config_root = runtime_root / "config"
            code_root.mkdir(parents=True, exist_ok=True)
            config_root.mkdir(parents=True, exist_ok=True)

            bundle_label = "MOLE_DAS_2026_04_27_v8"
            build_identity_path = config_root / "mole_build_identity_v1.json"
            build_identity_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_build_identity_v1",
                        "bundle_label": bundle_label,
                        "built_at": "2026-04-27T20:40:00Z",
                        "runtime_root": str(runtime_root),
                    }
                ),
                encoding="utf-8",
            )
            acceptance_json_path = install_root / "PACKAGED_ACCEPTANCE_SUMMARY.json"
            acceptance_json_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_packaged_acceptance_v1",
                        "status": "PASS",
                        "package_label": bundle_label,
                        "generated_at": "2026-04-27T20:41:00Z",
                    }
                ),
                encoding="utf-8",
            )
            acceptance_txt_path = install_root / "PACKAGED_ACCEPTANCE_SUMMARY.txt"
            acceptance_txt_path.write_text("status=PASS\n", encoding="utf-8")
            version_audit_json = install_root / "PACKAGE_VERSION_AUDIT.json"
            version_audit_json.write_text(
                json.dumps(
                    {
                        "schema": "mole_package_version_audit_v1",
                        "status": "PASS",
                        "expected_bundle_label": bundle_label,
                    }
                ),
                encoding="utf-8",
            )
            version_audit_txt = install_root / "PACKAGE_VERSION_AUDIT.txt"
            version_audit_txt.write_text(f"Bundle label: {bundle_label}\nStatus: PASS\n", encoding="utf-8")
            launcher_path = install_root / "LAUNCH_MOLE_DAS_EXE.bat"
            launcher_path.write_text("@echo off\r\n", encoding="utf-8")
            installer_script = install_root / "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
            installer_script.write_text("Write-Host 'install'\n", encoding="utf-8")
            wizard_exe = code_root / "MOLE_DAS_Wizard.exe"
            wizard_exe.write_bytes(b"wizard-binary")
            runner_exe = code_root / "MOLE_DAQ_Runner.exe"
            runner_exe.write_bytes(b"runner-binary")
            script_runner_exe = code_root / "MOLE_ScriptRunner.exe"
            script_runner_exe.write_bytes(b"script-runner-binary")
            manifest_path = install_root / "latest_verified_release_v1.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_latest_verified_release_v1",
                        "manifest_kind": "package_root",
                        "channel_name": "LOCAL_VERIFIED",
                        "generated_at": "2026-04-27T20:42:00Z",
                        "package_root": ".",
                        "package_label": bundle_label,
                        "git_commit": "6781524",
                        "git_branch": "codex/report-context-phase1",
                        "built_at": "2026-04-27T20:40:00Z",
                        "acceptance_status": "PASS",
                        "acceptance_summary_path": "PACKAGED_ACCEPTANCE_SUMMARY.txt",
                        "acceptance_summary_json_path": "PACKAGED_ACCEPTANCE_SUMMARY.json",
                        "installer_script_path": "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1",
                        "version_audit_json_path": "PACKAGE_VERSION_AUDIT.json",
                        "version_audit_txt_path": "PACKAGE_VERSION_AUDIT.txt",
                        "launcher_path": "LAUNCH_MOLE_DAS_EXE.bat",
                        "wizard_exe_path": "runtime\\MOLE_code\\MOLE_DAS_Wizard.exe",
                        "runner_exe_path": "runtime\\MOLE_code\\MOLE_DAQ_Runner.exe",
                        "script_runner_exe_path": "runtime\\MOLE_code\\MOLE_ScriptRunner.exe",
                        "build_identity_path": "runtime\\config\\mole_build_identity_v1.json",
                        "hashes": {
                            "build_identity_sha256": self._sha256(build_identity_path),
                            "acceptance_summary_txt_sha256": self._sha256(acceptance_txt_path),
                            "acceptance_summary_json_sha256": self._sha256(acceptance_json_path),
                            "installer_script_sha256": self._sha256(installer_script),
                            "launcher_batch_sha256": self._sha256(launcher_path),
                            "wizard_exe_sha256": self._sha256(wizard_exe),
                            "runner_exe_sha256": self._sha256(runner_exe),
                            "script_runner_exe_sha256": self._sha256(script_runner_exe),
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = verify_verified_release_reference(
                {
                    "install_root_path": str(install_root),
                    "installed_runtime_path": str(runtime_root),
                    "installed_wizard_executable_path": str(wizard_exe),
                    "build_identity_manifest_path": str(build_identity_path),
                    "verified_release_manifest_path": str(manifest_path),
                },
                purpose="RELAUNCH",
                target="WIZARD",
            )

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["package_label"], bundle_label)

    def test_verify_verified_release_reference_fails_on_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            package_root = root / "MOLE_DAS_2026_04_27_v9"
            runtime_root = package_root / "runtime"
            code_root = runtime_root / "MOLE_code"
            config_root = runtime_root / "config"
            code_root.mkdir(parents=True, exist_ok=True)
            config_root.mkdir(parents=True, exist_ok=True)

            bundle_label = "MOLE_DAS_2026_04_27_v9"
            build_identity_path = config_root / "mole_build_identity_v1.json"
            build_identity_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_build_identity_v1",
                        "bundle_label": bundle_label,
                        "built_at": "2026-04-27T20:50:00Z",
                        "runtime_root": str(runtime_root),
                    }
                ),
                encoding="utf-8",
            )
            acceptance_json_path = package_root / "PACKAGED_ACCEPTANCE_SUMMARY.json"
            acceptance_json_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_packaged_acceptance_v1",
                        "status": "PASS",
                        "package_label": bundle_label,
                    }
                ),
                encoding="utf-8",
            )
            acceptance_txt_path = package_root / "PACKAGED_ACCEPTANCE_SUMMARY.txt"
            acceptance_txt_path.write_text("status=PASS\n", encoding="utf-8")
            version_audit_json = package_root / "PACKAGE_VERSION_AUDIT.json"
            version_audit_json.write_text(
                json.dumps(
                    {
                        "schema": "mole_package_version_audit_v1",
                        "status": "PASS",
                        "expected_bundle_label": bundle_label,
                    }
                ),
                encoding="utf-8",
            )
            launcher_path = package_root / "LAUNCH_MOLE_DAS_EXE.bat"
            launcher_path.write_text("@echo off\r\n", encoding="utf-8")
            installer_script = package_root / "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
            installer_script.write_text("Write-Host 'install'\n", encoding="utf-8")
            wizard_exe = code_root / "MOLE_DAS_Wizard.exe"
            wizard_exe.write_bytes(b"wizard-binary")
            runner_exe = code_root / "MOLE_DAQ_Runner.exe"
            runner_exe.write_bytes(b"runner-binary")
            script_runner_exe = code_root / "MOLE_ScriptRunner.exe"
            script_runner_exe.write_bytes(b"script-runner-binary")
            manifest_path = package_root / "latest_verified_release_v1.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": "mole_latest_verified_release_v1",
                        "manifest_kind": "package_root",
                        "channel_name": "LOCAL_VERIFIED",
                        "generated_at": "2026-04-27T20:51:00Z",
                        "package_root": ".",
                        "package_label": bundle_label,
                        "git_commit": "6781524",
                        "git_branch": "codex/report-context-phase1",
                        "built_at": "2026-04-27T20:50:00Z",
                        "acceptance_status": "PASS",
                        "acceptance_summary_path": "PACKAGED_ACCEPTANCE_SUMMARY.txt",
                        "acceptance_summary_json_path": "PACKAGED_ACCEPTANCE_SUMMARY.json",
                        "installer_script_path": "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1",
                        "version_audit_json_path": "PACKAGE_VERSION_AUDIT.json",
                        "launcher_path": "LAUNCH_MOLE_DAS_EXE.bat",
                        "wizard_exe_path": "runtime\\MOLE_code\\MOLE_DAS_Wizard.exe",
                        "runner_exe_path": "runtime\\MOLE_code\\MOLE_DAQ_Runner.exe",
                        "script_runner_exe_path": "runtime\\MOLE_code\\MOLE_ScriptRunner.exe",
                        "build_identity_path": "runtime\\config\\mole_build_identity_v1.json",
                        "hashes": {
                            "build_identity_sha256": "BADHASH",
                            "acceptance_summary_txt_sha256": self._sha256(acceptance_txt_path),
                            "acceptance_summary_json_sha256": self._sha256(acceptance_json_path),
                            "installer_script_sha256": self._sha256(installer_script),
                            "launcher_batch_sha256": self._sha256(launcher_path),
                            "wizard_exe_sha256": self._sha256(wizard_exe),
                            "runner_exe_sha256": self._sha256(runner_exe),
                            "script_runner_exe_sha256": self._sha256(script_runner_exe),
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = verify_verified_release_reference(
                {"verified_release_manifest_path": str(manifest_path)},
                purpose="INSTALL",
                target="WIZARD",
            )

            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any("SHA256 mismatch" in detail for detail in result["details"]))

    def test_runtime_action_policy_blocks_unverified_compliance(self) -> None:
        result = evaluate_runtime_action_policy(
            package_status_record={
                "package_status": "UNVERIFIED",
                "package_status_summary": "Package verification or runtime identity is incomplete.",
                "package_status_detail": "Packaged acceptance summary is missing.",
            },
            action_scope="COMPLIANCE",
            action_label="Formal report build",
        )
        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["package_status"], "UNVERIFIED")

    def test_runtime_action_policy_requires_ack_for_stale(self) -> None:
        result = evaluate_runtime_action_policy(
            package_status_record={
                "package_status": "STALE",
                "package_status_summary": "Running package is older or different than the locally accepted install.",
                "package_status_detail": "Running package differs from the locally installed accepted package.",
            },
            action_scope="COMPLIANCE",
            action_label="DAQ Runner production launch",
        )
        self.assertEqual(result["decision"], "ACK")
        self.assertEqual(result["package_status"], "STALE")

    def test_runtime_action_policy_warns_for_portable_training(self) -> None:
        result = evaluate_runtime_action_policy(
            package_status_record={
                "package_status": "PORTABLE",
                "package_status_summary": "Running from a portable folder instead of the installed root.",
                "package_status_detail": "Running from a portable folder instead of the installed root.",
            },
            action_scope="TRAINING",
            action_label="DAQ Runner training launch",
        )
        self.assertEqual(result["decision"], "WARN")
        self.assertEqual(result["package_status"], "PORTABLE")

    def test_runtime_action_policy_allows_current_compliance(self) -> None:
        result = evaluate_runtime_action_policy(
            package_status_record={
                "package_status": "CURRENT",
                "package_status_summary": "Installed and verified package matches the local accepted install.",
                "package_status_detail": "Running from the installed root.",
                "packaged_acceptance_status": "PASS",
            },
            action_scope="COMPLIANCE",
            action_label="Session review signoff",
        )
        self.assertEqual(result["decision"], "ALLOW")
        self.assertEqual(result["package_status"], "CURRENT")

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
