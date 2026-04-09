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
