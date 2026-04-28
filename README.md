# mole_das
MOLE-DAS Data Acquisition System

## Release validation
- Local clean-workspace validation: [RUN_CLEAN_RELEASE_WORKFLOW.bat](RUN_CLEAN_RELEASE_WORKFLOW.bat)
- PowerShell entrypoint: [scripts/run_clean_release_workflow.ps1](scripts/run_clean_release_workflow.ps1)
- Packaged installer acceptance runner: [scripts/run_packaged_acceptance.ps1](scripts/run_packaged_acceptance.ps1)
- Executable bundle builder now runs packaged acceptance by default: [scripts/build_windows_executable_bundle.ps1](scripts/build_windows_executable_bundle.ps1)
- UI help coverage audit: [scripts/audit_ui_help_registry.py](scripts/audit_ui_help_registry.py)
- UI help doc update pack: [scripts/build_ui_help_doc_update_pack.py](scripts/build_ui_help_doc_update_pack.py)
- UI help doc source manifest: [config/mole_ui_help_doc_sources_v1.json](config/mole_ui_help_doc_sources_v1.json)
- UI help doc sync state: [config/mole_ui_help_doc_sync_state_v1.json](config/mole_ui_help_doc_sync_state_v1.json)
- GitHub Actions workflow: [.github/workflows/clean-release-validation.yml](.github/workflows/clean-release-validation.yml)
- Acceptance matrix source: [config/mole_release_acceptance_matrix_v1.json](config/mole_release_acceptance_matrix_v1.json)
- Release artifact contract source: [config/mole_release_artifact_contract_v1.json](config/mole_release_artifact_contract_v1.json)
- Final release gate entrypoint: [RUN_RELEASE_DECISION_GATE.bat](RUN_RELEASE_DECISION_GATE.bat)
- Generated release checklist artifacts appear under `RELEASES/clean_release_workflow/`
- Generated clean-workspace ZIP, release cert, and package hygiene reports also appear under `RELEASES/clean_release_workflow/`
- Generated executable bundle ZIPs and packaged-acceptance summaries also appear under `RELEASES/clean_release_workflow/`
- The canonical verified release channel manifest `latest_verified_release_v1.json` is emitted with executable bundle builds and copied into `RELEASES/clean_release_workflow/`
- The executable bundle builder also emits `PACKAGE_VERSION_AUDIT.json` and `PACKAGE_VERSION_AUDIT.txt`, and the clean release workflow copies both into `RELEASES/clean_release_workflow/`
- Portable and installer bundle ZIPs are now distinct payloads: the portable ZIP contains the direct-run shareable payload without installer scripts, while the installer ZIP contains the curated root install package
- Dependency manifests, release bundle summary, and release artifact contract are also emitted under `RELEASES/clean_release_workflow/`
- Final go/no-go decision artifacts are emitted under `RELEASES/clean_release_workflow/`
- UI help release artifacts now also include a coverage audit and a documentation update review pack under `RELEASES/clean_release_workflow/`
