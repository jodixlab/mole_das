from __future__ import annotations

import json
import unittest
from pathlib import Path

from mole_method_spec_engine import evaluate_regulatory_output


FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class RegulatoryEvalTests(unittest.TestCase):
    def test_ppmvd_limit_uses_o2_correction(self) -> None:
        fx = _fixture("regulatory_nox_ppmvd_pass.json")
        out = evaluate_regulatory_output(fx["channel"], fx["observed"], fx["limits"], fx["context"])
        self.assertEqual(out["concentration"]["compare_source"], fx["expected"]["compare_source"])
        self.assertEqual(out["concentration"]["status"], fx["expected"]["status"])
        self.assertEqual(out["concentration"]["pass"], fx["expected"]["pass"])
        self.assertIsNotNone(out["views"]["corrected"])

    def test_mass_rate_gbhphr_fixture(self) -> None:
        fx = _fixture("regulatory_co_gbhphr_pass.json")
        out = evaluate_regulatory_output(fx["channel"], fx["observed"], fx["limits"], fx["context"])
        self.assertEqual(out["mass"]["display_units"], fx["expected"]["display_units"])
        self.assertEqual(out["mass"]["status"], fx["expected"]["status"])
        self.assertEqual(out["mass"]["pass"], fx["expected"]["pass"])
        self.assertIsNotNone(out["mass"]["display_value"])

    def test_mass_rate_basis_flag_when_required_input_missing(self) -> None:
        out = evaluate_regulatory_output(
            "NOX",
            {"raw": 100.0, "units": "ppm"},
            [{"pollutant": "NOX", "value": 1.0, "units": "lb/MMBtu", "basis": "LB/MMBTU"}],
            {"raw_is_wet": False, "apply_o2_correction": False, "qd_dscfh": 100000.0},
        )
        self.assertEqual(out["mass"]["status"], "(basis)")
        self.assertFalse(out["mass"]["basis_ok"])

    def test_mass_rate_lb_per_mmbtu_reference_case(self) -> None:
        out = evaluate_regulatory_output(
            "NOX",
            {"raw": 100.0, "units": "ppm"},
            [{"pollutant": "NOX", "value": 0.2, "units": "lb/MMBtu", "basis": "LB/MMBTU"}],
            {
                "raw_is_wet": False,
                "apply_o2_correction": False,
                "qd_dscfh": 100000.0,
                "heat_mmbtu_hr": 10.0,
            },
        )
        self.assertEqual(out["mass"]["display_units"], "lb/MMBtu")
        self.assertAlmostEqual(out["mass"]["display_value"], 0.12123236411740212, places=12)
        self.assertEqual(out["mass"]["status"], "PASS")

    def test_mass_rate_tons_per_year_uses_project_hours(self) -> None:
        out = evaluate_regulatory_output(
            "NOX",
            {"raw": 100.0, "units": "ppm"},
            [{"pollutant": "NOX", "value": 3.0, "units": "tpy", "basis": "TPY"}],
            {
                "raw_is_wet": False,
                "apply_o2_correction": False,
                "qd_dscfh": 100000.0,
                "hours_per_year": 4000.0,
            },
        )
        self.assertEqual(out["mass"]["display_units"], "tons/yr")
        self.assertAlmostEqual(out["mass"]["display_value"], 2.4246472823480425, places=12)
        self.assertEqual(out["mass"]["hours_per_year"], 4000.0)
        self.assertEqual(out["mass"]["status"], "PASS")

    def test_wet_to_dry_mass_conversion_uses_override_h2o(self) -> None:
        out = evaluate_regulatory_output(
            "NOX",
            {"raw": 90.0, "units": "ppm"},
            [{"pollutant": "NOX", "value": 2.0, "units": "lb/hr", "basis": "LB_HR"}],
            {
                "raw_is_wet": True,
                "apply_o2_correction": False,
                "h2o_wet_frac": 0.1,
                "qd_dscfh": 100000.0,
            },
        )
        self.assertAlmostEqual(out["views"]["dry"], 100.0, places=9)
        self.assertAlmostEqual(out["views"]["dry_factor"], 1.1111111111111112, places=12)
        self.assertEqual(out["mass"]["ppm_input_source"], "DRY")
        self.assertAlmostEqual(out["mass"]["display_value"], 1.2123236411740212, places=12)

    def test_concentration_uses_raw_when_o2_correction_is_disabled(self) -> None:
        out = evaluate_regulatory_output(
            "NOX",
            {"raw": 100.0, "units": "ppm"},
            [{"pollutant": "NOX", "value": 40.0, "units": "ppmvd @15% O2", "o2_ref_pct": 15.0}],
            {
                "raw_is_wet": False,
                "apply_o2_correction": False,
                "o2_meas_pct": 5.0,
                "qd_dscfh": 100000.0,
            },
        )
        self.assertEqual(out["concentration"]["compare_source"], "DRY_PREF")
        self.assertEqual(out["concentration"]["status"], "FAIL")
        self.assertIsNone(out["views"]["corrected"])


if __name__ == "__main__":
    unittest.main()
