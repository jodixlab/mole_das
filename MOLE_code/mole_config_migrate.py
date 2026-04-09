"""MOLE Config Migrator (v10.0.24C)

Adds schema_version fields and performs small compatibility normalizations
without changing operator-facing meaning.

Usage:
  python mole_config_migrate.py --in ../mole_config.json --out ../mole_config.json

Tip:
  Run with --dry-run to print planned changes.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, cfg: Dict[str, Any]) -> None:
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def migrate(cfg: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    changes: Dict[str, Any] = {}
    if not cfg.get("schema_version"):
        cfg["schema_version"] = "mole_config_v1"
        changes["schema_version"] = cfg["schema_version"]
    if not cfg.get("schema_version_int"):
        cfg["schema_version_int"] = 1
        changes["schema_version_int"] = cfg["schema_version_int"]

    # release block normalization
    rel = cfg.get("release") or {}
    if isinstance(rel, dict):
        if "built_utc" not in rel:
            rel["built_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            changes["release.built_utc"] = rel["built_utc"]
        cfg["release"] = rel

    return cfg, changes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input mole_config.json")
    ap.add_argument("--out", dest="outp", required=True, help="Output path (may be same as input)")
    ap.add_argument("--dry-run", action="store_true", help="Print changes only; do not write.")
    args = ap.parse_args()

    inp = Path(args.inp).resolve()
    outp = Path(args.outp).resolve()

    cfg = _load(inp)
    new_cfg, changes = migrate(cfg)

    if not changes:
        print("No migration changes required.")
        return 0

    print("Planned changes:")
    for k, v in changes.items():
        print(f"  - {k} = {v}")

    if args.dry_run:
        return 0

    _save(outp, new_cfg)
    print(f"OK: wrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
