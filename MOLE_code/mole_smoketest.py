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
import re
import shutil
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


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _slug_text(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return text or "session"


def _seed_integration_session(root: Path) -> Optional[Path]:
    config_dir = root / "mole_das_data" / "configs"
    candidates: List[Path] = []
    preferred = config_dir / "mole_session_2026_03_31_1209.json"
    if preferred.exists():
        candidates.append(preferred)
    candidates.extend(sorted(config_dir.glob("mole_session_*.json"), key=lambda p: str(p).lower()))

    seen: set[str] = set()
    ordered: List[Path] = []
    for path in candidates:
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)

    session_cfg_path = next((path for path in ordered if path.exists()), None)
    if session_cfg_path is None:
        return None

    try:
        session = json.loads(session_cfg_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    if not isinstance(session, dict):
        return None

    meta = session.get("meta") if isinstance(session.get("meta"), dict) else {}
    project = session.get("project") if isinstance(session.get("project"), dict) else {}
    source = session.get("source") if isinstance(session.get("source"), dict) else {}
    job_id = str(project.get("job_id") or session_cfg_path.stem).strip() or session_cfg_path.stem
    site_slug = _slug_text(project.get("site_facility") or "fixture_site")
    run_id = f"{job_id}__SMOKETEST"

    fixture_root = root / "mole_das_data" / "validation" / "_smoke"
    session_dir = fixture_root / run_id
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)
    (session_dir / "meta").mkdir(parents=True, exist_ok=True)
    (session_dir / "raw").mkdir(parents=True, exist_ok=True)
    (session_dir / "exports").mkdir(parents=True, exist_ok=True)

    session["run_id"] = run_id
    paths = session.get("paths") if isinstance(session.get("paths"), dict) else {}
    paths["session_dir"] = str(session_dir)
    paths["daq_run_dir"] = str(session_dir)
    paths["db_path"] = str((root / "mole_das_data" / "db" / "mole_master.sqlite").resolve())
    paths["logs_dir"] = str((root / "mole_das_data" / "logs").resolve())
    session["paths"] = paths

    meta = dict(meta)
    meta["seeded_for_smoketest"] = True
    meta["seed_source_config"] = str(session_cfg_path.name)
    session["meta"] = meta

    runner_config_path = session_dir / "runner_config.json"
    runner_config_path.write_text(json.dumps(session, indent=2), encoding="utf-8")

    created_iso = str(meta.get("applied_iso") or meta.get("created_iso") or "").strip()
    session_profile = {
        "session_id": run_id,
        "run_id": run_id,
        "created_at": created_iso,
        "site_id": job_id,
        "location_id": str(project.get("asset_unit_id") or "001").strip() or "001",
        "source_category": str(source.get("source_category") or "").strip(),
        "manufacturer": str(source.get("manufacturer") or "").strip(),
        "model_number": str(source.get("model_number") or "").strip(),
        "serial_number": str(source.get("serial_number") or "").strip(),
        "asset_tag": str(source.get("asset_tag") or "").strip(),
        "instance_id": source.get("instance_id"),
        "paths": {
            "runner_config_path": str(runner_config_path),
            "session_config_path": str(session_cfg_path.resolve()),
            "session_dir": str(session_dir),
            "daq_run_dir": str(session_dir),
            "db_path": str((root / "mole_das_data" / "db" / "mole_master.sqlite").resolve()),
            "logs_dir": str((root / "mole_das_data" / "logs").resolve()),
        },
    }
    (session_dir / "session_profile.json").write_text(json.dumps(session_profile, indent=2), encoding="utf-8")

    session_meta = {
        "schema": "mole_smoketest_session_meta_v1",
        "session_id": run_id,
        "seeded_from": str(session_cfg_path.resolve()),
        "seeded_at": _now_iso(),
    }
    (session_dir / "meta" / "session.json").write_text(json.dumps(session_meta, indent=2), encoding="utf-8")
    return session_dir


def _find_integration_session(root: Path, explicit: Optional[Path] = None) -> Optional[Path]:
    if explicit is not None:
        candidate = Path(explicit).expanduser().resolve()
        if (candidate / "runner_config.json").exists():
            return candidate
        return None

    candidates: List[Path] = []
    for base in (root / "mole_das_data" / "sessions", root / "mole_das_data" / "training" / "sessions"):
        if not base.exists():
            continue
        for cfg in base.rglob("runner_config.json"):
            candidates.append(cfg.parent)
    if not candidates:
        seeded = _seed_integration_session(root)
        if seeded is not None and (seeded / "runner_config.json").exists():
            return seeded
        return None
    return sorted(candidates, key=lambda p: str(p).lower())[0]


def _run_launcher_report_pack_integration(root: Path, code_dir: Path, integration_session_dir: Optional[Path] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False,
        "session_dir": "",
        "session_source": "",
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

    session_dir = _find_integration_session(root, explicit=integration_session_dir)
    if session_dir is None:
        out["error"] = "no session fixture with runner_config.json found under mole_das_data"
        return out
    try:
        validation_fixture_root = (root / "mole_das_data" / "validation" / "_smoke").resolve()
        out["session_source"] = "SEEDED_FIXTURE" if session_dir.resolve().is_relative_to(validation_fixture_root) else "SESSION_TREE"
    except Exception:
        out["session_source"] = "SESSION_TREE"

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
    if result.get("session_source"):
        lines.append(f"  session_source: {result.get('session_source')}")
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
    ap.add_argument("--integration-session-dir", default=None, help="Optional explicit session directory for the integration smoke path.")
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
        integration_dir = Path(str(args.integration_session_dir)).expanduser().resolve() if args.integration_session_dir else None
        integration = _run_launcher_report_pack_integration(root=root, code_dir=code_dir, integration_session_dir=integration_dir)
        print("\n" + _format_integration_report(integration))
        if not bool(integration.get("ok")):
            return 3

    # warnings?
    if pf.get("warnings"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
