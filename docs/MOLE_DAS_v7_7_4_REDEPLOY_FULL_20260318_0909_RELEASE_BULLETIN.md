# MOLE DAS Release Bulletin

Document revised: 2026-04-01  
Deployment basis: `2026_03_24_002`  
Runtime identity: `MOLE DAS v10.0.25A - SIM Training Foundations`

## 1. Release Position

This bulletin reflects the current portable runtime state, not the older pre-diagnostics redeploy state implied by the historical filename.

The current build standard is:

- Wizard is the authoritative entrypoint.
- Only two normal operator launch paths are used:
  - `DAQ Runner (Test)`
  - `DAQ Runner (SIM)`
- `Diagnostics-only` changes the shell behind those same two buttons.

## 2. Major Current Capabilities

### 2.1 Formal DAQ Runner

With `Diagnostics-only` unchecked, the runner remains the full formal operator environment with:

- live pollutant display
- mass-rate display
- live graphs
- QA/QC worksteps
- FTIR reference/audit module
- report pack generation
- formal evidence capture
- test matrix / run controls

### 2.2 Diagnostics Runner

With `Diagnostics-only` checked, the same two runner launch buttons open the diagnostics-only shell instead of the formal runner.

Current diagnostics-only shell includes:

- live pollutant display
- mass-rate display
- live graphs
- weather/site conditions
- fuel basis and Method 19 reference
- Method 19 operator inputs / derived outputs
- trim panel
- diagnostics print panel
- diagnostics verification / technician attestation

Current diagnostics-only shell excludes:

- compliance support
- report-pack generation
- formal QA/QC console use as institutional record
- Method 2 / `STACK_MEASURED` operator input workflow

Diagnostics mode is now Method 19 only.

## 3. Policy Changes in the Current Build

### 3.1 Session-intent policy

- `Diagnostics-only` and `May Support Compliance` are mutually exclusive.
- If `Diagnostics-only` is enabled, compliance support is turned off automatically.

### 3.2 Diagnostics responsibility controls

- Diagnostics startup shows a responsibility notice that must be confirmed.
- If project pollutant limits are entered, diagnostics acquisition requires documented pre-test verification.
- If project pollutant limits are entered, diagnostics export requires documented post-test verification.
- Diagnostics artifacts explicitly state that technician-performed calibration verification before and after testing is the condition of use.

### 3.3 Diagnostics wording standard

- In diagnostics mode, `FAIL` is reserved for limit-related or calibration-limit-related conditions.
- General runtime health/comms/acquisition wording is now neutral:
  - `ALERT`
  - `OFFLINE`
  - `ERROR`

## 4. Documentation Changes

The packaged documentation set now aligns to the current workflow standard:

- Wizard includes a `Documents Library` tab that resolves the newest document in each companion-document family.
- Root package notes and startup guidance were refreshed.
- The FTIR simple workflow document was restored for operator use.
- The release bulletin, manual set, and package notes are expected to be updated in-place in this deployment lineage rather than split across stale filenames.

## 5. Current Build / Release Gate Standard

Minimum verification for a candidate package or runtime update:

```powershell
python -m py_compile MOLE_code\mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py
python -m py_compile MOLE_code\mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py
python MOLE_code\mole_smoketest.py --root .
MOLE_code\run_release_gate.bat
```

Expected result:

- compile checks pass
- smoketest reports `OK: No issues detected.`
- release gate passes or passes with warnings only when those warnings are understood and accepted

## 6. Operational Notes

- Use `MOLE_code\run_wizard_console.bat` for troubleshooting and acceptance testing.
- If the packaged `.venv` is stale, rebuild it with `INSTALL_MOLE_DAS.bat`.
- Diagnostics is for engineering/operator reference and troubleshooting. It is not a substitute for the formal compliance support path.
- FTIR side-by-side work should be run in the formal runner path, not diagnostics.

## 7. Current Known Boundaries

- Diagnostics artifacts do not enter the formal QA/QC evidence model.
- Diagnostics exports are intentionally segregated from report-pack generation and institutional recordkeeping.
- Binary document companions such as `.docx` forms may lag the markdown/text reference docs if not revised in the same patch cycle.
