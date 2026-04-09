"""Regression harness for post-cal carry-forward policy and artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import mole_postcal_policy
import mole_report_pack_v1


def _result(name: str, passed: bool, detail: str, **extra: Any) -> Dict[str, Any]:
    out = {
        "name": str(name),
        "passed": bool(passed),
        "detail": str(detail),
    }
    out.update(extra)
    return out


def _find_validation_session(root: Path, explicit: Optional[Path] = None) -> Optional[Path]:
    if explicit is not None:
        return explicit if explicit.exists() else None
    validation_dir = root / "mole_das_data" / "validation"
    if validation_dir.exists():
        preferred = sorted(validation_dir.rglob("mole_session_2026_03_02_2316.json"))
        if preferred:
            return preferred[-1]
        any_sessions = sorted(validation_dir.rglob("mole_session_*.json"))
        if any_sessions:
            return any_sessions[-1]
    return None


def _matrix_cases() -> List[Dict[str, Any]]:
    return [
        {
            "name": "EPA method stays manual",
            "ctx": {
                "code": "O2",
                "track": "PROJECT",
                "session_mode_name": "FORMAL",
                "diagnostic_only": False,
                "may_support_compliance": True,
                "method_effective": "EPA_3A_O2",
                "profile_id": "PROFILE:EPA_3A_O2",
            },
            "expect": {"policy_mode": "MANUAL_ONLY", "allow_auto_promote": False, "policy_rule_id": "epa_method_manual_only"},
        },
        {
            "name": "ASTM D6522 project track auto-zero",
            "ctx": {
                "code": "CO",
                "track": "PROJECT",
                "session_mode_name": "FORMAL",
                "diagnostic_only": False,
                "may_support_compliance": True,
                "method_effective": "ASTM_D6522",
                "profile_id": "PROFILE:DEFAULT",
            },
            "expect": {"policy_mode": "AUTO_ZERO_ONLY", "allow_auto_promote": True, "policy_rule_id": "astm_d6522_or_default_diag_track_auto_zero"},
        },
        {
            "name": "ASTM D6522 formal compliance manual",
            "ctx": {
                "code": "CO",
                "track": "COMPLIANCE",
                "session_mode_name": "FORMAL",
                "diagnostic_only": False,
                "may_support_compliance": True,
                "method_effective": "ASTM_D6522",
                "profile_id": "PROFILE:DEFAULT",
            },
            "expect": {"policy_mode": "MANUAL_ONLY", "allow_auto_promote": False, "policy_rule_id": "astm_d6522_or_default_manual_elsewhere"},
        },
        {
            "name": "Diagnostics without explicit method auto-zero",
            "ctx": {
                "code": "NOX",
                "track": "DIAG",
                "session_mode_name": "DIAGNOSTICS_SESSION",
                "diagnostic_only": True,
                "may_support_compliance": False,
                "method_effective": "",
                "profile_id": "",
            },
            "expect": {"policy_mode": "AUTO_ZERO_ONLY", "allow_auto_promote": True, "policy_rule_id": "diagnostic_only_without_explicit_method_auto_zero"},
        },
        {
            "name": "Unknown non-diagnostic method stays manual",
            "ctx": {
                "code": "VOC",
                "track": "FORMAL",
                "session_mode_name": "FORMAL",
                "diagnostic_only": False,
                "may_support_compliance": True,
                "method_effective": "ALT_VENDOR_METHOD",
                "profile_id": "PROFILE:ALT",
            },
            "expect": {"policy_mode": "MANUAL_ONLY", "allow_auto_promote": False, "policy_rule_id": "fallback_manual_only"},
        },
    ]


def _run_matrix_regression() -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for case in _matrix_cases():
        decision = mole_postcal_policy.evaluate_postcal_carry_forward_policy(dict(case.get("ctx") or {}))
        expect = dict(case.get("expect") or {})
        mismatches = []
        for key, value in expect.items():
            if decision.get(key) != value:
                mismatches.append(f"{key} expected {value!r} got {decision.get(key)!r}")
        results.append(_result(
            str(case.get("name") or "matrix case"),
            not mismatches,
            "; ".join(mismatches) if mismatches else f"{decision.get('policy_mode')} via {decision.get('policy_rule_id')}",
            decision=decision,
        ))
    return results


def _load_session(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _expected_sorted(values: List[str]) -> List[str]:
    return sorted(str(v).strip().upper() for v in values if str(v).strip())


def _lifecycle_regression_session() -> Dict[str, Any]:
    return {
        "daq_runner": {
            "active_run_index": 2,
            "runs": [
                {"run_no": 1, "start_iso": "2026-04-08T14:00:00Z", "end_iso": "2026-04-08T14:30:00Z"},
                {"run_no": 2, "start_iso": "2026-04-08T15:00:00Z", "end_iso": "2026-04-08T15:30:00Z"},
                {"run_no": 3, "start_iso": "2026-04-08T16:00:00Z", "end_iso": "2026-04-08T16:45:00Z"},
            ],
            "worksteps": {
                "postcal": {
                    "completed_runs": {
                        "2": {
                            "completed_iso": "2026-04-08T15:40:00Z",
                            "overall_pass": True,
                        }
                    }
                }
            },
            "pollutant_adjustments": {
                "enabled": True,
                "drift_basis": "ACTIVE_RUN_HR",
                "formula": "adjusted = raw + bias + (drift_per_hr * elapsed_run_hr)",
                "channels": {
                    "CO": {
                        "enabled": True,
                        "bias": 1.5,
                        "drift_per_hr": 0.0,
                        "note": "Persistent manual baseline trim",
                        "updated_by": "Regression",
                        "updated_iso": "2026-04-08T13:50:00Z",
                        "source": "MANUAL",
                        "scope": "PERSISTENT",
                    },
                    "NOX": {
                        "enabled": True,
                        "bias": -1.0,
                        "drift_per_hr": 0.1,
                        "note": "Single-run carry-forward trial",
                        "updated_by": "Regression",
                        "updated_iso": "2026-04-08T14:35:00Z",
                        "source": "MANUAL",
                        "scope": "NEXT_RUN_ONLY",
                        "effective_after_run_no": 1,
                        "expires_after_run_no": 2,
                    },
                    "VOC": {
                        "enabled": True,
                        "bias": 0.25,
                        "drift_per_hr": 0.0,
                        "note": "Inherited until next post-cal",
                        "updated_by": "Regression",
                        "updated_iso": "2026-04-08T14:35:00Z",
                        "source": "POSTCAL_AUTO",
                        "source_run_no": 1,
                        "scope": "UNTIL_NEXT_POSTCAL",
                        "effective_after_run_no": 1,
                        "expires_after_postcal_run_no": 2,
                    },
                    "O2": {
                        "enabled": False,
                        "bias": 0.0,
                        "drift_per_hr": 0.2,
                        "note": "Suspended inherited adjustment",
                        "updated_by": "Regression",
                        "updated_iso": "2026-04-08T15:45:00Z",
                        "source": "POSTCAL_AUTO",
                        "source_run_no": 1,
                        "scope": "UNTIL_NEXT_POSTCAL",
                        "effective_after_run_no": 1,
                        "lifecycle_status": "POLICY_SUSPENDED",
                        "status_reason": "Inherited adjustment suspended because method/profile changed.",
                    },
                },
            },
        },
        "pollutants": {
            "prescriptions": {
                "CO": {"expected_units": "ppm"},
                "NOX": {"expected_units": "ppm"},
                "VOC": {"expected_units": "ppm"},
                "O2": {"expected_units": "%"},
            }
        },
    }


def _run_validation_session_regression(root: Path, cfg_path: Optional[Path]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if cfg_path is None:
        return [_result("Validation session located", False, "No validation session JSON was found under mole_das_data/validation.")]

    session = _load_session(cfg_path)
    reviews = mole_postcal_policy.collect_postcal_reviews(session)
    history = mole_postcal_policy.collect_postcal_history(
        session,
        units_lookup=lambda sess_local, pollutant: mole_report_pack_v1._units_for_pollutant(sess_local, pollutant),
    )
    latest_review = reviews[0] if reviews else {}
    promoted = _expected_sorted(list(latest_review.get("promoted_codes") or []))
    manual_only = _expected_sorted(list(latest_review.get("manual_only_codes") or []))
    history_events = {(str(row.get("pollutant") or ""), str(row.get("event") or "")) for row in history if isinstance(row, dict)}

    results.append(_result(
        "Validation session review summary",
        bool(latest_review) and promoted == ["CO", "NOX"] and manual_only == ["O2", "VOC"],
        f"promoted={promoted} manual_only={manual_only}",
        cfg_path=str(cfg_path),
    ))
    results.append(_result(
        "Validation session history rows",
        len(history) == 4 and history_events == {("CO", "PROMOTED"), ("NOX", "PROMOTED"), ("O2", "MANUAL_ONLY"), ("VOC", "MANUAL_ONLY")},
        f"history_rows={len(history)} events={sorted(history_events)}",
    ))

    policy_expect = {
        "O2": "MANUAL_ONLY",
        "VOC": "MANUAL_ONLY",
        "CO": "AUTO_ZERO_ONLY",
        "NOX": "AUTO_ZERO_ONLY",
    }
    mismatches = []
    for pollutant, expected_mode in policy_expect.items():
        decision = mole_postcal_policy.postcal_carry_forward_policy(session, pollutant)
        if decision.get("policy_mode") != expected_mode:
            mismatches.append(f"{pollutant} expected {expected_mode} got {decision.get('policy_mode')}")
    results.append(_result(
        "Validation session policy decisions",
        not mismatches,
        "; ".join(mismatches) if mismatches else "mixed-method policy matrix matched expected analyte modes",
    ))

    padj_summary = mole_report_pack_v1._pollutant_adjustment_summary(session)
    active_rows = sorted(str(row.get("pollutant") or "") for row in list(padj_summary.get("rows") or []) if bool(row.get("active_now")))
    results.append(_result(
        "Report-pack pollutant adjustment summary",
        int(padj_summary.get("history_row_count") or 0) == 4
        and int(padj_summary.get("decision_review_count") or 0) >= 1
        and active_rows == ["CO", "NOX"],
        f"history_row_count={padj_summary.get('history_row_count')} decision_review_count={padj_summary.get('decision_review_count')} active_rows={active_rows}",
    ))

    lifecycle_summary = mole_report_pack_v1._pollutant_adjustment_summary(_lifecycle_regression_session())
    lifecycle_states = {
        str(row.get("pollutant") or ""): str(row.get("state") or "")
        for row in list(lifecycle_summary.get("rows") or [])
        if isinstance(row, dict)
    }
    lifecycle_scope = {
        str(row.get("pollutant") or ""): str(row.get("scope_label") or "")
        for row in list(lifecycle_summary.get("rows") or [])
        if isinstance(row, dict)
    }
    results.append(_result(
        "Lifecycle scope and expiry summary",
        lifecycle_states == {"CO": "ACTIVE", "NOX": "EXPIRED", "O2": "SUSPENDED", "VOC": "EXPIRED"}
        and lifecycle_scope == {
            "CO": "persistent",
            "NOX": "next run only",
            "O2": "until next post-cal",
            "VOC": "until next post-cal",
        },
        f"states={lifecycle_states} scope={lifecycle_scope}",
    ))

    with tempfile.TemporaryDirectory(prefix="mole_postcal_policy_regression_") as tmp:
        out_dir = mole_report_pack_v1.generate_report_pack_v1(
            session=session,
            cfg_path=cfg_path,
            session_dir=Path(tmp),
        )
        summary_json = out_dir / "summary.json"
        history_csv = out_dir / "pollutant_adjustment_history.csv"
        snapshot_csv = out_dir / "pollutant_adjustments_snapshot.csv"
        try:
            summary_payload = json.loads(summary_json.read_text(encoding="utf-8"))
        except Exception:
            summary_payload = {}
        try:
            with history_csv.open("r", encoding="utf-8", newline="") as fh:
                history_rows = list(csv.DictReader(fh))
        except Exception:
            history_rows = []
        try:
            with snapshot_csv.open("r", encoding="utf-8", newline="") as fh:
                snapshot_rows = list(csv.DictReader(fh))
        except Exception:
            snapshot_rows = []
        snapshot_fieldnames = list(snapshot_rows[0].keys()) if snapshot_rows else []

        summary_padj = summary_payload.get("pollutant_adjustments") if isinstance(summary_payload.get("pollutant_adjustments"), dict) else {}
        summary_review = summary_padj.get("latest_review") if isinstance(summary_padj.get("latest_review"), dict) else {}
        csv_events = {(str(row.get("pollutant") or ""), str(row.get("event") or "")) for row in history_rows}
        csv_active = sorted(str(row.get("pollutant") or "") for row in snapshot_rows if str(row.get("state") or "").strip().upper() == "ACTIVE")

        results.append(_result(
            "Temporary report-pack artifacts",
            summary_json.exists() and history_csv.exists() and snapshot_csv.exists(),
            f"summary={summary_json.exists()} history_csv={history_csv.exists()} snapshot_csv={snapshot_csv.exists()}",
            out_dir=str(out_dir),
        ))
        results.append(_result(
            "Temporary report-pack provenance content",
            _expected_sorted(list(summary_review.get("promoted_codes") or [])) == ["CO", "NOX"]
            and csv_events == {("CO", "PROMOTED"), ("NOX", "PROMOTED"), ("O2", "MANUAL_ONLY"), ("VOC", "MANUAL_ONLY")}
            and csv_active == ["CO", "NOX"]
            and {"scope_label", "lifecycle_status", "status_reason"}.issubset(set(snapshot_fieldnames)),
            f"summary_promoted={summary_review.get('promoted_codes')} csv_events={sorted(csv_events)} csv_active={csv_active} fields={snapshot_fieldnames}",
        ))
    return results


def run_regression(root: Optional[Path] = None, validation_config: Optional[Path] = None) -> Dict[str, Any]:
    code_dir = Path(__file__).resolve().parent
    root_dir = Path(root).resolve() if root else code_dir.parent
    cfg_path = _find_validation_session(root_dir, Path(validation_config).resolve() if validation_config else None)
    cases = []
    cases.extend(_run_matrix_regression())
    cases.extend(_run_validation_session_regression(root_dir, cfg_path))
    failures = [case for case in cases if not bool(case.get("passed"))]
    return {
        "ok": not failures,
        "root": str(root_dir),
        "validation_config": (str(cfg_path) if cfg_path else ""),
        "case_count": len(cases),
        "failure_count": len(failures),
        "cases": cases,
    }


def format_regression_report(report: Dict[str, Any]) -> str:
    lines = [
        "POST-CAL POLICY REGRESSION",
        "===========================",
        f"Root: {report.get('root')}",
        f"Validation config: {report.get('validation_config') or '(not found)'}",
        f"Cases: {report.get('case_count')}  Failures: {report.get('failure_count')}",
        "",
    ]
    for case in list(report.get("cases") or []):
        marker = "PASS" if case.get("passed") else "FAIL"
        lines.append(f"[{marker}] {case.get('name')}")
        lines.append(f"  {case.get('detail')}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="Package root (default: auto from script location).")
    ap.add_argument("--validation-config", default=None, help="Override validation session JSON used for artifact regression.")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else None
    validation_config = Path(args.validation_config).resolve() if args.validation_config else None
    report = run_regression(root=root, validation_config=validation_config)
    print(format_regression_report(report))
    return 0 if bool(report.get("ok")) else 3


if __name__ == "__main__":
    raise SystemExit(main())
