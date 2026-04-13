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
SIGNOFF_ACCEPTANCE_BASES = ("FORMAL_METHOD_301", "METHOD_301_INFORMED_COMPARISON", "NOT_ACCEPTED")
FTIR_VENDOR_PROFILES = ("AUTO", "GENERIC", "GASMET_CSV", "MKS_MULTIGAS_CSV", "OPSIS_CSV", "THERMOFISHER_MAX_CSV")
LEGACY_SIGNOFF_BASIS_MAP = {
    "FORMAL_METHOD_301_PASS": "FORMAL_METHOD_301",
    "INFORMED_COMPARISON_ONLY": "METHOD_301_INFORMED_COMPARISON",
    "REJECTED_NOT_ACCEPTED": "NOT_ACCEPTED",
}
COMMON_TS_COLUMNS = ("ts_iso", "ts_utc", "timestamp", "datetime", "date_time", "time")
ANALYTE_HEADER_ALIASES = {
    "O2": ("o2", "oxygen"),
    "CO2": ("co2", "carbondioxide"),
    "CO": ("co", "carbonmonoxide"),
    "NO": ("no", "nitricoxide"),
    "NO2": ("no2", "nitrogendioxide"),
    "NOX": ("nox", "nitrogenoxides"),
    "SO2": ("so2", "sulfurdioxide"),
    "VOC": ("voc", "totalvoc", "thc", "nmhc", "nonmethanehydrocarbons"),
    "NH3": ("nh3", "ammonia"),
    "CH4": ("ch4", "methane"),
}
HEADER_NOISE_TOKENS = (
    "ppm", "ppmv", "ppmd", "ppb", "percent", "pct", "vol", "volume", "conc", "concentration",
    "avg", "average", "mean", "dry", "wet", "corr", "corrected", "raw", "stack", "gas",
)
VENDOR_TIMESTAMP_HINTS = {
    "GENERIC": {
        "timestamp": COMMON_TS_COLUMNS,
        "date": (),
        "time": (),
    },
    "GASMET_CSV": {
        "timestamp": ("timestamp", "datetime", "sampletime", "time"),
        "date": ("date", "sampledate", "recorddate"),
        "time": ("time", "sampletime", "recordtime"),
    },
    "MKS_MULTIGAS_CSV": {
        "timestamp": ("recordtimestamp", "timestamp", "datetime"),
        "date": ("recorddate", "date"),
        "time": ("recordtime", "time"),
    },
    "OPSIS_CSV": {
        "timestamp": ("datetime", "sampletime", "timestamp", "timesampled"),
        "date": ("sampledate", "date", "recorddate"),
        "time": ("sampletime", "time", "recordtime"),
    },
    "THERMOFISHER_MAX_CSV": {
        "timestamp": ("datetime", "datetimestamp", "timestamp", "timestamputc", "sampletime", "timesampled"),
        "date": ("date", "sampledate", "recorddate", "datestamp"),
        "time": ("time", "sampletime", "recordtime", "timestamp", "timestamputc"),
    },
}
QA_MIN_ROWS_PER_SIDE = 2
QA_MIN_WINDOW_COVERAGE_RATIO = 0.50
QA_MAX_ABS_OFFSET_SECONDS = 30.0
QA_MAX_ABS_DRIFT_SECONDS = 15.0


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


def _canon_name(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _canon_measurement_name(value: Any) -> str:
    canon = _canon_name(value)
    for token in HEADER_NOISE_TOKENS:
        canon = canon.replace(token, "")
    return canon


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


def _parse_dt_flexible(text: Any) -> Optional[datetime]:
    dt = _parse_iso_dt(text)
    if dt is not None:
        return dt
    raw = str(text or "").strip()
    if not raw:
        return None
    raw_norm = raw.replace("/", "-")
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m-%d-%Y %H:%M:%S.%f",
        "%m-%d-%Y %H:%M:%S",
        "%m-%d-%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%m-%d-%y %H:%M:%S",
        "%m-%d-%y %H:%M",
    ):
        try:
            return datetime.strptime(raw_norm, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def _normalize_iso(dt: Optional[datetime]) -> Optional[str]:
    try:
        if dt is None:
            return None
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except Exception:
        return None


def _time_delta_seconds(left: Optional[datetime], right: Optional[datetime]) -> Optional[float]:
    try:
        if left is None or right is None:
            return None
        return float((left - right).total_seconds())
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


def _guess_timestamp_column(headers: Iterable[str]) -> str:
    header_list = [str(col or "").strip() for col in headers if str(col or "").strip()]
    canon_map = {_canon_name(col): col for col in header_list}
    for col in COMMON_TS_COLUMNS:
        found = canon_map.get(_canon_name(col))
        if found:
            return found
    for col in header_list:
        canon = _canon_name(col)
        if canon in ("sampletime", "samptime", "recordtime", "stacktime"):
            return col
        if "timestamp" in canon or ("date" in canon and "time" in canon):
            return col
    for col in header_list:
        canon = _canon_name(col)
        if canon.endswith("time") or canon.startswith("time"):
            return col
    return ""


def _find_header_match(headers: Iterable[str], hints: Iterable[str]) -> str:
    canon_map = {_canon_name(col): str(col or "").strip() for col in headers if str(col or "").strip()}
    for hint in hints:
        found = canon_map.get(_canon_name(hint))
        if found:
            return found
    return ""


def _resolve_vendor_profile(headers: Iterable[str], requested: str) -> Tuple[str, str]:
    req = str(requested or "AUTO").strip().upper() or "AUTO"
    if req not in FTIR_VENDOR_PROFILES:
        req = "AUTO"
    header_list = [str(col or "").strip() for col in headers if str(col or "").strip()]
    if req != "AUTO":
        return req, "configured"
    canon = {_canon_name(col) for col in header_list}
    if "recorddate" in canon and "recordtime" in canon:
        return "MKS_MULTIGAS_CSV", "auto-detected from Record Date/Time columns"
    if "sampledate" in canon and ("sampletime" in canon or "timesampled" in canon):
        return "OPSIS_CSV", "auto-detected from Sample Date/Time columns"
    if "datestamp" in canon and "timestamp" in canon:
        return "THERMOFISHER_MAX_CSV", "auto-detected from MAX date/timestamp columns"
    if "date" in canon and "time" in canon and any(("[%"
        in col) or ("[ppm" in col.lower()) or ("(ppm" in col.lower()) for col in header_list):
        return "GASMET_CSV", "auto-detected from Date/Time columns and unit-tagged analyte headers"
    return "GENERIC", "generic FTIR import profile"


def _parse_vendor_timestamp(row: Dict[str, Any], headers: Iterable[str], profile: str, configured_ts: str = "") -> Tuple[Optional[datetime], str]:
    header_list = [str(col or "").strip() for col in headers if str(col or "").strip()]
    hints = VENDOR_TIMESTAMP_HINTS.get(profile, VENDOR_TIMESTAMP_HINTS["GENERIC"])
    ts_col = str(configured_ts or "").strip()
    if ts_col and ts_col in row and row.get(ts_col) not in (None, ""):
        dt = _parse_dt_flexible(row.get(ts_col))
        if dt is not None:
            return dt, ts_col
    for candidate in [ts_col] if ts_col else []:
        dt = _parse_dt_flexible(row.get(candidate))
        if dt is not None:
            return dt, candidate
    ts_hint = _find_header_match(header_list, hints.get("timestamp") or [])
    if ts_hint and row.get(ts_hint) not in (None, ""):
        dt = _parse_dt_flexible(row.get(ts_hint))
        if dt is not None:
            return dt, ts_hint
    date_col = _find_header_match(header_list, hints.get("date") or [])
    time_col = _find_header_match(header_list, hints.get("time") or [])
    if date_col and time_col:
        dt = _parse_dt_flexible(f"{row.get(date_col, '')} {row.get(time_col, '')}")
        if dt is not None:
            return dt, f"{date_col}+{time_col}"
    return None, (ts_col or ts_hint or f"{date_col}+{time_col}" if (date_col and time_col) else "")


def _guess_column_map(headers: Iterable[str], analytes: Iterable[str]) -> Dict[str, str]:
    header_list = [str(col or "").strip() for col in headers if str(col or "").strip()]
    canon_headers = {col: _canon_name(col) for col in header_list}
    measure_headers = {col: _canon_measurement_name(col) for col in header_list}
    out: Dict[str, str] = {}
    for analyte in analytes:
        code = str(analyte or "").strip().upper()
        if not code:
            continue
        code_canon = _canon_name(code)
        aliases = tuple(_canon_name(alias) for alias in ANALYTE_HEADER_ALIASES.get(code, (code,)))
        exact = next((col for col, canon in canon_headers.items() if canon == code_canon), "")
        if exact:
            out[code] = exact
            continue
        exact_measure = next((col for col, canon in measure_headers.items() if canon in aliases), "")
        if exact_measure:
            out[code] = exact_measure
            continue
        candidates = [
            col
            for col, canon in measure_headers.items()
            if any(alias and alias in canon for alias in aliases) and not any(tok in canon for tok in ("time", "date"))
        ]
        if candidates:
            out[code] = sorted(candidates, key=lambda item: (len(item), item.lower()))[0]
    return out


def _series_stats(rows: Iterable[Dict[str, Any]], value_getter: Optional[Any] = None) -> Dict[str, Any]:
    items = list(rows or [])
    times = [row.get("ts_dt") for row in items if isinstance(row.get("ts_dt"), datetime)]
    times = sorted(times)
    out = {
        "count": len(items),
        "first_dt": times[0] if times else None,
        "last_dt": times[-1] if times else None,
        "midpoint_dt": None,
        "span_seconds": None,
        "values": [],
    }
    if times:
        out["midpoint_dt"] = times[0] + ((times[-1] - times[0]) / 2)
        out["span_seconds"] = max(0.0, float((times[-1] - times[0]).total_seconds()))
    vals: List[float] = []
    for row in items:
        try:
            value = value_getter(row) if callable(value_getter) else row.get("value")
        except Exception:
            value = None
        fv = _safe_float(value)
        if fv is not None:
            vals.append(float(fv))
    out["values"] = vals
    return out


def _row_qa_eval(row: Dict[str, Any]) -> Tuple[str, List[str]]:
    flags: List[str] = []
    if not bool(row.get("paired")):
        status = str(row.get("status") or "NO_DATA").strip().upper() or "NO_DATA"
        return ("ERROR", [status])

    mole_count = int(row.get("mole_count") or 0)
    ftir_count = int(row.get("ftir_count") or 0)
    if mole_count < QA_MIN_ROWS_PER_SIDE:
        flags.append("LOW_MOLE_COUNT")
    if ftir_count < QA_MIN_ROWS_PER_SIDE:
        flags.append("LOW_FTIR_COUNT")

    mole_cov = _safe_float(row.get("mole_coverage_ratio"))
    ftir_cov = _safe_float(row.get("ftir_coverage_ratio"))
    if mole_cov is not None and mole_cov < QA_MIN_WINDOW_COVERAGE_RATIO:
        flags.append("LOW_MOLE_COVERAGE")
    if ftir_cov is not None and ftir_cov < QA_MIN_WINDOW_COVERAGE_RATIO:
        flags.append("LOW_FTIR_COVERAGE")

    offset_adj = _safe_float(row.get("offset_seconds_adjusted"))
    if offset_adj is not None and abs(offset_adj) > QA_MAX_ABS_OFFSET_SECONDS:
        flags.append("HIGH_TIME_OFFSET")

    drift_adj = _safe_float(row.get("drift_seconds_adjusted"))
    if drift_adj is not None and abs(drift_adj) > QA_MAX_ABS_DRIFT_SECONDS:
        flags.append("HIGH_TIME_DRIFT")

    if any(flag in ("HIGH_TIME_OFFSET", "HIGH_TIME_DRIFT") for flag in flags):
        return ("ERROR", flags)
    if flags:
        return ("WARN", flags)
    return ("PASS", flags)


def _build_validation_qa(
    cfg: Dict[str, Any],
    ftir_summary: Dict[str, Any],
    mole_summary: Dict[str, Any],
    windows: Dict[str, Any],
    aligned_rows: Iterable[Dict[str, Any]],
    method301: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    rows = [dict(row) for row in list(aligned_rows or []) if isinstance(row, dict)]
    included_rows = [row for row in rows if not bool(row.get("excluded"))]
    row_status_counts: Dict[str, int] = {}
    blocking_issues: List[str] = []
    warnings: List[str] = []
    for row in included_rows:
        qa_status = str(row.get("qa_status") or "NO_DATA").strip().upper() or "NO_DATA"
        row_status_counts[qa_status] = int(row_status_counts.get(qa_status) or 0) + 1

    unresolved = list(ftir_summary.get("unresolved_analytes") or []) if isinstance(ftir_summary, dict) else []
    auto_cols = dict(ftir_summary.get("autodetected_columns_used") or {}) if isinstance(ftir_summary, dict) else {}
    ts_col = str(ftir_summary.get("timestamp_column") or "").strip() if isinstance(ftir_summary, dict) else ""
    suggested_ts = str(ftir_summary.get("suggested_timestamp_column") or "").strip() if isinstance(ftir_summary, dict) else ""

    if not ts_col:
        blocking_issues.append("FTIR timestamp column is not resolved.")
    elif suggested_ts and ts_col == suggested_ts:
        warnings.append(f"Using auto-detected FTIR timestamp column: {ts_col}.")

    if unresolved:
        blocking_issues.append(f"FTIR analyte columns unresolved: {', '.join([str(v) for v in unresolved])}.")
    if auto_cols:
        warnings.append(
            "Using auto-detected FTIR analyte columns: "
            + ", ".join([f"{code}->{col}" for code, col in sorted(auto_cols.items())])
        )

    if str(ftir_summary.get("status") or "").strip() != "Available":
        blocking_issues.append(str(ftir_summary.get("note") or "FTIR import is not available.").strip())
    if str(mole_summary.get("status") or "").strip() != "Available":
        blocking_issues.append(str(mole_summary.get("note") or "MOLE raw evidence is not available.").strip())
    if str(windows.get("status") or "").strip() != "Available":
        blocking_issues.append(str(windows.get("note") or "Comparison windows are not available.").strip())

    error_rows = [row for row in included_rows if str(row.get("qa_status") or "").strip().upper() == "ERROR"]
    warn_rows = [row for row in included_rows if str(row.get("qa_status") or "").strip().upper() == "WARN"]
    if error_rows:
        blocking_issues.append(f"{len(error_rows)} included FTIR comparison row(s) failed alignment QA.")
    if warn_rows:
        warnings.append(f"{len(warn_rows)} included FTIR comparison row(s) have QA warnings.")

    method_rows = [row for row in list(method301 or []) if isinstance(row, dict)]
    if not method_rows:
        blocking_issues.append("No FTIR validation statistics were produced from the current aligned rows.")
    elif str(cfg.get("validation_mode") or "").strip().upper() == "METHOD_301_FORMAL":
        insufficient = [
            str(row.get("analyte") or "").strip().upper()
            for row in method_rows
            if str(row.get("overall_status") or "").strip().upper() == "INSUFFICIENT_FORMAL_WINDOWS"
        ]
        if insufficient:
            warnings.append(
                "Formal Method 301 validation does not yet have six included comparison windows for: "
                + ", ".join([code for code in insufficient if code])
            )

    lock_ready = len(blocking_issues) == 0
    signoff_ready = lock_ready and not any(
        str(row.get("overall_status") or "").strip().upper() in ("NO_DATA", "GAP")
        for row in method_rows
    )
    summary_parts = [
        f"lock ready: {'YES' if lock_ready else 'NO'}",
        f"signoff ready: {'YES' if signoff_ready else 'NO'}",
        f"qa rows pass/warn/error: {int(row_status_counts.get('PASS') or 0)}/{int(row_status_counts.get('WARN') or 0)}/{int(row_status_counts.get('ERROR') or 0)}",
    ]
    if auto_cols:
        summary_parts.append(
            "auto-map: " + ", ".join([f"{code}->{col}" for code, col in sorted(auto_cols.items())])
        )
    if ts_col:
        summary_parts.append(f"timestamp: {ts_col}")
    return {
        "thresholds": {
            "min_rows_per_side": QA_MIN_ROWS_PER_SIDE,
            "min_window_coverage_ratio": QA_MIN_WINDOW_COVERAGE_RATIO,
            "max_abs_offset_seconds": QA_MAX_ABS_OFFSET_SECONDS,
            "max_abs_drift_seconds": QA_MAX_ABS_DRIFT_SECONDS,
        },
        "import_preview": {
            "vendor_profile_requested": str(ftir_summary.get("vendor_profile_requested") or ""),
            "vendor_profile_used": str(ftir_summary.get("vendor_profile_used") or ""),
            "vendor_profile_note": str(ftir_summary.get("vendor_profile_note") or ""),
            "timestamp_column": ts_col,
            "timestamp_candidates": list(ftir_summary.get("timestamp_candidates") or []),
            "suggested_timestamp_column": suggested_ts,
            "configured_column_map": dict(ftir_summary.get("configured_column_map") or {}),
            "effective_column_map": dict(ftir_summary.get("effective_column_map") or {}),
            "column_map_suggestions": dict(ftir_summary.get("column_map_suggestions") or {}),
            "autodetected_columns_used": auto_cols,
            "unresolved_analytes": unresolved,
            "headers": list(ftir_summary.get("headers") or []),
        },
        "row_status_counts": row_status_counts,
        "error_row_count": len(error_rows),
        "warning_row_count": len(warn_rows),
        "blocking_issues": blocking_issues,
        "warnings": warnings,
        "lock_ready": lock_ready,
        "signoff_ready": signoff_ready,
        "summary": " | ".join(summary_parts),
    }


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
    basis = LEGACY_SIGNOFF_BASIS_MAP.get(basis, basis)
    if basis not in ("",) + SIGNOFF_ACCEPTANCE_BASES:
        basis = ""
    return {
        "decision": decision,
        "basis": basis,
        "by": str(block.get("by") or "").strip(),
        "role": str(block.get("role") or "").strip(),
        "iso": str(block.get("iso") or "").strip(),
        "note": str(block.get("note") or "").strip(),
    }


def _derive_acceptance_basis(cfg: Dict[str, Any], method301: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    mode = str(cfg.get("validation_mode") or "METHOD_301_INFORMED_COMPARISON").strip().upper()
    rows = [row for row in list(method301 or []) if isinstance(row, dict)]
    statuses = [str(row.get("overall_status") or "").strip().upper() for row in rows]
    has_pairs = any(int(row.get("paired_window_count") or 0) > 0 for row in rows)
    has_fail = any(status == "FAIL" for status in statuses)
    formal_ready = (
        mode == "METHOD_301_FORMAL"
        and bool(rows)
        and all(
            str(row.get("overall_status") or "").strip().upper() in ("PASS", "PASS_WITH_CORRECTION_FACTOR")
            and int(row.get("paired_window_count") or 0) == 6
            for row in rows
        )
    )
    if formal_ready:
        return {
            "basis": "FORMAL_METHOD_301",
            "recommended_decision": "ACCEPTED",
            "note": "The FTIR comparison package supports formal Method 301 acceptance for the evaluated analytes.",
        }
    if has_pairs and not has_fail:
        return {
            "basis": "METHOD_301_INFORMED_COMPARISON",
            "recommended_decision": "ACCEPTED",
            "note": "The FTIR comparison package supports an informed side-by-side comparison basis only; it should not be described as a formal Method 301 acceptance.",
        }
    return {
        "basis": "NOT_ACCEPTED",
        "recommended_decision": "REJECTED",
        "note": "The FTIR comparison package does not support an accepted validation basis for this dataset.",
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
    vendor = str(block.get("ftir_vendor_profile") or "AUTO").strip().upper() or "AUTO"
    if vendor not in FTIR_VENDOR_PROFILES:
        vendor = "AUTO"
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
        "ftir_vendor_profile": vendor,
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
    requested_vendor = str(cfg.get("ftir_vendor_profile") or "AUTO").strip().upper() or "AUTO"
    out_rows: List[Dict[str, Any]] = []
    header_keys: set[str] = set()
    summary = {
        "status": "Gap",
        "path": str(src),
        "exists": src.exists(),
        "record_count": 0,
        "delimiter": None,
        "timestamp_column": str(cfg.get("ftir_timestamp_column") or ""),
        "suggested_timestamp_column": "",
        "timestamp_candidates": [],
        "headers": [],
        "requested_analytes": analytes,
        "vendor_profile_requested": requested_vendor,
        "vendor_profile_used": "",
        "vendor_profile_note": "",
        "configured_column_map": dict(column_map),
        "column_map_suggestions": {},
        "effective_column_map": {},
        "autodetected_columns_used": {},
        "unresolved_analytes": [],
        "analytes_found": [],
        "note": "",
    }
    if not src.exists():
        summary["note"] = "FTIR source file not found."
        return {"rows": out_rows, "summary": summary}

    try:
        if src.suffix.lower() == ".jsonl":
            ts_col = str(cfg.get("ftir_timestamp_column") or "").strip()
            for idx, line in enumerate(src.read_text(encoding="utf-8-sig", errors="replace").splitlines(), start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                header_keys.update([str(key or "").strip() for key in row.keys() if str(key or "").strip()])
                ts_val = row.get(ts_col) if ts_col else None
                if ts_val in (None, ""):
                    guess = _guess_timestamp_column(header_keys)
                    if guess and row.get(guess) not in (None, ""):
                        ts_col = guess
                        summary["timestamp_column"] = guess
                        ts_val = row.get(guess)
                src_dt = _parse_iso_dt(ts_val)
                if src_dt is None:
                    continue
                dt = src_dt + timedelta(seconds=float(cfg.get("time_offset_seconds") or 0.0))
                suggestions = _guess_column_map(header_keys, analytes)
                effective_map = dict(column_map)
                auto_used: Dict[str, str] = {}
                for code in analytes:
                    if code not in effective_map:
                        direct = code if code in row else ""
                        if direct:
                            effective_map[code] = direct
                        elif suggestions.get(code):
                            effective_map[code] = suggestions[code]
                            auto_used[code] = suggestions[code]
                values: Dict[str, float] = {}
                for code in analytes:
                    col = str(effective_map.get(code) or code)
                    fv = _safe_float(row.get(col))
                    if fv is not None:
                        values[code] = fv
                out_rows.append({
                    "source_ts_dt": src_dt,
                    "source_ts_iso": _normalize_iso(src_dt),
                    "ts_dt": dt,
                    "ts_iso": _normalize_iso(dt),
                    "values": values,
                    "row_index": idx,
                })
            headers = sorted(header_keys)
            summary["headers"] = headers
            vendor_used, vendor_note = _resolve_vendor_profile(headers, requested_vendor)
            summary["vendor_profile_used"] = vendor_used
            summary["vendor_profile_note"] = vendor_note
            summary["timestamp_candidates"] = [
                col for col in headers if col in COMMON_TS_COLUMNS or _guess_timestamp_column([col]) == col
            ]
            summary["suggested_timestamp_column"] = _guess_timestamp_column(headers)
            if not summary["timestamp_column"]:
                summary["timestamp_column"] = str(summary.get("suggested_timestamp_column") or "")
            suggestions = _guess_column_map(headers, analytes)
            effective_map = dict(column_map)
            auto_used = {}
            for code in analytes:
                if code not in effective_map:
                    direct = code if code in headers else ""
                    if direct:
                        effective_map[code] = direct
                    elif suggestions.get(code):
                        effective_map[code] = suggestions[code]
                        auto_used[code] = suggestions[code]
            summary["column_map_suggestions"] = suggestions
            summary["effective_column_map"] = effective_map
            summary["autodetected_columns_used"] = auto_used
        else:
            delim = _sniff_delimiter(src, str(cfg.get("ftir_delimiter") or "AUTO"))
            summary["delimiter"] = "TSV" if delim == "\t" else delim
            with src.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh, delimiter=delim)
                ts_col = str(cfg.get("ftir_timestamp_column") or "").strip()
                header = list(reader.fieldnames or [])
                summary["headers"] = header
                vendor_used, vendor_note = _resolve_vendor_profile(header, requested_vendor)
                summary["vendor_profile_used"] = vendor_used
                summary["vendor_profile_note"] = vendor_note
                summary["timestamp_candidates"] = [
                    col for col in header if col in COMMON_TS_COLUMNS or _guess_timestamp_column([col]) == col
                ]
                suggested_ts = _guess_timestamp_column(header)
                if not suggested_ts and vendor_used != "GENERIC":
                    vendor_ts_hint = _find_header_match(header, (VENDOR_TIMESTAMP_HINTS.get(vendor_used, {}).get("timestamp") or []))
                    if vendor_ts_hint:
                        suggested_ts = vendor_ts_hint
                summary["suggested_timestamp_column"] = suggested_ts
                if ts_col and ts_col not in header and "+" not in ts_col:
                    ts_col = ""
                if not ts_col:
                    ts_col = str(summary.get("suggested_timestamp_column") or "")
                summary["timestamp_column"] = ts_col
                suggestions = _guess_column_map(header, analytes)
                effective_map = dict(column_map)
                auto_used = {}
                for code in analytes:
                    if code not in effective_map:
                        direct = code if code in header else ""
                        if direct:
                            effective_map[code] = direct
                        elif suggestions.get(code):
                            effective_map[code] = suggestions[code]
                            auto_used[code] = suggestions[code]
                summary["column_map_suggestions"] = suggestions
                summary["effective_column_map"] = effective_map
                summary["autodetected_columns_used"] = auto_used
                for idx, row in enumerate(reader, start=2):
                    src_dt, ts_used = _parse_vendor_timestamp(row, header, vendor_used, ts_col)
                    if src_dt is None:
                        continue
                    if ts_used and (
                        not summary["timestamp_column"]
                        or "+" in ts_used
                        or str(summary.get("timestamp_column") or "").strip() == str(ts_col or "").strip()
                    ):
                        summary["timestamp_column"] = ts_used
                    dt = src_dt + timedelta(seconds=float(cfg.get("time_offset_seconds") or 0.0))
                    values: Dict[str, float] = {}
                    for code in analytes:
                        col = str(effective_map.get(code) or code)
                        fv = _safe_float(row.get(col))
                        if fv is not None:
                            values[code] = fv
                    out_rows.append({
                        "source_ts_dt": src_dt,
                        "source_ts_iso": _normalize_iso(src_dt),
                        "ts_dt": dt,
                        "ts_iso": _normalize_iso(dt),
                        "values": values,
                        "row_index": idx,
                    })
    except Exception as e:
        summary["status"] = "Gap"
        summary["note"] = f"FTIR ingest failed: {e}"
        return {"rows": [], "summary": summary}

    analytes_found = sorted({code for row in out_rows for code in (row.get("values") or {}).keys()})
    effective_map = dict(summary.get("effective_column_map") or {})
    summary["record_count"] = len(out_rows)
    summary["analytes_found"] = analytes_found
    summary["unresolved_analytes"] = [
        code for code in analytes if str(effective_map.get(code) or "").strip() not in list(summary.get("headers") or [])
    ]
    summary["status"] = "Available" if out_rows else "Gap"
    note_parts = []
    if out_rows:
        note_parts.append("FTIR ingest complete.")
    else:
        note_parts.append("No FTIR rows were parsed.")
    if summary["vendor_profile_used"]:
        note_parts.append(f"Vendor profile: {summary['vendor_profile_used']}.")
    if summary["autodetected_columns_used"]:
        note_parts.append(
            "Auto-detected analyte columns: "
            + ", ".join([f"{code}->{col}" for code, col in sorted((summary.get("autodetected_columns_used") or {}).items())])
        )
    if summary["unresolved_analytes"]:
        note_parts.append(
            "Unresolved analytes: " + ", ".join([str(v) for v in list(summary.get("unresolved_analytes") or [])])
        )
    summary["note"] = " ".join([part for part in note_parts if part])
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
            mole_window_rows = [
                row
                for row in mole_list
                if str(row.get("channel_id") or "").strip().upper() == code
                and isinstance(row.get("ts_dt"), datetime)
                and start_dt <= row["ts_dt"] < end_dt
            ]
            ftir_window_rows = [
                row
                for row in ftir_list
                if isinstance(row.get("ts_dt"), datetime)
                and start_dt <= row["ts_dt"] < end_dt
                and (row.get("values") or {}).get(code) is not None
            ]
            mole_stats = _series_stats(mole_window_rows, value_getter=lambda row: row.get("value"))
            ftir_stats = _series_stats(ftir_window_rows, value_getter=lambda row: (row.get("values") or {}).get(code))
            ftir_source_times = sorted([
                row.get("source_ts_dt")
                for row in ftir_window_rows
                if isinstance(row.get("source_ts_dt"), datetime)
            ])
            ftir_source_first = ftir_source_times[0] if ftir_source_times else None
            ftir_source_last = ftir_source_times[-1] if ftir_source_times else None
            ftir_source_mid = ftir_source_first + ((ftir_source_last - ftir_source_first) / 2) if ftir_source_first and ftir_source_last else None
            window_duration = max(0.0, float((end_dt - start_dt).total_seconds()))
            mole_avg = _mean(mole_stats.get("values") or [])
            ftir_avg = _mean(ftir_stats.get("values") or [])
            row = {
                "run_no": window.get("run_no"),
                "label": window.get("label"),
                "window_start_iso": window.get("window_start_iso"),
                "window_end_iso": window.get("window_end_iso"),
                "window_duration_seconds": window_duration,
                "analyte": code,
                "row_key": _row_key(window.get("run_no"), code, window.get("window_start_iso"), window.get("window_end_iso")),
                "mole_count": int(mole_stats.get("count") or 0),
                "ftir_count": int(ftir_stats.get("count") or 0),
                "mole_avg": mole_avg,
                "ftir_avg": ftir_avg,
                "difference": (mole_avg - ftir_avg) if (mole_avg is not None and ftir_avg is not None) else None,
                "paired": bool(mole_avg is not None and ftir_avg is not None),
                "mole_first_iso": _normalize_iso(mole_stats.get("first_dt")),
                "mole_last_iso": _normalize_iso(mole_stats.get("last_dt")),
                "mole_midpoint_iso": _normalize_iso(mole_stats.get("midpoint_dt")),
                "mole_span_seconds": mole_stats.get("span_seconds"),
                "mole_coverage_ratio": (
                    min(1.0, float(mole_stats.get("span_seconds") or 0.0) / window_duration)
                    if window_duration > 0 and mole_stats.get("span_seconds") is not None
                    else None
                ),
                "ftir_first_iso": _normalize_iso(ftir_stats.get("first_dt")),
                "ftir_last_iso": _normalize_iso(ftir_stats.get("last_dt")),
                "ftir_midpoint_iso": _normalize_iso(ftir_stats.get("midpoint_dt")),
                "ftir_span_seconds": ftir_stats.get("span_seconds"),
                "ftir_coverage_ratio": (
                    min(1.0, float(ftir_stats.get("span_seconds") or 0.0) / window_duration)
                    if window_duration > 0 and ftir_stats.get("span_seconds") is not None
                    else None
                ),
                "ftir_source_first_iso": _normalize_iso(ftir_source_first),
                "ftir_source_last_iso": _normalize_iso(ftir_source_last),
                "ftir_source_midpoint_iso": _normalize_iso(ftir_source_mid),
                "offset_seconds_raw": _time_delta_seconds(ftir_source_mid, mole_stats.get("midpoint_dt")),
                "offset_seconds_adjusted": _time_delta_seconds(ftir_stats.get("midpoint_dt"), mole_stats.get("midpoint_dt")),
                "drift_seconds_raw": (
                    (_time_delta_seconds(ftir_source_last, mole_stats.get("last_dt")) or 0.0)
                    - (_time_delta_seconds(ftir_source_first, mole_stats.get("first_dt")) or 0.0)
                    if ftir_source_first and ftir_source_last and mole_stats.get("first_dt") and mole_stats.get("last_dt")
                    else None
                ),
                "drift_seconds_adjusted": (
                    (_time_delta_seconds(ftir_stats.get("last_dt"), mole_stats.get("last_dt")) or 0.0)
                    - (_time_delta_seconds(ftir_stats.get("first_dt"), mole_stats.get("first_dt")) or 0.0)
                    if ftir_stats.get("first_dt") and ftir_stats.get("last_dt") and mole_stats.get("first_dt") and mole_stats.get("last_dt")
                    else None
                ),
                "status": (
                    "PAIRED"
                    if (mole_avg is not None and ftir_avg is not None)
                    else ("MISSING_MOLE" if ftir_avg is not None else ("MISSING_FTIR" if mole_avg is not None else "NO_DATA"))
                ),
            }
            qa_status, qa_flags = _row_qa_eval(row)
            row["qa_status"] = qa_status
            row["qa_flags"] = qa_flags
            out.append(row)
    return out


def build_comparison_sets(
    cfg: Dict[str, Any],
    windows: Iterable[Dict[str, Any]],
    aligned_rows: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    mode = str(cfg.get("validation_mode") or "METHOD_301_INFORMED_COMPARISON").strip().upper()
    review_locked = bool(cfg.get("review_locked"))
    signoff = dict(cfg.get("signoff") or {}) if isinstance(cfg.get("signoff"), dict) else {}
    signoff_decision = str(signoff.get("decision") or "UNSIGNED").strip().upper() or "UNSIGNED"

    def _set_key(window: Dict[str, Any]) -> str:
        return "|".join([
            str(window.get("run_no") or "").strip(),
            str(window.get("window_start_iso") or "").strip(),
            str(window.get("window_end_iso") or "").strip(),
        ])

    aligned_list = [row for row in list(aligned_rows or []) if isinstance(row, dict)]
    set_map: Dict[str, Dict[str, Any]] = {}
    ordered_keys: List[str] = []
    for idx, window in enumerate(list(windows or []), start=1):
        if not isinstance(window, dict):
            continue
        key = _set_key(window)
        if not key or key in set_map:
            continue
        ordered_keys.append(key)
        set_map[key] = {
            "set_no": idx,
            "set_key": key,
            "run_no": window.get("run_no"),
            "label": window.get("label"),
            "window_start_iso": window.get("window_start_iso"),
            "window_end_iso": window.get("window_end_iso"),
            "source": window.get("source"),
            "validation_mode": mode,
            "review_state": (
                "SIGNED_OFF"
                if signoff_decision in ("ACCEPTED", "REJECTED")
                else ("LOCKED_REVIEW" if review_locked else "LIVE_REVIEW")
            ),
            "analyte_rows": [],
        }

    for row in aligned_list:
        key = "|".join([
            str(row.get("run_no") or "").strip(),
            str(row.get("window_start_iso") or "").strip(),
            str(row.get("window_end_iso") or "").strip(),
        ])
        if key not in set_map:
            ordered_keys.append(key)
            set_map[key] = {
                "set_no": len(ordered_keys),
                "set_key": key,
                "run_no": row.get("run_no"),
                "label": row.get("label"),
                "window_start_iso": row.get("window_start_iso"),
                "window_end_iso": row.get("window_end_iso"),
                "source": "ALIGNED_ROWS",
                "validation_mode": mode,
                "review_state": (
                    "SIGNED_OFF"
                    if signoff_decision in ("ACCEPTED", "REJECTED")
                    else ("LOCKED_REVIEW" if review_locked else "LIVE_REVIEW")
                ),
                "analyte_rows": [],
            }
        row_view = {
            "row_key": row.get("row_key"),
            "analyte": row.get("analyte"),
            "paired": bool(row.get("paired")),
            "excluded": bool(row.get("excluded")),
            "exclusion_reason": row.get("exclusion_reason"),
            "reviewer": row.get("reviewer"),
            "updated_iso": row.get("updated_iso"),
            "qa_status": row.get("qa_status"),
            "qa_flags": list(row.get("qa_flags") or []),
            "mole_count": row.get("mole_count"),
            "ftir_count": row.get("ftir_count"),
            "mole_avg": row.get("mole_avg"),
            "ftir_avg": row.get("ftir_avg"),
            "difference": row.get("difference"),
            "offset_seconds_adjusted": row.get("offset_seconds_adjusted"),
            "drift_seconds_adjusted": row.get("drift_seconds_adjusted"),
            "mole_coverage_ratio": row.get("mole_coverage_ratio"),
            "ftir_coverage_ratio": row.get("ftir_coverage_ratio"),
            "status": row.get("status"),
        }
        set_map[key]["analyte_rows"].append(row_view)

    out: List[Dict[str, Any]] = []
    for key in ordered_keys:
        block = set_map.get(key)
        if not isinstance(block, dict):
            continue
        analyte_rows = list(block.get("analyte_rows") or [])
        included_rows = [row for row in analyte_rows if not bool(row.get("excluded"))]
        paired_rows = [row for row in analyte_rows if bool(row.get("paired"))]
        included_paired_rows = [row for row in included_rows if bool(row.get("paired"))]
        excluded_rows = [row for row in analyte_rows if bool(row.get("excluded"))]
        error_rows = [
            row for row in included_rows
            if str(row.get("qa_status") or "").strip().upper() == "ERROR"
        ]
        warn_rows = [
            row for row in included_rows
            if str(row.get("qa_status") or "").strip().upper() == "WARN"
        ]
        analytes = sorted({str(row.get("analyte") or "").strip().upper() for row in analyte_rows if str(row.get("analyte") or "").strip()})
        paired_analytes = sorted({str(row.get("analyte") or "").strip().upper() for row in included_paired_rows if str(row.get("analyte") or "").strip()})
        excluded_analytes = sorted({str(row.get("analyte") or "").strip().upper() for row in excluded_rows if str(row.get("analyte") or "").strip()})

        if not analyte_rows:
            inclusion_status = "NO_ROWS"
        elif included_paired_rows and not excluded_rows and len(included_paired_rows) == len(analyte_rows):
            inclusion_status = "INCLUDED"
        elif excluded_rows and len(excluded_rows) == len(analyte_rows):
            inclusion_status = "EXCLUDED"
        elif included_paired_rows:
            inclusion_status = "MIXED"
        else:
            inclusion_status = "NO_DATA"

        if included_paired_rows:
            formal_basis = "FORMAL_COMPARISON_SET" if mode == "METHOD_301_FORMAL" else "INFORMED_COMPARISON_SET"
        else:
            formal_basis = "NO_COMPARISON_BASIS"

        note_parts: List[str] = []
        if included_paired_rows:
            note_parts.append(f"{len(included_paired_rows)} included paired analyte row(s)")
        if excluded_rows:
            note_parts.append(f"{len(excluded_rows)} excluded analyte row(s)")
        if error_rows:
            note_parts.append(f"{len(error_rows)} included row(s) with QA errors")
        elif warn_rows:
            note_parts.append(f"{len(warn_rows)} included row(s) with QA warnings")
        block["analytes"] = analytes
        block["paired_analytes"] = paired_analytes
        block["excluded_analytes"] = excluded_analytes
        block["row_count"] = len(analyte_rows)
        block["paired_row_count"] = len(paired_rows)
        block["included_row_count"] = len(included_rows)
        block["included_paired_row_count"] = len(included_paired_rows)
        block["excluded_row_count"] = len(excluded_rows)
        block["error_row_count"] = len(error_rows)
        block["warning_row_count"] = len(warn_rows)
        block["inclusion_status"] = inclusion_status
        block["formal_basis"] = formal_basis
        block["note"] = "; ".join(note_parts) if note_parts else "No analyte comparison rows in this set."
        out.append(block)

        for row in analyte_rows:
            row_key = str(row.get("row_key") or "").strip()
            for source_row in aligned_list:
                if str(source_row.get("row_key") or "").strip() != row_key:
                    continue
                source_row["comparison_set_no"] = block["set_no"]
                source_row["comparison_set_key"] = block["set_key"]
                source_row["comparison_set_status"] = block["inclusion_status"]
                source_row["comparison_set_basis"] = block["formal_basis"]
                break
    return out


def compute_method301_stats(cfg: Dict[str, Any], comparison_sets: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mode = str(cfg.get("validation_mode") or "METHOD_301_INFORMED_COMPARISON").strip().upper()
    set_list = [dict(row) for row in list(comparison_sets or []) if isinstance(row, dict)]
    analytes = sorted({
        str(analyte or "").strip().upper()
        for row in set_list
        for analyte in list(row.get("analytes") or [])
        if str(analyte or "").strip()
    })
    out: List[Dict[str, Any]] = []
    for code in analytes:
        analyte_rows_all = [
            dict(analyte_row, set_no=row.get("set_no"), set_key=row.get("set_key"))
            for row in set_list
            for analyte_row in list(row.get("analyte_rows") or [])
            if str(analyte_row.get("analyte") or "").strip().upper() == code
        ]
        pairs_all = [row for row in analyte_rows_all if bool(row.get("paired"))]
        pairs = [row for row in pairs_all if not bool(row.get("excluded"))]
        mole_vals = [float(row.get("mole_avg")) for row in pairs if row.get("mole_avg") is not None]
        ftir_vals = [float(row.get("ftir_avg")) for row in pairs if row.get("ftir_avg") is not None]
        diffs = [float(row.get("difference")) for row in pairs if row.get("difference") is not None]
        n = len(diffs)
        comparison_set_count = len({
            str(row.get("set_key") or "")
            for row in analyte_rows_all
            if str(row.get("set_key") or "")
        })
        included_set_count = len({
            str(row.get("set_key") or "")
            for row in pairs
            if str(row.get("set_key") or "")
        })
        excluded_set_count = len({
            str(row.get("set_key") or "")
            for row in pairs_all
            if bool(row.get("excluded")) and str(row.get("set_key") or "")
        })
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
            "comparison_set_count": comparison_set_count,
            "included_comparison_set_count": included_set_count,
            "excluded_comparison_set_count": excluded_set_count,
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
            "comparison_sets": [],
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
    comparison_sets = build_comparison_sets(normalized, windows.get("rows") or [], aligned_rows)
    method301 = compute_method301_stats(normalized, comparison_sets)
    qa = _build_validation_qa(normalized, ftir.get("summary") or {}, mole.get("summary") or {}, windows, aligned_rows, method301)

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

    acceptance = _derive_acceptance_basis(normalized, method301)

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
        "comparison_sets": comparison_sets,
        "comparison_set_count": len(comparison_sets),
        "included_comparison_set_count": len([
            row for row in comparison_sets
            if str(row.get("inclusion_status") or "").strip().upper() in ("INCLUDED", "MIXED")
        ]),
        "excluded_comparison_set_count": len([
            row for row in comparison_sets
            if str(row.get("inclusion_status") or "").strip().upper() == "EXCLUDED"
        ]),
        "excluded_rows": excluded_rows,
        "method301": method301,
        "coverage_note": coverage_note,
        "overall_status": overall,
        "acceptance_basis": acceptance.get("basis"),
        "acceptance_recommended_decision": acceptance.get("recommended_decision"),
        "acceptance_basis_note": acceptance.get("note"),
        "paired_window_count": len([row for row in aligned_rows if bool(row.get("paired"))]),
        "excluded_count": len(excluded_rows),
        "source": "LIVE_COMPUTE",
        "qa": qa,
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
            "comparison_set_no",
            "comparison_set_key",
            "comparison_set_status",
            "comparison_set_basis",
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
            "qa_status",
            "qa_flags",
            "offset_seconds_adjusted",
            "drift_seconds_adjusted",
            "mole_coverage_ratio",
            "ftir_coverage_ratio",
            "excluded",
            "exclusion_reason",
            "reviewer",
            "updated_iso",
        ])
        for row in list(payload.get("aligned_rows") or []):
            if not isinstance(row, dict):
                continue
            w.writerow([
                row.get("comparison_set_no"),
                row.get("comparison_set_key"),
                row.get("comparison_set_status"),
                row.get("comparison_set_basis"),
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
                row.get("qa_status"),
                ";".join([str(v) for v in list(row.get("qa_flags") or []) if str(v or "").strip()]),
                _fmt_num(row.get("offset_seconds_adjusted"), 3),
                _fmt_num(row.get("drift_seconds_adjusted"), 3),
                _fmt_num(row.get("mole_coverage_ratio"), 3),
                _fmt_num(row.get("ftir_coverage_ratio"), 3),
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
            "comparison_set_count",
            "included_comparison_set_count",
            "excluded_comparison_set_count",
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
                row.get("comparison_set_count"),
                row.get("included_comparison_set_count"),
                row.get("excluded_comparison_set_count"),
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
