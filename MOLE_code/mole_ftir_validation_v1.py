"""mole_ftir_validation_v1

Session-scoped FTIR side-by-side validation helpers.

This module implements a first-pass validation workflow for MOLE vs FTIR
comparisons. It intentionally degrades cleanly when required evidence is
missing, rather than inventing statistics from incomplete data.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

VALIDATION_MODES = ("METHOD_301_FORMAL", "METHOD_301_INFORMED_COMPARISON")
COMMON_TS_COLUMNS = ("ts_iso", "ts_utc", "timestamp", "datetime", "date_time", "time")


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _fmt_num(value: Any, precision: int = 6) -> str:
    try:
        if value in (None, ""):
            return ""
        return f"{float(value):.{precision}f}"
    except Exception:
        return ""


def _parse_iso_dt(text: Any) -> Optional[datetime]:
    try:
        s = str(text or "").strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _normalize_iso(dt: Optional[datetime]) -> Optional[str]:
    try:
        if dt is None:
            return None
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except Exception:
        return None


def _mean(values: Iterable[float]) -> Optional[float]:
    vals = [float(v) for v in values]
    if not vals:
        return None
    return sum(vals) / float(len(vals))


def _sample_variance(values: Iterable[float]) -> Optional[float]:
    vals = [float(v) for v in values]
    n = len(vals)
    if n < 2:
        return None
    avg = sum(vals) / float(n)
    return sum((v - avg) ** 2 for v in vals) / float(n - 1)


def _sniff_delimiter(path: Path, configured: str) -> str:
    delim = str(configured or "AUTO").strip().upper()
    if delim == "TSV":
        return "\t"
    if delim == "CSV":
        return ","
    try:
        if path.suffix.lower() in (".tsv", ".tab"):
            return "\t"
        sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return str(dialect.delimiter or ",")
    except Exception:
        return ","


def _normalize_column_map(value: Any) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if isinstance(value, dict):
        for k, v in value.items():
            key = str(k or "").strip().upper()
            col = str(v or "").strip()
            if key and col:
                out[key] = col
        return out
    txt = str(value or "").replace("\r", "\n")
    for line in txt.split("\n"):
        row = str(line or "").strip()
        if not row or "=" not in row:
            continue
        left, right = row.split("=", 1)
        key = str(left or "").strip().upper()
        col = str(right or "").strip()
        if key and col:
            out[key] = col
    return out


def _normalize_manual_windows(value: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            out.append({
                "run_no": int(item.get("run_no") or 0) if str(item.get("run_no") or "").strip() else None,
                "start_ts_iso": str(item.get("start_ts_iso") or "").strip(),
                "end_ts_iso": str(item.get("end_ts_iso") or "").strip(),
                "label": str(item.get("label") or "").strip(),
            })
        return out
    txt = str(value or "").replace("\r", "\n").strip()
    if not txt:
        return out
    for line in txt.split("\n"):
        row = [str(part or "").strip() for part in line.split(",")]
        if len(row) < 3:
            continue
        run_no = None
        try:
            if row[0]:
                run_no = int(row[0])
        except Exception:
            run_no = None
        out.append({
            "run_no": run_no,
            "start_ts_iso": row[1],
            "end_ts_iso": row[2],
            "label": row[3] if len(row) > 3 else "",
        })
    return out


def _normalize_exclusions(value: Any) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if isinstance(value, dict):
        for k, v in value.items():
            key = str(k or "").strip()
            if not key or not isinstance(v, dict):
                continue
            out[key] = {
                "reason": str(v.get("reason") or "").strip(),
                "reviewer": str(v.get("reviewer") or "").strip(),
                "updated_iso": str(v.get("updated_iso") or "").strip(),
            }
    elif isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            key = str(item.get("row_key") or "").strip()
            if not key:
                continue
            out[key] = {
                "reason": str(item.get("reason") or "").strip(),
                "reviewer": str(item.get("reviewer") or "").strip(),
                "updated_iso": str(item.get("updated_iso") or "").strip(),
            }
    return out


def _normalize_review_snapshot(value: Any) -> Dict[str, Any]:
    block = dict(value or {}) if isinstance(value, dict) else {}
    return {
        "json_path": str(block.get("json_path") or "").strip(),
        "windows_csv_path": str(block.get("windows_csv_path") or "").strip(),
        "method301_csv_path": str(block.get("method301_csv_path") or "").strip(),
        "snapshot_iso": str(block.get("snapshot_iso") or "").strip(),
        "snapshot_by": str(block.get("snapshot_by") or "").strip(),
        "source": str(block.get("source") or "").strip(),
    }


def _normalize_signoff(value: Any) -> Dict[str, Any]:
    block = dict(value or {}) if isinstance(value, dict) else {}
    decision = str(block.get("decision") or "UNSIGNED").strip().upper() or "UNSIGNED"
    if decision not in ("UNSIGNED", "ACCEPTED", "REJECTED"):
        decision = "UNSIGNED"
    basis = str(block.get("basis") or "").strip().upper()
    if basis not in ("", "FORMAL_METHOD_301_PASS", "INFORMED_COMPARISON_ONLY", "REJECTED_NOT_ACCEPTED"):
        basis = ""
    return {
        "decision": decision,
        "basis": basis,
        "by": str(block.get("by") or "").strip(),
        "role": str(block.get("role") or "").strip(),
        "iso": str(block.get("iso") or "").strip(),
        "note": str(block.get("note") or "").strip(),
    }


def _row_key(run_no: Any, analyte: Any, start_iso: Any, end_iso: Any) -> str:
    return "|".join([
        str(run_no or "").strip(),
        str(analyte or "").strip().upper(),
        str(start_iso or "").strip(),
        str(end_iso or "").strip(),
    ])


def normalize_config(cfg: Any, *, analytes_default: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    block = dict(cfg or {}) if isinstance(cfg, dict) else {}
    mode = str(block.get("validation_mode") or "METHOD_301_INFORMED_COMPARISON").strip().upper()
    if mode not in VALIDATION_MODES:
        mode = "METHOD_301_INFORMED_COMPARISON"
    analytes = block.get("analytes")
    if isinstance(analytes, str):
        analytes = [part.strip().upper() for part in analytes.replace(",", ";").split(";") if part.strip()]
    elif isinstance(analytes, list):
        analytes = [str(part or "").strip().upper() for part in analytes if str(part or "").strip()]
    else:
        analytes = []
    if not analytes and analytes_default:
        analytes = [str(part or "").strip().upper() for part in analytes_default if str(part or "").strip()]
    timestamp_column = str(block.get("ftir_timestamp_column") or "").strip()
    column_map = _normalize_column_map(block.get("column_map"))
    manual_windows = _normalize_manual_windows(block.get("manual_windows"))
    comparator_method = str(block.get("comparator_method") or "FTIR_VALIDATED_METHOD").strip()
    clock = str(block.get("timestamp_master_clock") or "SESSION_MASTER_CLOCK").strip()
    return {
        "enabled": bool(block.get("enabled")),
        "validation_mode": mode,
        "comparator_method": comparator_method,
        "timestamp_master_clock": clock,
        "ftir_file_path": str(block.get("ftir_file_path") or "").strip(),
        "ftir_timestamp_column": timestamp_column,
        "ftir_delimiter": str(block.get("ftir_delimiter") or "AUTO").strip().upper() or "AUTO",
        "time_offset_seconds": _safe_float(block.get("time_offset_seconds")) or 0.0,
        "analytes": analytes,
        "column_map": column_map,
        "manual_windows": manual_windows,
        "notes": str(block.get("notes") or "").strip(),
        "review_notes": str(block.get("review_notes") or "").strip(),
        "reviewer": str(block.get("reviewer") or "").strip(),
        "review_locked": bool(block.get("review_locked")),
        "review_lock_by": str(block.get("review_lock_by") or "").strip(),
        "review_lock_iso": str(block.get("review_lock_iso") or "").strip(),
        "review_unlock_by": str(block.get("review_unlock_by") or "").strip(),
        "review_unlock_iso": str(block.get("review_unlock_iso") or "").strip(),
        "review_snapshot": _normalize_review_snapshot(block.get("review_snapshot")),
        "signoff": _normalize_signoff(block.get("signoff")),
        "exclusions": _normalize_exclusions(block.get("exclusions")),
    }


def load_ftir_records(cfg: Dict[str, Any]) -> Dict[str, Any]:
    src = Path(str(cfg.get("ftir_file_path") or "")).expanduser()
    analytes = [str(code or "").strip().upper() for code in (cfg.get("analytes") or []) if str(code or "").strip()]
    column_map = cfg.get("column_map") if isinstance(cfg.get("column_map"), dict) else {}
    out_rows: List[Dict[str, Any]] = []
    summary = {
        "status": "Gap",
        "path": str(src),
        "exists": src.exists(),
        "record_count": 0,
        "delimiter": None,
        "timestamp_column": str(cfg.get("ftir_timestamp_column") or ""),
        "analytes_found": [],
        "note": "",
    }
    if not src.exists():
        summary["note"] = "FTIR source file not found."
        return {"rows": out_rows, "summary": summary}

    try:
        if src.suffix.lower() == ".jsonl":
            for idx, line in enumerate(src.read_text(encoding="utf-8-sig", errors="replace").splitlines(), start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                ts_col = str(cfg.get("ftir_timestamp_column") or "").strip()
                ts_val = row.get(ts_col) if ts_col else None
                if ts_val in (None, ""):
                    for col in COMMON_TS_COLUMNS:
                        if row.get(col) not in (None, ""):
                            ts_val = row.get(col)
                            summary["timestamp_column"] = col
                            break
                dt = _parse_iso_dt(ts_val)
                if dt is None:
                    continue
                dt = dt + timedelta(seconds=float(cfg.get("time_offset_seconds") or 0.0))
                values: Dict[str, float] = {}
                for code in analytes:
                    col = str(column_map.get(code) or code)
                    fv = _safe_float(row.get(col))
                    if fv is not None:
                        values[code] = fv
                out_rows.append({"ts_dt": dt, "ts_iso": _normalize_iso(dt), "values": values, "row_index": idx})
        else:
            delim = _sniff_delimiter(src, str(cfg.get("ftir_delimiter") or "AUTO"))
            summary["delimiter"] = "TSV" if delim == "\t" else delim
            with src.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh, delimiter=delim)
                ts_col = str(cfg.get("ftir_timestamp_column") or "").strip()
                header = list(reader.fieldnames or [])
                if ts_col and ts_col not in header:
                    ts_col = ""
                if not ts_col:
                    for col in COMMON_TS_COLUMNS:
                        if col in header:
                            ts_col = col
                            break
                summary["timestamp_column"] = ts_col
                for idx, row in enumerate(reader, start=2):
                    dt = _parse_iso_dt(row.get(ts_col) if ts_col else None)
                    if dt is None:
                        continue
                    dt = dt + timedelta(seconds=float(cfg.get("time_offset_seconds") or 0.0))
                    values: Dict[str, float] = {}
                    for code in analytes:
                        col = str(column_map.get(code) or code)
                        fv = _safe_float(row.get(col))
                        if fv is not None:
                            values[code] = fv
                    out_rows.append({"ts_dt": dt, "ts_iso": _normalize_iso(dt), "values": values, "row_index": idx})
    except Exception as e:
        summary["status"] = "Gap"
        summary["note"] = f"FTIR ingest failed: {e}"
        return {"rows": [], "summary": summary}

    analytes_found = sorted({code for row in out_rows for code in (row.get("values") or {}).keys()})
    summary["record_count"] = len(out_rows)
    summary["analytes_found"] = analytes_found
    summary["status"] = "Available" if out_rows else "Gap"
    summary["note"] = "FTIR ingest complete." if out_rows else "No FTIR rows were parsed."
    return {"rows": out_rows, "summary": summary}


def load_mole_records(raw_samples_path: Any, analytes: Iterable[str]) -> Dict[str, Any]:
    path = Path(str(raw_samples_path or "")).expanduser()
    codes = {str(code or "").strip().upper() for code in analytes if str(code or "").strip()}
    out_rows: List[Dict[str, Any]] = []
    summary = {
        "status": "Gap",
        "path": str(path),
        "exists": path.exists(),
        "record_count": 0,
        "analytes_found": [],
        "note": "",
    }
    if not path.exists():
        summary["note"] = "MOLE raw samples file not found."
        return {"rows": out_rows, "summary": summary}
    try:
        for idx, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            code = str(row.get("channel_id") or "").strip().upper()
            if code not in codes:
                continue
            qual = row.get("quality_flags") if isinstance(row.get("quality_flags"), dict) else {}
            if qual and ((qual.get("comm_ok") is False) or (qual.get("decode_ok") is False)):
                continue
            dt = _parse_iso_dt(row.get("ts_utc") or row.get("ts_iso"))
            fv = _safe_float(row.get("value_eng"))
            if dt is None or fv is None:
                continue
            out_rows.append({"ts_dt": dt, "ts_iso": _normalize_iso(dt), "channel_id": code, "value": fv, "row_index": idx})
    except Exception as e:
        summary["note"] = f"MOLE raw ingest failed: {e}"
        return {"rows": [], "summary": summary}

    analytes_found = sorted({str(row.get("channel_id") or "").upper() for row in out_rows})
    summary["record_count"] = len(out_rows)
    summary["analytes_found"] = analytes_found
    summary["status"] = "Available" if out_rows else "Gap"
    summary["note"] = "MOLE raw ingest complete." if out_rows else "No MOLE rows were parsed for the requested analytes."
    return {"rows": out_rows, "summary": summary}


def build_windows(cfg: Dict[str, Any], actual_runs: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    manual = cfg.get("manual_windows") if isinstance(cfg.get("manual_windows"), list) else []
    if manual:
        for idx, item in enumerate(manual, start=1):
            if not isinstance(item, dict):
                continue
            start_dt = _parse_iso_dt(item.get("start_ts_iso"))
            end_dt = _parse_iso_dt(item.get("end_ts_iso"))
            if start_dt is None or end_dt is None or end_dt <= start_dt:
                continue
            rows.append({
                "run_no": item.get("run_no") or idx,
                "window_start_iso": _normalize_iso(start_dt),
                "window_end_iso": _normalize_iso(end_dt),
                "source": "MANUAL_WINDOWS",
                "label": str(item.get("label") or f"Manual window {idx}").strip(),
            })
        return {
            "status": "Available" if rows else "Gap",
            "source": "MANUAL_WINDOWS",
            "rows": rows,
            "note": "Manual FTIR validation windows were used." if rows else "Manual FTIR validation windows were configured but invalid.",
        }

    for item in actual_runs:
        if not isinstance(item, dict):
            continue
        start_dt = _parse_iso_dt(item.get("start_ts_iso"))
        end_dt = _parse_iso_dt(item.get("end_ts_iso"))
        if start_dt is None or end_dt is None or end_dt <= start_dt:
            continue
        rows.append({
            "run_no": item.get("run_no"),
            "window_start_iso": _normalize_iso(start_dt),
            "window_end_iso": _normalize_iso(end_dt),
            "source": "ACTUAL_RUNS",
            "label": f"Run {item.get('run_no')}",
        })
    return {
        "status": "Available" if rows else "Gap",
        "source": "ACTUAL_RUNS",
        "rows": rows,
        "note": "Session-scoped actual run windows were used." if rows else "No actual run windows were available for FTIR validation.",
    }


def align_windows(
    cfg: Dict[str, Any],
    windows: Iterable[Dict[str, Any]],
    mole_rows: Iterable[Dict[str, Any]],
    ftir_rows: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    analytes = [str(code or "").strip().upper() for code in (cfg.get("analytes") or []) if str(code or "").strip()]
    mole_list = list(mole_rows or [])
    ftir_list = list(ftir_rows or [])
    out: List[Dict[str, Any]] = []

    for window in windows:
        if not isinstance(window, dict):
            continue
        start_dt = _parse_iso_dt(window.get("window_start_iso"))
        end_dt = _parse_iso_dt(window.get("window_end_iso"))
        if start_dt is None or end_dt is None or end_dt <= start_dt:
            continue
        for code in analytes:
            mole_vals = [
                float(row.get("value"))
                for row in mole_list
                if str(row.get("channel_id") or "").strip().upper() == code
                and isinstance(row.get("ts_dt"), datetime)
                and start_dt <= row["ts_dt"] < end_dt
            ]
            ftir_vals = [
                float((row.get("values") or {}).get(code))
                for row in ftir_list
                if isinstance(row.get("ts_dt"), datetime)
                and start_dt <= row["ts_dt"] < end_dt
                and (row.get("values") or {}).get(code) is not None
            ]
            mole_avg = _mean(mole_vals)
            ftir_avg = _mean(ftir_vals)
            out.append({
                "run_no": window.get("run_no"),
                "label": window.get("label"),
                "window_start_iso": window.get("window_start_iso"),
                "window_end_iso": window.get("window_end_iso"),
                "analyte": code,
                "row_key": _row_key(window.get("run_no"), code, window.get("window_start_iso"), window.get("window_end_iso")),
                "mole_count": len(mole_vals),
                "ftir_count": len(ftir_vals),
                "mole_avg": mole_avg,
                "ftir_avg": ftir_avg,
                "difference": (mole_avg - ftir_avg) if (mole_avg is not None and ftir_avg is not None) else None,
                "paired": bool(mole_avg is not None and ftir_avg is not None),
                "status": (
                    "PAIRED"
                    if (mole_avg is not None and ftir_avg is not None)
                    else ("MISSING_MOLE" if ftir_avg is not None else ("MISSING_FTIR" if mole_avg is not None else "NO_DATA"))
                ),
            })
    return out


def compute_method301_stats(cfg: Dict[str, Any], aligned_rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mode = str(cfg.get("validation_mode") or "METHOD_301_INFORMED_COMPARISON").strip().upper()
    analytes = sorted({str(row.get("analyte") or "").strip().upper() for row in aligned_rows if str(row.get("analyte") or "").strip()})
    out: List[Dict[str, Any]] = []
    for code in analytes:
        pairs_all = [row for row in aligned_rows if str(row.get("analyte") or "").strip().upper() == code and bool(row.get("paired"))]
        pairs = [row for row in pairs_all if not bool(row.get("excluded"))]
        mole_vals = [float(row.get("mole_avg")) for row in pairs if row.get("mole_avg") is not None]
        ftir_vals = [float(row.get("ftir_avg")) for row in pairs if row.get("ftir_avg") is not None]
        diffs = [float(row.get("difference")) for row in pairs if row.get("difference") is not None]
        n = len(diffs)
        mole_mean = _mean(mole_vals)
        ftir_mean = _mean(ftir_vals)
        diff_mean = _mean(diffs)
        diff_var = _sample_variance(diffs)
        diff_sd = math.sqrt(diff_var) if diff_var is not None and diff_var >= 0 else None
        t_stat = None
        if n >= 2 and diff_sd is not None and diff_sd > 0:
            t_stat = abs(float(diff_mean or 0.0)) / (diff_sd / math.sqrt(float(n)))
        rel_bias_pct = None
        if ftir_mean not in (None, 0):
            rel_bias_pct = (float(diff_mean or 0.0) / float(ftir_mean)) * 100.0
        correction_factor = None
        if mole_mean not in (None, 0) and ftir_mean is not None:
            correction_factor = float(ftir_mean) / float(mole_mean)
        var_mole = _sample_variance(mole_vals)
        var_ftir = _sample_variance(ftir_vals)
        f_stat = None
        if var_mole is not None and var_ftir is not None and min(var_mole, var_ftir) > 0:
            f_stat = max(var_mole, var_ftir) / min(var_mole, var_ftir)
        t_crit = 2.571 if n == 6 else None
        f_crit = 4.28 if n == 6 else None
        bias_status = "NO_DATA"
        precision_status = "NO_DATA"
        overall = "NO_DATA"
        note = ""
        if n == 0:
            note = "No paired MOLE/FTIR windows were available for this analyte."
        elif mode == "METHOD_301_FORMAL" and n != 6:
            overall = "INSUFFICIENT_FORMAL_WINDOWS"
            bias_status = "INFORMED_ONLY"
            precision_status = "INFORMED_ONLY"
            note = "Formal Method 301 comparison requires six valid comparison sets; reported values are informational only."
        else:
            if t_stat is not None and t_crit is not None and t_stat <= t_crit:
                bias_status = "PASS"
            elif rel_bias_pct is not None:
                abs_bias = abs(rel_bias_pct)
                if abs_bias <= 10.0:
                    bias_status = "PASS"
                elif abs_bias <= 30.0 and correction_factor is not None and 0.70 <= correction_factor <= 1.30:
                    bias_status = "PASS_WITH_CORRECTION_FACTOR"
                else:
                    bias_status = "FAIL"
            else:
                bias_status = "PARTIAL"
            if f_stat is not None and f_crit is not None:
                precision_status = "PASS" if f_stat <= f_crit else "FAIL"
            elif mode == "METHOD_301_INFORMED_COMPARISON":
                precision_status = "INFORMED_ONLY"
            else:
                precision_status = "PARTIAL"
            if mode == "METHOD_301_INFORMED_COMPARISON":
                overall = "INFORMED_COMPARISON_ONLY"
                note = "Statistics were computed from time-matched windows but do not satisfy a formal Method 301 quadruplicate design by themselves."
            else:
                overall = "PASS" if bias_status in ("PASS", "PASS_WITH_CORRECTION_FACTOR") and precision_status == "PASS" else "FAIL"
                note = "Formal Method 301 thresholds applied using six comparison sets."
        out.append({
            "analyte": code,
            "mode": mode,
            "paired_window_count": n,
            "excluded_window_count": len([row for row in pairs_all if bool(row.get("excluded"))]),
            "mole_mean": mole_mean,
            "ftir_mean": ftir_mean,
            "mean_difference": diff_mean,
            "relative_bias_pct": rel_bias_pct,
            "correction_factor": correction_factor,
            "difference_sd": diff_sd,
            "t_statistic": t_stat,
            "t_critical_95_two_sided": t_crit,
            "candidate_variance": var_mole,
            "validated_variance": var_ftir,
            "f_statistic": f_stat,
            "f_critical_95": f_crit,
            "bias_status": bias_status,
            "precision_status": precision_status,
            "overall_status": overall,
            "note": note,
        })
    return out


def build_validation_package(
    cfg: Dict[str, Any],
    *,
    run_aggregation: Dict[str, Any],
    raw_samples_path: Any,
) -> Dict[str, Any]:
    normalized = normalize_config(cfg)
    if not normalized.get("enabled"):
        return {
            "status": "DISABLED",
            "config": normalized,
            "ftir_source": {"status": "Gap", "note": "FTIR validation not enabled."},
            "mole_source": {"status": "Gap", "note": "FTIR validation not enabled."},
            "windows": {"status": "Gap", "rows": [], "note": "FTIR validation not enabled."},
            "aligned_rows": [],
            "method301": [],
            "coverage_note": "FTIR validation not enabled for this session.",
            "overall_status": "DISABLED",
        }

    ftir = load_ftir_records(normalized)
    mole = load_mole_records(raw_samples_path, normalized.get("analytes") or [])
    actual_runs = run_aggregation.get("actual_runs") if isinstance(run_aggregation.get("actual_runs"), list) else []
    windows = build_windows(normalized, actual_runs)
    aligned_rows = align_windows(normalized, windows.get("rows") or [], mole.get("rows") or [], ftir.get("rows") or [])
    exclusions = normalized.get("exclusions") if isinstance(normalized.get("exclusions"), dict) else {}
    excluded_rows: List[Dict[str, Any]] = []
    for row in aligned_rows:
        if not isinstance(row, dict):
            continue
        row_key = str(row.get("row_key") or "").strip()
        exc = exclusions.get(row_key) if row_key else None
        if isinstance(exc, dict):
            row["excluded"] = True
            row["exclusion_reason"] = str(exc.get("reason") or "").strip()
            row["reviewer"] = str(exc.get("reviewer") or "").strip()
            row["updated_iso"] = str(exc.get("updated_iso") or "").strip()
            excluded_rows.append({
                "row_key": row_key,
                "run_no": row.get("run_no"),
                "label": row.get("label"),
                "analyte": row.get("analyte"),
                "reason": row.get("exclusion_reason"),
                "reviewer": row.get("reviewer"),
                "updated_iso": row.get("updated_iso"),
            })
        else:
            row["excluded"] = False
            row["exclusion_reason"] = ""
            row["reviewer"] = ""
            row["updated_iso"] = ""
    method301 = compute_method301_stats(normalized, aligned_rows)

    statuses = [str(row.get("overall_status") or "") for row in method301]
    overall = "Gap"
    if method301:
        if any(status == "FAIL" for status in statuses):
            overall = "FAIL"
        elif any(status == "PASS_WITH_CORRECTION_FACTOR" for status in statuses):
            overall = "PASS_WITH_CORRECTION_FACTOR"
        elif any(status == "PASS" for status in statuses):
            overall = "PASS"
        elif all(status in ("INFORMED_COMPARISON_ONLY", "INFORMED_ONLY", "PARTIAL", "NO_DATA", "INFORMED_COMPARISON_ONLY") for status in statuses):
            overall = "INFORMED_COMPARISON_ONLY"
    if not aligned_rows:
        overall = "Gap"

    coverage_note = []
    coverage_note.append(str(ftir.get("summary", {}).get("note") or "").strip())
    coverage_note.append(str(mole.get("summary", {}).get("note") or "").strip())
    coverage_note.append(str(windows.get("note") or "").strip())
    coverage_note = " | ".join([part for part in coverage_note if part])

    return {
        "status": "Available" if aligned_rows else "Gap",
        "config": normalized,
        "ftir_source": ftir.get("summary") or {},
        "mole_source": mole.get("summary") or {},
        "windows": windows,
        "aligned_rows": aligned_rows,
        "excluded_rows": excluded_rows,
        "method301": method301,
        "coverage_note": coverage_note,
        "overall_status": overall,
        "paired_window_count": len([row for row in aligned_rows if bool(row.get("paired"))]),
        "excluded_count": len(excluded_rows),
        "review_notes": str(normalized.get("review_notes") or "").strip(),
        "reviewer": str(normalized.get("reviewer") or "").strip(),
        "review_locked": bool(normalized.get("review_locked")),
        "review_lock_by": str(normalized.get("review_lock_by") or "").strip(),
        "review_lock_iso": str(normalized.get("review_lock_iso") or "").strip(),
        "review_unlock_by": str(normalized.get("review_unlock_by") or "").strip(),
        "review_unlock_iso": str(normalized.get("review_unlock_iso") or "").strip(),
        "review_snapshot": dict(normalized.get("review_snapshot") or {}) if isinstance(normalized.get("review_snapshot"), dict) else {},
        "signoff": dict(normalized.get("signoff") or {}) if isinstance(normalized.get("signoff"), dict) else _normalize_signoff(None),
    }


def write_validation_exports(
    payload: Dict[str, Any],
    *,
    json_path: Any,
    windows_csv_path: Any,
    method301_csv_path: Any,
) -> Dict[str, str]:
    json_p = Path(str(json_path)).expanduser()
    windows_p = Path(str(windows_csv_path)).expanduser()
    method_p = Path(str(method301_csv_path)).expanduser()
    for path in (json_p, windows_p, method_p):
        path.parent.mkdir(parents=True, exist_ok=True)

    json_p.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with open(windows_p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "run_no",
            "label",
            "window_start_iso",
            "window_end_iso",
            "analyte",
            "row_key",
            "mole_count",
            "ftir_count",
            "mole_avg",
            "ftir_avg",
            "difference",
            "paired",
            "status",
            "excluded",
            "exclusion_reason",
            "reviewer",
            "updated_iso",
        ])
        for row in list(payload.get("aligned_rows") or []):
            if not isinstance(row, dict):
                continue
            w.writerow([
                row.get("run_no"),
                row.get("label"),
                row.get("window_start_iso"),
                row.get("window_end_iso"),
                row.get("analyte"),
                row.get("row_key"),
                row.get("mole_count"),
                row.get("ftir_count"),
                _fmt_num(row.get("mole_avg"), 6),
                _fmt_num(row.get("ftir_avg"), 6),
                _fmt_num(row.get("difference"), 6),
                row.get("paired"),
                row.get("status"),
                row.get("excluded"),
                row.get("exclusion_reason"),
                row.get("reviewer"),
                row.get("updated_iso"),
            ])

    with open(method_p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "analyte",
            "mode",
            "paired_window_count",
            "excluded_window_count",
            "mole_mean",
            "ftir_mean",
            "mean_difference",
            "relative_bias_pct",
            "correction_factor",
            "difference_sd",
            "t_statistic",
            "t_critical_95_two_sided",
            "candidate_variance",
            "validated_variance",
            "f_statistic",
            "f_critical_95",
            "bias_status",
            "precision_status",
            "overall_status",
            "note",
        ])
        for row in list(payload.get("method301") or []):
            if not isinstance(row, dict):
                continue
            w.writerow([
                row.get("analyte"),
                row.get("mode"),
                row.get("paired_window_count"),
                row.get("excluded_window_count"),
                _fmt_num(row.get("mole_mean"), 6),
                _fmt_num(row.get("ftir_mean"), 6),
                _fmt_num(row.get("mean_difference"), 6),
                _fmt_num(row.get("relative_bias_pct"), 6),
                _fmt_num(row.get("correction_factor"), 6),
                _fmt_num(row.get("difference_sd"), 6),
                _fmt_num(row.get("t_statistic"), 6),
                _fmt_num(row.get("t_critical_95_two_sided"), 6),
                _fmt_num(row.get("candidate_variance"), 6),
                _fmt_num(row.get("validated_variance"), 6),
                _fmt_num(row.get("f_statistic"), 6),
                _fmt_num(row.get("f_critical_95"), 6),
                row.get("bias_status"),
                row.get("precision_status"),
                row.get("overall_status"),
                row.get("note"),
            ])

    return {
        "json_path": str(json_p),
        "windows_csv_path": str(windows_p),
        "method301_csv_path": str(method_p),
    }
