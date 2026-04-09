"""Shared post-cal carry-forward policy matrix and provenance helpers."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence


POSTCAL_POLICY_MATRIX_VERSION = "v1"


def policy_token(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


DEFAULT_POSTCAL_POLICY_MATRIX: List[Dict[str, Any]] = [
    {
        "id": "epa_method_manual_only",
        "priority": 10,
        "when": {
            "method_prefixes": ["EPA_"],
        },
        "policy_mode": "MANUAL_ONLY",
        "allow_auto_promote": False,
        "reason": "{display_method} keeps post-run bias/drift in validation/manual-adjustment mode.",
    },
    {
        "id": "astm_d6522_or_default_diag_flag_auto_zero",
        "priority": 20,
        "when": {
            "astm_d6522_or_default": True,
            "diagnostic_only": True,
        },
        "policy_mode": "AUTO_ZERO_ONLY",
        "allow_auto_promote": True,
        "reason": "{display_method} allows zero-based additive carry-forward after completed post-cal.",
    },
    {
        "id": "astm_d6522_or_default_diag_track_auto_zero",
        "priority": 21,
        "when": {
            "astm_d6522_or_default": True,
            "track_in": ["DIAG", "PROJECT"],
        },
        "policy_mode": "AUTO_ZERO_ONLY",
        "allow_auto_promote": True,
        "reason": "{display_method} allows zero-based additive carry-forward after completed post-cal.",
    },
    {
        "id": "astm_d6522_or_default_diag_session_auto_zero",
        "priority": 22,
        "when": {
            "astm_d6522_or_default": True,
            "session_mode_in": ["DIAGNOSTICS_SESSION"],
        },
        "policy_mode": "AUTO_ZERO_ONLY",
        "allow_auto_promote": True,
        "reason": "{display_method} allows zero-based additive carry-forward after completed post-cal.",
    },
    {
        "id": "astm_d6522_or_default_manual_elsewhere",
        "priority": 29,
        "when": {
            "astm_d6522_or_default": True,
        },
        "policy_mode": "MANUAL_ONLY",
        "allow_auto_promote": False,
        "reason": "{display_method} is active outside diagnostic/project workflow; keep carry-forward manual.",
    },
    {
        "id": "diagnostic_only_without_explicit_method_auto_zero",
        "priority": 40,
        "when": {
            "diagnostic_only": True,
            "may_support_compliance": False,
            "method_effective_empty": True,
        },
        "policy_mode": "AUTO_ZERO_ONLY",
        "allow_auto_promote": True,
        "reason": "Diagnostic-only session without an explicit EPA method may carry forward zero-based additive drift.",
    },
]


def policy_context_from_session(session: Dict[str, Any], code: Any) -> Dict[str, Any]:
    code_u = policy_token(code)
    qa = (session.get("qa_qc") or {}) if isinstance(session, dict) else {}
    sm = (session.get("session_mode") or {}) if isinstance(session, dict) else {}
    poll = (session.get("pollutants") or {}) if isinstance(session, dict) else {}
    resolved = poll.get("resolved") if isinstance(poll.get("resolved"), dict) else {}
    resolved_by = resolved.get("resolved_by_analyte") if isinstance(resolved.get("resolved_by_analyte"), dict) else {}
    method_map = resolved.get("method_map") if isinstance(resolved.get("method_map"), dict) else (qa.get("method_map") if isinstance(qa.get("method_map"), dict) else {})
    profile_map = resolved.get("profile_map") if isinstance(resolved.get("profile_map"), dict) else (qa.get("profile_map") if isinstance(qa.get("profile_map"), dict) else {})
    row = resolved_by.get(code_u) if isinstance(resolved_by.get(code_u), dict) else {}
    return {
        "code": code_u,
        "track": policy_token(resolved.get("track") or qa.get("track")),
        "session_mode_name": policy_token(sm.get("mode") or ""),
        "diagnostic_only": bool(sm.get("diagnostic_only")),
        "may_support_compliance": bool(sm.get("may_support_compliance")),
        "method_effective": policy_token(row.get("method_effective") or ((method_map or {}).get(code_u) if isinstance(method_map, dict) else "")),
        "method_selected": policy_token(row.get("method_selected")),
        "method_recommended": policy_token(row.get("method_recommended")),
        "profile_id": policy_token(row.get("profile_id") or ((profile_map or {}).get(code_u) if isinstance(profile_map, dict) else "")),
    }


def _astm_d6522_or_default(ctx: Dict[str, Any]) -> bool:
    method_effective = str(ctx.get("method_effective") or "")
    profile_id = str(ctx.get("profile_id") or "")
    return bool(method_effective == "ASTM_D6522" or ((not method_effective) and profile_id == "PROFILE:DEFAULT"))


def _rule_matches(ctx: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    when = rule.get("when") if isinstance(rule.get("when"), dict) else {}
    if not when:
        return True

    method_effective = str(ctx.get("method_effective") or "")
    profile_id = str(ctx.get("profile_id") or "")
    track = str(ctx.get("track") or "")
    session_mode_name = str(ctx.get("session_mode_name") or "")

    prefixes = when.get("method_prefixes")
    if isinstance(prefixes, (list, tuple, set)) and prefixes:
        if not any(method_effective.startswith(str(prefix or "")) for prefix in prefixes):
            return False

    values = when.get("method_in")
    if isinstance(values, (list, tuple, set)) and values:
        if method_effective not in {policy_token(value) for value in values}:
            return False

    values = when.get("profile_in")
    if isinstance(values, (list, tuple, set)) and values:
        if profile_id not in {policy_token(value) for value in values}:
            return False

    values = when.get("track_in")
    if isinstance(values, (list, tuple, set)) and values:
        if track not in {policy_token(value) for value in values}:
            return False

    values = when.get("session_mode_in")
    if isinstance(values, (list, tuple, set)) and values:
        if session_mode_name not in {policy_token(value) for value in values}:
            return False

    if "diagnostic_only" in when and bool(ctx.get("diagnostic_only")) != bool(when.get("diagnostic_only")):
        return False

    if "may_support_compliance" in when and bool(ctx.get("may_support_compliance")) != bool(when.get("may_support_compliance")):
        return False

    if "method_effective_empty" in when:
        is_empty = (not bool(method_effective))
        if is_empty != bool(when.get("method_effective_empty")):
            return False

    if "astm_d6522_or_default" in when:
        if _astm_d6522_or_default(ctx) != bool(when.get("astm_d6522_or_default")):
            return False

    return True


def evaluate_postcal_carry_forward_policy(
    ctx: Dict[str, Any],
    rules: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    ctx_norm = {
        "code": policy_token(ctx.get("code")),
        "track": policy_token(ctx.get("track")),
        "session_mode_name": policy_token(ctx.get("session_mode_name")),
        "diagnostic_only": bool(ctx.get("diagnostic_only")),
        "may_support_compliance": bool(ctx.get("may_support_compliance")),
        "method_effective": policy_token(ctx.get("method_effective")),
        "method_selected": policy_token(ctx.get("method_selected")),
        "method_recommended": policy_token(ctx.get("method_recommended")),
        "profile_id": policy_token(ctx.get("profile_id")),
    }
    display_method = str(ctx_norm.get("method_effective") or ctx_norm.get("profile_id") or "UNSPECIFIED_METHOD")
    ordered_rules = sorted(list(rules or DEFAULT_POSTCAL_POLICY_MATRIX), key=lambda item: int(item.get("priority") or 9999))
    for rule in ordered_rules:
        if not _rule_matches(ctx_norm, rule):
            continue
        return {
            **ctx_norm,
            "policy_mode": str(rule.get("policy_mode") or "MANUAL_ONLY"),
            "allow_auto_promote": bool(rule.get("allow_auto_promote")),
            "reason": str(rule.get("reason") or "").format(display_method=display_method),
            "display_method": display_method,
            "policy_rule_id": str(rule.get("id") or ""),
            "policy_matrix_version": POSTCAL_POLICY_MATRIX_VERSION,
        }
    return {
        **ctx_norm,
        "policy_mode": "MANUAL_ONLY",
        "allow_auto_promote": False,
        "reason": f"No auto carry-forward rule is defined for {display_method}; keep carry-forward manual.",
        "display_method": display_method,
        "policy_rule_id": "fallback_manual_only",
        "policy_matrix_version": POSTCAL_POLICY_MATRIX_VERSION,
    }


def postcal_carry_forward_policy(session: Dict[str, Any], code: Any) -> Dict[str, Any]:
    return evaluate_postcal_carry_forward_policy(policy_context_from_session(session, code))


def collect_postcal_reviews(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    daq = session.get("daq_runner") if isinstance(session.get("daq_runner"), dict) else {}
    ws = daq.get("worksteps") if isinstance(daq.get("worksteps"), dict) else {}
    ws_q = ws.get("qaqc") if isinstance(ws.get("qaqc"), dict) else {}
    post_runs = ws_q.get("post_runs") if isinstance(ws_q.get("post_runs"), dict) else {}
    rows: List[Dict[str, Any]] = []
    for run_key, prun in post_runs.items():
        if not isinstance(prun, dict):
            continue
        try:
            run_no = int(str(run_key))
        except Exception:
            continue
        review = prun.get("operator_review") if isinstance(prun.get("operator_review"), dict) else {}
        if not review:
            continue
        rows.append({
            "run_no": int(run_no),
            "overall_pass": bool(review.get("overall_pass")),
            "postcal_health": str(review.get("postcal_health") or prun.get("postcal_health") or "").strip().upper(),
            "headline": str(review.get("headline") or "").strip(),
            "message": str(review.get("message") or "").strip(),
            "promoted_codes": [str(code).strip().upper() for code in list(review.get("promoted_codes") or []) if str(code).strip()],
            "manual_only_codes": [str(code).strip().upper() for code in list(review.get("manual_only_codes") or []) if str(code).strip()],
            "invalidated_codes": [str(code).strip().upper() for code in list(review.get("invalidated_codes") or []) if str(code).strip()],
            "suspended_codes": [str(code).strip().upper() for code in list(review.get("suspended_codes") or []) if str(code).strip()],
            "row_count": len(list(review.get("rows") or [])),
        })
    rows.sort(key=lambda row: int(row.get("run_no") or 0), reverse=True)
    return rows


def collect_postcal_history(
    session: Dict[str, Any],
    *,
    code_name: Any = "",
    units_lookup: Optional[Callable[[Dict[str, Any], str], str]] = None,
) -> List[Dict[str, Any]]:
    daq = session.get("daq_runner") if isinstance(session.get("daq_runner"), dict) else {}
    ws = daq.get("worksteps") if isinstance(daq.get("worksteps"), dict) else {}
    ws_q = ws.get("qaqc") if isinstance(ws.get("qaqc"), dict) else {}
    post_runs = ws_q.get("post_runs") if isinstance(ws_q.get("post_runs"), dict) else {}
    code_filter = policy_token(code_name)
    rows: List[Dict[str, Any]] = []
    for run_key, prun in post_runs.items():
        if not isinstance(prun, dict):
            continue
        try:
            run_no = int(str(run_key))
        except Exception:
            continue
        review = prun.get("operator_review") if isinstance(prun.get("operator_review"), dict) else {}
        policy_by = prun.get("auto_apply_policy_by_channel") if isinstance(prun.get("auto_apply_policy_by_channel"), dict) else {}
        promoted = prun.get("auto_promoted_adjustments") if isinstance(prun.get("auto_promoted_adjustments"), dict) else {}
        suspended = prun.get("auto_suspended_adjustments") if isinstance(prun.get("auto_suspended_adjustments"), dict) else {}
        skipped = prun.get("auto_skipped_adjustments") if isinstance(prun.get("auto_skipped_adjustments"), dict) else {}
        ch_valid = prun.get("channel_valid") if isinstance(prun.get("channel_valid"), dict) else {}
        code_keys = set()
        code_keys.update(policy_token(k) for k in policy_by.keys())
        code_keys.update(policy_token(k) for k in promoted.keys())
        code_keys.update(policy_token(k) for k in suspended.keys())
        code_keys.update(policy_token(k) for k in skipped.keys())
        code_keys.update(policy_token(k) for k in ch_valid.keys())
        if code_filter:
            code_keys = {code_filter} if code_filter in code_keys else set()
        for pollutant in sorted(c for c in code_keys if c):
            policy = policy_by.get(pollutant) if isinstance(policy_by.get(pollutant), dict) else {}
            promoted_rec = promoted.get(pollutant) if isinstance(promoted.get(pollutant), dict) else {}
            suspended_rec = suspended.get(pollutant) if isinstance(suspended.get(pollutant), dict) else {}
            skipped_rec = skipped.get(pollutant) if isinstance(skipped.get(pollutant), dict) else {}
            passed = ch_valid.get(pollutant)
            event = ""
            detail = ""
            reason = ""
            bias = None
            drift_per_hr = None
            eff_run = None
            source_run = None
            if promoted_rec:
                event = "PROMOTED"
                bias = promoted_rec.get("bias")
                drift_per_hr = promoted_rec.get("drift_per_hr")
                eff_run = promoted_rec.get("effective_after_run_no")
                detail = f"bias={_fmt_num_or_blank(bias)}, drift/hr={_fmt_num_or_blank(drift_per_hr)}, effective after Run {eff_run}"
            elif suspended_rec:
                event = str(suspended_rec.get("status") or "SUSPENDED").strip().upper() or "SUSPENDED"
                source_run = suspended_rec.get("source_run_no")
                if source_run not in (None, ""):
                    detail = f"source run {source_run}"
                reason = str(suspended_rec.get("reason") or "").strip()
            elif skipped_rec:
                event = str(skipped_rec.get("status") or "MANUAL_ONLY").strip().upper() or "MANUAL_ONLY"
                detail = "auto carry-forward skipped"
                reason = str(skipped_rec.get("reason") or "").strip()
            elif passed is False:
                event = "INVALIDATED"
                reason = "Post-cal failed for this pollutant."
            if not event:
                continue
            if not reason:
                reason = str(policy.get("reason") or "").strip()
            try:
                units = str(units_lookup(session, pollutant) or "").strip() if callable(units_lookup) else ""
            except Exception:
                units = ""
            rows.append({
                "run_no": int(run_no),
                "pollutant": pollutant,
                "units": units,
                "event": event,
                "pass": (None if passed is None else bool(passed)),
                "policy_mode": str(policy.get("mode") or policy.get("policy_mode") or "").strip().upper(),
                "method_effective": str(policy.get("method_effective") or "").strip(),
                "profile_id": str(policy.get("profile_id") or "").strip(),
                "track": str(policy.get("track") or "").strip(),
                "policy_rule_id": str(policy.get("policy_rule_id") or "").strip(),
                "policy_matrix_version": str(policy.get("policy_matrix_version") or "").strip(),
                "bias": bias,
                "drift_per_hr": drift_per_hr,
                "effective_after_run_no": eff_run,
                "source_run_no": source_run,
                "detail": detail,
                "reason": reason,
                "review_headline": str(review.get("headline") or "").strip(),
                "review_overall_pass": (None if not review else bool(review.get("overall_pass"))),
                "postcal_health": str(review.get("postcal_health") or prun.get("postcal_health") or "").strip().upper(),
            })
    rows.sort(key=lambda row: (int(row.get("run_no") or 0), str(row.get("pollutant") or "")), reverse=True)
    return rows


def _fmt_num_or_blank(value: Any) -> str:
    try:
        return f"{float(value):.6f}"
    except Exception:
        return ""


__all__ = [
    "POSTCAL_POLICY_MATRIX_VERSION",
    "DEFAULT_POSTCAL_POLICY_MATRIX",
    "policy_token",
    "policy_context_from_session",
    "evaluate_postcal_carry_forward_policy",
    "postcal_carry_forward_policy",
    "collect_postcal_reviews",
    "collect_postcal_history",
]
