"""Shared simulator/training scenario builder for the method/spec engine."""

from __future__ import annotations

import hashlib
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .method_profiles import get_method_profile
from .schemas import SPEC_ENGINE_FORMULA_VERSION


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value or "").strip()
        if not text:
            return None
        text = text.replace(",", "")
        match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
        if not match:
            return None
        return float(match.group(0))
    except Exception:
        return None


def _norm_code(value: Any) -> str:
    return str(value or "").strip().upper()


def _norm_token(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


def _triangular(u: float, a: float, c: float, b: float) -> float:
    if b <= a:
        return a
    if c < a:
        c = a
    if c > b:
        c = b
    u = 0.0 if u < 0.0 else (1.0 if u > 1.0 else u)
    fc = (c - a) / (b - a) if (b - a) > 0 else 0.5
    if u < fc:
        return a + math.sqrt(u * (b - a) * (c - a))
    return b - math.sqrt((1.0 - u) * (b - a) * (b - c))


@lru_cache(maxsize=8)
def _ranges_db_cached(ranges_path: str) -> Dict[str, Any]:
    try:
        path = Path(ranges_path)
        if path.exists():
            obj = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                return obj
    except Exception:
        pass
    return {}


def _ranges_db(package_root: Optional[Path], explicit: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(explicit, dict):
        return explicit
    if package_root is None:
        return {}
    path = Path(package_root) / "mole_das_data" / "configs" / "sim_emissions_ranges.json"
    return _ranges_db_cached(str(path))


def _resolve_profile_inputs(session: Dict[str, Any]) -> Dict[str, str]:
    project = session.get("project") if isinstance(session.get("project"), dict) else {}
    source = session.get("source") if isinstance(session.get("source"), dict) else {}
    fuel = session.get("fuel") if isinstance(session.get("fuel"), dict) else {}
    regulatory = session.get("regulatory") if isinstance(session.get("regulatory"), dict) else {}
    reg_ctx = regulatory.get("context") if isinstance(regulatory.get("context"), dict) else {}

    source_type = (
        source.get("source_type")
        or source.get("source_category")
        or project.get("source_type")
        or source.get("category")
        or project.get("unit_type")
        or project.get("source_category")
        or "GENERIC"
    )
    fuel_type = (
        fuel.get("fuel_type")
        or fuel.get("fuel_button_code")
        or fuel.get("fuel_code")
        or fuel.get("fuel_category")
        or fuel.get("category")
        or ""
    )
    fuel_map = {
        "NG": "NATURAL_GAS",
        "DSL": "DIESEL",
        "DG": "DUAL_FUEL",
        "BG": "BIOGAS",
        "RFG": "REFINERY_FUEL_GAS",
        "OT": "OTHER",
    }
    fuel_type_norm = _norm_token(fuel_type)
    fuel_type = fuel_map.get(fuel_type_norm, fuel_type)
    duty_type = (
        source.get("duty_type")
        or project.get("duty_type")
        or reg_ctx.get("engine_service")
        or project.get("engine_type")
        or source.get("engine_type")
        or ""
    )
    if (not duty_type) and _norm_token(source_type) == "ENGINE":
        duty_type = "RICE"
    regulation = (
        regulatory.get("regulation")
        or regulatory.get("subpart")
        or project.get("regulation")
        or project.get("program")
        or ""
    )
    return {
        "source_type": str(source_type or ""),
        "fuel_type": str(fuel_type or ""),
        "duty_type": str(duty_type or ""),
        "regulation": str(regulation or ""),
    }


def _training_source_signature(session: Dict[str, Any]) -> Dict[str, str]:
    source = session.get("source") if isinstance(session.get("source"), dict) else {}
    fuel = session.get("fuel") if isinstance(session.get("fuel"), dict) else {}
    regulatory = session.get("regulatory") if isinstance(session.get("regulatory"), dict) else {}
    reg_ctx = regulatory.get("context") if isinstance(regulatory.get("context"), dict) else {}

    source_family = _norm_token(
        source.get("source_category")
        or source.get("source_type")
        or source.get("category")
        or "GENERIC"
    )
    if source_family not in {"ENGINE", "TURBINE", "HEATER", "BOILER", "FLARE"}:
        source_family = "GENERIC"

    fuel_token = _norm_token(
        fuel.get("fuel_button_code")
        or fuel.get("fuel_type")
        or fuel.get("fuel_code")
        or fuel.get("fuel_category")
        or fuel.get("category")
        or ""
    )
    if fuel_token in {"NG", "NATURAL_GAS", "BIOGAS", "BG", "REFINERY_FUEL_GAS", "RFG", "LANDFILL_GAS", "DIGESTER_GAS"}:
        fuel_family = "GAS"
    elif fuel_token in {"DSL", "DIESEL", "ULSD", "DISTILLATE"}:
        fuel_family = "LIQUID"
    elif fuel_token in {"DG", "DUAL_FUEL"}:
        fuel_family = "DUAL"
    else:
        fuel_family = "UNKNOWN"

    ignition = _norm_token(
        reg_ctx.get("engine_ignition")
        or source.get("engine_ignition")
        or regulatory.get("engine_ignition")
        or ""
    )
    return {
        "source_family": source_family,
        "fuel_family": fuel_family,
        "fuel_token": fuel_token,
        "ignition": ignition,
    }


def _training_sample_envelope(signature: Dict[str, str], code: str) -> Optional[Dict[str, float]]:
    code_u = _norm_code(code)
    source_family = str(signature.get("source_family") or "GENERIC")
    fuel_family = str(signature.get("fuel_family") or "UNKNOWN")
    ignition = str(signature.get("ignition") or "")

    profile_key = "GENERIC"
    if source_family == "ENGINE":
        if ignition == "CI" or fuel_family == "LIQUID":
            profile_key = "ENGINE_DIESEL"
        else:
            profile_key = "ENGINE_GAS"
    elif source_family == "TURBINE":
        profile_key = "TURBINE_GAS" if fuel_family in {"GAS", "DUAL", "UNKNOWN"} else "TURBINE_LIQUID"
    elif source_family in {"HEATER", "BOILER"}:
        profile_key = "FIRED_LIQUID" if fuel_family == "LIQUID" else "FIRED_GAS"
    elif source_family == "FLARE":
        profile_key = "FLARE_GAS"

    envelopes: Dict[str, Dict[str, Dict[str, float]]] = {
        "ENGINE_GAS": {
            "O2": {"lo": 3.0, "md": 6.0, "hi": 10.0},
            "CO2": {"lo": 5.0, "md": 8.0, "hi": 11.0},
            "NOX": {"lo": 40.0, "md": 90.0, "hi": 180.0},
            "NO": {"lo": 35.0, "md": 80.0, "hi": 165.0},
            "NO2": {"lo": 1.0, "md": 4.0, "hi": 18.0},
            "CO": {"lo": 15.0, "md": 60.0, "hi": 220.0},
            "VOC": {"lo": 1.0, "md": 12.0, "hi": 45.0},
        },
        "ENGINE_DIESEL": {
            "O2": {"lo": 9.0, "md": 11.5, "hi": 14.5},
            "CO2": {"lo": 2.5, "md": 4.5, "hi": 7.0},
            "NOX": {"lo": 140.0, "md": 240.0, "hi": 380.0},
            "NO": {"lo": 125.0, "md": 220.0, "hi": 350.0},
            "NO2": {"lo": 2.0, "md": 8.0, "hi": 28.0},
            "CO": {"lo": 3.0, "md": 18.0, "hi": 70.0},
            "VOC": {"lo": 0.5, "md": 4.0, "hi": 18.0},
        },
        "TURBINE_GAS": {
            "O2": {"lo": 12.0, "md": 14.5, "hi": 17.5},
            "CO2": {"lo": 2.0, "md": 3.0, "hi": 4.8},
            "NOX": {"lo": 10.0, "md": 35.0, "hi": 90.0},
            "NO": {"lo": 8.0, "md": 30.0, "hi": 80.0},
            "NO2": {"lo": 0.5, "md": 2.0, "hi": 8.0},
            "CO": {"lo": 1.0, "md": 10.0, "hi": 40.0},
            "VOC": {"lo": 0.2, "md": 1.5, "hi": 8.0},
        },
        "TURBINE_LIQUID": {
            "O2": {"lo": 11.0, "md": 13.5, "hi": 16.5},
            "CO2": {"lo": 2.5, "md": 4.0, "hi": 6.0},
            "NOX": {"lo": 20.0, "md": 55.0, "hi": 120.0},
            "NO": {"lo": 18.0, "md": 48.0, "hi": 105.0},
            "NO2": {"lo": 0.5, "md": 2.5, "hi": 10.0},
            "CO": {"lo": 2.0, "md": 12.0, "hi": 45.0},
            "VOC": {"lo": 0.3, "md": 2.0, "hi": 9.0},
        },
        "FIRED_GAS": {
            "O2": {"lo": 2.0, "md": 4.0, "hi": 7.0},
            "CO2": {"lo": 7.0, "md": 9.0, "hi": 11.5},
            "NOX": {"lo": 15.0, "md": 45.0, "hi": 120.0},
            "NO": {"lo": 12.0, "md": 40.0, "hi": 110.0},
            "NO2": {"lo": 0.2, "md": 1.0, "hi": 5.0},
            "CO": {"lo": 4.0, "md": 18.0, "hi": 70.0},
            "VOC": {"lo": 0.3, "md": 1.5, "hi": 6.0},
        },
        "FIRED_LIQUID": {
            "O2": {"lo": 2.5, "md": 4.5, "hi": 8.0},
            "CO2": {"lo": 8.0, "md": 10.5, "hi": 14.0},
            "NOX": {"lo": 30.0, "md": 80.0, "hi": 180.0},
            "NO": {"lo": 25.0, "md": 70.0, "hi": 160.0},
            "NO2": {"lo": 0.5, "md": 2.0, "hi": 8.0},
            "CO": {"lo": 5.0, "md": 20.0, "hi": 75.0},
            "VOC": {"lo": 0.5, "md": 2.0, "hi": 8.0},
        },
        "FLARE_GAS": {
            "O2": {"lo": 0.5, "md": 2.0, "hi": 5.0},
            "CO2": {"lo": 4.0, "md": 8.0, "hi": 13.0},
            "NOX": {"lo": 10.0, "md": 40.0, "hi": 120.0},
            "NO": {"lo": 8.0, "md": 35.0, "hi": 105.0},
            "NO2": {"lo": 0.2, "md": 1.0, "hi": 5.0},
            "CO": {"lo": 5.0, "md": 30.0, "hi": 140.0},
            "VOC": {"lo": 0.5, "md": 4.0, "hi": 20.0},
        },
        "GENERIC": {
            "O2": {"lo": 4.0, "md": 8.0, "hi": 12.0},
            "CO2": {"lo": 4.0, "md": 8.0, "hi": 12.0},
            "NOX": {"lo": 20.0, "md": 80.0, "hi": 220.0},
            "NO": {"lo": 15.0, "md": 70.0, "hi": 200.0},
            "NO2": {"lo": 0.5, "md": 2.0, "hi": 10.0},
            "CO": {"lo": 5.0, "md": 40.0, "hi": 160.0},
            "VOC": {"lo": 0.5, "md": 6.0, "hi": 30.0},
        },
    }
    profile = envelopes.get(profile_key) or envelopes["GENERIC"]
    row = profile.get(code_u)
    return dict(row) if isinstance(row, dict) else None


def build_training_scenario(
    session: Dict[str, Any],
    *,
    codes: Sequence[str],
    prescriptions: Dict[str, Dict[str, Any]],
    package_root: Optional[Path] = None,
    ranges_db: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the canonical training scenario used by the live simulator."""

    job_id = str(
        (session.get("project") or {}).get("job_id")
        or (session.get("project_session") or {}).get("job_id")
        or session.get("job_id")
        or "session"
    ).strip()

    def _stable_u01(tag: str) -> float:
        h = hashlib.sha256((job_id + "|" + tag).encode("utf-8")).hexdigest()[:16]
        u = int(h, 16) / float(0xFFFFFFFFFFFFFFFF)
        if u < 0.0:
            return 0.0
        if u > 1.0:
            return 1.0
        return float(u)

    ranges_root = _ranges_db(package_root, ranges_db)
    ranges = (ranges_root.get("pollutants") or {}) if isinstance(ranges_root, dict) else {}

    poll = session.get("pollutants") if isinstance(session.get("pollutants"), dict) else {}
    resolved_by = ((poll.get("resolved") or {}).get("resolved_by_analyte") or {}) if isinstance(poll, dict) else {}
    selected = poll.get("selected") if isinstance(poll, dict) else []
    if not isinstance(selected, list):
        selected = []

    poll_codes = []
    for code in list(selected) + list(codes or []):
        code_u = _norm_code(code)
        if code_u and code_u not in poll_codes:
            poll_codes.append(code_u)

    for extra in ("O2", "CO2"):
        if extra not in poll_codes:
            poll_codes.append(extra)

    ws = ((session.get("daq_runner") or {}).get("worksteps") or {})
    ws_q = ws.get("qaqc") if isinstance(ws.get("qaqc"), dict) else {}

    def _upper_qblk(block: Any) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if isinstance(block, dict):
            for key, value in block.items():
                code_u = _norm_code(key)
                if code_u:
                    out[code_u] = value
        return out

    q_zero = _upper_qblk(ws_q.get("zero") or {})
    q_mid = _upper_qblk(ws_q.get("mid") or {})
    q_span = _upper_qblk(ws_q.get("span") or {})

    targets_ambient: Dict[str, float] = {code: 0.0 for code in poll_codes}
    targets_ambient["O2"] = 20.9
    targets_ambient["CO2"] = 0.04

    targets_zero: Dict[str, float] = {}
    targets_mid: Dict[str, float] = {}
    targets_span: Dict[str, float] = {}

    for code in poll_codes:
        zt = _safe_float((q_zero.get(code) or {}).get("target"))
        mt = _safe_float((q_mid.get(code) or {}).get("target"))
        st = _safe_float((q_span.get(code) or {}).get("target"))

        pres_row = prescriptions.get(code) if isinstance(prescriptions, dict) else {}
        pres_row = pres_row if isinstance(pres_row, dict) else {}
        resolved_row = resolved_by.get(code) if isinstance(resolved_by, dict) else {}
        resolved_row = resolved_row if isinstance(resolved_row, dict) else {}

        if st is None:
            st = _safe_float(pres_row.get("span_target"))
        if mt is None:
            mt = _safe_float(pres_row.get("mid_target"))

        zt = 0.0

        if mt is None and st is not None:
            mid_frac = _safe_float(resolved_row.get("mid_fraction"))
            if mid_frac is None or not (0.0 < float(mid_frac) < 1.0):
                mid_frac = 0.50
            mt = st * float(mid_frac)

        targets_zero[code] = float(zt or 0.0)
        targets_mid[code] = float(mt) if mt is not None else float(zt or 0.0)
        targets_span[code] = float(st) if st is not None else float(mt or zt or 0.0)

    def _has_explicit_target(qblk: Dict[str, Any], code: str) -> bool:
        try:
            row = qblk.get(code)
            if isinstance(row, dict):
                return _safe_float(row.get("target")) is not None
            return _safe_float(row) is not None
        except Exception:
            return False

    for code in ("O2", "CO2"):
        try:
            pres_row = prescriptions.get(code) if isinstance(prescriptions, dict) else {}
            pres_row = pres_row if isinstance(pres_row, dict) else {}
            z_exp = _has_explicit_target(q_zero, code) or (_safe_float(pres_row.get("zero_target")) is not None)
            m_exp = _has_explicit_target(q_mid, code)
            s_exp = _has_explicit_target(q_span, code) or (_safe_float(pres_row.get("span_target")) is not None)

            if code == "O2":
                if not z_exp:
                    targets_zero[code] = 0.0
                if not m_exp:
                    targets_mid[code] = 0.0
                if not s_exp:
                    targets_span[code] = 0.0
            else:
                if not z_exp:
                    targets_zero[code] = 0.0
                if not m_exp:
                    targets_mid[code] = 0.0
                if not s_exp:
                    targets_span[code] = 0.0
        except Exception:
            pass

    signature = _training_source_signature(session)
    combustion_u = _stable_u01("combustion:excess_air")
    targets_sample: Dict[str, float] = dict(targets_span)
    for code in poll_codes:
        envelope = _training_sample_envelope(signature, code)
        if code in ("O2", "CO2"):
            if isinstance(envelope, dict):
                lo = float(envelope.get("lo") or 0.0)
                md = float(envelope.get("md") or lo)
                hi = float(envelope.get("hi") or md)
                u = combustion_u if code == "O2" else (1.0 - combustion_u)
                targets_sample[code] = float(_triangular(u, lo, md, hi))
                continue
            rng = ranges.get(code) if isinstance(ranges, dict) else None
            if isinstance(rng, dict):
                lo = _safe_float(rng.get("p25") or rng.get("p10") or rng.get("p05"))
                md = _safe_float(rng.get("p50") or rng.get("median"))
                hi = _safe_float(rng.get("p75") or rng.get("p90") or rng.get("p95"))
                if lo is not None and md is not None and hi is not None:
                    targets_sample[code] = float(_triangular(_stable_u01(f"{code}:sample"), float(lo), float(md), float(hi)))
                    continue
            targets_sample[code] = 8.4 if code == "O2" else 7.7
            continue

        rng = ranges.get(code) if isinstance(ranges, dict) else None
        span_target = float(targets_span.get(code, 0.0) or 0.0)
        sample_val: Optional[float] = None
        if isinstance(rng, dict):
            lo = _safe_float(rng.get("p25") or rng.get("p10") or rng.get("p05"))
            md = _safe_float(rng.get("p50") or rng.get("median"))
            hi = _safe_float(rng.get("p75") or rng.get("p90") or rng.get("p95"))
            if lo is not None and md is not None and hi is not None:
                if isinstance(envelope, dict):
                    env_lo = float(envelope.get("lo") or 0.0)
                    env_md = float(envelope.get("md") or env_lo)
                    env_hi = float(envelope.get("hi") or env_md)
                    lo = max(float(lo), env_lo)
                    hi = min(float(hi), env_hi)
                    if hi < lo:
                        lo, md, hi = env_lo, env_md, env_hi
                    else:
                        md = min(max(float(md), lo), hi)
                sample_val = float(_triangular(_stable_u01(f"{code}:sample"), float(lo), float(md), float(hi)))

        if sample_val is None and isinstance(envelope, dict):
            sample_val = float(
                _triangular(
                    _stable_u01(f"{code}:sample"),
                    float(envelope.get("lo") or 0.0),
                    float(envelope.get("md") or envelope.get("lo") or 0.0),
                    float(envelope.get("hi") or envelope.get("md") or envelope.get("lo") or 0.0),
                )
            )

        if sample_val is None:
            sample_val = span_target * 0.60 if span_target > 0.0 else 0.0
        if span_target > 0.0 and sample_val > 0.85 * span_target:
            sample_val = 0.85 * span_target
        if sample_val < 0.0:
            sample_val = 0.0
        targets_sample[code] = float(sample_val)

    post_zero: Dict[str, float] = dict(targets_zero)
    post_span: Dict[str, float] = dict(targets_span)
    postcal = ws.get("postcal") if isinstance(ws.get("postcal"), dict) else {}
    try:
        run_no = int(postcal.get("run_no") or 0)
    except Exception:
        run_no = 0

    poll_units: Dict[str, str] = {}
    try:
        if isinstance(prescriptions, dict):
            for key, row in prescriptions.items():
                code_u = _norm_code(key)
                row_d = row if isinstance(row, dict) else {}
                raw_u = str(
                    row_d.get("units")
                    or row_d.get("expected_units")
                    or row_d.get("unit")
                    or ""
                ).strip().lower()
                if (not raw_u) and code_u in ("O2", "CO2", "H2O", "RH"):
                    raw_u = "%"
                if code_u:
                    poll_units[code_u] = raw_u
    except Exception:
        poll_units = {}

    for code in poll_codes:
        span_target = float(targets_span.get(code, 0.0) or 0.0)
        zero_target = float(targets_zero.get(code, 0.0) or 0.0)
        unit_text = str(poll_units.get(code, "ppm") or "ppm").lower().strip()
        is_pct_units = bool(("%" in unit_text) or ("pct" in unit_text) or ("percent" in unit_text))

        if is_pct_units:
            if code == "O2":
                drift_abs = max(0.20, 0.01 * span_target)
            else:
                drift_abs = max(0.02, 0.05 * span_target)
        else:
            drift_abs = max(0.5, 0.001 * span_target)

        u_zero = (_stable_u01(f"{code}:run{run_no}:zero_drift") - 0.5) * 2.0
        u_span = (_stable_u01(f"{code}:run{run_no}:span_drift") - 0.5) * 2.0
        post_zero_val = zero_target + (u_zero * drift_abs)
        post_span_val = span_target * (1.0 + (u_span * 0.01))

        if code == "O2":
            post_zero_val = max(0.0, min(21.0, post_zero_val))
            post_span_val = max(0.0, min(21.0, post_span_val))
        elif code == "CO2":
            post_zero_val = max(0.0, min(25.0, post_zero_val))
            post_span_val = max(0.0, min(25.0, post_span_val))
        else:
            post_zero_val = max(0.0, post_zero_val)
            post_span_val = max(0.0, post_span_val)

        post_zero[code] = post_zero_val
        post_span[code] = post_span_val

    profile_inputs = _resolve_profile_inputs(session)
    profile = get_method_profile(
        profile_inputs.get("source_type"),
        profile_inputs.get("fuel_type"),
        profile_inputs.get("duty_type"),
        profile_inputs.get("regulation"),
    )

    scenario = {
        "name": "sim_training",
        "formula_version": SPEC_ENGINE_FORMULA_VERSION,
        "codes": list(poll_codes),
        "method_profile": dict(profile or {}),
        "profile_inputs": profile_inputs,
        "recommended_sequence": list((profile or {}).get("cal_sequence") or ["ZERO", "MID", "SPAN", "SAMPLE", "POST_ZERO", "POST_SPAN"]),
        "required_channels": list((profile or {}).get("required_channels") or []),
        "targets": {
            "AMBIENT": targets_ambient,
            "ZERO": targets_zero,
            "MID": targets_mid,
            "SPAN": targets_span,
            "SAMPLE": targets_sample,
            "POST_ZERO": post_zero,
            "POST_SPAN": post_span,
        },
        "tau_s": 4.0,
        "noise": 0.02,
        "noise_frac": 0.004,
        "simulator": {
            "engine": "mole_method_spec_engine.training_scenario",
            "job_id": job_id,
            "ranges_source": "package_ranges" if package_root is not None else "none",
            "zero_policy": "100pct_n2_all_channels",
            "span_policy": "wizard_authoritative",
        },
    }
    return scenario
