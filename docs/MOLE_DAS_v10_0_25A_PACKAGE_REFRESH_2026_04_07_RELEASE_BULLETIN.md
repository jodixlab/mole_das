# MOLE DAS Package Refresh Release Bulletin

Date: 2026-04-07

## Package

- Package workspace: `2026_04_07_001`
- Runtime lineage basis: `2026_03_24_002`
- Runtime identity: `MOLE DAS v10.0.25A - SIM Training Foundations`
- Refresh purpose: package audit closeout, documentation refresh, and release-metadata cleanup

## What This Refresh Confirms

This April 7 package refresh did not identify a dropped core runtime capability from the March 18 / March 24 runtime line.

The active package continues to carry forward the major runtime families already established in the prior audited builds:

- Wizard-authoritative formal runner and diagnostics-only launch model
- FTIR ingest and method-driven audit workflow support
- spike recovery and shared method/spec evaluation
- diagnostics-only verification controls and non-compliance boundary
- live graphs, static artifacts, trim panel, and diagnostics print panel
- ASTM D3588 fuel-analysis handling and report-pack fuel outputs

## Carried-Forward HK-Series Runtime Surfaces

The active package codebase also continues to carry forward later hotfix-era runtime surfaces that were checked during the April 7 audit:

- derived CSV export path including `exports\records.csv`
- O2-corrected runtime status/display handling
- live mass-rate display surfaces
- VOC mass-rate labeling on a propane-equivalent basis where that workflow is in use

## Refresh Actions Completed In This Package

- package-facing startup and package notes were updated to match the active runtime surface
- this release bulletin was added to the packaged docs set
- the April 7 feature-port audit was saved into the package docs set
- release packaging logic was updated to exclude workspace-only artifacts such as:
  - `.git`
  - `.vs`
  - `.venv_stale`
  - office lock files
  - SQLite WAL / SHM sidecars
- `BUILD_MANIFEST.json` was brought back under active release control

## Current Documentation Front Door

Use these as the primary package-status entry points:

- `README_FIRST.txt`
- `PORTABLE_PACKAGE_NOTES.txt`
- `FEATURE_PORT_AUDIT_2026_04_07.md`
- `work_instructions\README.md`

Primary operating references remain:

- `MOLE_DAS_TECHNICAL_AND_OPERATING_MANUAL_2026_03_12.md`
- `MOLE_DAS_CALCULATIONS_FORMULAS_AND_METHODOLOGIES_APPENDIX_2026_03_12.md`
- `MOLE_DAS_TERMS_DEFINITIONS_AND_REFERENCES_2026_03_12.md`
- `MOLE_DAS_FTIR_SIDE_BY_SIDE_SIMPLE_WORKFLOW_2026_03_25.md`

## Verification

Verification completed from the active runtime:

- smoketest: `PASS`
- release gate: `PASS`
- strict asset hashes: `PASS`
- Python files compiled by release gate: `42`
- `BUILD_MANIFEST.json` was regenerated during the package refresh.

Certified outputs:

- The latest certified ZIP and release certificate are written under `RELEASES\`.
- Use the newest `RELEASE_CERT_*.txt` / `RELEASE_CERT_*.json` pair as the authoritative
  verification record for the current package.

Packaging boundary noted during certification:

- Three historical session-export files under `mole_das_data\sessions\...` were unreadable
  OneDrive placeholder artifacts at package time and were skipped with warning during
  certified ZIP creation.
