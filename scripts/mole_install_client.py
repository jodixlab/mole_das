from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List

_MUTABLE_DATA_LABELS = (
    "logs",
    "backups",
    "sessions",
    "daq_runs",
    "exports",
    "validation",
    "inbox_packages",
    "inbox_archive",
    "cache",
)
_UPGRADE_REPORT_LATEST_JSON = "upgrade_report__latest.json"
_UPGRADE_REPORT_LATEST_TXT = "upgrade_report__latest.txt"
_ROLLBACK_REPORT_LATEST_JSON = "rollback_report__latest.json"
_ROLLBACK_REPORT_LATEST_TXT = "rollback_report__latest.txt"
_RESTORE_POINT_KEEP = 8


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _remove_tree(path: Path) -> None:
    path = Path(path)
    if path.exists():
        shutil.rmtree(path)


def _copy_tree(src: Path, dst: Path) -> None:
    src = Path(src)
    dst = Path(dst)
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            [
                "robocopy",
                str(src),
                str(dst),
                "/E",
                "/R:2",
                "/W:1",
                "/NFL",
                "/NDL",
                "/NJH",
                "/NJS",
                "/NP",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode < 8:
            return
    except Exception:
        pass
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _default_install_root() -> Path:
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return (Path(local) / "Programs" / "MOLE_DAS").resolve()


def _resolve_package_root(arg_value: str | None) -> Path:
    if arg_value:
        return Path(arg_value).expanduser().resolve()
    here = Path(__file__).resolve().parent
    if (here / "runtime").exists():
        return here
    if (here.parent / "runtime").exists():
        return here.parent.resolve()
    return here


def _extract_runtime_constant(package_root: Path, constant_name: str) -> str:
    runtime_module = package_root / "runtime" / "MOLE_code" / "mole_runtime_durability_v1.py"
    if not runtime_module.exists():
        return ""
    try:
        text = runtime_module.read_text(encoding="utf-8")
    except Exception:
        return ""
    pattern = re.compile(rf"^{re.escape(constant_name)}\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)
    match = pattern.search(text)
    return str(match.group(1)).strip() if match else ""


def _count_files(path: Path) -> int:
    path = Path(path)
    if not path.exists():
        return 0
    if path.is_file():
        return 1
    count = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                count += 1
    except Exception:
        return count
    return count


def _summarize_mutable_payload(root: Path) -> Dict[str, Any]:
    root = Path(root)
    entries: List[Dict[str, Any]] = []
    total_files = 0
    for label in _MUTABLE_DATA_LABELS:
        path = root / label
        file_count = _count_files(path)
        if file_count <= 0:
            continue
        total_files += file_count
        entries.append(
            {
                "label": label,
                "path": str(path),
                "file_count": file_count,
            }
        )
    return {
        "root": str(root),
        "has_payload": total_files > 0,
        "file_count": total_files,
        "entries": entries,
    }


def _inventory_files(root: Path, *, scoped_labels: tuple[str, ...] | None = None) -> Dict[str, Dict[str, Any]]:
    root = Path(root)
    inventory: Dict[str, Dict[str, Any]] = {}
    if not root.exists():
        return inventory
    for item in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
        if not item.is_file():
            continue
        rel = item.relative_to(root)
        if scoped_labels is not None:
            parts = rel.parts
            if not parts or parts[0] not in scoped_labels:
                continue
        inventory[rel.as_posix()] = {
            "relative_path": rel.as_posix(),
            "absolute_path": str(item),
            "size_bytes": int(item.stat().st_size),
            "sha256": "",
        }
    return inventory


def _attach_hashes(records: Dict[str, Dict[str, Any]], *, rel_paths: List[str]) -> None:
    for rel in rel_paths:
        entry = records.get(rel)
        if not entry:
            continue
        if entry.get("sha256"):
            continue
        try:
            entry["sha256"] = _sha256_file(Path(entry["absolute_path"]))
        except Exception:
            entry["sha256"] = ""


def _render_delta_lines(delta: Dict[str, Any]) -> List[str]:
    lines = [
        f"Package data files to add: {delta['package_add_count']}",
        f"Package data files to update: {delta['package_update_count']}",
        f"Installed data files left untouched: {delta['installed_untouched_count']}",
        f"Legacy runtime files to migrate: {delta['legacy_migrate_count']}",
        f"Legacy runtime files already present in data root (back up + remove runtime copy only): {delta['legacy_preserve_existing_count']}",
        f"Legacy runtime files to back up before cleanup: {delta['legacy_backup_count']}",
    ]
    for heading, key in (
        ("Package additions", "package_additions"),
        ("Package updates", "package_updates"),
        ("Installed data left untouched", "installed_untouched"),
        ("Legacy runtime files to migrate", "legacy_runtime_migrate"),
        ("Legacy runtime files to back up and then remove", "legacy_runtime_backup"),
        ("Legacy runtime files whose installed data copy stays untouched", "legacy_runtime_existing_targets"),
    ):
        items = list(delta.get(key) or [])
        lines.append("")
        lines.append(f"{heading}:")
        if not items:
            lines.append("  (none)")
            continue
        for item in items:
            rel = str(item.get("relative_path") or "")
            extra = ""
            if key == "package_updates":
                extra = f" [installed={item.get('installed_sha256','')[:12]} incoming={item.get('package_sha256','')[:12]}]"
            elif key == "legacy_runtime_existing_targets":
                extra = f" [runtime={item.get('runtime_sha256','')[:12]} installed={item.get('installed_sha256','')[:12]}]"
            lines.append(f"  - {rel}{extra}")
    return lines


def _build_upgrade_delta(package: Dict[str, Any], installed: Dict[str, Any]) -> Dict[str, Any]:
    package_root = Path(str(package.get("package_root") or "")).resolve()
    install_root = Path(str(installed.get("install_root") or "")).resolve()
    package_data_root = package_root / "data"
    installed_data_root = install_root / "data"
    legacy_runtime_root = install_root / "runtime" / "mole_das_data"

    package_files = _inventory_files(package_data_root)
    installed_files = _inventory_files(installed_data_root)
    legacy_files = _inventory_files(legacy_runtime_root, scoped_labels=_MUTABLE_DATA_LABELS)

    package_additions: List[Dict[str, Any]] = []
    package_updates: List[Dict[str, Any]] = []
    installed_untouched: List[Dict[str, Any]] = []
    legacy_runtime_migrate: List[Dict[str, Any]] = []
    legacy_runtime_existing_targets: List[Dict[str, Any]] = []
    legacy_runtime_backup: List[Dict[str, Any]] = []

    overlapping_package_paths = [rel for rel in package_files if rel in installed_files]
    _attach_hashes(package_files, rel_paths=overlapping_package_paths)
    _attach_hashes(installed_files, rel_paths=overlapping_package_paths)

    for rel, package_entry in package_files.items():
        installed_entry = installed_files.get(rel)
        if not installed_entry:
            package_additions.append(dict(package_entry))
            continue
        package_hash = str(package_entry.get("sha256") or "")
        installed_hash = str(installed_entry.get("sha256") or "")
        if package_hash != installed_hash:
            package_updates.append(
                {
                    **dict(package_entry),
                    "package_sha256": package_hash,
                    "installed_sha256": installed_hash,
                    "installed_absolute_path": installed_entry.get("absolute_path"),
                }
            )

    for rel, installed_entry in installed_files.items():
        if rel not in package_files:
            installed_untouched.append(dict(installed_entry))

    overlapping_legacy_paths = [rel for rel in legacy_files if rel in installed_files]
    _attach_hashes(legacy_files, rel_paths=list(legacy_files.keys()))
    _attach_hashes(installed_files, rel_paths=overlapping_legacy_paths)

    for rel, legacy_entry in legacy_files.items():
        legacy_runtime_backup.append(dict(legacy_entry))
        installed_entry = installed_files.get(rel)
        if installed_entry:
            legacy_runtime_existing_targets.append(
                {
                    **dict(legacy_entry),
                    "runtime_sha256": legacy_entry.get("sha256"),
                    "installed_sha256": installed_entry.get("sha256"),
                    "installed_absolute_path": installed_entry.get("absolute_path"),
                }
            )
        else:
            legacy_runtime_migrate.append(dict(legacy_entry))

    delta = {
        "schema": "mole_install_upgrade_delta_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_root": str(package_root),
        "install_root": str(install_root),
        "package_data_root": str(package_data_root),
        "installed_data_root": str(installed_data_root),
        "legacy_runtime_root": str(legacy_runtime_root),
        "package_add_count": len(package_additions),
        "package_update_count": len(package_updates),
        "installed_untouched_count": len(installed_untouched),
        "legacy_migrate_count": len(legacy_runtime_migrate),
        "legacy_preserve_existing_count": len(legacy_runtime_existing_targets),
        "legacy_backup_count": len(legacy_runtime_backup),
        "package_additions": package_additions,
        "package_updates": package_updates,
        "installed_untouched": installed_untouched,
        "legacy_runtime_migrate": legacy_runtime_migrate,
        "legacy_runtime_existing_targets": legacy_runtime_existing_targets,
        "legacy_runtime_backup": legacy_runtime_backup,
    }
    delta["lines"] = _render_delta_lines(delta)
    return delta


def _build_upgrade_review_text(plan: Dict[str, Any], delta: Dict[str, Any]) -> str:
    plan_lines = list(plan.get("lines") or [])
    delta_lines = list(delta.get("lines") or [])
    sections: List[str] = []
    if plan_lines:
        sections.append("Upgrade Plan")
        sections.append("------------")
        sections.extend(plan_lines)
    if delta_lines:
        if sections:
            sections.append("")
        sections.append("Preflight Delta Review")
        sections.append("----------------------")
        sections.extend(delta_lines)
    return "\n".join(sections).strip()


def _default_upgrade_report_dir(package_root: Path, install_root: Path) -> Path:
    install_root = Path(install_root)
    if install_root.exists():
        return install_root / "data" / "backups" / "upgrade_reviews"
    return Path(package_root) / "_upgrade_reports"


def _build_upgrade_report(
    package: Dict[str, Any],
    installed: Dict[str, Any],
    plan: Dict[str, Any],
    delta: Dict[str, Any],
) -> Dict[str, Any]:
    review_text = _build_upgrade_review_text(plan, delta)
    return {
        "schema": "mole_install_upgrade_report_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_label": str(package.get("package_label") or ""),
        "package_git_commit": str(package.get("git_commit") or ""),
        "package_git_branch": str(package.get("git_branch") or ""),
        "install_root": str(installed.get("install_root") or ""),
        "installed_bundle_label": str(installed.get("bundle_label") or ""),
        "installed_data_schema_version": str(installed.get("data_schema_version") or ""),
        "upgrade_action": str(plan.get("action") or ""),
        "upgrade_summary": str(plan.get("summary") or ""),
        "plan": plan,
        "delta": delta,
        "review_text": review_text,
    }


def _render_upgrade_report_text(report: Dict[str, Any]) -> str:
    lines = [
        "MOLE-DAS Upgrade Report",
        "=======================",
        f"Generated at: {report.get('generated_at') or ''}",
        f"Package label: {report.get('package_label') or '(unknown)'}",
        f"Package git commit: {report.get('package_git_commit') or '(unknown)'}",
        f"Package git branch: {report.get('package_git_branch') or '(unknown)'}",
        f"Install root: {report.get('install_root') or '(unset)'}",
        f"Installed bundle label: {report.get('installed_bundle_label') or '(none)'}",
        f"Installed data schema version: {report.get('installed_data_schema_version') or '(none)'}",
        f"Upgrade action: {report.get('upgrade_action') or '(none)'}",
        f"Upgrade summary: {report.get('upgrade_summary') or '(none)'}",
        "",
        str(report.get("review_text") or "").strip(),
    ]
    return "\n".join(lines).strip() + "\n"


def _write_upgrade_report(report: Dict[str, Any], output_dir: Path) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    package_label = str(report.get("package_label") or "MOLE_DAS").strip() or "MOLE_DAS"
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", package_label)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = f"upgrade_report__{safe_label}__{stamp}"
    json_path = output_dir / f"{prefix}.json"
    txt_path = output_dir / f"{prefix}.txt"
    latest_json_path = output_dir / _UPGRADE_REPORT_LATEST_JSON
    latest_txt_path = output_dir / _UPGRADE_REPORT_LATEST_TXT
    json_text = json.dumps(report, indent=2)
    txt_text = _render_upgrade_report_text(report)
    json_path.write_text(json_text, encoding="utf-8")
    txt_path.write_text(txt_text, encoding="utf-8")
    latest_json_path.write_text(json_text, encoding="utf-8")
    latest_txt_path.write_text(txt_text, encoding="utf-8")
    return {
        "output_dir": str(output_dir),
        "json_path": str(json_path),
        "txt_path": str(txt_path),
        "latest_json_path": str(latest_json_path),
        "latest_txt_path": str(latest_txt_path),
    }


def _restore_points_root(install_root: Path) -> Path:
    return Path(install_root) / "_data_restore_points"


def _rotate_restore_points(restore_points_root: Path, *, keep: int = _RESTORE_POINT_KEEP) -> None:
    manifests = sorted(
        restore_points_root.glob("restore_point__*/restore_point_manifest_v1.json"),
        key=lambda p: p.parent.name.lower(),
        reverse=True,
    )
    for manifest_path in manifests[keep:]:
        _remove_tree(manifest_path.parent)


def _inventory_restore_points(install_root: Path) -> List[Dict[str, Any]]:
    install_root = Path(install_root)
    restore_points_root = _restore_points_root(install_root)
    points: List[Dict[str, Any]] = []
    if not restore_points_root.exists():
        return points
    manifests = sorted(
        restore_points_root.glob("restore_point__*/restore_point_manifest_v1.json"),
        key=lambda p: p.parent.name.lower(),
        reverse=True,
    )
    for manifest_path in manifests:
        payload = _load_json(manifest_path)
        point_root = manifest_path.parent
        data_snapshot_root = (point_root / str(payload.get("data_snapshot_rel_path") or "data")).resolve()
        legacy_snapshot_root = (point_root / str(payload.get("legacy_runtime_snapshot_rel_path") or "legacy_runtime")).resolve()
        points.append(
            {
                **payload,
                "manifest_path": str(manifest_path.resolve()),
                "point_root": str(point_root.resolve()),
                "data_snapshot_root": str(data_snapshot_root),
                "legacy_runtime_snapshot_root": str(legacy_snapshot_root),
                "has_data_snapshot": data_snapshot_root.exists(),
                "has_legacy_runtime_snapshot": legacy_snapshot_root.exists(),
            }
        )
    return points


def _build_restore_point_manifest(
    installed: Dict[str, Any],
    *,
    point_root: Path,
    reason: str,
) -> Dict[str, Any]:
    install_root = Path(str(installed.get("install_root") or "")).resolve()
    data_root = Path(str(installed.get("data_root") or "")).resolve()
    legacy_runtime_root = Path(str(installed.get("legacy_runtime_data_root") or "")).resolve()
    data_files = _inventory_files(data_root)
    legacy_files = _inventory_files(legacy_runtime_root, scoped_labels=_MUTABLE_DATA_LABELS)
    return {
        "schema": "mole_install_restore_point_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "install_root": str(install_root),
        "data_root": str(data_root),
        "legacy_runtime_root": str(legacy_runtime_root),
        "bundle_label": str(installed.get("bundle_label") or ""),
        "installed_at": str(installed.get("installed_at") or ""),
        "data_schema_version": str(installed.get("data_schema_version") or ""),
        "data_snapshot_rel_path": "data",
        "legacy_runtime_snapshot_rel_path": "legacy_runtime",
        "data_root_file_count": len(data_files),
        "legacy_runtime_file_count": len(legacy_files),
        "install_manifest_path": str(installed.get("install_manifest_path") or ""),
        "build_identity_path": str(installed.get("build_identity_path") or ""),
        "data_root_manifest_path": str(installed.get("data_root_manifest_path") or ""),
        "install_manifest": dict(installed.get("install_manifest") or {}),
        "build_identity": dict(installed.get("build_identity") or {}),
        "data_root_manifest": dict(installed.get("data_manifest") or {}),
        "point_root": str(point_root.resolve()),
    }


def _create_restore_point_from_installed(installed: Dict[str, Any], *, reason: str) -> Dict[str, Any]:
    install_root = Path(str(installed.get("install_root") or "")).resolve()
    if not install_root.exists():
        raise RuntimeError(f"Install root does not exist: {install_root}")
    restore_points_root = _restore_points_root(install_root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    point_root = restore_points_root / f"restore_point__{stamp}"
    data_snapshot_root = point_root / "data"
    legacy_snapshot_root = point_root / "legacy_runtime"
    manifest_path = point_root / "restore_point_manifest_v1.json"
    data_root = Path(str(installed.get("data_root") or "")).resolve()
    legacy_runtime_root = Path(str(installed.get("legacy_runtime_data_root") or "")).resolve()

    if data_root.exists():
        _copy_tree(data_root, data_snapshot_root)
    if legacy_runtime_root.exists() and any(legacy_runtime_root.rglob("*")):
        _copy_tree(legacy_runtime_root, legacy_snapshot_root)

    payload = _build_restore_point_manifest(installed, point_root=point_root, reason=reason)
    _write_json(manifest_path, payload)
    _rotate_restore_points(restore_points_root)
    return {
        **payload,
        "manifest_path": str(manifest_path.resolve()),
        "point_root": str(point_root.resolve()),
        "data_snapshot_root": str(data_snapshot_root.resolve()),
        "legacy_runtime_snapshot_root": str(legacy_snapshot_root.resolve()),
        "has_data_snapshot": data_snapshot_root.exists(),
        "has_legacy_runtime_snapshot": legacy_snapshot_root.exists(),
    }


def _render_rollback_delta_lines(delta: Dict[str, Any]) -> List[str]:
    lines = [
        f"Restore-point files to add back: {delta['snapshot_add_count']}",
        f"Restore-point files to overwrite: {delta['snapshot_update_count']}",
        f"Restore-point files already matching current data root: {delta['snapshot_preserve_count']}",
        f"Current data-root files to remove during restore: {delta['current_remove_count']}",
    ]
    for heading, key in (
        ("Restore-point additions", "snapshot_additions"),
        ("Restore-point overwrites", "snapshot_updates"),
        ("Restore-point files already matching current data root", "snapshot_preserved"),
        ("Current files that will be removed", "current_removals"),
    ):
        items = list(delta.get(key) or [])
        lines.append("")
        lines.append(f"{heading}:")
        if not items:
            lines.append("  (none)")
            continue
        for item in items:
            rel = str(item.get("relative_path") or "")
            extra = ""
            if key == "snapshot_updates":
                extra = f" [current={item.get('current_sha256','')[:12]} restore={item.get('snapshot_sha256','')[:12]}]"
            lines.append(f"  - {rel}{extra}")
    return lines


def _build_rollback_plan(package: Dict[str, Any], installed: Dict[str, Any]) -> Dict[str, Any]:
    install_root = Path(str(installed.get("install_root") or "")).resolve()
    restore_points = list(installed.get("restore_points") or [])
    latest_restore_point = dict(restore_points[0]) if restore_points else {}
    package_label = str(package.get("package_label") or "").strip()
    installed_label = str(installed.get("bundle_label") or "").strip()
    if not install_root.exists():
        action = "NONE"
        summary = "No installed root is available to restore."
        lines = [
            f"Action: {action}",
            f"Incoming package: {package_label or '(unknown)'}",
            f"Installed package: {installed_label or '(none)'}",
            f"Install root: {install_root}",
            "Rollback is unavailable because the install root does not exist.",
        ]
    elif not latest_restore_point:
        action = "NONE"
        summary = "No data-root restore point is available."
        lines = [
            f"Action: {action}",
            f"Incoming package: {package_label or '(unknown)'}",
            f"Installed package: {installed_label or '(none)'}",
            f"Install root: {install_root}",
            "Rollback is unavailable because no restore point has been captured yet.",
        ]
    else:
        action = "ROLLBACK"
        summary = "Restore the external data root from the latest captured restore point."
        restore_label = str(latest_restore_point.get("bundle_label") or "(unknown)")
        restore_created = str(latest_restore_point.get("created_at") or "(unknown)")
        restore_reason = str(latest_restore_point.get("reason") or "(unknown)")
        restore_snapshot_root = str(latest_restore_point.get("data_snapshot_root") or "(missing)")
        lines = [
            f"Action: {action}",
            f"Incoming package: {package_label or '(unknown)'}",
            f"Installed package: {installed_label or '(none)'}",
            f"Install root: {install_root}",
            f"Restore point created at: {restore_created}",
            f"Restore point source package: {restore_label}",
            f"Restore point reason: {restore_reason}",
            f"Target data root: {installed.get('data_root') or '(unset)'}",
            f"Restore-point snapshot: {restore_snapshot_root}",
            f"Restore points available: {len(restore_points)}",
        ]
        if latest_restore_point.get("data_schema_version"):
            lines.append(f"Restore-point data schema: {latest_restore_point.get('data_schema_version')}")
        lines.append(
            f"Restore-point captured {int(latest_restore_point.get('data_root_file_count') or 0)} external data file(s)."
        )
        legacy_count = int(latest_restore_point.get("legacy_runtime_file_count") or 0)
        if legacy_count > 0:
            lines.append(
                f"Restore-point also captured {legacy_count} legacy runtime file(s) for forensic recovery."
            )
        lines.append("Rollback will back up the current external data root before restoring the selected snapshot.")
        lines.append("Rollback restores data only. The installed executable payload stays on the current verified build.")
    return {
        "action": action,
        "summary": summary,
        "lines": lines,
        "restore_point": latest_restore_point,
        "restore_point_count": len(restore_points),
    }


def _build_rollback_delta(installed: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    restore_point = dict(plan.get("restore_point") or {})
    current_data_root = Path(str(installed.get("data_root") or "")).resolve()
    if str(plan.get("action") or "") != "ROLLBACK" or not restore_point:
        delta = {
            "schema": "mole_install_rollback_delta_v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "current_data_root": str(current_data_root),
            "snapshot_root": "",
            "snapshot_add_count": 0,
            "snapshot_update_count": 0,
            "snapshot_preserve_count": 0,
            "current_remove_count": 0,
            "snapshot_additions": [],
            "snapshot_updates": [],
            "snapshot_preserved": [],
            "current_removals": [],
        }
        delta["lines"] = ["Rollback delta review is unavailable because no restore point is selected."]
        return delta

    snapshot_root = Path(str(restore_point.get("data_snapshot_root") or "")).resolve()
    snapshot_files = _inventory_files(snapshot_root)
    current_files = _inventory_files(current_data_root)
    overlap_paths = sorted(set(snapshot_files.keys()) & set(current_files.keys()))
    _attach_hashes(snapshot_files, rel_paths=list(snapshot_files.keys()))
    _attach_hashes(current_files, rel_paths=overlap_paths)

    snapshot_additions: List[Dict[str, Any]] = []
    snapshot_updates: List[Dict[str, Any]] = []
    snapshot_preserved: List[Dict[str, Any]] = []
    current_removals: List[Dict[str, Any]] = []

    for rel, snapshot_entry in snapshot_files.items():
        current_entry = current_files.get(rel)
        if not current_entry:
            snapshot_additions.append(dict(snapshot_entry))
            continue
        snapshot_hash = str(snapshot_entry.get("sha256") or "")
        current_hash = str(current_entry.get("sha256") or "")
        if snapshot_hash == current_hash:
            snapshot_preserved.append(dict(snapshot_entry))
        else:
            snapshot_updates.append(
                {
                    **dict(snapshot_entry),
                    "snapshot_sha256": snapshot_hash,
                    "current_sha256": current_hash,
                    "current_absolute_path": current_entry.get("absolute_path"),
                }
            )

    for rel, current_entry in current_files.items():
        if rel not in snapshot_files:
            current_removals.append(dict(current_entry))

    delta = {
        "schema": "mole_install_rollback_delta_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_data_root": str(current_data_root),
        "snapshot_root": str(snapshot_root),
        "snapshot_add_count": len(snapshot_additions),
        "snapshot_update_count": len(snapshot_updates),
        "snapshot_preserve_count": len(snapshot_preserved),
        "current_remove_count": len(current_removals),
        "snapshot_additions": snapshot_additions,
        "snapshot_updates": snapshot_updates,
        "snapshot_preserved": snapshot_preserved,
        "current_removals": current_removals,
    }
    delta["lines"] = _render_rollback_delta_lines(delta)
    return delta


def _build_rollback_review_text(plan: Dict[str, Any], delta: Dict[str, Any]) -> str:
    plan_lines = list(plan.get("lines") or [])
    delta_lines = list(delta.get("lines") or [])
    sections: List[str] = []
    if plan_lines:
        sections.append("Rollback Plan")
        sections.append("-------------")
        sections.extend(plan_lines)
    if delta_lines:
        if sections:
            sections.append("")
        sections.append("Rollback Delta Review")
        sections.append("---------------------")
        sections.extend(delta_lines)
    return "\n".join(sections).strip()


def _default_rollback_report_dir(package_root: Path, install_root: Path) -> Path:
    install_root = Path(install_root)
    if install_root.exists():
        return install_root / "_rollback_reports"
    return Path(package_root) / "_rollback_reports"


def _build_rollback_report(
    package: Dict[str, Any],
    installed: Dict[str, Any],
    plan: Dict[str, Any],
    delta: Dict[str, Any],
) -> Dict[str, Any]:
    review_text = _build_rollback_review_text(plan, delta)
    restore_point = dict(plan.get("restore_point") or {})
    return {
        "schema": "mole_install_rollback_report_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_label": str(package.get("package_label") or ""),
        "package_git_commit": str(package.get("git_commit") or ""),
        "package_git_branch": str(package.get("git_branch") or ""),
        "install_root": str(installed.get("install_root") or ""),
        "installed_bundle_label": str(installed.get("bundle_label") or ""),
        "installed_data_schema_version": str(installed.get("data_schema_version") or ""),
        "rollback_action": str(plan.get("action") or ""),
        "rollback_summary": str(plan.get("summary") or ""),
        "restore_point_manifest_path": str(restore_point.get("manifest_path") or ""),
        "restore_point_created_at": str(restore_point.get("created_at") or ""),
        "restore_point_bundle_label": str(restore_point.get("bundle_label") or ""),
        "plan": plan,
        "delta": delta,
        "review_text": review_text,
    }


def _render_rollback_report_text(report: Dict[str, Any]) -> str:
    lines = [
        "MOLE-DAS Rollback Report",
        "========================",
        f"Generated at: {report.get('generated_at') or ''}",
        f"Package label: {report.get('package_label') or '(unknown)'}",
        f"Package git commit: {report.get('package_git_commit') or '(unknown)'}",
        f"Package git branch: {report.get('package_git_branch') or '(unknown)'}",
        f"Install root: {report.get('install_root') or '(unset)'}",
        f"Installed bundle label: {report.get('installed_bundle_label') or '(none)'}",
        f"Installed data schema version: {report.get('installed_data_schema_version') or '(none)'}",
        f"Rollback action: {report.get('rollback_action') or '(none)'}",
        f"Rollback summary: {report.get('rollback_summary') or '(none)'}",
        f"Restore point manifest: {report.get('restore_point_manifest_path') or '(none)'}",
        "",
        str(report.get("review_text") or "").strip(),
    ]
    return "\n".join(lines).strip() + "\n"


def _write_rollback_report(report: Dict[str, Any], output_dir: Path) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    package_label = str(report.get("package_label") or "MOLE_DAS").strip() or "MOLE_DAS"
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", package_label)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = f"rollback_report__{safe_label}__{stamp}"
    json_path = output_dir / f"{prefix}.json"
    txt_path = output_dir / f"{prefix}.txt"
    latest_json_path = output_dir / _ROLLBACK_REPORT_LATEST_JSON
    latest_txt_path = output_dir / _ROLLBACK_REPORT_LATEST_TXT
    json_text = json.dumps(report, indent=2)
    txt_text = _render_rollback_report_text(report)
    json_path.write_text(json_text, encoding="utf-8")
    txt_path.write_text(txt_text, encoding="utf-8")
    latest_json_path.write_text(json_text, encoding="utf-8")
    latest_txt_path.write_text(txt_text, encoding="utf-8")
    return {
        "output_dir": str(output_dir),
        "json_path": str(json_path),
        "txt_path": str(txt_path),
        "latest_json_path": str(latest_json_path),
        "latest_txt_path": str(latest_txt_path),
    }


def _apply_rollback_restore(
    package: Dict[str, Any],
    installed: Dict[str, Any],
    plan: Dict[str, Any],
    delta: Dict[str, Any],
    *,
    relaunch: bool = True,
) -> Dict[str, Any]:
    restore_point = dict(plan.get("restore_point") or {})
    if str(plan.get("action") or "") != "ROLLBACK" or not restore_point:
        raise RuntimeError("Rollback is unavailable because no restore point is selected.")
    install_root = Path(str(installed.get("install_root") or "")).resolve()
    data_root = Path(str(installed.get("data_root") or "")).resolve()
    snapshot_root = Path(str(restore_point.get("data_snapshot_root") or "")).resolve()
    if not snapshot_root.exists():
        raise RuntimeError(f"Restore-point snapshot is missing: {snapshot_root}")

    pre_restore_point = _create_restore_point_from_installed(installed, reason="PRE_ROLLBACK_RESTORE")
    staging_root = install_root / "_rollback_stage" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    staged_data_root = staging_root / "data"
    _copy_tree(snapshot_root, staged_data_root)
    if data_root.exists():
        _remove_tree(data_root)
    data_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(staged_data_root), str(data_root))
    _remove_tree(staging_root)

    manifest_path = data_root / "data_root_manifest_v1.json"
    manifest = _load_json(manifest_path)
    rollback_entry = {
        "restored_at": datetime.now(timezone.utc).isoformat(),
        "restore_point_manifest_path": str(restore_point.get("manifest_path") or ""),
        "restore_point_bundle_label": str(restore_point.get("bundle_label") or ""),
        "pre_restore_point_manifest_path": str(pre_restore_point.get("manifest_path") or ""),
        "restored_file_count": len(_inventory_files(data_root)),
        "snapshot_add_count": int(delta.get("snapshot_add_count") or 0),
        "snapshot_update_count": int(delta.get("snapshot_update_count") or 0),
        "current_remove_count": int(delta.get("current_remove_count") or 0),
    }
    if manifest:
        history = list(manifest.get("rollback_history") or [])
        history.append(rollback_entry)
        manifest["rollback_history"] = history[-10:]
        manifest["last_rollback"] = rollback_entry
        manifest["data_root"] = str(data_root)
        _write_json(manifest_path, manifest)

    wizard_exe = Path(str(installed.get("wizard_exe_path") or "")).resolve()
    if relaunch and wizard_exe.exists():
        subprocess.Popen([str(wizard_exe)], cwd=str(wizard_exe.parent))

    return {
        "status": "PASS",
        "install_root": str(install_root),
        "data_root": str(data_root),
        "restore_point_manifest_path": str(restore_point.get("manifest_path") or ""),
        "pre_restore_point_manifest_path": str(pre_restore_point.get("manifest_path") or ""),
        "data_root_manifest_path": str(manifest_path),
        "wizard_exe_path": str(wizard_exe) if wizard_exe.exists() else "",
    }


def _build_upgrade_plan(package: Dict[str, Any], installed: Dict[str, Any]) -> Dict[str, Any]:
    package_label = str(package.get("package_label") or "").strip()
    installed_label = str(installed.get("bundle_label") or "").strip()
    expected_schema = str(package.get("data_schema_version_expected") or "").strip()
    installed_schema = str(installed.get("data_schema_version") or "").strip()
    installed_exists = bool(installed.get("exists"))
    data_manifest_present = bool(installed.get("data_manifest_present"))
    portable_payload = bool(package.get("has_data_payload"))
    legacy_payload = dict(installed.get("legacy_runtime_payload") or {})
    legacy_has_payload = bool(legacy_payload.get("has_payload"))
    legacy_entries = list(legacy_payload.get("entries") or [])
    install_root = str(installed.get("install_root") or "").strip()
    migration_backup_root = str(installed.get("migration_backup_root") or "").strip()

    if not installed_exists:
        action = "INSTALL"
        summary = "Fresh install into a new root."
    elif installed_label and package_label and installed_label != package_label:
        action = "UPGRADE"
        summary = "In-place upgrade of the installed copy."
    elif legacy_has_payload or not data_manifest_present or (expected_schema and installed_schema and expected_schema != installed_schema):
        action = "REPAIR"
        summary = "Repair and normalize the installed data root."
    else:
        action = "RELAUNCH"
        summary = "Installed copy already matches the selected package."

    lines = [
        f"Action: {action}",
        f"Incoming package: {package_label or '(unknown)'}",
        f"Installed package: {installed_label or '(none)'}",
        f"Install root: {install_root or '(unset)'}",
    ]
    if expected_schema:
        lines.append(f"Expected data schema: {expected_schema}")
    if installed_schema:
        lines.append(f"Installed data schema: {installed_schema}")
    elif installed_exists:
        lines.append("Installed data schema: missing")

    if portable_payload:
        lines.append("Package contains a portable data payload; installer will merge it into the installed data root.")
    if not data_manifest_present and installed_exists:
        lines.append("Installed data-root manifest is missing; first launch will create and stamp a new manifest.")
    if legacy_has_payload:
        lines.append(
            f"Legacy mutable runtime payload detected: {legacy_payload.get('file_count', 0)} file(s) across {len(legacy_entries)} runtime folder(s)."
        )
        labels = ", ".join(str(entry.get("label") or "") for entry in legacy_entries if entry.get("label")) or "(unknown)"
        lines.append(f"Legacy folders queued for migration: {labels}")
        if migration_backup_root:
            lines.append(f"Migration backup root: {migration_backup_root}")
        lines.append("First launch after install will migrate those files into the external data root and remove them from runtime\\mole_das_data.")
    elif installed_exists:
        lines.append("No legacy mutable runtime payload was detected under runtime\\mole_das_data.")

    if action == "UPGRADE":
        lines.append("The existing install root will be updated in place, then the verified app will relaunch.")
    elif action == "REPAIR":
        lines.append("The install root already matches this package label; repair will re-run install logic and relaunch.")
    elif action == "RELAUNCH":
        lines.append("No upgrade is required; relaunch is optional unless you want to refresh shortcuts or repair manifests.")
    else:
        lines.append("A new install root will be created, verified, and launched.")

    return {
        "action": action,
        "summary": summary,
        "lines": lines,
        "has_legacy_runtime_payload": legacy_has_payload,
        "legacy_runtime_file_count": int(legacy_payload.get("file_count") or 0),
        "portable_data_payload": portable_payload,
    }


def _package_summary(package_root: Path) -> Dict[str, Any]:
    runtime_root = package_root / "runtime"
    build_identity_path = runtime_root / "config" / "mole_build_identity_v1.json"
    verified_release_path = package_root / "latest_verified_release_v1.json"
    verified_release_signature_path = package_root / "latest_verified_release_v1.signature.json"
    signing_public_key_path = package_root / "mole_release_signing_public_key_v1.json"
    acceptance_json_path = package_root / "PACKAGED_ACCEPTANCE_SUMMARY.json"
    version_audit_path = package_root / "PACKAGE_VERSION_AUDIT.json"
    immutable_audit_path = package_root / "IMMUTABLE_PACKAGE_AUDIT.json"
    installer_script_path = package_root / "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
    uninstall_script_path = package_root / "UNINSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
    launcher_path = package_root / "LAUNCH_MOLE_DAS_EXE.bat"
    build_identity = _load_json(build_identity_path)
    verified_release = _load_json(verified_release_path)
    verified_release_signature = _load_json(verified_release_signature_path)
    signing_public_key = _load_json(signing_public_key_path)
    acceptance = _load_json(acceptance_json_path)
    version_audit = _load_json(version_audit_path)
    immutable_audit = _load_json(immutable_audit_path)
    return {
        "package_root": str(package_root),
        "runtime_root": str(runtime_root),
        "build_identity_path": str(build_identity_path),
        "verified_release_path": str(verified_release_path),
        "verified_release_signature_path": str(verified_release_signature_path),
        "signing_public_key_path": str(signing_public_key_path),
        "acceptance_json_path": str(acceptance_json_path),
        "version_audit_path": str(version_audit_path),
        "immutable_audit_path": str(immutable_audit_path),
        "installer_script_path": str(installer_script_path),
        "uninstall_script_path": str(uninstall_script_path),
        "launcher_path": str(launcher_path),
        "package_label": str(build_identity.get("bundle_label") or verified_release.get("package_label") or package_root.name),
        "git_commit": str(build_identity.get("git_commit") or verified_release.get("git_commit") or ""),
        "git_branch": str(build_identity.get("git_branch") or verified_release.get("git_branch") or ""),
        "acceptance_status": str(acceptance.get("status") or verified_release.get("acceptance_status") or ""),
        "version_audit_status": str(version_audit.get("status") or ""),
        "immutable_audit_status": str(immutable_audit.get("status") or ""),
        "verified_release_channel": str(verified_release.get("channel_name") or ""),
        "signature_key_id": str(verified_release_signature.get("key_id") or signing_public_key.get("key_id") or ""),
        "signature_status": str(verified_release_signature.get("schema") or ""),
        "data_schema_version_expected": _extract_runtime_constant(package_root, "DATA_ROOT_SCHEMA_VERSION"),
        "data_manifest_schema_expected": _extract_runtime_constant(package_root, "DATA_ROOT_MANIFEST_SCHEMA"),
        "build_identity": build_identity,
        "verified_release": verified_release,
        "verified_release_signature": verified_release_signature,
        "signing_public_key": signing_public_key,
        "acceptance": acceptance,
        "version_audit": version_audit,
        "immutable_audit": immutable_audit,
        "has_data_payload": (package_root / "data").exists() and any((package_root / "data").rglob("*")),
    }


def _installed_summary(install_root: Path) -> Dict[str, Any]:
    install_manifest_path = install_root / "mole_install_manifest_v1.json"
    build_identity_path = install_root / "runtime" / "config" / "mole_build_identity_v1.json"
    data_root_manifest_path = install_root / "data" / "data_root_manifest_v1.json"
    data_root = install_root / "data"
    legacy_runtime_data_root = install_root / "runtime" / "mole_das_data"
    restore_points_root = _restore_points_root(install_root)
    restore_points = _inventory_restore_points(install_root)
    latest_restore_point = dict(restore_points[0]) if restore_points else {}
    rollback_report_root = install_root / "_rollback_reports"
    rollback_report_latest_txt = rollback_report_root / _ROLLBACK_REPORT_LATEST_TXT
    rollback_report_latest_json = rollback_report_root / _ROLLBACK_REPORT_LATEST_JSON
    wizard_exe = install_root / "runtime" / "MOLE_code" / "MOLE_DAS_Wizard.exe"
    uninstall_script = install_root / "UNINSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
    install_manifest = _load_json(install_manifest_path)
    build_identity = _load_json(build_identity_path)
    data_manifest = _load_json(data_root_manifest_path)
    return {
        "install_root": str(install_root),
        "exists": install_root.exists(),
        "install_manifest_path": str(install_manifest_path),
        "build_identity_path": str(build_identity_path),
        "data_root_manifest_path": str(data_root_manifest_path),
        "data_root": str(data_root),
        "legacy_runtime_data_root": str(legacy_runtime_data_root),
        "migration_backup_root": str(data_root / "backups" / "migrations"),
        "restore_points_root": str(restore_points_root),
        "restore_point_count": len(restore_points),
        "restore_points": restore_points,
        "latest_restore_point_manifest_path": str(latest_restore_point.get("manifest_path") or ""),
        "latest_restore_point_bundle_label": str(latest_restore_point.get("bundle_label") or ""),
        "rollback_report_root": str(rollback_report_root),
        "rollback_report_latest_txt_path": str(rollback_report_latest_txt),
        "rollback_report_latest_json_path": str(rollback_report_latest_json),
        "wizard_exe_path": str(wizard_exe),
        "uninstall_script_path": str(uninstall_script),
        "bundle_label": str(build_identity.get("bundle_label") or install_manifest.get("bundle_label") or ""),
        "installed_at": str(install_manifest.get("installed_at") or ""),
        "data_schema_version": str(data_manifest.get("data_schema_version") or ""),
        "data_manifest_present": data_root_manifest_path.exists(),
        "install_manifest": install_manifest,
        "build_identity": build_identity,
        "data_manifest": data_manifest,
        "legacy_runtime_payload": _summarize_mutable_payload(legacy_runtime_data_root),
    }


def _open_path(path_value: str) -> None:
    path = Path(path_value)
    if not path.exists():
        messagebox.showwarning("Open Path", f"Path not found:\n{path}")
        return
    os.startfile(str(path))


def _run_powershell(script_path: Path, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *args,
    ]
    return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)


def _verify_package_with_installer(
    package: Dict[str, Any], package_root: Path, *, bootstrap_package_verification: bool = False
) -> tuple[bool, Dict[str, Any], str]:
    installer_script = Path(str(package.get("installer_script_path") or ""))
    if not installer_script.exists():
        return False, {}, f"Installer script is missing:\n{installer_script}"
    args = ["-VerifyPackageOnly", "-Quiet"]
    if bootstrap_package_verification:
        args.append("-BootstrapPackageVerification")
    result = _run_powershell(installer_script, args, package_root)
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    payload: Dict[str, Any] = {}
    if stdout:
        try:
            payload = json.loads(stdout)
        except Exception:
            payload = {}
    if result.returncode != 0:
        detail = stderr or stdout or f"Exit code: {result.returncode}"
        return False, payload, detail
    if payload and str(payload.get("status") or "") != "PASS":
        return False, payload, stdout or "Signed package verification did not return PASS."
    return True, payload, stdout or "Signed package verification passed."


class InstallClient(tk.Tk):
    def __init__(self, package_root: Path, *, install_root: Path | None = None) -> None:
        super().__init__()
        self.package_root = package_root
        self.package = _package_summary(package_root)
        self.title("MOLE-DAS Installation Client")
        self.geometry("1040x760")
        self.configure(bg="#0b1118")
        try:
            icon = package_root / "MOLE_DAS.ico"
            if icon.exists():
                self.iconbitmap(default=str(icon))
        except Exception:
            pass

        self.install_root_var = tk.StringVar(value=str((install_root or _default_install_root()).resolve()))
        self.launch_after_install_var = tk.BooleanVar(value=True)
        self.desktop_shortcut_var = tk.BooleanVar(value=True)
        self.start_menu_var = tk.BooleanVar(value=True)
        self.uninstall_reg_var = tk.BooleanVar(value=True)
        self.current_install = _installed_summary(Path(self.install_root_var.get()))
        self.upgrade_plan: Dict[str, Any] = {}
        self.upgrade_delta: Dict[str, Any] = {}
        self.rollback_plan: Dict[str, Any] = {}
        self.rollback_delta: Dict[str, Any] = {}

        self._build_ui()
        self._refresh_state()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(outer, text="MOLE-DAS Installation Client", font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w")
        subtitle = ttk.Label(
            outer,
            text="1. Verify package. 2. Choose install root. 3. Install, upgrade, repair, or uninstall.",
        )
        subtitle.pack(anchor="w", pady=(0, 12))

        top = ttk.Frame(outer)
        top.pack(fill="x")

        package_box = ttk.LabelFrame(top, text="Package Verification", padding=12)
        package_box.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.package_text = tk.Text(package_box, height=11, width=60, wrap="word")
        self.package_text.pack(fill="both", expand=True)

        install_box = ttk.LabelFrame(top, text="Install Target", padding=12)
        install_box.pack(side="left", fill="both", expand=True)
        entry_row = ttk.Frame(install_box)
        entry_row.pack(fill="x")
        ttk.Entry(entry_row, textvariable=self.install_root_var).pack(side="left", fill="x", expand=True)
        ttk.Button(entry_row, text="Browse", command=self._browse_install_root).pack(side="left", padx=(8, 0))
        self.install_text = tk.Text(install_box, height=11, width=48, wrap="word")
        self.install_text.pack(fill="both", expand=True, pady=(8, 0))

        plan_box = ttk.LabelFrame(outer, text="Upgrade Plan", padding=12)
        plan_box.pack(fill="x", pady=(12, 0))
        self.plan_text = tk.Text(plan_box, height=8, wrap="word")
        self.plan_text.pack(fill="both", expand=True)

        delta_box = ttk.LabelFrame(outer, text="Preflight Delta Review", padding=12)
        delta_box.pack(fill="both", expand=True, pady=(12, 0))
        self.delta_text = tk.Text(delta_box, height=14, wrap="word")
        self.delta_text.pack(fill="both", expand=True)

        options = ttk.LabelFrame(outer, text="Options", padding=12)
        options.pack(fill="x", pady=(12, 0))
        ttk.Checkbutton(options, text="Launch Wizard after install", variable=self.launch_after_install_var).pack(anchor="w")
        ttk.Checkbutton(options, text="Create Desktop shortcut", variable=self.desktop_shortcut_var).pack(anchor="w")
        ttk.Checkbutton(options, text="Create Start Menu shortcuts", variable=self.start_menu_var).pack(anchor="w")
        ttk.Checkbutton(options, text="Register uninstall entry", variable=self.uninstall_reg_var).pack(anchor="w")

        actions = ttk.LabelFrame(outer, text="Actions", padding=12)
        actions.pack(fill="x", pady=(12, 0))
        row1 = ttk.Frame(actions)
        row1.pack(fill="x")
        ttk.Button(row1, text="Refresh", command=self._refresh_state).pack(side="left")
        ttk.Button(row1, text="Validate Package", command=self._validate_package).pack(side="left", padx=(8, 0))
        ttk.Button(row1, text="Preview Upgrade Plan", command=self._preview_upgrade_plan).pack(side="left", padx=(8, 0))
        ttk.Button(row1, text="Preview Delta Review", command=self._preview_delta_review).pack(side="left", padx=(8, 0))
        ttk.Button(row1, text="Export Upgrade Report", command=self._export_upgrade_report).pack(side="left", padx=(8, 0))
        ttk.Button(row1, text="Install / Upgrade", command=self._install_package).pack(side="left", padx=(8, 0))
        ttk.Button(row1, text="Upgrade + Relaunch", command=self._upgrade_and_relaunch).pack(side="left", padx=(8, 0))
        ttk.Button(row1, text="Repair Install", command=self._repair_install).pack(side="left", padx=(8, 0))
        row2 = ttk.Frame(actions)
        row2.pack(fill="x", pady=(8, 0))
        ttk.Button(row2, text="Preview Rollback Plan", command=self._preview_rollback_plan).pack(side="left")
        ttk.Button(row2, text="Export Rollback Report", command=self._export_rollback_report).pack(side="left", padx=(8, 0))
        ttk.Button(row2, text="Rollback / Restore", command=self._rollback_restore).pack(side="left", padx=(8, 0))
        ttk.Button(row2, text="Uninstall Installed Copy", command=self._uninstall_install).pack(side="left", padx=(8, 0))
        row3 = ttk.Frame(actions)
        row3.pack(fill="x", pady=(8, 0))
        ttk.Button(row3, text="Launch Installed App", command=self._launch_installed).pack(side="left")
        ttk.Button(row3, text="Open Install Root", command=lambda: _open_path(self.install_root_var.get())).pack(side="left", padx=(8, 0))
        ttk.Button(row3, text="Open Acceptance Summary", command=lambda: _open_path(self.package["acceptance_json_path"])).pack(side="left", padx=(8, 0))
        ttk.Button(row3, text="Open Verified Release", command=lambda: _open_path(self.package["verified_release_path"])).pack(side="left", padx=(8, 0))

        log_box = ttk.LabelFrame(outer, text="Install Log", padding=12)
        log_box.pack(fill="both", expand=True, pady=(12, 0))
        self.log = tk.Text(log_box, wrap="word")
        self.log.pack(fill="both", expand=True)

    def _browse_install_root(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.install_root_var.get() or str(Path.home()))
        if selected:
            self.install_root_var.set(str(Path(selected).resolve()))
            self._refresh_state()

    def _write_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _append_log(self, content: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", content.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _show_text_dialog(self, title: str, content: str, *, confirm_label: str = "") -> bool:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("920x720")

        outer = ttk.Frame(dialog, padding=12)
        outer.pack(fill="both", expand=True)

        text = tk.Text(outer, wrap="word")
        text.pack(fill="both", expand=True)
        text.insert("1.0", content.strip() or "(no details)")
        text.configure(state="disabled")

        button_row = ttk.Frame(outer)
        button_row.pack(fill="x", pady=(12, 0))

        result = {"confirmed": False}

        def close_with(value: bool) -> None:
            result["confirmed"] = value
            dialog.destroy()

        if confirm_label:
            ttk.Button(button_row, text=confirm_label, command=lambda: close_with(True)).pack(side="left")
            ttk.Button(button_row, text="Cancel", command=lambda: close_with(False)).pack(side="left", padx=(8, 0))
        else:
            ttk.Button(button_row, text="Close", command=lambda: close_with(False)).pack(side="left")

        dialog.protocol("WM_DELETE_WINDOW", lambda: close_with(False))
        self.wait_window(dialog)
        return bool(result["confirmed"])

    def _refresh_state(self) -> None:
        self.package = _package_summary(self.package_root)
        self.current_install = _installed_summary(Path(self.install_root_var.get()))
        self.upgrade_plan = _build_upgrade_plan(self.package, self.current_install)
        self.upgrade_delta = _build_upgrade_delta(self.package, self.current_install)
        self.rollback_plan = _build_rollback_plan(self.package, self.current_install)
        self.rollback_delta = _build_rollback_delta(self.current_install, self.rollback_plan)
        package_lines = [
            f"Package label: {self.package['package_label']}",
            f"Git commit: {self.package['git_commit']}",
            f"Git branch: {self.package['git_branch']}",
            f"Acceptance: {self.package['acceptance_status'] or '(missing)'}",
            f"Version audit: {self.package['version_audit_status'] or '(missing)'}",
            f"Immutable audit: {self.package['immutable_audit_status'] or '(missing)'}",
            f"Verified channel: {self.package['verified_release_channel'] or '(none)'}",
            f"Signing key: {self.package['signature_key_id'] or '(missing)'}",
            f"Signature schema: {self.package['signature_status'] or '(missing)'}",
            f"Expected data schema: {self.package['data_schema_version_expected'] or '(unknown)'}",
            f"Package root: {self.package['package_root']}",
            f"Runtime root: {self.package['runtime_root']}",
            f"Portable data payload present: {'yes' if self.package['has_data_payload'] else 'no'}",
        ]
        install_lines = [
            f"Install root: {self.current_install['install_root']}",
            f"Installed: {'yes' if self.current_install['exists'] else 'no'}",
            f"Installed label: {self.current_install['bundle_label'] or '(none)'}",
            f"Installed at: {self.current_install['installed_at'] or '(unknown)'}",
            f"Data manifest present: {'yes' if self.current_install['data_manifest_present'] else 'no'}",
            f"Data schema version: {self.current_install['data_schema_version'] or '(none)'}",
            f"Legacy runtime payload present: {'yes' if self.current_install['legacy_runtime_payload'].get('has_payload') else 'no'}",
            f"Restore points available: {self.current_install['restore_point_count']}",
            f"Latest restore point: {self.current_install['latest_restore_point_bundle_label'] or '(none)'}",
            f"Data root: {self.current_install['data_root']}",
            f"Restore-point root: {self.current_install['restore_points_root']}",
            f"Rollback report root: {self.current_install['rollback_report_root']}",
            f"Wizard path: {self.current_install['wizard_exe_path']}",
        ]
        plan_lines = [
            f"Summary: {self.upgrade_plan.get('summary') or '(none)'}",
            *list(self.upgrade_plan.get("lines") or []),
        ]
        delta_lines = list(self.upgrade_delta.get("lines") or [])
        rollback_lines = [
            "",
            "",
            "Rollback Summary:",
            f"Summary: {self.rollback_plan.get('summary') or '(none)'}",
            *list(self.rollback_plan.get("lines") or []),
            "",
            *list(self.rollback_delta.get("lines") or []),
        ]
        self._write_text(self.package_text, "\n".join(package_lines))
        self._write_text(self.install_text, "\n".join(install_lines))
        self._write_text(self.plan_text, "\n".join(plan_lines))
        self._write_text(self.delta_text, "\n".join(delta_lines + rollback_lines))

    def _validate_package(self) -> bool:
        failures = []
        if self.package["acceptance_status"] != "PASS":
            failures.append("Packaged acceptance is not PASS.")
        if self.package["version_audit_status"] != "PASS":
            failures.append("Package version audit is not PASS.")
        if self.package["immutable_audit_status"] != "PASS":
            failures.append("Immutable package audit is not PASS.")
        if not Path(self.package["installer_script_path"]).exists():
            failures.append("Installer script is missing.")
        if failures:
            messagebox.showerror("Validate Package", "\n".join(failures))
            self._append_log("Package validation failed:\n" + "\n".join(failures))
            return False
        ok, payload, detail = _verify_package_with_installer(self.package, self.package_root)
        if not ok:
            messagebox.showerror("Validate Package", f"Signed package verification failed.\n\n{detail}")
            self._append_log("Signed package verification failed:\n" + detail)
            return False
        verified_label = str(payload.get("package_label") or self.package["package_label"])
        verified_key = str(payload.get("key_id") or self.package["signature_key_id"] or "(unknown)")
        self._append_log(f"Package validation passed for {verified_label} using signing key {verified_key}.")
        messagebox.showinfo("Validate Package", f"Package validation passed.\n\nSigning key: {verified_key}")
        return True

    def _ensure_signed_package(self, action_label: str) -> bool:
        ok, payload, detail = _verify_package_with_installer(self.package, self.package_root)
        if not ok:
            messagebox.showerror(action_label, f"Signed package verification failed.\n\n{detail}")
            self._append_log(f"{action_label}: signed package verification failed.\n{detail}")
            return False
        verified_label = str(payload.get("package_label") or self.package["package_label"])
        verified_key = str(payload.get("key_id") or self.package["signature_key_id"] or "(unknown)")
        self._append_log(f"{action_label}: signed package verification passed for {verified_label} using signing key {verified_key}.")
        return True

    def _install_args(self, *, force_launch: bool = False) -> list[str]:
        args = ["-InstallRoot", self.install_root_var.get()]
        if not self.launch_after_install_var.get() and not force_launch:
            args.append("-NoLaunch")
        if not self.desktop_shortcut_var.get():
            args.append("-NoDesktopShortcut")
        if not self.start_menu_var.get():
            args.append("-NoStartMenuShortcut")
        if not self.uninstall_reg_var.get():
            args.append("-NoUninstallRegistration")
        return args

    def _preview_upgrade_plan(self) -> None:
        self._refresh_state()
        plan_lines = list(self.upgrade_plan.get("lines") or [])
        detail = "\n".join(plan_lines).strip() or "No upgrade plan is available."
        self._append_log("Upgrade plan preview:\n" + detail)
        messagebox.showinfo("Upgrade Plan", detail)

    def _preview_delta_review(self) -> None:
        self._refresh_state()
        delta_lines = list(self.upgrade_delta.get("lines") or [])
        detail = "\n".join(delta_lines).strip() or "No delta review is available."
        self._append_log("Preflight delta review:\n" + detail)
        self._show_text_dialog("Preflight Delta Review", detail)

    def _preview_rollback_plan(self) -> None:
        self._refresh_state()
        detail = _build_rollback_review_text(self.rollback_plan, self.rollback_delta).strip() or "No rollback plan is available."
        self._append_log("Rollback plan preview:\n" + detail)
        self._show_text_dialog("Rollback Plan", detail)

    def _export_upgrade_report(self, *, output_dir: str = "") -> Dict[str, str] | None:
        self._refresh_state()
        default_dir = _default_upgrade_report_dir(self.package_root, Path(self.install_root_var.get()))
        target_dir = output_dir.strip()
        if not target_dir:
            selected = filedialog.askdirectory(initialdir=str(default_dir))
            if not selected:
                self._append_log("Upgrade report export canceled by user.")
                return None
            target_dir = selected
        report = _build_upgrade_report(self.package, self.current_install, self.upgrade_plan, self.upgrade_delta)
        try:
            result = _write_upgrade_report(report, Path(target_dir))
        except Exception as exc:
            messagebox.showerror("Export Upgrade Report", f"Failed to write upgrade report.\n\n{exc}")
            self._append_log(f"Upgrade report export failed: {exc}")
            return None
        self._append_log(
            "Upgrade report exported:\n"
            f"  TXT: {result['txt_path']}\n"
            f"  JSON: {result['json_path']}"
        )
        if not output_dir:
            messagebox.showinfo(
                "Export Upgrade Report",
                f"Upgrade report exported.\n\nTXT:\n{result['txt_path']}\n\nJSON:\n{result['json_path']}",
            )
        return result

    def _export_rollback_report(self, *, output_dir: str = "") -> Dict[str, str] | None:
        self._refresh_state()
        default_dir = _default_rollback_report_dir(self.package_root, Path(self.install_root_var.get()))
        target_dir = output_dir.strip()
        if not target_dir:
            selected = filedialog.askdirectory(initialdir=str(default_dir))
            if not selected:
                self._append_log("Rollback report export canceled by user.")
                return None
            target_dir = selected
        report = _build_rollback_report(self.package, self.current_install, self.rollback_plan, self.rollback_delta)
        try:
            result = _write_rollback_report(report, Path(target_dir))
        except Exception as exc:
            messagebox.showerror("Export Rollback Report", f"Failed to write rollback report.\n\n{exc}")
            self._append_log(f"Rollback report export failed: {exc}")
            return None
        self._append_log(
            "Rollback report exported:\n"
            f"  TXT: {result['txt_path']}\n"
            f"  JSON: {result['json_path']}"
        )
        if not output_dir:
            messagebox.showinfo(
                "Export Rollback Report",
                f"Rollback report exported.\n\nTXT:\n{result['txt_path']}\n\nJSON:\n{result['json_path']}",
            )
        return result

    def _run_async(self, label: str, script_path: Path, args: list[str]) -> None:
        def worker() -> None:
            self._append_log(f"{label} started.")
            result = _run_powershell(script_path, args, self.package_root)
            if result.stdout:
                self._append_log(result.stdout)
            if result.stderr:
                self._append_log(result.stderr)
            if result.returncode == 0:
                self._append_log(f"{label} completed successfully.")
                self.after(0, self._refresh_state)
                self.after(0, lambda: messagebox.showinfo(label, f"{label} completed successfully."))
            else:
                self._append_log(f"{label} failed with exit code {result.returncode}.")
                self.after(0, lambda: messagebox.showerror(label, f"{label} failed.\n\nExit code: {result.returncode}"))

        threading.Thread(target=worker, daemon=True).start()

    def _install_package(self) -> None:
        if not self._ensure_signed_package("Install / Upgrade"):
            return
        self._run_async("Install / Upgrade", Path(self.package["installer_script_path"]), self._install_args())

    def _upgrade_and_relaunch(self) -> None:
        self._refresh_state()
        if not self._validate_package():
            return
        detail = _build_upgrade_review_text(self.upgrade_plan, self.upgrade_delta)
        ok = self._show_text_dialog(
            "Upgrade + Relaunch Review",
            detail + "\n\nContinue with the verified install and relaunch?",
            confirm_label="Continue",
        )
        if not ok:
            self._append_log("Upgrade + Relaunch canceled by user.")
            return
        export_result = self._export_upgrade_report(output_dir=str(_default_upgrade_report_dir(self.package_root, Path(self.install_root_var.get()))))
        if not export_result:
            self._append_log("Upgrade + Relaunch aborted because the upgrade report could not be exported.")
            return
        self._append_log("Upgrade + Relaunch confirmed.\n" + detail)
        self._append_log(
            "Upgrade + Relaunch report:\n"
            f"  TXT: {export_result['txt_path']}\n"
            f"  JSON: {export_result['json_path']}"
        )
        self._run_async("Upgrade + Relaunch", Path(self.package["installer_script_path"]), self._install_args(force_launch=True))

    def _rollback_restore(self) -> None:
        self._refresh_state()
        if not self._ensure_signed_package("Rollback / Restore"):
            return
        if str(self.rollback_plan.get("action") or "") != "ROLLBACK":
            messagebox.showwarning("Rollback / Restore", self.rollback_plan.get("summary") or "No restore point is available.")
            self._append_log("Rollback / Restore unavailable: " + str(self.rollback_plan.get("summary") or "No restore point is available."))
            return
        detail = _build_rollback_review_text(self.rollback_plan, self.rollback_delta)
        ok = self._show_text_dialog(
            "Rollback / Restore Review",
            detail + "\n\nContinue with the data-root restore and relaunch?",
            confirm_label="Restore",
        )
        if not ok:
            self._append_log("Rollback / Restore canceled by user.")
            return
        export_result = self._export_rollback_report(
            output_dir=str(_default_rollback_report_dir(self.package_root, Path(self.install_root_var.get())))
        )
        if not export_result:
            self._append_log("Rollback / Restore aborted because the rollback report could not be exported.")
            return

        def worker() -> None:
            try:
                result = _apply_rollback_restore(self.package, self.current_install, self.rollback_plan, self.rollback_delta)
            except Exception as exc:
                self._append_log(f"Rollback / Restore failed: {exc}")
                self.after(0, lambda: messagebox.showerror("Rollback / Restore", f"Rollback / Restore failed.\n\n{exc}"))
                return
            self._append_log("Rollback / Restore completed successfully.")
            self._append_log(
                "Rollback / Restore result:\n"
                f"  Restore point: {result.get('restore_point_manifest_path','')}\n"
                f"  Pre-restore snapshot: {result.get('pre_restore_point_manifest_path','')}\n"
                f"  Data root: {result.get('data_root','')}"
            )
            self.after(0, self._refresh_state)
            self.after(0, lambda: messagebox.showinfo("Rollback / Restore", "Rollback / Restore completed successfully."))

        threading.Thread(target=worker, daemon=True).start()

    def _repair_install(self) -> None:
        if not self._ensure_signed_package("Repair Install"):
            return
        self._run_async("Repair Install", Path(self.package["installer_script_path"]), self._install_args())

    def _uninstall_install(self) -> None:
        uninstall_script = Path(self.current_install["uninstall_script_path"])
        if not uninstall_script.exists():
            messagebox.showwarning("Uninstall", f"Uninstall script not found:\n{uninstall_script}")
            return
        self._run_async("Uninstall", uninstall_script, ["-InstallRoot", self.install_root_var.get()])

    def _launch_installed(self) -> None:
        if not self._ensure_signed_package("Launch Installed App"):
            return
        wizard = Path(self.current_install["wizard_exe_path"])
        if not wizard.exists():
            messagebox.showwarning("Launch Installed App", f"Installed Wizard not found:\n{wizard}")
            return
        subprocess.Popen([str(wizard)], cwd=str(wizard.parent))
        self._append_log(f"Launched installed Wizard: {wizard}")


def main() -> int:
    parser = argparse.ArgumentParser(description="MOLE-DAS installation client")
    parser.add_argument("--package-root", default="", help="Override package root")
    parser.add_argument("--install-root", default="", help="Override installed root to inspect or mutate")
    parser.add_argument("--headless-summary", action="store_true", help="Print package/install summary JSON and exit")
    parser.add_argument("--headless-verify-package", action="store_true", help="Run the signed package verification flow and print the result as JSON")
    parser.add_argument("--headless-export-upgrade-report", default="", help="Write upgrade report files to the given directory and print the output paths as JSON")
    parser.add_argument("--headless-export-rollback-report", default="", help="Write rollback report files to the given directory and print the output paths as JSON")
    parser.add_argument("--headless-apply-rollback", action="store_true", help="Apply the latest rollback restore point and print the result as JSON")
    parser.add_argument("--bootstrap-package-verification", action="store_true", help="Use signature-only bootstrap verification for pre-acceptance installer validation flows")
    args = parser.parse_args()

    package_root = _resolve_package_root(args.package_root or None)
    package = _package_summary(package_root)
    install_root = Path(args.install_root).expanduser().resolve() if args.install_root else _default_install_root()
    installed = _installed_summary(install_root)
    upgrade_plan = _build_upgrade_plan(package, installed)
    upgrade_delta = _build_upgrade_delta(package, installed)
    rollback_plan = _build_rollback_plan(package, installed)
    rollback_delta = _build_rollback_delta(installed, rollback_plan)
    if args.headless_summary:
        print(
            json.dumps(
                {
                    "schema": "mole_install_client_summary_v1",
                    "package": package,
                    "installed": installed,
                    "upgrade_plan": upgrade_plan,
                    "upgrade_delta": upgrade_delta,
                    "rollback_plan": rollback_plan,
                    "rollback_delta": rollback_delta,
                },
                indent=2,
            )
        )
        return 0
    if args.headless_verify_package:
        ok, payload, detail = _verify_package_with_installer(
            package, package_root, bootstrap_package_verification=args.bootstrap_package_verification
        )
        result_payload = {
            "schema": "mole_install_client_verify_package_v1",
            "status": "PASS" if ok else "FAIL",
            "detail": detail,
            "package_label": package.get("package_label") or "",
            "git_commit": package.get("git_commit") or "",
            "git_branch": package.get("git_branch") or "",
        }
        result_payload.update(payload or {})
        print(json.dumps(result_payload, indent=2))
        return 0 if ok else 1
    if args.headless_export_upgrade_report:
        report = _build_upgrade_report(package, installed, upgrade_plan, upgrade_delta)
        result = _write_upgrade_report(report, Path(args.headless_export_upgrade_report))
        print(json.dumps(result, indent=2))
        return 0
    if args.headless_export_rollback_report:
        report = _build_rollback_report(package, installed, rollback_plan, rollback_delta)
        result = _write_rollback_report(report, Path(args.headless_export_rollback_report))
        print(json.dumps(result, indent=2))
        return 0
    if args.headless_apply_rollback:
        ok, payload, detail = _verify_package_with_installer(
            package, package_root, bootstrap_package_verification=args.bootstrap_package_verification
        )
        if not ok:
            raise RuntimeError(f"Signed package verification failed before rollback restore.\n{detail}")
        report_dir = _default_rollback_report_dir(package_root, install_root)
        _write_rollback_report(_build_rollback_report(package, installed, rollback_plan, rollback_delta), report_dir)
        result = _apply_rollback_restore(package, installed, rollback_plan, rollback_delta, relaunch=False)
        print(json.dumps(result, indent=2))
        return 0

    app = InstallClient(package_root, install_root=install_root)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
