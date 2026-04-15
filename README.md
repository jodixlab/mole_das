# mole_das
MOLE-DAS Data Acquisition System

## Release validation
- Local clean-workspace validation: [RUN_CLEAN_RELEASE_WORKFLOW.bat](RUN_CLEAN_RELEASE_WORKFLOW.bat)
- PowerShell entrypoint: [scripts/run_clean_release_workflow.ps1](scripts/run_clean_release_workflow.ps1)
- UI help coverage audit: [scripts/audit_ui_help_registry.py](scripts/audit_ui_help_registry.py)
- GitHub Actions workflow: [.github/workflows/clean-release-validation.yml](.github/workflows/clean-release-validation.yml)
- Acceptance matrix source: [config/mole_release_acceptance_matrix_v1.json](config/mole_release_acceptance_matrix_v1.json)
- Release artifact contract source: [config/mole_release_artifact_contract_v1.json](config/mole_release_artifact_contract_v1.json)
- Final release gate entrypoint: [RUN_RELEASE_DECISION_GATE.bat](RUN_RELEASE_DECISION_GATE.bat)
- Generated release checklist artifacts appear under `RELEASES/clean_release_workflow/`
- Generated clean-workspace ZIP, release cert, and package hygiene reports also appear under `RELEASES/clean_release_workflow/`
- Dependency manifests, release bundle summary, and release artifact contract are also emitted under `RELEASES/clean_release_workflow/`
- Final go/no-go decision artifacts are emitted under `RELEASES/clean_release_workflow/`
