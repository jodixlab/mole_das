# MOLE DAS FTIR Side-by-Side Simple Workflow

Document revised: 2026-04-01  
Deployment basis: `2026_03_24_002`

## 1. Use Boundary

This workflow is for formal side-by-side field work using the Wizard plus the formal DAQ Runner.

Do not use the diagnostics shell for FTIR side-by-side comparison work. Diagnostics mode is non-compliance and excludes the formal evidence and report path.

## 2. Required Companion Assets

Use these together:

- `MOLE_DAS_FTIR_SIDE_BY_SIDE_FIELD_FORM_1PAGE_2026_03_25.md`
- `MOLE_DAS_FTIR_SIDE_BY_SIDE_FIELD_DATA_COLLECTION_TABLE_2026_03_25.md`
- `MOLE_DAS_FTIR_SIDE_BY_SIDE_FIELD_DATA_TEMPLATE_2026_03_25.csv`

## 3. Startup

1. Launch `MOLE_code\run_wizard_console.bat`.
2. Create or load the project session.
3. Leave `Diagnostic-only` unchecked.
4. Configure the source, pollutants, QA/QC, site, fuel, and FTIR settings.
5. Save + Apply Config.
6. Launch `DAQ Runner (Test)` or `DAQ Runner (SIM)` as appropriate.

## 4. Wizard Configuration Checklist

Before launching the runner, verify:

- source details are complete
- pollutants are selected and mapped
- QA/QC settings are complete
- site conditions are configured
- fuel analysis is reviewed or confirmed
- FTIR is enabled
- FTIR role is set correctly:
  - `AUDIT` when FTIR is part of the comparison / evaluation workflow
  - `REFERENCE` when FTIR is informational only
- FTIR method is selected for the project basis
- FTIR file path or watch folder is set

## 5. Field Workflow

### 5.1 Warmup and ready state

1. Power FTIR and allow it to stabilize.
2. Power MOLE and allow it to stabilize.
3. Confirm tee installation, branch valve arrangement, and safe vent routing.
4. Confirm timing alignment notes between FTIR and MOLE systems.

### 5.2 Pre-project calibration

1. Perform the required ambient purge / zero / span sequence.
2. Record the times and gas IDs on the field form.
3. Confirm O2 behavior during purge where applicable.

### 5.3 Acquisition

1. Start acquisition in the formal runner.
2. Verify live pollutant display, FTIR panel, and run state.
3. Record run start/stop times for both systems.
4. Record any bias-valve events and timestamp markers.
5. Record notes on drift, stability, purge transitions, and unusual operating conditions.

### 5.4 Between-run activities

1. Perform required purge steps.
2. Record purge start/stop and O2 behavior.
3. Confirm FTIR ingest freshness and file progression.

### 5.5 Post-project verification

1. Perform the post-project drift / post-cal sequence.
2. Record gas used, measured response, and operator notes.
3. Confirm the MOLE session folder and FTIR exports are retained.

## 6. Artifact Standard

Minimum expected retained artifacts:

- MOLE session directory
- FTIR project export or `.prn` source set
- field form / field table
- timestamp alignment notes
- pre-project calibration evidence
- post-project drift evidence

## 7. Current Build Notes

- The Wizard Documents Library tab should be treated as the operator reference shelf for the newest companion docs.
- Diagnostics mode is not the correct shell for FTIR side-by-side execution.
- The formal runner remains the authoritative path for FTIR comparison, QA/QC, and downstream report artifacts.
