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
    $ScratchRoot = Join-Path $env:TEMP "mole_rel_$stamp"
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

    Invoke-Step "Run release gate" {
        Invoke-Native -FilePath $python -ArgumentList @("MOLE_code\mole_release_gate.py", "--root", ".", "--outdir", "RELEASES\clean_release_workflow", "--strict-hash") -WorkingDirectory $workspace
        Add-StepResult -Name "release_gate" -Status "PASS" -Detail "Release gate completed with strict hashes."
    }

    Invoke-Step "Collect release artifacts" {
        $sourceArtifacts = Join-Path $workspace "RELEASES\clean_release_workflow"
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
