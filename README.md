# mole_das
MOLE-DAS Data Acquisition System

## Release validation
- Local clean-workspace validation: [RUN_CLEAN_RELEASE_WORKFLOW.bat](RUN_CLEAN_RELEASE_WORKFLOW.bat)
- PowerShell entrypoint: [scripts/run_clean_release_workflow.ps1](scripts/run_clean_release_workflow.ps1)
- GitHub Actions workflow: [.github/workflows/clean-release-validation.yml](.github/workflows/clean-release-validation.yml)
- Acceptance matrix source: [config/mole_release_acceptance_matrix_v1.json](config/mole_release_acceptance_matrix_v1.json)
- Generated release checklist artifacts appear under `RELEASES/clean_release_workflow/`
- Generated clean-workspace ZIP, release cert, and package hygiene reports also appear under `RELEASES/clean_release_workflow/`
