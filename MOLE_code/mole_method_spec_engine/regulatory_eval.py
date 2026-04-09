"""Shared regulatory evaluation for live emissions and mass-rate outputs."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


LBMOL_SCF = 379.482
DEFAULT_HOURS_PER_YEAR = 8760.0
MOLECULAR_WEIGHTS_LB_LBMOL: Dict[str, float] = {
    "CO": 28.010,
    "NO": 30.006,
    "NO2": 46.0055,
    "NOX": 46.0055,
    "VOC": 44.097,
}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _units_key(units: Any) -> str:
    text = str(units or "").strip().lower().replace(" ", "")
    for tok in ("(dry)", "(wet)", "dry", "wet", "vd", "dv", "_"):
        text = text.replace(tok, "")
    return text


def units_is_dry(units: Any) -> bool:
    try:
        u = str(units or "").strip().lower().replace(" ", "")
        if not u:
            return False
        return any(tok in u for tok in ("dry", "vd", "dv", "dscf", "dscm"))
    except Exception:
        return False


def units_is_concentration(units: Any) -> bool:
    try:
        u = str(units or "").strip().lower().replace(" ", "")
        if not u:
            return False
        for bad in (
            "lb",
            "mmbtu",
            "bhp",
            "hp",
            "g/hp",
            "g/bhp",
            "lbhr",
            "lb/hr",
            "scfh",
            "scfm",
            "scfd",
            "acfm",
            "dscf",
            "dscm",
            "tons/yr",
            "tpy",
        ):
            if bad in u:
                return False
        return any(tok in u for tok in ("ppm", "ppb", "%", "pct", "mg/m3", "mgm3", "ug/m3", "µg/m3"))
    except Exception:
        return False


def units_compatible(units_obs: Any, units_lim: Any) -> bool:
    u1 = _units_key(units_obs)
    u2 = _units_key(units_lim)
    if not u1 or not u2:
        return False
    if u1 == u2:
        return True
    if ("ppm" in u1) and ("ppm" in u2):
        return True
    if ("ppb" in u1) and ("ppb" in u2):
        return True
    if ((u1.endswith("%") or "pct" in u1 or "percent" in u1) and (u2.endswith("%") or "pct" in u2 or "percent" in u2)):
        return True
    if (("lb/hr" in u1 or "lbhr" in u1) and ("lb/hr" in u2 or "lbhr" in u2)):
        return True
    if (("g/bhp" in u1 or "gbhp" in u1) and ("g/bhp" in u2 or "gbhp" in u2)):
        return True
    if (("lb/mmbtu" in u1) and ("lb/mmbtu" in u2)):
        return True
    return False


def limit_o2_ref_pct(limit: Any) -> Optional[float]:
    if not isinstance(limit, dict):
        return None
    for key in ("o2_ref_pct", "o2_ref", "o2"):
        value = _safe_float(limit.get(key))
        if value is not None:
            return float(value)
    return None


def normalize_mass_limit_units(units: Any) -> str:
    raw = str(units or "").strip()
    lu = raw.lower().replace(" ", "")
    if lu in ("lb/hr", "lbs/hr", "lbshr", "lbperhr", "lbperhour"):
        return "lb/hr"
    if "g/bhp" in lu:
        return "g/bhp-hr"
    if "lb/mmbtu" in lu:
        return "lb/MMBtu"
    if lu in ("tpy", "tons/year", "tons/yr", "ton/year", "ton/yr", "tonsperyear"):
        return "tons/yr"
    if ("tons" in lu) and ("year" in lu or "yr" in lu):
        return "tons/yr"
    return raw


def is_mass_limit_units(units: Any) -> bool:
    lu = str(units or "").lower().replace(" ", "")
    return any(token in lu for token in ("lb/hr", "lbshr", "g/bhp", "lb/mmbtu", "tpy", "tons/"))


def choose_primary_limit(limits: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for row in list(limits or []):
        if isinstance(row, dict):
            return row
    return None


def choose_mass_limit(limits: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    first = None
    for row in list(limits or []):
        if not isinstance(row, dict):
            continue
        if first is None:
            first = row
        if is_mass_limit_units(row.get("units")):
            return row
    return first


def infer_stack_context(
    o2_meas_pct: Optional[float],
    co2_meas_pct: Optional[float],
    *,
    sim_env: Any = None,
    sim_mode: Any = None,
) -> bool:
    try:
        if str(sim_env or "").strip().upper() == "TRAINING":
            return str(sim_mode or "").strip().upper() == "SAMPLE"
    except Exception:
        pass
    try:
        if o2_meas_pct is not None and float(o2_meas_pct) >= 19.0:
            if co2_meas_pct is None or float(co2_meas_pct) < 0.5:
                return False
    except Exception:
        return True
    return True


def estimate_h2o_wet_frac(
    combustion_model: Dict[str, Any],
    o2_meas_pct: Optional[float] = None,
    co2_meas_pct: Optional[float] = None,
    co_meas_pct: Optional[float] = None,
) -> Optional[float]:
    comb = combustion_model if isinstance(combustion_model, dict) else {}
    wet_fr = comb.get("wet_mol_fracs") if isinstance(comb.get("wet_mol_fracs"), dict) else {}
    dry_fr = comb.get("dry_mol_fracs") if isinstance(comb.get("dry_mol_fracs"), dict) else {}

    base_h2o = _safe_float(wet_fr.get("H2O"))
    if base_h2o is None or base_h2o <= 0 or base_h2o >= 0.95:
        return None

    n_h2o0 = float(base_h2o)
    n_dry0 = 1.0 - n_h2o0
    if n_dry0 <= 1e-9:
        return base_h2o

    k = 4.761

    def _delta_from_o2(o2pct: float) -> Optional[float]:
        try:
            y = max(0.0, min(0.209, float(o2pct) / 100.0))
            denom = 1.0 - y * k
            if denom <= 1e-9:
                return None
            return (y * n_dry0) / denom
        except Exception:
            return None

    def _delta_from_co2(co2pct: float) -> Optional[float]:
        try:
            z = max(1e-6, min(0.25, float(co2pct) / 100.0))
            base_co2_dry = _safe_float(dry_fr.get("CO2"))
            if base_co2_dry is None or base_co2_dry <= 0 or base_co2_dry >= 0.95:
                return None
            n_co2_0 = float(base_co2_dry) * n_dry0
            total_dry = n_co2_0 / z
            delta = (total_dry - n_dry0) / k
            return max(0.0, delta)
        except Exception:
            return None

    d_o2 = _delta_from_o2(o2_meas_pct) if o2_meas_pct is not None else None
    d_co2 = _delta_from_co2(co2_meas_pct) if co2_meas_pct is not None else None

    co_bias = False
    try:
        if co_meas_pct is not None and float(co_meas_pct) >= 0.1:
            co_bias = True
    except Exception:
        pass

    if d_o2 is None and d_co2 is None:
        return base_h2o
    if d_o2 is not None and (d_co2 is None or co_bias):
        delta = d_o2
    elif d_o2 is None and d_co2 is not None:
        delta = d_co2
    else:
        delta = 0.7 * float(d_o2) + 0.3 * float(d_co2)

    wet_total = 1.0 + k * float(delta)
    if wet_total <= 1e-9:
        return base_h2o
    est = n_h2o0 / wet_total
    return max(0.0, min(0.95, est))


def wet_to_dry_factor(h2o_wet_frac: Optional[float]) -> Optional[float]:
    if h2o_wet_frac is None:
        return None
    try:
        frac = float(h2o_wet_frac)
    except Exception:
        return None
    if frac <= 0:
        return 1.0
    if frac >= 0.95:
        return None
    return 1.0 / (1.0 - frac)


def _co_pct_from_observed(value: Optional[float], units: Any) -> Optional[float]:
    if value is None:
        return None
    u = str(units or "").lower()
    try:
        f = float(value)
    except Exception:
        return None
    if "ppb" in u:
        return f / 10_000_000.0
    if "ppm" in u:
        return f / 10_000.0
    return (f / 10_000.0) if f > 1.0 else f


def _normalize_to_ppm(value: Optional[float], units: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        ppm = float(value)
        u = str(units or "").lower().strip()
        if ("%" in u) and ("ppm" not in u) and ("ppb" not in u):
            return ppm * 10000.0
        if "ppb" in u:
            return ppm / 1000.0
        return ppm
    except Exception:
        return None


def _fmt_status_from_pass(pass_value: Optional[bool], *, no_data: str = "NO_DATA", no_basis: str = "(basis)") -> str:
    if pass_value is None:
        return no_data
    return "PASS" if bool(pass_value) else "FAIL"


def evaluate_regulatory_output(
    channel: Any,
    observed: Dict[str, Any],
    limits: Iterable[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ctx = dict(context or {})
    code = str(channel or "").strip().upper()
    limits_list = [row for row in list(limits or []) if isinstance(row, dict)]

    raw_value = _safe_float(observed.get("raw"))
    units = str(observed.get("units") or "").strip()
    raw_is_wet = bool(ctx.get("raw_is_wet", True))
    apply_o2_correction = bool(ctx.get("apply_o2_correction", True))
    default_o2_ref = _safe_float(ctx.get("default_o2_ref"))
    qd_dscfh = _safe_float(ctx.get("qd_dscfh"))
    heat_mmbtu_hr = _safe_float(ctx.get("heat_mmbtu_hr"))
    bhp = _safe_float(ctx.get("bhp"))
    hours_per_year = _safe_float(ctx.get("hours_per_year"))
    if hours_per_year is None or hours_per_year <= 0:
        hours_per_year = DEFAULT_HOURS_PER_YEAR

    o2_meas_pct = _safe_float(ctx.get("o2_meas_pct"))
    co2_meas_pct = _safe_float(ctx.get("co2_meas_pct"))
    co_meas_pct = _safe_float(ctx.get("co_meas_pct"))
    combustion_model = ctx.get("combustion_model") if isinstance(ctx.get("combustion_model"), dict) else {}

    h2o_wet_frac = _safe_float(ctx.get("h2o_wet_frac"))
    if h2o_wet_frac is None:
        h2o_wet_frac = estimate_h2o_wet_frac(combustion_model, o2_meas_pct, co2_meas_pct, co_meas_pct)
    dry_factor = _safe_float(ctx.get("dry_factor"))
    if dry_factor is None:
        dry_factor = wet_to_dry_factor(h2o_wet_frac)

    stack_context = ctx.get("stack_context")
    if stack_context is None:
        stack_context = infer_stack_context(
            o2_meas_pct,
            co2_meas_pct,
            sim_env=ctx.get("sim_env"),
            sim_mode=ctx.get("sim_mode"),
        )
    stack_context = bool(stack_context)

    primary_limit = choose_primary_limit(limits_list)
    mass_limit = choose_mass_limit(limits_list)

    limit_units = str((primary_limit or {}).get("units") or "").strip()
    limit_value = _safe_float((primary_limit or {}).get("value"))
    limit_basis = str((primary_limit or {}).get("basis") or "").strip().upper()
    explicit_limit_o2_ref = limit_o2_ref_pct(primary_limit)
    display_o2_ref = explicit_limit_o2_ref
    if display_o2_ref is None and default_o2_ref is not None and code not in ("O2",):
        display_o2_ref = default_o2_ref

    dry_value = raw_value
    if raw_value is not None:
        if units_is_dry(units) or (not raw_is_wet):
            dry_value = raw_value
        elif dry_factor is not None:
            dry_value = float(raw_value) * float(dry_factor)
        else:
            dry_value = None

    corrected_value = None
    if (
        apply_o2_correction
        and stack_context
        and units_is_concentration(units)
        and dry_value is not None
        and display_o2_ref is not None
        and o2_meas_pct is not None
        and code not in ("O2",)
    ):
        try:
            den = 20.9 - float(o2_meas_pct)
            num = 20.9 - float(display_o2_ref)
            if den > 1e-9 and num > 1e-9:
                corrected_value = float(dry_value) * (num / den)
        except Exception:
            corrected_value = None

    conc_units_ok = bool(units and limit_units and units_compatible(units, limit_units))
    compare_value = None
    compare_source = ""
    if primary_limit and conc_units_ok:
        if explicit_limit_o2_ref is not None and corrected_value is not None:
            compare_value = corrected_value
            compare_source = "O2_CORR"
        elif "DRY" in limit_basis and dry_value is not None:
            compare_value = dry_value
            compare_source = "DRY"
        elif "WET" in limit_basis and raw_value is not None:
            compare_value = raw_value
            compare_source = "RAW"
        elif dry_value is not None:
            compare_value = dry_value
            compare_source = "DRY_PREF"
        elif raw_value is not None:
            compare_value = raw_value
            compare_source = "RAW_FALLBACK"

    conc_pct_limit = None
    conc_pass = None
    conc_status = "NO_LIMIT"
    if primary_limit:
        if not conc_units_ok and limit_units:
            conc_status = "LIMIT_UNITS"
        elif compare_value is None:
            conc_status = "NO_DATA"
        elif limit_value in (None, 0.0):
            conc_status = "NO_LIMIT"
        else:
            try:
                conc_pct_limit = (float(compare_value) / float(limit_value)) * 100.0
                conc_pass = float(compare_value) <= float(limit_value)
                conc_status = _fmt_status_from_pass(conc_pass)
            except Exception:
                conc_pct_limit = None
                conc_pass = None
                conc_status = "ERROR"

    mw = _safe_float((ctx.get("molecular_weights") or {}).get(code)) if isinstance(ctx.get("molecular_weights"), dict) else None
    if mw is None:
        mw = MOLECULAR_WEIGHTS_LB_LBMOL.get(code)

    ppm_input_source = "RAW"
    ppm_input_value = raw_value
    if corrected_value is not None:
        ppm_input_source = "CORR"
        ppm_input_value = corrected_value
    elif dry_value is not None:
        ppm_input_source = "DRY"
        ppm_input_value = dry_value
    ppm_input = _normalize_to_ppm(ppm_input_value, units)

    raw_lb_hr = None
    lbmol_per_hr = None
    if qd_dscfh is not None and qd_dscfh > 0:
        lbmol_per_hr = float(qd_dscfh) / LBMOL_SCF
    if ppm_input is not None and lbmol_per_hr is not None and mw is not None:
        raw_lb_hr = float(ppm_input) * 1e-6 * float(lbmol_per_hr) * float(mw)

    mass_limit_value = _safe_float((mass_limit or {}).get("value"))
    mass_limit_units = normalize_mass_limit_units((mass_limit or {}).get("units") or "")
    mass_display_value = raw_lb_hr
    mass_display_units = "lb/hr" if raw_lb_hr is not None else ""
    mass_pct_limit = None
    mass_pass = None
    mass_status = "NO_DATA"
    mass_basis_ok = True

    if mass_limit is None:
        mass_status = "NO_LIMIT"
    elif raw_lb_hr is None:
        mass_status = "NO_DATA"
    else:
        lu = mass_limit_units.lower().replace(" ", "")
        try:
            if lu in ("lb/hr", "lbs/hr", "lbshr", "lbperhr", "lbperhour"):
                mass_display_value = raw_lb_hr
                mass_display_units = "lb/hr"
            elif "g/bhp" in lu:
                if bhp is not None and bhp > 0:
                    mass_display_value = (float(raw_lb_hr) * 453.59237) / float(bhp)
                    mass_display_units = "g/bhp-hr"
                else:
                    mass_basis_ok = False
            elif "lb/mmbtu" in lu:
                if heat_mmbtu_hr is not None and heat_mmbtu_hr > 0:
                    mass_display_value = float(raw_lb_hr) / float(heat_mmbtu_hr)
                    mass_display_units = "lb/MMBtu"
                else:
                    mass_basis_ok = False
            elif ("tpy" in lu) or ("tons/yr" in lu) or (("tons" in lu) and ("yr" in lu or "year" in lu)):
                mass_display_value = (float(raw_lb_hr) * float(hours_per_year)) / 2000.0
                mass_display_units = "tons/yr"
            else:
                mass_basis_ok = False

            if not mass_basis_ok:
                mass_status = "(basis)"
            elif mass_limit_value in (None, 0.0):
                mass_status = "NO_LIMIT"
            else:
                mass_pct_limit = (float(mass_display_value) / float(mass_limit_value)) * 100.0
                mass_pass = float(mass_display_value) <= float(mass_limit_value)
                mass_status = _fmt_status_from_pass(mass_pass)
        except Exception:
            mass_status = "ERROR"
            mass_pass = None

    return {
        "channel": code,
        "views": {
            "raw": raw_value,
            "dry": dry_value,
            "corrected": corrected_value,
            "units": units,
            "o2_ref": display_o2_ref,
            "explicit_limit_o2_ref": explicit_limit_o2_ref,
            "h2o_wet_frac": h2o_wet_frac,
            "dry_factor": dry_factor,
            "stack_context": stack_context,
        },
        "limits": {
            "primary": dict(primary_limit or {}),
            "mass": dict(mass_limit or {}),
        },
        "concentration": {
            "limit_value": limit_value,
            "limit_units": limit_units,
            "basis": limit_basis,
            "units_compatible": conc_units_ok,
            "compare_value": compare_value,
            "compare_source": compare_source,
            "pct_limit": conc_pct_limit,
            "pass": conc_pass,
            "status": conc_status,
        },
        "mass": {
            "ppm_input": ppm_input,
            "ppm_input_source": ppm_input_source,
            "lbmol_per_hr": lbmol_per_hr,
            "raw_lb_hr": raw_lb_hr,
            "display_value": mass_display_value,
            "display_units": mass_display_units,
            "limit_value": mass_limit_value,
            "limit_units": mass_limit_units,
            "pct_limit": mass_pct_limit,
            "pass": mass_pass,
            "status": mass_status,
            "basis_ok": mass_basis_ok,
            "hours_per_year": hours_per_year,
        },
    }
