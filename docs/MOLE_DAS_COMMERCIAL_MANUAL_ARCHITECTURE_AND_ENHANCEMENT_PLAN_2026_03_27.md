# MOLE DAS Commercial Manual Architecture and Enhancement Plan

Document revised: 2026-04-01  
Deployment basis: `2026_03_24_002`

## 1. Purpose

This document defines the current recommended documentation architecture around the live MOLE DAS build.

It is not the operator manual itself. It is the plan for keeping the operator-facing documentation set coherent as the runtime evolves.

## 2. Current Documentation Architecture

The current packaged document family should be treated as:

- package startup guidance
- technical/operator manual
- calculations/methodology appendix
- terms/references appendix
- release bulletin
- FTIR companion workflow/forms

The Wizard `Documents Library` tab is now the in-app front door to that set.

## 3. Current Documentation Standard

The document family should reflect these runtime truths:

- Wizard is the authoritative entrypoint.
- Only two normal operator runner launch buttons exist.
- `Diagnostics-only` changes those same buttons into diagnostics-only launch paths.
- Diagnostics is Method 19 only.
- Diagnostics is non-compliance and excluded from the formal record path.
- FTIR side-by-side work belongs in the formal runner path.
- Build verification includes compile, smoketest, and release gate.

## 4. Recommended Document Family

### 4.1 Primary operator-facing docs

- `README_FIRST.txt`
- `PORTABLE_PACKAGE_NOTES.txt`
- `MOLE_DAS_TECHNICAL_AND_OPERATING_MANUAL_2026_03_12.md`
- `MOLE_DAS_v7_7_4_REDEPLOY_FULL_20260318_0909_RELEASE_BULLETIN.md`

### 4.2 Supporting reference docs

- `MOLE_DAS_CALCULATIONS_FORMULAS_AND_METHODOLOGIES_APPENDIX_2026_03_12.md`
- `MOLE_DAS_TERMS_DEFINITIONS_AND_REFERENCES_2026_03_12.md`

### 4.3 Workflow companions

- `MOLE_DAS_FTIR_SIDE_BY_SIDE_SIMPLE_WORKFLOW_2026_03_25.md`
- `MOLE_DAS_FTIR_SIDE_BY_SIDE_FIELD_FORM_1PAGE_2026_03_25.md`
- `MOLE_DAS_FTIR_SIDE_BY_SIDE_FIELD_DATA_COLLECTION_TABLE_2026_03_25.md`
- `MOLE_DAS_FTIR_SIDE_BY_SIDE_FIELD_DATA_TEMPLATE_2026_03_25.csv`

## 5. Documentation Gaps to Avoid

Avoid these failure modes:

- stale filenames being mistaken for stale content
- docs describing old runner launch models
- docs treating diagnostics as compliance-capable
- docs describing Method 2 availability in diagnostics
- docs omitting the diagnostics verification gate
- docs omitting build verification standards

## 6. Recommended Next Documentation Enhancements

- Create a dedicated troubleshooting appendix keyed to Wizard, formal runner, and diagnostics runner.
- Add screenshot callouts for:
  - Documents Library
  - Diagnostics Verification
  - Diagnostics Print Panel
  - Trim Panel
- Update the binary `.docx` field form when the markdown companion changes materially.
- Add a short release checklist that explicitly includes document review before package cut.
