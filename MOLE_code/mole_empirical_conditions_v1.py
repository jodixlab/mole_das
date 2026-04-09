"""Empirical Conditions Registry (v1)

Provides a lightweight, editable registry of formulas/constants used across MOLE-DAS.
- Stored as JSON (grouped by category)
- Supports user override values per formula
- Provides safe evaluation for suggested values (math-only)
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Optional

SAFE_FUNCS = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
SAFE_FUNCS.update({"abs": abs, "min": min, "max": max, "round": round})

def load_registry(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"version": 1, "constants": {}, "formulas": []}
    return json.loads(p.read_text(encoding="utf-8"))

def save_registry(path: str | Path, reg: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(reg, indent=2, sort_keys=False), encoding="utf-8")

def eval_expr(expr: str, variables: Dict[str, Any]) -> Optional[float]:
    if not expr or not isinstance(expr, str):
        return None
    env: Dict[str, Any] = {}
    env.update(SAFE_FUNCS)
    # vars
    for k, v in (variables or {}).items():
        try:
            env[k] = float(v)
        except Exception:
            env[k] = v
    try:
        val = eval(expr, {"__builtins__": {}}, env)  # noqa: S307
        try:
            return float(val)
        except Exception:
            return None
    except Exception:
        return None

def applied_value(formula: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
    """Return dict with suggested/applied values."""
    expr = str(formula.get("expr") or "").strip()
    suggested = eval_expr(expr, variables) if expr else None
    ov_en = bool(formula.get("override_enabled"))
    ov_val = formula.get("override_value")
    applied = None
    if ov_en and ov_val not in (None, ""):
        try:
            applied = float(ov_val)
        except Exception:
            applied = suggested
    else:
        applied = suggested
    return {"suggested": suggested, "applied": applied}

def get_formula(reg: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    for f in (reg.get("formulas") or []):
        if str(f.get("key")) == str(key):
            return f
    return None
