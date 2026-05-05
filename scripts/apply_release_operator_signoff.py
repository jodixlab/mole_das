from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


PACKAGE_SIGNOFF_ID = "package_review_signoff"


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _decision_value(value: Any) -> str:
    return str(value or "").strip().upper()


def _default_date() -> str:
    return datetime.now().astimezone().date().isoformat()


def _load_package_summary(artifact_dir: Path) -> Dict[str, Any]:
    path = artifact_dir / "packaged_acceptance_summary.json"
    if path.exists():
        return _read_json(path)
    return {}


def _receipt_lines(
    artifact_dir: Path,
    checklist: Dict[str, Any],
    package_summary: Dict[str, Any],
    *,
    approved_by: str,
    decision: str,
    approval_basis: str,
    date: str,
    notes: str,
) -> List[str]:
    package_label = str(package_summary.get("package_label") or "")
    git_commit = str(package_summary.get("git_commit") or "")
    lines = [
        "# MOLE-DAS Release Operator Signoff",
        "",
        f"- Artifact directory: `{artifact_dir}`",
        f"- Package label: `{package_label}`",
        f"- Git commit: `{git_commit}`",
        f"- Decision: `{decision}`",
        f"- Approved by: `{approved_by}`",
        f"- Date: `{date}`",
        f"- Approval basis: {approval_basis}",
        f"- Notes: {notes or '(none)'}",
        "",
        "## Blocking Gates",
    ]
    for item in list(checklist.get("items") or []):
        if str(item.get("gate") or "").strip().upper() != "BLOCKING":
            continue
        lines.append(
            f"- `{item.get('id')}`: decision `{item.get('decision') or ''}` "
            f"source `{item.get('decision_source') or ''}`"
        )
    return lines


def apply_signoff(
    artifact_dir: Path,
    *,
    approved_by: str,
    approval_basis: str,
    decision: str,
    date: str,
    notes: str,
) -> Dict[str, Any]:
    artifact_dir = artifact_dir.resolve()
    checklist_path = artifact_dir / "operator_go_no_go_checklist.json"
    if not checklist_path.exists():
        raise FileNotFoundError(f"operator checklist not found: {checklist_path}")

    decision_u = _decision_value(decision)
    if decision_u not in {"GO", "NO-GO"}:
        raise ValueError("--decision must be GO or NO-GO")
    if not approved_by.strip():
        raise ValueError("--approved-by is required")
    if not approval_basis.strip():
        raise ValueError("--approval-basis is required")

    checklist = _read_json(checklist_path)
    items = list(checklist.get("items") or [])
    matched = False
    for item in items:
        if str(item.get("id") or "") != PACKAGE_SIGNOFF_ID:
            continue
        item["decision"] = decision_u
        item["decision_source"] = "operator_signoff"
        item["operator"] = approved_by.strip()
        item["date"] = date
        item["notes"] = notes.strip()
        item["approval_basis"] = approval_basis.strip()
        matched = True
        break
    if not matched:
        raise ValueError(f"{PACKAGE_SIGNOFF_ID} is not present in operator checklist")

    checklist["items"] = items
    checklist["final_decision"] = {
        "decision": decision_u,
        "approved_by": approved_by.strip(),
        "approval_basis": approval_basis.strip(),
        "date": date,
        "notes": notes.strip(),
    }
    _write_json(checklist_path, checklist)

    package_summary = _load_package_summary(artifact_dir)
    receipt = {
        "schema": "mole_release_operator_signoff_v1",
        "artifact_dir": str(artifact_dir),
        "package_label": str(package_summary.get("package_label") or ""),
        "git_commit": str(package_summary.get("git_commit") or ""),
        "decision": decision_u,
        "approved_by": approved_by.strip(),
        "approval_basis": approval_basis.strip(),
        "date": date,
        "notes": notes.strip(),
        "checklist_path": str(checklist_path),
    }
    receipt_json = artifact_dir / "operator_release_signoff.json"
    receipt_md = artifact_dir / "operator_release_signoff.md"
    _write_json(receipt_json, receipt)
    receipt_md.write_text(
        "\n".join(
            _receipt_lines(
                artifact_dir,
                checklist,
                package_summary,
                approved_by=approved_by.strip(),
                decision=decision_u,
                approval_basis=approval_basis.strip(),
                date=date,
                notes=notes.strip(),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return receipt


def _run_release_gate(artifact_dir: Path) -> int:
    script = Path(__file__).resolve().with_name("release_go_no_go_gate.py")
    result = subprocess.run(
        [sys.executable, str(script), "--artifact-dir", str(artifact_dir)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return int(result.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply final MOLE-DAS operator release signoff to an artifact folder.")
    ap.add_argument("--artifact-dir", required=True)
    ap.add_argument("--approved-by", required=True)
    ap.add_argument("--approval-basis", required=True)
    ap.add_argument("--decision", choices=["GO", "NO-GO"], default="GO")
    ap.add_argument("--date", default=_default_date())
    ap.add_argument("--notes", default="")
    ap.add_argument("--skip-gate", action="store_true", help="Update checklist only; do not refresh release_go_no_go_decision.*")
    args = ap.parse_args()

    artifact_dir = Path(args.artifact_dir).expanduser().resolve()
    receipt = apply_signoff(
        artifact_dir,
        approved_by=str(args.approved_by),
        approval_basis=str(args.approval_basis),
        decision=str(args.decision),
        date=str(args.date),
        notes=str(args.notes),
    )
    print(json.dumps(receipt, indent=2))
    if args.skip_gate:
        return 0
    return _run_release_gate(artifact_dir)


if __name__ == "__main__":
    raise SystemExit(main())
