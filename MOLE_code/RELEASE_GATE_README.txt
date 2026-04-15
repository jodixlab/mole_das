MOLE-DAS Release Gate (v10.0.24D)
================================

Purpose
  Generate a deterministic, "certified" runtime ZIP from a working MOLE-DAS folder.
  Prevents regressions caused by missing assets, bad imports, syntax errors, or
  packaging drift.

How to run (Windows)
  1) Open the MOLE_code folder.
  2) Double-click:
       run_release_gate.bat

What you get
  A new folder will be created at:
     <root>\RELEASES\

  It will contain:
    - v10.0.24D_MOLE_DAS_<timestamp>_RUNTIME_READY_FULL_DATA.zip
    - RELEASE_CERT_<timestamp>.txt
    - RELEASE_CERT_<timestamp>.json

Notes
  - The packager excludes the RELEASES folder so builds don't recursively include
    prior artifacts.
  - Use run_release_gate_console.bat for CI / non-interactive execution.
  - For a clean-machine release candidate run, use:
      <root>\RUN_CLEAN_RELEASE_WORKFLOW.bat
    This copies tracked files into a fresh workspace, installs the runtime,
    runs unit tests + smoketest integration, then runs the release gate.
  - The clean workflow also emits a production acceptance matrix and
    operator go / no-go checklist into:
      <root>\RELEASES\clean_release_workflow\
  - The clean workflow also emits:
      dependency_manifest.txt / .json
      release_bundle_summary.md / .json
      release_artifact_contract.md / .json
      release_go_no_go_decision.md / .json
  - The release gate now also emits a package hygiene report and fails
    if the runtime ZIP contains banned paths or absolute local path
    drift in packaged config/runtime text files.
  - Use:
      <root>\RUN_RELEASE_DECISION_GATE.bat
    for the single final release decision entrypoint before field use.
