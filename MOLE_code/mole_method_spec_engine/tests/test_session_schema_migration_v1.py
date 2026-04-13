from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Callable, Dict


TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
CODE_DIR = TESTS_DIR.parents[1]

WIZARD_PATH = CODE_DIR / "mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py"
RUNNER_PATH = CODE_DIR / "mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py"


def _load_module(module_path: Path, module_name: str):
    if str(CODE_DIR) not in sys.path:
        sys.path.insert(0, str(CODE_DIR))
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class SessionSchemaMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wizard_mod = _load_module(WIZARD_PATH, "mole_wizard_schema_test")
        cls.runner_mod = _load_module(RUNNER_PATH, "mole_runner_schema_test")

    def _fixture(self, name: str) -> Dict[str, Any]:
        return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))

    def _assert_diag_fixture(self, ensure_fn: Callable[..., Dict[str, Any]]) -> None:
        sess = ensure_fn(self._fixture("legacy_diag_session.json"), actor="unit_test")
        meta = sess["meta"]

        self.assertEqual(sess["schema_version"], "mole_session_config_v2")
        self.assertEqual(meta["session_schema_version"], "mole_session_config_v2")
        self.assertEqual(meta["session_schema_revision"], 2)
        self.assertEqual(meta["session_schema_status"], "MIGRATED")
        self.assertEqual(meta["session_schema_last_actor"], "unit_test")
        self.assertIn("normalized to mole_session_config_v2 rev 2", meta["session_schema_summary"])
        self.assertTrue(meta["schema_migrations"])

        self.assertFalse(sess["session_mode"]["may_support_compliance"])
        self.assertEqual(sess["site_conditions"]["z_model"], "IDEAL")
        self.assertNotIn("compressibility_model", sess["site_conditions"])
        self.assertEqual(sess["fuel"]["dg"]["share_basis"], "SELECTED_HEAT_INPUT_PCT")
        self.assertNotIn("STATE_PERMIT_GENERAL", sess["regulatory"]["selected_rule_ids"])
        self.assertNotIn("STATE_PERMIT_GENERAL", sess["regulatory"]["selected_rule_meta"])
        self.assertEqual(sess["validation_plan"]["session_type"], "STANDARD_TEST")
        self.assertEqual(sess["validation_plan"]["validation_mode"], "NONE")
        self.assertFalse(sess["session_review"]["enabled"])
        self.assertEqual(sess["session_review"]["scope"], "PROJECT_REVIEW")
        self.assertEqual(sess["session_review"]["signoff"]["decision"], "UNSIGNED")

        note_blob = " | ".join(meta["session_schema_last_notes"])
        self.assertIn("may_support_compliance=true", note_blob)
        self.assertIn("Unsupported compressibility mode", note_blob)
        self.assertIn("Dual-fuel liquid share semantics", note_blob)
        self.assertIn("STATE_PERMIT_GENERAL", note_blob)
        self.assertIn("Session review / approval block", note_blob)

    def _assert_prod_fixture(self, ensure_fn: Callable[..., Dict[str, Any]]) -> None:
        sess = ensure_fn(self._fixture("legacy_prod_session.json"), actor="unit_test")
        meta = sess["meta"]

        self.assertEqual(sess["schema_version"], "mole_session_config_v2")
        self.assertEqual(meta["session_schema_status"], "MIGRATED")
        self.assertEqual(meta["session_schema_migrated_from_version"], "mole_session_config_v1")
        self.assertNotIn("ui_mode", sess["daq_runner"])
        self.assertEqual(sess["site_conditions"]["z_model"], "IDEAL")
        self.assertNotIn("z_basis", sess["site_conditions"])
        self.assertEqual(sess["validation_plan"]["session_type"], "STANDARD_TEST")
        self.assertEqual(sess["validation_plan"]["validation_mode"], "NONE")
        self.assertFalse(sess["session_review"]["enabled"])
        self.assertEqual(sess["session_review"]["signoff"]["decision"], "UNSIGNED")

        note_blob = " | ".join(meta["session_schema_last_notes"])
        self.assertIn("Stale diagnostics UI mode was cleared", note_blob)
        self.assertIn("Legacy site_conditions.z_basis key was retired", note_blob)
        self.assertIn("Session review / approval block", note_blob)

    def _assert_ftir_validation_backfill(self, ensure_fn: Callable[..., Dict[str, Any]]) -> None:
        sess = ensure_fn({
            "session_mode": {"record_data": True, "tokenize": True, "diagnostic_only": False, "may_support_compliance": False},
            "ftir_validation": {
                "enabled": True,
                "validation_mode": "METHOD_301_FORMAL",
                "comparator_method": "FTIR_VALIDATED_METHOD",
                "timestamp_master_clock": "SESSION_MASTER_CLOCK",
                "ftir_vendor_profile": "THERMOFISHER_MAX_CSV",
                "reviewer": "Peer Scientist",
                "signoff": {"by": "Lead Scientist", "role": "Principal Scientist"},
                "execution": {
                    "planned_run_count_override": 6,
                    "planned_run_minutes_override": 20.0,
                    "purge_minutes_required": 5.0,
                    "require_purge_event": True,
                    "require_bias_event": True,
                },
            },
        }, actor="unit_test")
        plan = sess["validation_plan"]
        notes = " | ".join(sess["meta"]["session_schema_last_notes"])
        self.assertTrue(plan["enabled"])
        self.assertEqual(plan["session_type"], "FTIR_VALIDATION")
        self.assertEqual(plan["validation_mode"], "METHOD_301_FORMAL")
        self.assertEqual(plan["comparator_vendor_profile"], "THERMOFISHER_MAX_CSV")
        self.assertEqual(plan["planned_set_count"], 6)
        self.assertEqual(plan["planned_run_minutes"], 20.0)
        self.assertEqual(plan["planned_purge_minutes"], 5.0)
        self.assertTrue(plan["require_purge_each_set"])
        self.assertTrue(plan["require_bias_each_set"])
        self.assertEqual(plan["peer_reviewer"], "Peer Scientist")
        self.assertEqual(plan["final_approver"], "Lead Scientist")
        self.assertEqual(plan["final_approver_role"], "Principal Scientist")
        review = sess["session_review"]
        self.assertTrue(review["enabled"])
        self.assertEqual(review["scope"], "VALIDATION_REPORT")
        self.assertEqual(review["reviewer_name"], "Peer Scientist")
        self.assertEqual(review["default_approver"], "Lead Scientist")
        self.assertEqual(review["default_approver_role"], "Principal Scientist")
        self.assertEqual(review["signoff"]["decision"], "UNSIGNED")
        self.assertIn("Validation test plan", notes)
        self.assertIn("backfilled from FTIR validation settings", notes)

    def _assert_standard_compliance_review(self, ensure_fn: Callable[..., Dict[str, Any]]) -> None:
        sess = ensure_fn({
            "session_mode": {
                "record_data": True,
                "tokenize": True,
                "diagnostic_only": False,
                "may_support_compliance": True,
            },
            "session_review": {
                "enabled": True,
                "scope": "COMPLIANCE_REPORT",
                "reviewer_name": "Peer Scientist",
                "reviewer_role": "Peer Reviewer",
                "review_notes": "Package reviewed for non-FTIR compliance deliverable.",
                "review_locked": True,
                "review_lock_by": "Peer Scientist",
                "review_lock_iso": "2026-04-13T10:15:00-05:00",
                "default_approver": "Lead Scientist",
                "default_approver_role": "Principal Scientist",
                "signoff": {
                    "decision": "APPROVED",
                    "basis": "COMPLIANCE_REPORT_READY",
                    "by": "Lead Scientist",
                    "role": "Principal Scientist",
                    "iso": "2026-04-13T10:20:00-05:00",
                    "note": "Approved for compliance report generation.",
                },
            },
        }, actor="unit_test")
        review = sess["session_review"]
        self.assertTrue(review["enabled"])
        self.assertEqual(review["scope"], "COMPLIANCE_REPORT")
        self.assertEqual(review["reviewer_name"], "Peer Scientist")
        self.assertTrue(review["review_locked"])
        self.assertEqual(review["review_lock_by"], "Peer Scientist")
        self.assertEqual(review["default_approver"], "Lead Scientist")
        self.assertEqual(review["signoff"]["decision"], "APPROVED")
        self.assertEqual(review["signoff"]["basis"], "COMPLIANCE_REPORT_READY")
        self.assertEqual(review["signoff"]["by"], "Lead Scientist")
        self.assertEqual(review["signoff"]["role"], "Principal Scientist")

    def test_wizard_migrates_legacy_diagnostic_session(self) -> None:
        self._assert_diag_fixture(self.wizard_mod.ensure_session_schema)

    def test_runner_migrates_legacy_diagnostic_session(self) -> None:
        self._assert_diag_fixture(self.runner_mod.ensure_session_schema)

    def test_wizard_migrates_legacy_production_session(self) -> None:
        self._assert_prod_fixture(self.wizard_mod.ensure_session_schema)

    def test_runner_migrates_legacy_production_session(self) -> None:
        self._assert_prod_fixture(self.runner_mod.ensure_session_schema)

    def test_wizard_backfills_validation_plan_from_ftir_validation(self) -> None:
        self._assert_ftir_validation_backfill(self.wizard_mod.ensure_session_schema)

    def test_runner_backfills_validation_plan_from_ftir_validation(self) -> None:
        self._assert_ftir_validation_backfill(self.runner_mod.ensure_session_schema)

    def test_wizard_preserves_standard_compliance_review(self) -> None:
        self._assert_standard_compliance_review(self.wizard_mod.ensure_session_schema)

    def test_runner_preserves_standard_compliance_review(self) -> None:
        self._assert_standard_compliance_review(self.runner_mod.ensure_session_schema)


if __name__ == "__main__":
    unittest.main()
