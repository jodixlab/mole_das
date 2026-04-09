"""FTIR method-specific workstep templates.

This module provides a light, auditable checklist layer for FTIR audit work.
It does not replace the primary gas QA/QC worksteps already present in the
runner; instead it adds method-specific operator checkpoints when the FTIR
audit/reference module is enabled.
"""

from __future__ import annotations

from typing import Any, Dict, List


METHOD_ASTM_D6348_12 = "ASTM_D6348_12"
METHOD_ASTM_D6348_03 = "ASTM_D6348_03"
METHOD_EPA_320 = "EPA_METHOD_320"
METHOD_PS15 = "PERFORMANCE_SPEC_15"
DEFAULT_METHOD = METHOD_ASTM_D6348_12


METHODS: Dict[str, Dict[str, Any]] = {
    METHOD_ASTM_D6348_12: {
        "label": "ASTM D6348-12",
        "summary": "Extractive FTIR field test emphasizing interface equilibration, background acquisition, full-system zero, CTS pathlength verification, mechanical and equilibration response checks, analyte spiking, and post-spike zero recovery.",
        "basis": "ASTM D6348-12e1 Sections 4.3, 11.2-11.4 and Annex A2-A7, especially the Annex A4 pre-test workflow and Annex A5 spiking technique.",
        "steps": [
            {
                "id": "PLAN_REVIEW",
                "label": "Confirm source-specific FTIR plan",
                "criterion": "Target analytes, interferents, DQOs, and reference spectra are confirmed before field work.",
            },
            {
                "id": "INTERFACE_EQ_BACKGROUND_PRE",
                "label": "Equilibrate interface and acquire background spectrum",
                "criterion": "Allow the sample interface to equilibrate and collect the background/Io spectrum before any sample, zero, or spike analysis.",
            },
            {
                "id": "SYSTEM_ZERO_PRE",
                "label": "Run pretest system zero",
                "criterion": "Nitrogen or zero gas is pulled through the entire sampling system and no contamination or leak indicators remain.",
            },
            {
                "id": "CTS_PATHLENGTH_PRE",
                "label": "Verify CTS pathlength",
                "criterion": "Use the CTS to verify sample-cell pathlength before field sampling; the pathlength check remains within the expected acceptance band.",
            },
            {
                "id": "MECH_RESPONSE_PRE",
                "label": "Run mechanical response time check",
                "criterion": "Document the system mechanical response time as part of the pre-test FTIR performance verification.",
            },
            {
                "id": "EQUIL_RESPONSE_PRE",
                "label": "Run equilibration response check",
                "criterion": "Measure the equilibration response using the most reactive or adsorptive target analyte and document the response stabilization time.",
            },
            {
                "id": "SPIKE_RECOVERY",
                "label": "Perform analyte spike / recovery check",
                "criterion": "Spike recovery is documented against the project DQO or stated acceptance basis; the spike concentration should approximate native effluent within about 50% when practicable.",
            },
            {
                "id": "SYSTEM_ZERO_POST_SPIKE",
                "label": "Run post-spike system zero",
                "criterion": "After spike exposure, rerun the full-system zero until analytes are absent or have decreased by at least 95% from the spiked level.",
            },
            {
                "id": "TEST_RUN",
                "label": "Collect FTIR test run",
                "criterion": "Collect the FTIR test run per the field plan after the pre-test checks and post-spike zero recovery are complete.",
            },
            {
                "id": "CTS_POST",
                "label": "Run post-test CTS / pathlength verification",
                "criterion": "Post-test CTS or pathlength verification confirms the sample cell remains within the acceptance expectation established in the plan.",
            },
            {
                "id": "POST_REVIEW",
                "label": "Review ASTM D6348-12 evidence package",
                "criterion": "Review the pre-test checks, spike recovery, post-spike zero, CTS evidence, and archived spectra before closing the FTIR audit.",
            },
        ],
    },
    METHOD_EPA_320: {
        "label": "EPA Method 320",
        "summary": "EPA FTIR stack method emphasizing background acquisition, CTS checks, response-time determination, native sampling, and spiked bias/recovery verification.",
        "basis": "EPA Method 320 Sections 8.6.1-8.6.3 and 9.1-9.2.6.",
        "steps": [
            {
                "id": "BACKGROUND_PRE",
                "label": "Acquire background spectrum",
                "criterion": "Background spectrum is collected before native or spiked effluent samples are analyzed.",
            },
            {
                "id": "CTS_PRE",
                "label": "Verify sample-cell pathlength with CTS",
                "criterion": "CTS/pathlength agrees within 5% of the most recent reference value.",
            },
            {
                "id": "RESPONSE_TIME",
                "label": "Determine FTIR response time",
                "criterion": "Use 2x measured response time or 2 minutes, whichever is greater, before collecting stabilized spiked samples.",
            },
            {
                "id": "NATIVE_SAMPLE",
                "label": "Collect native effluent samples",
                "criterion": "Unspiked effluent concentrations are characterized before the bias check.",
            },
            {
                "id": "SPIKE_RECOVERY",
                "label": "Run sampling-system bias / spike recovery",
                "criterion": "At least 3 independent spiked samples are collected after equilibration; the correction factor should fall within 0.70-1.30 (70-130%).",
            },
            {
                "id": "TEST_RUN",
                "label": "Collect FTIR method run(s)",
                "criterion": "Independent FTIR samples are collected and archived according to the test plan.",
            },
            {
                "id": "DATA_REVIEW",
                "label": "Review Method 320 bias results",
                "criterion": "Any out-of-range spike recovery is corrected or clearly qualified in the run record/report.",
            },
        ],
    },
    METHOD_PS15: {
        "label": "Performance Specification 15",
        "summary": "FTIR CEMS-style qualification framework emphasizing daily system audits, qualification-path selection, validation or reference-method comparison data, and recurring QA.",
        "basis": "40 CFR Part 60, Appendix B, Performance Specification 15 Sections 8.3, 13.2, 13.3 and 13.4.",
        "steps": [
            {
                "id": "SYSTEM_AUDIT_PRE",
                "label": "Run daily system audit precheck",
                "criterion": "Before data collection, verify the CTS is within 5% of the reference and confirm the daily audit sample path is ready.",
            },
            {
                "id": "AUDIT_SAMPLE",
                "label": "Analyze daily audit sample",
                "criterion": "Analyze the audit sample within the 24-hour audit window and confirm the reported concentration is within the PS 15 daily audit acceptance band.",
            },
            {
                "id": "BIAS_CHECK",
                "label": "Perform sampling-system bias test",
                "criterion": "Probe-point or equivalent audit spike/bias check is completed and documented before qualification data are accepted.",
            },
            {
                "id": "QUAL_PATH",
                "label": "Document PS 15 qualification path",
                "criterion": "Document whether this project is using validation spectra or paired reference-method runs to demonstrate PS 15 performance.",
            },
            {
                "id": "VALIDATION_DATA",
                "label": "Collect validation data set",
                "criterion": "If using validation, capture the required spiked and unspiked spectra set across the operating range and evaluate it against the PS 15 acceptance tables.",
            },
            {
                "id": "RM_COMPARISON",
                "label": "Collect paired reference-method runs",
                "criterion": "If using the RM comparison path, collect the required paired FTIR-versus-reference runs; PS 15 requires a minimum of 9 runs for that path.",
            },
            {
                "id": "DAILY_QA",
                "label": "Record daily operational QA",
                "criterion": "Daily or operating-period QA checks remain logged at least every 24 hours while the FTIR audit/CEMS workflow is active.",
            },
            {
                "id": "POST_REVIEW",
                "label": "Review PS 15 qualification results",
                "criterion": "Disposition bias, validation or RM-comparison results, and daily audit evidence before closing the FTIR audit.",
            },
        ],
    },
}


def normalize_method(value: Any) -> str:
    raw = str(value or "").strip()
    if raw in METHODS:
        return raw
    upper = raw.upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "ASTM_D6348": METHOD_ASTM_D6348_12,
        "ASTM_D6348_03": METHOD_ASTM_D6348_12,
        "ASTM_D6348_12": METHOD_ASTM_D6348_12,
        "ASTM_D6348_12E1": METHOD_ASTM_D6348_12,
        "D6348": METHOD_ASTM_D6348_12,
        "EPA_METHOD_320": METHOD_EPA_320,
        "METHOD_320": METHOD_EPA_320,
        "EPA_320": METHOD_EPA_320,
        "320": METHOD_EPA_320,
        "PERFORMANCE_SPEC_15": METHOD_PS15,
        "PS15": METHOD_PS15,
        "PS_15": METHOD_PS15,
        "PERFORMANCE_SPECIFICATION_15": METHOD_PS15,
    }
    return aliases.get(upper, DEFAULT_METHOD)


def method_display_label(value: Any) -> str:
    return str((METHODS.get(normalize_method(value)) or {}).get("label") or METHODS[DEFAULT_METHOD]["label"])


def method_codes() -> List[str]:
    return list(METHODS.keys())


def method_display_labels() -> List[str]:
    return [METHODS[code]["label"] for code in method_codes()]


def code_from_display(value: Any) -> str:
    raw = str(value or "").strip()
    for code, meta in METHODS.items():
        if raw == str(meta.get("label") or ""):
            return code
    return normalize_method(raw)


def method_meta(value: Any) -> Dict[str, Any]:
    code = normalize_method(value)
    meta = METHODS.get(code) or METHODS[DEFAULT_METHOD]
    return {
        "code": code,
        "label": str(meta.get("label") or ""),
        "summary": str(meta.get("summary") or ""),
        "basis": str(meta.get("basis") or ""),
        "steps": [dict(step) for step in (meta.get("steps") or []) if isinstance(step, dict)],
    }
