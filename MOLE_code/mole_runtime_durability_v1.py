from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _slug(value: str, default: str = "snapshot") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._-")
    return text or default


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{_utc_stamp()}")
    try:
        tmp.write_text(text, encoding=encoding)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def atomic_write_json(path: Path, payload: Dict[str, Any], *, encoding: str = "utf-8") -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False), encoding=encoding)


def rotate_dir_entries(directory: Path, pattern: str, *, keep: int) -> None:
    if keep <= 0:
        keep = 1
    items = sorted(directory.glob(pattern), key=lambda p: p.name.lower(), reverse=True)
    for old in items[keep:]:
        try:
            if old.is_dir():
                for child in old.rglob("*"):
                    if child.is_file():
                        child.unlink(missing_ok=True)
                old.rmdir()
            else:
                old.unlink(missing_ok=True)
        except Exception:
            pass


def write_recovery_snapshot(
    payload: Dict[str, Any],
    snapshot_dir: Path,
    *,
    label: str,
    keep: int = 20,
) -> Path:
    snapshot_dir = Path(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    base = _slug(label)
    out = snapshot_dir / f"{base}__{_utc_stamp()}.json"
    atomic_write_json(out, payload)
    rotate_dir_entries(snapshot_dir, f"{base}__*.json", keep=keep)
    return out


def backup_sqlite_database(
    db_path: Path,
    backup_dir: Path,
    *,
    label: str,
    keep: int = 10,
) -> Optional[Path]:
    db_path = Path(db_path)
    if not db_path.exists():
        return None
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    base = _slug(label, default="sqlite_backup")
    out = backup_dir / f"{base}__{_utc_stamp()}.sqlite"

    src = None
    dst = None
    try:
        src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        dst = sqlite3.connect(str(out))
        with dst:
            src.backup(dst)
    finally:
        if dst is not None:
            try:
                dst.close()
            except Exception:
                pass
        if src is not None:
            try:
                src.close()
            except Exception:
                pass

    rotate_dir_entries(backup_dir, f"{base}__*.sqlite", keep=keep)
    return out
