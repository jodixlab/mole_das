# MOLE DAS Terms, Definitions, and References

Document revised: 2026-04-01  
Deployment basis: `2026_03_24_002`

## 1. Key Terms

### Analyzer validity

Current validity rollup used by the runner and related logic:

- `VALID`
- `DEGRADED`
- `INVALID`

### Diagnostics Runner

The diagnostics-only shell that opens when `Diagnostics-only` is enabled and the operator launches `DAQ Runner (Test)` or `DAQ Runner (SIM)`.

### Diagnostics Verification

The diagnostics-only technician attestation workflow that records pre-test and post-test verification status, operator identity, worksheet reference, gas IDs, and notes.

<!-- HELP_ID: wizard.session_intent.diagnostics_only -->
### Diagnostics-only

Wizard session-intent flag that routes the runner launch buttons into the diagnostics-only shell and disables compliance support.

### Documents Library

Wizard tab that resolves and opens the newest companion document in each packaged document family.

### F-factor

Combustion-gas-volume-to-heat-input factor used by the build's Method 19-based crosswalk.

### Formal Runner

The full DAQ Runner environment used when `Diagnostics-only` is not enabled.

### FTIR side-by-side

The formal comparison workflow using the Wizard plus the formal DAQ Runner. It is not a diagnostics-shell workflow.

### Method 19 crosswalk

The build's fuel/heat-input/exhaust-flow helper relationship used in runner displays and mass-rate support.

### Method 2 / STACK_MEASURED

The stack-measured operator path that exists in the formal runner context but is excluded from diagnostics mode in the current build.

### Non-compliance artifact

A diagnostics-only output that is intentionally excluded from the formal QA/QC and institutional-record path.

### Raw / Dry / Corr

The three main live concentration views:

- `Raw`
- `Dry`
- `Corr`

### Release gate

The runtime verification process invoked by `MOLE_code\run_release_gate.bat`.

### Trim Panel

Read-only combustion advisory panel fed from current runner state, site conditions, Method 19 reference logic, and pollutant state.

## 2. Current Policy Definitions

<!-- HELP_ID: wizard.session_intent.may_support_compliance -->
### Compliance support

A session posture in which the formal runner and downstream QA/QC/report features are intended to support formal project execution.

### Diagnostics policy

Current diagnostics policy means:

- no compliance support
- no formal report-pack path
- no institutional-record status
- Method 19 only
- verification gate required when project pollutant limits are entered

### FAIL wording rule in diagnostics

In diagnostics mode, `FAIL` is reserved for limit-related or calibration-limit-related meaning. General runtime status uses neutral wording such as `ALERT`, `OFFLINE`, and `ERROR`.

## 3. Current Document Family

Primary operator/build references in this deployment:

- `README_FIRST.txt`
- `PORTABLE_PACKAGE_NOTES.txt`
- `docs/MOLE_DAS_TECHNICAL_AND_OPERATING_MANUAL_2026_03_12.md`
- `docs/MOLE_DAS_CALCULATIONS_FORMULAS_AND_METHODOLOGIES_APPENDIX_2026_03_12.md`
- `docs/MOLE_DAS_v7_7_4_REDEPLOY_FULL_20260318_0909_RELEASE_BULLETIN.md`
- `docs/MOLE_DAS_FTIR_SIDE_BY_SIDE_SIMPLE_WORKFLOW_2026_03_25.md`

## 4. Core Runtime References

Primary Wizard module:

- `MOLE_code/mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py`

Primary Runner module:

- `MOLE_code/mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py`

Primary quick verification tool:

- `MOLE_code/mole_smoketest.py`

Primary release-gate launcher:

- `MOLE_code/run_release_gate.bat`

## 5. Operational Reference Notes

- Start in the Wizard.
- Use the Documents Library tab as the in-app document shelf.
- Use the formal runner for FTIR side-by-side work.
- Use diagnostics for engineering/operator troubleshooting, not institutional truth.
