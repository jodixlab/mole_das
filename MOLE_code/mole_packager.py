"""MOLE Packager (v10.0.25A)

Deterministic runtime ZIP builder that:
  - validates package via preflight
  - writes BUILD_MANIFEST.json with sha256 for packaged files
  - zips files in stable order (path-sorted) to prevent "mystery deltas"

Packaging notes:
  - excludes workspace-only artifacts such as `.git`, `.vs`, office lock files,
    stale virtualenv folders, and SQLite WAL/SHM sidecars
  - excludes BUILD_MANIFEST.json from its own file inventory to avoid
    self-referential hashing, but still includes the manifest in the ZIP
  - skips unreadable placeholder files with a warning so certified runtime
    packaging can continue when historical cloud-only artifacts are present

Usage:
  # From MOLE_code folder:
  python mole_packager.py --root .. --out MOLE_DAS_runtime.zip

  # Strict mode (verify asset hashes):
  python mole_packager.py --root .. --out MOLE_DAS_runtime.zip --strict-hash
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from mole_preflight import run_preflight, format_preflight_report


SKIP_DIR_NAMES = {
    "RELEASES",
    ".git",
    ".github",
    ".vs",
    "scripts",
    "__pycache__",
}
SKIP_FILE_NAMES = {
    ".gitattributes",
    ".gitignore",
    "BUILD_WHEELHOUSE.bat",
    "RUN_CLEAN_RELEASE_WORKFLOW.bat",
    "desktop.ini",
    "Thumbs.db",
}


def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _should_skip_file(root: Path, path: Path, *, include_manifest: bool) -> bool:
    rel_parts = path.relative_to(root).parts
    if any(part in SKIP_DIR_NAMES or part.startswith(".venv_stale") for part in rel_parts):
        return True
    if "mole_das_data" in rel_parts and "logs" in rel_parts:
        return True
    name = path.name
    if name in SKIP_FILE_NAMES:
        return True
    if name.startswith("~$") or name.startswith("~$$"):
        return True
    if name.endswith(".sqlite-shm") or name.endswith(".sqlite-wal"):
        return True
    if path.suffix.lower() in {".pyc", ".pyo"}:
        return True
    if (not include_manifest) and name == "BUILD_MANIFEST.json":
        return True
    return False


def _iter_files(root: Path, *, include_manifest: bool) -> List[Path]:
    files: List[Path] = []
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if _should_skip_file(root, p, include_manifest=include_manifest):
            continue
        files.append(p)
    return sorted(files, key=lambda x: str(x.relative_to(root)).lower())


def _split_readable_files(root: Path, files: List[Path]) -> Tuple[List[Path], List[Tuple[Path, str]]]:
    readable: List[Path] = []
    unreadable: List[Tuple[Path, str]] = []
    for p in files:
        try:
            with p.open("rb") as f:
                f.read(1)
            readable.append(p)
        except OSError as e:
            unreadable.append((p, f"{type(e).__name__}: {e}"))
    return readable, unreadable


def _build_manifest(root: Path, files: List[Path]) -> Dict[str, object]:
    items: List[Dict[str, object]] = []
    for p in files:
        rel = str(p.relative_to(root)).replace(os.sep, "/")
        items.append({
            "path": rel,
            "bytes": p.stat().st_size,
            "sha256": _sha256_file(p),
        })
    return {
        "schema": "mole_build_manifest_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(items),
        "files": items,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Root folder containing mole_assets + mole_das_data + mole_config.json (typically _fixpkg).")
    ap.add_argument("--out", required=True, help="Output zip file path.")
    ap.add_argument("--strict-hash", action="store_true", help="Verify asset hashes from ASSET_MANIFEST.json before packaging.")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    code_dir = root / "MOLE_code"

    pf = run_preflight(app="packager", code_dir=code_dir, strict_hash=bool(args.strict_hash))
    print(format_preflight_report(pf))
    if pf.get("errors"):
        print("\nPackaging aborted due to preflight errors.")
        return 3

    files_for_manifest, unreadable = _split_readable_files(
        root,
        _iter_files(root, include_manifest=False),
    )
    if unreadable:
        print("\nWARNING: skipping unreadable files during packaging:")
        for p, err in unreadable[:50]:
            rel = str(p.relative_to(root)).replace(os.sep, "/")
            print(f"  - {rel} ({err})")
    manifest = _build_manifest(root, files_for_manifest)

    # Write manifest into root (included in zip)
    manifest_path = root / "BUILD_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    # deterministic zip: fixed timestamp for entries
    fixed_date_time = (2026, 2, 1, 0, 0, 0)
    files_for_zip = sorted(files_for_manifest + [manifest_path], key=lambda x: str(x.relative_to(root)).lower())

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files_for_zip:
            rel = str(p.relative_to(root)).replace(os.sep, "/")
            zi = zipfile.ZipInfo(rel, date_time=fixed_date_time)
            zi.compress_type = zipfile.ZIP_DEFLATED
            # Preserve executable bit for .bat on unix-like systems (harmless on Windows)
            if p.suffix.lower() == ".bat":
                zi.external_attr = 0o775 << 16
            with p.open("rb") as f:
                z.writestr(zi, f.read())

    print(f"\nOK: wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
