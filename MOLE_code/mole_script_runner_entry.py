from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(
        description="MOLE script helper for frozen executable bundles."
    )
    ap.add_argument("script", help="Absolute or bundle-relative path to the Python script to run.")
    ap.add_argument("script_args", nargs=argparse.REMAINDER, help="Arguments passed to the target script.")
    ns = ap.parse_args()

    script_path = Path(ns.script)
    if not script_path.is_absolute():
        script_path = (Path(sys.executable).resolve().parent / script_path).resolve()
    if not script_path.exists():
        raise SystemExit(f"Script not found: {script_path}")

    sys.path.insert(0, str(script_path.parent))
    sys.argv = [str(script_path)] + list(ns.script_args or [])
    runpy.run_path(str(script_path), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
