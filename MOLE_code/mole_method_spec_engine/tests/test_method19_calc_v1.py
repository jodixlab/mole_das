from __future__ import annotations

import unittest

from mole_method_spec_engine import (
    dual_fuel_basis_shares,
    method19_fuel_flow_from_heat_input,
    method19_heat_input_from_fuel_flow,
    method19_heat_input_from_qd,
    method19_pick_fd,
    method19_pick_heat_value,
    method19_qd_from_heat_input,
)


class Method19CalcTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ng_comb = {
            "family": "GAS",
            "basis_sel": "LHV",
            "F_selected": 9368.114454252687,
            "Fd_sel_dscf_per_MMBtu": 9368.114454252687,
            "Fd_LHV_dscf_per_MMBtu": 9368.114454252687,
            "Fd_HHV_dscf_per_MMBtu": 8455.987714132507,
            "LHV_Btu_scf": 959.51,
            "HHV_Btu_scf": 1063.01,
        }

    def test_lhv_crosswalk_matches_reference_case(self) -> None:
        heat_value, kind, basis = method19_pick_heat_value(self.ng_comb, "scf")
        fd = method19_pick_fd(self.ng_comb)
        heat_input = method19_heat_input_from_fuel_flow(9200.0, heat_value)
        qd = method19_qd_from_heat_input(heat_input, fd, o2_dry_pct=5.0)

        self.assertEqual(kind, "scf")
        self.assertEqual(basis, "LHV")
        self.assertAlmostEqual(heat_input, 8.827492, places=6)
        self.assertAlmostEqual(qd, 108702.2872867924, places=6)

    def test_qd_inverse_recovers_heat_input(self) -> None:
        fd = method19_pick_fd(self.ng_comb)
        heat_input = 8.827492
        qd = method19_qd_from_heat_input(heat_input, fd, o2_dry_pct=5.0)
        recovered = method19_heat_input_from_qd(qd, fd, o2_dry_pct=5.0)

        self.assertAlmostEqual(recovered, heat_input, places=9)

    def test_basis_consistent_hhv_and_lhv_pairs_produce_same_qd(self) -> None:
        lhv_heat = method19_heat_input_from_fuel_flow(9200.0, 959.51)
        hhv_heat = method19_heat_input_from_fuel_flow(9200.0, 1063.01)
        qd_lhv = method19_qd_from_heat_input(lhv_heat, 9368.114454252687, o2_dry_pct=5.0)
        qd_hhv = method19_qd_from_heat_input(hhv_heat, 8455.987714132507, o2_dry_pct=5.0)

        self.assertAlmostEqual(qd_lhv, qd_hhv, places=9)
        self.assertAlmostEqual(qd_lhv, 108702.2872867924, places=6)

    def test_heat_value_falls_back_to_opposite_basis_when_selected_missing(self) -> None:
        comb = {
            "family": "GAS",
            "basis_sel": "LHV",
            "HHV_Btu_scf": 1050.0,
        }
        heat_value, kind, basis = method19_pick_heat_value(comb, "scf")

        self.assertEqual(kind, "scf")
        self.assertEqual(basis, "HHV")
        self.assertEqual(heat_value, 1050.0)

    def test_fuel_flow_backcalc_is_basis_consistent(self) -> None:
        scfh = method19_fuel_flow_from_heat_input(8.827492, 959.51)
        self.assertAlmostEqual(scfh, 9200.0, places=6)

    def test_dual_fuel_basis_shares_convert_selected_lhv_share_to_hhv_share(self) -> None:
        shares = dual_fuel_basis_shares(
            liquid_share_pct_selected=20.0,
            basis_sel="LHV",
            gas_hhv=1063.01,
            gas_lhv=959.51,
            liquid_hhv=18995.2,
            liquid_lhv=17920.0,
        )

        self.assertAlmostEqual(shares["liquid_sel"], 0.2, places=12)
        self.assertAlmostEqual(shares["gas_sel"], 0.8, places=12)
        self.assertAlmostEqual(shares["liquid_hhv"], 0.19302663142688364, places=12)
        self.assertAlmostEqual(shares["gas_hhv"], 0.8069733685731163, places=12)
        self.assertAlmostEqual(shares["liquid_lhv"], 0.2, places=12)

    def test_dual_fuel_blended_qd_reference_case(self) -> None:
        shares = dual_fuel_basis_shares(
            liquid_share_pct_selected=20.0,
            basis_sel="LHV",
            gas_hhv=1063.01,
            gas_lhv=959.51,
            liquid_hhv=18995.2,
            liquid_lhv=17920.0,
        )
        fd_sel = (shares["gas_sel"] * 9368.114454252687) + (shares["liquid_sel"] * 9872.487304950242)
        gas_heat = method19_heat_input_from_fuel_flow(9200.0, 959.51)
        total_heat = gas_heat / shares["gas_sel"]
        qd = method19_qd_from_heat_input(total_heat, fd_sel, o2_dry_pct=5.0)

        self.assertAlmostEqual(fd_sel, 9468.989024392198, places=9)
        self.assertAlmostEqual(total_heat, 11.034365, places=6)
        self.assertAlmostEqual(qd, 137340.97323844477, places=6)


if __name__ == "__main__":
    unittest.main()
