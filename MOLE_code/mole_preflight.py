"""MOLE Preflight (v10.0.24C)

Purpose
-------
Provide a single, deterministic integrity check for runtime-ready packages so the app
doesn't "sort of start" and then fail later due to missing assets/modules/config keys.

This module is intentionally stdlib-only.

Usage (wizard/runner)
---------------------
from mole_preflight import run_preflight, format_preflight_report
pf = run_preflight(app="wizard", code_dir=Path(__file__).resolve().parent)
if pf["errors"]:
    ... block and show dialog ...
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _utc_iso(ts: Optional[float] = None) -> str:
    dt = datetime.fromtimestamp(ts or time.time(), tz=timezone.utc)
    return dt.isoformat()


def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _find_root_from_code_dir(code_dir: Path) -> Path:
    """Find _fixpkg root (contains mole_assets + mole_das_data)."""
    cd = code_dir.resolve()
    # typical layout: <root>/_fixpkg/MOLE_code/<this_file>
    # so root candidate = cd.parent
    candidates = [
        cd.parent,
        cd.parent.parent,
        cd.parent.parent.parent,
    ]
    for c in candidates:
        if (c / "mole_assets" / "ASSET_MANIFEST.json").exists() and (c / "mole_das_data").exists():
            return c
    # fallback: search upwards
    cur = cd
    for _ in range(8):
        if (cur / "mole_assets" / "ASSET_MANIFEST.json").exists() and (cur / "mole_das_data").exists():
            return cur
        cur = cur.parent
    return cd.parent


def _safe_json_load(path: Path) -> Tuple[Optional[dict], Optional[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def run_preflight(*, app: str, code_dir: Path, strict_hash: bool = False) -> Dict[str, Any]:
    """Run a package integrity check.

    Returns dict:
      { "ok": bool, "errors": [..], "warnings": [..], "info": {...}, "log_path": str|None }
    """
    t0 = time.time()
    code_dir = code_dir.resolve()
    root = _find_root_from_code_dir(code_dir)
    info: Dict[str, Any] = {
        "app": app,
        "utc": _utc_iso(),
        "code_dir": str(code_dir),
        "root_dir": str(root),
        "python": sys.version.split()[0],
        "exe": sys.executable,
        "cwd": os.getcwd(),
    }
    errors: List[str] = []
    warnings: List[str] = []

    # --- required directories
    assets_manifest = root / "mole_assets" / "ASSET_MANIFEST.json"
    if not assets_manifest.exists():
        errors.append(f"Missing asset manifest: {assets_manifest}")
    if not (root / "mole_das_data").exists():
        errors.append(f"Missing mole_das_data folder: {root / 'mole_das_data'}")

    # --- config existence
    cfg_path = root / "mole_config.json"
    if not cfg_path.exists():
        warnings.append(f"mole_config.json not found at expected path: {cfg_path}")
    else:
        cfg, err = _safe_json_load(cfg_path)
        if err:
            errors.append(f"Invalid mole_config.json: {err}")
        else:
            sv = (cfg or {}).get("schema_version")
            if not sv:
                warnings.append("mole_config.json missing schema_version (migration recommended).")
            rel = (cfg or {}).get("release") or {}
            info["release"] = {
                "name": rel.get("name"),
                "version": rel.get("version"),
                "build": rel.get("build") or rel.get("build_date") or rel.get("built_utc"),
                "channel": rel.get("channel"),
            }

    # --- verify assets
    if assets_manifest.exists():
        man, err = _safe_json_load(assets_manifest)
        if err:
            errors.append(f"Invalid ASSET_MANIFEST.json: {err}")
        else:
            assets = (man or {}).get("assets") or []
            info["asset_count"] = len(assets)
            for a in assets:
                try:
                    rel_path = str(a.get("path") or "").strip()
                    if not rel_path:
                        continue
                    ap = root / rel_path
                    if not ap.exists():
                        errors.append(f"Missing asset: {rel_path}")
                        continue
                    expected_bytes = a.get("bytes")
                    if expected_bytes and ap.stat().st_size != int(expected_bytes):
                        warnings.append(f"Asset size mismatch: {rel_path} (expected {expected_bytes}, got {ap.stat().st_size})")
                    expected_sha = str(a.get("sha256") or "").strip().lower()
                    if strict_hash and expected_sha:
                        got = _sha256_file(ap)
                        if got.lower() != expected_sha:
                            errors.append(f"Asset hash mismatch: {rel_path}")
                except Exception as e:
                    warnings.append(f"Asset check failed: {a} ({type(e).__name__}: {e})")

    # --- key module presence (common regression)
    must_have = [
        "mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py",
        "mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py",
        "mole_soundtrack.py",
        "mole_site_map_widget_v1.py",
        "mole_empirical_conditions_v1.py",
    ]
    for name in must_have:
        p = code_dir / name
        if not p.exists():
            errors.append(f"Missing required module: MOLE_code/{name}")

    ok = (len(errors) == 0)
    info["elapsed_ms"] = int((time.time() - t0) * 1000)

    # --- write log
    log_path = None
    try:
        logs_dir = root / "mole_das_data" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / f"mole_preflight_{app}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        log_path.write_text(json.dumps({
            "ok": ok,
            "errors": errors,
            "warnings": warnings,
            "info": info,
        }, indent=2), encoding="utf-8")
    except Exception:
        log_path = None

    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "log_path": str(log_path) if log_path else None,
    }


def format_preflight_report(pf: Dict[str, Any], *, max_lines: int = 40) -> str:
    errs = pf.get("errors") or []
    warns = pf.get("warnings") or []
    info = pf.get("info") or {}
    lines: List[str] = []
    lines.append(f"MOLE Preflight — {info.get('app')}  (UTC: {info.get('utc')})")
    lines.append(f"Python: {info.get('python')}  |  CWD: {info.get('cwd')}")
    lines.append(f"Code: {info.get('code_dir')}")
    lines.append(f"Root: {info.get('root_dir')}")
    rel = info.get('release') or {}
    if rel:
        lines.append(f"Release: {rel.get('version')}  {rel.get('channel')}  {rel.get('name')}")
    lines.append("")
    if errs:
        lines.append(f"ERRORS ({len(errs)}):")
        for e in errs[:max_lines]:
            lines.append(f"  - {e}")
    if warns:
        if errs:
            lines.append("")
        lines.append(f"WARNINGS ({len(warns)}):")
        for w in warns[:max_lines]:
            lines.append(f"  - {w}")
    if not errs and not warns:
        lines.append("OK: No issues detected.")
    lp = pf.get("log_path")
    if lp:
        lines.append("")
        lines.append(f"Log: {lp}")
    return "\n".join(lines)
