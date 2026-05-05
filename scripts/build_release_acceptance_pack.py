from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


PACKAGED_EVIDENCE_RULES: Dict[str, Dict[str, Any]] = {
    "wizard_launch": {
        "steps": ["launch_wizard"],
        "fields": ["wizard_startup_path"],
        "summary": "Packaged acceptance launched the installed Wizard and captured startup diagnostics.",
    },
    "runner_launch_test": {
        "steps": ["launch_runner"],
        "fields": ["runner_startup_path", "runner_config_path"],
        "summary": "Packaged acceptance launched the installed Runner in SIM UI mode and captured startup diagnostics.",
    },
    "standard_recorded_test_flow": {
        "steps": ["seed_session", "launch_runner", "export_report_pack"],
        "fields": ["session_dir", "runner_config_path", "report_pack_summary_path"],
        "summary": "Packaged acceptance seeded a deterministic session, launched Runner, and exported the report pack.",
    },
    "final_report_export": {
        "steps": ["export_report_pack"],
        "fields": ["final_report_path", "final_report_index_path"],
        "requires_final_report_render": True,
        "summary": "Packaged acceptance generated the final report artifacts from the seeded session.",
    },
}


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_json_optional(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _workflow_step_status(summary: Dict[str, Any], step_name: str) -> str:
    for step in list(summary.get("steps") or []):
        if not isinstance(step, dict):
            continue
        if str(step.get("name") or "").strip() == step_name:
            return str(step.get("status") or "").strip().upper()
    return ""


def _packaged_step_status(packaged: Dict[str, Any], step_name: str) -> str:
    for step in list(packaged.get("steps") or []):
        if not isinstance(step, dict):
            continue
        if str(step.get("name") or "").strip() == step_name:
            return str(step.get("status") or "").strip().upper()
    return ""


def _load_report_pack_summary(output_dir: Path, packaged: Dict[str, Any]) -> Dict[str, Any]:
    candidates = [output_dir / "report_pack_summary.json"]
    packaged_report_path = str(packaged.get("report_pack_summary_path") or "").strip()
    if packaged_report_path:
        candidates.append(Path(packaged_report_path))
    for candidate in candidates:
        if candidate.is_file():
            return _read_json_optional(candidate)
    return {}


def _final_report_render_pass(report_summary: Dict[str, Any]) -> Tuple[bool, str]:
    final_report = report_summary.get("final_report") if isinstance(report_summary.get("final_report"), dict) else {}
    render_status = final_report.get("render_status") if isinstance(final_report.get("render_status"), dict) else {}
    docx = render_status.get("docx") if isinstance(render_status.get("docx"), dict) else {}
    pdf = render_status.get("pdf") if isinstance(render_status.get("pdf"), dict) else {}
    docx_status = str(docx.get("status") or "").strip().lower()
    pdf_status = str(pdf.get("status") or "").strip().lower()
    if docx_status == "generated" and pdf_status == "generated":
        return True, "final report DOCX and PDF render status are generated"
    if not report_summary:
        return False, "report_pack_summary.json is unavailable"
    return False, f"final report render status is docx={docx_status or '(missing)'}, pdf={pdf_status or '(missing)'}"


def _evidence_paths_for_rule(rule: Dict[str, Any], packaged: Dict[str, Any], output_dir: Path) -> List[str]:
    paths: List[str] = []
    for field in list(rule.get("fields") or []):
        value = str(packaged.get(field) or "").strip()
        if value:
            paths.append(value)
    for local_name in [
        "wizard_startup__latest.json",
        "runner_startup__latest.json",
        "report_pack_summary.json",
        "final_test_report_v1.md",
        "final_report_index.json",
    ]:
        local_path = output_dir / local_name
        if local_path.exists():
            paths.append(str(local_path))
    return sorted(dict.fromkeys(paths))


def _packaged_evidence_status(item_id: str, packaged: Dict[str, Any], output_dir: Path) -> Tuple[str, str, List[str]]:
    rule = PACKAGED_EVIDENCE_RULES.get(item_id)
    if not rule:
        return "PENDING_OPERATOR", "manual operator evidence required", []
    if not packaged:
        return "PENDING_OPERATOR", "packaged_acceptance_summary.json is unavailable", []
    if str(packaged.get("status") or "").strip().upper() == "FAIL":
        return "FAIL", "packaged acceptance status is FAIL", []

    missing_steps: List[str] = []
    failed_steps: List[str] = []
    for step_name in list(rule.get("steps") or []):
        status = _packaged_step_status(packaged, step_name)
        if status == "FAIL":
            failed_steps.append(step_name)
        elif status != "PASS":
            missing_steps.append(step_name)
    if failed_steps:
        return "FAIL", "packaged acceptance failed: " + ", ".join(failed_steps), []
    if missing_steps:
        return "PENDING_OPERATOR", "packaged acceptance did not prove: " + ", ".join(missing_steps), []

    missing_fields = [field for field in list(rule.get("fields") or []) if not str(packaged.get(field) or "").strip()]
    if missing_fields:
        return "PENDING_OPERATOR", "packaged acceptance summary lacks evidence fields: " + ", ".join(missing_fields), []

    if bool(rule.get("requires_final_report_render")):
        render_ok, render_detail = _final_report_render_pass(_load_report_pack_summary(output_dir, packaged))
        if not render_ok:
            return "PENDING_OPERATOR", render_detail, _evidence_paths_for_rule(rule, packaged, output_dir)

    evidence_paths = _evidence_paths_for_rule(rule, packaged, output_dir)
    return "PASS", str(rule.get("summary") or "packaged acceptance evidence passed"), evidence_paths


def _derive_item_status(
    item: Dict[str, Any],
    summary: Dict[str, Any],
    packaged: Dict[str, Any],
    output_dir: Path,
) -> Tuple[str, str, str, List[str]]:
    acceptance_type = str(item.get("acceptance_type") or "").strip().upper()
    if acceptance_type == "AUTOMATED":
        step_name = str(item.get("workflow_step") or "").strip()
        step_status = _workflow_step_status(summary, step_name)
        if step_status == "PASS":
            return "PASS", "clean_workflow", f"clean workflow step `{step_name}` passed", []
        if step_status == "FAIL":
            return "FAIL", "clean_workflow", f"clean workflow step `{step_name}` failed", []
        return "NOT_RUN", "clean_workflow", f"clean workflow step `{step_name}` was not run", []

    status, detail, evidence_paths = _packaged_evidence_status(str(item.get("id") or ""), packaged, output_dir)
    if status == "PASS":
        return status, "packaged_acceptance", detail, evidence_paths
    if status == "FAIL":
        return status, "packaged_acceptance", detail, evidence_paths
    return "PENDING_OPERATOR", "operator_pending", detail, evidence_paths


def _matrix_rows(defn: Dict[str, Any], summary: Dict[str, Any], packaged: Dict[str, Any], output_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in list(defn.get("items") or []):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        status, decision_source, evidence_summary, evidence_paths = _derive_item_status(item, summary, packaged, output_dir)
        row["status"] = status
        row["decision_source"] = decision_source
        row["evidence_summary"] = evidence_summary
        row["evidence_paths"] = evidence_paths
        rows.append(row)
    return rows


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "id",
        "category",
        "scenario",
        "entrypoint",
        "acceptance_type",
        "gate",
        "status",
        "decision_source",
        "expected_outcome",
        "evidence_required",
        "evidence_summary",
        "workflow_step",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def _write_matrix_md(path: Path, rows: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    lines = [
        "# MOLE-DAS Production Acceptance Matrix",
        "",
        f"- Workflow status: `{summary.get('status') or 'UNKNOWN'}`",
        f"- Source summary: `{summary.get('artifact_dir') or ''}`",
        "",
        "| ID | Category | Scenario | Type | Gate | Status | Decision Source | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('id','')} | {row.get('category','')} | {row.get('scenario','')} | "
            f"{row.get('acceptance_type','')} | {row.get('gate','')} | {row.get('status','')} | "
            f"{row.get('decision_source','')} | {str(row.get('evidence_summary','')).replace('|', '/')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _checklist_decision(row: Dict[str, Any]) -> Any:
    if str(row.get("status") or "").strip().upper() in {"PASS", "FAIL"} and str(row.get("decision_source") or "") != "operator_pending":
        return row.get("status")
    if str(row.get("acceptance_type") or "").strip().upper() == "AUTOMATED":
        return row.get("status")
    return None


def _write_checklist_md(path: Path, rows: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    lines = [
        "# MOLE-DAS Operator Go / No-Go Checklist",
        "",
        f"- Release workflow status: `{summary.get('status') or 'UNKNOWN'}`",
        "- Instruction: automation-backed manual gates are pre-filled from packaged acceptance evidence.",
        "- Instruction: remaining manual gates must be marked `GO`, `NO-GO`, or `N/A`, then signed and dated.",
        "",
    ]
    for row in rows:
        if str(row.get("acceptance_type") or "").strip().upper() != "MANUAL":
            continue
        decision = _checklist_decision(row)
        lines.extend(
            [
                f"## {row.get('scenario','')}",
                f"- ID: `{row.get('id','')}`",
                f"- Gate: `{row.get('gate','')}`",
                f"- Entry point: `{row.get('entrypoint','')}`",
                f"- Expected outcome: {row.get('expected_outcome','')}",
                f"- Evidence required: {row.get('evidence_required','')}",
                f"- Current decision: `{decision or 'PENDING_OPERATOR'}`",
                f"- Decision source: `{row.get('decision_source','')}`",
                f"- Evidence summary: {row.get('evidence_summary','')}",
                "- Operator / reviewer:",
                "- Date:",
                "- Notes:",
                "",
            ]
        )
    lines.extend(
        [
            "## Final release decision",
            "- Overall decision: [ ] GO   [ ] NO-GO",
            "- Approved by:",
            "- Approval basis:",
            "- Date:",
            "- Notes:",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_checklist_json(path: Path, rows: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    payload = {
        "schema": "mole_release_go_no_go_checklist_v1",
        "workflow_status": summary.get("status") or "UNKNOWN",
        "items": [
            {
                "id": row.get("id"),
                "scenario": row.get("scenario"),
                "gate": row.get("gate"),
                "entrypoint": row.get("entrypoint"),
                "expected_outcome": row.get("expected_outcome"),
                "evidence_required": row.get("evidence_required"),
                "decision": _checklist_decision(row),
                "decision_source": row.get("decision_source"),
                "evidence_summary": row.get("evidence_summary"),
                "evidence_paths": row.get("evidence_paths") or [],
                "operator": "",
                "date": "",
                "notes": "",
            }
            for row in rows
        ],
        "final_decision": {
            "decision": "",
            "approved_by": "",
            "approval_basis": "",
            "date": "",
            "notes": "",
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_evidence_json(path: Path, rows: List[Dict[str, Any]], packaged: Dict[str, Any]) -> None:
    payload = {
        "schema": "mole_operator_validation_evidence_v1",
        "package_label": packaged.get("package_label") or "",
        "git_commit": packaged.get("git_commit") or "",
        "packaged_acceptance_status": packaged.get("status") or "",
        "items": [
            {
                "id": row.get("id"),
                "status": row.get("status"),
                "decision_source": row.get("decision_source"),
                "evidence_summary": row.get("evidence_summary"),
                "evidence_paths": row.get("evidence_paths") or [],
            }
            for row in rows
            if row.get("decision_source") == "packaged_acceptance"
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_evidence_md(path: Path, rows: List[Dict[str, Any]], packaged: Dict[str, Any]) -> None:
    lines = [
        "# MOLE-DAS Operator Validation Evidence",
        "",
        f"- Package label: `{packaged.get('package_label') or ''}`",
        f"- Git commit: `{packaged.get('git_commit') or ''}`",
        f"- Packaged acceptance: `{packaged.get('status') or ''}`",
        "",
    ]
    for row in rows:
        if row.get("decision_source") != "packaged_acceptance":
            continue
        lines.extend(
            [
                f"## {row.get('id')}",
                f"- Status: `{row.get('status')}`",
                f"- Evidence: {row.get('evidence_summary')}",
            ]
        )
        for evidence_path in list(row.get("evidence_paths") or []):
            lines.append(f"- Path: `{evidence_path}`")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build MOLE-DAS release acceptance artifacts.")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--summary-json", required=True)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    summary_json = Path(args.summary_json).resolve()

    matrix_def = _read_json(repo_root / "config" / "mole_release_acceptance_matrix_v1.json")
    summary = _read_json(summary_json)
    packaged = _read_json_optional(output_dir / "packaged_acceptance_summary.json")
    rows = _matrix_rows(matrix_def, summary, packaged, output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "production_acceptance_matrix.csv", rows)
    _write_matrix_md(output_dir / "production_acceptance_matrix.md", rows, summary)
    _write_checklist_md(output_dir / "operator_go_no_go_checklist.md", rows, summary)
    _write_checklist_json(output_dir / "operator_go_no_go_checklist.json", rows, summary)
    _write_evidence_json(output_dir / "operator_validation_evidence.json", rows, packaged)
    _write_evidence_md(output_dir / "operator_validation_evidence.md", rows, packaged)
    (output_dir / "production_acceptance_matrix_source.json").write_text(json.dumps(matrix_def, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
