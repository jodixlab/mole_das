from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


SHEET_NAMES = [
    "mole_welcome_master_sheet_512.png",
    "mole_welcome_master_sheet_384.png",
    "mole_welcome_master_sheet_256.png",
    "mole_welcome_master_sheet_192.png",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _to_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.resolve().as_posix()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--manifest-path", default="config/mole_welcome_asset_manifest_v1.json")
    parser.add_argument("--source-key-art", default="output/imagegen/welcome_master/welcome_master_keyart_v3.png")
    parser.add_argument("--frames-dir", default="output/imagegen/welcome_master/frames")
    parser.add_argument("--sheets-dir", default="mole_assets/sprites")
    parser.add_argument("--prompt-version", default="welcome_animation_prompt_pack_2026_04_17_001")
    parser.add_argument("--approved-version-label", default="welcome_master_v1")
    parser.add_argument("--approval-status", choices=["approved", "pending", "rejected"], default="approved")
    parser.add_argument("--approved-by", default="codex")
    parser.add_argument("--approval-note", default="Approved welcome animation reel for packaged use.")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    manifest_path = (root / args.manifest_path).resolve()
    source_key_art = (root / args.source_key_art).resolve()
    frames_dir = (root / args.frames_dir).resolve()
    sheets_dir = (root / args.sheets_dir).resolve()

    if not source_key_art.exists():
        raise FileNotFoundError(f"Source key art not found: {source_key_art}")
    if not frames_dir.exists():
        raise FileNotFoundError(f"Frames directory not found: {frames_dir}")

    frames = sorted(frames_dir.glob("frame_*.png"))
    if not frames:
        raise FileNotFoundError(f"No animation frames found in: {frames_dir}")

    sheet_entries: list[dict[str, object]] = []
    for name in SHEET_NAMES:
        sheet_path = sheets_dir / name
        if not sheet_path.exists():
            raise FileNotFoundError(f"Missing assembled sheet: {sheet_path}")
        sheet_entries.append(
            {
                "file_name": name,
                "path": _to_rel(sheet_path, root),
                "sha256": _sha256(sheet_path),
            }
        )

    approved = args.approval_status == "approved"
    now_iso = datetime.now(timezone.utc).isoformat()

    existing: dict[str, object] = {}
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))

    manifest = {
        "schema": "mole_welcome_asset_manifest_v1",
        "asset_id": "mole_welcome_animation_reel",
        "asset_family": "welcome_animation",
        "asset_status": args.approval_status,
        "approved": approved,
        "approved_version_label": args.approved_version_label,
        "prompt_version": args.prompt_version,
        "source_key_art": {
            "path": _to_rel(source_key_art, root),
            "sha256": _sha256(source_key_art),
        },
        "frames_dir": _to_rel(frames_dir, root),
        "frame_count": len(frames),
        "assembled_sheets": sheet_entries,
        "approved_by": args.approved_by if approved else None,
        "approved_at": now_iso if approved else None,
        "approval_note": args.approval_note if approved else (args.approval_note or "Approval pending."),
        "packaged_build_version": existing.get("packaged_build_version"),
        "packaged_build_at": existing.get("packaged_build_at"),
        "updated_at": now_iso,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
