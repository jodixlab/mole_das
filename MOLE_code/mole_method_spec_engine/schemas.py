"""Shared schemas for the starter method/spec engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


SPEC_ENGINE_FORMULA_VERSION = "spec_engine_v1"


def normalize_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def normalize_step(value: Any) -> str:
    raw = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "POSTZERO": "POST_ZERO",
        "POSTSPAN": "POST_SPAN",
    }
    return aliases.get(raw, raw or "UNKNOWN")


def values_from_series(value_series: Any) -> List[float]:
    values: List[float] = []
    if not isinstance(value_series, list):
        return values
    for item in value_series:
        if isinstance(item, (int, float)):
            values.append(float(item))
            continue
        if isinstance(item, (list, tuple)) and item:
            cand = item[-1]
            fv = normalize_float(cand)
            if fv is not None:
                values.append(float(fv))
            continue
        if isinstance(item, dict):
            for key in ("value", "meas", "avg"):
                fv = normalize_float(item.get(key))
                if fv is not None:
                    values.append(float(fv))
                    break
    return values


@dataclass
class StepEvaluation:
    step: str
    basis: str
    target: Optional[float]
    tolerance: Optional[float]
    avg: Optional[float]
    std: Optional[float]
    n: int
    stability_range: Optional[float]
    stability_threshold: Optional[float]
    stable: bool
    within_tolerance: Optional[bool]
    pass_: bool
    status: str
    reason: str
    comparison_value: Optional[float] = None
    recovery_pct: Optional[float] = None
    units_hint: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["pass"] = out.pop("pass_")
        return out


@dataclass
class EvidenceRecord:
    event: str
    step: str
    channel: str
    timestamp: str
    formula_version: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
