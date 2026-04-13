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
        "final_report_path": "",
        "final_report_index_path": "",
        "ftir_appendix_cover_path": "",
        "ftir_appendix_ledger_path": "",
        "ftir_appendix_method301_path": "",
        "ftir_appendix_exclusions_path": "",
        "ftir_appendix_delta_trace_json_path": "",
        "ftir_appendix_delta_trace_csv_path": "",
        "ftir_appendix_index_path": "",
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

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as e:
        out["error"] = f"failed to load report pack summary: {type(e).__name__}: {e}"
        return out

    final_report = summary.get("final_report") if isinstance(summary, dict) else {}
    if not isinstance(final_report, dict):
        out["error"] = "summary.json missing final_report block"
        return out

    md_path_raw = final_report.get("markdown_path")
    idx_path_raw = final_report.get("index_path")
    if not md_path_raw or not idx_path_raw:
        out["error"] = "summary.json final_report block missing markdown_path or index_path"
        return out

    final_report_path = Path(str(md_path_raw))
    final_report_index_path = Path(str(idx_path_raw))
    out["final_report_path"] = str(final_report_path)
    out["final_report_index_path"] = str(final_report_index_path)

    if not final_report_path.exists():
        out["error"] = f"expected final report not found: {final_report_path}"
        return out
    if not final_report_index_path.exists():
        out["error"] = f"expected final report index not found: {final_report_index_path}"
        return out

    try:
        final_index = json.loads(final_report_index_path.read_text(encoding="utf-8"))
    except Exception as e:
        out["error"] = f"failed to load final report index: {type(e).__name__}: {e}"
        return out

    file_names = {str(item.get('name') or '') for item in (final_index.get("files") or []) if isinstance(item, dict)}
    if "final_test_report_v1.md" not in file_names:
        out["error"] = "final report index does not include final_test_report_v1.md"
        return out

    ftir_validation = summary.get("ftir_validation") if isinstance(summary, dict) else {}
    if not isinstance(ftir_validation, dict):
        out["error"] = "summary.json missing ftir_validation block"
        return out
    appendix = ftir_validation.get("appendix")
    if not isinstance(appendix, dict):
        out["error"] = "summary.json ftir_validation block missing appendix"
        return out

    appendix_keys = {
        "cover_md": "ftir_appendix_cover_path",
        "ledger_csv": "ftir_appendix_ledger_path",
        "method301_csv": "ftir_appendix_method301_path",
        "exclusions_csv": "ftir_appendix_exclusions_path",
        "delta_trace_json": "ftir_appendix_delta_trace_json_path",
        "delta_trace_csv": "ftir_appendix_delta_trace_csv_path",
        "workbook_xlsx": "ftir_appendix_workbook_path",
        "index_json": "ftir_appendix_index_path",
    }
    appendix_paths: Dict[str, Path] = {}
    for src_key, out_key in appendix_keys.items():
        raw = appendix.get(src_key)
        if not raw:
            out["error"] = f"summary.json ftir_validation appendix missing {src_key}"
            return out
        path = Path(str(raw))
        appendix_paths[src_key] = path
        out[out_key] = str(path)
        if not path.exists():
            out["error"] = f"expected FTIR appendix artifact not found: {path}"
            return out

    try:
        appendix_index = json.loads(appendix_paths["index_json"].read_text(encoding="utf-8"))
    except Exception as e:
        out["error"] = f"failed to load FTIR appendix index: {type(e).__name__}: {e}"
        return out

    appendix_file_names = {
        str(item.get("name") or "")
        for item in (appendix_index.get("files") or [])
        if isinstance(item, dict)
    }
    for expected_name in {
        "ftir_validation_signoff_cover_v1.md",
        "ftir_validation_signed_comparison_ledger.csv",
        "ftir_validation_signed_method301_stats.csv",
        "ftir_validation_signed_exclusion_register.csv",
        "ftir_validation_delta_trace_v1.json",
        "ftir_validation_delta_trace_v1.csv",
        "ftir_validation_reviewer_workbook_v1.xlsx",
    }:
        if expected_name not in appendix_file_names:
            out["error"] = f"FTIR appendix index does not include {expected_name}"
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
    if result.get("final_report_path"):
        lines.append(f"  final_report: {result.get('final_report_path')}")
    if result.get("final_report_index_path"):
        lines.append(f"  final_report_index: {result.get('final_report_index_path')}")
    if result.get("ftir_appendix_cover_path"):
        lines.append(f"  ftir_appendix_cover: {result.get('ftir_appendix_cover_path')}")
    if result.get("ftir_appendix_ledger_path"):
        lines.append(f"  ftir_appendix_ledger: {result.get('ftir_appendix_ledger_path')}")
    if result.get("ftir_appendix_method301_path"):
        lines.append(f"  ftir_appendix_method301: {result.get('ftir_appendix_method301_path')}")
    if result.get("ftir_appendix_exclusions_path"):
        lines.append(f"  ftir_appendix_exclusions: {result.get('ftir_appendix_exclusions_path')}")
    if result.get("ftir_appendix_delta_trace_json_path"):
        lines.append(f"  ftir_appendix_delta_trace_json: {result.get('ftir_appendix_delta_trace_json_path')}")
    if result.get("ftir_appendix_delta_trace_csv_path"):
        lines.append(f"  ftir_appendix_delta_trace_csv: {result.get('ftir_appendix_delta_trace_csv_path')}")
    if result.get("ftir_appendix_workbook_path"):
        lines.append(f"  ftir_appendix_workbook: {result.get('ftir_appendix_workbook_path')}")
    if result.get("ftir_appendix_index_path"):
        lines.append(f"  ftir_appendix_index: {result.get('ftir_appendix_index_path')}")
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
