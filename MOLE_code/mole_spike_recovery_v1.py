"""Shared spike-recovery configuration and evaluation helpers.

This module keeps spike-recovery policy consistent between the Wizard,
DAQ Runner, and downstream artifacts.

Design rules:
- Non-FTIR projects may enable spike recovery optionally and choose their
  own acceptance band.
- When FTIR audit mode is active, spike recovery becomes mandatory and the
  default acceptance criteria are resolved from the selected FTIR method.
- ASTM D6348 defaults to the project's stated accuracy DQO because the
  method does not impose a single fixed universal recovery band.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, Optional, Tuple


METHOD_ASTM_D6348_12 = "ASTM_D6348_12"
METHOD_ASTM_D6348_03 = "ASTM_D6348_03"
METHOD_EPA_320 = "EPA_METHOD_320"
METHOD_PS15 = "PERFORMANCE_SPEC_15"

SOURCE_PROJECT_OPTIONAL = "PROJECT_OPTIONAL"
SOURCE_FTIR_METHOD = "FTIR_METHOD"


DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "mandatory": False,
    "source": SOURCE_PROJECT_OPTIONAL,
    "applies_to_mole": True,
    "applies_to_ftir": False,
    "requires_flow_restriction": False,
    "flow_restriction_pct": 10.0,
    "flow_restriction_summary": "",
    "criteria_mode": "RECOVERY_PERCENT_BAND",
    "recovery_pct_min": 70.0,
    "recovery_pct_max": 130.0,
    "project_accuracy_dqo_pct": None,
    "expected_replicates": 1,
    "method_standard": "",
    "method_label": "",
    "method_basis": "",
    "criterion_summary": "Optional spike recovery disabled.",
    "notes": "",
    "channels": {},
}


DEFAULT_STATE: Dict[str, Any] = {
    "active_phase": "IDLE",
    "sample_flow_value": None,
    "sample_flow_units": "",
    "sample_flow_source": "",
    "sample_flow_override": None,
    "spike_flow_value": None,
    "target_spike_flow_value": None,
    "flow_result": {},
    "channels": {},
    "history": [],
}


METHOD_DEFAULTS: Dict[str, Dict[str, Any]] = {
    METHOD_ASTM_D6348_12: {
        "method_label": "ASTM D6348-12",
        "method_basis": "ASTM D6348-12e1 Sections 11.3.5 and Annex A2.4/A5.",
        "requires_flow_restriction": True,
        "flow_restriction_pct": 10.0,
        "flow_restriction_summary": "Mandatory: spike calibration flow should not exceed 10% of the sample flow rate.",
        "criteria_mode": "PROJECT_DQO_ACCURACY",
        "project_accuracy_dqo_pct": None,
        "expected_replicates": 1,
        "notes": "Mandatory FTIR spike recovery is checked against the project's stated accuracy DQO. ASTM D6348-12e1 also expects the spike concentration to approximate the native effluent level within about 50% when practicable and recognizes that recoveries within about 30% are generally achievable when the method is functioning properly.",
        "criterion_summary": "Mandatory: recovery must be within the project's stated DQO accuracy band.",
    },
    METHOD_EPA_320: {
        "method_label": "EPA Method 320",
        "method_basis": "EPA Method 320 Sections 8.6.3, 9.1.2, 9.1.4, and 9.1.5.",
        "requires_flow_restriction": True,
        "flow_restriction_pct": 10.0,
        "flow_restriction_summary": "Mandatory: spike calibration flow should not exceed 10% of the sample flow rate.",
        "criteria_mode": "RECOVERY_PERCENT_BAND",
        "recovery_pct_min": 70.0,
        "recovery_pct_max": 130.0,
        "expected_replicates": 3,
        "notes": "Mandatory FTIR spike recovery uses the Method 301-style correction-factor window. Method 320 also expects at least three independent spiked samples and duplicate QA spikes within 5% of expected concentration during validation.",
        "criterion_summary": "Mandatory: recovery must be 70-130% with at least 3 independent spike samples expected by the method.",
    },
    METHOD_PS15: {
        "method_label": "Performance Specification 15",
        "method_basis": "40 CFR Part 60 Appendix B Performance Specification 15 Sections 8.3 and 13.2.",
        "requires_flow_restriction": True,
        "flow_restriction_pct": 10.0,
        "flow_restriction_summary": "Mandatory: spike calibration flow should not exceed 10% of the sample flow rate.",
        "criteria_mode": "RECOVERY_PERCENT_BAND",
        "recovery_pct_min": 95.0,
        "recovery_pct_max": 105.0,
        "expected_replicates": 1,
        "notes": "Mandatory FTIR spike recovery defaults to the daily audit sample acceptance band of +/-5% of the expected audit concentration. PS 15 validation also references Method 301-style correction-factor evaluation where applicable.",
        "criterion_summary": "Mandatory: recovery must be 95-105% of the expected audit concentration.",
    },
}


def _clone_jsonable(obj: Any) -> Any:
    try:
        return json.loads(json.dumps(obj))
    except Exception:
        return deepcopy(obj)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if not value:
                return None
        return float(value)
    except Exception:
        return None


def normalize_method(value: Any) -> str:
    raw = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        METHOD_ASTM_D6348_12: METHOD_ASTM_D6348_12,
        METHOD_ASTM_D6348_03: METHOD_ASTM_D6348_12,
        "ASTM_D6348": METHOD_ASTM_D6348_12,
        "D6348": METHOD_ASTM_D6348_12,
        "ASTM_D6348_12E1": METHOD_ASTM_D6348_12,
        METHOD_EPA_320: METHOD_EPA_320,
        "EPA_320": METHOD_EPA_320,
        "METHOD_320": METHOD_EPA_320,
        "320": METHOD_EPA_320,
        METHOD_PS15: METHOD_PS15,
        "PS15": METHOD_PS15,
        "PS_15": METHOD_PS15,
        "PERFORMANCE_SPECIFICATION_15": METHOD_PS15,
    }
    return aliases.get(raw, METHOD_ASTM_D6348_12)


def method_default_config(method_value: Any, project_accuracy_dqo_pct: Any = None) -> Dict[str, Any]:
    method_code = normalize_method(method_value)
    meta = _clone_jsonable(METHOD_DEFAULTS.get(method_code) or METHOD_DEFAULTS[METHOD_ASTM_D6348_12])
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(meta)
    cfg["enabled"] = True
    cfg["mandatory"] = True
    cfg["source"] = SOURCE_FTIR_METHOD
    cfg["applies_to_mole"] = True
    cfg["applies_to_ftir"] = True
    cfg["method_standard"] = method_code
    dqo = _safe_float(project_accuracy_dqo_pct)
    if cfg.get("criteria_mode") == "PROJECT_DQO_ACCURACY":
        cfg["project_accuracy_dqo_pct"] = dqo
        if dqo is not None and dqo >= 0.0:
            cfg["recovery_pct_min"] = max(0.0, 100.0 - float(dqo))
            cfg["recovery_pct_max"] = 100.0 + float(dqo)
            cfg["criterion_summary"] = f"Mandatory: recovery must be within the project's stated DQO accuracy band (100 +/- {float(dqo):g}%)."
        else:
            cfg["recovery_pct_min"] = None
            cfg["recovery_pct_max"] = None
            cfg["criterion_summary"] = "Mandatory: enter the ASTM D6348 project accuracy DQO to evaluate spike recovery."
    return cfg


def normalize_config(
    cfg: Any,
    *,
    ftir_enabled: bool = False,
    ftir_role: str = "AUDIT",
    ftir_method: Any = None,
) -> Dict[str, Any]:
    out = dict(DEFAULT_CONFIG)
    if isinstance(cfg, dict):
        out.update(_clone_jsonable(cfg))

    out["enabled"] = bool(out.get("enabled"))
    out["mandatory"] = bool(out.get("mandatory"))
    src = str(out.get("source") or SOURCE_PROJECT_OPTIONAL).strip().upper()
    out["source"] = src if src in (SOURCE_PROJECT_OPTIONAL, SOURCE_FTIR_METHOD) else SOURCE_PROJECT_OPTIONAL
    out["applies_to_mole"] = bool(out.get("applies_to_mole", True))
    out["applies_to_ftir"] = bool(out.get("applies_to_ftir", False))
    out["requires_flow_restriction"] = bool(out.get("requires_flow_restriction", False))
    out["flow_restriction_pct"] = _safe_float(out.get("flow_restriction_pct"))
    out["flow_restriction_summary"] = str(out.get("flow_restriction_summary") or "").strip()
    out["criteria_mode"] = str(out.get("criteria_mode") or "RECOVERY_PERCENT_BAND").strip().upper()
    out["recovery_pct_min"] = _safe_float(out.get("recovery_pct_min"))
    out["recovery_pct_max"] = _safe_float(out.get("recovery_pct_max"))
    out["project_accuracy_dqo_pct"] = _safe_float(out.get("project_accuracy_dqo_pct"))
    try:
        out["expected_replicates"] = max(1, int(out.get("expected_replicates") or 1))
    except Exception:
        out["expected_replicates"] = 1
    out["method_standard"] = normalize_method(out.get("method_standard") or ftir_method)
    out["method_label"] = str(out.get("method_label") or "").strip()
    out["method_basis"] = str(out.get("method_basis") or "").strip()
    out["criterion_summary"] = str(out.get("criterion_summary") or "").strip()
    out["notes"] = str(out.get("notes") or "").strip()
    out["channels"] = dict(out.get("channels") or {})

    ftir_active = bool(ftir_enabled and str(ftir_role or "AUDIT").strip().upper() == "AUDIT")
    if ftir_active:
        forced = method_default_config(
            ftir_method or out.get("method_standard"),
            project_accuracy_dqo_pct=out.get("project_accuracy_dqo_pct"),
        )
        if isinstance(cfg, dict) and cfg.get("project_accuracy_dqo_pct") not in (None, ""):
            forced["project_accuracy_dqo_pct"] = _safe_float(cfg.get("project_accuracy_dqo_pct"))
            if forced.get("criteria_mode") == "PROJECT_DQO_ACCURACY":
                dqo = forced.get("project_accuracy_dqo_pct")
                if dqo is not None:
                    forced["recovery_pct_min"] = max(0.0, 100.0 - float(dqo))
                    forced["recovery_pct_max"] = 100.0 + float(dqo)
                    forced["criterion_summary"] = f"Mandatory: recovery must be within the project's stated DQO accuracy band (100 +/- {float(dqo):g}%)."
        forced["channels"] = dict(out.get("channels") or {})
        return forced

    if out.get("enabled"):
        if out.get("requires_flow_restriction"):
            if out.get("flow_restriction_pct") is None or float(out.get("flow_restriction_pct") or 0.0) <= 0.0:
                out["flow_restriction_pct"] = 10.0
            if not out.get("flow_restriction_summary"):
                out["flow_restriction_summary"] = f"Spike calibration flow must not exceed {float(out['flow_restriction_pct']):g}% of the sample flow rate."
        if out.get("recovery_pct_min") is None:
            out["recovery_pct_min"] = 70.0
        if out.get("recovery_pct_max") is None:
            out["recovery_pct_max"] = 130.0
        if not out.get("criterion_summary"):
            out["criterion_summary"] = f"Optional: recovery must be between {float(out['recovery_pct_min']):g}% and {float(out['recovery_pct_max']):g}%."
    else:
        out["criterion_summary"] = "Optional spike recovery disabled."
        if not out.get("flow_restriction_summary"):
            out["flow_restriction_summary"] = ""

    if not out.get("method_label") and out.get("method_standard") in METHOD_DEFAULTS:
        out["method_label"] = str((METHOD_DEFAULTS.get(out["method_standard"]) or {}).get("method_label") or "")
    if not out.get("method_basis") and out.get("method_standard") in METHOD_DEFAULTS:
        out["method_basis"] = str((METHOD_DEFAULTS.get(out["method_standard"]) or {}).get("method_basis") or "")
    return out


def normalize_state(state: Any) -> Dict[str, Any]:
    out = _clone_jsonable(DEFAULT_STATE)
    if isinstance(state, dict):
        out.update(_clone_jsonable(state))
    out["active_phase"] = str(out.get("active_phase") or "IDLE").strip().upper() or "IDLE"
    out["sample_flow_value"] = _safe_float(out.get("sample_flow_value"))
    out["sample_flow_units"] = str(out.get("sample_flow_units") or "").strip()
    out["sample_flow_source"] = str(out.get("sample_flow_source") or "").strip()
    out["sample_flow_override"] = _safe_float(out.get("sample_flow_override"))
    out["spike_flow_value"] = _safe_float(out.get("spike_flow_value"))
    out["target_spike_flow_value"] = _safe_float(out.get("target_spike_flow_value"))
    out["flow_result"] = _clone_jsonable(out.get("flow_result") if isinstance(out.get("flow_result"), dict) else {})
    chans_in = out.get("channels") if isinstance(out.get("channels"), dict) else {}
    chans_out: Dict[str, Dict[str, Any]] = {}
    for code, spec in chans_in.items():
        canon = str(code or "").strip().upper()
        if not canon:
            continue
        rec = spec if isinstance(spec, dict) else {}
        chans_out[canon] = {
            "spike_amount": _safe_float(rec.get("spike_amount")),
            "units": str(rec.get("units") or "").strip(),
            "native_mole": _safe_float(rec.get("native_mole")),
            "spike_mole": _safe_float(rec.get("spike_mole")),
            "native_ftir": _safe_float(rec.get("native_ftir")),
            "spike_ftir": _safe_float(rec.get("spike_ftir")),
            "mole_result": _clone_jsonable(rec.get("mole_result") if isinstance(rec.get("mole_result"), dict) else {}),
            "ftir_result": _clone_jsonable(rec.get("ftir_result") if isinstance(rec.get("ftir_result"), dict) else {}),
            "native_timestamp_iso": str(rec.get("native_timestamp_iso") or ""),
            "spike_timestamp_iso": str(rec.get("spike_timestamp_iso") or ""),
        }
    out["channels"] = chans_out
    history = out.get("history")
    out["history"] = list(history) if isinstance(history, list) else []
    return out


def effective_recovery_band(cfg: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    norm = normalize_config(cfg)
    return (_safe_float(norm.get("recovery_pct_min")), _safe_float(norm.get("recovery_pct_max")))


def effective_flow_restriction(cfg: Dict[str, Any]) -> Tuple[bool, Optional[float]]:
    norm = normalize_config(cfg)
    return (bool(norm.get("requires_flow_restriction")), _safe_float(norm.get("flow_restriction_pct")))


def evaluate_flow_restriction(sample_flow_value: Any, spike_flow_value: Any, cfg: Dict[str, Any]) -> Dict[str, Any]:
    sample_v = _safe_float(sample_flow_value)
    spike_v = _safe_float(spike_flow_value)
    required, limit_pct = effective_flow_restriction(cfg)
    result: Dict[str, Any] = {
        "sample_flow_value": sample_v,
        "spike_flow_value": spike_v,
        "flow_restriction_pct": limit_pct,
        "target_spike_flow_value": None,
        "status": "NOT_REQUIRED",
        "reason": "",
    }
    if not required:
        result["reason"] = "Flow restriction is not required for this project."
        return result
    if limit_pct is None or float(limit_pct) <= 0.0:
        result["status"] = "CRITERIA_REQUIRED"
        result["reason"] = "Flow restriction percentage is not defined."
        return result
    if sample_v is None or float(sample_v) <= 0.0:
        result["status"] = "SAMPLE_FLOW_REQUIRED"
        result["reason"] = "Sample flow is missing or invalid."
        return result
    target_v = float(sample_v) * (float(limit_pct) / 100.0)
    result["target_spike_flow_value"] = target_v
    if spike_v is None or float(spike_v) < 0.0:
        result["status"] = "SPIKE_FLOW_REQUIRED"
        result["reason"] = "Calibration spike flow is missing."
        return result
    if float(spike_v) <= float(target_v) + 1e-12:
        result["status"] = "PASS"
        result["reason"] = (
            f"Spike flow {float(spike_v):.4g} is within the {float(limit_pct):.4g}% limit "
            f"(target <= {float(target_v):.4g})."
        )
    else:
        result["status"] = "FAIL"
        result["reason"] = (
            f"Spike flow {float(spike_v):.4g} exceeds the {float(limit_pct):.4g}% limit "
            f"(target <= {float(target_v):.4g})."
        )
    return result


def evaluate_capture(native_value: Any, spike_value: Any, spike_amount: Any, cfg: Dict[str, Any]) -> Dict[str, Any]:
    native_v = _safe_float(native_value)
    spike_v = _safe_float(spike_value)
    spike_amt = _safe_float(spike_amount)
    low, high = effective_recovery_band(cfg)
    result: Dict[str, Any] = {
        "native_value": native_v,
        "spike_value": spike_v,
        "spike_amount": spike_amt,
        "expected_total": None,
        "observed_delta": None,
        "recovery_pct": None,
        "status": "INCOMPLETE",
        "reason": "",
    }
    if native_v is None:
        result["reason"] = "Native capture missing."
        return result
    if spike_v is None:
        result["reason"] = "Spike capture missing."
        return result
    if spike_amt is None or abs(float(spike_amt)) <= 1e-12:
        result["reason"] = "Spike amount is missing or zero."
        return result

    expected_total = float(native_v) + float(spike_amt)
    observed_delta = float(spike_v) - float(native_v)
    recovery_pct = (observed_delta / float(spike_amt)) * 100.0
    result["expected_total"] = expected_total
    result["observed_delta"] = observed_delta
    result["recovery_pct"] = recovery_pct

    if low is None or high is None:
        result["status"] = "CRITERIA_REQUIRED"
        result["reason"] = "Recovery criteria are not fully defined."
        return result

    if float(low) <= float(recovery_pct) <= float(high):
        result["status"] = "PASS"
        result["reason"] = f"Recovery {float(recovery_pct):.1f}% is within {float(low):.1f}-{float(high):.1f}%."
    else:
        result["status"] = "FAIL"
        result["reason"] = f"Recovery {float(recovery_pct):.1f}% is outside {float(low):.1f}-{float(high):.1f}%."
    return result
