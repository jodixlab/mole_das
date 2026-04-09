"""MOLE Release Gate (v10.0.25A)

One-command "CERTIFIED BUILD" generator.

What it does:
  1) Runs preflight + py_compile smoke checks
  2) Builds deterministic runtime ZIP (via mole_packager)
  3) Writes RELEASE_CERT.txt + RELEASE_CERT.json with hashes + environment info

Usage (from MOLE_code):
  python mole_release_gate.py
  python mole_release_gate.py --strict-hash

Exit codes:
  0 = pass
  2 = pass with warnings
  3 = fail
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import py_compile
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mole_preflight import run_preflight
from mole_postcal_policy_regression import run_regression as run_postcal_policy_regression


def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _walk_py_files(code_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in code_dir.rglob("*.py"):
        if any(part == "__pycache__" or part == ".venv" or part.startswith(".venv_stale") for part in p.parts):
            continue
        files.append(p)
    return sorted(files, key=lambda x: str(x).lower())


def _compile_all(code_dir: Path) -> Tuple[int, List[str]]:
    failures: List[str] = []
    count = 0
    for f in _walk_py_files(code_dir):
        count += 1
        try:
            py_compile.compile(str(f), doraise=True)
        except Exception as e:
            failures.append(f"{f.name}: {type(e).__name__}: {e}")
    return count, failures


def _now_build_id(prefix: str = "MOLE_DAS") -> str:
    # UTC build id (deterministic-ish)
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')}"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _format_cert_txt(cert: Dict[str, object]) -> str:
    lines: List[str] = []
    lines.append("MOLE-DAS RELEASE CERTIFICATE")
    lines.append("=" * 30)
    lines.append(f"Build ID: {cert.get('build_id')}")
    lines.append(f"Status:   {cert.get('status')}")
    lines.append(f"Created:  {cert.get('created_at_utc')}")
    lines.append("")

    env = cert.get("env") or {}
    lines.append("Environment")
    lines.append("-----------")
    lines.append(f"OS:        {env.get('os')}")
    lines.append(f"Python:    {env.get('python')}")
    lines.append(f"Platform:  {env.get('platform')}")
    lines.append(f"CWD:       {env.get('cwd')}")
    lines.append("")

    checks = cert.get("checks") or {}
    lines.append("Checks")
    lines.append("------")
    lines.append(f"Preflight errors:    {checks.get('preflight_error_count')}")
    lines.append(f"Preflight warnings:  {checks.get('preflight_warning_count')}")
    lines.append(f"Strict asset hashes: {checks.get('strict_hash')}")
    lines.append(f"Python files compiled: {checks.get('py_compile_count')}")
    lines.append(f"Policy regression cases: {checks.get('policy_regression_case_count')}")
    lines.append(f"Policy regression failures: {checks.get('policy_regression_failure_count')}")
    if checks.get("py_compile_failures"):
        lines.append("Compile failures:")
        for x in checks.get("py_compile_failures") or []:
            lines.append(f"  - {x}")
    if checks.get("policy_regression_failures"):
        lines.append("Policy regression failures:")
        for x in checks.get("policy_regression_failures") or []:
            lines.append(f"  - {x}")
    lines.append("")

    out = cert.get("output") or {}
    lines.append("Artifact")
    lines.append("--------")
    lines.append(f"ZIP:      {out.get('zip_path')}")
    lines.append(f"Bytes:    {out.get('zip_bytes')}")
    lines.append(f"SHA256:   {out.get('zip_sha256')}")
    lines.append("")

    notes = cert.get("notes") or []
    if notes:
        lines.append("Notes")
        lines.append("-----")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        default=None,
        help="Root folder containing mole_assets + mole_das_data + mole_config.json (default: auto from script location).",
    )
    ap.add_argument(
        "--outdir",
        default=None,
        help="Output directory for certified builds (default: <root>/RELEASES).",
    )
    ap.add_argument(
        "--strict-hash",
        action="store_true",
        help="Verify sha256 hashes for locked assets (slower).",
    )
    ap.add_argument(
        "--label",
        default="v10.0.25A_PACKAGE_REFRESH_20260407",
        help="Label included in output zip name.",
    )
    ap.add_argument(
        "--no-policy-regression",
        action="store_true",
        help="Skip post-cal carry-forward regression checks.",
    )
    args = ap.parse_args()

    code_dir = Path(__file__).resolve().parent
    root = Path(args.root).resolve() if args.root else code_dir.parent
    outdir = Path(args.outdir).resolve() if args.outdir else (root / "RELEASES")
    outdir.mkdir(parents=True, exist_ok=True)

    build_id = _now_build_id(prefix="MOLE_DAS")
    created_at = datetime.now(timezone.utc).isoformat()

    # 1) preflight
    pf = run_preflight(app="release_gate", code_dir=code_dir, strict_hash=bool(args.strict_hash))
    pf_errors = pf.get("errors") or []
    pf_warnings = pf.get("warnings") or []

    # 2) compile
    py_count, py_failures = _compile_all(code_dir)

    # 3) post-cal policy regression
    regression_report = {"ok": True, "case_count": 0, "failure_count": 0, "cases": []}
    if not args.no_policy_regression:
        regression_report = run_postcal_policy_regression(root=root)

    # 4) decide status
    status = "PASS"
    exit_code = 0
    notes: List[str] = []
    regression_failures = [case.get("name") for case in list(regression_report.get("cases") or []) if not bool(case.get("passed"))]
    if pf_errors or py_failures or regression_failures:
        status = "FAIL"
        exit_code = 3
    elif pf_warnings:
        status = "PASS_WITH_WARNINGS"
        exit_code = 2

    # 5) package if not fail
    zip_path: Optional[Path] = None
    zip_sha: Optional[str] = None
    zip_bytes: Optional[int] = None
    if status != "FAIL":
        label = str(args.label).strip().replace(" ", "_")
        zip_path = outdir / f"{label}_{build_id}_RUNTIME_READY_FULL_DATA.zip"

        import mole_packager  # local

        argv_bak = sys.argv[:]
        try:
            sys.argv = [
                "mole_packager.py",
                "--root",
                str(root),
                "--out",
                str(zip_path),
            ]
            if args.strict_hash:
                sys.argv.append("--strict-hash")
            rc = mole_packager.main()
            if rc != 0:
                status = "FAIL"
                exit_code = 3
                notes.append("Packaging failed (mole_packager returned non-zero).")
            else:
                zip_bytes = zip_path.stat().st_size
                zip_sha = _sha256_file(zip_path)
        finally:
            sys.argv = argv_bak

    cert: Dict[str, object] = {
        "schema": "mole_release_cert_v1",
        "build_id": build_id,
        "status": status,
        "created_at_utc": created_at,
        "env": {
            "os": platform.platform(),
            "python": sys.version.replace("\n", " "),
            "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "cwd": str(Path.cwd()),
        },
        "checks": {
            "strict_hash": bool(args.strict_hash),
            "preflight_error_count": len(pf_errors),
            "preflight_warning_count": len(pf_warnings),
            "preflight_errors": pf_errors[:50],
            "preflight_warnings": pf_warnings[:50],
            "py_compile_count": py_count,
            "py_compile_failures": py_failures[:50],
            "policy_regression_case_count": int(regression_report.get("case_count") or 0),
            "policy_regression_failure_count": int(regression_report.get("failure_count") or 0),
            "policy_regression_failures": regression_failures[:50],
        },
        "output": {
            "zip_path": str(zip_path) if zip_path else None,
            "zip_bytes": zip_bytes,
            "zip_sha256": zip_sha,
        },
        "notes": notes,
    }

    cert_txt = _format_cert_txt(cert)
    cert_txt_path = outdir / f"RELEASE_CERT_{build_id}.txt"
    cert_json_path = outdir / f"RELEASE_CERT_{build_id}.json"
    _write_text(cert_txt_path, cert_txt)
    cert_json_path.write_text(json.dumps(cert, indent=2), encoding="utf-8")

    print(cert_txt)
    if zip_path:
        print(f"\nOK: certified artifact at {zip_path}")
    print(f"OK: certificate at {cert_txt_path}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
