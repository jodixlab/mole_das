param(
    [Parameter(Mandatory = $true)]
    [string]$ArtifactDir,

    [string]$RepoRoot = (Join-Path $PSScriptRoot ".."),
    [string]$BackupRoot = "C:\Users\User\OneDrive - Encino Environmental Services, LLC\mole_development\executables",
    [switch]$Force
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

function Copy-And-Verify {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    $sourceHash = Get-Sha256 -Path $Source
    $destinationHash = Get-Sha256 -Path $Destination
    return [ordered]@{
        source = $Source
        destination = $Destination
        source_sha256 = $sourceHash
        destination_sha256 = $destinationHash
        match = ($sourceHash -eq $destinationHash)
    }
}

$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$artifact = (Resolve-Path -LiteralPath $ArtifactDir).Path
$backupRootPath = $BackupRoot
New-Item -ItemType Directory -Force -Path $backupRootPath | Out-Null

$decisionPath = Join-Path $artifact "release_go_no_go_decision.json"
$contractPath = Join-Path $artifact "release_artifact_contract.json"
$recipientPath = Join-Path $artifact "RECIPIENT_VALIDATION_FROM_INSTALLER.json"
$verifiedPath = Join-Path $artifact "latest_verified_release_v1.json"
$handoffPath = Join-Path $artifact "APPROVED_RELEASE_HANDOFF.md"
$tagPath = Join-Path $artifact "GIT_RELEASE_TAG.txt"
Require-File -Path $decisionPath -Description "Go/no-go decision"
Require-File -Path $contractPath -Description "Artifact contract"
Require-File -Path $recipientPath -Description "Recipient validation summary"
Require-File -Path $verifiedPath -Description "Latest verified release manifest"
Require-File -Path $handoffPath -Description "Approved release handoff"
Require-File -Path $tagPath -Description "Git release tag metadata"

$decision = Read-Json -Path $decisionPath
$contract = Read-Json -Path $contractPath
$recipient = Read-Json -Path $recipientPath
$verified = Read-Json -Path $verifiedPath

if (("$($decision.status)".Trim().ToUpperInvariant()) -ne "PASS" -or ("$($decision.overall_decision)".Trim().ToUpperInvariant()) -ne "GO") {
    throw "Release is not approved for promotion. status=$($decision.status) overall=$($decision.overall_decision)"
}
if (("$($contract.status)".Trim().ToUpperInvariant()) -ne "PASS") {
    throw "Artifact contract is not PASS: $($contract.status)"
}
if (("$($recipient.status)".Trim().ToUpperInvariant()) -ne "PASS") {
    throw "Recipient installer validation is not PASS: $($recipient.status)"
}

$packageLabel = "$($verified.package_label)".Trim()
$gitCommitShort = "$($verified.git_commit)".Trim()
if (-not $packageLabel) {
    throw "latest_verified_release_v1.json does not contain package_label"
}
if (-not $gitCommitShort) {
    throw "latest_verified_release_v1.json does not contain git_commit"
}

$tagName = "release/$packageLabel"
$tagCommit = Invoke-GitText -Repo $repo -Args @("rev-list", "-n", "1", $tagName)
$expectedCommit = Invoke-GitText -Repo $repo -Args @("rev-parse", $gitCommitShort)
if ($tagCommit -ne $expectedCommit) {
    throw "Git tag mismatch. $tagName points to $tagCommit, expected $expectedCommit"
}
$tagObject = Invoke-GitText -Repo $repo -Args @("rev-parse", $tagName)

$installerZip = "$($verified.installer_bundle_path)".Trim()
$portableZip = "$($verified.portable_bundle_path)".Trim()
$runtimeZip = (Get-ChildItem -LiteralPath $artifact -Filter "*_RUNTIME_READY_FULL_DATA.zip" | Select-Object -First 1).Name
if (-not $installerZip) {
    throw "latest_verified_release_v1.json missing installer_bundle_path"
}
if (-not $portableZip) {
    throw "latest_verified_release_v1.json missing portable_bundle_path"
}
if (-not $runtimeZip) {
    throw "Runtime ZIP not found in artifact directory"
}

$primaryFiles = @(
    $installerZip,
    $portableZip,
    $runtimeZip,
    "APPROVED_RELEASE_HANDOFF.md",
    "GIT_RELEASE_TAG.txt",
    "release_go_no_go_decision.json",
    "release_artifact_contract.json",
    "release_artifact_contract.md",
    "release_bundle_summary.json",
    "release_bundle_summary.md",
    "RECIPIENT_VALIDATION_FROM_INSTALLER.json",
    "RECIPIENT_VALIDATION_FROM_INSTALLER.md",
    "recipient_wizard_startup__latest.json",
    "recipient_diagnostics_snapshot_manifest.json",
    "clean_release_summary.json",
    "clean_release_summary.txt",
    "latest_verified_release_v1.json",
    "latest_verified_release_v1.signature.json"
)
foreach ($file in $primaryFiles) {
    Require-File -Path (Join-Path $artifact $file) -Description "Primary promotion file $file"
}

$backupDir = Join-Path $backupRootPath ([System.IO.Path]::GetFileName($artifact))
if ((Test-Path -LiteralPath $backupDir) -and -not $Force) {
    throw "Backup destination already exists: $backupDir. Re-run with -Force to replace it."
}
if (Test-Path -LiteralPath $backupDir) {
    $resolvedBackup = (Resolve-Path -LiteralPath $backupDir).Path
    $resolvedRoot = (Resolve-Path -LiteralPath $backupRootPath).Path
    if (-not $resolvedBackup.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove backup outside backup root: $resolvedBackup"
    }
    Remove-Item -LiteralPath $backupDir -Recurse -Force
}

Copy-Item -LiteralPath $artifact -Destination $backupDir -Recurse -Force

$fileResults = @()
foreach ($file in $primaryFiles) {
    $source = Join-Path $artifact $file
    $dest = Join-Path $backupDir $file
    $sourceHash = Get-Sha256 -Path $source
    $destHash = Get-Sha256 -Path $dest
    $fileResults += [ordered]@{
        name = $file
        source = $source
        destination = $dest
        sha256 = $sourceHash
        backup_sha256 = $destHash
        match = ($sourceHash -eq $destHash)
    }
}
$mismatches = @($fileResults | Where-Object { -not $_.match })
if ($mismatches.Count -gt 0) {
    throw "Backup hash verification failed for $($mismatches.Count) primary files."
}

$installerHash = Get-Sha256 -Path (Join-Path $artifact $installerZip)
$portableHash = Get-Sha256 -Path (Join-Path $artifact $portableZip)
$runtimeHash = Get-Sha256 -Path (Join-Path $artifact $runtimeZip)
$latestPointer = [ordered]@{
    schema = "mole_latest_approved_release_pointer_v1"
    package_label = $packageLabel
    artifact_dir = $artifact
    backup_dir = $backupDir
    git_commit = $gitCommitShort
    git_commit_full = $expectedCommit
    git_tag = $tagName
    git_tag_object = $tagObject
    approved_status = $decision.status
    overall_decision = $decision.overall_decision
    approved_by = $decision.final_release_decision.approved_by
    approved_date = $decision.final_release_decision.date
    clean_workflow_status = "PASS"
    artifact_contract_status = $contract.status
    recipient_validation_status = $recipient.status
    installer_zip = $installerZip
    installer_sha256 = $installerHash
    portable_zip = $portableZip
    portable_sha256 = $portableHash
    runtime_zip = $runtimeZip
    runtime_sha256 = $runtimeHash
    generated_local = (Get-Date).ToString("s")
}
$latestMd = @(
    "# Latest Approved MOLE-DAS Release",
    "",
    "- Package: ``$packageLabel``",
    "- Status: ``$($decision.status) / $($decision.overall_decision)``",
    "- Commit: ``$gitCommitShort``",
    "- Tag: ``$tagName``",
    "- Tag object: ``$tagObject``",
    "- Artifact directory: ``$artifact``",
    "- Backup directory: ``$backupDir``",
    "- Installer SHA256: ``$installerHash``"
)

$latestJsonPath = Join-Path $repo "RELEASES\LATEST_APPROVED_RELEASE.json"
$latestMdPath = Join-Path $repo "RELEASES\LATEST_APPROVED_RELEASE.md"
Write-Utf8NoBom -Path $latestJsonPath -Text ($latestPointer | ConvertTo-Json -Depth 10)
Write-Utf8NoBom -Path $latestMdPath -Text ($latestMd -join [Environment]::NewLine)

$backupLatestJson = Join-Path $backupRootPath "LATEST_APPROVED_RELEASE.json"
$backupLatestMd = Join-Path $backupRootPath "LATEST_APPROVED_RELEASE.md"
$latestCopyResults = @(
    (Copy-And-Verify -Source $latestJsonPath -Destination $backupLatestJson),
    (Copy-And-Verify -Source $latestMdPath -Destination $backupLatestMd)
)
$summary = [ordered]@{
    schema = "mole_release_backup_promotion_summary_v1"
    status = "PASS"
    generated_local = (Get-Date).ToString("s")
    artifact_dir = $artifact
    backup_dir = $backupDir
    backup_root = $backupRootPath
    package_label = $packageLabel
    git_commit = $gitCommitShort
    git_commit_full = $expectedCommit
    git_tag = $tagName
    git_tag_object = $tagObject
    release_decision = $decision.status
    overall_decision = $decision.overall_decision
    artifact_contract_status = $contract.status
    recipient_validation_status = $recipient.status
    primary_file_results = $fileResults
    latest_pointer_results = $latestCopyResults
}
$summaryMd = @(
    "# MOLE-DAS Release Backup Promotion",
    "",
    "- Status: ``PASS``",
    "- Package: ``$packageLabel``",
    "- Commit: ``$gitCommitShort``",
    "- Tag: ``$tagName``",
    "- Artifact directory: ``$artifact``",
    "- Backup directory: ``$backupDir``",
    "- Primary files verified: ``$($fileResults.Count)``",
    "",
    "## Primary Hashes",
    "",
    "- Installer: ``$installerHash``",
    "- Portable: ``$portableHash``",
    "- Runtime: ``$runtimeHash``"
)

$summaryJsonPath = Join-Path $artifact "PROMOTION_TO_BACKUP_SUMMARY.json"
$summaryMdPath = Join-Path $artifact "PROMOTION_TO_BACKUP_SUMMARY.md"
Write-Utf8NoBom -Path $summaryJsonPath -Text ($summary | ConvertTo-Json -Depth 20)
Write-Utf8NoBom -Path $summaryMdPath -Text ($summaryMd -join [Environment]::NewLine)
$backupSummaryJson = Join-Path $backupDir "PROMOTION_TO_BACKUP_SUMMARY.json"
$backupSummaryMd = Join-Path $backupDir "PROMOTION_TO_BACKUP_SUMMARY.md"
Copy-Item -LiteralPath $summaryJsonPath -Destination $backupSummaryJson -Force
Copy-Item -LiteralPath $summaryMdPath -Destination $backupSummaryMd -Force

Write-Host "Release backup promotion PASS"
Write-Host "Package: $packageLabel"
Write-Host "Backup: $backupDir"
Write-Host "Summary: $summaryJsonPath"
