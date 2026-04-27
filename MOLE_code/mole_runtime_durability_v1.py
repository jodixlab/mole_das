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


def _package_root_from_runtime_root(runtime_root: Path) -> Path:
    runtime_root = Path(runtime_root).resolve()
    if runtime_root.name.strip().lower() == "runtime":
        return runtime_root.parent.resolve()
    return runtime_root


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
