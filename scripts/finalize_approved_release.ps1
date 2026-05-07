param(
    [Parameter(Mandatory = $true)]
    [string]$ArtifactDir,

    [Parameter(Mandatory = $true)]
    [string]$ApprovedBy,

    [Parameter(Mandatory = $true)]
    [string]$ApprovalBasis,

    [string]$RepoRoot = (Join-Path $PSScriptRoot ".."),
    [string]$BackupRoot = "C:\Users\User\OneDrive - Encino Environmental Services, LLC\mole_development\executables",
    [string]$Notes = "",
    [string]$Decision = "GO",
    [string]$ApprovalDate = "",
    [string]$ReleaseTag = "",
    [switch]$ForceTag,
    [switch]$ForceBackup
)

$ErrorActionPreference = "Stop"

function Read-Json {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Text
    )

    $dir = Split-Path -Parent $Path
    if ($dir) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $utf8NoBom)
}

function Require-File {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Description
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Description missing: $Path"
    }
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

function Invoke-GitText {
    param(
        [Parameter(Mandatory = $true)][string]$Repo,
        [Parameter(Mandatory = $true)][string[]]$Args
    )

    $output = & git -C $Repo @Args
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Args -join ' ') failed with exit code $LASTEXITCODE"
    }
    return (($output | Select-Object -First 1) -as [string]).Trim()
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
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

function Refresh-ArtifactContract {
    param(
        [Parameter(Mandatory = $true)][string]$Repo,
        [Parameter(Mandatory = $true)][string]$Artifact,
        [Parameter(Mandatory = $true)][string]$Python
    )

    Invoke-Native -FilePath $Python -ArgumentList @(
        (Join-Path $Repo "scripts\build_release_artifact_contract.py"),
        "--repo-root", $Repo,
        "--output-dir", $Artifact,
        "--summary-json", (Join-Path $Artifact "clean_release_summary.json"),
        "--python-exe", $Python
    ) -WorkingDirectory $Repo
}

$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$artifact = (Resolve-Path -LiteralPath $ArtifactDir).Path
$python = Join-Path $repo "MOLE_code\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

$verifiedPath = Join-Path $artifact "latest_verified_release_v1.json"
$decisionPath = Join-Path $artifact "release_go_no_go_decision.json"
$contractPath = Join-Path $artifact "release_artifact_contract.json"
$recipientPath = Join-Path $artifact "RECIPIENT_VALIDATION_FROM_INSTALLER.json"
Require-File -Path $verifiedPath -Description "Latest verified release manifest"
Require-File -Path $decisionPath -Description "Go/no-go decision"
Require-File -Path $contractPath -Description "Artifact contract"
Require-File -Path $recipientPath -Description "Recipient validation summary"

$verified = Read-Json -Path $verifiedPath
$packageLabel = "$($verified.package_label)".Trim()
$gitCommitShort = "$($verified.git_commit)".Trim()
if (-not $packageLabel) {
    throw "latest_verified_release_v1.json does not contain package_label"
}
if (-not $gitCommitShort) {
    throw "latest_verified_release_v1.json does not contain git_commit"
}
if (-not $ReleaseTag) {
    $ReleaseTag = "release/$packageLabel"
}

$expectedCommit = Invoke-GitText -Repo $repo -Args @("rev-parse", $gitCommitShort)
$installerZip = "$($verified.installer_bundle_path)".Trim()
$portableZip = "$($verified.portable_bundle_path)".Trim()
$runtimeZip = (Get-ChildItem -LiteralPath $artifact -Filter "*_RUNTIME_READY_FULL_DATA.zip" | Select-Object -First 1).Name
Require-File -Path (Join-Path $artifact $installerZip) -Description "Installer ZIP"
Require-File -Path (Join-Path $artifact $portableZip) -Description "Portable ZIP"
Require-File -Path (Join-Path $artifact $runtimeZip) -Description "Runtime ZIP"

Write-Host "Applying operator signoff..."
$signoffArgs = @(
    (Join-Path $repo "scripts\apply_release_operator_signoff.py"),
    "--artifact-dir", $artifact,
    "--approved-by", $ApprovedBy,
    "--approval-basis", $ApprovalBasis,
    "--decision", $Decision,
    "--notes", $Notes
)
if ($ApprovalDate) {
    $signoffArgs += @("--date", $ApprovalDate)
}
Invoke-Native -FilePath $python -ArgumentList $signoffArgs -WorkingDirectory $repo

$decisionAfter = Read-Json -Path $decisionPath
if (("$($decisionAfter.status)".Trim().ToUpperInvariant()) -ne "PASS" -or ("$($decisionAfter.overall_decision)".Trim().ToUpperInvariant()) -ne "GO") {
    throw "Release decision is not PASS/GO after signoff. status=$($decisionAfter.status) overall=$($decisionAfter.overall_decision)"
}

Write-Host "Creating or verifying release tag..."
$tagExists = $false
try {
    $existingTagCommit = Invoke-GitText -Repo $repo -Args @("rev-list", "-n", "1", $ReleaseTag)
    $tagExists = $true
}
catch {
    $existingTagCommit = ""
    $tagExists = $false
}
if ($tagExists -and $existingTagCommit -ne $expectedCommit) {
    if (-not $ForceTag) {
        throw "Tag $ReleaseTag points to $existingTagCommit, expected $expectedCommit. Re-run with -ForceTag to replace it."
    }
    Invoke-Native -FilePath "git" -ArgumentList @("-C", $repo, "tag", "-d", $ReleaseTag) -WorkingDirectory $repo
    & git -C $repo push origin ":refs/tags/$ReleaseTag"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to delete remote tag $ReleaseTag"
    }
    $tagExists = $false
}
if (-not $tagExists) {
    Invoke-Native -FilePath "git" -ArgumentList @("-C", $repo, "tag", "-a", $ReleaseTag, $expectedCommit, "-m", "Approve $packageLabel") -WorkingDirectory $repo
    Invoke-Native -FilePath "git" -ArgumentList @("-C", $repo, "push", "origin", $ReleaseTag) -WorkingDirectory $repo
}
$tagObject = Invoke-GitText -Repo $repo -Args @("rev-parse", $ReleaseTag)
$tagCommit = Invoke-GitText -Repo $repo -Args @("rev-list", "-n", "1", $ReleaseTag)
if ($tagCommit -ne $expectedCommit) {
    throw "Tag $ReleaseTag points to $tagCommit after finalization, expected $expectedCommit"
}

Write-Host "Writing handoff and tag metadata..."
$installerHash = Get-Sha256 -Path (Join-Path $artifact $installerZip)
$portableHash = Get-Sha256 -Path (Join-Path $artifact $portableZip)
$runtimeHash = Get-Sha256 -Path (Join-Path $artifact $runtimeZip)
$contract = Read-Json -Path $contractPath
$recipient = Read-Json -Path $recipientPath
$handoffLines = @(
    "# MOLE-DAS Approved Release Handoff",
    "",
    "- Package: ``$packageLabel``",
    "- Status: ``$($decisionAfter.status) / $($decisionAfter.overall_decision)``",
    "- Commit: ``$gitCommitShort``",
    "- Tag: ``$ReleaseTag``",
    "- Tag object: ``$tagObject``",
    "- Artifact directory: ``$artifact``",
    "",
    "## Release Gates",
    "",
    "- Clean release workflow: ``PASS``",
    "- Packaged acceptance: ``PASS``",
    "- Recipient installer validation: ``$($recipient.status)``",
    "- Artifact contract: ``$($contract.status)``",
    "- Go/no-go decision: ``$($decisionAfter.status) / $($decisionAfter.overall_decision)``",
    "",
    "## Primary Artifacts",
    "",
    "- Installer ZIP: ``$installerZip``",
    "- Installer SHA256: ``$installerHash``",
    "- Portable ZIP: ``$portableZip``",
    "- Portable SHA256: ``$portableHash``",
    "- Runtime ZIP: ``$runtimeZip``",
    "- Runtime SHA256: ``$runtimeHash``"
)
$tagLines = @(
    "Tag: $ReleaseTag",
    "Tag object: $tagObject",
    "Commit: $expectedCommit",
    "Package: $packageLabel"
)
Write-Utf8NoBom -Path (Join-Path $artifact "APPROVED_RELEASE_HANDOFF.md") -Text ($handoffLines -join [Environment]::NewLine)
Write-Utf8NoBom -Path (Join-Path $artifact "GIT_RELEASE_TAG.txt") -Text ($tagLines -join [Environment]::NewLine)

Write-Host "Refreshing artifact contract..."
Refresh-ArtifactContract -Repo $repo -Artifact $artifact -Python $python

Write-Host "Promoting to backup..."
$promotionArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $repo "scripts\promote_approved_release_to_backup.ps1"),
    "-ArtifactDir", $artifact,
    "-RepoRoot", $repo,
    "-BackupRoot", $BackupRoot
)
if ($ForceBackup) {
    $promotionArgs += "-Force"
}
Invoke-Native -FilePath "powershell.exe" -ArgumentList $promotionArgs -WorkingDirectory $repo

$promotionSummaryPath = Join-Path $artifact "PROMOTION_TO_BACKUP_SUMMARY.json"
Require-File -Path $promotionSummaryPath -Description "Promotion summary"
$promotion = Read-Json -Path $promotionSummaryPath

$finalSummary = [ordered]@{
    schema = "mole_final_release_summary_v1"
    status = "PASS"
    generated_local = (Get-Date).ToString("s")
    artifact_dir = $artifact
    backup_dir = $promotion.backup_dir
    package_label = $packageLabel
    git_commit = $gitCommitShort
    git_commit_full = $expectedCommit
    git_tag = $ReleaseTag
    git_tag_object = $tagObject
    approved_by = $ApprovedBy
    release_decision = $decisionAfter.status
    overall_decision = $decisionAfter.overall_decision
    artifact_contract_status = (Read-Json -Path $contractPath).status
    recipient_validation_status = $recipient.status
    promotion_status = $promotion.status
    installer_sha256 = $installerHash
    portable_sha256 = $portableHash
    runtime_sha256 = $runtimeHash
}
$finalLines = @(
    "# MOLE-DAS Final Release Summary",
    "",
    "- Status: ``PASS``",
    "- Package: ``$packageLabel``",
    "- Commit: ``$gitCommitShort``",
    "- Tag: ``$ReleaseTag``",
    "- Artifact directory: ``$artifact``",
    "- Backup directory: ``$($promotion.backup_dir)``",
    "- Decision: ``$($decisionAfter.status) / $($decisionAfter.overall_decision)``",
    "- Promotion: ``$($promotion.status)``",
    "",
    "## Primary Hashes",
    "",
    "- Installer: ``$installerHash``",
    "- Portable: ``$portableHash``",
    "- Runtime: ``$runtimeHash``"
)
$finalJsonPath = Join-Path $artifact "FINAL_RELEASE_SUMMARY.json"
$finalMdPath = Join-Path $artifact "FINAL_RELEASE_SUMMARY.md"
Write-Utf8NoBom -Path $finalJsonPath -Text ($finalSummary | ConvertTo-Json -Depth 12)
Write-Utf8NoBom -Path $finalMdPath -Text ($finalLines -join [Environment]::NewLine)
Copy-Item -LiteralPath $finalJsonPath -Destination (Join-Path $promotion.backup_dir "FINAL_RELEASE_SUMMARY.json") -Force
Copy-Item -LiteralPath $finalMdPath -Destination (Join-Path $promotion.backup_dir "FINAL_RELEASE_SUMMARY.md") -Force

Write-Host "Final release PASS"
Write-Host "Package: $packageLabel"
Write-Host "Artifact: $artifact"
Write-Host "Backup: $($promotion.backup_dir)"
Write-Host "Summary: $finalJsonPath"
