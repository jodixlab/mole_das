"""MOLE DAS CSV Export Utilities (v1)

Goals:
 - Provide dependency-free CSV export for UI "tabs" (wizard states).
 - Provide a one-click "export full package" that writes multiple CSVs into a folder.

Design notes:
 - Exports are best-effort. If a dataset isn't present, the CSV is still created with a note.
 - Caller controls destination folder (training vs production).
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import mole_ftir_reference_v1 as mole_ftir_reference
except Exception:
    mole_ftir_reference = None


def _safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _csv_safe(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, (int, float, str)):
        return v
    try:
        return json.dumps(v, ensure_ascii=False)
    except Exception:
        return str(v)


def write_kv_csv(path: str, kv: Dict[str, Any], header: Tuple[str, str] = ("key", "value")) -> None:
    _safe_mkdir(os.path.dirname(path) or ".")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(list(header))
        for k in sorted((kv or {}).keys()):
            v = kv.get(k)
            if isinstance(v, (dict, list)):
                try:
                    v = json.dumps(v, ensure_ascii=False)
                except Exception:
                    v = str(v)
            w.writerow([k, v])


def write_rows_csv(path: str, rows: Sequence[Dict[str, Any]], fieldnames: Optional[Sequence[str]] = None) -> None:
    _safe_mkdir(os.path.dirname(path) or ".")
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["note"])
            w.writerow(["no rows"])
        return

    if fieldnames is None:
        keys = set()
        for r in rows:
            keys.update((r or {}).keys())
        fieldnames = sorted(keys)

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _csv_safe((r or {}).get(k)) for k in fieldnames})


def flatten_dict(d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (d or {}).items():
        kk = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            out.update(flatten_dict(v, kk))
        else:
            out[kk] = v
    return out


def _reference_cfg_from_session(session: Dict[str, Any]) -> Dict[str, Any]:
    cfg = session.get("reference_audit")
    if not isinstance(cfg, dict):
        runner = session.get("daq_runner") if isinstance(session.get("daq_runner"), dict) else {}
        cfg = runner.get("reference_audit") if isinstance(runner.get("reference_audit"), dict) else {}
    if mole_ftir_reference is not None:
        try:
            return mole_ftir_reference.normalize_config(cfg if isinstance(cfg, dict) else {})
        except Exception:
            pass
    out = dict(cfg if isinstance(cfg, dict) else {})
    out.setdefault("enabled", False)
    out.setdefault("provider", "MG2000_FTIR_PRN")
    out.setdefault("role", "AUDIT")
    out.setdefault("prn_path", "")
    out.setdefault("file_pattern", "*.prn")
    out.setdefault("recursive", False)
    out.setdefault("freshness_s", 120.0)
    out.setdefault("column_overrides", {})
    out.setdefault("units_overrides", {})
    return out


def _reference_cfg_seeded(cfg: Dict[str, Any]) -> bool:
    if not isinstance(cfg, dict):
        return False
    return bool(
        cfg.get("enabled")
        or cfg.get("prn_path")
        or cfg.get("column_overrides")
        or cfg.get("units_overrides")
    )


def _spike_cfg_from_session(session: Dict[str, Any]) -> Dict[str, Any]:
    daq = session.get("daq_runner") if isinstance(session.get("daq_runner"), dict) else {}
    for candidate in (
        daq.get("spike_recovery"),
        session.get("spike_recovery"),
    ):
        if isinstance(candidate, dict):
            return dict(candidate)
    return {}


def _spike_state_from_session(session: Dict[str, Any]) -> Dict[str, Any]:
    daq = session.get("daq_runner") if isinstance(session.get("daq_runner"), dict) else {}
    ws = daq.get("worksteps") if isinstance(daq.get("worksteps"), dict) else {}
    state = ws.get("spike_recovery")
    return dict(state) if isinstance(state, dict) else {}


def export_sqlite_all_tables(db_path: str, out_dir: str) -> List[str]:
    """Dump all tables in a sqlite database into CSVs."""
    written: List[str] = []
    if not db_path or not os.path.exists(db_path):
        return written

    _safe_mkdir(out_dir)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        for t in tables:
            rows = cur.execute(f"SELECT * FROM {t}").fetchall()
            cols = [c[0] for c in cur.description] if cur.description else []
            csv_path = os.path.join(out_dir, f"{os.path.basename(db_path)}__{t}.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                for r in rows:
                    w.writerow(list(r))
            written.append(csv_path)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return written


@dataclass
class ExportResult:
    out_dir: str
    files: List[str]


def export_wizard_state_csv(current_state: str, session: Dict[str, Any], out_dir: str) -> ExportResult:
    """Export the data for the given wizard UI state into a CSV file."""
    _safe_mkdir(out_dir)
    files: List[str] = []

    st = (current_state or "UNKNOWN").upper()
    base = os.path.join(out_dir, f"wizard_{st.lower()}")

    if st in ("WELCOME",):
        path = base + ".csv"
        write_kv_csv(path, {"state": st, "note": "welcome screen"})
        files.append(path)
        return ExportResult(out_dir, files)

    if st in ("PROJECT", "PROJECT_CONFIGS", "PROJECT_CONFIGS_HUB"):
        path = base + ".csv"
        write_kv_csv(path, flatten_dict(session.get("project", {}), "project"))
        files.append(path)
        return ExportResult(out_dir, files)

    if st in ("EMPIRICAL", "EMPIRICAL_CONDITIONS"):
        emp = session.get("empirical", {})
        path = base + ".csv"
        write_kv_csv(path, flatten_dict(emp, "empirical"))
        files.append(path)
        return ExportResult(out_dir, files)

    if st in ("DBPATHS", "DB_PATHS"):
        path = base + ".csv"
        write_kv_csv(path, flatten_dict(session.get("db_paths", {}), "db_paths"))
        files.append(path)
        return ExportResult(out_dir, files)

    if st in ("GOV", "CATALOG_GOVERNANCE"):
        path = base + ".csv"
        write_kv_csv(path, flatten_dict(session.get("catalog_governance", {}), "catalog_governance"))
        files.append(path)
        return ExportResult(out_dir, files)

    if st in ("SOURCE", "SOURCE_DETAILS"):
        path = base + ".csv"
        write_kv_csv(path, flatten_dict(session.get("source", {}), "source"))
        files.append(path)
        return ExportResult(out_dir, files)

    if st in ("POLLUTANTS",):
        pol = session.get("pollutants", {})
        selected = pol.get("selected", []) or []
        prescriptions = (pol.get("prescriptions") or {})
        rows: List[Dict[str, Any]] = []
        for p in selected:
            pr = prescriptions.get(p, {}) if isinstance(prescriptions, dict) else {}
            row = {"pollutant": p}
            if isinstance(pr, dict):
                row.update(pr)
            rows.append(row)
        path = base + ".csv"
        write_rows_csv(path, rows)
        files.append(path)
        return ExportResult(out_dir, files)

    if st in ("QAQC",):
        qaqc = session.get("qaqc", {})
        path = base + ".csv"
        merged = flatten_dict(qaqc, "qaqc")
        merged.update(flatten_dict(_spike_cfg_from_session(session), "spike_recovery.config"))
        merged.update(flatten_dict(_spike_state_from_session(session), "spike_recovery.state"))
        write_kv_csv(path, merged)
        files.append(path)
        return ExportResult(out_dir, files)

    if st in ("TEST_MATRIX", "TESTMATRIX"):
        tm = session.get("test_matrix", {})
        rows = tm.get("runs", []) if isinstance(tm, dict) else []
        path = base + ".csv"
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            write_rows_csv(path, rows)
        else:
            write_kv_csv(path, flatten_dict(tm, "test_matrix"))
        files.append(path)
        return ExportResult(out_dir, files)

    if st in ("SITE", "SITE_CONDITIONS"):
        sc = session.get("site_conditions", {})
        path = base + ".csv"
        write_kv_csv(path, flatten_dict(sc, "site_conditions"))
        files.append(path)
        return ExportResult(out_dir, files)

    if st in ("REF_AUDIT", "REFERENCE_AUDIT"):
        ref_cfg = _reference_cfg_from_session(session)
        path = base + ".csv"
        write_kv_csv(path, flatten_dict(ref_cfg, "reference_audit"))
        files.append(path)
        return ExportResult(out_dir, files)

    # Fallback
    path = base + ".csv"
    write_kv_csv(path, {"note": "fallback export", **flatten_dict(session, "session")})
    files.append(path)
    return ExportResult(out_dir, files)


def export_full_csv_pack(session: Dict[str, Any], out_root: str, include_sqlite: bool = True) -> ExportResult:
    """Export a multi-CSV package representing the current session + key DB assets."""

    tag = _now_tag()
    out_dir = os.path.join(out_root, f"MOLE_CSV_EXPORT_{tag}")
    _safe_mkdir(out_dir)
    files: List[str] = []

    session_json = os.path.join(out_dir, "session_snapshot.json")
    with open(session_json, "w", encoding="utf-8") as f:
        json.dump(session or {}, f, indent=2, ensure_ascii=False)
    files.append(session_json)

    session_csv = os.path.join(out_dir, "session_snapshot.csv")
    write_kv_csv(session_csv, flatten_dict(session or {}, "session"))
    files.append(session_csv)

    for st in ["PROJECT", "EMPIRICAL", "DBPATHS", "GOV", "SOURCE", "POLLUTANTS", "QAQC", "TEST_MATRIX", "SITE", "REF_AUDIT"]:
        res = export_wizard_state_csv(st, session, out_dir)
        files.extend(res.files)

    spike_cfg = _spike_cfg_from_session(session)
    spike_state = _spike_state_from_session(session)
    if spike_cfg or spike_state:
        spike_summary_csv = os.path.join(out_dir, "spike_recovery_snapshot.csv")
        spike_summary = flatten_dict(spike_cfg, "spike_recovery.config")
        spike_summary.update(flatten_dict({k: v for k, v in spike_state.items() if k != "channels"}, "spike_recovery.state"))
        write_kv_csv(spike_summary_csv, spike_summary)
        files.append(spike_summary_csv)

        channel_rows: List[Dict[str, Any]] = []
        channels = spike_state.get("channels") if isinstance(spike_state.get("channels"), dict) else {}
        for pollutant, rec in sorted(channels.items()):
            if not isinstance(rec, dict):
                continue
            mole_result = rec.get("mole_result") if isinstance(rec.get("mole_result"), dict) else {}
            ftir_result = rec.get("ftir_result") if isinstance(rec.get("ftir_result"), dict) else {}
            channel_rows.append({
                "pollutant": pollutant,
                "units": rec.get("units"),
                "spike_amount": rec.get("spike_amount"),
                "native_mole": rec.get("native_mole"),
                "spike_mole": rec.get("spike_mole"),
                "mole_recovery_pct": mole_result.get("recovery_pct"),
                "mole_status": mole_result.get("status"),
                "native_ftir": rec.get("native_ftir"),
                "spike_ftir": rec.get("spike_ftir"),
                "ftir_recovery_pct": ftir_result.get("recovery_pct"),
                "ftir_status": ftir_result.get("status"),
                "native_timestamp_iso": rec.get("native_timestamp_iso"),
                "spike_timestamp_iso": rec.get("spike_timestamp_iso"),
            })
        spike_channels_csv = os.path.join(out_dir, "spike_recovery_channels.csv")
        write_rows_csv(spike_channels_csv, channel_rows, fieldnames=[
            "pollutant",
            "units",
            "spike_amount",
            "native_mole",
            "spike_mole",
            "mole_recovery_pct",
            "mole_status",
            "native_ftir",
            "spike_ftir",
            "ftir_recovery_pct",
            "ftir_status",
            "native_timestamp_iso",
            "spike_timestamp_iso",
        ])
        files.append(spike_channels_csv)

    ref_cfg = _reference_cfg_from_session(session)
    if _reference_cfg_seeded(ref_cfg):
        ref_cfg_csv = os.path.join(out_dir, "reference_audit_config.csv")
        write_kv_csv(ref_cfg_csv, flatten_dict(ref_cfg, "reference_audit"))
        files.append(ref_cfg_csv)

        if mole_ftir_reference is not None:
            try:
                snapshot = mole_ftir_reference.MG2000PrnIngestor(ref_cfg).read_snapshot()
            except Exception:
                snapshot = None
            if isinstance(snapshot, dict):
                snap_json = os.path.join(out_dir, "reference_audit_snapshot.json")
                with open(snap_json, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, indent=2, ensure_ascii=False)
                files.append(snap_json)

                snap_csv = os.path.join(out_dir, "reference_audit_snapshot.csv")
                snap_meta = dict(snapshot)
                snap_meta.pop("measurements", None)
                write_kv_csv(snap_csv, flatten_dict(snap_meta, "reference_audit_snapshot"))
                files.append(snap_csv)

                meas_rows: List[Dict[str, Any]] = []
                for code, rec in (snapshot.get("measurements") or {}).items():
                    if not isinstance(rec, dict):
                        continue
                    meas_rows.append({
                        "pollutant": code,
                        "value": rec.get("value"),
                        "units": rec.get("units"),
                        "source_column": rec.get("source_column"),
                        "mapping_source": rec.get("mapping_source"),
                    })
                meas_csv = os.path.join(out_dir, "reference_audit_measurements.csv")
                write_rows_csv(meas_csv, meas_rows, fieldnames=["pollutant", "value", "units", "source_column", "mapping_source"])
                files.append(meas_csv)

    if include_sqlite:
        dbdir = os.path.join(out_dir, "sqlite")
        db_paths: List[str] = []
        dbp = (session or {}).get("db_paths", {})
        if isinstance(dbp, dict):
            for k in ("master_db_path", "session_db_path", "master_db", "db"):
                v = dbp.get(k)
                if isinstance(v, str) and v.lower().endswith(".sqlite"):
                    db_paths.append(v)
        for p in db_paths:
            try:
                files.extend(export_sqlite_all_tables(p, dbdir))
            except Exception:
                continue

    return ExportResult(out_dir, files)
