"""Evidence helpers for starter spec-engine evaluations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .schemas import EvidenceRecord, SPEC_ENGINE_FORMULA_VERSION


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def build_evidence_record(
    step: Any,
    inputs: Any,
    outputs: Any,
    result: Any,
    *,
    channel: Any = None,
    timestamp: Any = None,
    event: str = "STEP_EVAL",
    formula_version: str = SPEC_ENGINE_FORMULA_VERSION,
) -> Dict[str, Any]:
    result_dict = dict(result or {})
    record = EvidenceRecord(
        event=str(event or "STEP_EVAL"),
        step=str(result_dict.get("step") or step or ""),
        channel=str(channel or result_dict.get("details", {}).get("channel") or ""),
        timestamp=str(timestamp or _iso_now()),
        formula_version=str(formula_version or SPEC_ENGINE_FORMULA_VERSION),
        inputs=dict(inputs or {}),
        outputs=dict(outputs or {}),
        result=result_dict,
    )
    return record.to_dict()
