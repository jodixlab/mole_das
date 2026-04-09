"""Pure Method 19 helper calculations used by the runner and validation tests."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def method19_o2_factor(o2_dry_pct: Optional[float]) -> Optional[float]:
    if o2_dry_pct is None:
        return None
    try:
        o2 = float(o2_dry_pct)
    except Exception:
        return None
    if o2 < 0:
        o2 = 0.0
    if o2 >= 20.9:
        return None
    denom = 20.9 - o2
    if denom <= 1e-9:
        return None
    return 20.9 / denom


def method19_pick_fd(comb: Dict[str, Any]) -> Optional[float]:
    if not isinstance(comb, dict):
        return None
    for key in ("F_selected", "Fd_sel_dscf_per_MMBtu", "F_HHV", "Fd_HHV_dscf_per_MMBtu"):
        value = _safe_float(comb.get(key))
        if value is not None and value > 0:
            return float(value)
    return None


def method19_pick_heat_value(comb: Dict[str, Any], kind: Optional[str]) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """Return (heating value, base kind, basis code) aligned to the selected F-factor basis."""
    if not isinstance(comb, dict):
        return None, None, None

    basis = str(comb.get("basis_sel") or "HHV").strip().upper()
    value_key_map = {
        "HHV": {
            "scf": "HHV_Btu_scf",
            "gal": "HHV_Btu_gal",
            "lb": "HHV_Btu_lb",
        },
        "LHV": {
            "scf": "LHV_Btu_scf",
            "gal": "LHV_Btu_gal",
            "lb": "LHV_Btu_lb",
        },
    }

    requested = value_key_map.get(basis) or value_key_map["HHV"]
    opposite_basis = "LHV" if basis == "HHV" else "HHV"
    opposite = value_key_map.get(opposite_basis) or {}

    if kind in requested:
        value = _safe_float(comb.get(requested[kind]))
        if value is not None and value > 0:
            return float(value), kind, basis
        value = _safe_float(comb.get(opposite.get(kind)))
        if value is not None and value > 0:
            return float(value), kind, opposite_basis

    family = str(comb.get("family") or "").strip().upper()
    if family in ("GAS", "NG", "NATURAL_GAS"):
        value = _safe_float(comb.get(requested["scf"]))
        if value is not None and value > 0:
            return float(value), "scf", basis
    if family in ("LIQUID", "OIL", "DIESEL", "GASOLINE"):
        value = _safe_float(comb.get(requested["gal"]))
        if value is not None and value > 0:
            return float(value), "gal", basis

    fallbacks = (
        (requested["scf"], "scf"),
        (requested["gal"], "gal"),
        (requested["lb"], "lb"),
        (opposite.get("scf"), "scf"),
        (opposite.get("gal"), "gal"),
        (opposite.get("lb"), "lb"),
    )
    for key, chosen_kind in fallbacks:
        if not key:
            continue
        value = _safe_float(comb.get(key))
        if value is not None and value > 0:
            use_basis = basis if key in requested.values() else opposite_basis
            return float(value), chosen_kind, use_basis
    return None, None, None


def method19_heat_input_from_fuel_flow(rate_per_hr: Optional[float], heating_value_btu_per_unit: Optional[float]) -> Optional[float]:
    try:
        if rate_per_hr is None or heating_value_btu_per_unit is None:
            return None
        rate = float(rate_per_hr)
        heating_value = float(heating_value_btu_per_unit)
        if rate <= 0 or heating_value <= 0:
            return None
        return (rate * heating_value) / 1_000_000.0
    except Exception:
        return None


def method19_qd_from_heat_input(
    heat_input_mmbtu_hr: Optional[float],
    fd_dscf_per_mmbtu: Optional[float],
    *,
    o2_dry_pct: Optional[float] = None,
    o2_factor: Optional[float] = None,
) -> Optional[float]:
    try:
        heat_input = float(heat_input_mmbtu_hr) if heat_input_mmbtu_hr is not None else None
        fd = float(fd_dscf_per_mmbtu) if fd_dscf_per_mmbtu is not None else None
        fac = float(o2_factor) if o2_factor is not None else method19_o2_factor(o2_dry_pct)
        if heat_input is None or fd is None or fac is None:
            return None
        if heat_input <= 0 or fd <= 0 or fac <= 0:
            return None
        return heat_input * fd * fac
    except Exception:
        return None


def method19_heat_input_from_qd(
    qd_dscfh: Optional[float],
    fd_dscf_per_mmbtu: Optional[float],
    *,
    o2_dry_pct: Optional[float] = None,
    o2_factor: Optional[float] = None,
) -> Optional[float]:
    try:
        qd = float(qd_dscfh) if qd_dscfh is not None else None
        fd = float(fd_dscf_per_mmbtu) if fd_dscf_per_mmbtu is not None else None
        fac = float(o2_factor) if o2_factor is not None else method19_o2_factor(o2_dry_pct)
        if qd is None or fd is None or fac is None:
            return None
        denom = fd * fac
        if qd <= 0 or denom <= 0:
            return None
        return qd / denom
    except Exception:
        return None


def method19_fuel_flow_from_heat_input(
    heat_input_mmbtu_hr: Optional[float],
    heating_value_btu_per_unit: Optional[float],
) -> Optional[float]:
    try:
        heat_input = float(heat_input_mmbtu_hr) if heat_input_mmbtu_hr is not None else None
        heating_value = float(heating_value_btu_per_unit) if heating_value_btu_per_unit is not None else None
        if heat_input is None or heating_value is None:
            return None
        if heat_input <= 0 or heating_value <= 0:
            return None
        return (heat_input * 1_000_000.0) / heating_value
    except Exception:
        return None


def dual_fuel_normalize_liquid_share_pct(value: Any) -> float:
    share_pct = _safe_float(value)
    if share_pct is None:
        return 0.0
    return max(0.0, min(100.0, float(share_pct)))


def dual_fuel_basis_shares(
    *,
    liquid_share_pct_selected: Any,
    basis_sel: Any,
    gas_hhv: Any,
    gas_lhv: Any,
    liquid_hhv: Any,
    liquid_lhv: Any,
) -> Dict[str, float]:
    """Return gas/liquid selected-basis and converted HHV/LHV energy-share fractions."""
    liquid_sel = dual_fuel_normalize_liquid_share_pct(liquid_share_pct_selected) / 100.0
    gas_sel = 1.0 - liquid_sel
    basis = str(basis_sel or "HHV").strip().upper() or "HHV"

    gas_hhv_v = _safe_float(gas_hhv)
    gas_lhv_v = _safe_float(gas_lhv)
    liquid_hhv_v = _safe_float(liquid_hhv)
    liquid_lhv_v = _safe_float(liquid_lhv)

    def _convert(liquid_share_from: float, gas_factor: Optional[float], liquid_factor: Optional[float]) -> float:
        gas_share_from = 1.0 - liquid_share_from
        if gas_factor is None or liquid_factor is None or gas_factor <= 0 or liquid_factor <= 0:
            return liquid_share_from
        gas_energy = gas_share_from * gas_factor
        liquid_energy = liquid_share_from * liquid_factor
        total = gas_energy + liquid_energy
        if total <= 1e-12:
            return liquid_share_from
        return liquid_energy / total

    if basis == "LHV":
        gas_factor_to_hhv = (gas_hhv_v / gas_lhv_v) if gas_hhv_v and gas_lhv_v else None
        liquid_factor_to_hhv = (liquid_hhv_v / liquid_lhv_v) if liquid_hhv_v and liquid_lhv_v else None
        liquid_hhv_share = _convert(liquid_sel, gas_factor_to_hhv, liquid_factor_to_hhv)
        liquid_lhv_share = liquid_sel
    else:
        gas_factor_to_lhv = (gas_lhv_v / gas_hhv_v) if gas_hhv_v and gas_lhv_v else None
        liquid_factor_to_lhv = (liquid_lhv_v / liquid_hhv_v) if liquid_hhv_v and liquid_lhv_v else None
        liquid_hhv_share = liquid_sel
        liquid_lhv_share = _convert(liquid_sel, gas_factor_to_lhv, liquid_factor_to_lhv)

    return {
        "basis_sel": "LHV" if basis == "LHV" else "HHV",
        "liquid_sel": liquid_sel,
        "gas_sel": 1.0 - liquid_sel,
        "liquid_hhv": liquid_hhv_share,
        "gas_hhv": 1.0 - liquid_hhv_share,
        "liquid_lhv": liquid_lhv_share,
        "gas_lhv": 1.0 - liquid_lhv_share,
    }
