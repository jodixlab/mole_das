"""mole_session_package_2026_01_19_v10_0_10_ARCADE_RELEASE.py

CLI utility used by the Wizard to:
- export a session folder to a ZIP package
- ingest a ZIP package into the local sessions root (conflict-safe)

Wizard calls:
  python <this> export --session <dir> --out <zip>
  python <this> ingest --package <zip> --sessions-root <root> --on-conflict new --verify

Output convention (for Wizard parsing):
  print('dest: <path>') on successful ingest.

This is intentionally dependency-free (stdlib only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _zip_dir(src_dir: Path, out_zip: Path) -> None:
    src_dir = src_dir.resolve()
    out_zip = out_zip.resolve()
    _safe_mkdir(out_zip.parent)

    with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in src_dir.rglob('*'):
            if path.is_dir():
                continue
            rel = path.relative_to(src_dir)
            zf.write(path, arcname=str(rel).replace('\\','/'))

def _read_zip_json(zf: zipfile.ZipFile, names) -> Optional[Dict[str, Any]]:
    for n in names:
        try:
            with zf.open(n) as fp:
                return json.loads(fp.read().decode('utf-8', errors='ignore'))
        except KeyError:
            continue
        except Exception:
            continue
    return None

def _choose_dest_from_zip(zf: zipfile.ZipFile, sessions_root: Path) -> Tuple[str, str]:
    """Return (day, session_id) best-effort."""
    day = ''
    session_id = ''

    cfg = _read_zip_json(zf, [
        'session_profile.json',
        'das_session_config.json',
        'mole_das_configs/das_session_config.json',
        'metadata.json',
        'session_metadata.json',
    ]) or {}

    # attempt common structures
    session_id = str(cfg.get('session_id') or (cfg.get('metadata') or {}).get('session_id') or '').strip()
    day = str(cfg.get('day') or cfg.get('date') or (cfg.get('metadata') or {}).get('day') or '').strip()

    if not day:
        # try parse from filenames inside zip
        for n in zf.namelist():
            if '20' in n:
                import re
                m = re.search(r'(20\d{2}-\d{2}-\d{2})', n)
                if m:
                    day = m.group(1)
                    break

    if not session_id:
        # fall back to hash of zip central dir entries
        session_id = hashlib.sha1(('|'.join(sorted(zf.namelist()))).encode('utf-8', errors='ignore')).hexdigest()[:16]

    if not day:
        day = time.strftime('%Y-%m-%d')

    return day, session_id

def export_session(session_dir: Path, out_zip: Path) -> None:
    if not session_dir.exists() or not session_dir.is_dir():
        raise SystemExit(f"Session dir not found: {session_dir}")
    _zip_dir(session_dir, out_zip)
    print(f"ok: wrote {out_zip}")
    try:
        print(f"sha256: {_sha256_file(out_zip)}")
    except Exception:
        pass

def ingest_package(package_zip: Path, sessions_root: Path, on_conflict: str = 'new', verify: bool = False) -> Path:
    package_zip = package_zip.resolve()
    sessions_root = sessions_root.resolve()
    if not package_zip.exists():
        raise SystemExit(f"Package not found: {package_zip}")
    _safe_mkdir(sessions_root)

    with zipfile.ZipFile(package_zip, 'r') as zf:
        day, session_id = _choose_dest_from_zip(zf, sessions_root)
        dest_base = sessions_root / day / session_id
        dest = dest_base

        if dest.exists():
            if on_conflict.lower() == 'overwrite':
                shutil.rmtree(dest)
            elif on_conflict.lower() == 'skip':
                return dest
            else:
                # new
                i = 1
                while dest.exists():
                    dest = sessions_root / day / f"{session_id}_{i}"
                    i += 1

        _safe_mkdir(dest)
        zf.extractall(dest)

    if verify:
        # light verify: ensure we can open at least one json/csv if present
        ok = True
        for p in dest.rglob('*'):
            if p.is_file() and p.suffix.lower() in ('.json', '.csv', '.txt', '.log'):
                try:
                    _ = p.read_bytes()[:64]
                except Exception:
                    ok = False
                    break
        if not ok:
            raise SystemExit('verify failed: unable to read extracted artifacts')

    return dest

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)

    ap_exp = sub.add_parser('export')
    ap_exp.add_argument('--session', required=True, help='Path to session folder')
    ap_exp.add_argument('--out', required=True, help='Output zip path')

    ap_ing = sub.add_parser('ingest')
    ap_ing.add_argument('--package', required=True, help='Path to zip package')
    ap_ing.add_argument('--sessions-root', required=True, help='Root sessions directory')
    ap_ing.add_argument('--on-conflict', default='new', choices=['new','overwrite','skip'])
    ap_ing.add_argument('--verify', action='store_true')

    args = ap.parse_args()

    if args.cmd == 'export':
        export_session(Path(args.session), Path(args.out))
        return

    if args.cmd == 'ingest':
        dest = ingest_package(Path(args.package), Path(args.sessions_root), on_conflict=args.on_conflict, verify=bool(args.verify))
        print(f"dest: {dest}")
        return

if __name__ == '__main__':
    main()
