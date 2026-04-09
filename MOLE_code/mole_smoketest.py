"""MOLE Smoke Test (v10.0.24C)

Runs fast, deterministic checks intended to catch packaging regressions:
  - syntax errors (py_compile)
  - missing assets referenced by ASSET_MANIFEST.json
  - basic preflight health

Usage:
  python mole_smoketest.py --root ../  (when executed from MOLE_code)
  python mole_smoketest.py --strict-hash

Exit codes:
  0 = pass
  2 = warnings only
  3 = failures
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import py_compile
from pathlib import Path
from typing import List

from mole_preflight import run_preflight, format_preflight_report
from mole_postcal_policy_regression import run_regression as run_postcal_policy_regression, format_regression_report


def _walk_py_files(code_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in code_dir.rglob("*.py"):
        if any(part == "__pycache__" or part == ".venv" or part.startswith(".venv_stale") for part in p.parts):
            continue
        files.append(p)
    return sorted(files, key=lambda x: str(x).lower())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="Root folder containing mole_assets + mole_das_data + mole_config.json (default: auto from script location).")
    ap.add_argument("--strict-hash", action="store_true", help="Verify sha256 hashes for assets (slower).")
    ap.add_argument("--no-compile", action="store_true", help="Skip py_compile step.")
    ap.add_argument("--no-policy-regression", action="store_true", help="Skip post-cal carry-forward regression checks.")
    args = ap.parse_args()

    code_dir = Path(__file__).resolve().parent
    root = Path(args.root).resolve() if args.root else code_dir.parent

    # 1) preflight
    pf = run_preflight(app="smoketest", code_dir=code_dir, strict_hash=bool(args.strict_hash))
    print(format_preflight_report(pf))
    if pf.get("errors"):
        return 3

    # 2) py_compile
    if not args.no_compile:
        failures: List[str] = []
        for f in _walk_py_files(code_dir):
            try:
                py_compile.compile(str(f), doraise=True)
            except Exception as e:
                failures.append(f"{f.name}: {type(e).__name__}: {e}")
        if failures:
            print("\nCOMPILE FAILURES:")
            for x in failures:
                print("  -", x)
            return 3

    if not args.no_policy_regression:
        regression = run_postcal_policy_regression(root=root)
        print("\n" + format_regression_report(regression))
        if not bool(regression.get("ok")):
            return 3

    # warnings?
    if pf.get("warnings"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
