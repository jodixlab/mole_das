MOLE-DAS Runtime Package - Quick Start
======================================

Deployment basis:
  - Workspace / deployment: 2026_04_07_001
  - Package refresh date: 2026-04-07
  - Runtime lineage basis: 2026_03_24_002
  - Runtime identity: MOLE DAS v10.0.25A - SIM Training Foundations
  - Validated runtime target: Python 3.12 x64

Standard operator startup:
  1. Run INSTALL_MOLE_DAS.bat if MOLE_code\.venv is missing or stale.
  2. Launch MOLE_code\run_wizard_console.bat for normal setup and acceptance testing.
  3. Create or load the session in the Wizard.
  4. Save + Apply Config.
  5. Use one of the two standard launch buttons:
       - DAQ Runner (Test)
       - DAQ Runner (SIM)

Current session intent policy:
  - Diagnostics-only OFF:
      The buttons above launch the full formal DAQ Runner.
      This path supports the full operator UI, QA/QC worksteps, FTIR, graphs,
      report pack generation, and the formal evidence model.
  - Diagnostics-only ON:
      The same buttons launch the diagnostics-only shell.
      Compliance support is disabled automatically.

Current diagnostics behavior:
  - Uses the same Wizard session content as the formal runner.
  - Includes live pollutant display, mass-rate display, live graphs, weather,
    fuel basis, Method 19 operator inputs, diagnostics verification,
    trim panel, and diagnostics print panel.
  - Excludes formal compliance support, report-pack generation,
    QA/QC console use as institutional record, and Method 2 / STACK_MEASURED input UI.
  - Uses Method 19 only in diagnostics mode.
  - Shows a startup responsibility notice that must be confirmed before proceeding.
  - Requires documented pre-test and post-test verification in diagnostics mode
    when project pollutant limits are entered.

Important operating rule:
  - Diagnostics output is non-compliance only.
  - It is excluded from the formal QA/QC trending and institutional-record path.
  - In diagnostics mode, FAIL wording is reserved for limit or calibration-limit
    gate conditions only.

Carried-forward active runtime surfaces:
  - Formal runner exports continue to write derived operator artifacts,
    including `exports\records.csv` and report-pack outputs.
  - Normalization-aware runner status remains available, including O2-corrected
    state handling in the live runner path.
  - Live mass-rate surfaces remain active, including VOC-as-propane-equivalent
    labeling where the current workflow uses that basis.
  - FTIR ingest, spike recovery, shared method/spec evaluation, and ASTM D3588
    fuel-analysis reporting remain carried forward in this package.

Recommended launchers:
  - Wizard normal:   MOLE_code\run_wizard.bat
  - Wizard console:  MOLE_code\run_wizard_console.bat
  - Wizard training: MOLE_code\run_wizard_training.bat
  - Direct runner troubleshooting only:
      MOLE_code\run_daq_runner_console.bat

Minimum build / release checks:
  - python -m py_compile MOLE_code\mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py
  - python -m py_compile MOLE_code\mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py
  - python MOLE_code\mole_smoketest.py --root .
  - MOLE_code\run_release_gate.bat

Package troubleshooting:
  - If the venv points at a removed Python install, delete MOLE_code\.venv
    and rerun INSTALL_MOLE_DAS.bat.
  - Use the console launcher first when troubleshooting startup or UI errors.
  - Logs are written under mole_das_data\logs.

Documentation entry points:
  - docs\MOLE_DAS_v10_0_25A_PACKAGE_REFRESH_2026_04_07_RELEASE_BULLETIN.md
  - docs\FEATURE_PORT_AUDIT_2026_04_07.md
  - docs\work_instructions\README.md
  - docs\MOLE_DAS_TECHNICAL_AND_OPERATING_MANUAL_2026_03_12.md
  - docs\MOLE_DAS_CALCULATIONS_FORMULAS_AND_METHODOLOGIES_APPENDIX_2026_03_12.md
  - docs\MOLE_DAS_TERMS_DEFINITIONS_AND_REFERENCES_2026_03_12.md
  - docs\MOLE_DAS_FTIR_SIDE_BY_SIDE_SIMPLE_WORKFLOW_2026_03_25.md
  - docs\MOLE_DAS_v7_7_4_REDEPLOY_FULL_20260318_0909_RELEASE_BULLETIN.md
