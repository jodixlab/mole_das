"""mole_package_inbox_db_v1

SQLite-backed index for inbound MOLE session ZIP packages.

Used by: mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py (Packages Inbox tab)

Design goals:
- Fast scan / rescan of a drop folder
- Light metadata extraction from ZIP contents (best-effort)
- Search by free-text across key fields
- Record ingest destination after extraction

Schema is intentionally small and tolerant of missing metadata.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS inbox_packages (
    package_path TEXT PRIMARY KEY,
    package_name TEXT,
    file_size INTEGER,
    mtime INTEGER,
    sha256 TEXT,

    status TEXT DEFAULT 'NEW',              -- NEW | INGESTED | ERROR
    extracted_session_path TEXT,
    indexed_at TEXT,
    ingested_at TEXT,

    day TEXT,
    session_id TEXT,
    run_id TEXT,

    instance_id TEXT,
    serial TEXT,
    asset_tag TEXT,
    site TEXT,
    model TEXT,

    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_inbox_status ON inbox_packages(status);
CREATE INDEX IF NOT EXISTS idx_inbox_day ON inbox_packages(day);
CREATE INDEX IF NOT EXISTS idx_inbox_session_id ON inbox_packages(session_id);
CREATE INDEX IF NOT EXISTS idx_inbox_instance_id ON inbox_packages(instance_id);
CREATE INDEX IF NOT EXISTS idx_inbox_serial ON inbox_packages(serial);
CREATE INDEX IF NOT EXISTS idx_inbox_asset_tag ON inbox_packages(asset_tag);
CREATE INDEX IF NOT EXISTS idx_inbox_site ON inbox_packages(site);
CREATE INDEX IF NOT EXISTS idx_inbox_model ON inbox_packages(model);
"""


def _connect(db_path: Path, busy_timeout_ms: int = 2500) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        con.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)};")
    except Exception:
        pass
    return con


def init_db(db_path: Path, busy_timeout_ms: int = 2500) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path, busy_timeout_ms) as con:
        con.executescript(SCHEMA_SQL)
        con.commit()


def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _read_zip_json(zf: zipfile.ZipFile, candidate_names: List[str]) -> Optional[Dict[str, Any]]:
    for name in candidate_names:
        try:
            with zf.open(name) as fp:
                import json
                return json.loads(fp.read().decode("utf-8", errors="ignore"))
        except KeyError:
            continue
        except Exception:
            continue
    return None


def _extract_metadata(zip_path: Path) -> Dict[str, Any]:
    """Best-effort metadata extraction from known JSON files or filename patterns."""
    meta: Dict[str, Any] = {}

    # Filename heuristics first
    fname = zip_path.name
    # common patterns: YYYY-MM-DD, session uuid-ish, run
    m = re.search(r"(20\d{2}-\d{2}-\d{2})", fname)
    if m:
        meta["day"] = m.group(1)

    # open ZIP and look for known metadata files
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

            # Prefer canonical session_profile.json if present
            cfg = _read_zip_json(zf, [
                "session_profile.json",
                "das_session_config.json",
                "mole_das_configs/das_session_config.json",
                "metadata.json",
                "session_metadata.json",
            ])
            if cfg:
                meta["session_id"] = str(cfg.get("session_id") or cfg.get("metadata", {}).get("session_id") or "").strip() or None
                meta["day"] = str(cfg.get("day") or cfg.get("date") or cfg.get("metadata", {}).get("day") or meta.get("day") or "").strip() or None

                proj = cfg.get("project") or cfg.get("metadata") or {}
                # try multiple keys (tolerant)
                meta["site"] = str(proj.get("site") or proj.get("site_name") or proj.get("siteName") or "").strip() or None
                meta["asset_tag"] = str(proj.get("asset_tag") or proj.get("asset_id") or proj.get("asset") or "").strip() or None
                meta["model"] = str(proj.get("model") or proj.get("model_name") or proj.get("source_category") or "").strip() or None

                # hardware identity: instance_id / serial
                hw = cfg.get("hardware") or {}
                meta["instance_id"] = str(hw.get("instance_id") or hw.get("instanceId") or "").strip() or None
                meta["serial"] = str(hw.get("serial") or hw.get("serial_number") or hw.get("serialNumber") or "").strip() or None

            # If still missing, try manifest / evidence contract
            if not meta.get("session_id"):
                manifest = _read_zip_json(zf, ["manifest.json", "evidence_manifest.json"])
                if manifest and isinstance(manifest, dict):
                    meta["session_id"] = str(manifest.get("session_id") or manifest.get("sessionId") or "").strip() or None
                    meta["day"] = str(manifest.get("day") or manifest.get("date") or meta.get("day") or "").strip() or None

            # run_id heuristics
            if not meta.get("run_id"):
                for n in names:
                    if n.endswith("run.json") or n.endswith("run_metadata.json"):
                        run = _read_zip_json(zf, [n])
                        if run:
                            meta["run_id"] = str(run.get("run_id") or run.get("runId") or "").strip() or None
                            break

    except Exception:
        # ignore; keep filename heuristics
        pass

    # normalize None / blanks
    for k in list(meta.keys()):
        if meta[k] in ("", None):
            meta.pop(k, None)
    return meta


def index_inbox_dir(
    inbox_dir: Path,
    db_path: Path,
    recursive: bool = True,
    compute_sha: bool = True,
    busy_timeout_ms: int = 2500,
) -> Dict[str, int]:
    """Scan inbox_dir for *.zip and upsert metadata.

    Returns summary: found, indexed, updated, errors
    """
    inbox_dir = Path(inbox_dir)
    db_path = Path(db_path)
    init_db(db_path, busy_timeout_ms=busy_timeout_ms)

    zips: List[Path] = []
    if recursive:
        zips = list(inbox_dir.rglob("*.zip"))
    else:
        zips = list(inbox_dir.glob("*.zip"))

    summ = {"found": len(zips), "indexed": 0, "updated": 0, "errors": 0}

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    with _connect(db_path, busy_timeout_ms) as con:
        for zp in zips:
            try:
                stat = zp.stat()
                pkg_path = str(zp.resolve())
                pkg_name = zp.name
                file_size = int(stat.st_size)
                mtime = int(stat.st_mtime)

                row = con.execute(
                    "SELECT file_size, mtime, sha256, status, extracted_session_path FROM inbox_packages WHERE package_path=?",
                    (pkg_path,),
                ).fetchone()

                sha = None
                if compute_sha:
                    # compute only if new or changed
                    if row is None or int(row["file_size"]) != file_size or int(row["mtime"]) != mtime or not row["sha256"]:
                        sha = _sha256_file(zp)
                    else:
                        sha = row["sha256"]

                # extract metadata (best-effort)
                meta = _extract_metadata(zp)

                # if already ingested, keep that status/path
                status = (row["status"] if row else "NEW") or "NEW"
                extracted_session_path = (row["extracted_session_path"] if row else None)

                con.execute(
                    """INSERT INTO inbox_packages (
                        package_path, package_name, file_size, mtime, sha256,
                        status, extracted_session_path, indexed_at,
                        day, session_id, run_id, instance_id, serial, asset_tag, site, model, notes
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(package_path) DO UPDATE SET
                        package_name=excluded.package_name,
                        file_size=excluded.file_size,
                        mtime=excluded.mtime,
                        sha256=excluded.sha256,
                        indexed_at=excluded.indexed_at,
                        day=COALESCE(excluded.day, inbox_packages.day),
                        session_id=COALESCE(excluded.session_id, inbox_packages.session_id),
                        run_id=COALESCE(excluded.run_id, inbox_packages.run_id),
                        instance_id=COALESCE(excluded.instance_id, inbox_packages.instance_id),
                        serial=COALESCE(excluded.serial, inbox_packages.serial),
                        asset_tag=COALESCE(excluded.asset_tag, inbox_packages.asset_tag),
                        site=COALESCE(excluded.site, inbox_packages.site),
                        model=COALESCE(excluded.model, inbox_packages.model)
                    """,
                    (
                        pkg_path, pkg_name, file_size, mtime, sha,
                        status, extracted_session_path, now_iso,
                        meta.get("day"), meta.get("session_id"), meta.get("run_id"),
                        meta.get("instance_id"), meta.get("serial"), meta.get("asset_tag"),
                        meta.get("site"), meta.get("model"), None
                    ),
                )
                if row is None:
                    summ["indexed"] += 1
                else:
                    summ["updated"] += 1
            except Exception:
                summ["errors"] += 1
        con.commit()

    return summ


def query_packages(
    db_path: Path,
    filter_text: str = "",
    status: str = "ALL",
    limit: int = 200,
    busy_timeout_ms: int = 2500,
) -> List[Dict[str, Any]]:
    db_path = Path(db_path)
    init_db(db_path, busy_timeout_ms=busy_timeout_ms)

    filter_text = (filter_text or "").strip()
    status = (status or "ALL").strip().upper()
    limit = int(limit or 200)

    clauses = []
    params: List[Any] = []

    if status and status != "ALL":
        clauses.append("status=?")
        params.append(status)

    if filter_text:
        like = f"%{filter_text}%"
        clauses.append("(" + " OR ".join([
            "package_name LIKE ?",
            "package_path LIKE ?",
            "COALESCE(day,'') LIKE ?",
            "COALESCE(session_id,'') LIKE ?",
            "COALESCE(run_id,'') LIKE ?",
            "COALESCE(instance_id,'') LIKE ?",
            "COALESCE(serial,'') LIKE ?",
            "COALESCE(asset_tag,'') LIKE ?",
            "COALESCE(site,'') LIKE ?",
            "COALESCE(model,'') LIKE ?",
        ]) + ")")
        params.extend([like]*10)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    sql = f"""SELECT
        package_path, package_name, file_size, mtime, sha256,
        status, extracted_session_path, indexed_at, ingested_at,
        day, session_id, run_id, instance_id, serial, asset_tag, site, model, notes
    FROM inbox_packages
    {where}
    ORDER BY mtime DESC
    LIMIT {limit}
    """

    with _connect(db_path, busy_timeout_ms) as con:
        rows = con.execute(sql, params).fetchall()

    return [dict(r) for r in rows]


def get_by_path(db_path: Path, package_path: Path, busy_timeout_ms: int = 2500) -> Optional[Dict[str, Any]]:
    db_path = Path(db_path)
    init_db(db_path, busy_timeout_ms=busy_timeout_ms)
    p = str(Path(package_path).resolve())
    with _connect(db_path, busy_timeout_ms) as con:
        row = con.execute("SELECT * FROM inbox_packages WHERE package_path=?", (p,)).fetchone()
        return dict(row) if row else None


def mark_ingested(db_path: Path, package_path: Path, extracted_session_path: str, busy_timeout_ms: int = 2500) -> None:
    db_path = Path(db_path)
    init_db(db_path, busy_timeout_ms=busy_timeout_ms)
    p = str(Path(package_path).resolve())
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    with _connect(db_path, busy_timeout_ms) as con:
        con.execute(
            """UPDATE inbox_packages
               SET status='INGESTED', extracted_session_path=?, ingested_at=?
               WHERE package_path=?""",
            (str(extracted_session_path), now_iso, p),
        )
        con.commit()
