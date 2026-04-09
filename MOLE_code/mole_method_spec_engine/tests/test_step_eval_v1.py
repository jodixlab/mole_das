from __future__ import annotations

import json
import unittest
from pathlib import Path

from mole_method_spec_engine import (
    SPEC_ENGINE_FORMULA_VERSION,
    build_evidence_record,
    derive_analyzer_validity,
    evaluate_channel_step,
    get_method_profile,
)


FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class StepEvalTests(unittest.TestCase):
    def test_zero_o2_in_band_fixture(self) -> None:
        fx = _fixture("zero_o2_in_band.json")
        out = evaluate_channel_step(fx["channel"], fx["step_state"], fx["value_series"], fx["targets"], fx["tolerances"])
        self.assertEqual(out["basis"], fx["expected"]["basis"])
        self.assertEqual(out["status"], fx["expected"]["status"])
        self.assertEqual(out["pass"], fx["expected"]["pass"])

    def test_span_nox_pass_fixture(self) -> None:
        fx = _fixture("span_nox_pass.json")
        out = evaluate_channel_step(fx["channel"], fx["step_state"], fx["value_series"], fx["targets"], fx["tolerances"])
        self.assertEqual(out["basis"], fx["expected"]["basis"])
        self.assertEqual(out["status"], fx["expected"]["status"])
        self.assertEqual(out["pass"], fx["expected"]["pass"])
        self.assertAlmostEqual(out["recovery_pct"], 99.88, places=1)

    def test_post_zero_fail_fixture(self) -> None:
        fx = _fixture("post_zero_fail.json")
        out = evaluate_channel_step(fx["channel"], fx["step_state"], fx["value_series"], fx["targets"], fx["tolerances"])
        self.assertEqual(out["basis"], fx["expected"]["basis"])
        self.assertEqual(out["status"], fx["expected"]["status"])
        self.assertEqual(out["pass"], fx["expected"]["pass"])

    def test_evidence_record_is_versioned(self) -> None:
        fx = _fixture("zero_o2_in_band.json")
        out = evaluate_channel_step(fx["channel"], fx["step_state"], fx["value_series"], fx["targets"], fx["tolerances"])
        rec = build_evidence_record(
            step=fx["step_state"]["step"],
            channel=fx["channel"],
            inputs={"targets": fx["targets"], "tolerances": fx["tolerances"]},
            outputs={"series_len": len(fx["value_series"])},
            result=out,
        )
        self.assertEqual(rec["formula_version"], SPEC_ENGINE_FORMULA_VERSION)
        self.assertEqual(rec["channel"], "O2")
        self.assertEqual(rec["result"]["status"], "OK")

    def test_analyzer_validity_rollup(self) -> None:
        out_zero = evaluate_channel_step("NOX", {"step": "ZERO"}, [0.2, 0.1, 0.2], {"target": 0.0}, {"tol_abs": 2.0})
        out_span = evaluate_channel_step("NOX", {"step": "SPAN"}, [99.8, 100.2, 100.1], {"target": 100.0}, {"tol_pct": 2.0})
        validity = derive_analyzer_validity(out_zero, out_span)
        self.assertEqual(validity["state"], "VALID")
        self.assertTrue(validity["gates"]["allow_regulatory"])

    def test_analyzer_validity_invalidates_on_drift_when_requested(self) -> None:
        out_zero = {"pass": True, "status": "OK"}
        out_span = {"pass": True, "status": "OK"}
        out_drift = {"pass": False, "status": "FAIL"}
        validity = derive_analyzer_validity(out_zero, out_span, out_drift, latched_invalid=False, invalidate_on_drift=True)
        self.assertEqual(validity["state"], "INVALID")
        self.assertFalse(validity["gates"]["allow_regulatory"])

    def test_method_profile_lookup(self) -> None:
        profile = get_method_profile("engine", "natural gas", "rice", "subpart jjjj")
        self.assertEqual(profile["profile_id"], "ENGINE_SI_RICE_JJJJ_NG")
        self.assertIn("G_BHP_HR", profile["supported_bases"])


if __name__ == "__main__":
    unittest.main()
