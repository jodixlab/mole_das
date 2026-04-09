"""Starter method-profile registry.

This is intentionally small for the first rollout. It gives the spec engine
one place to answer method/profile questions without forcing a large rewrite.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _norm(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


_PROFILES: List[Dict[str, Any]] = [
    {
        "profile_id": "ENGINE_SI_RICE_JJJJ_NG",
        "match": {
            "source_type": "ENGINE",
            "fuel_type": "NATURAL_GAS",
            "duty_type": "RICE",
            "regulation": "SUBPART_JJJJ",
        },
        "o2_reference_pct": 15.0,
        "supported_bases": ["PPMVD_O2_CORR", "G_BHP_HR", "LB_MMBTU", "LB_HR", "TPY"],
        "required_channels": ["O2"],
        "required_inputs": ["brake_horsepower", "fuel_flow"],
        "cal_sequence": ["ZERO", "MID", "SPAN", "SAMPLE", "POST_ZERO", "POST_SPAN"],
        "post_cal_required": True,
    },
    {
        "profile_id": "GENERIC_FTIR_AUDIT",
        "match": {
            "source_type": "GENERIC",
            "fuel_type": "",
            "duty_type": "",
            "regulation": "",
        },
        "o2_reference_pct": None,
        "supported_bases": ["PPMVD_O2_CORR", "LB_HR"],
        "required_channels": [],
        "required_inputs": [],
        "cal_sequence": ["ZERO", "SPAN", "SAMPLE", "POST_ZERO", "POST_SPAN"],
        "post_cal_required": True,
    },
]


def get_method_profile(source_type: Any, fuel_type: Any, duty_type: Any, regulation: Any) -> Dict[str, Any]:
    wanted = {
        "source_type": _norm(source_type),
        "fuel_type": _norm(fuel_type),
        "duty_type": _norm(duty_type),
        "regulation": _norm(regulation),
    }
    best = None
    best_score = -1
    for profile in _PROFILES:
        score = 0
        for key, val in (profile.get("match") or {}).items():
            want = wanted.get(key, "")
            have = _norm(val)
            if not have:
                continue
            if have == want:
                score += 2
            elif have == "GENERIC":
                score += 1
        if score > best_score:
            best = profile
            best_score = score
    return dict(best or _PROFILES[-1])
