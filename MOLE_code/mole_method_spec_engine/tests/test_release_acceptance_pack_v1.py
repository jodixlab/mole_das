from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parent


class ReleaseAcceptancePackTests(unittest.TestCase):
    def test_packaged_acceptance_evidence_prefills_supported_operator_gates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output_dir = root / "artifacts"
            output_dir.mkdir()
            summary_json = root / "clean_release_summary.json"
            summary_json.write_text(
                json.dumps(
                    {
                        "schema": "mole_clean_release_workflow_v1",
                        "status": "PASS",
                        "artifact_dir": str(output_dir),
                        "steps": [
                            {"name": "install_runtime", "status": "PASS"},
                            {"name": "unit_tests", "status": "PASS"},
                            {"name": "smoketest", "status": "PASS"},
                            {"name": "release_gate", "status": "PASS"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (output_dir / "packaged_acceptance_summary.json").write_text(
                json.dumps(
                    {
                        "schema": "mole_packaged_acceptance_v1",
                        "status": "PASS",
                        "package_label": "MOLE_DAS_REL_TEST",
                        "git_commit": "abc1234",
                        "wizard_startup_path": str(output_dir / "wizard_startup__latest.json"),
                        "runner_startup_path": str(output_dir / "runner_startup__latest.json"),
                        "session_dir": str(output_dir / "session"),
                        "runner_config_path": str(output_dir / "session" / "runner_config.json"),
                        "report_pack_summary_path": str(output_dir / "report_pack_summary.json"),
                        "final_report_path": str(output_dir / "final_test_report_v1.md"),
                        "final_report_index_path": str(output_dir / "final_report_index.json"),
                        "diagnostics_config_path": str(output_dir / "session" / "runner_config_diag_training.json"),
                        "diagnostics_snapshot_path": str(output_dir / "diagnostics_snapshot.txt"),
                        "diagnostics_manifest_path": str(output_dir / "diagnostics_snapshot_manifest.json"),
                        "diagnostics_calc_audit_json_path": str(output_dir / "diagnostics_calc_audit.json"),
                        "diagnostics_calc_audit_csv_path": str(output_dir / "diagnostics_calc_audit.csv"),
                        "steps": [
                            {"name": "launch_wizard", "status": "PASS"},
                            {"name": "seed_session", "status": "PASS"},
                            {"name": "launch_runner", "status": "PASS"},
                            {"name": "export_report_pack", "status": "PASS"},
                            {"name": "diagnostics_only_flow", "status": "PASS"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (output_dir / "report_pack_summary.json").write_text(
                json.dumps(
                    {
                        "final_report": {
                            "render_status": {
                                "docx": {"status": "generated"},
                                "pdf": {"status": "generated"},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (output_dir / "wizard_startup__latest.json").write_text("{}", encoding="utf-8")
            (output_dir / "runner_startup__latest.json").write_text("{}", encoding="utf-8")
            (output_dir / "diagnostics_snapshot.txt").write_text(
                "MOLE DAS DIAGNOSTICS SNAPSHOT\nCompliance support: DISABLED\n",
                encoding="utf-8",
            )
            (output_dir / "diagnostics_calc_audit.json").write_text("{}", encoding="utf-8")
            (output_dir / "diagnostics_calc_audit.csv").write_text("section,label,value\n", encoding="utf-8")
            (output_dir / "diagnostics_snapshot_manifest.json").write_text(
                json.dumps(
                    {
                        "schema": "mole_diagnostics_headless_manifest_v1",
                        "status": "PASS",
                        "diagnostic_only": True,
                        "may_support_compliance": False,
                        "report_pack_enabled": False,
                        "formal_report_enabled": False,
                        "compliance_claimed": False,
                        "samples_captured": 4,
                    }
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "build_release_acceptance_pack.py"),
                    "--repo-root",
                    str(REPO_ROOT),
                    "--output-dir",
                    str(output_dir),
                    "--summary-json",
                    str(summary_json),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            checklist = json.loads((output_dir / "operator_go_no_go_checklist.json").read_text(encoding="utf-8"))
            decisions = {item["id"]: item.get("decision") for item in checklist["items"]}
            sources = {item["id"]: item.get("decision_source") for item in checklist["items"]}

            self.assertEqual(decisions["wizard_launch"], "PASS")
            self.assertEqual(decisions["runner_launch_test"], "PASS")
            self.assertEqual(decisions["standard_recorded_test_flow"], "PASS")
            self.assertEqual(decisions["final_report_export"], "PASS")
            self.assertEqual(decisions["diagnostics_only_flow"], "PASS")
            self.assertIsNone(decisions["package_review_signoff"])
            self.assertEqual(sources["wizard_launch"], "packaged_acceptance")
            self.assertEqual(sources["diagnostics_only_flow"], "packaged_acceptance")
            evidence_paths = {
                item["id"]: [Path(path).name for path in item.get("evidence_paths") or []]
                for item in checklist["items"]
            }
            self.assertIn("wizard_startup__latest.json", evidence_paths["wizard_launch"])
            self.assertNotIn("diagnostics_snapshot_manifest.json", evidence_paths["wizard_launch"])
            self.assertIn("diagnostics_snapshot_manifest.json", evidence_paths["diagnostics_only_flow"])
            self.assertTrue((output_dir / "operator_validation_evidence.json").exists())

    def test_operator_signoff_script_closes_final_release_gate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            artifact_dir = Path(td)
            (artifact_dir / "clean_release_summary.json").write_text(
                json.dumps({"status": "PASS"}),
                encoding="utf-8",
            )
            (artifact_dir / "release_bundle_summary.json").write_text(
                json.dumps({"overall_status": "PASS"}),
                encoding="utf-8",
            )
            (artifact_dir / "RELEASE_CERT_TEST.json").write_text(
                json.dumps({"status": "PASS"}),
                encoding="utf-8",
            )
            (artifact_dir / "RELEASE_HYGIENE_TEST.json").write_text(
                json.dumps({"status": "PASS"}),
                encoding="utf-8",
            )
            (artifact_dir / "packaged_acceptance_summary.json").write_text(
                json.dumps(
                    {
                        "package_label": "MOLE_DAS_REL_TEST",
                        "git_commit": "abc1234",
                    }
                ),
                encoding="utf-8",
            )
            (artifact_dir / "operator_go_no_go_checklist.json").write_text(
                json.dumps(
                    {
                        "schema": "mole_release_go_no_go_checklist_v1",
                        "items": [
                            {
                                "id": "clean_release_gate",
                                "gate": "BLOCKING",
                                "decision": "PASS",
                                "decision_source": "clean_workflow",
                            },
                            {
                                "id": "package_review_signoff",
                                "gate": "BLOCKING",
                                "decision": None,
                                "decision_source": "operator_pending",
                            },
                        ],
                        "final_decision": {
                            "decision": "",
                            "approved_by": "",
                            "approval_basis": "",
                            "date": "",
                            "notes": "",
                        },
                    }
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "apply_release_operator_signoff.py"),
                    "--artifact-dir",
                    str(artifact_dir),
                    "--approved-by",
                    "QA Reviewer",
                    "--approval-basis",
                    "Reviewed packaged acceptance evidence and release hashes.",
                    "--date",
                    "2026-05-05",
                    "--notes",
                    "Unit test signoff.",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            decision = json.loads((artifact_dir / "release_go_no_go_decision.json").read_text(encoding="utf-8"))
            checklist = json.loads((artifact_dir / "operator_go_no_go_checklist.json").read_text(encoding="utf-8"))
            package_item = next(item for item in checklist["items"] if item["id"] == "package_review_signoff")

            self.assertEqual(decision["status"], "PASS")
            self.assertEqual(decision["overall_decision"], "GO")
            self.assertEqual(package_item["decision"], "GO")
            self.assertEqual(package_item["decision_source"], "operator_signoff")
            self.assertTrue((artifact_dir / "operator_release_signoff.json").exists())


if __name__ == "__main__":
    unittest.main()
