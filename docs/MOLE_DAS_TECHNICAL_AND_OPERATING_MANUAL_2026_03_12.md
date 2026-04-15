# MOLE DAS Technical and Operating Manual

Document revised: 2026-04-01  
Deployment basis: `2026_03_24_002`  
Runtime identity: `MOLE DAS v10.0.25A - SIM Training Foundations`

## 1. Purpose

This manual describes the current MOLE DAS operating model as implemented in the active portable runtime.

It covers:

- package startup
- Wizard workflow
- formal DAQ Runner workflow
- diagnostics workflow
- FTIR boundary
- artifact and build standards

This is build-specific operating guidance. Governing methods, permits, and source-specific procedures remain controlling.

## 2. System Layers

### 2.1 Wizard

Primary file:

- `MOLE_code/mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py`

Primary role:

- create or load the session
- enforce session-intent policy
- capture source, pollutant, QA/QC, site, fuel, regulatory, FTIR, and runner config
- launch the runner
- host the Documents Library tab

### 2.2 DAQ Runner

Primary file:

- `MOLE_code/mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py`

Primary role:

- acquire or simulate data
- display pollutant and mass-rate data
- run QA/QC worksteps
- support FTIR comparison
- generate artifacts appropriate to the active mode

### 2.3 Data and evidence root

Primary root:

- `mole_das_data/`

Primary content:

- sessions
- training sessions
- DBs
- logs
- configs
- exports

### 2.4 Documentation root

Primary root:

- `docs/`

Operator reference access:

- direct file access under `docs/`
- Wizard `Documents Library` tab

## 3. Startup Standard

Recommended startup:

```powershell
cd D:\codex_environ\2026_03_24_002\2026_03_24_002
.\INSTALL_MOLE_DAS.bat
.\MOLE_code\run_wizard_console.bat
```

Use the console launcher for troubleshooting and acceptance testing because it exposes tracebacks.

Validated runtime target:

- Python 3.12 x64

Practical note:

- If `MOLE_code\.venv` points to a removed Python install, rebuild the venv and rerun the installer.

## 3.1 Recovery and Support Capture

<!-- HELP_ID: runner.recovery.export_support_bundle -->
The current build preserves recovery snapshots, database backups, and support-bundle export actions so recoverable state and field-support evidence can be captured before or after a runtime failure.

## 4. Current Operator Workflow

## 4.1 Wizard-first workflow

The Wizard is the authoritative operating front end.

Current sequence:

1. Launch the Wizard.
<!-- HELP_ID: wizard.actions.load_existing_config -->
2. Create or load the session.
3. Complete source details.
4. Complete pollutants, QA/QC, site, fuel, regulatory, and FTIR settings as applicable.
5. Set session intent.
<!-- HELP_ID: wizard.actions.save_apply -->
6. Save + Apply Config.
7. Launch the runner from the Wizard.

## 4.2 Session-intent policy

The current build has one important intent split:

- `Diagnostics-only`
- `May Support Compliance`

Current rule:

- These are mutually exclusive.
- If `Diagnostics-only` is enabled, compliance support is disabled automatically.

## 4.3 Runner launch model

Only two standard launch paths are used:

- `DAQ Runner (Test)`
- `DAQ Runner (SIM)`

Those two buttons behave as follows:

- `Diagnostics-only` unchecked:
  launches the full formal runner
- `Diagnostics-only` checked:
  launches the diagnostics-only shell

This design is intentional so operators do not have to choose among separate formal and diagnostic buttons.

## 5. Formal DAQ Runner

When `Diagnostics-only` is off, the runner is the full formal operator environment.

Current formal-runner capabilities include:

- live pollutant table with raw, dry, and corrected views
- live mass-rate table
- live graphs
- run controls
- QA/QC worksteps
- FTIR reference/audit panel
- test matrix / reporting controls
- formal evidence outputs
- report-pack generation

Use the formal runner for:

- compliance support sessions
- FTIR side-by-side field work
- full QA/QC capture
- formal report artifacts

## 6. Diagnostics Runner

When `Diagnostics-only` is on, the same two runner launch buttons open the diagnostics-only shell.

Current diagnostics capabilities:

- live pollutant display
- live mass-rate display
- live graphs
- weather/site conditions
- fuel basis and combustion reference
- Method 19 operator inputs / derived outputs
- trim panel
- diagnostics verification panel
- diagnostics print panel

Current diagnostics restrictions:

- non-compliance only
- excluded from formal QA/QC recordkeeping
- excluded from report-pack generation
- excluded from institutional-record status
- Method 2 / `STACK_MEASURED` operator workflow is disabled
- diagnostics uses Method 19 only

## 6.1 Diagnostics responsibility controls

Diagnostics startup now presents a responsibility notice that must be confirmed.

The diagnostics artifact language and the startup notice are intentionally aligned:

- technician/operator is responsible for linearity / calibration verification before and after testing
- diagnostics output depends on the technician performing those steps

## 6.2 Diagnostics verification workflow

If project pollutant limits are entered:

- pre-test verification is required before diagnostics acquisition starts
- post-test verification is required before diagnostics export

If project pollutant limits are not entered:

- the diagnostics verification path remains advisory

## 6.3 Diagnostics wording standard

In diagnostics mode:

- `FAIL` is reserved for calibration-limit or limit-exceedance meaning
- general runtime wording uses neutral labels such as:
  - `ALERT`
  - `OFFLINE`
  - `ERROR`

## 7. Fuel, Crosswalk, and Mass-Rate Standard

The current build supports Wizard fuel-analysis capture plus source-backed defaults.

The current operator flow is:

1. review or capture fuel analysis in the Wizard
2. save the session
3. use the runner's Method 19 crosswalk and derived views

Important build rule:

- diagnostics mode is Method 19 only
- diagnostics mode excludes the Method 2 / stack-measured operator path

## 8. FTIR Boundary

FTIR side-by-side work belongs in the formal runner path.

Current FTIR notes:

- use the formal runner, not diagnostics
- configure FTIR in the Wizard
- use the FTIR side-by-side companion docs from the Documents Library
- retain MOLE and FTIR artifacts together for later alignment and audit support

## 9. Artifact Model

### 9.1 Formal sessions

Formal sessions can generate:

- raw evidence
- QA/QC captures
- FTIR evidence
- report pack outputs
- deterministic session artifacts

### 9.2 Diagnostics sessions

Diagnostics sessions can generate:

- diagnostics verification metadata
- diagnostics text/PDF snapshot exports
- diagnostics trim / advisory outputs

Diagnostics artifacts are intentionally segregated from the formal report-pack path.

## 10. Documents Library

The Wizard now contains a `Documents Library` tab.

Current behavior:

- scans the packaged document roots
- resolves the newest file in each document family
- provides one-click open actions for operator reference

This is the recommended in-app reference shelf for operators and technicians.

## 11. Build and Release Standards

Minimum verification standard:

```powershell
python -m py_compile MOLE_code\mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py
python -m py_compile MOLE_code\mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py
python MOLE_code\mole_smoketest.py --root .
MOLE_code\run_release_gate.bat
```

Expected baseline:

- compile passes
- smoketest reports no issues
- release gate passes or only emits understood warnings

## 12. Practical Troubleshooting Notes

- Use console launchers first when debugging.
- If startup fails, check `mole_das_data/logs`.
- If a packaged venv is stale, rebuild it instead of trying to patch around it.
- If a runner artifact repeats labels such as `Status: Status: READY`, that is a formatting defect and should be fixed in the snapshot builder, not in the underlying UI state variable.
