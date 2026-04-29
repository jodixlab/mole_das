from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import shutil
import sys
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

try:
    import winreg
except Exception:
    winreg = None


_UTC_STAMP_LOCK = threading.Lock()
_UTC_STAMP_LAST_BASE = ""
_UTC_STAMP_SEQ = 0
DATA_ROOT_MANIFEST_SCHEMA = "mole_data_root_manifest_v1"
DATA_ROOT_SCHEMA_VERSION = "2026_04_29_v1"


def _utc_stamp() -> str:
    global _UTC_STAMP_LAST_BASE, _UTC_STAMP_SEQ
    base = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    with _UTC_STAMP_LOCK:
        if base == _UTC_STAMP_LAST_BASE:
            _UTC_STAMP_SEQ += 1
        else:
            _UTC_STAMP_LAST_BASE = base
            _UTC_STAMP_SEQ = 0
        return f"{base}{_UTC_STAMP_SEQ:03d}Z"


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


def _safe_path(path_value: Any) -> Optional[Path]:
    text = str(path_value or "").strip()
    if not text:
        return None
    try:
        return Path(text).expanduser().resolve()
    except Exception:
        try:
            return Path(text).expanduser()
        except Exception:
            return None


def _load_json_dict(path_value: Any) -> Dict[str, Any]:
    path = path_value if isinstance(path_value, Path) else _safe_path(path_value)
    if not isinstance(path, Path) or not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _sha256_file(path_value: Any) -> str:
    path = path_value if isinstance(path_value, Path) else _safe_path(path_value)
    if not isinstance(path, Path) or not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
    except Exception:
        return ""
    return digest.hexdigest().upper()


def _normalize_hash_map(raw_value: Any) -> Dict[str, str]:
    if not isinstance(raw_value, Mapping):
        return {}
    normalized: Dict[str, str] = {}
    for key, value in raw_value.items():
        name = str(key or "").strip()
        if not name:
            continue
        normalized[name] = str(value or "").strip().upper()
    return normalized


def _path_is_same_or_child(path: Path, root: Path) -> bool:
    try:
        path_r = path.resolve()
        root_r = root.resolve()
        return path_r == root_r or path_r.is_relative_to(root_r)
    except Exception:
        return False


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except Exception:
        return None


def load_uninstall_registration() -> Dict[str, Any]:
    if winreg is None:
        return {}
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\MOLE_DAS"
    fields = {
        "DisplayName": "display_name",
        "DisplayVersion": "display_version",
        "InstallLocation": "install_location",
        "Publisher": "publisher",
        "DisplayIcon": "display_icon",
        "UninstallString": "uninstall_string",
        "QuietUninstallString": "quiet_uninstall_string",
        "InstallDate": "install_date",
    }
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            record: Dict[str, Any] = {"registry_key": f"HKCU\\{key_path}"}
            for src, dest in fields.items():
                try:
                    value, _ = winreg.QueryValueEx(key, src)
                except Exception:
                    continue
                text = str(value or "").strip()
                if text:
                    record[dest] = text
            return record
    except Exception:
        return {}


def _package_root_from_runtime_root(runtime_root: Path) -> Path:
    runtime_root = Path(runtime_root).resolve()
    if runtime_root.name.strip().lower() == "runtime":
        return runtime_root.parent.resolve()
    return runtime_root


def _copy_file_if_missing(source: Path, destination: Path) -> None:
    source = Path(source)
    destination = Path(destination)
    if not source.exists() or not source.is_file() or destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_tree_if_missing(source: Path, destination: Path) -> None:
    source = Path(source)
    destination = Path(destination)
    if not source.exists() or not source.is_dir():
        return
    for item in sorted(source.rglob("*"), key=lambda p: str(p).lower()):
        rel = item.relative_to(source)
        target = destination / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def _runtime_env_is_training(env_mode: Any) -> bool:
    text = str(env_mode or "").strip().upper()
    return text in {"TRAINING", "SIM_TRAINING", "SIMTRAINING", "TRAIN"}


def _runtime_seed_config_sources(seed_root: Path, *, training: bool) -> list[Path]:
    seed_root = Path(seed_root).resolve()
    sources: list[Path] = []
    direct = seed_root / "configs"
    if direct.exists():
        sources.append(direct)
    if training:
        nested = seed_root / "training" / "configs"
        if nested.exists():
            sources.append(nested)
    return sources


def _path_has_payload(path: Path) -> bool:
    path = Path(path)
    if not path.exists():
        return False
    if path.is_file():
        return True
    try:
        return any(item.is_file() for item in path.rglob("*"))
    except Exception:
        return False


def _copy_tree_backup(source: Path, destination: Path) -> int:
    source = Path(source)
    destination = Path(destination)
    if not source.exists():
        return 0
    copied = 0
    for item in sorted(source.rglob("*"), key=lambda p: str(p).lower()):
        rel = item.relative_to(source)
        target = destination / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        copied += 1
    return copied


def _remove_tree_payload(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return
    if path.is_file():
        path.unlink(missing_ok=True)
        return
    shutil.rmtree(path, ignore_errors=True)


def _data_root_manifest_path(layout: Mapping[str, Any]) -> Path:
    return (Path(layout.get("data_root") or "") / "data_root_manifest_v1.json").resolve()


def _data_root_migration_backup_root(layout: Mapping[str, Any]) -> Path:
    return (Path(layout.get("backups_dir") or "") / "migrations").resolve()


def _migrate_legacy_packaged_runtime_data(layout: Mapping[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "performed": False,
        "backup_path": "",
        "migrated_labels": [],
        "migrated_source_paths": [],
        "migrated_target_paths": [],
        "removed_source_paths": [],
    }
    if not bool(layout.get("packaged_layout")):
        return result

    seed_root = Path(layout.get("seed_root") or "")
    if not seed_root.exists():
        return result

    mappings = [
        ("logs", seed_root / "logs", Path(layout.get("logs_dir") or "")),
        ("backups", seed_root / "backups", Path(layout.get("backups_dir") or "")),
        ("sessions", seed_root / "sessions", Path(layout.get("sessions_dir") or "")),
        ("daq_runs", seed_root / "daq_runs", Path(layout.get("daq_runs_dir") or "")),
        ("exports", seed_root / "exports", Path(layout.get("exports_dir") or "")),
        ("validation", seed_root / "validation", Path(layout.get("validation_dir") or "")),
        ("inbox_packages", seed_root / "inbox_packages", Path(layout.get("packages_inbox_dir") or "")),
        ("inbox_archive", seed_root / "inbox_archive", Path(layout.get("packages_archive_dir") or "")),
        ("cache", seed_root / "cache", Path(layout.get("cache_dir") or "")),
    ]
    active = [(label, src, dst) for (label, src, dst) in mappings if _path_has_payload(src)]
    if not active:
        return result

    backup_root = _data_root_migration_backup_root(layout) / f"runtime_data_root_migration__{_utc_stamp()}"
    for label, source, destination in active:
        try:
            snapshot_root = backup_root / "legacy_runtime_data" / label
            copied = _copy_tree_backup(source, snapshot_root)
            if source.is_dir():
                _copy_tree_if_missing(source, destination)
            elif source.is_file():
                _copy_file_if_missing(source, destination)
            _remove_tree_payload(source)
            result["performed"] = True
            result["migrated_labels"].append(label)
            result["migrated_source_paths"].append(str(source.resolve()))
            result["migrated_target_paths"].append(str(destination.resolve()))
            result["removed_source_paths"].append(str(source.resolve()))
            if copied > 0:
                result["backup_path"] = str(backup_root.resolve())
        except Exception:
            continue

    if result["backup_path"]:
        atomic_write_json(
            backup_root / "migration_manifest.json",
            {
                "schema": "mole_data_root_migration_backup_v1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data_root": str(Path(layout.get("data_root") or "").resolve()),
                "seed_root": str(seed_root.resolve()),
                "migration": result,
            },
        )
    return result


def _seed_runtime_data_root(layout: Mapping[str, Any]) -> list[str]:
    data_root = Path(layout.get("data_root") or "")
    seed_root = Path(layout.get("seed_root") or "")
    config_root = Path(layout.get("config_root") or "")
    if not data_root:
        return []

    actions: list[str] = []

    for key in (
        "data_root",
        "config_root",
        "logs_dir",
        "backups_dir",
        "sessions_dir",
        "daq_runs_dir",
        "rule_packs_dir",
        "packages_inbox_dir",
        "packages_archive_dir",
        "db_dir",
        "cache_dir",
        "exports_dir",
        "validation_dir",
    ):
        try:
            target = Path(layout.get(key) or "")
            if target:
                existed = target.exists()
                target.mkdir(parents=True, exist_ok=True)
                if not existed:
                    actions.append(f"mkdir:{key}")
        except Exception:
            continue

    for db_name in ("mole_master.sqlite", "mole_packages_inbox.sqlite"):
        try:
            target = Path(layout.get("db_dir") or "") / db_name
            existed = target.exists()
            _copy_file_if_missing(seed_root / "db" / db_name, target)
            if (not existed) and target.exists():
                actions.append(f"seed_db:{db_name}")
        except Exception:
            continue

    try:
        target = Path(layout.get("rule_packs_dir") or "")
        existed = target.exists()
        _copy_tree_if_missing(seed_root / "rule_packs", target)
        if (not existed) and target.exists():
            actions.append("seed_rule_packs")
    except Exception:
        pass

    for source_dir in _runtime_seed_config_sources(
        seed_root,
        training=bool(layout.get("training")),
    ):
        try:
            for item in sorted(source_dir.rglob("*"), key=lambda p: str(p).lower()):
                rel = item.relative_to(source_dir)
                target = config_root / rel
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if item.name.lower().startswith("mole_config"):
                    continue
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
                actions.append(f"seed_config:{rel.as_posix()}")
        except Exception:
            continue
    return actions


def ensure_runtime_data_root(layout: Mapping[str, Any]) -> Dict[str, Any]:
    migration = _migrate_legacy_packaged_runtime_data(layout)
    repair_actions = _seed_runtime_data_root(layout)
    manifest_path = _data_root_manifest_path(layout)
    previous = _load_json_dict(manifest_path)
    previous_migration = previous.get("migration")
    if (
        isinstance(previous_migration, Mapping)
        and bool(previous_migration.get("performed"))
        and not bool(migration.get("performed"))
    ):
        migration = dict(previous_migration)
    build_identity = _load_json_dict(Path(layout.get("runtime_root") or "") / "config" / "mole_build_identity_v1.json")
    created_utc = str(previous.get("created_utc") or datetime.now(timezone.utc).isoformat())
    payload: Dict[str, Any] = {
        "schema": DATA_ROOT_MANIFEST_SCHEMA,
        "data_schema_version": DATA_ROOT_SCHEMA_VERSION,
        "created_utc": created_utc,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "package_label": str(build_identity.get("bundle_label") or previous.get("package_label") or ""),
        "git_commit": str(build_identity.get("git_commit") or previous.get("git_commit") or ""),
        "git_branch": str(build_identity.get("git_branch") or previous.get("git_branch") or ""),
        "packaged_layout": bool(layout.get("packaged_layout")),
        "training": bool(layout.get("training")),
        "env_mode": str(layout.get("env_mode") or ""),
        "package_root": str(Path(layout.get("package_root") or "").resolve()),
        "runtime_root": str(Path(layout.get("runtime_root") or "").resolve()),
        "seed_root": str(Path(layout.get("seed_root") or "").resolve()),
        "immutable_runtime_data_root": str(Path(layout.get("immutable_runtime_data_root") or "").resolve()),
        "data_root": str(Path(layout.get("data_root") or "").resolve()),
        "config_root": str(Path(layout.get("config_root") or "").resolve()),
        "db_path": str(Path(layout.get("db_path") or "").resolve()),
        "logs_dir": str(Path(layout.get("logs_dir") or "").resolve()),
        "exports_dir": str(Path(layout.get("exports_dir") or "").resolve()),
        "validation_dir": str(Path(layout.get("validation_dir") or "").resolve()),
        "migration": migration,
        "repair_actions": repair_actions,
    }
    atomic_write_json(manifest_path, payload)
    return payload


def resolve_runtime_storage_layout(
    runtime_base_dir: Path,
    *,
    env_mode: str = "PRODUCTION",
    seed_if_missing: bool = False,
) -> Dict[str, Any]:
    code_root = Path(runtime_base_dir).resolve()
    runtime_root = code_root.parent.resolve()
    package_root = _package_root_from_runtime_root(runtime_root)
    training = _runtime_env_is_training(env_mode)
    frozen = bool(getattr(sys, "frozen", False))
    packaged_layout = frozen or runtime_root.name.strip().lower() == "runtime"
    seed_root = (runtime_root / "mole_das_data" / ("training" if training else "")).resolve()
    data_root = ((package_root / "data") / ("training" if training else "")).resolve() if packaged_layout else seed_root
    config_name = "mole_config_training.json" if training else "mole_config.json"
    layout: Dict[str, Any] = {
        "frozen": frozen,
        "packaged_layout": packaged_layout,
        "training": training,
        "env_mode": "TRAINING" if training else "PRODUCTION",
        "code_root": code_root,
        "runtime_root": runtime_root,
        "package_root": package_root,
        "seed_root": seed_root,
        "immutable_runtime_data_root": (runtime_root / "mole_das_data").resolve(),
        "data_root": data_root,
        "config_root": (data_root / "configs").resolve(),
        "config_path": (data_root / "configs" / config_name).resolve(),
        "logs_dir": (data_root / "logs").resolve(),
        "backups_dir": (data_root / "backups").resolve(),
        "sessions_dir": (data_root / "sessions").resolve(),
        "daq_runs_dir": (data_root / "daq_runs").resolve(),
        "rule_packs_dir": (data_root / "rule_packs").resolve(),
        "packages_inbox_dir": (data_root / "inbox_packages").resolve(),
        "packages_archive_dir": (data_root / "inbox_archive").resolve(),
        "db_dir": (data_root / "db").resolve(),
        "db_path": (data_root / "db" / "mole_master.sqlite").resolve(),
        "package_index_db_path": (data_root / "db" / "mole_packages_inbox.sqlite").resolve(),
        "cache_dir": (data_root / "cache").resolve(),
        "exports_dir": (data_root / "exports").resolve(),
        "validation_dir": (data_root / "validation").resolve(),
        "assets_dir": (runtime_root / "mole_assets").resolve(),
        "data_root_manifest_path": (data_root / "data_root_manifest_v1.json").resolve(),
    }
    if seed_if_missing:
        ensure_runtime_data_root(layout)
    return layout


def resolve_runtime_storage_layout_from_root(
    runtime_root: Path,
    *,
    env_mode: str = "PRODUCTION",
    seed_if_missing: bool = False,
) -> Dict[str, Any]:
    runtime_root = Path(runtime_root).resolve()
    code_root = runtime_root / "MOLE_code"
    if not code_root.exists():
        code_root = runtime_root
    return resolve_runtime_storage_layout(code_root, env_mode=env_mode, seed_if_missing=seed_if_missing)


def _first_existing_path(*paths: Path) -> Optional[Path]:
    for path in paths:
        try:
            if isinstance(path, Path) and path.exists():
                return path.resolve()
        except Exception:
            continue
    return None


def _package_acceptance_paths(package_root: Optional[Path]) -> Dict[str, Optional[Path]]:
    root = _safe_path(package_root)
    if not isinstance(root, Path):
        return {"text": None, "json": None}
    return {
        "text": _first_existing_path(
            root / "PACKAGED_ACCEPTANCE_SUMMARY.txt",
            root / "_acceptance_artifacts" / "packaged_acceptance_summary.txt",
        ),
        "json": _first_existing_path(
            root / "PACKAGED_ACCEPTANCE_SUMMARY.json",
            root / "_acceptance_artifacts" / "packaged_acceptance_summary.json",
        ),
    }


def _package_build_identity_path(package_root: Optional[Path]) -> Optional[Path]:
    root = _safe_path(package_root)
    if not isinstance(root, Path):
        return None
    return _first_existing_path(
        root / "runtime" / "config" / "mole_build_identity_v1.json",
        root / "config" / "mole_build_identity_v1.json",
    )


def _package_installer_targets(package_root: Optional[Path]) -> Dict[str, Optional[Path]]:
    root = _safe_path(package_root)
    if not isinstance(root, Path):
        return {"script": None, "bundle": None}
    script = _first_existing_path(
        root / "INSTALL_MOLE_DAS_EXE_BUNDLE.bat",
        root / "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1",
    )
    bundle = None
    try:
        bundle_candidates = sorted(root.glob("*_installer_exe_bundle.zip"), key=lambda p: p.name.lower(), reverse=True)
        bundle = bundle_candidates[0].resolve() if bundle_candidates else None
    except Exception:
        bundle = None
    return {"script": script, "bundle": bundle}


def _runtime_executable_targets(runtime_root: Optional[Path]) -> Dict[str, Optional[Path]]:
    root = _safe_path(runtime_root)
    if not isinstance(root, Path):
        return {"wizard": None, "runner": None}
    code_root = root / "MOLE_code"
    return {
        "wizard": _first_existing_path(code_root / "MOLE_DAS_Wizard.exe"),
        "runner": _first_existing_path(code_root / "MOLE_DAQ_Runner.exe"),
    }


def _package_sort_ts(identity: Mapping[str, Any], acceptance: Mapping[str, Any]) -> Optional[datetime]:
    return (
        _parse_iso_datetime(identity.get("built_at"))
        or _parse_iso_datetime(acceptance.get("generated_at"))
        or _parse_iso_datetime(acceptance.get("built_at"))
    )


def _resolve_manifest_path(
    manifest_path: Optional[Path],
    raw_value: Any,
    *,
    root_fallback: Optional[Path] = None,
) -> Optional[Path]:
    text = str(raw_value or "").strip()
    if not text:
        return None
    try:
        candidate = Path(text)
    except Exception:
        return None
    base = None
    if not candidate.is_absolute():
        if isinstance(root_fallback, Path):
            base = root_fallback
        elif isinstance(manifest_path, Path):
            base = manifest_path.parent
        if isinstance(base, Path):
            candidate = base / candidate
    try:
        return candidate.resolve()
    except Exception:
        return candidate


def _normalize_verified_release_manifest(
    manifest_path: Optional[Path],
    payload: Mapping[str, Any],
    *,
    root_fallback: Optional[Path] = None,
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    schema = str(payload.get("schema") or "").strip()
    if schema != "mole_latest_verified_release_v1":
        return {}
    package_root = _resolve_manifest_path(
        manifest_path,
        payload.get("package_root"),
        root_fallback=root_fallback,
    )
    if not isinstance(package_root, Path) and isinstance(root_fallback, Path):
        try:
            package_root = root_fallback.resolve()
        except Exception:
            package_root = root_fallback
    return {
        "manifest_path": manifest_path.resolve() if isinstance(manifest_path, Path) else None,
        "manifest_kind": str(payload.get("manifest_kind") or "").strip(),
        "channel_name": str(payload.get("channel_name") or "LOCAL_VERIFIED").strip() or "LOCAL_VERIFIED",
        "generated_at": str(payload.get("generated_at") or "").strip(),
        "package_root": package_root,
        "package_label": str(payload.get("package_label") or "").strip(),
        "acceptance_text_path": _resolve_manifest_path(
            manifest_path,
            payload.get("acceptance_summary_path"),
            root_fallback=package_root,
        ),
        "acceptance_json_path": _resolve_manifest_path(
            manifest_path,
            payload.get("acceptance_summary_json_path"),
            root_fallback=package_root,
        ),
        "acceptance_status": str(payload.get("acceptance_status") or "").strip().upper(),
        "installer_script_path": _resolve_manifest_path(
            manifest_path,
            payload.get("installer_script_path"),
            root_fallback=package_root,
        ),
        "version_audit_json_path": _resolve_manifest_path(
            manifest_path,
            payload.get("version_audit_json_path"),
            root_fallback=package_root,
        ),
        "version_audit_txt_path": _resolve_manifest_path(
            manifest_path,
            payload.get("version_audit_txt_path"),
            root_fallback=package_root,
        ),
        "launcher_path": _resolve_manifest_path(
            manifest_path,
            payload.get("launcher_path"),
            root_fallback=package_root,
        ),
        "wizard_exe_path": _resolve_manifest_path(
            manifest_path,
            payload.get("wizard_exe_path"),
            root_fallback=package_root,
        ),
        "runner_exe_path": _resolve_manifest_path(
            manifest_path,
            payload.get("runner_exe_path"),
            root_fallback=package_root,
        ),
        "script_runner_exe_path": _resolve_manifest_path(
            manifest_path,
            payload.get("script_runner_exe_path"),
            root_fallback=package_root,
        ),
        "installer_bundle_path": _resolve_manifest_path(
            manifest_path,
            payload.get("installer_bundle_path"),
            root_fallback=package_root,
        ),
        "portable_bundle_path": _resolve_manifest_path(
            manifest_path,
            payload.get("portable_bundle_path"),
            root_fallback=package_root,
        ),
        "build_identity_path": _resolve_manifest_path(
            manifest_path,
            payload.get("build_identity_path"),
            root_fallback=package_root,
        ),
        "git_commit": str(payload.get("git_commit") or "").strip(),
        "git_branch": str(payload.get("git_branch") or "").strip(),
        "built_at": str(payload.get("built_at") or "").strip(),
        "hashes": _normalize_hash_map(payload.get("hashes") or {}),
    }


def _latest_verified_release_manifest_candidates(
    current_package_root: Optional[Path],
    install_root: Optional[Path],
) -> list[Path]:
    roots: list[Optional[Path]] = []
    current_root = _safe_path(current_package_root)
    installed_root = _safe_path(install_root)
    if isinstance(installed_root, Path):
        roots.extend([installed_root.parent, installed_root])
    if isinstance(current_root, Path):
        roots.extend([current_root.parent, current_root])
    seen: set[str] = set()
    candidates: list[Path] = []
    for base in roots:
        if not isinstance(base, Path):
            continue
        try:
            candidate = (base / "latest_verified_release_v1.json").resolve()
        except Exception:
            candidate = base / "latest_verified_release_v1.json"
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return candidates


def _load_latest_verified_release(
    current_package_root: Optional[Path],
    install_root: Optional[Path],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "manifest_path": None,
        "manifest_kind": "",
        "channel_name": "",
        "generated_at": "",
        "package_root": None,
        "package_label": "",
        "acceptance_text_path": None,
        "acceptance_json_path": None,
        "acceptance_status": "",
        "installer_script_path": None,
        "installer_bundle_path": None,
        "portable_bundle_path": None,
        "build_identity_path": None,
        "git_commit": "",
        "git_branch": "",
        "built_at": "",
    }
    current_root = _safe_path(current_package_root)
    installed_root = _safe_path(install_root)
    for manifest_path in _latest_verified_release_manifest_candidates(current_root, installed_root):
        payload = _load_json_dict(manifest_path)
        normalized = _normalize_verified_release_manifest(
            manifest_path,
            payload,
            root_fallback=(manifest_path.parent if manifest_path.name.lower() == "latest_verified_release_v1.json" else None),
        )
        if normalized and str(normalized.get("acceptance_status") or "").upper() == "PASS":
            return normalized

    search_root = current_root.parent if isinstance(current_root, Path) else None
    fallback = _find_latest_verified_package(search_root)
    if str(fallback.get("acceptance_status") or "").strip().upper() == "PASS":
        result.update(
            {
                "manifest_kind": "fallback_search",
                "channel_name": "LOCAL_HEURISTIC",
                "package_root": fallback.get("package_root"),
                "package_label": str(fallback.get("package_label") or "").strip(),
                "acceptance_text_path": fallback.get("acceptance_text_path"),
                "acceptance_json_path": fallback.get("acceptance_json_path"),
                "acceptance_status": "PASS",
                "installer_script_path": fallback.get("installer_script_path"),
                "installer_bundle_path": fallback.get("installer_bundle_path"),
            }
        )
    return result


def _find_latest_verified_package(search_root: Optional[Path]) -> Dict[str, Any]:
    root = _safe_path(search_root)
    result: Dict[str, Any] = {
        "package_root": None,
        "package_label": "",
        "acceptance_text_path": None,
        "acceptance_json_path": None,
        "acceptance_status": "",
        "installer_script_path": None,
        "installer_bundle_path": None,
    }
    if not isinstance(root, Path) or not root.exists() or not root.is_dir():
        return result

    best_key: tuple[str, str] | None = None
    for child in root.iterdir():
        try:
            if not child.is_dir():
                continue
            child_name = child.name.strip()
            if not child_name or "mole_das" not in child_name.lower():
                continue
            acceptance_paths = _package_acceptance_paths(child)
            acceptance_json = acceptance_paths.get("json")
            acceptance = _load_json_dict(acceptance_json)
            if str(acceptance.get("status") or "").strip().upper() != "PASS":
                continue
            identity = _load_json_dict(_package_build_identity_path(child))
            ts = _package_sort_ts(identity, acceptance)
            ts_key = ts.isoformat() if isinstance(ts, datetime) else ""
            label = str(identity.get("bundle_label") or acceptance.get("package_label") or child.name).strip()
            sort_key = (ts_key, label.lower())
            if best_key is not None and sort_key <= best_key:
                continue
            installers = _package_installer_targets(child)
            result = {
                "package_root": child.resolve(),
                "package_label": label,
                "acceptance_text_path": acceptance_paths.get("text"),
                "acceptance_json_path": acceptance_json,
                "acceptance_status": "PASS",
                "installer_script_path": installers.get("script"),
                "installer_bundle_path": installers.get("bundle"),
            }
            best_key = sort_key
        except Exception:
            continue
    return result


def evaluate_runtime_package_status(
    *,
    current_runtime_root: Path,
    current_build_identity: Optional[Mapping[str, Any]] = None,
    current_acceptance_summary_path: Optional[Path] = None,
) -> Dict[str, Any]:
    runtime_root = Path(current_runtime_root).resolve()
    current_package_root = _package_root_from_runtime_root(runtime_root)
    build_identity = dict(current_build_identity or {})
    current_acceptance_path = _safe_path(current_acceptance_summary_path)
    current_acceptance = _load_json_dict(current_acceptance_path)
    current_acceptance_status = str(current_acceptance.get("status") or "").strip().upper()
    current_bundle_label = str(
        build_identity.get("bundle_label")
        or current_acceptance.get("package_label")
        or ""
    ).strip()
    current_built_at = _parse_iso_datetime(build_identity.get("built_at"))
    current_identity_runtime_root = _safe_path(build_identity.get("runtime_root"))

    current_install_manifest_path = runtime_root.parent / "mole_install_manifest_v1.json"
    current_install_manifest = _load_json_dict(
        current_install_manifest_path if current_install_manifest_path.exists() else None
    )
    current_install_root = None
    if current_install_manifest:
        current_install_root = _safe_path(current_install_manifest.get("install_root")) or runtime_root.parent.resolve()

    uninstall_registration = load_uninstall_registration()
    registry_install_root = _safe_path(uninstall_registration.get("install_location"))
    local_install_root = registry_install_root or current_install_root

    install_manifest_path = None
    if isinstance(local_install_root, Path):
        candidate = local_install_root / "mole_install_manifest_v1.json"
        if candidate.exists():
            install_manifest_path = candidate.resolve()
    elif current_install_manifest:
        install_manifest_path = current_install_manifest_path.resolve()

    install_manifest = _load_json_dict(install_manifest_path)
    installed_runtime_root = _safe_path(install_manifest.get("runtime_root"))
    if installed_runtime_root is None and isinstance(local_install_root, Path):
        candidate = local_install_root / "runtime"
        if candidate.exists():
            installed_runtime_root = candidate.resolve()

    installed_identity_path = None
    if isinstance(installed_runtime_root, Path):
        candidate = installed_runtime_root / "config" / "mole_build_identity_v1.json"
        if candidate.exists():
            installed_identity_path = candidate.resolve()
    installed_identity = _load_json_dict(installed_identity_path)
    installed_built_at = _parse_iso_datetime(installed_identity.get("built_at"))

    accepted_marker_path = None
    if isinstance(local_install_root, Path):
        for candidate in (
            local_install_root / "PACKAGED_ACCEPTANCE_SUMMARY.json",
            local_install_root / "_acceptance_artifacts" / "packaged_acceptance_summary.json",
        ):
            if candidate.exists():
                accepted_marker_path = candidate.resolve()
                break
    if accepted_marker_path is None and isinstance(current_acceptance_path, Path) and current_acceptance_path.exists():
        accepted_marker_path = current_acceptance_path.resolve()
    accepted_marker = _load_json_dict(accepted_marker_path)
    accepted_bundle_label = str(
        accepted_marker.get("package_label")
        or install_manifest.get("bundle_label")
        or uninstall_registration.get("display_version")
        or ""
    ).strip()

    current_is_installed = bool(isinstance(local_install_root, Path) and _path_is_same_or_child(runtime_root, local_install_root))
    portable_launch = not current_is_installed
    build_identity_runtime_mismatch = bool(
        isinstance(current_identity_runtime_root, Path) and current_identity_runtime_root != runtime_root
    )
    install_manifest_runtime_mismatch = bool(
        current_is_installed and isinstance(installed_runtime_root, Path) and installed_runtime_root != runtime_root
    )
    installed_label_mismatch = bool(
        current_is_installed and accepted_bundle_label and current_bundle_label and accepted_bundle_label != current_bundle_label
    )
    acceptance_missing = not (isinstance(current_acceptance_path, Path) and current_acceptance_path.exists())
    acceptance_failed = bool(current_acceptance and current_acceptance_status and current_acceptance_status != "PASS")

    verified_release = _load_latest_verified_release(current_package_root, local_install_root)
    verified_release_label = str(verified_release.get("package_label") or "").strip()
    verified_release_built_at = _parse_iso_datetime(verified_release.get("built_at"))
    stale_due_to_release_label = bool(
        verified_release_label and current_bundle_label and verified_release_label != current_bundle_label
    )
    stale_due_to_release_time = bool(
        current_built_at is not None and verified_release_built_at is not None and current_built_at < verified_release_built_at
    )
    stale_launch = False
    if stale_due_to_release_label or stale_due_to_release_time:
        stale_launch = True
    elif portable_launch and isinstance(local_install_root, Path):
        if accepted_bundle_label and current_bundle_label and accepted_bundle_label != current_bundle_label:
            stale_launch = True
        elif current_built_at is not None and installed_built_at is not None and current_built_at < installed_built_at:
            stale_launch = True

    details: list[str] = []
    if acceptance_missing:
        details.append("Packaged acceptance summary is missing.")
    elif acceptance_failed:
        details.append(f"Packaged acceptance summary is {current_acceptance_status}, not PASS.")
    if build_identity_runtime_mismatch:
        details.append("Build identity runtime path does not match the running runtime path.")
    if install_manifest_runtime_mismatch:
        details.append("Installed runtime manifest does not match the running runtime path.")
    if installed_label_mismatch:
        details.append("Installed package label does not match the running package label.")
    if stale_launch:
        if stale_due_to_release_label:
            details.append("Running package differs from the latest verified release.")
        elif stale_due_to_release_time:
            details.append("Running package build time is older than the latest verified release.")
        else:
            details.append("Running package differs from the locally installed accepted package.")
    elif portable_launch:
        details.append("Running from a portable folder instead of the installed root.")
    elif current_is_installed:
        details.append("Running from the installed root.")
    else:
        details.append("No installed root was detected on this machine.")

    if acceptance_missing or acceptance_failed or build_identity_runtime_mismatch or install_manifest_runtime_mismatch or installed_label_mismatch:
        status = "UNVERIFIED"
        summary = "Package verification or runtime identity is incomplete."
    elif stale_launch:
        status = "STALE"
        summary = "Running package is older or different than the locally accepted install."
    elif portable_launch:
        status = "PORTABLE"
        summary = "Running from a portable folder instead of the installed root."
    else:
        status = "CURRENT"
        summary = "Installed and verified package matches the local accepted install."

    current_installers = _package_installer_targets(current_package_root)
    latest_verified_search_root = current_package_root.parent if isinstance(current_package_root, Path) else None
    latest_verified = _find_latest_verified_package(latest_verified_search_root)
    installed_executables = _runtime_executable_targets(installed_runtime_root)

    return {
        "package_status": status,
        "package_status_summary": summary,
        "package_status_detail": details[0] if details else summary,
        "package_status_details": details,
        "portable_launch": portable_launch,
        "build_identity_runtime_mismatch": build_identity_runtime_mismatch,
        "install_manifest_runtime_mismatch": install_manifest_runtime_mismatch,
        "installed_label_mismatch": installed_label_mismatch,
        "packaged_acceptance_status": current_acceptance_status,
        "packaged_acceptance_generated_at": str(current_acceptance.get("generated_at") or "").strip(),
        "install_root_path": str(local_install_root) if isinstance(local_install_root, Path) else "",
        "install_manifest_path": str(install_manifest_path) if isinstance(install_manifest_path, Path) else "",
        "installed_runtime_path": str(installed_runtime_root) if isinstance(installed_runtime_root, Path) else "",
        "installed_bundle_label": accepted_bundle_label,
        "local_accepted_package_marker_path": str(accepted_marker_path) if isinstance(accepted_marker_path, Path) else "",
        "local_accepted_package_label": accepted_bundle_label,
        "uninstall_registry_install_location": str(uninstall_registration.get("install_location") or "").strip(),
        "uninstall_registry_display_version": str(uninstall_registration.get("display_version") or "").strip(),
        "uninstall_registry_key": str(uninstall_registration.get("registry_key") or "").strip(),
        "current_package_root_path": str(current_package_root) if isinstance(current_package_root, Path) else "",
        "current_installer_script_path": str(current_installers.get("script")) if isinstance(current_installers.get("script"), Path) else "",
        "current_installer_bundle_path": str(current_installers.get("bundle")) if isinstance(current_installers.get("bundle"), Path) else "",
        "verified_release_manifest_path": str(verified_release.get("manifest_path")) if isinstance(verified_release.get("manifest_path"), Path) else "",
        "verified_release_manifest_kind": str(verified_release.get("manifest_kind") or "").strip(),
        "verified_release_channel_name": str(verified_release.get("channel_name") or "").strip(),
        "verified_release_generated_at": str(verified_release.get("generated_at") or "").strip(),
        "verified_release_package_root_path": str(verified_release.get("package_root")) if isinstance(verified_release.get("package_root"), Path) else "",
        "verified_release_package_label": str(verified_release.get("package_label") or "").strip(),
        "verified_release_release_summary_path": str(verified_release.get("acceptance_text_path")) if isinstance(verified_release.get("acceptance_text_path"), Path) else "",
        "verified_release_release_summary_json_path": str(verified_release.get("acceptance_json_path")) if isinstance(verified_release.get("acceptance_json_path"), Path) else "",
        "verified_release_acceptance_status": str(verified_release.get("acceptance_status") or "").strip(),
        "verified_release_installer_script_path": str(verified_release.get("installer_script_path")) if isinstance(verified_release.get("installer_script_path"), Path) else "",
        "verified_release_installer_bundle_path": str(verified_release.get("installer_bundle_path")) if isinstance(verified_release.get("installer_bundle_path"), Path) else "",
        "verified_release_portable_bundle_path": str(verified_release.get("portable_bundle_path")) if isinstance(verified_release.get("portable_bundle_path"), Path) else "",
        "verified_release_build_identity_path": str(verified_release.get("build_identity_path")) if isinstance(verified_release.get("build_identity_path"), Path) else "",
        "verified_release_git_commit": str(verified_release.get("git_commit") or "").strip(),
        "verified_release_git_branch": str(verified_release.get("git_branch") or "").strip(),
        "verified_release_built_at": str(verified_release.get("built_at") or "").strip(),
        "latest_verified_package_root_path": str(latest_verified.get("package_root")) if isinstance(latest_verified.get("package_root"), Path) else "",
        "latest_verified_package_label": str(latest_verified.get("package_label") or "").strip(),
        "latest_verified_package_acceptance_summary_path": str(latest_verified.get("acceptance_text_path")) if isinstance(latest_verified.get("acceptance_text_path"), Path) else "",
        "latest_verified_package_acceptance_summary_json_path": str(latest_verified.get("acceptance_json_path")) if isinstance(latest_verified.get("acceptance_json_path"), Path) else "",
        "latest_verified_package_acceptance_status": str(latest_verified.get("acceptance_status") or "").strip(),
        "latest_verified_installer_script_path": str(latest_verified.get("installer_script_path")) if isinstance(latest_verified.get("installer_script_path"), Path) else "",
        "latest_verified_installer_bundle_path": str(latest_verified.get("installer_bundle_path")) if isinstance(latest_verified.get("installer_bundle_path"), Path) else "",
        "installed_wizard_executable_path": str(installed_executables.get("wizard")) if isinstance(installed_executables.get("wizard"), Path) else "",
        "installed_runner_executable_path": str(installed_executables.get("runner")) if isinstance(installed_executables.get("runner"), Path) else "",
    }


def _load_verified_release_manifest_for_purpose(
    record: Optional[Mapping[str, Any]],
    *,
    purpose: str,
) -> Dict[str, Any]:
    data = dict(record or {})
    purpose_key = str(purpose or "").strip().upper()
    candidates: list[Path] = []
    install_root = _safe_path(data.get("install_root_path"))
    if purpose_key.startswith("RELAUNCH") and isinstance(install_root, Path):
        candidates.append(install_root / "latest_verified_release_v1.json")
    manifest_path = _safe_path(data.get("verified_release_manifest_path"))
    if isinstance(manifest_path, Path):
        candidates.append(manifest_path)
    current_package_root = _safe_path(data.get("current_package_root_path"))
    if isinstance(current_package_root, Path):
        candidates.append(current_package_root / "latest_verified_release_v1.json")
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        payload = _load_json_dict(candidate)
        normalized = _normalize_verified_release_manifest(
            candidate,
            payload,
            root_fallback=(candidate.parent if candidate.name.lower() == "latest_verified_release_v1.json" else None),
        )
        if normalized and str(normalized.get("acceptance_status") or "").upper() == "PASS":
            return normalized
    return {}


def _append_release_verification_issue(details: list[str], message: str) -> None:
    text = str(message or "").strip()
    if text:
        details.append(text)


def _verify_release_hash(
    details: list[str],
    *,
    label: str,
    path: Optional[Path],
    expected_hash: str,
    required: bool = True,
) -> None:
    target = path if isinstance(path, Path) else None
    if not isinstance(target, Path) or not target.exists() or not target.is_file():
        if required:
            _append_release_verification_issue(details, f"{label} is missing.")
        return
    expected = str(expected_hash or "").strip().upper()
    if not expected:
        if required:
            _append_release_verification_issue(details, f"Verified release manifest is missing {label} SHA256.")
        return
    actual = _sha256_file(target)
    if not actual:
        _append_release_verification_issue(details, f"{label} SHA256 could not be computed.")
        return
    if actual != expected:
        _append_release_verification_issue(
            details,
            f"{label} SHA256 mismatch. Expected {expected}, got {actual}.",
        )


def verify_verified_release_reference(
    package_status_record: Optional[Mapping[str, Any]] = None,
    *,
    purpose: str = "INSTALL",
    target: str = "WIZARD",
) -> Dict[str, Any]:
    record = dict(package_status_record or {})
    purpose_key = str(purpose or "INSTALL").strip().upper() or "INSTALL"
    target_key = str(target or "WIZARD").strip().upper() or "WIZARD"
    manifest = _load_verified_release_manifest_for_purpose(record, purpose=purpose_key)
    details: list[str] = []
    if not manifest:
        details.append("No PASS verified release manifest was found for this action.")
        return {
            "status": "FAIL",
            "purpose": purpose_key,
            "target": target_key,
            "package_label": "",
            "manifest_path": "",
            "details": details,
            "summary": details[0],
        }

    package_label = str(manifest.get("package_label") or "").strip()
    package_root = manifest.get("package_root") if isinstance(manifest.get("package_root"), Path) else None
    hashes = dict(manifest.get("hashes") or {})

    build_identity_path = manifest.get("build_identity_path") if isinstance(manifest.get("build_identity_path"), Path) else None
    acceptance_text_path = manifest.get("acceptance_text_path") if isinstance(manifest.get("acceptance_text_path"), Path) else None
    acceptance_json_path = manifest.get("acceptance_json_path") if isinstance(manifest.get("acceptance_json_path"), Path) else None
    installer_script_path = manifest.get("installer_script_path") if isinstance(manifest.get("installer_script_path"), Path) else None
    version_audit_json_path = manifest.get("version_audit_json_path") if isinstance(manifest.get("version_audit_json_path"), Path) else None

    if not package_label:
        _append_release_verification_issue(details, "Verified release manifest is missing package_label.")
    if not isinstance(package_root, Path) or not package_root.exists():
        _append_release_verification_issue(details, "Verified release package root is missing.")

    audit_payload = _load_json_dict(version_audit_json_path)
    if not audit_payload:
        _append_release_verification_issue(details, "Package version audit is missing.")
    else:
        if str(audit_payload.get("status") or "").strip().upper() != "PASS":
            _append_release_verification_issue(details, "Package version audit is not PASS.")
        audit_label = str(audit_payload.get("expected_bundle_label") or "").strip()
        if package_label and audit_label and audit_label != package_label:
            _append_release_verification_issue(
                details,
                f"Package version audit label {audit_label} does not match verified release label {package_label}.",
            )

    build_identity_payload = _load_json_dict(build_identity_path)
    if not build_identity_payload:
        _append_release_verification_issue(details, "Build identity manifest is missing.")
    elif package_label and str(build_identity_payload.get("bundle_label") or "").strip() != package_label:
        _append_release_verification_issue(details, "Build identity bundle label does not match the verified release label.")

    acceptance_payload = _load_json_dict(acceptance_json_path)
    if not acceptance_payload:
        _append_release_verification_issue(details, "Packaged acceptance summary JSON is missing.")
    else:
        if str(acceptance_payload.get("status") or "").strip().upper() != "PASS":
            _append_release_verification_issue(details, "Packaged acceptance summary JSON is not PASS.")
        if package_label and str(acceptance_payload.get("package_label") or "").strip() != package_label:
            _append_release_verification_issue(details, "Packaged acceptance package label does not match the verified release label.")

    _verify_release_hash(details, label="Build identity manifest", path=build_identity_path, expected_hash=hashes.get("build_identity_sha256", ""), required=True)
    _verify_release_hash(details, label="Packaged acceptance summary", path=acceptance_text_path, expected_hash=hashes.get("acceptance_summary_txt_sha256", ""), required=True)
    _verify_release_hash(details, label="Packaged acceptance summary JSON", path=acceptance_json_path, expected_hash=hashes.get("acceptance_summary_json_sha256", ""), required=True)

    if purpose_key.startswith("INSTALL"):
        _verify_release_hash(details, label="Installer script", path=installer_script_path, expected_hash=hashes.get("installer_script_sha256", ""), required=True)
        _verify_release_hash(details, label="Launcher batch", path=manifest.get("launcher_path") if isinstance(manifest.get("launcher_path"), Path) else None, expected_hash=hashes.get("launcher_batch_sha256", ""), required=True)
        _verify_release_hash(details, label="Wizard executable", path=manifest.get("wizard_exe_path") if isinstance(manifest.get("wizard_exe_path"), Path) else None, expected_hash=hashes.get("wizard_exe_sha256", ""), required=True)
        _verify_release_hash(details, label="Runner executable", path=manifest.get("runner_exe_path") if isinstance(manifest.get("runner_exe_path"), Path) else None, expected_hash=hashes.get("runner_exe_sha256", ""), required=True)
        _verify_release_hash(details, label="ScriptRunner executable", path=manifest.get("script_runner_exe_path") if isinstance(manifest.get("script_runner_exe_path"), Path) else None, expected_hash=hashes.get("script_runner_exe_sha256", ""), required=True)
    elif purpose_key.startswith("RELAUNCH"):
        install_root = _safe_path(record.get("install_root_path"))
        installed_runtime_root = _safe_path(record.get("installed_runtime_path"))
        installed_build_identity_path = _safe_path(record.get("build_identity_manifest_path"))
        if not isinstance(installed_build_identity_path, Path) and isinstance(installed_runtime_root, Path):
            installed_build_identity_path = installed_runtime_root / "config" / "mole_build_identity_v1.json"
        installed_acceptance_paths = _package_acceptance_paths(install_root)
        installed_acceptance_txt = installed_acceptance_paths.get("text")
        installed_acceptance_json = installed_acceptance_paths.get("json")
        installed_acceptance_payload = _load_json_dict(installed_acceptance_json)
        installed_build_identity_payload = _load_json_dict(installed_build_identity_path)
        if not installed_build_identity_payload:
            _append_release_verification_issue(details, "Installed build identity manifest is missing.")
        elif package_label and str(installed_build_identity_payload.get("bundle_label") or "").strip() != package_label:
            _append_release_verification_issue(details, "Installed build identity bundle label does not match the verified release label.")
        if not installed_acceptance_payload:
            _append_release_verification_issue(details, "Installed packaged acceptance summary JSON is missing.")
        else:
            if str(installed_acceptance_payload.get("status") or "").strip().upper() != "PASS":
                _append_release_verification_issue(details, "Installed packaged acceptance summary JSON is not PASS.")
            if package_label and str(installed_acceptance_payload.get("package_label") or "").strip() != package_label:
                _append_release_verification_issue(details, "Installed packaged acceptance package label does not match the verified release label.")
        _verify_release_hash(details, label="Installed build identity manifest", path=installed_build_identity_path, expected_hash=hashes.get("build_identity_sha256", ""), required=True)
        _verify_release_hash(details, label="Installed packaged acceptance summary", path=installed_acceptance_txt, expected_hash=hashes.get("acceptance_summary_txt_sha256", ""), required=True)
        _verify_release_hash(details, label="Installed packaged acceptance summary JSON", path=installed_acceptance_json, expected_hash=hashes.get("acceptance_summary_json_sha256", ""), required=True)
        if target_key == "RUNNER":
            _verify_release_hash(details, label="Installed Runner executable", path=_safe_path(record.get("installed_runner_executable_path")), expected_hash=hashes.get("runner_exe_sha256", ""), required=True)
        else:
            _verify_release_hash(details, label="Installed Wizard executable", path=_safe_path(record.get("installed_wizard_executable_path")), expected_hash=hashes.get("wizard_exe_sha256", ""), required=True)

    status = "PASS" if not details else "FAIL"
    summary = "Verified release reference passed integrity checks." if status == "PASS" else details[0]
    return {
        "status": status,
        "purpose": purpose_key,
        "target": target_key,
        "package_label": package_label,
        "manifest_path": str(manifest.get("manifest_path")) if isinstance(manifest.get("manifest_path"), Path) else "",
        "details": details,
        "summary": summary,
    }


def evaluate_runtime_action_policy(
    *,
    package_status_record: Optional[Mapping[str, Any]] = None,
    package_status: Any = None,
    action_scope: str = "GENERAL",
    action_label: str = "This action",
) -> Dict[str, Any]:
    record = dict(package_status_record or {})
    status = str(package_status or record.get("package_status") or "UNVERIFIED").strip().upper() or "UNVERIFIED"
    scope = str(action_scope or "GENERAL").strip().upper() or "GENERAL"
    if scope not in {"COMPLIANCE", "DIAGNOSTICS", "TRAINING", "GENERAL"}:
        scope = "GENERAL"
    label = str(action_label or "This action").strip() or "This action"
    summary = str(record.get("package_status_summary") or "").strip()
    detail = str(record.get("package_status_detail") or "").strip()
    acceptance_status = str(record.get("packaged_acceptance_status") or "").strip().upper()

    lines = []
    if summary:
        lines.append(f"Summary: {summary}")
    if detail and detail != summary:
        lines.append(f"Detail: {detail}")
    if acceptance_status:
        lines.append(f"Acceptance: {acceptance_status}")
    detail_block = "\n".join(lines).strip()

    decision = "ALLOW"
    title = f"{label} - Package Status"
    message = f"{label} can continue."

    if status == "CURRENT":
        decision = "ALLOW"
        message = f"{label} can continue.\n\nInstalled and verified package is current."
    elif status == "STALE":
        decision = "ACK"
        message = (
            f"{label} is running from a stale package.\n\n"
            "Explicit acknowledgment is required before continuing."
        )
    elif status == "PORTABLE":
        if scope == "COMPLIANCE":
            decision = "BLOCK"
            message = (
                f"{label} is blocked from a portable runtime.\n\n"
                "Portable packages are allowed only for diagnostics or training workflows."
            )
        else:
            decision = "WARN"
            message = (
                f"{label} is running from a portable runtime.\n\n"
                "Portable packages are allowed for diagnostics and training workflows with warning only."
            )
    elif status == "UNVERIFIED":
        if scope == "COMPLIANCE":
            decision = "BLOCK"
            message = (
                f"{label} is blocked because package verification is incomplete.\n\n"
                "Field/compliance workflows require a verified installed package."
            )
        else:
            decision = "WARN"
            message = (
                f"{label} is running from an unverified package.\n\n"
                "This non-compliance workflow is being allowed with warning only."
            )
    else:
        decision = "WARN"
        message = (
            f"{label} is running with an unknown package status ({status}).\n\n"
            "This workflow is being allowed with warning only."
        )

    if detail_block:
        message = f"{message}\n\n{detail_block}"

    return {
        "decision": decision,
        "title": title,
        "message": message,
        "package_status": status,
        "action_scope": scope,
        "action_label": label,
    }


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
