from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rooted(root: Path, maybe_rel: str) -> Path:
    path = Path(maybe_rel)
    if path.is_absolute():
        return path
    return (root / path).resolve()


def _build_contact_sheet(frames: list[Image.Image], out_path: Path) -> None:
    thumb_w = 256
    thumb_h = 256
    margin = 18
    label_h = 36
    cols = min(4, max(1, len(frames)))
    rows = (len(frames) + cols - 1) // cols
    canvas = Image.new("RGBA", (cols * (thumb_w + margin) + margin, rows * (thumb_h + label_h + margin) + margin), (8, 16, 25, 255))
    for idx, frame in enumerate(frames):
        row = idx // cols
        col = idx % cols
        x = margin + col * (thumb_w + margin)
        y = margin + row * (thumb_h + label_h + margin)
        thumb = ImageOps.contain(frame.convert("RGBA"), (thumb_w, thumb_h), Image.LANCZOS)
        framed = Image.new("RGBA", (thumb_w, thumb_h), (12, 25, 37, 255))
        px = (thumb_w - thumb.width) // 2
        py = (thumb_h - thumb.height) // 2
        framed.alpha_composite(thumb, (px, py))
        canvas.alpha_composite(framed, (x, y))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def _build_preview_gif(frames: list[Image.Image], out_path: Path) -> None:
    if not frames:
        raise ValueError("No frames available for preview GIF.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    resized = [ImageOps.contain(frame.convert("RGBA"), (512, 512), Image.LANCZOS).convert("P", palette=Image.ADAPTIVE) for frame in frames]
    resized[0].save(out_path, save_all=True, append_images=resized[1:], duration=130, loop=0, disposal=2)


def _load_frames_from_master_sheet(manifest: dict, root: Path) -> list[Image.Image]:
    frame_count = max(int(manifest.get("frame_count") or 0), 0)
    if frame_count <= 0:
        raise FileNotFoundError("Welcome asset manifest does not declare a positive frame_count.")

    sheet_specs = []
    for item in manifest.get("assembled_sheets", []) or []:
        if not isinstance(item, dict):
            continue
        candidate = _rooted(root, str(item.get("path") or ""))
        if not candidate.exists():
            continue
        match = str(item.get("file_name") or candidate.name)
        digits = "".join(ch for ch in match if ch.isdigit())
        resolution = int(digits) if digits else 0
        sheet_specs.append((resolution, candidate))
    if not sheet_specs:
        raise FileNotFoundError("No assembled welcome master sheet found for review-pack fallback.")

    sheet_specs.sort(key=lambda item: item[0], reverse=True)
    sheet_path = sheet_specs[0][1]
    sheet = Image.open(sheet_path).convert("RGBA")
    frame_width = sheet.width // frame_count
    if frame_width <= 0 or (frame_width * frame_count) != sheet.width:
        raise ValueError(f"Master sheet width {sheet.width} is not divisible by frame_count {frame_count}.")

    frames: list[Image.Image] = []
    for idx in range(frame_count):
        left = idx * frame_width
        frames.append(sheet.crop((left, 0, left + frame_width, sheet.height)).copy())
    return frames


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--manifest-path", default="config/mole_welcome_asset_manifest_v1.json")
    parser.add_argument("--output-dir", default="RELEASES/clean_release_workflow")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    manifest_path = _rooted(root, args.manifest_path)
    output_dir = _rooted(root, args.output_dir)
    manifest = _load_json(manifest_path)

    frames_dir = _rooted(root, manifest["frames_dir"])
    frame_paths = sorted(frames_dir.glob("frame_*.png")) if frames_dir.exists() else []
    if frame_paths:
        frames = [Image.open(path).convert("RGBA") for path in frame_paths]
        frame_source = "frame_dir"
    else:
        frames = _load_frames_from_master_sheet(manifest, root)
        frame_source = "master_sheet"
    contact_path = output_dir / "welcome_asset_contact_sheet.png"
    preview_path = output_dir / "welcome_asset_preview.gif"
    manifest_copy_path = output_dir / "welcome_asset_manifest.json"
    review_json_path = output_dir / "welcome_asset_review.json"
    review_md_path = output_dir / "welcome_asset_review.md"

    _build_contact_sheet(frames, contact_path)
    _build_preview_gif(frames, preview_path)
    manifest_copy_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    review = {
        "schema": "mole_welcome_asset_review_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_copy_path.name),
        "contact_sheet": str(contact_path.name),
        "preview_gif": str(preview_path.name),
        "asset_status": manifest.get("asset_status"),
        "approved": bool(manifest.get("approved")),
        "approved_version_label": manifest.get("approved_version_label"),
        "prompt_version": manifest.get("prompt_version"),
        "frame_count": len(frames),
        "frame_source": frame_source,
        "source_key_art": manifest.get("source_key_art", {}),
        "assembled_sheets": manifest.get("assembled_sheets", []),
    }
    review_json_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")

    md = [
        "# MOLE-DAS Welcome Asset Review",
        "",
        f"- Status: `{manifest.get('asset_status')}`",
        f"- Approved: `{bool(manifest.get('approved'))}`",
        f"- Approved version: `{manifest.get('approved_version_label')}`",
        f"- Prompt version: `{manifest.get('prompt_version')}`",
        f"- Frame count: `{len(frames)}`",
        f"- Frame source: `{frame_source}`",
        f"- Source key art: `{manifest.get('source_key_art', {}).get('path', '')}`",
        "",
        "Artifacts:",
        f"- `welcome_asset_manifest.json`",
        f"- `welcome_asset_contact_sheet.png`",
        f"- `welcome_asset_preview.gif`",
        f"- `welcome_asset_review.json`",
    ]
    review_md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(review_json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
