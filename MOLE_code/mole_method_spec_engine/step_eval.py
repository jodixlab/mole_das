"""Shared step evaluation for calibration and post-cal captures."""

from __future__ import annotations

import statistics
from typing import Any, Dict

from .schemas import StepEvaluation, normalize_float, normalize_step, values_from_series


def _basis_for_step(step: str, step_state: Dict[str, Any]) -> str:
    explicit = str((step_state or {}).get("basis") or "").strip().upper()
    if explicit:
        return explicit
    if step in ("ZERO", "POST_ZERO", "PURGE"):
        return "ABS"
    return "RECOVERY_PCT"


def _default_min_stability_abs(channel: str) -> float:
    return 0.05 if str(channel or "").strip().upper() in ("O2", "CO2") else 0.5


def _stability_threshold(channel: str, basis: str, target: float | None, tolerance: float | None, step_state: Dict[str, Any], tolerances: Dict[str, Any]) -> float:
    min_abs = normalize_float((tolerances or {}).get("min_stability_abs"))
    if min_abs is None:
        min_abs = normalize_float((step_state or {}).get("min_stability_abs"))
    if min_abs is None:
        min_abs = _default_min_stability_abs(channel)

    frac = normalize_float((tolerances or {}).get("stability_frac_of_tol"))
    if frac is None:
        frac = normalize_float((step_state or {}).get("stability_frac_of_tol"))
    if frac is None or frac <= 0.0:
        frac = 0.5

    if tolerance is None:
        return float(min_abs)

    tol_band = float(tolerance)
    if basis == "RECOVERY_PCT" and target not in (None, 0.0):
        tol_band = abs(float(target)) * abs(float(tolerance)) / 100.0
    return max(float(min_abs), abs(float(frac)) * abs(float(tol_band)))


def evaluate_channel_step(
    channel: Any,
    step_state: Any,
    value_series: Any,
    targets: Any,
    tolerances: Any,
) -> Dict[str, Any]:
    """Evaluate a calibration/test step without any UI dependencies.

    `pass` is intentionally driven by tolerance compliance only.
    Stability is carried separately so current MOLE green/red behavior is preserved.
    """
    step_state = dict(step_state or {})
    targets = dict(targets or {})
    tolerances = dict(tolerances or {})

    channel_code = str(channel or "").strip().upper() or "UNKNOWN"
    step = normalize_step(step_state.get("step"))
    if step == "PURGE" and bool(step_state.get("treat_purge_as_zero", True)):
        basis = "ABS"
    else:
        basis = _basis_for_step(step, step_state)

    vals = values_from_series(value_series)
    n = len(vals)
    avg = float(sum(vals) / n) if n else None
    std = float(statistics.pstdev(vals)) if n > 1 else (0.0 if n == 1 else None)
    stability_range = (max(vals) - min(vals)) if n else None

    target = normalize_float(targets.get("target"))
    if target is None and basis == "ABS" and step in ("ZERO", "POST_ZERO", "PURGE"):
        target = 0.0

    tol_abs = normalize_float(tolerances.get("tol_abs"))
    tol_pct = normalize_float(tolerances.get("tol_pct"))
    tol_any = normalize_float(tolerances.get("tolerance"))
    tolerance = tol_abs if basis == "ABS" else tol_pct
    if tolerance is None:
        tolerance = tol_any

    stable = False
    threshold = _stability_threshold(channel_code, basis, target, tolerance, step_state, tolerances)
    if n >= 3 and stability_range is not None:
        stable = float(stability_range) <= float(threshold)

    comparison_value = avg
    recovery_pct = None
    within_tolerance = None
    allow_missing_target_pass = bool(step_state.get("allow_missing_target_pass"))
    stable_required_for_pass = bool(step_state.get("stable_required_for_pass"))
    units_hint = str(targets.get("units") or step_state.get("units") or "").strip()

    status = "NO_DATA"
    reason = "No data in evaluation window."
    passed = False

    if not n:
        result = StepEvaluation(
            step=step,
            basis=basis,
            target=target,
            tolerance=tolerance,
            avg=avg,
            std=std,
            n=n,
            stability_range=stability_range,
            stability_threshold=threshold,
            stable=stable,
            within_tolerance=within_tolerance,
            pass_=passed,
            status=status,
            reason=reason,
            comparison_value=comparison_value,
            recovery_pct=recovery_pct,
            units_hint=units_hint,
            details={"channel": channel_code},
        )
        return result.to_dict()

    if basis == "ABS":
        if target is None or tolerance is None:
            status = "NO_TARGET"
            reason = "Absolute step target or tolerance is not configured."
            passed = bool(allow_missing_target_pass)
        else:
            within_tolerance = abs(float(avg) - float(target)) <= abs(float(tolerance))
            passed = bool(within_tolerance)
            if passed and stable_required_for_pass:
                passed = bool(stable)
            if passed and not stable:
                status = "UNSTABLE"
                reason = "In tolerance, but the evaluation window is still unstable."
            elif passed:
                status = "OK"
                reason = "Average is within absolute tolerance."
            else:
                status = "FAIL"
                reason = "Average is outside absolute tolerance."
    else:
        if target in (None, 0.0) or tolerance is None:
            status = "NO_TARGET"
            reason = "Recovery-based step target or tolerance is not configured."
            passed = bool(allow_missing_target_pass)
        else:
            recovery_pct = (float(avg) / float(target)) * 100.0
            comparison_value = float(recovery_pct)
            within_tolerance = abs(float(recovery_pct) - 100.0) <= abs(float(tolerance))
            passed = bool(within_tolerance)
            if passed and stable_required_for_pass:
                passed = bool(stable)
            if passed and not stable:
                status = "UNSTABLE"
                reason = "Recovery is in tolerance, but the evaluation window is still unstable."
            elif passed:
                status = "OK"
                reason = "Recovery is within tolerance."
            else:
                status = "FAIL"
                reason = "Recovery is outside tolerance."

    result = StepEvaluation(
        step=step,
        basis=basis,
        target=target,
        tolerance=tolerance,
        avg=float(avg) if avg is not None else None,
        std=float(std) if std is not None else None,
        n=n,
        stability_range=float(stability_range) if stability_range is not None else None,
        stability_threshold=float(threshold),
        stable=bool(stable),
        within_tolerance=within_tolerance,
        pass_=bool(passed),
        status=status,
        reason=reason,
        comparison_value=float(comparison_value) if comparison_value is not None else None,
        recovery_pct=float(recovery_pct) if recovery_pct is not None else None,
        units_hint=units_hint,
        details={"channel": channel_code},
    )
    return result.to_dict()
