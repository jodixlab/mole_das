from __future__ import annotations

import unittest

from mole_method_spec_engine import build_training_scenario


class TrainingScenarioTests(unittest.TestCase):
    def test_training_scenario_uses_authoritative_targets_and_profile(self) -> None:
        session = {
            "project": {
                "job_id": "JOB-1",
                "source_type": "engine",
                "duty_type": "rice",
            },
            "fuel": {
                "fuel_type": "natural gas",
            },
            "regulatory": {
                "regulation": "subpart jjjj",
            },
            "pollutants": {
                "selected": ["CO", "NOX"],
                "resolved": {
                    "resolved_by_analyte": {
                        "NOX": {"mid_fraction": 0.4},
                    }
                },
            },
            "daq_runner": {
                "worksteps": {
                    "qaqc": {
                        "span": {
                            "CO": {"target": 500.0},
                        }
                    },
                    "postcal": {
                        "run_no": 2,
                    },
                }
            },
        }
        prescriptions = {
            "CO": {"span_target": 500.0, "units": "ppm"},
            "NOX": {"span_target": 100.0, "units": "ppm"},
            "O2": {"span_target": 20.9, "units": "%"},
        }

        scenario = build_training_scenario(session, codes=["VOC"], prescriptions=prescriptions, ranges_db={})

        self.assertEqual(scenario["name"], "sim_training")
        self.assertEqual(scenario["method_profile"]["profile_id"], "ENGINE_SI_RICE_JJJJ_NG")
        self.assertIn("CO", scenario["codes"])
        self.assertIn("VOC", scenario["codes"])
        self.assertIn("O2", scenario["codes"])
        self.assertIn("CO2", scenario["codes"])
        self.assertEqual(scenario["targets"]["ZERO"]["CO"], 0.0)
        self.assertEqual(scenario["targets"]["SPAN"]["CO"], 500.0)
        self.assertEqual(scenario["targets"]["MID"]["NOX"], 40.0)
        self.assertEqual(scenario["targets"]["SPAN"]["O2"], 20.9)
        self.assertEqual(scenario["targets"]["ZERO"]["O2"], 0.0)

    def test_training_scenario_is_deterministic(self) -> None:
        session = {
            "project": {"job_id": "JOB-2"},
            "pollutants": {"selected": ["CO"]},
        }
        prescriptions = {"CO": {"span_target": 100.0, "units": "ppm"}}

        a = build_training_scenario(session, codes=[], prescriptions=prescriptions, ranges_db={})
        b = build_training_scenario(session, codes=[], prescriptions=prescriptions, ranges_db={})

        self.assertEqual(a["targets"]["SAMPLE"]["CO"], b["targets"]["SAMPLE"]["CO"])
        self.assertEqual(a["targets"]["POST_ZERO"]["CO"], b["targets"]["POST_ZERO"]["CO"])
        self.assertEqual(a["targets"]["POST_SPAN"]["CO"], b["targets"]["POST_SPAN"]["CO"])

    def test_training_scenario_uses_engine_exhaust_envelopes_for_wizard_style_sessions(self) -> None:
        gas_session = {
            "project": {"job_id": "JOB-GAS"},
            "source": {"source_category": "Engine"},
            "fuel": {"fuel_button_code": "NG"},
            "pollutants": {"selected": ["CO", "NOX"]},
        }
        diesel_session = {
            "project": {"job_id": "JOB-DSL"},
            "source": {"source_category": "Engine"},
            "fuel": {"fuel_button_code": "DSL"},
            "regulatory": {"context": {"engine_ignition": "CI"}},
            "pollutants": {"selected": ["CO", "NOX"]},
        }

        gas = build_training_scenario(gas_session, codes=[], prescriptions={}, ranges_db={})
        diesel = build_training_scenario(diesel_session, codes=[], prescriptions={}, ranges_db={})

        self.assertGreaterEqual(gas["targets"]["SAMPLE"]["O2"], 3.0)
        self.assertLessEqual(gas["targets"]["SAMPLE"]["O2"], 10.0)
        self.assertGreaterEqual(gas["targets"]["SAMPLE"]["CO2"], 5.0)
        self.assertLessEqual(gas["targets"]["SAMPLE"]["CO2"], 11.0)

        self.assertGreaterEqual(diesel["targets"]["SAMPLE"]["O2"], 9.0)
        self.assertLessEqual(diesel["targets"]["SAMPLE"]["O2"], 14.5)
        self.assertGreaterEqual(diesel["targets"]["SAMPLE"]["CO2"], 2.5)
        self.assertLessEqual(diesel["targets"]["SAMPLE"]["CO2"], 7.0)
        self.assertGreater(diesel["targets"]["SAMPLE"]["O2"], gas["targets"]["SAMPLE"]["O2"])
        self.assertLess(diesel["targets"]["SAMPLE"]["CO2"], gas["targets"]["SAMPLE"]["CO2"])
        self.assertGreater(diesel["targets"]["SAMPLE"]["NOX"], gas["targets"]["SAMPLE"]["NOX"])


if __name__ == "__main__":
    unittest.main()
