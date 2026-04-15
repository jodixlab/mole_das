from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ANCHOR_LINE_RE = re.compile(
    r"(?:<!--\s*HELP_ID:\s*([a-z0-9_\.]+)\s*-->)|(?:\[\s*HELP_ID:\s*([a-z0-9_\.]+)\s*\])",
    re.IGNORECASE,
)


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


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


def _load_previous_anchor_state(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = _read_json(path)
    except Exception:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for item in payload.get("anchors") or []:
        if isinstance(item, dict) and item.get("help_id"):
            out[str(item["help_id"])] = item
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


def _registry_entry_text(entry: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("label", "short_description", "definition", "process_note"):
        value = str(entry.get(key) or "").strip()
        if value:
            parts.append(f"{key}: {value}")
    return "\n".join(parts).strip()


def _extract_anchor_id(line: str) -> str:
    match = ANCHOR_LINE_RE.search(line)
    if not match:
        return ""
    return str(match.group(1) or match.group(2) or "").strip()


def _parse_doc_anchors(path: Path, max_excerpt_lines: int = 10) -> Dict[str, Dict[str, Any]]:
    anchors: Dict[str, Dict[str, Any]] = {}
    try:
        raw_lines = path.read_text(encoding="utf-8-sig").splitlines()
    except Exception:
        return anchors

    pending_ids: List[str] = []
    excerpt_lines: List[str] = []
    first_anchor_line = 0

    def _flush() -> None:
        nonlocal pending_ids, excerpt_lines, first_anchor_line
        if not pending_ids:
            return
        excerpt = "\n".join(line for line in excerpt_lines if line.strip()).strip()
        for help_id in pending_ids:
            anchors[help_id] = {
                "help_id": help_id,
                "anchor_line": first_anchor_line,
                "excerpt": excerpt,
                "excerpt_hash": _hash_text(excerpt),
                "excerpt_line_count": len([line for line in excerpt_lines if line.strip()]),
            }
        pending_ids = []
        excerpt_lines = []
        first_anchor_line = 0

    for idx, raw_line in enumerate(raw_lines, start=1):
        help_id = _extract_anchor_id(raw_line)
        if help_id:
            if pending_ids and excerpt_lines:
                _flush()
            if not pending_ids:
                first_anchor_line = idx
            pending_ids.append(help_id)
            continue

        if not pending_ids:
            continue

        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            if len([item for item in excerpt_lines if item.strip()]) >= 2:
                _flush()
            continue

        excerpt_lines.append(stripped)
        if len([item for item in excerpt_lines if item.strip()]) >= max_excerpt_lines:
            _flush()

    if pending_ids:
        _flush()

    return anchors


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
    anchor_contract_path = repo_root / "config" / "mole_ui_help_anchor_contract_v1.json"
    anchor_state_path = repo_root / "config" / "mole_ui_help_anchor_sync_state_v1.json"
    registry_path = repo_root / "config" / "mole_ui_help_registry_v1.json"

    manifest = _read_json(manifest_path)
    prev_state = _load_previous_state(state_path)
    prev_anchor_state = _load_previous_anchor_state(anchor_state_path)
    registry = _read_json(registry_path)
    anchor_contract = _read_json(anchor_contract_path)
    entries = registry.get("entries") or {}
    doc_usage = _registry_doc_usage(entries if isinstance(entries, dict) else {})

    source_index: Dict[str, Dict[str, Any]] = {}
    doc_label_to_id: Dict[str, str] = {}
    parsed_doc_anchors: Dict[str, Dict[str, Dict[str, Any]]] = {}
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
        source_index[src_id] = item
        if doc_label:
            doc_label_to_id[doc_label] = src_id
        if exists:
            parsed_doc_anchors[src_id] = _parse_doc_anchors(abs_path)
        else:
            parsed_doc_anchors[src_id] = {}
        sources_out.append(item)
        if required and not exists:
            missing_required.append(src_id)
        if changed or first_seen:
            changed_docs.append(item)

    anchor_results: List[Dict[str, Any]] = []
    missing_anchor_contracts: List[str] = []
    anchor_review_needed: List[str] = []

    for item in anchor_contract.get("required_anchors") or []:
        if not isinstance(item, dict):
            continue
        help_id = str(item.get("help_id") or "").strip()
        doc_id = str(item.get("doc_id") or "").strip()
        if not help_id or not doc_id:
            continue
        doc_info = source_index.get(doc_id)
        if not isinstance(doc_info, dict):
            missing_anchor_contracts.append(help_id)
            continue
        doc_anchors = parsed_doc_anchors.get(doc_id, {})
        anchor_info = doc_anchors.get(help_id, {})
        registry_entry = entries.get(help_id, {}) if isinstance(entries, dict) else {}
        registry_text = _registry_entry_text(registry_entry if isinstance(registry_entry, dict) else {})
        registry_hash = _hash_text(registry_text)
        source_excerpt = str(anchor_info.get("excerpt") or "").strip()
        excerpt_hash = str(anchor_info.get("excerpt_hash") or "")
        previous = prev_anchor_state.get(help_id, {})
        previous_excerpt_hash = str(previous.get("excerpt_hash") or "")
        previous_registry_hash = str(previous.get("registry_hash") or "")
        anchor_exists = bool(anchor_info)
        registry_exists = isinstance(registry_entry, dict) and bool(registry_entry)
        first_seen = bool(anchor_exists and not previous_excerpt_hash)
        excerpt_changed = bool(anchor_exists and previous_excerpt_hash and previous_excerpt_hash != excerpt_hash)
        registry_changed = bool(registry_exists and previous_registry_hash and previous_registry_hash != registry_hash)
        needs_review = bool(first_seen or excerpt_changed or registry_changed)
        if needs_review:
            anchor_review_needed.append(help_id)
        anchor_results.append(
            {
                "help_id": help_id,
                "doc_id": doc_id,
                "doc_label": doc_info.get("doc_label"),
                "path": doc_info.get("path"),
                "required": True,
                "registry_exists": registry_exists,
                "anchor_exists": anchor_exists,
                "anchor_line": anchor_info.get("anchor_line"),
                "source_excerpt": source_excerpt,
                "source_excerpt_hash": excerpt_hash,
                "previous_excerpt_hash": previous_excerpt_hash,
                "excerpt_changed": excerpt_changed,
                "registry_snapshot": registry_text,
                "registry_hash": registry_hash,
                "previous_registry_hash": previous_registry_hash,
                "registry_changed": registry_changed,
                "first_seen": first_seen,
                "needs_review": needs_review,
                "contract_note": str(item.get("note") or "").strip(),
            }
        )

    missing_required_anchors = sorted(
        result["help_id"]
        for result in anchor_results
        if not result["anchor_exists"] or not result["registry_exists"]
    )

    status = "PASS"
    if missing_required or missing_anchor_contracts or missing_required_anchors:
        status = "FAIL"
    elif changed_docs or anchor_review_needed:
        status = "REVIEW_NEEDED"

    generated_utc = datetime.now(timezone.utc).isoformat()

    if args.write_state and status != "FAIL":
        status = "PASS"

    payload = {
        "schema": "mole_ui_help_doc_update_pack_v2",
        "generated_utc": generated_utc,
        "source_manifest": str(manifest_path.relative_to(repo_root)).replace("\\", "/"),
        "anchor_contract_path": str(anchor_contract_path.relative_to(repo_root)).replace("\\", "/"),
        "anchor_state_path": str(anchor_state_path.relative_to(repo_root)).replace("\\", "/"),
        "registry_path": str(registry_path.relative_to(repo_root)).replace("\\", "/"),
        "status": status,
        "source_count": len(sources_out),
        "changed_doc_count": len(changed_docs),
        "missing_required_sources": missing_required,
        "anchor_required_count": len(anchor_results),
        "anchor_review_needed_count": len(anchor_review_needed),
        "missing_required_anchors": missing_required_anchors,
        "sources": sources_out,
        "changed_docs": changed_docs,
        "anchors": anchor_results,
        "review_note": "When a source doc or anchored excerpt changes, review the affected help IDs, update scripts/seed_ui_help_registry.py or manual registry entries as needed, then rerun seed + audit. Use --write-state only after accepting the reconciled tooltip language.",
    }

    _write_json(output_dir / "ui_help_doc_update_pack.json", payload)

    lines = [
        "# MOLE-DAS UI Help Documentation Update Pack",
        "",
        f"- Status: `{status}`",
        f"- Source count: `{len(sources_out)}`",
        f"- Changed docs: `{len(changed_docs)}`",
        f"- Anchored help IDs: `{len(anchor_results)}`",
        f"- Anchor reviews needed: `{len(anchor_review_needed)}`",
        "",
    ]
    if missing_required:
        lines.append("## Missing required sources")
        for src_id in missing_required:
            lines.append(f"- `{src_id}`")
        lines.append("")
    if missing_required_anchors:
        lines.append("## Missing required anchors")
        for help_id in missing_required_anchors:
            lines.append(f"- `{help_id}`")
        lines.append("")
    if changed_docs:
        lines.append("## Docs requiring review")
        for item in changed_docs:
            lines.append(f"- `{item['doc_label']}` -> `{item['path']}`")
            lines.append(f"  - referenced help IDs: `{item['referenced_help_id_count']}`")
        lines.append("")
    if anchor_results:
        lines.append("## Anchored help review")
        for item in anchor_results:
            if not item["needs_review"] and item["anchor_exists"] and item["registry_exists"]:
                continue
            lines.append(f"- `{item['help_id']}` -> `{item['doc_label']}`")
            lines.append(f"  - anchor exists: `{item['anchor_exists']}` | registry exists: `{item['registry_exists']}`")
            lines.append(f"  - first seen: `{item['first_seen']}` | excerpt changed: `{item['excerpt_changed']}` | registry changed: `{item['registry_changed']}`")
            if item["source_excerpt"]:
                lines.append("  - source excerpt:")
                for line in str(item["source_excerpt"]).splitlines()[:6]:
                    lines.append(f"    - {line}")
            if item["registry_snapshot"]:
                lines.append("  - registry snapshot:")
                for line in str(item["registry_snapshot"]).splitlines()[:6]:
                    lines.append(f"    - {line}")
        lines.append("")
    lines.append("## Review process")
    lines.append("1. Update the source documentation and anchored help excerpts.")
    lines.append("2. Run `scripts/build_ui_help_doc_update_pack.py` without `--write-state`.")
    lines.append("3. Review changed docs, anchor excerpts, and registry text deltas.")
    lines.append("4. Update `scripts/seed_ui_help_registry.py` or manual registry entries as needed.")
    lines.append("5. Re-run `scripts/seed_ui_help_registry.py` and `scripts/audit_ui_help_registry.py`.")
    lines.append("6. Run `scripts/build_ui_help_doc_update_pack.py --write-state` only after accepting the reconciled help language.")
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
        anchor_state_payload = {
            "schema": "mole_ui_help_anchor_sync_state_v1",
            "generated_utc": generated_utc,
            "anchor_contract_path": str(anchor_contract_path.relative_to(repo_root)).replace("\\", "/"),
            "anchors": [
                {
                    "help_id": item["help_id"],
                    "doc_id": item["doc_id"],
                    "doc_label": item["doc_label"],
                    "path": item["path"],
                    "excerpt_hash": item["source_excerpt_hash"],
                    "registry_hash": item["registry_hash"],
                }
                for item in anchor_results
                if item.get("anchor_exists") and item.get("registry_exists")
            ],
        }
        _write_json(anchor_state_path, anchor_state_payload)

    print(json.dumps(payload, indent=2))
    return 1 if status != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
