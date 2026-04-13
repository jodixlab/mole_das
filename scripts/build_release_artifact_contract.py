from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _run_python(python_exe: Path, args: List[str]) -> str:
    completed = subprocess.run(
        [str(python_exe), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _find_artifact(output_dir: Path, spec: Dict[str, Any]) -> Dict[str, Any]:
    pattern = str(spec.get("pattern") or "")
    match_mode = str(spec.get("match") or "exact").strip().lower()
    matches: List[Path]
    if match_mode == "glob":
        matches = sorted(output_dir.glob(pattern), key=lambda p: p.name.lower())
    else:
        candidate = output_dir / pattern
        matches = [candidate] if candidate.exists() else []
    selected = matches[0] if matches else None
    return {
        "id": spec.get("id"),
        "required": bool(spec.get("required")),
        "description": spec.get("description"),
        "match": match_mode,
        "pattern": pattern,
        "status": "PRESENT" if selected else "MISSING",
        "path": selected.name if selected else "",
        "bytes": selected.stat().st_size if selected else None,
        "match_count": len(matches),
    }


def _build_dependency_manifest(python_exe: Path) -> Dict[str, Any]:
    version = _run_python(python_exe, ["--version"]).strip()
    pip_freeze = _run_python(python_exe, ["-m", "pip", "freeze", "--all"])
    pip_list = _run_python(python_exe, ["-m", "pip", "list", "--format", "json"])
    packages = json.loads(pip_list)
    packages = sorted(packages, key=lambda item: (str(item.get("name") or "").lower(), str(item.get("version") or "")))
    return {
        "schema": "mole_dependency_manifest_v1",
        "python_exe": str(python_exe),
        "python_version": version,
        "package_count": len(packages),
        "packages": packages,
        "freeze_lines": [line for line in pip_freeze.splitlines() if line.strip()],
    }


def _artifact_status_map(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(item.get("id") or ""): item for item in items}


def _build_bundle_summary(
    summary: Dict[str, Any],
    cert: Dict[str, Any],
    hygiene: Dict[str, Any],
    dependencies: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
    ignore_missing_ids: List[str] | None = None,
) -> Dict[str, Any]:
    artifact_map = _artifact_status_map(artifacts)
    ignore_missing = set(ignore_missing_ids or [])
    missing_required = [
        item["id"]
        for item in artifacts
        if item.get("required")
        and item.get("status") != "PRESENT"
        and str(item.get("id") or "") not in ignore_missing
    ]
    overall_status = "PASS"
    if (
        str(summary.get("status") or "").upper() != "PASS"
        or str(cert.get("status") or "").upper() != "PASS"
        or str(hygiene.get("status") or "").upper() != "PASS"
        or missing_required
    ):
        overall_status = "FAIL"
    return {
        "schema": "mole_release_bundle_summary_v1",
        "overall_status": overall_status,
        "workflow_status": summary.get("status") or "UNKNOWN",
        "release_cert_status": cert.get("status") or "UNKNOWN",
        "package_hygiene_status": hygiene.get("status") or "UNKNOWN",
        "required_artifact_count": len([item for item in artifacts if item.get("required")]),
        "missing_required_artifacts": missing_required,
        "build_id": cert.get("build_id"),
        "zip_path": artifact_map.get("runtime_zip", {}).get("path"),
        "zip_sha256": ((cert.get("output") or {}).get("zip_sha256")),
        "zip_bytes": ((cert.get("output") or {}).get("zip_bytes")),
        "dependency_package_count": dependencies.get("package_count"),
    }


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _contract_md(
    contract: Dict[str, Any],
    bundle_summary: Dict[str, Any],
    dependencies: Dict[str, Any],
) -> str:
    lines = [
        "# MOLE-DAS Release Artifact Contract",
        "",
        f"- Status: `{bundle_summary.get('overall_status')}`",
        f"- Build ID: `{bundle_summary.get('build_id') or ''}`",
        f"- Workflow status: `{bundle_summary.get('workflow_status')}`",
        f"- Release certificate: `{bundle_summary.get('release_cert_status')}`",
        f"- Package hygiene: `{bundle_summary.get('package_hygiene_status')}`",
        f"- Dependency packages: `{dependencies.get('package_count')}`",
        "",
        "| ID | Required | Status | Path | Description |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in contract.get("artifacts") or []:
        lines.append(
            f"| {item.get('id','')} | {'YES' if item.get('required') else 'NO'} | {item.get('status','')} | "
            f"{item.get('path','')} | {str(item.get('description','')).replace('|', '/')} |"
        )
    return "\n".join(lines) + "\n"


def _bundle_summary_md(bundle_summary: Dict[str, Any], dependencies: Dict[str, Any]) -> str:
    lines = [
        "# MOLE-DAS Release Bundle Summary",
        "",
        f"- Overall status: `{bundle_summary.get('overall_status')}`",
        f"- Build ID: `{bundle_summary.get('build_id') or ''}`",
        f"- Workflow status: `{bundle_summary.get('workflow_status')}`",
        f"- Release cert status: `{bundle_summary.get('release_cert_status')}`",
        f"- Package hygiene status: `{bundle_summary.get('package_hygiene_status')}`",
        f"- Runtime ZIP: `{bundle_summary.get('zip_path') or ''}`",
        f"- Runtime ZIP bytes: `{bundle_summary.get('zip_bytes') or ''}`",
        f"- Runtime ZIP SHA256: `{bundle_summary.get('zip_sha256') or ''}`",
        f"- Dependency package count: `{dependencies.get('package_count')}`",
        "",
    ]
    missing = bundle_summary.get("missing_required_artifacts") or []
    if missing:
        lines.append("## Missing required artifacts")
        for item in missing:
            lines.append(f"- `{item}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build MOLE-DAS release artifact contract outputs.")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--summary-json", required=True)
    ap.add_argument("--python-exe", required=True)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    summary = _read_json(Path(args.summary_json).resolve())
    python_exe = Path(args.python_exe).resolve()

    contract_source = _read_json(repo_root / "config" / "mole_release_artifact_contract_v1.json")
    dependencies = _build_dependency_manifest(python_exe)

    output_dir.mkdir(parents=True, exist_ok=True)
    dependency_txt = output_dir / "dependency_manifest.txt"
    dependency_json = output_dir / "dependency_manifest.json"
    _write_text(dependency_txt, "\n".join(dependencies.get("freeze_lines") or []) + "\n")
    _write_json(dependency_json, dependencies)

    def resolve_artifacts() -> List[Dict[str, Any]]:
        return [_find_artifact(output_dir, spec) for spec in list(contract_source.get("artifacts") or [])]

    artifacts = resolve_artifacts()

    cert_path = next((output_dir / item["path"] for item in artifacts if item.get("id") == "release_cert_json" and item.get("path")), None)
    hygiene_path = next((output_dir / item["path"] for item in artifacts if item.get("id") == "release_hygiene_json" and item.get("path")), None)
    cert = _read_json(cert_path) if cert_path and cert_path.exists() else {}
    hygiene = _read_json(hygiene_path) if hygiene_path and hygiene_path.exists() else {}

    bundle_summary = _build_bundle_summary(
        summary,
        cert,
        hygiene,
        dependencies,
        artifacts,
        ignore_missing_ids=[
            "release_bundle_summary_json",
            "release_bundle_summary_md",
            "release_artifact_contract_json",
            "release_artifact_contract_md",
        ],
    )
    contract = {
        "schema": "mole_release_artifact_contract_v1",
        "source_schema": contract_source.get("schema"),
        "build_id": bundle_summary.get("build_id"),
        "status": bundle_summary.get("overall_status"),
        "artifacts": artifacts,
    }

    _write_json(output_dir / "release_bundle_summary.json", bundle_summary)
    _write_text(output_dir / "release_bundle_summary.md", _bundle_summary_md(bundle_summary, dependencies))
    _write_json(output_dir / "release_artifact_contract.json", contract)
    _write_text(output_dir / "release_artifact_contract.md", _contract_md(contract, bundle_summary, dependencies))

    artifacts = resolve_artifacts()
    bundle_summary = _build_bundle_summary(summary, cert, hygiene, dependencies, artifacts)
    contract = {
        "schema": "mole_release_artifact_contract_v1",
        "source_schema": contract_source.get("schema"),
        "build_id": bundle_summary.get("build_id"),
        "status": bundle_summary.get("overall_status"),
        "artifacts": artifacts,
    }
    _write_json(output_dir / "release_bundle_summary.json", bundle_summary)
    _write_text(output_dir / "release_bundle_summary.md", _bundle_summary_md(bundle_summary, dependencies))
    _write_json(output_dir / "release_artifact_contract.json", contract)
    _write_text(output_dir / "release_artifact_contract.md", _contract_md(contract, bundle_summary, dependencies))

    return 0 if bundle_summary.get("overall_status") == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
