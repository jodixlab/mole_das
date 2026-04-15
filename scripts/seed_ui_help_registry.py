from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "config" / "mole_ui_help_registry_v1.json"
TARGET_MANIFEST_PATH = ROOT / "config" / "mole_ui_help_target_manifest_v1.json"


def _refs(*items: tuple[str, str]) -> list[dict[str, str]]:
    return [{"doc_label": doc_label, "section": section} for doc_label, section in items]


SEED_ENTRIES = {
    "wizard.project.job_id": {
        "label": "Job ID",
        "short_description": "Stores the canonical project/session identifier used to name the project package and track the session through the workflow.",
        "definition": "The Job ID is the leading project identifier in the MOLE DAS naming schema and remains the stable identifier even when the generated project folder includes the broader descriptive slug.",
        "process_note": "Keep the generated Job ID unless there is a controlled project reason to override it. The downstream project folder now extends this with descriptive project metadata.",
        "doc_refs": _refs(
            ("MOLE DAS Technical and Operating Manual", "4.1 Wizard-first workflow"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "Project Configurations (Hub)"),
        ),
    },
    "wizard.project.project_name": {
        "label": "Project Name",
        "short_description": "Describes the project or test campaign name that should travel with the session package and report outputs.",
        "definition": "Project name is the human-readable project descriptor used in the generated folder name, reports, and session summaries.",
        "process_note": "Enter the formal project name that should appear in the generated project folder and downstream deliverables.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Project Configurations (Hub)"),
            ("MOLE DAS Technical and Operating Manual", "4.1 Wizard-first workflow"),
        ),
    },
    "wizard.project.site_facility": {
        "label": "Site / Facility",
        "short_description": "Identifies the physical site or facility where the project is being executed.",
        "definition": "Site / Facility is the location descriptor used in project metadata, generated folder naming, and final report language.",
        "process_note": "Use the formal site or facility name expected in the project record and final deliverable.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Project Configurations (Hub)"),
            ("MOLE DAS Technical and Operating Manual", "4.1 Wizard-first workflow"),
        ),
    },
    "wizard.project.operator": {
        "label": "Operator",
        "short_description": "Stores the operator or company name associated with the project execution context.",
        "definition": "Operator is the project operator descriptor used in the generated folder name, session metadata, and deliverable context.",
        "process_note": "Use the formal operator/company name that should persist with the project record.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Project Configurations (Hub)"),
            ("MOLE DAS Technical and Operating Manual", "4.1 Wizard-first workflow"),
        ),
    },
    "wizard.project.asset_unit_id": {
        "label": "Asset / Unit ID",
        "short_description": "Stores the asset or unit identifier used to distinguish the tested source within the project package.",
        "definition": "Asset / Unit ID is the source-specific unit identifier carried in project metadata, generated folder naming, and report language.",
        "process_note": "Use the formal unit, engine, compressor, or asset identifier expected in field records and final deliverables.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Project Configurations (Hub)"),
            ("MOLE DAS Technical and Operating Manual", "4.1 Wizard-first workflow"),
        ),
    },
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
    "wizard.source.category": {
        "label": "Source Category",
        "short_description": "Classifies the physical source category so the Wizard can constrain downstream source logic and equipment defaults.",
        "definition": "Source category is the top-level source classification used to drive source application options, engine-specific fields, and related normalization assumptions.",
        "process_note": "Set this first in the Source Schema section because downstream fields such as Application, Engine Cycle, and Cylinder Count depend on it.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
            ("MOLE DAS Technical and Operating Manual", "4.1 Wizard-first workflow"),
        ),
    },
    "wizard.source.application": {
        "label": "Application",
        "short_description": "Describes the source application within the selected source category.",
        "definition": "Application is the source-use classification beneath the top-level source category and is used to preserve equipment context in the session package.",
        "process_note": "Select the application that best matches the tested source after setting Source Category.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
            ("MOLE DAS Technical and Operating Manual", "4.1 Wizard-first workflow"),
        ),
    },
    "wizard.source.service_class": {
        "label": "Service Class",
        "short_description": "Captures whether the source is stationary, portable, mobile, offshore, or unknown.",
        "definition": "Service class is a source-context descriptor used to distinguish the operating deployment class of the equipment.",
        "process_note": "Use the actual deployment class of the tested equipment so the project record stays defensible.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.output_type": {
        "label": "Output Type",
        "short_description": "Records whether the source output is mechanical, electrical, thermal, or unknown.",
        "definition": "Output type is the functional output classification of the tested source and helps preserve the equipment context in the session record.",
        "process_note": "Choose the output type that matches the actual work produced by the source.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.engine_cycle": {
        "label": "Engine Cycle",
        "short_description": "Stores the engine cycle class used for engine-specific regulatory and equipment context.",
        "definition": "Engine cycle distinguishes two-cycle, four-cycle, or unknown engine classification for source records where the source category is Engine.",
        "process_note": "Populate this only for engine sources. Leave the source category correct first so the field is enabled only when appropriate.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.engine_cyl_count": {
        "label": "Cylinder Count",
        "short_description": "Stores the engine cylinder count for engine sources.",
        "definition": "Cylinder count is the equipment-specific engine count used for source identification and regulatory/equipment context where applicable.",
        "process_note": "Enter this only for engine sources and use the actual installed cylinder count.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.manufacturer": {
        "label": "Manufacturer",
        "short_description": "Identifies the equipment manufacturer for the tested source.",
        "definition": "Manufacturer is the equipment-maker field carried in source metadata and used by the equipment catalog picklists.",
        "process_note": "Use the manufacturer that matches the actual tested equipment. Review the model defaults after selection.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.model_number": {
        "label": "Model Number",
        "short_description": "Identifies the equipment model for the tested source.",
        "definition": "Model Number is the equipment model identifier carried in the source record and used by catalog-driven defaults where available.",
        "process_note": "Use the actual model identifier for the tested equipment. This may drive catalog defaults in the source form.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.serial_number": {
        "label": "Serial Number",
        "short_description": "Captures the equipment serial number for source identification.",
        "definition": "Serial Number is the source-specific equipment serial identifier recorded in project metadata and supporting documentation.",
        "process_note": "Enter the actual equipment serial number used in field and report records.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.asset_tag": {
        "label": "Asset Tag",
        "short_description": "Captures the local asset tag or plant identifier for the tested source.",
        "definition": "Asset Tag is the plant or operator-specific asset identifier that supplements model and serial information.",
        "process_note": "Use the facility’s actual asset tag when one exists so the project record matches field documentation.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.power_units": {
        "label": "Power Units",
        "short_description": "Defines the engineering units used for rating and capacity inputs.",
        "definition": "Power Units determines the unit basis for the source rating and capacity values used in normalization context.",
        "process_note": "Choose the unit basis before entering rating values so Nameplate, Site Rated, and Estimated Operating stay coherent.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.max_power": {
        "label": "Nameplate / Max",
        "short_description": "Stores the nameplate or maximum rated source capacity.",
        "definition": "Nameplate / Max is the maximum equipment rating preserved for source normalization context and reporting.",
        "process_note": "Enter the best-supported nameplate or maximum rating available for the tested source.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.site_rated_power": {
        "label": "Site Rated",
        "short_description": "Stores the site-rated or declared operating capacity for the source.",
        "definition": "Site Rated is the source’s site-declared or permitted rating used when nameplate data is not the chosen normalization basis.",
        "process_note": "Use the declared site-rated value when that is the operational rating the project intends to use.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.estimated_power": {
        "label": "Estimated Operating",
        "short_description": "Stores an estimated operating rating when stronger rating evidence is unavailable.",
        "definition": "Estimated Operating is the fallback operating-capacity estimate used only when better rating evidence is not available.",
        "process_note": "Use this only as a fallback and prefer nameplate or site-rated values when available.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.load_basis": {
        "label": "Load Basis",
        "short_description": "Selects which rating basis should be treated as the current operating basis.",
        "definition": "Load Basis declares whether nameplate, site-rated, or estimated capacity is the active basis for source normalization context.",
        "process_note": "Choose the basis that matches the project’s defensible rating reference.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.source.fuel_flow_basis": {
        "label": "Fuel Flow Basis",
        "short_description": "Declares whether fuel flow is metered, manual, estimated, or unset.",
        "definition": "Fuel Flow Basis is the data-quality posture for fuel flow information used in optional source and exhaust-flow logic.",
        "process_note": "Choose the strongest basis actually available and leave it unset when no fuel-flow value is being carried.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Fuel Analysis"),
        ),
    },
    "wizard.source.fuel_flow_units": {
        "label": "Fuel Flow Units",
        "short_description": "Defines the engineering units used for optional fuel-flow values.",
        "definition": "Fuel Flow Units stores the unit basis for the declared fuel-flow context and adapts to the resolved fuel family.",
        "process_note": "Use units consistent with the source fuel family and the actual field or records basis.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Fuel Analysis"),
        ),
    },
    "wizard.source.fuel_flow_variation_pct": {
        "label": "Typical Variation (%)",
        "short_description": "Captures the expected run-to-run fuel-flow variation percentage.",
        "definition": "Typical Variation is an acknowledgement value representing expected run-to-run fuel-flow variability.",
        "process_note": "Use a realistic variation figure if fuel flow is being carried into the source context.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Fuel Analysis"),
        ),
    },
    "wizard.source.fuel_flow_ack": {
        "label": "Acknowledge Fuel Flow Variation",
        "short_description": "Confirms that run-to-run fuel-flow variation is recognized for the current source context.",
        "definition": "This acknowledgement indicates that optional fuel-flow context may vary between runs and should be treated accordingly.",
        "process_note": "Check this when the project is intentionally carrying an approximate or variable fuel-flow context.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Fuel Analysis"),
        ),
    },
    "wizard.source.exhaust_method": {
        "label": "Exhaust Flow Determination",
        "short_description": "Declares how exhaust flow will be determined for the source workflow.",
        "definition": "Exhaust Flow Determination records whether exhaust flow is derived stoichiometrically, measured, or carried from manufacturer inputs.",
        "process_note": "Choose the actual exhaust-flow determination basis planned for the project so downstream assumptions remain consistent.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Source Info"),
        ),
    },
    "wizard.site.latitude": {
        "label": "Latitude",
        "short_description": "Stores the site latitude in WGS84 coordinates.",
        "definition": "Latitude is the site-location coordinate used for weather and location-aware project context.",
        "process_note": "Use the actual test-site latitude or fetch coordinates before weather compilation.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.longitude": {
        "label": "Longitude",
        "short_description": "Stores the site longitude in WGS84 coordinates.",
        "definition": "Longitude is the site-location coordinate used for weather and location-aware project context.",
        "process_note": "Use the actual test-site longitude or fetch coordinates before weather compilation.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.station_id": {
        "label": "Station ID",
        "short_description": "Stores the preferred weather-station identifier for site weather retrieval.",
        "definition": "Station ID is the site weather-reference identifier used to anchor weather compilation when a specific station is known.",
        "process_note": "Populate this when a preferred station is known; otherwise let the weather workflow resolve it from coordinates.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.elevation_ft_msl": {
        "label": "Elevation (ft MSL)",
        "short_description": "Stores the site elevation above mean sea level in feet.",
        "definition": "Elevation is the site-location elevation used for environmental context and related computations.",
        "process_note": "Enter or fetch the site elevation in feet MSL so the site record stays internally consistent.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.mode": {
        "label": "Weather Mode",
        "short_description": "Declares whether site conditions are sourced automatically from weather data or managed manually.",
        "definition": "Weather Mode controls whether the session relies on automatic weather retrieval or manual site-condition fallback.",
        "process_note": "Use the mode that matches how site conditions will be maintained for the session.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.weather_fail": {
        "label": "On Fetch Fail",
        "short_description": "Defines the failover behavior if automatic weather retrieval is unsuccessful.",
        "definition": "On Fetch Fail is the policy setting that determines how the session should behave when weather retrieval cannot complete as planned.",
        "process_note": "Choose the failover posture that matches the project’s tolerance for manual fallback versus interruption.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.auto_weather_compile": {
        "label": "Auto-compile Weather Data",
        "short_description": "Controls whether the session should compile weather data automatically for the site context.",
        "definition": "Auto-compile weather data enables periodic weather compilation and later Runner backfill for the declared site coordinates and station.",
        "process_note": "Enable this when the project intends to carry automatically compiled weather data in the session record.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.manual_t_amb_f": {
        "label": "T_amb (degF)",
        "short_description": "Stores manual ambient temperature as an optional site-condition fallback value.",
        "definition": "Manual ambient temperature is the fallback temperature value used when the session relies on manually entered site conditions.",
        "process_note": "Use this only when manual site-condition fallback is part of the project’s site-conditions posture.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.manual_p_bar_psia": {
        "label": "P_bar (psia)",
        "short_description": "Stores manual barometric pressure as an optional site-condition fallback value.",
        "definition": "Manual barometric pressure is the fallback pressure value used when the session relies on manually entered site conditions.",
        "process_note": "Use this only when manual site-condition fallback is part of the project’s site-conditions posture.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.manual_rh_frac": {
        "label": "RH (0-1)",
        "short_description": "Stores manual relative humidity as an optional site-condition fallback value.",
        "definition": "Manual RH is the fallback relative-humidity fraction used when the session relies on manually entered site conditions.",
        "process_note": "Enter RH as a fraction from 0 to 1 when using manual site-condition fallback.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.z_model": {
        "label": "Z Model",
        "short_description": "Defines the compressibility-factor model used for site-condition handling.",
        "definition": "Z Model is the compressibility-factor treatment used in the site-conditions context, including ideal or fixed-Z handling.",
        "process_note": "Use the project’s intended compressibility treatment and provide Fixed Z when that mode is selected.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.fixed_z": {
        "label": "Fixed Z",
        "short_description": "Stores the fixed compressibility factor when a fixed-Z site-condition model is used.",
        "definition": "Fixed Z is the explicit compressibility-factor value carried when the site-condition posture uses a fixed-Z model.",
        "process_note": "Populate this only when the selected Z Model requires a fixed Z value.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.fetch_weather": {
        "label": "Fetch Weather",
        "short_description": "Retrieves site weather context using the current coordinates and weather-source policy.",
        "definition": "Fetch Weather is the site-conditions action that populates session weather context from the configured weather source and station logic.",
        "process_note": "Use this after latitude and longitude are set so the site conditions record can be refreshed from NOAA or station-based weather inputs.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.fetch_coordinates": {
        "label": "Fetch Coordinates",
        "short_description": "Attempts to populate site coordinates from the current location metadata.",
        "definition": "Fetch Coordinates is the site-location action that resolves latitude and longitude from the available site or facility context.",
        "process_note": "Use this when the session has enough site metadata to resolve coordinates automatically.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.fetch_elevation": {
        "label": "Fetch Elevation",
        "short_description": "Resolves elevation from the current site coordinates.",
        "definition": "Fetch Elevation is the site-location action that looks up elevation above mean sea level for the entered coordinates.",
        "process_note": "Use this after coordinates are set so the site record can carry a resolved elevation basis.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "wizard.site.open_map": {
        "label": "Open Map",
        "short_description": "Opens the current site coordinates in a map view for visual confirmation.",
        "definition": "Open Map is the location-review action used to visually verify the session site coordinates against a map.",
        "process_note": "Use this to confirm that the entered or fetched coordinates point at the intended site.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
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
    "wizard.pollutants.selection": {
        "label": "Pollutant Selection",
        "short_description": "Enables or disables a pollutant in the active project selection set.",
        "definition": "Pollutant selection drives the downstream QA/QC profile, method resolution, and Test Matrix autogeneration contract.",
        "process_note": "Select only the pollutants that are actually in scope for the project so the downstream workflow resolves correctly.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Pollutants"),
            ("MOLE DAS Technical and Operating Manual", "Pollutants -> QA/QC profile/method auto-population -> Test Matrix autogeneration"),
        ),
    },
    "wizard.pollutants.active": {
        "label": "Active Pollutant",
        "short_description": "Selects which enabled pollutant is currently being edited in the active pollutant prescription panel.",
        "definition": "The active pollutant is the current pollutant context used for pollutant-specific configuration fields on the right-hand editor panel.",
        "process_note": "Use this to switch between enabled pollutants when reviewing or editing pollutant-specific settings.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Pollutants"),
        ),
    },
    "wizard.pollutants.expected_max": {
        "label": "Expected Max",
        "short_description": "Stores the expected maximum concentration for the active pollutant.",
        "definition": "Expected Max is the pollutant-specific expected concentration ceiling used for span suggestion and setup context.",
        "process_note": "Enter a realistic upper-bound expectation for the active pollutant so downstream suggestions and review context remain defensible.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Pollutants"),
        ),
    },
    "wizard.pollutants.units": {
        "label": "Units",
        "short_description": "Stores the expected engineering units for the active pollutant.",
        "definition": "Units determine the engineering basis for the active pollutant’s expected maximum and related setup context.",
        "process_note": "Use the engineering units that match the actual measurement basis for the pollutant.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Pollutants"),
        ),
    },
    "wizard.pollutants.method_selected": {
        "label": "Method (Selected)",
        "short_description": "Shows or selects the pollutant-specific method basis currently associated with the active pollutant.",
        "definition": "Method (Selected) is the pollutant-level method selection used as input to the effective-method and QA/QC resolution logic.",
        "process_note": "Review this for the active pollutant and keep it aligned with the intended method basis for the project.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Pollutants"),
        ),
    },
    "wizard.pollutants.cal_points_selected": {
        "label": "CAL Points (Selected)",
        "short_description": "Stores the active pollutant’s selected calibration-point count.",
        "definition": "CAL Points (Selected) is the pollutant-specific selected calibration-point posture before effective QA/QC resolution.",
        "process_note": "Use AUTO unless a controlled reason exists to override the pollutant’s selected calibration-point count.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Pollutants"),
        ),
    },
    "wizard.pollutants.lin_points_selected": {
        "label": "LIN Points (Selected)",
        "short_description": "Stores the active pollutant’s selected linearity-point count.",
        "definition": "LIN Points (Selected) is the pollutant-specific selected linearity-point posture before effective QA/QC resolution.",
        "process_note": "Use AUTO unless a controlled reason exists to override the pollutant’s selected linearity-point count.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Pollutants"),
        ),
    },
    "wizard.pollutants.nox_converter_efficiency": {
        "label": "NOx Converter Eff.",
        "short_description": "Enables the optional NOx converter efficiency workflow for the active pollutant when applicable.",
        "definition": "NOx Converter Eff. is the pollutant-level switch for adding the optional converter-efficiency workflow to the active pollutant prescription.",
        "process_note": "Use this only when the active pollutant and project configuration require the converter-efficiency workflow.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Pollutants"),
        ),
    },
    "wizard.qaqc.sig_digits": {
        "label": "Sig digits (display)",
        "short_description": "Controls the display precision used in QA/QC-facing numeric presentation.",
        "definition": "Sig digits (display) defines the displayed significant-digit precision used in QA/QC-facing calculations and review surfaces.",
        "process_note": "Use the project’s intended review/display precision and avoid changing this casually once a project is underway.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "QA/QC"),
        ),
    },
    "wizard.qaqc.portable_track": {
        "label": "Portable Track (2-point typical)",
        "short_description": "Sets the QA/QC posture to the portable-track configuration where that project mode applies.",
        "definition": "Portable Track is the QA/QC project posture used for portable-style workflows with the typical two-point approach.",
        "process_note": "Enable this only when the project is intentionally using the portable-track QA/QC posture.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "QA/QC"),
        ),
    },
    "wizard.qaqc.diag_optin_cal_lin": {
        "label": "DIAG + Record+Token: include Cal/Linearity capture anyway (opt-in)",
        "short_description": "Allows a diagnostics-flavored project to capture calibration and linearity evidence when intentionally opted in.",
        "definition": "This opt-in overrides the default diagnostics posture for the limited purpose of including calibration and linearity capture anyway.",
        "process_note": "Use this only when the project intentionally needs Cal/Linearity capture despite the diagnostics posture.",
        "doc_refs": _refs(
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
    "wizard.reference_ftir.prn_path": {
        "label": "Path",
        "short_description": "Points the reference FTIR ingest path at the PRN file or folder used for companion FTIR evidence.",
        "definition": "The path is the concrete file or folder location scanned by the packaged FTIR ingest path for reference or audit evidence.",
        "process_note": "Use the actual FTIR export location intended for the current project. Keep this pointed at the controlled evidence source, not a temporary copy.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Reference / Audit FTIR"),
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
    "runner.ftir.master_clock": {
        "label": "Master clock",
        "short_description": "Defines the authoritative time basis used by the Runner when aligning MOLE and FTIR evidence.",
        "definition": "The master clock is the declared time basis used for the side-by-side alignment and final validation package.",
        "process_note": "Set this to the same declared clock basis used upstream in the validation plan so the Runner and final report stay consistent.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Post-processing and timestamp alignment"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "Validation Test Plan"),
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
    "runner.ftir.browse_file": {
        "label": "Browse FTIR File",
        "short_description": "Selects the comparator FTIR export file for the validation package.",
        "definition": "Browse FTIR File is the action used to choose the source comparator file that will be imported into the FTIR validation workflow.",
        "process_note": "Use this to point the package at the exact FTIR export intended for review, lock, and report generation.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR formal Method 301 comparison"),
        ),
    },
    "runner.ftir.open_template_folder": {
        "label": "Open Template Folder",
        "short_description": "Opens the FTIR validation template folder used for imports and alignment support.",
        "definition": "Open Template Folder exposes the maintained FTIR validation templates that support field preparation and review.",
        "process_note": "Use this when preparing or checking the FTIR import and alignment support files.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR / validation-specific tabs and sections"),
        ),
    },
    "runner.ftir.open_import_template": {
        "label": "Open Import Template",
        "short_description": "Opens the FTIR import template used to prepare comparator data in the expected shape.",
        "definition": "Open Import Template exposes the maintained FTIR import template used for comparator data preparation.",
        "process_note": "Use this when the FTIR export needs to be normalized into the expected import structure.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR / validation-specific tabs and sections"),
        ),
    },
    "runner.ftir.open_alignment_worksheet": {
        "label": "Open Alignment Worksheet",
        "short_description": "Opens the FTIR alignment worksheet used to support timestamp and window review.",
        "definition": "Open Alignment Worksheet exposes the alignment worksheet used to prepare or review comparison-window timing.",
        "process_note": "Use this when the FTIR comparison package needs explicit window and timestamp alignment support.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR / validation-specific tabs and sections"),
        ),
    },
    "runner.ftir.refresh_preview": {
        "label": "Refresh FTIR Validation Preview",
        "short_description": "Recomputes the current FTIR validation preview and review status from the active settings and evidence.",
        "definition": "Refresh FTIR Validation Preview updates the current comparison, QA, and review-state preview without building the final report.",
        "process_note": "Use this after changing FTIR settings, exclusions, or alignment assumptions so the preview reflects current state.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder -> FTIR Side-by-Side Validation"),
        ),
    },
    "runner.test_matrix.waive_reason": {
        "label": "Waive reason",
        "short_description": "Captures the explicit rationale for waiving a test-matrix item instead of performing it as planned.",
        "definition": "A waived test-matrix item requires a documented reason so the session record and final package show why the planned activity was not performed.",
        "process_note": "Enter the waiver basis before toggling a step to waived so the decision is preserved in the tracking record.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Test Matrix"),
        ),
    },
    "runner.test_matrix.toggle_performed": {
        "label": "Toggle Performed",
        "short_description": "Marks the selected test-matrix item as performed or not performed.",
        "definition": "Performed state is the live tracking flag that records whether a planned test-matrix activity has been completed.",
        "process_note": "Use this only on the selected test-matrix row and keep it aligned with the actual executed work.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Test Matrix"),
        ),
    },
    "runner.test_matrix.toggle_waived": {
        "label": "Toggle Waived",
        "short_description": "Marks the selected test-matrix item as waived when it will not be executed.",
        "definition": "Waived state is the explicit tracking posture for a planned test activity that is intentionally not executed.",
        "process_note": "Use this only with a documented waive reason so the tracking and final record remain defensible.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Test Matrix"),
        ),
    },
    "runner.runs.notes": {
        "label": "Run Notes",
        "short_description": "Stores run-specific notes for the currently selected run in the method-input workflow.",
        "definition": "Run notes are the per-run freeform remarks preserved with the run record for later review and reporting context.",
        "process_note": "Use this for material run-specific observations, not general project notes.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.runs.new_run": {
        "label": "New Run",
        "short_description": "Creates the next run record in the current session.",
        "definition": "New Run is the run-lifecycle action that opens a new method-input run context for acquisition and run-specific notes.",
        "process_note": "Use this when starting the next run in the session. Do not create extra runs that are not part of the actual execution record.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.runs.end_run": {
        "label": "End Run",
        "short_description": "Closes the selected active run record.",
        "definition": "End Run is the run-lifecycle action that stamps the current run as complete for the session record.",
        "process_note": "Use this only when the active run is actually complete and ready to be closed in the run history.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.runs.save_inputs": {
        "label": "Save Run Inputs",
        "short_description": "Writes the current run method-input values into the session state.",
        "definition": "Save Run Inputs preserves the currently edited run notes and method-input values for the selected run.",
        "process_note": "Use this after editing per-run inputs so the current run state is preserved before moving on.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.hp_mode": {
        "label": "HP Input Mode",
        "short_description": "Declares which horsepower/load input basis the run is using.",
        "definition": "HP Input Mode selects whether horsepower is carried as direct horsepower, load fraction, or IMAP-derived load context.",
        "process_note": "Choose the strongest actual run basis available so the Method 19 crosswalk and load context remain defensible.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.load_fraction": {
        "label": "Load Fraction",
        "short_description": "Stores the run load fraction when load-based horsepower input is used.",
        "definition": "Load Fraction is the fractional engine load basis used to estimate horsepower for the current run.",
        "process_note": "Use a 0 to 1 fractional value that matches the run-specific operating load basis.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.actual_hp": {
        "label": "Actual HP",
        "short_description": "Stores direct measured or declared brake horsepower for the current run.",
        "definition": "Actual HP is the direct horsepower input used when the run has a known horsepower value instead of a derived load basis.",
        "process_note": "Use this only when a direct run horsepower basis exists.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.imap_value": {
        "label": "IMAP",
        "short_description": "Stores intake manifold pressure for IMAP-based horsepower estimation.",
        "definition": "IMAP is the intake manifold absolute or gauge pressure input used for IMAP-based load interpretation.",
        "process_note": "Use this only when the run is using IMAP mode and ensure the units field matches the entered value.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.imap_units": {
        "label": "IMAP Units",
        "short_description": "Defines the engineering units used for the IMAP input.",
        "definition": "IMAP Units sets the pressure-unit basis for the run IMAP value and related idle/full calibration points.",
        "process_note": "Keep this aligned with the instrumentation or source record basis used for the run.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.imap_idle": {
        "label": "IMAP Idle",
        "short_description": "Stores the idle or minimum IMAP reference point used in IMAP mode.",
        "definition": "IMAP Idle is the low-end reference point for interpreting current IMAP relative to the run’s operating envelope.",
        "process_note": "Populate this when IMAP mode is used and the idle reference is known.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.imap_full": {
        "label": "IMAP Full",
        "short_description": "Stores the full-load or maximum IMAP reference point used in IMAP mode.",
        "definition": "IMAP Full is the high-end reference point for interpreting current IMAP relative to the run’s operating envelope.",
        "process_note": "Populate this when IMAP mode is used and the full-load reference is known.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.imap_mid": {
        "label": "IMAP Mid",
        "short_description": "Stores an optional midpoint IMAP reference for non-linear IMAP interpretation.",
        "definition": "IMAP Mid is an optional reference point between idle and full load used to improve IMAP-based load interpretation.",
        "process_note": "Use this only when a midpoint reference belongs in the IMAP load model for the source.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.imap_mid_util": {
        "label": "Mid Util",
        "short_description": "Stores the utilization associated with the optional IMAP midpoint.",
        "definition": "Mid Util is the load/utilization value paired with the optional IMAP midpoint reference.",
        "process_note": "Enter this only when IMAP Mid is being used and the midpoint utilization is known.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.fuel_flow_value": {
        "label": "Fuel Flow (this run)",
        "short_description": "Stores the run-specific fuel-flow value used for Method 19 stoichiometric handling.",
        "definition": "Fuel Flow is the current run fuel-flow basis used when exhaust flow is being determined stoichiometrically from fuel input.",
        "process_note": "Use the run-specific fuel-flow value that matches the declared units and fuel-flow basis.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.fuel_flow_units": {
        "label": "Fuel Flow Units",
        "short_description": "Defines the engineering units for the run-specific fuel-flow value.",
        "definition": "Fuel Flow Units sets the engineering basis for the run fuel-flow value used in Method 19 stoichiometric handling.",
        "process_note": "Keep this aligned with the actual field or record basis for the run fuel-flow value.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.o2_dry_pct": {
        "label": "O2 dry %",
        "short_description": "Stores dry-basis oxygen used in the Method 19 crosswalk or stack-measured helper path.",
        "definition": "O2 dry percent is the oxygen input used in oxygen-correction and Method 19 crosswalk logic when the operator provides an override.",
        "process_note": "Enter this only when the run needs an explicit operator-provided O2 value rather than the live analyzer feed.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Oxygen correction"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.qd_dscfh": {
        "label": "Qd dry dscfh",
        "short_description": "Stores direct-entry dry standard exhaust flow for the current run.",
        "definition": "Qd dry dscfh is the dry standard exhaust flow basis used when the operator provides direct stack-flow entry instead of deriving it from pitot inputs.",
        "process_note": "Use this as the single direct-entry dry standard flow basis when it is known for the run.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.stack_flow_acfm": {
        "label": "Stack flow (acfm)",
        "short_description": "Stores direct-entry actual stack flow for the current run.",
        "definition": "Stack flow ACFM is the actual cubic-feet-per-minute run flow used only when a direct actual-flow basis is being carried.",
        "process_note": "Use this only when direct-entry stack flow is the chosen run basis and avoid mixing it with conflicting direct Qd values.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.stack_velocity_fps": {
        "label": "Stack velocity (ft/s)",
        "short_description": "Stores direct-entry stack velocity for the current run.",
        "definition": "Stack velocity is the run-specific actual velocity basis carried only when the operator is using direct-entry measured velocity context.",
        "process_note": "Use this only when the run has a defensible direct velocity basis and avoid duplicating conflicting direct-entry values.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.pitot_dp_inh2o": {
        "label": "Pitot ΔP",
        "short_description": "Stores average pitot differential pressure for the Method 2 helper path.",
        "definition": "Pitot differential pressure is the Method 2 traverse pressure input used to calculate stack velocity and flow.",
        "process_note": "Use the average traverse differential pressure for the current run when Method 2 helper calculations are being used.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.pitot_cp": {
        "label": "Pitot Cp",
        "short_description": "Stores the pitot coefficient used in the Method 2 helper calculation path.",
        "definition": "Pitot Cp is the pitot calibration coefficient applied in Method 2 helper calculations.",
        "process_note": "Use the coefficient associated with the pitot setup used for the run.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.stack_temp_f": {
        "label": "Stack temp (F)",
        "short_description": "Stores stack temperature for the Method 2 helper path.",
        "definition": "Stack temperature is the run stack-gas temperature input used in Method 2 helper calculations.",
        "process_note": "Use the run-average stack temperature basis that matches the current Method 2 traverse inputs.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.stack_static_inh2o": {
        "label": "Stack static (inH2O)",
        "short_description": "Stores stack static pressure for the Method 2 helper path.",
        "definition": "Stack static pressure is the run stack static input used in Method 2 helper calculations.",
        "process_note": "Use the run static-pressure basis that matches the current Method 2 traverse inputs.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.baro_psia": {
        "label": "Baro override (psia)",
        "short_description": "Stores an explicit barometric-pressure override for the run.",
        "definition": "Barometric pressure override is the operator-provided barometric basis used instead of a derived site-condition value when needed.",
        "process_note": "Use this only when the run requires an explicit barometric override.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "Site Conditions"),
        ),
    },
    "runner.method_input.co_dry_pct": {
        "label": "CO dry %",
        "short_description": "Stores dry-basis carbon monoxide used in stack-measured helper calculations.",
        "definition": "CO dry percent is the carbon monoxide input used in the combustion/moisture approximation path for the current run.",
        "process_note": "Use this only when the stack-measured helper path requires an explicit operator-provided CO value.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.co2_dry_pct": {
        "label": "CO2 dry %",
        "short_description": "Stores dry-basis carbon dioxide used in stack-measured helper calculations.",
        "definition": "CO2 dry percent is the carbon dioxide input used in the combustion/moisture approximation path for the current run.",
        "process_note": "Use this only when the run needs an explicit operator-provided CO2 value rather than a live feed.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.h2o_wet_pct": {
        "label": "H2O wet %",
        "short_description": "Stores wet-basis moisture used for wet-to-dry handling.",
        "definition": "H2O wet percent is the moisture input used in wet-to-dry conversion and crosswalk handling for the current run.",
        "process_note": "Use this only when the run has an explicit wet-basis moisture value that should override estimated moisture.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.method_input.swirl_alpha_deg": {
        "label": "Avg swirl α",
        "short_description": "Stores average swirl angle for stack-measured flow interpretation.",
        "definition": "Average swirl alpha is the run swirl-angle input used to interpret stack-measured flow when applicable.",
        "process_note": "Enter this only when the run has a defensible average swirl-angle basis.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Method Inputs (Per Run)"),
        ),
    },
    "runner.diagnostics_verification.technician_operator": {
        "label": "Technician / Operator",
        "short_description": "Identifies the person documenting diagnostics verification details.",
        "definition": "Technician / Operator is the named person responsible for the diagnostics verification record captured in the Runner.",
        "process_note": "Enter the person actually responsible for the recorded diagnostics verification entry.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Diagnostics-only Test"),
            ("MOLE DAS Terms, Definitions, and References", "Diagnostics Verification"),
        ),
    },
    "runner.diagnostics_verification.worksheet_ref": {
        "label": "Worksheet / Form Ref",
        "short_description": "Stores the supporting worksheet or form reference for the diagnostics verification record.",
        "definition": "Worksheet / Form Ref is the external document or record reference tied to the diagnostics verification evidence.",
        "process_note": "Use a stable worksheet, form, or log reference that can be audited later.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Diagnostics Verification"),
        ),
    },
    "runner.diagnostics_verification.calibration_gas_ids": {
        "label": "Calibration Gas IDs",
        "short_description": "Stores the calibration-gas identifiers associated with diagnostics verification.",
        "definition": "Calibration Gas IDs are the gas-cylinder or standard identifiers used to support diagnostics verification documentation.",
        "process_note": "Record the actual gas IDs used for the documented verification event.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Diagnostics Verification"),
        ),
    },
    "runner.diagnostics_verification.attachment_path": {
        "label": "Attachment Path",
        "short_description": "Stores or opens the supporting attachment for the diagnostics verification record.",
        "definition": "Attachment Path is the file reference to supporting evidence such as a worksheet, photo, or supporting record.",
        "process_note": "Point this at the specific supporting evidence file for the diagnostics verification record.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Diagnostics Verification"),
        ),
    },
    "runner.diagnostics_verification.notes": {
        "label": "Verification Notes",
        "short_description": "Stores freeform notes supporting the diagnostics verification record.",
        "definition": "Verification Notes are the operator-entered narrative comments that explain the diagnostics verification record.",
        "process_note": "Use this for concise verification evidence context, not general run notes.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Diagnostics Verification"),
        ),
    },
    "runner.diagnostics_verification.save_details": {
        "label": "Save Verification Details",
        "short_description": "Saves the current diagnostics verification details into session state.",
        "definition": "This action preserves the current diagnostics verification form values without marking pre-test or post-test completion.",
        "process_note": "Use this after updating diagnostics verification details so the evidence record is preserved.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Diagnostics Verification"),
        ),
    },
    "runner.diagnostics_verification.mark_pretest": {
        "label": "Mark Pre-Test Verified",
        "short_description": "Marks the diagnostics pre-test verification stage as complete.",
        "definition": "This action records explicit completion of the pre-test diagnostics verification stage in the session evidence.",
        "process_note": "Use this only after the pre-test diagnostics verification evidence is actually complete and documented.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Diagnostics Verification"),
        ),
    },
    "runner.diagnostics_verification.clear_pretest": {
        "label": "Clear Pre-Test",
        "short_description": "Clears the explicit pre-test verification mark from the diagnostics verification record.",
        "definition": "This action removes the explicit completed state for the pre-test diagnostics verification stage.",
        "process_note": "Use this when the pre-test verification state needs correction or was marked in error.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Diagnostics Verification"),
        ),
    },
    "runner.diagnostics_verification.mark_posttest": {
        "label": "Mark Post-Test Verified",
        "short_description": "Marks the diagnostics post-test verification stage as complete.",
        "definition": "This action records explicit completion of the post-test diagnostics verification stage in the session evidence.",
        "process_note": "Use this only after the post-test diagnostics verification evidence is actually complete and documented.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Diagnostics Verification"),
        ),
    },
    "runner.diagnostics_verification.clear_posttest": {
        "label": "Clear Post-Test",
        "short_description": "Clears the explicit post-test verification mark from the diagnostics verification record.",
        "definition": "This action removes the explicit completed state for the post-test diagnostics verification stage.",
        "process_note": "Use this when the post-test verification state needs correction or was marked in error.",
        "doc_refs": _refs(
            ("MOLE DAS Terms, Definitions, and References", "Diagnostics Verification"),
        ),
    },
    "runner.side_by_side.note": {
        "label": "Operator note",
        "short_description": "Stores the current side-by-side operator note used to annotate alignment and cadence events.",
        "definition": "The operator note is the current annotation carried with side-by-side sync, bias, purge, and drift events.",
        "process_note": "Enter the note before logging a side-by-side event when the event needs context preserved in the alignment history.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR Side-by-Side Informed Comparison"),
            ("MOLE FTIR Method 301 Experiment Protocol", "Procedure"),
        ),
    },
    "runner.side_by_side.sync_mark": {
        "label": "Mark Sync Point",
        "short_description": "Records a side-by-side synchronization marker used to align MOLE and FTIR timelines.",
        "definition": "A sync point is a logged side-by-side event that marks a known alignment reference in the comparison history.",
        "process_note": "Use this whenever a deliberate synchronization marker is needed to interpret the MOLE/FTIR timeline.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Procedure"),
        ),
    },
    "runner.side_by_side.bias_valve": {
        "label": "Log Bias Valve",
        "short_description": "Records the side-by-side bias-valve event required by the comparison cadence when bias is due.",
        "definition": "Bias-valve events are explicit cadence records used in the side-by-side package and FTIR execution workflow.",
        "process_note": "Log this after the completed run whenever the planned cadence requires a post-run bias event.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Recommended schedule within one 3-hour FTIR run"),
            ("MOLE DAS Worksteps - All Tabs and Flows", "FTIR formal Method 301 comparison"),
        ),
    },
    "runner.side_by_side.ambient_purge": {
        "label": "Log Ambient Purge",
        "short_description": "Records the planned ambient purge step in the side-by-side alignment history.",
        "definition": "Ambient purge is a logged cadence event used when the side-by-side plan requires a purge period between comparison windows.",
        "process_note": "Log this when the purge step is part of the planned side-by-side procedure and should be preserved in the event history.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Procedure"),
        ),
    },
    "runner.side_by_side.project_drift": {
        "label": "Log Project Drift",
        "short_description": "Records the project drift step in the side-by-side alignment history.",
        "definition": "Project drift is a logged side-by-side event used when the comparison workflow requires drift tracking between windows or runs.",
        "process_note": "Log this when the project plan or review package requires explicit drift documentation.",
        "doc_refs": _refs(
            ("MOLE FTIR Method 301 Experiment Protocol", "Procedure"),
        ),
    },
    "runner.report.notice_of_intent_date": {
        "label": "Notice of intent date",
        "short_description": "Stores the notice-of-intent timing reference used in the formal report package.",
        "definition": "The notice-of-intent date is the project-level reporting reference for the submitted or planned NOI timing.",
        "process_note": "Populate this when the project requires NOI context in the final report or compliance package.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.client_name": {
        "label": "Client name",
        "short_description": "Stores the client name used in the formal report package.",
        "definition": "Client name is the project customer or client identifier carried into the report context and final deliverable.",
        "process_note": "Use the formal client name that should appear in the final report.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.facility_owner": {
        "label": "Facility owner / operator",
        "short_description": "Stores the facility owner or operator name used in the formal report package.",
        "definition": "Facility owner / operator is the owner/operator identity carried into the report context and final deliverable.",
        "process_note": "Use the formal facility owner or operator name expected in the final report.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.test_company": {
        "label": "Test company",
        "short_description": "Stores the test company responsible for the project execution or report package.",
        "definition": "Test company is the organization performing the test program and preparing the deliverable package.",
        "process_note": "Use the formal test company name that should appear in the final report.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.laboratory": {
        "label": "Laboratory",
        "short_description": "Stores the laboratory identity used in the formal report package when applicable.",
        "definition": "Laboratory is the lab name carried into the report context for analytical or organizational reference.",
        "process_note": "Use this when a lab identity belongs in the final package.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.session_operator": {
        "label": "Session operator",
        "short_description": "Stores the session operator name carried into the formal report context.",
        "definition": "Session operator is the operator identity associated with the active test session and final report context.",
        "process_note": "Use the person or operator identity that should appear in the formal package.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.responsible_official": {
        "label": "Responsible official",
        "short_description": "Stores the responsible official identified for the final report package.",
        "definition": "Responsible official is the formal accountable official carried into the final report and approval context.",
        "process_note": "Use the actual responsible official expected to appear in the deliverable.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.responsible_title": {
        "label": "Responsible title",
        "short_description": "Stores the official title of the responsible official in the final report package.",
        "definition": "Responsible title is the formal title associated with the recorded responsible official.",
        "process_note": "Use the title that should appear verbatim in the report.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.agency_contact": {
        "label": "Agency contact",
        "short_description": "Stores the relevant agency contact context for the formal report package.",
        "definition": "Agency contact is the project regulatory contact carried into the report context when applicable.",
        "process_note": "Use this when the report package needs to preserve the project agency contact.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.submission_status": {
        "label": "Submission status",
        "short_description": "Stores the current submission or filing status associated with the test package.",
        "definition": "Submission status is the formal deliverable-status note carried into the report context and approval summary.",
        "process_note": "Use clear status language that matches the current regulatory or client-submission posture.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.observer_contacts": {
        "label": "Observer contacts",
        "short_description": "Captures the observer or witness contact context used in the report package.",
        "definition": "Observer contacts are the people or organizations recorded as test observers, witnesses, or review participants in the formal package.",
        "process_note": "Use this when observer contact information should travel with the final report context.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.approval_dates": {
        "label": "Approval dates",
        "short_description": "Captures approval-date references that need to appear in the report package.",
        "definition": "Approval dates are the formal dates associated with approvals, agency coordination, or report review milestones.",
        "process_note": "Enter only the dates that belong in the formal project package and final report context.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.session_review.scope": {
        "label": "Review scope",
        "short_description": "Defines the package-level approval scope applied to the current formal deliverable.",
        "definition": "Review scope determines whether the current package is being reviewed as a project review, compliance report, or validation report.",
        "process_note": "Choose the scope that matches the deliverable being prepared so approval basis and signoff language stay consistent.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.session_review.reviewer_name": {
        "label": "Reviewer name",
        "short_description": "Stores the person performing the current package-level review.",
        "definition": "Reviewer name is the package reviewer carried into shared review metadata and final report approval context.",
        "process_note": "Use the actual reviewer responsible for the current review cycle.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.session_review.reviewer_role": {
        "label": "Reviewer role",
        "short_description": "Stores the reviewer role associated with the current package-level review.",
        "definition": "Reviewer role is the formal role or title associated with the recorded package reviewer.",
        "process_note": "Use the role/title that should persist into the package approval record.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.session_review.default_approver": {
        "label": "Default approver",
        "short_description": "Stores the planned approver for the package-level signoff path.",
        "definition": "Default approver is the expected signoff authority for the current deliverable scope.",
        "process_note": "Set this to the person expected to approve the current report or validation package.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.session_review.default_approver_role": {
        "label": "Approver role",
        "short_description": "Stores the formal role of the planned approver for the package-level signoff path.",
        "definition": "Approver role is the role/title associated with the expected signoff authority.",
        "process_note": "Use the formal title that belongs in the package approval record.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.session_review.decision": {
        "label": "Decision",
        "short_description": "Records the current package-level approval decision.",
        "definition": "Decision is the shared review/signoff outcome carried into the report context and approval summary.",
        "process_note": "Set this only after the review basis and scope are correct for the current package.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.session_review.acceptance_basis": {
        "label": "Acceptance basis",
        "short_description": "Records the approval basis used to justify the current package-level decision.",
        "definition": "Acceptance basis is the formal basis state attached to the package review and signoff record.",
        "process_note": "Keep this aligned with the actual deliverable scope and decision state.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.session_review.signoff_by": {
        "label": "Signoff by",
        "short_description": "Stores the approving person for the current shared review signoff.",
        "definition": "Signoff by is the person recorded as the package approver in the final approval metadata.",
        "process_note": "Populate this at actual signoff time so the approval record reflects the true approver.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.session_review.signoff_role": {
        "label": "Signoff role",
        "short_description": "Stores the approver role for the current shared review signoff.",
        "definition": "Signoff role is the formal role/title associated with the recorded approving person.",
        "process_note": "Use the formal approver title that belongs in the package approval record.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.session_review.notes": {
        "label": "Session Review Notes",
        "short_description": "Stores package-level reviewer observations, limitations, and release notes.",
        "definition": "Session review notes are the shared package-review remarks carried into report context and approval records.",
        "process_note": "Use this for substantive review observations or package constraints that should survive into the final record.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.session_review.signoff_note": {
        "label": "Session Review Signoff Note",
        "short_description": "Stores the explicit approval conditions, restrictions, or rejection basis attached to signoff.",
        "definition": "The signoff note is the package-level approval narrative associated with the recorded decision.",
        "process_note": "Use this to preserve approval conditions, exceptions, or a specific rejection basis.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.process_narrative": {
        "label": "Process Narrative",
        "short_description": "Stores the report-ready narrative describing the source, duty, and operating context.",
        "definition": "Process narrative is the formal descriptive narrative used in the final report to explain the source and test context.",
        "process_note": "Write this in report-ready language because it can flow directly into the formal deliverable.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.control_equipment_description": {
        "label": "Control Equipment Description",
        "short_description": "Stores the report-ready description of any relevant control equipment.",
        "definition": "Control equipment description is the formal narrative describing control devices and relevant operating context for the source.",
        "process_note": "Use this when the report should describe control devices or control-side operating context.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.planned_deviations": {
        "label": "Planned Deviations",
        "short_description": "Stores planned or pre-approved departures from the standard procedure.",
        "definition": "Planned deviations are the preplanned or pre-approved departures from standard execution preserved in the formal package.",
        "process_note": "Use one item per line so the package and report can preserve each deviation cleanly.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.field_deviations": {
        "label": "Field Deviations",
        "short_description": "Stores observed field deviations that occurred during testing.",
        "definition": "Field deviations are the actual departures from expected execution observed during the test program.",
        "process_note": "Use one item per line and keep the text factual and review-ready.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.alternative_method_approvals": {
        "label": "Alternative Method / Approval References",
        "short_description": "Stores the identifiers for alternative methods, approvals, or related supporting references.",
        "definition": "Alternative method / approval references are the formal permit, email, or approval identifiers preserved in the report package.",
        "process_note": "Use one item per line so each approval or reference remains distinct in the final record.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.impact_statement": {
        "label": "Impact Statement",
        "short_description": "Stores the statement describing whether deviations or approvals affected validity or interpretation.",
        "definition": "Impact statement is the report-ready explanation of whether recorded deviations or approvals affected data validity, comparability, or interpretation.",
        "process_note": "State the impact clearly so the final report can preserve the conclusion without rework.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.correspondence_notes": {
        "label": "Regulatory / Correspondence Notes",
        "short_description": "Stores regulatory and correspondence context carried into the final report package.",
        "definition": "Regulatory / correspondence notes summarize NOI, agency coordination, ERT/CEDRI status, and related project correspondence context.",
        "process_note": "Use this for concise summary context, not full correspondence transcripts.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.save_metadata": {
        "label": "Save Report Metadata",
        "short_description": "Persists the current report-builder metadata into the session state.",
        "definition": "Save Report Metadata records the current report-builder inputs without running a full report build.",
        "process_note": "Use this after editing report metadata so the current report context is preserved.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.build_final_report": {
        "label": "Build Final Report",
        "short_description": "Generates the formal report outputs from the current session, report metadata, and supporting artifacts.",
        "definition": "Build Final Report is the report-builder action that assembles the report pack and final deliverables from the current session state.",
        "process_note": "Use this only after the package review state and supporting evidence are ready for deliverable generation.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.refresh_status": {
        "label": "Refresh Status",
        "short_description": "Refreshes the report-builder status view from current session and export state.",
        "definition": "Refresh Status updates the report-builder status summaries, artifact paths, and readiness indicators without rebuilding outputs.",
        "process_note": "Use this after external changes or session-state changes when you need the status panel refreshed.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.open_final_report": {
        "label": "Open Final Report",
        "short_description": "Opens the current final report artifact, preferring DOCX or PDF when available.",
        "definition": "Open Final Report launches the current final deliverable artifact from the report-builder output set.",
        "process_note": "Use this to review the built final deliverable after report generation completes.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.open_final_report_folder": {
        "label": "Open Final Report Folder",
        "short_description": "Opens the folder containing the current final report outputs.",
        "definition": "Open Final Report Folder exposes the final-report output directory so the built artifacts can be inspected directly.",
        "process_note": "Use this when you need to inspect or transfer the final report artifact set.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
    "runner.report.open_report_pack_folder": {
        "label": "Open Report Pack Folder",
        "short_description": "Opens the report-pack folder containing summary and evidence-package artifacts.",
        "definition": "Open Report Pack Folder exposes the report-pack directory that contains the structured export set behind the final report.",
        "process_note": "Use this when you need the evidence-oriented report-pack outputs rather than the final formatted deliverable.",
        "doc_refs": _refs(
            ("MOLE DAS Worksteps - All Tabs and Flows", "Report Builder"),
        ),
    },
}


def _load_existing_entries() -> dict[str, Any]:
    try:
        payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    entries = payload.get("entries")
    return entries if isinstance(entries, dict) else {}


def main() -> None:
    existing_entries = _load_existing_entries()
    merged_entries: dict[str, Any] = {}
    for help_id, entry in existing_entries.items():
        if isinstance(entry, dict):
            merged_entries[help_id] = dict(entry)
    for help_id, seed_entry in SEED_ENTRIES.items():
        current = merged_entries.get(help_id)
        base = dict(current) if isinstance(current, dict) else {}
        base.update(seed_entry)
        merged_entries[help_id] = base
    payload = {
        "registry_version": "1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "scripts/seed_ui_help_registry.py",
        "seed_note": "Seeded UI help registry. Re-run after documentation updates; existing manual entries are preserved and seeded entries are refreshed from this script.",
        "seeded_entry_count": len(SEED_ENTRIES),
        "total_entry_count": len(merged_entries),
        "entries": merged_entries,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    target_payload = {
        "manifest_version": "1",
        "generated_utc": payload["generated_utc"],
        "generator": "scripts/seed_ui_help_registry.py",
        "note": "Current required UI help IDs. Tighten this list as tooltip coverage expands.",
        "required_help_ids": sorted(merged_entries.keys()),
    }
    TARGET_MANIFEST_PATH.write_text(json.dumps(target_payload, indent=2), encoding="utf-8")
    print(f"{OUT_PATH} | seeded={len(SEED_ENTRIES)} total={len(merged_entries)}")


if __name__ == "__main__":
    main()
