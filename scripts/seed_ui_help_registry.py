from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "config" / "mole_ui_help_registry_v1.json"


def _refs(*items: tuple[str, str]) -> list[dict[str, str]]:
    return [{"doc_label": doc_label, "section": section} for doc_label, section in items]


SEED_ENTRIES = {
    "wizard.session_intent.record_data": {
        "label": "Record Data",
        "short_description": "Controls whether the session is intended to capture a recorded evidence stream instead of functioning only as a transient setup shell.",
        "definition": "Recorded sessions preserve project evidence under the MOLE DAS data root and support downstream export and reporting paths when the rest of the session posture allows them.",
        "process_note": "Enable this for normal formal testing and comparison work. Leave it off only for limited configuration or simulation cases where no recorded field evidence is intended.",
        "doc_refs": _refs(
            ("MOLE DAS Technical and Operating Manual", "4.1 Wizard-first workflow"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "Required Tabs by Scenario Matrix"),
        ),
    },
    "wizard.session_intent.tokenize": {
        "label": "Tokenize",
        "short_description": "Keeps the session on the standard packaged project/session structure used by the current runtime.",
        "definition": "Tokenized sessions follow the MOLE DAS session packaging model and preserve structured artifacts beneath the session root.",
        "process_note": "Use the default packaged session model for ordinary project execution. This should remain on unless a controlled engineering exception exists.",
        "doc_refs": _refs(
            ("MOLE DAS Technical and Operating Manual", "2.3 Data and evidence root"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "Standard Recorded Test - No FTIR"),
        ),
    },
    "wizard.session_intent.diagnostics_only": {
        "label": "Diagnostics-only",
        "short_description": "Routes DAQ Runner launch into the diagnostics-only shell and disables compliance support.",
        "definition": "Diagnostics-only is a session-intent flag for neutral diagnostic work that is intentionally outside the formal compliance-support and institutional-record path.",
        "process_note": "Use this only for diagnostics, troubleshooting, or training shells. When enabled, formal compliance support is turned off automatically.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Diagnostics-only"),
            ("MOLE DAS Technical and Operating Manual", "4.2 Session-intent policy"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "Diagnostics-only Test"),
        ),
    },
    "wizard.session_intent.may_support_compliance": {
        "label": "May Support Compliance",
        "short_description": "Marks the session posture as potentially supporting formal project execution and formal downstream QA/QC and reporting.",
        "definition": "Compliance support is the session posture in which the formal runner and downstream report features are intended to support formal project execution.",
        "process_note": "Use this when the session may contribute to a formal project deliverable. It is mutually exclusive with Diagnostics-only.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Compliance support"),
            ("MOLE DAS Technical and Operating Manual", "4.2 Session-intent policy"),
        ),
    },
    "wizard.validation.session_type": {
        "label": "Session Type",
        "short_description": "Defines the top-level project/testing posture before the Runner starts.",
        "definition": "The validation plan session type determines whether the project is a standard test, validation package, or other planned workflow branch.",
        "process_note": "Set this before Save + Apply so downstream FTIR validation and report-builder logic inherits the right plan context.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Validation Test Plan"),
            ("MOLE FTIR Method 301 Experiment Protocol", "Scope and Objectives"),
        ),
    },
    "wizard.validation.mode": {
        "label": "Validation Mode",
        "short_description": "Defines whether the planned comparison is a formal Method 301 workflow, an informed comparison, or no validation workflow.",
        "definition": "Validation mode determines how the project should interpret comparison-set structure, review gates, and final acceptance language.",
        "process_note": "Use formal mode only when the project intends to satisfy the required comparison-set structure. Otherwise use the informed comparison posture.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Acceptance Criteria"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR formal Method 301 comparison"),
        ),
    },
    "wizard.validation.comparator_method": {
        "label": "Comparator Method",
        "short_description": "Identifies the comparator method or validated reference method used by the planned validation package.",
        "definition": "For FTIR side-by-side work this is the method basis applied to the comparator dataset and the resulting report language.",
        "process_note": "Set the comparator method explicitly so the report and review package carry the right basis statement.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Terms and Definitions"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR Side-by-Side Informed Comparison"),
        ),
    },
    "wizard.validation.vendor_profile": {
        "label": "FTIR Vendor Profile",
        "short_description": "Selects the FTIR import adapter profile used to interpret comparator exports.",
        "definition": "Vendor profiles apply file-shape, timestamp, and analyte-header assumptions for supported FTIR export formats.",
        "process_note": "Choose the explicit vendor profile when known. Use AUTO only when the export shape is stable and the adapter can resolve it reliably.",
        "doc_refs": _refs(
            ("MOLE DAS Technical and Operating Manual", "2.2 DAQ Runner"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR / validation-specific tabs and sections"),
        ),
    },
    "wizard.validation.master_clock": {
        "label": "Timestamp Master Clock",
        "short_description": "Defines the authoritative time basis used to align MOLE and comparator records.",
        "definition": "The timestamp master clock is the authoritative clock used to align raw and processed records during side-by-side comparison.",
        "process_note": "Set this before acquisition so post-processing alignment, review, and report text use a single declared time basis.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Terms and Definitions"),
            ("MOLE FTIR Method 301 Experiment Protocol", "Post-processing and timestamp alignment"),
        ),
    },
    "wizard.validation.planned_sets": {
        "label": "Planned Sets",
        "short_description": "Stores the planned number of comparison sets for the validation execution plan.",
        "definition": "Comparison sets are the structured units used for FTIR/MOLE side-by-side review and statistical interpretation.",
        "process_note": "Populate this with the intended project plan so the Runner execution planner can measure planned versus completed sets.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Recommended 3-hour run structure"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR formal Method 301 comparison"),
        ),
    },
    "wizard.validation.run_minutes": {
        "label": "Run Minutes",
        "short_description": "Defines the planned comparison-window duration for each test run.",
        "definition": "Run minutes establishes the intended capture interval used in comparison-set planning and cadence review.",
        "process_note": "For the current field design this is typically 20 minutes for FTIR side-by-side comparison blocks.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Recommended schedule within one 3-hour FTIR run"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR formal Method 301 comparison"),
        ),
    },
    "wizard.validation.purge_minutes": {
        "label": "Purge Minutes",
        "short_description": "Defines the planned purge interval between comparison windows.",
        "definition": "The purge interval is the non-comparison period used to clear the sampling path between comparison windows.",
        "process_note": "For the current side-by-side field plan this is typically 5 minutes between 20-minute test windows.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Terms and Definitions"),
            ("MOLE FTIR Method 301 Experiment Protocol", "Recommended schedule within one 3-hour FTIR run"),
        ),
    },
    "wizard.fuel.category": {
        "label": "Fuel Category",
        "short_description": "Classifies the project fuel basis used for downstream analysis defaults and fuel-analysis expectations.",
        "definition": "Fuel category determines the expected fuel-analysis profile family and the assumptions carried into fuel and crosswalk logic.",
        "process_note": "Choose the category that matches the project source fuel. This should be stable before Save + Apply.",
        "doc_refs": _refs(
            ("MOLE DAS Technical and Operating Manual", "4.1 Wizard-first workflow"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "Fuel Analysis"),
        ),
    },
    "wizard.qaqc.method": {
        "label": "Resolved Profile (from Pollutants)",
        "short_description": "Shows the effective QA/QC profile resolved from the selected pollutant and workflow posture.",
        "definition": "The resolved QA/QC profile is the active method/profile selection currently driving calibration, linearity, and related workstep expectations.",
        "process_note": "This is a read-only result of the current pollutant and workflow state. Review it before acquisition or report generation.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Diagnostics Verification"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "QA/QC"),
        ),
    },
    "wizard.reference_ftir.enable_ingest": {
        "label": "Enable MG2000 FTIR ingest",
        "short_description": "Turns on MG2000 FTIR PRN parsing as an optional reference or audit evidence stream.",
        "definition": "Reference FTIR ingest is the packaged FTIR file-ingest path used for reference or audit evidence in the Wizard and formal runner context.",
        "process_note": "Enable this only when the project includes a supported MG2000 reference/audit stream and the pathing is ready.",
        "doc_refs": _refs(
            ("MOLE DAS Technical and Operating Manual", "2.2 DAQ Runner"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR Reference / Audit Companion Workflow"),
        ),
    },
    "wizard.reference_ftir.provider": {
        "label": "Provider",
        "short_description": "Identifies the packaged FTIR ingest provider profile.",
        "definition": "The provider determines how the project interprets the incoming FTIR reference file family.",
        "process_note": "Leave this on the supported MG2000 provider unless the packaged ingest layer is extended intentionally.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Reference / Audit FTIR"),
        ),
    },
    "wizard.reference_ftir.role": {
        "label": "Role",
        "short_description": "Declares whether the FTIR stream is being used as audit evidence or a general reference stream.",
        "definition": "Role changes how the workflow interprets the FTIR contribution to worksteps and report language.",
        "process_note": "Use AUDIT when the FTIR stream is part of a comparison or audit record. Use REFERENCE for a lighter observational companion path.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR Reference / Audit Companion Workflow"),
        ),
    },
    "wizard.reference_ftir.file_pattern": {
        "label": "Pattern",
        "short_description": "Limits which FTIR files are included when the configured path points at a folder.",
        "definition": "The file pattern is the filename filter applied to the FTIR ingest folder scan.",
        "process_note": "Use this to restrict ingest to the intended PRN file family when the folder contains unrelated exports.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Reference / Audit FTIR"),
        ),
    },
    "wizard.reference_ftir.freshness_s": {
        "label": "Freshness (s)",
        "short_description": "Defines how stale an FTIR file update may be before the ingest path considers it out of date.",
        "definition": "Freshness is the allowable age threshold for the active FTIR file update stream.",
        "process_note": "Use a short threshold for live audit/reference use so stale FTIR files are not mistaken for current evidence.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Reference / Audit FTIR"),
        ),
    },
    "runner.ftir.enable_package": {
        "label": "Enable FTIR validation package",
        "short_description": "Turns on the FTIR side-by-side validation package inside the formal Report Builder.",
        "definition": "The FTIR validation package controls import, alignment, comparison-set review, lock/signoff, and FTIR appendix generation.",
        "process_note": "Enable this only for projects that need the FTIR comparison package carried into the final deliverable.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder -> FTIR Side-by-Side Validation"),
            ("MOLE FTIR Method 301 Experiment Protocol", "Procedure"),
        ),
    },
    "runner.ftir.validation_mode": {
        "label": "Validation mode",
        "short_description": "Sets whether the Runner should interpret the FTIR package as a formal Method 301 workflow or an informed comparison.",
        "definition": "Validation mode drives review gating, acceptance basis language, and final package interpretation.",
        "process_note": "Choose formal mode only when the executed comparison-set structure supports that designation.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Acceptance Criteria"),
        ),
    },
    "runner.ftir.vendor_profile": {
        "label": "Vendor profile",
        "short_description": "Chooses the FTIR import adapter profile used to parse the comparator export file.",
        "definition": "Vendor profiles carry file-shape and timestamp parsing assumptions for supported FTIR export formats, including ThermoFisher MAX.",
        "process_note": "Use the explicit vendor profile when known. That reduces import ambiguity and alignment cleanup work.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR formal Method 301 comparison"),
        ),
    },
    "runner.ftir.data_file": {
        "label": "FTIR data file",
        "short_description": "Points the validation package at the comparator export file used for side-by-side alignment and statistics.",
        "definition": "This is the source FTIR dataset preserved as import evidence for the validation package.",
        "process_note": "Choose the exact comparator export file intended for the review package. Do not point this at a transient or manually edited derivative.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Data package contents"),
        ),
    },
    "runner.ftir.timestamp_column": {
        "label": "Timestamp column",
        "short_description": "Names the FTIR file column used as the primary timestamp basis for alignment.",
        "definition": "The timestamp column is the imported FTIR time field used to construct aligned comparison windows.",
        "process_note": "Set this explicitly when the vendor export does not map cleanly from the chosen profile.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Post-processing and timestamp alignment"),
        ),
    },
    "runner.ftir.delimiter": {
        "label": "Delimiter",
        "short_description": "Controls how the FTIR import parser splits incoming text rows.",
        "definition": "Delimiter tells the import path whether the comparator export is CSV, TSV, or should be auto-detected.",
        "process_note": "Set this explicitly when vendor exports are inconsistent or when AUTO detection is ambiguous.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Post-processing and timestamp alignment"),
        ),
    },
    "runner.ftir.offset_seconds": {
        "label": "Time offset (s)",
        "short_description": "Applies a uniform timestamp shift to the FTIR dataset before alignment review.",
        "definition": "Time offset is the global seconds adjustment applied to imported FTIR timestamps for comparison-window pairing.",
        "process_note": "Use this only as part of the documented alignment review and preserve the chosen basis in reviewer notes.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Post-processing and timestamp alignment"),
        ),
    },
    "runner.ftir.analytes": {
        "label": "Analytes",
        "short_description": "Limits the validation package to the target analytes that should participate in the side-by-side review.",
        "definition": "Only analytes measured by both systems and on the same reporting basis should be included in the comparison package.",
        "process_note": "Restrict this to the analytes actually in scope for the project comparison basis.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Scope and Objectives"),
        ),
    },
    "runner.ftir.execution_profile": {
        "label": "Execution profile",
        "short_description": "Defines whether comparison sets come from session run structure or only from manually defined windows.",
        "definition": "The execution profile controls how the side-by-side package builds comparison sets and cadence expectations.",
        "process_note": "Use session-run execution for live controlled field execution. Use manual windows only when the project is being assembled from external reviewed windows.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder -> FTIR Side-by-Side Validation"),
        ),
    },
    "runner.ftir.purge_minutes": {
        "label": "Purge minutes",
        "short_description": "Defines the planned purge interval between live comparison sets in the FTIR execution planner.",
        "definition": "The purge interval is the planned non-comparison period between live comparison windows.",
        "process_note": "Set this to the field protocol value used by the side-by-side test plan, typically 5 minutes in the current workflow.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Recommended schedule within one 3-hour FTIR run"),
        ),
    },
    "runner.ftir.require_purge": {
        "label": "Require ambient purge event",
        "short_description": "Requires an explicit purge event in the live comparison cadence before the next comparison set can be treated as ready.",
        "definition": "Ambient purge events are part of the live side-by-side cadence record when the field protocol requires them.",
        "process_note": "Keep this on when purge evidence is part of the project review basis.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Procedure"),
        ),
    },
    "runner.ftir.planned_sets_override": {
        "label": "Planned sets override",
        "short_description": "Overrides the inherited planned comparison-set count for the current FTIR execution package.",
        "definition": "The planned set count is used by the execution planner to compare completed versus expected comparison sets.",
        "process_note": "Use this only when the Runner package needs a deliberate override from the upstream project plan.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Recommended 3-hour run structure"),
        ),
    },
    "runner.ftir.planned_run_min_override": {
        "label": "Planned run min override",
        "short_description": "Overrides the inherited planned run duration for live FTIR comparison execution.",
        "definition": "This value changes the execution planner’s expected live comparison-window duration.",
        "process_note": "Use this only when the current field execution intentionally departs from the planned run duration captured upstream.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Recommended schedule within one 3-hour FTIR run"),
        ),
    },
    "runner.ftir.use_live_session_runs": {
        "label": "Use live session runs as comparison sets",
        "short_description": "Builds comparison sets directly from the executed MOLE session runs instead of relying only on manual windows.",
        "definition": "Live execution mode derives FTIR comparison sets from recorded run windows and cadence events in the session.",
        "process_note": "Use this for field execution when the session run structure is the intended basis for comparison-set review.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR formal Method 301 comparison"),
            ("MOLE FTIR Method 301 Experiment Protocol", "Procedure"),
        ),
    },
    "runner.ftir.require_bias": {
        "label": "Require bias valve event",
        "short_description": "Requires the side-by-side package to record the expected bias event between comparison windows when the planned cadence calls for it.",
        "definition": "Bias-event requirements are part of the FTIR/MOLE side-by-side cadence review and package readiness logic.",
        "process_note": "Keep this enabled when the field protocol requires a bias event after each planned comparison run.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Recommended schedule within one 3-hour FTIR run"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR formal Method 301 comparison"),
        ),
    },
}


def main() -> None:
    payload = {
        "registry_version": "1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "scripts/seed_ui_help_registry.py",
        "seed_note": "Phase 1 seeded UI help registry. Expand this file as docs and fields grow.",
        "entries": SEED_ENTRIES,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(str(OUT_PATH))


if __name__ == "__main__":
    main()
