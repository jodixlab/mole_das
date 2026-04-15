from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _headings(path: Path, max_lines: int = 12) -> List[str]:
    lines: List[str] = []
    try:
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line:
                continue
            if path.suffix.lower() == ".md":
                if line.startswith("#"):
                    lines.append(line)
            else:
                if len(line) <= 120:
                    lines.append(line)
            if len(lines) >= max_lines:
                break
    except Exception:
        return []
    return lines


def _load_previous_state(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = _read_json(path)
    except Exception:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for item in payload.get("sources") or []:
        if isinstance(item, dict) and item.get("id"):
            out[str(item["id"])] = item
    return out


def _registry_doc_usage(entries: Dict[str, Any]) -> Dict[str, List[str]]:
    usage: Dict[str, List[str]] = {}
    for help_id, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        for ref in entry.get("doc_refs") or []:
            if not isinstance(ref, dict):
                continue
            doc_label = str(ref.get("doc_label") or ref.get("doc") or "").strip()
            if not doc_label:
                continue
            usage.setdefault(doc_label, []).append(str(help_id))
    for doc_label in usage:
        usage[doc_label] = sorted(set(usage[doc_label]))
    return usage


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a review pack for UI-help documentation updates.")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--write-state", action="store_true")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = repo_root / "config" / "mole_ui_help_doc_sources_v1.json"
    state_path = repo_root / "config" / "mole_ui_help_doc_sync_state_v1.json"
    registry_path = repo_root / "config" / "mole_ui_help_registry_v1.json"

    manifest = _read_json(manifest_path)
    prev_state = _load_previous_state(state_path)
    registry = _read_json(registry_path)
    entries = registry.get("entries") or {}
    doc_usage = _registry_doc_usage(entries if isinstance(entries, dict) else {})

    sources_out: List[Dict[str, Any]] = []
    changed_docs: List[Dict[str, Any]] = []
    missing_required: List[str] = []

    for src in manifest.get("sources") or []:
        if not isinstance(src, dict):
            continue
        src_id = str(src.get("id") or "").strip()
        doc_label = str(src.get("doc_label") or "").strip()
        rel_path = str(src.get("path") or "").replace("\\", "/").strip()
        required = bool(src.get("required"))
        abs_path = repo_root / rel_path
        exists = abs_path.exists()
        prev = prev_state.get(src_id, {})
        current_hash = _sha256(abs_path) if exists else ""
        previous_hash = str(prev.get("sha256") or "")
        changed = exists and bool(previous_hash) and previous_hash != current_hash
        first_seen = exists and not previous_hash
        referenced_help_ids = doc_usage.get(doc_label, [])
        item = {
            "id": src_id,
            "doc_label": doc_label,
            "path": rel_path,
            "exists": exists,
            "required": required,
            "sha256": current_hash,
            "previous_sha256": previous_hash,
            "changed": changed,
            "first_seen": first_seen,
            "referenced_help_id_count": len(referenced_help_ids),
            "referenced_help_ids": referenced_help_ids,
            "preview_headings": _headings(abs_path) if exists else [],
        }
        sources_out.append(item)
        if required and not exists:
            missing_required.append(src_id)
        if changed or first_seen:
            changed_docs.append(item)

    status = "PASS"
    if missing_required:
        status = "FAIL"
    elif changed_docs:
        status = "REVIEW_NEEDED"

    generated_utc = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema": "mole_ui_help_doc_update_pack_v1",
        "generated_utc": generated_utc,
        "source_manifest": str(manifest_path.relative_to(repo_root)).replace("\\", "/"),
        "registry_path": str(registry_path.relative_to(repo_root)).replace("\\", "/"),
        "status": status,
        "source_count": len(sources_out),
        "changed_doc_count": len(changed_docs),
        "missing_required_sources": missing_required,
        "sources": sources_out,
        "changed_docs": changed_docs,
        "review_note": "When a source doc changes, review the listed help IDs, update scripts/seed_ui_help_registry.py or manual registry entries as needed, then rerun seed + audit.",
    }

    _write_json(output_dir / "ui_help_doc_update_pack.json", payload)

    lines = [
        "# MOLE-DAS UI Help Documentation Update Pack",
        "",
        f"- Status: `{status}`",
        f"- Source count: `{len(sources_out)}`",
        f"- Changed docs: `{len(changed_docs)}`",
        "",
    ]
    if missing_required:
        lines.append("## Missing required sources")
        for src_id in missing_required:
            lines.append(f"- `{src_id}`")
        lines.append("")
    if changed_docs:
        lines.append("## Docs requiring review")
        for item in changed_docs:
            lines.append(f"- `{item['doc_label']}` -> `{item['path']}`")
            lines.append(f"  - referenced help IDs: `{item['referenced_help_id_count']}`")
            for help_id in item.get("referenced_help_ids", [])[:20]:
                lines.append(f"    - `{help_id}`")
        lines.append("")
    else:
        lines.append("## Docs requiring review")
        lines.append("- none")
        lines.append("")
    lines.append("## Review process")
    lines.append("1. Update the source documentation.")
    lines.append("2. Run `scripts/build_ui_help_doc_update_pack.py`.")
    lines.append("3. Review changed docs and listed help IDs.")
    lines.append("4. Update `scripts/seed_ui_help_registry.py` or manual registry entries as needed.")
    lines.append("5. Re-run `scripts/seed_ui_help_registry.py` and `scripts/audit_ui_help_registry.py`.")
    lines.append("")
    _write_text(output_dir / "ui_help_doc_update_pack.md", "\n".join(lines) + "\n")

    if args.write_state:
        state_payload = {
            "schema": "mole_ui_help_doc_sync_state_v1",
            "generated_utc": generated_utc,
            "source_manifest": str(manifest_path.relative_to(repo_root)).replace("\\", "/"),
            "sources": [
                {
                    "id": item["id"],
                    "doc_label": item["doc_label"],
                    "path": item["path"],
                    "sha256": item["sha256"],
                }
                for item in sources_out
                if item.get("exists")
            ],
        }
        _write_json(state_path, state_payload)

    print(json.dumps(payload, indent=2))
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
