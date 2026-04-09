# Feature Port Audit - 2026_04_07_001

Date: 2026-04-07

## Scope

Audit target:
- `2026_04_07_001`

Comparison sources reviewed:
- `archived_2026_04_07\2026_03_24_002`
- `archived_2026_04_07\2026_03_18_001`
- `archived_2026_04_07\2026_03_12_003\MOLE_DAS_v7_7_4_PORTABLE`
- `archived_2026_04_07\archived_code\MOLE_DAS_v10_0_25A_HK5_CSV_EXPORTS_RUNTIME_READY_FULL_DATA`
- `archived_2026_04_07\archived_code\MOLE_DAS_v10_0_25A_HK6_O2CORR_PPM_ONLY_RUNTIME_READY_FULL_DATA`
- `archived_2026_04_07\MOLE_DAS_v10_0_25A_HK7B_MASS_RATE_VOC_PROPANE_RUNTIME_READY_FULL_DATA`

Audit method:
- compared active code/docs/config structure against the March 24 baseline and later HK-series runtime packages
- checked archived release bulletin claims against current source/docs
- checked package metadata and operator-facing docs for release drift

## Summary

Result:
- `2026_04_07_001` appears to be a functional superset of the March 24 runtime for the tracked code/docs/config surface.
- I did not find evidence that the major March release features were dropped.
- I did find two packaging/documentation issues that should be treated as real audit findings.

Remediation status after package refresh:
- `BUILD_MANIFEST.json` was regenerated during the package refresh.
- Package-facing docs were refreshed to describe the carried-forward runtime surfaces.
- `mole_smoketest.py` passed.
- `mole_release_gate.py --strict-hash` passed and produced a certified ZIP plus release certificate.
- Remaining packaging boundary:
  three historical session-export files were unreadable OneDrive placeholder artifacts
  and were skipped with warning during certified ZIP creation.

## What Is Present

Evidence that the major March release capabilities were carried forward:
- FTIR MG2000 PRN ingest is present in `MOLE_code/mole_ftir_reference_v1.py`.
- FTIR method-driven spike recovery remains present in `MOLE_code/mole_spike_recovery_v1.py`.
- Shared method/spec engine remains present under `MOLE_code/mole_method_spec_engine`.
- Derived live NOx and converter-efficiency workflow logic remain present in `MOLE_code/mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py`.
- Diagnostics-only workflow, Documents Library entrypoint, live graphs, static artifacts, trim panel, and diagnostics print panel remain represented in the active docs and runtime.
- ASTM D3588 fuel-analysis handling and report-pack fuel summary outputs remain present.

Evidence that later HK-series features also appear to be present in code:
- CSV export utility remains present in `MOLE_code/mole_csv_export_v1.py`.
- Active runner still writes `records.csv` under `exports`.
- Active runner still exposes O2-corrected status text.
- Active runner still includes live mass-rate UI.
- Active runner still labels VOC as propane-equivalent in the mass-rate surface.

## Findings

### 1. BUILD_MANIFEST is stale for the active package

`BUILD_MANIFEST.json` in `2026_04_07_001` still reports:
- `generated_at = 2026-03-24T15:46:07.386769+00:00`
- `file_count = 5268`

That does not match the current April 7 package contents. The active package now contains later files that are not represented in the manifest, including examples such as:
- `docs/FEATURE_PORT_AUDIT_2026_04_07.md`
- `docs/MOLE_DAS_COMMERCIAL_MANUAL_ARCHITECTURE_AND_ENHANCEMENT_PLAN_2026_03_27.md`
- `docs/work_instructions/mole_das_operator_workflow_2026_04_06_001.txt`
- `docs/work_instructions/mole_das_diagnostics_only_appendix_2026_04_06_001.txt`
- `figures/mole_das_architecture_and_data_mapping_2026_04_02.vsdx`
- `MOLE_code/mole_method_spec_engine/method19_calc.py`
- `MOLE_code/mole_ui_text_registry.py`

Impact:
- package hash/accountability is no longer trustworthy for the current deliverable
- release provenance is ambiguous
- any future audit based on the manifest could incorrectly conclude that current files were never shipped

Status:
- remediated during the April 7 package refresh

### 2. Package-facing docs do not fully advertise later HK-series features that are present in code

I found later hotfix-era capabilities in the active codebase, but I did not find matching coverage in the main package-facing docs (`README_FIRST.txt`, `PORTABLE_PACKAGE_NOTES.txt`, and the top-level markdown docs set).

Examples present in code:
- CSV export path: `records.csv`
- O2-corrected status display: `O2corr: ...`
- live mass-rate section
- VOC-as-propane-equivalent label: `VOC (C3H8)`

Impact:
- operators/reviewers may assume these features were not carried forward
- auditability is reduced even when the feature is actually present
- acceptance testing can miss valid surfaces because the docs no longer point at them

Status:
- remediated during the April 7 package refresh

## Comparison Notes

March 24 baseline comparison:
- tracked active code/docs/config files covered all tracked baseline files
- no baseline-core tracked files were missing from the active package
- the active package contains additional docs, work instructions, figures, method/spec files, and updated runtime code

HK5/HK6/HK7B comparison:
- the active runtime contains newer and larger versions of the overlapping core runner/wizard/report files
- the active runtime still contains feature signatures for CSV export, O2-corrected handling, mass-rate display, VOC, and propane support
- some old standalone helper scripts present in archived HK packages are not present as separate files in the active package, but current docs and launch model indicate the package has intentionally consolidated around the Wizard and DAQ Runner workflow

## Recommended Actions

1. Regenerate `BUILD_MANIFEST.json` from the actual `2026_04_07_001` contents.
2. Run the current package verification flow again after manifest regeneration:
   `mole_smoketest.py` and `run_release_gate.bat`.
3. Update the package-facing docs to explicitly mention the later carried-forward features if they are intended to remain operator-visible:
   CSV exports, O2-corrected view/state, and VOC/propane mass-rate handling.
4. If those HK-series features are intentionally internal-only, state that explicitly in the docs to avoid future ambiguity.

## Bottom Line

The active package does not look like it lost the important March-era or HK-series runtime capabilities. The original audit findings were release metadata drift and feature-documentation drift, not obvious feature loss, and both of those findings have now been closed in the refreshed package.
