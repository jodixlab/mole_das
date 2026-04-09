"""Shared UI text registry for MOLE-DAS.

This module centralizes high-drift labels and notices that appear across the
Wizard, DAQ Runner, and exported artifacts.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Sequence


TEXT_INTAKE_POLICY_NOTE = (
    "Policy: If 'May Support Compliance' is enabled (Project -> Session Intent), "
    "this checklist must be complete (each item = Provided OR Not Provided + Reason) "
    "before Save+Apply and before DAQ Runner will start."
)
TEXT_INTAKE_COL_ITEM = "Item"
TEXT_INTAKE_COL_PROVIDED = "Provided"
TEXT_INTAKE_COL_NOT_PROVIDED = "Not Provided"
TEXT_INTAKE_COL_REASON = "Reason"

TEXT_FUEL_FLOW_UNITS = "Fuel flow units"
TEXT_O2_DRY_OPTIONAL = "O2 dry % (optional)"
TEXT_QD_DRY_DSCFH = "Qd dry (dscfh)"
TEXT_HEAT_INPUT_BASIS = "Heat input basis"
TEXT_DG_LIQUID_SHARE_SELECTED_HEAT_INPUT = "DG liquid share (% selected heat input)"

TEXT_DIAGNOSTICS_ONLY = "Diagnostics-only"
TEXT_DIAGNOSTICS_ONLY_UPPER = "DIAGNOSTICS-ONLY"
TEXT_DIAG_VERIFICATION = "Diagnostics Verification"
TEXT_DIAG_VERIFICATION_ATTESTATION = "Diagnostics Verification / Technician Attestation"
TEXT_DIAG_VERIFICATION_RECORD = "DIAGNOSTICS VERIFICATION RECORD"
TEXT_SESSION_SCHEMA_MIGRATION = "SESSION SCHEMA / MIGRATION"
TEXT_RUNNER_STATUS = "RUNNER STATUS"
TEXT_CALIBRATION_LINEARITY_CONDITION = "CALIBRATION / LINEARITY CONDITION OF USE"
TEXT_LIVE_POLLUTANTS = "LIVE POLLUTANTS"
TEXT_MASS_RATES_METHOD19_BASIS = "MASS RATES (METHOD 19 BASIS)"
TEXT_WEATHER_SITE_CONDITIONS = "WEATHER / SITE CONDITIONS"
TEXT_FUEL_METHOD19_BASIS = "FUEL / METHOD 19 BASIS"
TEXT_METHOD19_OPERATOR_INPUTS = "METHOD 19 OPERATOR INPUTS"
TEXT_METHOD19_DERIVED_OUTPUTS = "METHOD 19 DERIVED OUTPUTS"
TEXT_METHOD19_ROLLUP = "METHOD 19 ROLLUP"
TEXT_DIAG_NON_COMPLIANCE_NOTICE = (
    "Diagnostic output is non-compliance only and is excluded from QA/QC trending, "
    "report-pack generation, and institutional recordkeeping."
)
TEXT_DIAG_NOT_FOR_RECORD_NOTICE = (
    "NOT FOR COMPLIANCE SUPPORT, REPORT PACK, OR INSTITUTIONAL RECORD."
)


def with_colon(text: str) -> str:
    return f"{text}:"


def diag_limits_entered_text(limits_present: bool) -> str:
    return f"Project pollutant limits entered: {'YES' if limits_present else 'NO'}"


def diag_verification_gate_text(
    limits_present: bool,
    pretest_verified: bool,
    posttest_verified: bool,
) -> str:
    if not limits_present:
        return (
            "Verification gate: ADVISORY ONLY - no project pollutant limits are entered."
        )
    if not pretest_verified:
        return (
            "Verification gate: ACQUISITION BLOCKED - confirm pre-test verification "
            "before starting diagnostics acquisition."
        )
    if not posttest_verified:
        return (
            "Verification gate: ACQUISITION READY / EXPORT BLOCKED - confirm "
            "post-test verification before final diagnostics export."
        )
    return (
        "Verification gate: READY - pre-test and post-test verification are both "
        "documented."
    )


def wizard_runner_nav_label(mode: str, diagnostics_only: bool) -> str:
    mode_u = str(mode or "").strip().upper()
    if mode_u == "SIM":
        return f"DAQ Runner (SIM - {TEXT_DIAGNOSTICS_ONLY})" if diagnostics_only else "DAQ Runner (SIM)"
    return f"DAQ Runner (Test - {TEXT_DIAGNOSTICS_ONLY})" if diagnostics_only else "DAQ Runner (Test)"


def wizard_runner_launch_button_label(mode: str, diagnostics_only: bool) -> str:
    mode_u = str(mode or "").strip().upper()
    if mode_u == "SIM":
        return (
            f"Launch DAQ Runner (SIM - {TEXT_DIAGNOSTICS_ONLY})"
            if diagnostics_only
            else "Launch DAQ Runner (SIM / TRAINING)"
        )
    return (
        f"Launch DAQ Runner (TEST - {TEXT_DIAGNOSTICS_ONLY})"
        if diagnostics_only
        else "Launch DAQ Runner (TEST)"
    )


def runner_driver_status_text(
    driver_name: str,
    running: bool,
    comm_ok: object,
    diagnostics_only: bool,
) -> str:
    driver_name = str(driver_name or "(n/a)")
    if not running:
        return f"Driver: {driver_name} (stopped)"
    if comm_ok is True:
        return f"Driver: {driver_name} OK"
    if comm_ok is False:
        return f"Driver: {driver_name} {'ALERT' if diagnostics_only else 'FAIL'}"
    return f"Driver: {driver_name} ..."


def runner_comms_status_text(
    comm_ok: object,
    comm_note: str,
    diagnostics_only: bool,
    has_frame: bool,
) -> str:
    note = str(comm_note or "").strip()
    if comm_ok is True:
        return "Comms: OK"
    if comm_ok is False:
        suffix = f" | {note}" if note else ""
        return f"Comms: {'OFFLINE' if diagnostics_only else 'FAIL'}{suffix}"
    if has_frame:
        return "Comms: pending / no explicit comm flag yet"
    return "Comms: (no frames yet)"


def runner_acquisition_failed_text(diagnostics_only: bool) -> str:
    return "Acquisition: ERROR" if diagnostics_only else "Acquisition: FAILED"


def runner_acquisition_error_title(diagnostics_only: bool) -> str:
    return "Acquisition error" if diagnostics_only else "Acquisition failed"


def runner_site_refresh_status_text(diagnostics_only: bool) -> str:
    return "Status: SITE REFRESH ERROR" if diagnostics_only else "Status: SITE REFRESH FAILED"


def diag_mode_label(training: bool) -> str:
    return f"{TEXT_DIAGNOSTICS_ONLY_UPPER} TRAINING" if training else TEXT_DIAGNOSTICS_ONLY_UPPER


_TEXT_AUDIT_DUPLICATE_MIN_CHARS = 28
_TEXT_AUDIT_STALE_RULES = (
    (
        re.compile(r"\bDIAGNOSTIC ONLY\b", re.IGNORECASE),
        "Use 'Diagnostics-only' in the Wizard or 'DIAGNOSTICS-ONLY' in the Runner/artifacts.",
    ),
    (
        re.compile(r"\bDIAGNOSTIC TRAINING\b", re.IGNORECASE),
        "Use 'DIAGNOSTICS-ONLY TRAINING'.",
    ),
    (
        re.compile(r"Project pollutant limits present", re.IGNORECASE),
        "Use 'Project pollutant limits entered'.",
    ),
)
_TEXT_AUDIT_DIAGNOSTICS_FORBIDDEN_RULES = (
    (
        re.compile(r"\bFAIL(?:ED)?\b", re.IGNORECASE),
        "Diagnostics surfaces must avoid 'FAIL'/'FAILED'; use ALERT, OFFLINE, or ERROR unless the text is a formal limit exceedance statement.",
    ),
)


def _normalize_audit_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _entry_matches_text_audit_exemption(
    item: Dict[str, str],
    finding_type: str,
    exemptions: Sequence[Dict[str, Any]],
) -> bool:
    for raw in exemptions or ():
        types = raw.get("types")
        if types:
            allowed = {str(v or "").strip().upper() for v in (types if isinstance(types, (list, tuple, set)) else [types]) if str(v or "").strip()}
            if allowed and str(finding_type or "").strip().upper() not in allowed:
                continue
        surface = _normalize_audit_text(raw.get("surface") or "")
        if surface and surface.casefold() != str(item.get("surface") or "").casefold():
            continue
        source_contains = _normalize_audit_text(raw.get("source_contains") or "")
        if source_contains and source_contains.casefold() not in str(item.get("source") or "").casefold():
            continue
        text_exact = _normalize_audit_text(raw.get("text_exact") or "")
        if text_exact and text_exact.casefold() != str(item.get("text") or "").casefold():
            continue
        text_contains = _normalize_audit_text(raw.get("text_contains") or "")
        if text_contains and text_contains.casefold() not in str(item.get("text") or "").casefold():
            continue
        return True
    return False


def audit_ui_text_entries(
    entries: Sequence[Dict[str, Any]],
    diagnostics_only: bool = False,
    exemptions: Sequence[Dict[str, Any]] = (),
) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    normalized_entries: List[Dict[str, str]] = []
    duplicates: Dict[tuple[str, str], List[Dict[str, str]]] = defaultdict(list)

    for raw in entries or ():
        surface = _normalize_audit_text(raw.get("surface") or "")
        source = _normalize_audit_text(raw.get("source") or "")
        text = _normalize_audit_text(raw.get("text") or "")
        if not text:
            continue
        item = {"surface": surface or "UNSCOPED", "source": source or "(unknown)", "text": text}
        normalized_entries.append(item)
        if len(text) >= _TEXT_AUDIT_DUPLICATE_MIN_CHARS:
            duplicates[(item["surface"], text.casefold())].append(item)

        for pattern, message in _TEXT_AUDIT_STALE_RULES:
            if pattern.search(text):
                if _entry_matches_text_audit_exemption(item, "STALE", exemptions):
                    continue
                findings.append(
                    {
                        "type": "STALE",
                        "surface": item["surface"],
                        "source": item["source"],
                        "text": item["text"],
                        "message": message,
                    }
                )
        if diagnostics_only:
            for pattern, message in _TEXT_AUDIT_DIAGNOSTICS_FORBIDDEN_RULES:
                if pattern.search(text):
                    if _entry_matches_text_audit_exemption(item, "FORBIDDEN_DIAGNOSTICS", exemptions):
                        continue
                    findings.append(
                        {
                            "type": "FORBIDDEN_DIAGNOSTICS",
                            "surface": item["surface"],
                            "source": item["source"],
                            "text": item["text"],
                            "message": message,
                        }
                    )

    for (surface, _), items in duplicates.items():
        if len(items) < 2:
            continue
        sample = items[0]
        if _entry_matches_text_audit_exemption(sample, "DUPLICATE", exemptions):
            continue
        findings.append(
            {
                "type": "DUPLICATE",
                "surface": surface,
                "source": ", ".join(item["source"] for item in items[:4]),
                "text": sample["text"],
                "message": f"Repeated {len(items)} time(s) on the same surface.",
            }
        )

    findings.sort(key=lambda item: (str(item.get("surface") or ""), str(item.get("type") or ""), str(item.get("source") or "")))
    return {
        "entry_count": len(normalized_entries),
        "surface_count": len({item["surface"] for item in normalized_entries}),
        "findings": findings,
        "exemption_count": len(list(exemptions or [])),
    }


def format_ui_text_audit_report(title: str, report: Dict[str, Any]) -> str:
    findings = list(report.get("findings") or [])
    stale = [item for item in findings if str(item.get("type") or "") == "STALE"]
    forbidden = [item for item in findings if str(item.get("type") or "") == "FORBIDDEN_DIAGNOSTICS"]
    duplicates = [item for item in findings if str(item.get("type") or "") == "DUPLICATE"]
    lines = [
        str(title or "UI TEXT AUDIT").strip() or "UI TEXT AUDIT",
        "",
        f"Surfaces scanned: {int(report.get('surface_count') or 0)}",
        f"Text entries scanned: {int(report.get('entry_count') or 0)}",
        f"Explicit text exemptions: {int(report.get('exemption_count') or 0)}",
        f"Stale labels / phrases: {len(stale)}",
        f"Forbidden diagnostics terms: {len(forbidden)}",
        f"Duplicate long phrases: {len(duplicates)}",
        "",
    ]
    if findings:
        lines.append("Findings:")
        for item in findings:
            lines.append(
                f"  [{item.get('surface')}] {item.get('type')} | {item.get('source')} | {item.get('text')}"
            )
            lines.append(f"    {item.get('message')}")
    else:
        lines.extend(["Findings:", "  none"])
    lines.extend(
        [
            "",
            "Rule summary:",
            "  - flags legacy diagnostics wording",
            "  - flags FAIL/FAILED on diagnostics surfaces",
            "  - flags repeated long phrases on the same surface",
        ]
    )
    return "\n".join(lines)
