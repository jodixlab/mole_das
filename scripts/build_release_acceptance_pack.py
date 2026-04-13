from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _workflow_step_status(summary: Dict[str, Any], step_name: str) -> str:
    for step in list(summary.get("steps") or []):
        if not isinstance(step, dict):
            continue
        if str(step.get("name") or "").strip() == step_name:
            return str(step.get("status") or "").strip().upper()
    return ""


def _derive_item_status(item: Dict[str, Any], summary: Dict[str, Any]) -> str:
    acceptance_type = str(item.get("acceptance_type") or "").strip().upper()
    if acceptance_type != "AUTOMATED":
        return "PENDING_OPERATOR"
    step_name = str(item.get("workflow_step") or "").strip()
    step_status = _workflow_step_status(summary, step_name)
    if step_status == "PASS":
        return "PASS"
    if step_status == "FAIL":
        return "FAIL"
    return "NOT_RUN"


def _matrix_rows(defn: Dict[str, Any], summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in list(defn.get("items") or []):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["status"] = _derive_item_status(item, summary)
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
        "expected_outcome",
        "evidence_required",
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
        "| ID | Category | Scenario | Type | Gate | Status | Expected Outcome | Evidence Required |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('id','')} | {row.get('category','')} | {row.get('scenario','')} | "
            f"{row.get('acceptance_type','')} | {row.get('gate','')} | {row.get('status','')} | "
            f"{str(row.get('expected_outcome','')).replace('|', '/')} | {str(row.get('evidence_required','')).replace('|', '/')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_checklist_md(path: Path, rows: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    lines = [
        "# MOLE-DAS Operator Go / No-Go Checklist",
        "",
        f"- Release workflow status: `{summary.get('status') or 'UNKNOWN'}`",
        "- Instruction: mark each manual gate `GO`, `NO-GO`, or `N/A`, then sign and date the checklist.",
        "",
    ]
    for row in rows:
        if str(row.get("acceptance_type") or "").strip().upper() != "MANUAL":
            continue
        lines.extend(
            [
                f"## {row.get('scenario','')}",
                f"- ID: `{row.get('id','')}`",
                f"- Gate: `{row.get('gate','')}`",
                f"- Entry point: `{row.get('entrypoint','')}`",
                f"- Expected outcome: {row.get('expected_outcome','')}",
                f"- Evidence required: {row.get('evidence_required','')}",
                "- Decision: [ ] GO   [ ] NO-GO   [ ] N/A",
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
                "decision": None if str(row.get("acceptance_type") or "").strip().upper() == "MANUAL" else row.get("status"),
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
    rows = _matrix_rows(matrix_def, summary)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "production_acceptance_matrix.csv", rows)
    _write_matrix_md(output_dir / "production_acceptance_matrix.md", rows, summary)
    _write_checklist_md(output_dir / "operator_go_no_go_checklist.md", rows, summary)
    _write_checklist_json(output_dir / "operator_go_no_go_checklist.json", rows, summary)
    (output_dir / "production_acceptance_matrix_source.json").write_text(json.dumps(matrix_def, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
