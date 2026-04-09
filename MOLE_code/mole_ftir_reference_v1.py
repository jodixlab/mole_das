"""Optional MG2000 FTIR PRN ingest for reference/audit comparisons.

This module is intentionally conservative:
- It never blocks primary acquisition.
- It reads the latest MG2000 `.prn` file from a configured file or folder.
- It auto-detects common delimited tabular formats (tab/comma/semicolon/pipe/whitespace).
- It extracts the latest numeric row and maps known analyte columns into canonical keys.

The parser is designed to be configurable enough for field use, while staying safe when
no sample PRN is available yet. Column overrides can be supplied when MG2000 uses site-
specific names (for example `VOC=THC; NOX=NOX_CORR`).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import mole_ftir_method_worksteps_v1 as mole_ftir_methods
except Exception:
    mole_ftir_methods = None


DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "provider": "MG2000_FTIR_PRN",
    "role": "AUDIT",
    "prn_path": "",
    "file_pattern": "*.prn",
    "recursive": False,
    "freshness_s": 120.0,
    "column_overrides": {},
    "units_overrides": {},
    "method_standard": "ASTM_D6348_12",
}

DEFAULT_UNITS: Dict[str, str] = {
    "O2": "%",
    "CO2": "%",
    "H2O": "%",
    "RH": "%",
    "CO": "ppm",
    "NO": "ppm",
    "NO2": "ppm",
    "NOX": "ppm",
    "VOC": "ppm",
    "THC": "ppm",
    "CH4": "ppm",
    "SO2": "ppm",
    "NH3": "ppm",
    "HCL": "ppm",
}

ALIASES: Dict[str, tuple[str, ...]] = {
    "O2": ("O2_PCT_DRY", "O2_DRY", "O2_PCT_WET", "O2_WET", "O2", "OXYGEN"),
    "CO2": ("CO2_PCT_DRY", "CO2_DRY", "CO2_PCT_WET", "CO2_WET", "CO2_PCT", "CO2", "CARBON_DIOXIDE"),
    "CO": ("CO_PPM_DRY", "CO_DRY", "CO_WET", "CO_500_191C_1OF2", "CO", "CARBON_MONOXIDE"),
    "NO": ("NO_DRY", "NO_WET", "NO_350_3000_191C", "NO", "NITRIC_OXIDE"),
    "NO2": ("NO2_DRY", "NO2_WET", "NO2_150_191C_SPAN", "NO2", "NITROGEN_DIOXIDE"),
    "NOX": ("NOX_DRY", "NOX_TOTAL_DRY", "NOX_AS_NO2_DRY", "NOX", "NO_X", "NOX_AS_NO2", "NOX_TOTAL", "TOTAL_NOX"),
    "VOC": ("VOC_DRY_AS_PROPANE", "VOC_C3_MASS_BASIS_DRY", "VOC_AS_PROPANE", "VOC", "NMHC", "NMOG"),
    "THC": ("THC_DRY_AS_PROPANE", "THC_C3_MASS_BASIS_DRY", "THC", "TOTAL_HC", "TOTAL_HYDROCARBONS"),
    "CH4": ("METHANE_DRY", "CH4_DRY", "CH4_3000_191C", "CH4", "METHANE"),
    "SO2": ("SO2_DRY", "SO2_WET", "SO2", "SULFUR_DIOXIDE"),
    "NH3": ("NH3_DRY", "NH3_WET", "NH3_3000_191C_2OF2", "NH3_300_191C_1OF2", "NH3", "AMMONIA"),
    "H2O": ("H2O_PCT", "H2O_PCT_DRY", "H2O_PCT_WET", "H2O_PCT_40_191C", "H2O_WET", "H2O", "WATER", "MOISTURE"),
    "HCL": ("HCL", "HYDROGEN_CHLORIDE"),
}


def _now_iso() -> str:
    try:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    except Exception:
        return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_key(text: Any) -> str:
    s = str(text or "").strip().upper()
    s = s.replace("%", " PCT ")
    s = re.sub(r"[^A-Z0-9]+", "_", s)
    return s.strip("_")


def _parse_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            return None
        s = s.replace(",", "")
        m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
        if not m:
            return None
        return float(m.group(0))
    except Exception:
        return None


def parse_overrides_text(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for part in re.split(r"[;\n]+", str(text or "").strip()):
        if "=" not in part:
            continue
        left, right = part.split("=", 1)
        canon = _normalize_key(left)
        source = str(right or "").strip()
        if canon and source:
            out[canon] = source
    return out


def format_overrides_text(overrides: Dict[str, Any]) -> str:
    if not isinstance(overrides, dict):
        return ""
    parts = []
    for canon in sorted(overrides.keys()):
        source = str(overrides.get(canon) or "").strip()
        if canon and source:
            parts.append(f"{canon}={source}")
    return "; ".join(parts)


def normalize_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(DEFAULT_CONFIG)
    if isinstance(cfg, dict):
        out.update(cfg)
    out["enabled"] = bool(out.get("enabled"))
    out["provider"] = str(out.get("provider") or DEFAULT_CONFIG["provider"]).strip() or DEFAULT_CONFIG["provider"]
    role = str(out.get("role") or DEFAULT_CONFIG["role"]).strip().upper()
    out["role"] = role if role in ("AUDIT", "REFERENCE") else DEFAULT_CONFIG["role"]
    out["prn_path"] = str(out.get("prn_path") or "").strip()
    out["file_pattern"] = str(out.get("file_pattern") or "*.prn").strip() or "*.prn"
    out["recursive"] = bool(out.get("recursive"))
    try:
        out["freshness_s"] = max(0.0, float(out.get("freshness_s") or 0.0))
    except Exception:
        out["freshness_s"] = float(DEFAULT_CONFIG["freshness_s"])
    out["column_overrides"] = dict(out.get("column_overrides") or {})
    out["units_overrides"] = dict(out.get("units_overrides") or {})
    if mole_ftir_methods is not None:
        try:
            out["method_standard"] = mole_ftir_methods.normalize_method(out.get("method_standard"))
        except Exception:
            out["method_standard"] = str(DEFAULT_CONFIG["method_standard"])
    else:
        out["method_standard"] = str(out.get("method_standard") or DEFAULT_CONFIG["method_standard"]).strip() or DEFAULT_CONFIG["method_standard"]
    return out


def _split_line(line: str, delimiter: str) -> list[str]:
    if delimiter == "WS":
        text = str(line or "").strip()
        if not text:
            return []
        # Preserve unit-bearing headers like "CO ppm" by only treating repeated whitespace
        # as a column break when we are in generic fixed-width mode.
        parts = re.split(r"\s{2,}", text)
    else:
        parts = str(line or "").split(delimiter)
    return [str(p or "").strip() for p in parts]


def _detect_delimiter(line: str) -> str:
    text = str(line or "")
    best = ("", 0)
    for delim in ("\t", ",", ";", "|"):
        if delim not in text:
            continue
        count = len(_split_line(text, delim))
        if count > best[1]:
            best = (delim, count)
    if best[1] >= 2:
        return best[0]
    ws_count = len(_split_line(text, "WS"))
    if ws_count >= 2:
        return "WS"
    return best[0] or "WS"


def _infer_units(header_text: str, canonical: str, overrides: Dict[str, Any]) -> str:
    override = str((overrides or {}).get(canonical) or "").strip()
    if override:
        return override
    norm = _normalize_key(header_text)
    if "PPM" in norm:
        return "ppm"
    if "PPB" in norm:
        return "ppb"
    if "PCT" in norm or "PERCENT" in norm or "%" in str(header_text or ""):
        return "%"
    return DEFAULT_UNITS.get(canonical, "")


def _resolve_source_path(cfg: Dict[str, Any]) -> Optional[Path]:
    raw = str(cfg.get("prn_path") or "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    if any(ch in raw for ch in "*?["):
        parent = p.parent if str(p.parent) not in ("", ".") else Path.cwd()
        pattern = p.name or str(cfg.get("file_pattern") or "*.prn")
        matches = sorted(parent.glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True)
        return matches[0] if matches else None
    if p.is_dir():
        pattern = str(cfg.get("file_pattern") or "*.prn").strip() or "*.prn"
        iterator = p.rglob(pattern) if bool(cfg.get("recursive")) else p.glob(pattern)
        matches = sorted((m for m in iterator if m.is_file()), key=lambda x: x.stat().st_mtime, reverse=True)
        return matches[0] if matches else None
    if p.is_file():
        return p
    return None


def _read_text(path: Path) -> str:
    last_err: Optional[Exception] = None
    for enc in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except Exception as exc:
            last_err = exc
    if last_err is not None:
        raise last_err
    return path.read_text()


def _match_columns(header: list[str], cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    norm_header = [_normalize_key(h) for h in header]
    overrides = dict(cfg.get("column_overrides") or {})
    units_overrides = dict(cfg.get("units_overrides") or {})

    for canonical, source_name in overrides.items():
        canon = _normalize_key(canonical)
        source_norm = _normalize_key(source_name)
        if not canon or not source_norm:
            continue
        for idx, hdr_norm in enumerate(norm_header):
            if hdr_norm == source_norm:
                out[canon] = {
                    "index": idx,
                    "header": header[idx],
                    "units": _infer_units(header[idx], canon, units_overrides),
                    "source": "override",
                }
                break

    for canonical, aliases in ALIASES.items():
        if canonical in out:
            continue
        ordered_aliases = [_normalize_key(a) for a in aliases]
        found = False
        for alias_norm in ordered_aliases:
            for idx, hdr_norm in enumerate(norm_header):
                if hdr_norm == alias_norm:
                    out[canonical] = {
                        "index": idx,
                        "header": header[idx],
                        "units": _infer_units(header[idx], canonical, units_overrides),
                        "source": "auto",
                    }
                    found = True
                    break
            if found:
                break
    return out


def _find_header_and_row(lines: list[str], cfg: Dict[str, Any]) -> tuple[Optional[int], Optional[str], list[str], Optional[int], list[str]]:
    best: tuple[float, Optional[int], Optional[str], list[str]] = (-1.0, None, None, [])
    search_limit = min(len(lines), 60)

    for idx in range(search_limit):
        delim = _detect_delimiter(lines[idx])
        header = _split_line(lines[idx], delim)
        if len(header) < 2:
            continue
        mapping = _match_columns(header, cfg)
        alias_hits = len(mapping)
        alpha_hits = sum(1 for cell in header if re.search(r"[A-Za-z]", cell or ""))
        data_rows = 0
        for j in range(idx + 1, min(len(lines), idx + 8)):
            row = _split_line(lines[j], delim)
            numeric = sum(1 for cell in row if _parse_float(cell) is not None)
            if numeric >= 2:
                data_rows += 1
        score = (alias_hits * 100.0) + (data_rows * 10.0) + alpha_hits - (idx * 0.05)
        if score > best[0]:
            best = (score, idx, delim, header)

    _, header_idx, delim, header = best
    if header_idx is None or delim is None or not header:
        return None, None, [], None, []

    row_idx: Optional[int] = None
    row_cells: list[str] = []
    for idx in range(len(lines) - 1, header_idx, -1):
        cells = _split_line(lines[idx], delim)
        numeric = sum(1 for cell in cells if _parse_float(cell) is not None)
        if numeric >= 2:
            row_idx = idx
            row_cells = cells
            break
    return header_idx, delim, header, row_idx, row_cells


def snapshot_frame_fields(snapshot: Dict[str, Any], prefix: str = "REF") -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    if not isinstance(snapshot, dict):
        return fields
    pfx = str(prefix or "REF").strip().upper()
    fields[f"{pfx}_STATUS"] = str(snapshot.get("status") or "")
    fields[f"{pfx}_ROLE"] = str(snapshot.get("role") or "")
    fields[f"{pfx}_SOURCE_PATH"] = str(snapshot.get("source_path") or "")
    fields[f"{pfx}_AGE_S"] = snapshot.get("age_s")
    fields[f"{pfx}_SOURCE_MTIME_ISO"] = str(snapshot.get("source_mtime_iso") or "")
    fields[f"{pfx}_SOURCE_SHA256"] = str(snapshot.get("source_sha256") or "")
    for canonical, rec in (snapshot.get("measurements") or {}).items():
        fields[f"{pfx}_{canonical}"] = rec.get("value")
        fields[f"{pfx}_{canonical}_UNITS"] = rec.get("units")
    return fields


class MG2000PrnIngestor:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = normalize_config(config or {})
        self._cache_key = ""
        self._cache_snapshot: Optional[Dict[str, Any]] = None

    def configure(self, config: Dict[str, Any]) -> None:
        self._config = normalize_config(config or {})
        self._cache_key = ""

    def read_snapshot(self) -> Dict[str, Any]:
        cfg = normalize_config(self._config)
        base: Dict[str, Any] = {
            "ok": False,
            "status": "DISABLED" if not cfg.get("enabled") else "IDLE",
            "provider": str(cfg.get("provider") or DEFAULT_CONFIG["provider"]),
            "role": str(cfg.get("role") or DEFAULT_CONFIG["role"]),
            "source_path": "",
            "source_mtime_iso": "",
            "source_sha256": "",
            "source_bytes": None,
            "age_s": None,
            "header_index": None,
            "row_index": None,
            "delimiter": "",
            "measurements": {},
            "notes": [],
            "updated_value_count": 0,
            "ts_iso": _now_iso(),
            "error": "",
        }
        if not cfg.get("enabled"):
            return base

        src = _resolve_source_path(cfg)
        if src is None:
            base["status"] = "MISSING"
            base["error"] = "Configured PRN path was not found."
            return base

        stat = src.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).astimezone()
        age_s = max(0.0, datetime.now(timezone.utc).timestamp() - stat.st_mtime)
        base["source_path"] = str(src)
        base["source_mtime_iso"] = mtime.isoformat(timespec="seconds")
        base["source_bytes"] = int(stat.st_size)
        base["age_s"] = age_s

        cache_key = json.dumps(
            {
                "path": str(src),
                "mtime_ns": getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)),
                "size": stat.st_size,
                "cfg": cfg,
            },
            sort_keys=True,
            default=str,
        )
        if cache_key == self._cache_key and isinstance(self._cache_snapshot, dict):
            snap = dict(self._cache_snapshot)
            snap["age_s"] = age_s
            snap["ts_iso"] = _now_iso()
            if cfg.get("freshness_s") and age_s > float(cfg["freshness_s"]):
                snap["status"] = "STALE"
                snap["ok"] = False
            return snap

        try:
            text = _read_text(src)
        except Exception as exc:
            base["status"] = "READ_FAIL"
            base["error"] = str(exc)
            return base

        try:
            base["source_sha256"] = _sha256_file(src)
        except Exception:
            base["source_sha256"] = ""

        lines = [line.rstrip("\r\n") for line in text.splitlines() if str(line or "").strip()]
        if not lines:
            base["status"] = "EMPTY"
            return base

        header_idx, delim, header, row_idx, row_cells = _find_header_and_row(lines, cfg)
        if header_idx is None or delim is None or not header or row_idx is None or not row_cells:
            base["status"] = "PARSE_FAIL"
            base["error"] = "Could not identify a tabular header/data row in the PRN file."
            return base

        mapping = _match_columns(header, cfg)
        measures: Dict[str, Dict[str, Any]] = {}
        for canonical, meta in mapping.items():
            idx = int(meta.get("index"))
            if idx >= len(row_cells):
                continue
            value = _parse_float(row_cells[idx])
            if value is None:
                continue
            measures[canonical] = {
                "value": float(value),
                "units": str(meta.get("units") or DEFAULT_UNITS.get(canonical, "")).strip(),
                "source_column": str(meta.get("header") or ""),
                "mapping_source": str(meta.get("source") or ""),
            }

        base["measurements"] = measures
        base["header_index"] = int(header_idx)
        base["row_index"] = int(row_idx)
        base["delimiter"] = {
            "\t": "TAB",
            ",": "COMMA",
            ";": "SEMICOLON",
            "|": "PIPE",
            "WS": "WHITESPACE",
        }.get(delim, str(delim or ""))
        base["updated_value_count"] = len(measures)
        base["status"] = "OK" if measures else "NO_MATCH"
        base["ok"] = bool(measures)

        freshness_s = float(cfg.get("freshness_s") or 0.0)
        if freshness_s > 0 and age_s > freshness_s:
            base["status"] = "STALE"
            base["ok"] = False

        self._cache_key = cache_key
        self._cache_snapshot = dict(base)
        return base
