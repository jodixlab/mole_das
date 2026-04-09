"""Traceable FTIR offset recommendation helpers.

This module keeps FTIR bias-correction recommendations separate from hardware
channel calibration. Recommendations are derived from captured MOLE-vs-FTIR
comparisons, written into report-pack artifacts, and optionally promoted into a
global carry-forward store for future projects.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_PROJECT_POLICY: Dict[str, Any] = {
    "use_global": False,
    "promote_latest_for_future_projects": False,
}

DEFAULT_STORE: Dict[str, Any] = {
    "version": 1,
    "updated_iso": "",
    "auto_apply_future_projects": False,
    "active_set_id": "",
    "sets": [],
}

_STORE_CACHE: Dict[str, Any] = {
    "path": "",
    "mtime_ns": None,
    "store": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _clone_jsonable(obj: Any) -> Any:
    try:
        return json.loads(json.dumps(obj))
    except Exception:
        return obj


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def default_store_path() -> Path:
    return (Path(__file__).resolve().parent.parent / "mole_das_data" / "configs" / "ftir_offset_recommendations.json").resolve()


def normalize_project_policy(cfg: Any, default_use_global: Optional[bool] = None) -> Dict[str, Any]:
    out = dict(DEFAULT_PROJECT_POLICY)
    if default_use_global is not None:
        out["use_global"] = bool(default_use_global)
    if isinstance(cfg, dict):
        if cfg.get("use_global") is not None:
            out["use_global"] = bool(cfg.get("use_global"))
        out["promote_latest_for_future_projects"] = bool(cfg.get("promote_latest_for_future_projects"))
    return out


def _normalize_set(item: Any, active_set_id: str = "") -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None

    set_id = str(item.get("set_id") or "").strip()
    if not set_id:
        return None

    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    report = item.get("report") if isinstance(item.get("report"), dict) else {}
    eligibility = item.get("eligibility") if isinstance(item.get("eligibility"), dict) else {}
    channels_in = item.get("channels") if isinstance(item.get("channels"), dict) else {}

    channels_out: Dict[str, Dict[str, Any]] = {}
    for code, spec in channels_in.items():
        if not isinstance(spec, dict):
            continue
        canon = str(code or "").strip().upper()
        if not canon:
            continue
        channels_out[canon] = {
            "pollutant": canon,
            "units": str(spec.get("units") or "").strip(),
            "recommended_offset": _safe_float(spec.get("recommended_offset")),
            "recommended_scale": _safe_float(spec.get("recommended_scale")) if spec.get("recommended_scale") not in (None, "") else 1.0,
            "delta_avg": _safe_float(spec.get("delta_avg")),
            "abs_delta_avg": _safe_float(spec.get("abs_delta_avg")),
            "delta_count": int(spec.get("delta_count") or 0),
            "reference_count": int(spec.get("reference_count") or 0),
            "latest_delta": _safe_float(spec.get("latest_delta")),
            "latest_status": str(spec.get("latest_status") or "").strip(),
            "pass_count": int(spec.get("pass_count") or 0),
            "fail_count": int(spec.get("fail_count") or 0),
            "unknown_count": int(spec.get("unknown_count") or 0),
            "basis": _clone_jsonable(spec.get("basis") if isinstance(spec.get("basis"), dict) else {}),
        }

    status = str(item.get("status") or "").strip().upper()
    if status not in ("PROPOSED", "APPROVED", "RETIRED"):
        status = "APPROVED" if set_id and set_id == active_set_id else "PROPOSED"

    return {
        "set_id": set_id,
        "generated_iso": str(item.get("generated_iso") or ""),
        "status": status,
        "eligible_for_promotion": bool(item.get("eligible_for_promotion")),
        "channel_count": int(item.get("channel_count") or len(channels_out)),
        "formula": str(item.get("formula") or "corrected = measured + recommended_offset"),
        "source": {
            "job_id": str(source.get("job_id") or ""),
            "run_id": str(source.get("run_id") or ""),
            "session_dir": str(source.get("session_dir") or ""),
            "config_path": str(source.get("config_path") or ""),
            "config_sha256": str(source.get("config_sha256") or ""),
            "reference_mode": str(source.get("reference_mode") or ""),
            "captured_record_count": int(source.get("captured_record_count") or 0),
            "reference_source_path": str(source.get("reference_source_path") or ""),
            "reference_source_sha256": str(source.get("reference_source_sha256") or ""),
        },
        "report": {
            "report_pack_dir": str(report.get("report_pack_dir") or ""),
            "summary_json": str(report.get("summary_json") or ""),
            "offsets_json": str(report.get("offsets_json") or ""),
            "offsets_csv": str(report.get("offsets_csv") or ""),
        },
        "eligibility": {
            "captured_evidence_required": bool(eligibility.get("captured_evidence_required", True)),
            "reference_mode": str(eligibility.get("reference_mode") or ""),
            "captured_record_count": int(eligibility.get("captured_record_count") or 0),
            "has_channels": bool(eligibility.get("has_channels", bool(channels_out))),
            "reason": str(eligibility.get("reason") or ""),
        },
        "channels": channels_out,
    }


def normalize_store(store: Any) -> Dict[str, Any]:
    out = dict(DEFAULT_STORE)
    if isinstance(store, dict):
        out.update(store)

    out["version"] = 1
    out["updated_iso"] = str(out.get("updated_iso") or "")
    out["auto_apply_future_projects"] = bool(out.get("auto_apply_future_projects"))
    active_set_id = str(out.get("active_set_id") or "").strip()
    out["active_set_id"] = active_set_id

    sets_out: List[Dict[str, Any]] = []
    for item in out.get("sets") or []:
        norm = _normalize_set(item, active_set_id=active_set_id)
        if norm is not None:
            sets_out.append(norm)

    if active_set_id and not any(str(item.get("set_id") or "") == active_set_id for item in sets_out):
        out["active_set_id"] = ""

    out["sets"] = sets_out
    return out


def load_store(path: Optional[Path] = None) -> Dict[str, Any]:
    store_path = Path(path or default_store_path()).expanduser().resolve()
    try:
        mtime_ns = store_path.stat().st_mtime_ns if store_path.exists() else None
    except Exception:
        mtime_ns = None

    if (
        _STORE_CACHE.get("path") == str(store_path)
        and _STORE_CACHE.get("mtime_ns") == mtime_ns
        and isinstance(_STORE_CACHE.get("store"), dict)
    ):
        return _clone_jsonable(_STORE_CACHE["store"])

    if not store_path.exists():
        store = normalize_store({})
        _STORE_CACHE["path"] = str(store_path)
        _STORE_CACHE["mtime_ns"] = None
        _STORE_CACHE["store"] = _clone_jsonable(store)
        return store

    try:
        raw = json.loads(store_path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    store = normalize_store(raw)
    _STORE_CACHE["path"] = str(store_path)
    _STORE_CACHE["mtime_ns"] = mtime_ns
    _STORE_CACHE["store"] = _clone_jsonable(store)
    return store


def save_store(store: Dict[str, Any], path: Optional[Path] = None) -> Path:
    store_path = Path(path or default_store_path()).expanduser().resolve()
    store_path.parent.mkdir(parents=True, exist_ok=True)
    payload = normalize_store(store)
    payload["updated_iso"] = _now_iso()
    store_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        mtime_ns = store_path.stat().st_mtime_ns
    except Exception:
        mtime_ns = None
    _STORE_CACHE["path"] = str(store_path)
    _STORE_CACHE["mtime_ns"] = mtime_ns
    _STORE_CACHE["store"] = _clone_jsonable(payload)
    return store_path


def get_active_set(store: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    norm = normalize_store(store)
    active_id = str(norm.get("active_set_id") or "").strip()
    if active_id:
        for item in norm.get("sets") or []:
            if str(item.get("set_id") or "") == active_id:
                return item
    approved = [item for item in norm.get("sets") or [] if str(item.get("status") or "").strip().upper() == "APPROVED"]
    if approved:
        return approved[-1]
    return None


def summarize_store(store: Dict[str, Any]) -> Dict[str, Any]:
    norm = normalize_store(store)
    active = get_active_set(norm)
    return {
        "path": str(default_store_path()),
        "exists": bool(norm.get("sets")),
        "auto_apply_future_projects": bool(norm.get("auto_apply_future_projects")),
        "active_set_id": str((active or {}).get("set_id") or ""),
        "active_channel_count": int((active or {}).get("channel_count") or 0),
        "active_generated_iso": str((active or {}).get("generated_iso") or ""),
    }


def active_channel_map(store: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    active = get_active_set(store)
    if not isinstance(active, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for code, spec in ((active.get("channels") or {}) if isinstance(active.get("channels"), dict) else {}).items():
        if not isinstance(spec, dict):
            continue
        canon = str(code or "").strip().upper()
        if not canon:
            continue
        out[canon] = {
            "offset": _safe_float(spec.get("recommended_offset")) or 0.0,
            "scale": _safe_float(spec.get("recommended_scale")) or 1.0,
            "units": str(spec.get("units") or "").strip(),
            "set_id": str(active.get("set_id") or ""),
            "generated_iso": str(active.get("generated_iso") or ""),
        }
    return out


def derive_recommendation_set(
    session: Dict[str, Any],
    reference_summary: Dict[str, Any],
    trace_rows: List[Dict[str, Any]],
    report_pack_dir: Optional[Path] = None,
    session_dir: Optional[Path] = None,
    cfg_path: Optional[Path] = None,
) -> Dict[str, Any]:
    evidence = reference_summary.get("evidence") if isinstance(reference_summary.get("evidence"), dict) else {}
    latest = reference_summary.get("latest") if isinstance(reference_summary.get("latest"), dict) else {}
    per_poll = reference_summary.get("per_pollutant") if isinstance(reference_summary.get("per_pollutant"), dict) else {}
    project = session.get("project") if isinstance(session.get("project"), dict) else {}

    captured_record_count = int(evidence.get("captured_record_count") or 0)
    reference_mode = str(evidence.get("mode") or "").strip().lower()
    channels: Dict[str, Dict[str, Any]] = {}

    for code, rec in sorted(per_poll.items()):
        if not isinstance(rec, dict):
            continue
        canon = str(code or "").strip().upper()
        if not canon:
            continue
        delta_count = int(rec.get("delta_count") or 0)
        delta_avg = _safe_float(rec.get("delta_avg"))
        if delta_count <= 0 or delta_avg is None:
            continue
        acc = rec.get("acceptance") if isinstance(rec.get("acceptance"), dict) else {}
        basis = acc.get("basis") if isinstance(acc.get("basis"), dict) else {}
        channels[canon] = {
            "pollutant": canon,
            "units": str(rec.get("units") or "").strip(),
            "recommended_offset": -float(delta_avg),
            "recommended_scale": 1.0,
            "delta_avg": delta_avg,
            "abs_delta_avg": _safe_float(rec.get("abs_delta_avg")),
            "delta_count": delta_count,
            "reference_count": int(rec.get("reference_count") or 0),
            "latest_delta": _safe_float(acc.get("latest_delta")),
            "latest_status": str(acc.get("latest_status") or "").strip(),
            "pass_count": int(acc.get("pass_count") or 0),
            "fail_count": int(acc.get("fail_count") or 0),
            "unknown_count": int(acc.get("unknown_count") or 0),
            "basis": _clone_jsonable(basis),
        }

    eligible = bool(reference_mode == "captured" and captured_record_count > 0 and channels)
    reason = "ready"
    if reference_mode != "captured":
        reason = "captured_reference_evidence_required"
    elif captured_record_count <= 0:
        reason = "captured_reference_evidence_missing"
    elif not channels:
        reason = "no_offsetable_channels"

    now_token = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    set_id = f"FTIR_OFFSETS_{now_token}"

    config_sha256 = ""
    if cfg_path:
        try:
            cfg_res = Path(cfg_path).expanduser().resolve()
            if cfg_res.exists():
                config_sha256 = _sha256_file(cfg_res)
        except Exception:
            config_sha256 = ""

    trace_count = 0
    try:
        trace_count = len([row for row in trace_rows if isinstance(row, dict)])
    except Exception:
        trace_count = 0

    return {
        "set_id": set_id,
        "generated_iso": _now_iso(),
        "status": "PROPOSED",
        "eligible_for_promotion": eligible,
        "channel_count": len(channels),
        "formula": "corrected = measured + recommended_offset",
        "source": {
            "job_id": str(project.get("job_id") or ""),
            "run_id": str(session.get("run_id") or ""),
            "session_dir": str(Path(session_dir).expanduser().resolve()) if session_dir else "",
            "config_path": str(Path(cfg_path).expanduser().resolve()) if cfg_path else "",
            "config_sha256": config_sha256,
            "reference_mode": reference_mode,
            "captured_record_count": captured_record_count,
            "reference_trace_count": trace_count,
            "reference_source_path": str(latest.get("source_path") or ""),
            "reference_source_sha256": str(latest.get("source_sha256") or ""),
        },
        "report": {
            "report_pack_dir": str(Path(report_pack_dir).expanduser().resolve()) if report_pack_dir else "",
            "summary_json": "",
            "offsets_json": "",
            "offsets_csv": "",
        },
        "eligibility": {
            "captured_evidence_required": True,
            "reference_mode": reference_mode,
            "captured_record_count": captured_record_count,
            "has_channels": bool(channels),
            "reason": reason,
        },
        "channels": channels,
    }


def promote_recommendation_set(
    recommendation_set: Dict[str, Any],
    path: Optional[Path] = None,
    auto_apply_future_projects: Optional[bool] = None,
) -> Dict[str, Any]:
    store = load_store(path)
    norm_set = _normalize_set(recommendation_set, active_set_id=str(store.get("active_set_id") or ""))
    if norm_set is None:
        return store

    norm_set["status"] = "APPROVED"
    set_id = str(norm_set.get("set_id") or "")

    sets_out: List[Dict[str, Any]] = []
    replaced = False
    for item in store.get("sets") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("set_id") or "") == set_id:
            sets_out.append(norm_set)
            replaced = True
            continue
        existing = dict(item)
        if str(existing.get("status") or "").strip().upper() == "APPROVED":
            existing["status"] = "RETIRED"
        sets_out.append(existing)
    if not replaced:
        sets_out.append(norm_set)

    store["sets"] = sets_out
    store["active_set_id"] = set_id
    if auto_apply_future_projects is not None:
        store["auto_apply_future_projects"] = bool(auto_apply_future_projects)

    save_store(store, path=path)
    return load_store(path)
