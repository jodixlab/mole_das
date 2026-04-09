"""Starter analyzer validity rollup."""

from __future__ import annotations

from typing import Any, Dict, Optional


def _check_pass(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, dict):
        if "pass" in value:
            try:
                return bool(value.get("pass"))
            except Exception:
                return None
        if "status" in value:
            status = str(value.get("status") or "").strip().upper()
            if status in ("OK", "PASS"):
                return True
            if status in ("FAIL", "INVALID"):
                return False
    if isinstance(value, bool):
        return value
    return None


def derive_analyzer_validity(
    zero: Any,
    span: Any,
    drift: Any = None,
    linearity: Any = None,
    *,
    latched_invalid: bool = False,
    invalidate_on_drift: bool = False,
    invalidate_on_linearity: bool = False,
) -> Dict[str, Any]:
    zero_ok = _check_pass(zero)
    span_ok = _check_pass(span)
    drift_ok = _check_pass(drift)
    linearity_ok = _check_pass(linearity)

    state = "VALID"
    reason = "Calibration checks are acceptable."
    if bool(latched_invalid):
        state = "INVALID"
        reason = "Channel is latched invalid."
    elif zero_ok is False or span_ok is False:
        state = "INVALID"
        reason = "Zero or span check failed."
    elif drift_ok is False and bool(invalidate_on_drift):
        state = "INVALID"
        reason = "Post-calibration drift check failed."
    elif linearity_ok is False and bool(invalidate_on_linearity):
        state = "INVALID"
        reason = "Linearity check failed."
    elif drift_ok is False or linearity_ok is False:
        state = "DEGRADED"
        reason = "Drift or linearity check failed."
    elif zero_ok is None or span_ok is None:
        state = "DEGRADED"
        reason = "Zero or span check is missing."

    gates = {
        "allow_display": True,
        "allow_regulatory": state == "VALID",
        "allow_combustion_math": state == "VALID",
    }
    return {
        "state": state,
        "scores": {
            "zero": zero_ok,
            "span": span_ok,
            "drift": drift_ok,
            "linearity": linearity_ok,
        },
        "gates": gates,
        "latched_invalid": bool(latched_invalid),
        "invalidate_on_drift": bool(invalidate_on_drift),
        "invalidate_on_linearity": bool(invalidate_on_linearity),
        "reason": reason,
    }
