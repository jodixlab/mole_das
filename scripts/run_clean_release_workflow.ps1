param(
    [string]$RepoRoot = (Join-Path $PSScriptRoot ".."),
    [string]$ScratchRoot = "",
    [string]$ArtifactOutDir = "",
    [switch]$KeepScratch
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Script
    )
    Write-Host ""
    Write-Host "==> $Name"
    & $Script
}

function Invoke-Native {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory
    )
    Push-Location $WorkingDirectory
    try {
        & $FilePath @ArgumentList
        if ($LASTEXITCODE -ne 0) {
            throw "$FilePath exited with code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

$repo = (Resolve-Path $RepoRoot).Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
if (-not $ScratchRoot) {
    $scratchBase = Join-Path $env:SystemDrive "temp"
    New-Item -ItemType Directory -Path $scratchBase -Force | Out-Null
    $ScratchRoot = Join-Path $scratchBase "mrel_$stamp"
}
if (-not $ArtifactOutDir) {
    $ArtifactOutDir = Join-Path $repo "RELEASES\clean_release_workflow"
}

$scratch = $ScratchRoot
$workspace = Join-Path $scratch "workspace"
$artifactDir = $ArtifactOutDir
$summaryPath = Join-Path $artifactDir "clean_release_summary.json"
$summaryTxtPath = Join-Path $artifactDir "clean_release_summary.txt"

$summary = [ordered]@{
    schema = "mole_clean_release_workflow_v1"
    started_at = (Get-Date).ToUniversalTime().ToString("o")
    repo_root = $repo
    scratch_root = $scratch
    workspace = $workspace
    artifact_dir = $artifactDir
    steps = @()
    status = "RUNNING"
}

$bundleLabel = "MOLE_DAS_REL_$stamp"
$bundleRoot = Join-Path $scratch "bundle"
$releaseOutDir = Join-Path $workspace "RELEASES\clean_release_workflow"

function Add-StepResult {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Detail
    )
    $summary.steps += [ordered]@{
        name = $Name
        status = $Status
        detail = $Detail
        at = (Get-Date).ToUniversalTime().ToString("o")
    }
}

if (Test-Path $scratch) {
    Remove-Item -LiteralPath $scratch -Recurse -Force
}
New-Item -ItemType Directory -Path $workspace -Force | Out-Null
New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null

try {
    Invoke-Step "Copy tracked files into clean workspace" {
        $tracked = git -C $repo ls-files
        if ($LASTEXITCODE -ne 0) {
            throw "git ls-files failed"
        }
        foreach ($rel in $tracked) {
            if (-not $rel) { continue }
            $src = Join-Path $repo $rel
            $dst = Join-Path $workspace $rel
            $dstDir = Split-Path -Parent $dst
            if (-not (Test-Path $dstDir)) {
                New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
            }
            Copy-Item -LiteralPath $src -Destination $dst -Force
        }
        Add-StepResult -Name "copy_tracked_files" -Status "PASS" -Detail "Tracked repository files copied into clean workspace."
    }

    Invoke-Step "Install runtime in clean workspace" {
        Invoke-Native -FilePath "cmd.exe" -ArgumentList @("/c", "INSTALL_MOLE_DAS.bat", "--nopause") -WorkingDirectory $workspace
        Add-StepResult -Name "install_runtime" -Status "PASS" -Detail "INSTALL_MOLE_DAS.bat completed in clean workspace."
    }

    $python = Join-Path $workspace "MOLE_code\.venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "Clean workspace runtime missing: $python"
    }

    Invoke-Step "Run unit suite" {
        Invoke-Native -FilePath $python -ArgumentList @("-m", "unittest", "discover", "-s", "MOLE_code\mole_method_spec_engine\tests", "-p", "test_*_v1.py") -WorkingDirectory $workspace
        Add-StepResult -Name "unit_tests" -Status "PASS" -Detail "Unit discovery suite passed."
    }

    Invoke-Step "Run launcher/report integration smoketest" {
        Invoke-Native -FilePath $python -ArgumentList @("MOLE_code\mole_smoketest.py", "--root", ".", "--integration-launcher-report-pack") -WorkingDirectory $workspace
        Add-StepResult -Name "smoketest" -Status "PASS" -Detail "Smoketest with launcher/report integration passed."
    }

    Invoke-Step "Run UI help registry audit" {
        New-Item -ItemType Directory -Path $releaseOutDir -Force | Out-Null
        $uiHelpAuditJson = Join-Path $releaseOutDir "ui_help_audit.json"
        $uiHelpAuditTxt = Join-Path $releaseOutDir "ui_help_audit.txt"
        $auditRaw = & $python "scripts\audit_ui_help_registry.py"
        if ($LASTEXITCODE -ne 0) {
            throw "scripts\\audit_ui_help_registry.py failed with exit code $LASTEXITCODE"
        }
        $auditText = ($auditRaw | Out-String).Trim()
        Set-Content -LiteralPath $uiHelpAuditJson -Value $auditText -Encoding UTF8
        try {
            $auditObj = $auditText | ConvertFrom-Json
            $auditLines = @(
                "MOLE-DAS UI Help Audit"
                "Status: $($auditObj.status)"
                "Bound IDs: $($auditObj.bound_id_count)"
                "Registry IDs: $($auditObj.registry_id_count)"
                "Target IDs: $($auditObj.target_id_count)"
                "Missing registry entries: $([int]($auditObj.missing_registry_entries | Measure-Object).Count)"
                "Target missing bound entries: $([int]($auditObj.target_missing_bound_entries | Measure-Object).Count)"
                "Entries missing doc refs: $([int]($auditObj.entries_missing_doc_refs | Measure-Object).Count)"
            )
            Set-Content -LiteralPath $uiHelpAuditTxt -Value ($auditLines -join [Environment]::NewLine) -Encoding UTF8
        }
        catch {
            Set-Content -LiteralPath $uiHelpAuditTxt -Value $auditText -Encoding UTF8
        }
        Add-StepResult -Name "ui_help_audit" -Status "PASS" -Detail "UI help registry audit passed."
    }

    Invoke-Step "Run release gate" {
        Invoke-Native -FilePath $python -ArgumentList @("MOLE_code\mole_release_gate.py", "--root", ".", "--outdir", "RELEASES\clean_release_workflow", "--strict-hash") -WorkingDirectory $workspace
        Add-StepResult -Name "release_gate" -Status "PASS" -Detail "Release gate completed with strict hashes."
    }

    Invoke-Step "Build Windows executable bundle" {
        $gitCommit = (git -C $repo rev-parse --short HEAD | Select-Object -First 1).Trim()
        $gitBranch = (git -C $repo rev-parse --abbrev-ref HEAD | Select-Object -First 1).Trim()
        Invoke-Native -FilePath "powershell.exe" -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", "scripts\build_windows_executable_bundle.ps1",
            "-RepoRoot", ".",
            "-OutputRoot", $bundleRoot,
            "-BundleLabel", $bundleLabel,
            "-GitCommit", $gitCommit,
            "-GitBranch", $gitBranch
        ) -WorkingDirectory $workspace

        $installerZip = Join-Path $bundleRoot ($bundleLabel + "_installer_exe_bundle.zip")
        $portableZip = Join-Path $bundleRoot ($bundleLabel + "_portable_exe_bundle.zip")
        $verifiedReleaseManifest = Join-Path $bundleRoot "latest_verified_release_v1.json"
        $verifiedReleaseSignature = Join-Path $bundleRoot "latest_verified_release_v1.signature.json"
        $releaseSigningPublicKey = Join-Path $bundleRoot "mole_release_signing_public_key_v1.json"
        $versionAuditJson = Join-Path $bundleRoot "PACKAGE_VERSION_AUDIT.json"
        $versionAuditTxt = Join-Path $bundleRoot "PACKAGE_VERSION_AUDIT.txt"
        $upgradeReportPreviewJson = Join-Path $bundleRoot "UPGRADE_REPORT_PREVIEW.json"
        $upgradeReportPreviewTxt = Join-Path $bundleRoot "UPGRADE_REPORT_PREVIEW.txt"
        $rollbackReportPreviewJson = Join-Path $bundleRoot "ROLLBACK_REPORT_PREVIEW.json"
        $rollbackReportPreviewTxt = Join-Path $bundleRoot "ROLLBACK_REPORT_PREVIEW.txt"
        if (-not (Test-Path -LiteralPath $installerZip)) {
            throw "Installer ZIP missing after bundle build: $installerZip"
        }
        if (-not (Test-Path -LiteralPath $portableZip)) {
            throw "Portable ZIP missing after bundle build: $portableZip"
        }
        if (-not (Test-Path -LiteralPath $verifiedReleaseManifest)) {
            throw "Verified release manifest missing after bundle build: $verifiedReleaseManifest"
        }
        if (-not (Test-Path -LiteralPath $verifiedReleaseSignature)) {
            throw "Verified release signature missing after bundle build: $verifiedReleaseSignature"
        }
        if (-not (Test-Path -LiteralPath $releaseSigningPublicKey)) {
            throw "Release signing public key missing after bundle build: $releaseSigningPublicKey"
        }
        if (-not (Test-Path -LiteralPath $versionAuditJson)) {
            throw "Package version audit JSON missing after bundle build: $versionAuditJson"
        }
        if (-not (Test-Path -LiteralPath $versionAuditTxt)) {
            throw "Package version audit text summary missing after bundle build: $versionAuditTxt"
        }
        if (-not (Test-Path -LiteralPath $upgradeReportPreviewJson)) {
            throw "Upgrade report preview JSON missing after bundle build: $upgradeReportPreviewJson"
        }
        if (-not (Test-Path -LiteralPath $upgradeReportPreviewTxt)) {
            throw "Upgrade report preview text summary missing after bundle build: $upgradeReportPreviewTxt"
        }
        if (-not (Test-Path -LiteralPath $rollbackReportPreviewJson)) {
            throw "Rollback report preview JSON missing after bundle build: $rollbackReportPreviewJson"
        }
        if (-not (Test-Path -LiteralPath $rollbackReportPreviewTxt)) {
            throw "Rollback report preview text summary missing after bundle build: $rollbackReportPreviewTxt"
        }

        $acceptanceArtifacts = Join-Path $bundleRoot "_acceptance_artifacts"
        $acceptanceJson = Join-Path $acceptanceArtifacts "packaged_acceptance_summary.json"
        $acceptanceTxt = Join-Path $acceptanceArtifacts "packaged_acceptance_summary.txt"
        if (-not (Test-Path -LiteralPath $acceptanceJson)) {
            throw "Packaged acceptance summary missing after bundle build: $acceptanceJson"
        }
        if (-not (Test-Path -LiteralPath $acceptanceTxt)) {
            throw "Packaged acceptance text summary missing after bundle build: $acceptanceTxt"
        }

        New-Item -ItemType Directory -Path $releaseOutDir -Force | Out-Null
        Copy-Item -LiteralPath $installerZip -Destination (Join-Path $releaseOutDir ([System.IO.Path]::GetFileName($installerZip))) -Force
        Copy-Item -LiteralPath $portableZip -Destination (Join-Path $releaseOutDir ([System.IO.Path]::GetFileName($portableZip))) -Force
        Copy-Item -LiteralPath $verifiedReleaseManifest -Destination (Join-Path $releaseOutDir "latest_verified_release_v1.json") -Force
        Copy-Item -LiteralPath $verifiedReleaseSignature -Destination (Join-Path $releaseOutDir "latest_verified_release_v1.signature.json") -Force
        Copy-Item -LiteralPath $releaseSigningPublicKey -Destination (Join-Path $releaseOutDir "mole_release_signing_public_key_v1.json") -Force
        Copy-Item -LiteralPath $versionAuditJson -Destination (Join-Path $releaseOutDir "PACKAGE_VERSION_AUDIT.json") -Force
        Copy-Item -LiteralPath $versionAuditTxt -Destination (Join-Path $releaseOutDir "PACKAGE_VERSION_AUDIT.txt") -Force
        Copy-Item -LiteralPath $upgradeReportPreviewJson -Destination (Join-Path $releaseOutDir "UPGRADE_REPORT_PREVIEW.json") -Force
        Copy-Item -LiteralPath $upgradeReportPreviewTxt -Destination (Join-Path $releaseOutDir "UPGRADE_REPORT_PREVIEW.txt") -Force
        Copy-Item -LiteralPath $rollbackReportPreviewJson -Destination (Join-Path $releaseOutDir "ROLLBACK_REPORT_PREVIEW.json") -Force
        Copy-Item -LiteralPath $rollbackReportPreviewTxt -Destination (Join-Path $releaseOutDir "ROLLBACK_REPORT_PREVIEW.txt") -Force
        Copy-Item -LiteralPath $acceptanceJson -Destination (Join-Path $releaseOutDir "packaged_acceptance_summary.json") -Force
        Copy-Item -LiteralPath $acceptanceTxt -Destination (Join-Path $releaseOutDir "packaged_acceptance_summary.txt") -Force
        $supportBundleDir = Join-Path $acceptanceArtifacts "support_bundles"
        if (Test-Path -LiteralPath $supportBundleDir) {
            Get-ChildItem -LiteralPath $supportBundleDir -Filter "*.zip" -ErrorAction SilentlyContinue | ForEach-Object {
                Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $releaseOutDir $_.Name) -Force
            }
        }

        Add-StepResult -Name "build_windows_executable_bundle" -Status "PASS" -Detail "Windows executable bundle built and packaged acceptance passed in clean workspace."
    }

    Invoke-Step "Collect release artifacts" {
        $sourceArtifacts = $releaseOutDir
        if (-not (Test-Path $sourceArtifacts)) {
            throw "Expected release artifact directory not found: $sourceArtifacts"
        }
        Get-ChildItem -LiteralPath $artifactDir -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null
        Get-ChildItem -LiteralPath $sourceArtifacts -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $artifactDir -Recurse -Force
        }
        Add-StepResult -Name "collect_artifacts" -Status "PASS" -Detail "Release artifacts copied back from clean workspace."
    }

    $summary.status = "PASS"
}
catch {
    $summary.status = "FAIL"
    Add-StepResult -Name "workflow_failure" -Status "FAIL" -Detail $_.Exception.Message
    throw
}
finally {
    function Write-SummaryFiles {
        $summary.finished_at = (Get-Date).ToUniversalTime().ToString("o")
        $summaryJson = $summary | ConvertTo-Json -Depth 6
        Set-Content -LiteralPath $summaryPath -Value $summaryJson -Encoding UTF8
        $summaryText = @(
            "MOLE-DAS Clean Release Workflow"
            "Status: $($summary.status)"
            "Repo: $repo"
            "Workspace: $workspace"
            "Artifacts: $artifactDir"
            ""
            "Steps:"
        )
        foreach ($step in $summary.steps) {
            $summaryText += "- $($step.name): $($step.status) :: $($step.detail)"
        }
        Set-Content -LiteralPath $summaryTxtPath -Value ($summaryText -join [Environment]::NewLine) -Encoding UTF8
    }

    Write-SummaryFiles

    try {
        $acceptanceScript = Join-Path $repo "scripts\build_release_acceptance_pack.py"
        if ((Test-Path $acceptanceScript) -and (Test-Path $python)) {
            Invoke-Native -FilePath $python -ArgumentList @(
                $acceptanceScript,
                "--repo-root", $repo,
                "--output-dir", $artifactDir,
                "--summary-json", $summaryPath
            ) -WorkingDirectory $repo
            Add-StepResult -Name "acceptance_pack" -Status "PASS" -Detail "Acceptance matrix and go/no-go checklist generated."
            Write-SummaryFiles
        }
    }
    catch {
        Add-StepResult -Name "acceptance_pack" -Status "FAIL" -Detail $_.Exception.Message
        $summary.status = "FAIL"
        Write-SummaryFiles
    }

    try {
        $docSyncScript = Join-Path $repo "scripts\build_ui_help_doc_update_pack.py"
        if ((Test-Path $docSyncScript) -and (Test-Path $python)) {
            Invoke-Native -FilePath $python -ArgumentList @(
                $docSyncScript,
                "--repo-root", $repo,
                "--output-dir", $artifactDir
            ) -WorkingDirectory $repo
            Add-StepResult -Name "ui_help_doc_update_pack" -Status "PASS" -Detail "UI help documentation update pack generated."
            Write-SummaryFiles
        }
    }
    catch {
        Add-StepResult -Name "ui_help_doc_update_pack" -Status "FAIL" -Detail $_.Exception.Message
        $summary.status = "FAIL"
        Write-SummaryFiles
    }

    try {
        $welcomeReviewScript = Join-Path $repo "scripts\build_welcome_asset_review_pack.py"
        if ((Test-Path $welcomeReviewScript) -and (Test-Path $python)) {
            Invoke-Native -FilePath $python -ArgumentList @(
                $welcomeReviewScript,
                "--repo-root", $repo,
                "--output-dir", $artifactDir
            ) -WorkingDirectory $repo
            Add-StepResult -Name "welcome_asset_review_pack" -Status "PASS" -Detail "Welcome asset manifest and review pack generated."
            Write-SummaryFiles
        }
    }
    catch {
        Add-StepResult -Name "welcome_asset_review_pack" -Status "FAIL" -Detail $_.Exception.Message
        $summary.status = "FAIL"
        Write-SummaryFiles
    }

    try {
        $artifactContractScript = Join-Path $repo "scripts\build_release_artifact_contract.py"
        if ((Test-Path $artifactContractScript) -and (Test-Path $python)) {
            Invoke-Native -FilePath $python -ArgumentList @(
                $artifactContractScript,
                "--repo-root", $repo,
                "--output-dir", $artifactDir,
                "--summary-json", $summaryPath,
                "--python-exe", $python
            ) -WorkingDirectory $repo
            Add-StepResult -Name "artifact_contract" -Status "PASS" -Detail "Release artifact contract, dependency manifest, and bundle summary generated."
            Write-SummaryFiles
        }
    }
    catch {
        Add-StepResult -Name "artifact_contract" -Status "FAIL" -Detail $_.Exception.Message
        $summary.status = "FAIL"
        Write-SummaryFiles
    }

    try {
        $decisionScript = Join-Path $repo "scripts\release_go_no_go_gate.py"
        if ((Test-Path $decisionScript) -and (Test-Path $python)) {
            Invoke-Native -FilePath $python -ArgumentList @(
                $decisionScript,
                "--artifact-dir", $artifactDir,
                "--allow-pending-operator"
            ) -WorkingDirectory $repo
            Add-StepResult -Name "go_no_go_gate" -Status "PASS" -Detail "Release go/no-go decision emitted."
            Write-SummaryFiles
        }
    }
    catch {
        Add-StepResult -Name "go_no_go_gate" -Status "FAIL" -Detail $_.Exception.Message
        $summary.status = "FAIL"
        Write-SummaryFiles
    }

    try {
        $artifactContractScript = Join-Path $repo "scripts\build_release_artifact_contract.py"
        if ((Test-Path $artifactContractScript) -and (Test-Path $python)) {
            Invoke-Native -FilePath $python -ArgumentList @(
                $artifactContractScript,
                "--repo-root", $repo,
                "--output-dir", $artifactDir,
                "--summary-json", $summaryPath,
                "--python-exe", $python
            ) -WorkingDirectory $repo
            Add-StepResult -Name "artifact_contract_finalize" -Status "PASS" -Detail "Release artifact contract refreshed after go/no-go decision."
            Write-SummaryFiles
        }
    }
    catch {
        Add-StepResult -Name "artifact_contract_finalize" -Status "FAIL" -Detail $_.Exception.Message
        $summary.status = "FAIL"
        Write-SummaryFiles
    }

    if ((-not $KeepScratch) -and (Test-Path $scratch)) {
        Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if ($summary.status -ne "PASS") {
    exit 1
}

Write-Host ""
Write-Host "Clean release workflow completed."
Write-Host "Artifacts: $artifactDir"
