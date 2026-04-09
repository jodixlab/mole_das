"""Starter method/spec engine for shared evaluation logic.

Phase 0 / 1 scope:
- shared step evaluation
- starter analyzer validity rollup
- starter method profile registry
- versioned evidence records
"""

from .analyzer_validity import derive_analyzer_validity
from .evidence import build_evidence_record
from .method_profiles import get_method_profile
from .method19_calc import (
    dual_fuel_basis_shares,
    dual_fuel_normalize_liquid_share_pct,
    method19_fuel_flow_from_heat_input,
    method19_heat_input_from_fuel_flow,
    method19_heat_input_from_qd,
    method19_o2_factor,
    method19_pick_fd,
    method19_pick_heat_value,
    method19_qd_from_heat_input,
)
from .regulatory_eval import evaluate_regulatory_output
from .schemas import SPEC_ENGINE_FORMULA_VERSION
from .step_eval import evaluate_channel_step
from .training_scenario import build_training_scenario

__all__ = [
    "SPEC_ENGINE_FORMULA_VERSION",
    "build_evidence_record",
    "dual_fuel_basis_shares",
    "dual_fuel_normalize_liquid_share_pct",
    "derive_analyzer_validity",
    "evaluate_channel_step",
    "evaluate_regulatory_output",
    "get_method_profile",
    "method19_fuel_flow_from_heat_input",
    "method19_heat_input_from_fuel_flow",
    "method19_heat_input_from_qd",
    "method19_o2_factor",
    "method19_pick_fd",
    "method19_pick_heat_value",
    "method19_qd_from_heat_input",
    "build_training_scenario",
]
