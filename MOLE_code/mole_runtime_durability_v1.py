from __future__ import annotations

import json
import os
import re
import sqlite3
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


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


def latest_matching_path(directory: Path, pattern: str) -> Optional[Path]:
    directory = Path(directory)
    if not directory.exists():
        return None
    matches = sorted(directory.glob(pattern), key=lambda p: p.name.lower(), reverse=True)
    return matches[0] if matches else None


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


def create_support_bundle(
    bundle_root: Path,
    *,
    label: str,
    manifest: Dict[str, Any],
    artifacts: Mapping[str, Optional[Path]],
    keep: int = 10,
) -> Path:
    bundle_root = Path(bundle_root)
    bundle_root.mkdir(parents=True, exist_ok=True)
    base = _slug(label, default="support_bundle")
    bundle_dir = bundle_root / f"{base}__{_utc_stamp()}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    copied: Dict[str, Dict[str, Any]] = {}
    for name, source in artifacts.items():
        src = Path(source).expanduser() if source is not None else None
        if src is None or not src.exists() or not src.is_file():
            copied[str(name)] = {"source": str(source) if source is not None else "", "copied": False}
            continue
        safe_name = _slug(str(name), default="artifact")
        dest = bundle_dir / f"{safe_name}{src.suffix}"
        shutil.copy2(src, dest)
        copied[str(name)] = {
            "source": str(src),
            "copied": True,
            "bundle_path": str(dest),
        }

    manifest_payload = dict(manifest or {})
    manifest_payload.setdefault("created_utc", datetime.now(timezone.utc).isoformat())
    manifest_payload["artifacts"] = copied
    manifest_path = bundle_dir / "support_bundle_manifest.json"
    atomic_write_json(manifest_path, manifest_payload)

    zip_path = bundle_root / f"{bundle_dir.name}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(bundle_dir.rglob("*")):
            if item.is_file():
                zf.write(item, item.relative_to(bundle_dir))

    rotate_dir_entries(bundle_root, f"{base}__*.zip", keep=keep)
    rotate_dir_entries(bundle_root, f"{base}__*", keep=keep * 2)
    return zip_path


def record_health_journal(
    journal_dir: Path,
    *,
    label: str,
    event: str,
    payload: Dict[str, Any],
    keep_lines: int = 200,
) -> Dict[str, Path]:
    journal_dir = Path(journal_dir)
    journal_dir.mkdir(parents=True, exist_ok=True)
    base = _slug(label, default="health_journal")
    latest_path = journal_dir / f"{base}__latest.json"
    history_path = journal_dir / f"{base}__history.jsonl"

    latest_payload: Dict[str, Any] = {}
    if latest_path.exists():
        try:
            latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
        except Exception:
            latest_payload = {}
    latest_payload.update(dict(payload or {}))
    latest_payload["last_event"] = str(event or "").strip().upper() or "UPDATE"
    latest_payload["updated_utc"] = datetime.now(timezone.utc).isoformat()
    atomic_write_json(latest_path, latest_payload)

    entry = {
        "event": latest_payload["last_event"],
        "ts_utc": latest_payload["updated_utc"],
        "payload": dict(payload or {}),
    }
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    try:
        lines = history_path.read_text(encoding="utf-8").splitlines()
        if len(lines) > keep_lines:
            atomic_write_text(history_path, "\n".join(lines[-keep_lines:]) + "\n")
    except Exception:
        pass

    return {"latest": latest_path, "history": history_path}


def load_latest_health_summary(journal_dir: Path, *, label: str) -> Dict[str, Any]:
    journal_dir = Path(journal_dir)
    latest_path = journal_dir / f"{_slug(label, default='health_journal')}__latest.json"
    if not latest_path.exists():
        return {}
    try:
        payload = json.loads(latest_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def load_recent_health_history(journal_dir: Path, *, label: str, limit: int = 10) -> list[Dict[str, Any]]:
    journal_dir = Path(journal_dir)
    history_path = journal_dir / f"{_slug(label, default='health_journal')}__history.jsonl"
    if not history_path.exists():
        return []
    try:
        rows = []
        for line in history_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
        return rows[-max(int(limit), 1):]
    except Exception:
        return []


def write_startup_diagnostic(
    log_dir: Path,
    *,
    label: str,
    payload: Dict[str, Any],
    keep: int = 20,
) -> Dict[str, Path]:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    base = _slug(label, default="startup_diagnostic")
    ts = _utc_stamp()
    stamped_path = log_dir / f"{base}__{ts}.json"
    latest_path = log_dir / f"{base}__latest.json"

    record = dict(payload or {})
    record.setdefault("schema", "mole_startup_diagnostic_v1")
    record.setdefault("recorded_utc", datetime.now(timezone.utc).isoformat())

    atomic_write_json(stamped_path, record)
    atomic_write_json(latest_path, record)
    rotate_dir_entries(log_dir, f"{base}__*.json", keep=max(int(keep), 2))
    return {"latest": latest_path, "stamped": stamped_path}
