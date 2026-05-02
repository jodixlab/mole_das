from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _missing_artifacts_report(artifact_dir: Path, missing: List[str], allow_pending_operator: bool) -> Dict[str, Any]:
    return {
        "schema": "mole_release_go_no_go_decision_v1",
        "status": "MISSING_ARTIFACTS",
        "overall_decision": "NO-GO",
        "allow_pending_operator": allow_pending_operator,
        "artifact_dir": str(artifact_dir),
        "clean_workflow_status": None,
        "bundle_status": None,
        "release_cert_status": None,
        "package_hygiene_status": None,
        "blocking_manual_pending": [],
        "blocking_manual_fail": [],
        "conditional_manual_fail": [],
        "final_release_decision": {},
        "missing_artifacts": missing,
        "findings": [
            "release decision artifacts are missing",
            "run RUN_CLEAN_RELEASE_WORKFLOW.bat before RUN_RELEASE_DECISION_GATE.bat",
        ],
    }


def _decision_upper(value: Any) -> str:
    return str(value or "").strip().upper()


def _evaluate(artifact_dir: Path, allow_pending_operator: bool) -> Dict[str, Any]:
    cert_paths = sorted(artifact_dir.glob("RELEASE_CERT_*.json"))
    hygiene_paths = sorted(artifact_dir.glob("RELEASE_HYGIENE_*.json"))
    required_paths = [
        artifact_dir / "clean_release_summary.json",
        artifact_dir / "release_bundle_summary.json",
        artifact_dir / "operator_go_no_go_checklist.json",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if not cert_paths:
        missing.append(str(artifact_dir / "RELEASE_CERT_*.json"))
    if not hygiene_paths:
        missing.append(str(artifact_dir / "RELEASE_HYGIENE_*.json"))
    if missing:
        return _missing_artifacts_report(artifact_dir, missing, allow_pending_operator)

    summary = _read_json(artifact_dir / "clean_release_summary.json")
    bundle = _read_json(artifact_dir / "release_bundle_summary.json")
    cert = _read_json(cert_paths[0])
    hygiene = _read_json(hygiene_paths[0])
    checklist = _read_json(artifact_dir / "operator_go_no_go_checklist.json")

    findings: List[str] = []
    blocking_manual_pending: List[str] = []
    blocking_manual_fail: List[str] = []
    conditional_manual_fail: List[str] = []

    if _decision_upper(summary.get("status")) != "PASS":
        findings.append("clean_release_summary.status is not PASS")
    if _decision_upper(bundle.get("overall_status")) != "PASS":
        findings.append("release_bundle_summary.overall_status is not PASS")
    if _decision_upper(cert.get("status")) != "PASS":
        findings.append("release certificate status is not PASS")
    if _decision_upper((hygiene.get("status"))) != "PASS":
        findings.append("package hygiene status is not PASS")

    for item in list(checklist.get("items") or []):
        gate = _decision_upper(item.get("gate"))
        decision = _decision_upper(item.get("decision"))
        item_id = str(item.get("id") or "")
        if gate == "BLOCKING":
            if decision in {"", "NONE", "NULL"}:
                blocking_manual_pending.append(item_id)
            elif decision in {"NO-GO", "FAIL", "REJECTED"}:
                blocking_manual_fail.append(item_id)
        elif gate == "CONDITIONAL":
            if decision in {"NO-GO", "FAIL", "REJECTED"}:
                conditional_manual_fail.append(item_id)

    final_decision = checklist.get("final_decision") or {}
    final_decision_value = _decision_upper(final_decision.get("decision"))

    if blocking_manual_fail:
        findings.append(f"blocking manual gates failed: {', '.join(blocking_manual_fail)}")
    if conditional_manual_fail:
        findings.append(f"conditional manual gates failed: {', '.join(conditional_manual_fail)}")

    status = "PASS"
    if findings:
        status = "FAIL"
    elif blocking_manual_pending or final_decision_value not in {"GO", "PASS", "APPROVED"}:
        status = "PENDING_OPERATOR"

    if status == "PASS" and final_decision_value not in {"GO", "PASS", "APPROVED"}:
        status = "FAIL"
        findings.append("final release decision is not GO")

    if status == "PASS":
        overall_decision = "GO"
    elif status == "PENDING_OPERATOR":
        overall_decision = "PENDING_OPERATOR"
    else:
        overall_decision = "NO-GO"

    return {
        "schema": "mole_release_go_no_go_decision_v1",
        "status": status,
        "overall_decision": overall_decision,
        "allow_pending_operator": allow_pending_operator,
        "clean_workflow_status": summary.get("status"),
        "bundle_status": bundle.get("overall_status"),
        "release_cert_status": cert.get("status"),
        "package_hygiene_status": hygiene.get("status"),
        "blocking_manual_pending": blocking_manual_pending,
        "blocking_manual_fail": blocking_manual_fail,
        "conditional_manual_fail": conditional_manual_fail,
        "final_release_decision": final_decision,
        "findings": findings,
    }


def _render_md(report: Dict[str, Any]) -> str:
    lines = [
        "# MOLE-DAS Release Go / No-Go Decision",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Overall decision: `{report.get('overall_decision')}`",
        f"- Clean workflow: `{report.get('clean_workflow_status')}`",
        f"- Release bundle: `{report.get('bundle_status')}`",
        f"- Release certificate: `{report.get('release_cert_status')}`",
        f"- Package hygiene: `{report.get('package_hygiene_status')}`",
        "",
    ]
    if report.get("blocking_manual_pending"):
        lines.append("## Blocking manual gates pending")
        for item in report.get("blocking_manual_pending") or []:
            lines.append(f"- `{item}`")
        lines.append("")
    if report.get("blocking_manual_fail"):
        lines.append("## Blocking manual gates failed")
        for item in report.get("blocking_manual_fail") or []:
            lines.append(f"- `{item}`")
        lines.append("")
    if report.get("conditional_manual_fail"):
        lines.append("## Conditional manual gates failed")
        for item in report.get("conditional_manual_fail") or []:
            lines.append(f"- `{item}`")
        lines.append("")
    if report.get("findings"):
        lines.append("## Findings")
        for item in report.get("findings") or []:
            lines.append(f"- {item}")
        lines.append("")
    if report.get("missing_artifacts"):
        lines.append("## Missing Artifacts")
        for item in report.get("missing_artifacts") or []:
            lines.append(f"- `{item}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate the final MOLE-DAS release go/no-go decision.")
    ap.add_argument("--artifact-dir", required=True)
    ap.add_argument("--allow-pending-operator", action="store_true")
    args = ap.parse_args()

    artifact_dir = Path(args.artifact_dir).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report = _evaluate(artifact_dir, allow_pending_operator=bool(args.allow_pending_operator))

    json_path = artifact_dir / "release_go_no_go_decision.json"
    md_path = artifact_dir / "release_go_no_go_decision.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(_render_md(report), encoding="utf-8")

    print(md_path.read_text(encoding="utf-8"))

    if report.get("status") == "PASS":
        return 0
    if report.get("status") == "PENDING_OPERATOR" and args.allow_pending_operator:
        return 0
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
