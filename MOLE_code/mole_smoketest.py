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
import subprocess
import sys
import py_compile
from pathlib import Path
from typing import Any, Dict, List, Optional

from mole_preflight import run_preflight, format_preflight_report
from mole_postcal_policy_regression import run_regression as run_postcal_policy_regression, format_regression_report


def _walk_py_files(code_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in code_dir.rglob("*.py"):
        if any(part == "__pycache__" or part == ".venv" or part.startswith(".venv_stale") for part in p.parts):
            continue
        files.append(p)
    return sorted(files, key=lambda x: str(x).lower())


def _find_integration_session(root: Path) -> Optional[Path]:
    candidates: List[Path] = []
    for base in (root / "mole_das_data" / "sessions", root / "mole_das_data" / "training" / "sessions"):
        if not base.exists():
            continue
        for cfg in base.rglob("runner_config.json"):
            candidates.append(cfg.parent)
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: str(p).lower())[0]


def _run_launcher_report_pack_integration(root: Path, code_dir: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False,
        "session_dir": "",
        "summary_path": "",
        "bootstrap_stdout": "",
        "bootstrap_stderr": "",
        "report_stdout": "",
        "report_stderr": "",
        "error": "",
    }

    helper_cmd = 'call _resolve_mole_python.bat --nopause && .venv\\Scripts\\python.exe -V'
    boot = subprocess.run(
        ["cmd.exe", "/c", helper_cmd],
        capture_output=True,
        text=True,
        cwd=str(code_dir),
    )
    out["bootstrap_stdout"] = boot.stdout or ""
    out["bootstrap_stderr"] = boot.stderr or ""
    if int(boot.returncode) != 0:
        out["error"] = f"launcher bootstrap failed with exit code {boot.returncode}"
        return out

    session_dir = _find_integration_session(root)
    if session_dir is None:
        out["error"] = "no session fixture with runner_config.json found under mole_das_data"
        return out

    py = code_dir / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        out["error"] = f"resolved runtime missing: {py}"
        return out

    report = subprocess.run(
        [str(py), str(code_dir / "mole_report_pack_v1.py"), "--session-dir", str(session_dir)],
        capture_output=True,
        text=True,
    )
    out["session_dir"] = str(session_dir)
    out["report_stdout"] = report.stdout or ""
    out["report_stderr"] = report.stderr or ""
    if int(report.returncode) != 0:
        out["error"] = f"report pack export failed with exit code {report.returncode}"
        return out

    summary_path = session_dir / "exports" / "report_pack_v1" / "summary.json"
    out["summary_path"] = str(summary_path)
    if not summary_path.exists():
        out["error"] = f"expected report pack summary not found: {summary_path}"
        return out

    out["ok"] = True
    return out


def _format_integration_report(result: Dict[str, Any]) -> str:
    lines = ["INTEGRATION: launcher + report pack"]
    lines.append(f"  ok: {'YES' if bool(result.get('ok')) else 'NO'}")
    if result.get("session_dir"):
        lines.append(f"  session: {result.get('session_dir')}")
    if result.get("summary_path"):
        lines.append(f"  summary: {result.get('summary_path')}")
    if result.get("error"):
        lines.append(f"  error: {result.get('error')}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="Root folder containing mole_assets + mole_das_data + mole_config.json (default: auto from script location).")
    ap.add_argument("--strict-hash", action="store_true", help="Verify sha256 hashes for assets (slower).")
    ap.add_argument("--no-compile", action="store_true", help="Skip py_compile step.")
    ap.add_argument("--no-policy-regression", action="store_true", help="Skip post-cal carry-forward regression checks.")
    ap.add_argument("--integration-launcher-report-pack", action="store_true", help="Run launcher bootstrap + report-pack export integration smoke path.")
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

    if args.integration_launcher_report_pack:
        integration = _run_launcher_report_pack_integration(root=root, code_dir=code_dir)
        print("\n" + _format_integration_report(integration))
        if not bool(integration.get("ok")):
            return 3

    # warnings?
    if pf.get("warnings"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
