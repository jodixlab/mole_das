from __future__ import annotations

import json
import os
import re
import sqlite3
import shutil
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


def evaluate_runtime_package_status(
    *,
    current_runtime_root: Path,
    current_build_identity: Optional[Mapping[str, Any]] = None,
    current_acceptance_summary_path: Optional[Path] = None,
) -> Dict[str, Any]:
    runtime_root = Path(current_runtime_root).resolve()
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

    stale_launch = False
    if portable_launch and isinstance(local_install_root, Path):
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
