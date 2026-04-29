param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,

    [string]$BundleLabel = "MOLE_DAS_WINDOWS_EXE_BUNDLE",

    [string]$GitCommit = "",

    [string]$GitBranch = "",

    [switch]$SkipPackagedAcceptance
)

$ErrorActionPreference = "Stop"

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [string]$WorkingDirectory
    )
    if ($WorkingDirectory) {
        Push-Location $WorkingDirectory
    }
    try {
        & $FilePath @ArgumentList
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed ($LASTEXITCODE): $FilePath $($ArgumentList -join ' ')"
        }
    }
    finally {
        if ($WorkingDirectory) {
            Pop-Location
        }
    }
}

function Require-Path {
    param([string]$PathValue, [string]$Label)
    if (-not (Test-Path -LiteralPath $PathValue)) {
        throw "$Label not found: $PathValue"
    }
}

function Copy-TreeRobust {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $log = Join-Path $env:TEMP ("mole_robocopy_" + [guid]::NewGuid().ToString("N") + ".log")
    try {
        & robocopy $Source $Destination /E /NFL /NDL /NJH /NJS /NC /NS /NP /R:2 /W:1 /LOG:$log | Out-Null
        $code = $LASTEXITCODE
        if ($code -ge 8) {
            $detail = ""
            if (Test-Path -LiteralPath $log) {
                $detail = Get-Content -LiteralPath $log -Tail 40 | Out-String
            }
            throw "robocopy failed ($code) from $Source to $Destination`n$detail"
        }
    }
    finally {
        if (Test-Path -LiteralPath $log) {
            Remove-Item -LiteralPath $log -Force -ErrorAction SilentlyContinue
        }
    }
}

function Initialize-CleanDirectory {
    param([Parameter(Mandatory = $true)][string]$PathValue)
    if (Test-Path -LiteralPath $PathValue) {
        Remove-Item -LiteralPath $PathValue -Recurse -Force
    }
    New-Item -ItemType Directory -Path $PathValue -Force | Out-Null
}

function Copy-VariantPaths {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$DestinationRoot,
        [Parameter(Mandatory = $true)][string[]]$RelativePaths
    )
    foreach ($relativePath in $RelativePaths) {
        $sourcePath = Join-Path $SourceRoot $relativePath
        if (-not (Test-Path -LiteralPath $sourcePath)) {
            throw "Variant source path not found: $sourcePath"
        }
        $destinationPath = Join-Path $DestinationRoot $relativePath
        if (Test-Path -LiteralPath $sourcePath -PathType Container) {
            Copy-TreeRobust -Source $sourcePath -Destination $destinationPath
        }
        else {
            New-Item -ItemType Directory -Path (Split-Path -Parent $destinationPath) -Force | Out-Null
            Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
        }
    }
}

function Write-ZipFromDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$DestinationZip
    )
    if (Test-Path -LiteralPath $DestinationZip) {
        Remove-Item -LiteralPath $DestinationZip -Force
    }
    Invoke-Native -FilePath $python -ArgumentList @(
        "-c",
        @"
from pathlib import Path
import zipfile
src = Path(r'''$SourceRoot''')
dst = Path(r'''$DestinationZip''')
with zipfile.ZipFile(dst, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
    for path in src.rglob('*'):
        if path.is_file():
            zf.write(path, path.relative_to(src))
"@
    ) -WorkingDirectory $RepoRoot
}

$RepoRoot = (Resolve-Path $RepoRoot).Path
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$codeRoot = Join-Path $RepoRoot "MOLE_code"
$python = Join-Path $codeRoot ".venv\Scripts\python.exe"
$packager = Join-Path $codeRoot "mole_packager.py"
$wizardScript = Join-Path $codeRoot "mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py"
$runnerScript = Join-Path $codeRoot "mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py"
$scriptRunnerEntry = Join-Path $codeRoot "mole_script_runner_entry.py"

Require-Path $python "Python runtime"
Require-Path $packager "Packager"
Require-Path $wizardScript "Wizard script"
Require-Path $runnerScript "Runner script"
Require-Path $scriptRunnerEntry "Script runner entrypoint"

$buildRoot = Join-Path $OutputRoot "_build"
$distRoot = Join-Path $buildRoot "dist"
$workRoot = Join-Path $buildRoot "work"
$specRoot = Join-Path $buildRoot "spec"
$runtimeZip = Join-Path $OutputRoot "$BundleLabel`_runtime.zip"
$runtimeRoot = Join-Path $OutputRoot "runtime"
$runtimeCodeRoot = Join-Path $runtimeRoot "MOLE_code"
$runtimeConfigRoot = Join-Path $runtimeRoot "config"
$shareRoot = Join-Path $OutputRoot "shareable"
$installRoot = Join-Path $shareRoot $BundleLabel
$shareZip = Join-Path $OutputRoot "$BundleLabel`_portable_exe_bundle.zip"
$installerZip = Join-Path $OutputRoot "$BundleLabel`_installer_exe_bundle.zip"
$zipStageRoot = Join-Path $OutputRoot "_z"
$portableStageRoot = Join-Path $zipStageRoot "p"
$installerStageRoot = Join-Path $zipStageRoot "i"
$acceptanceArtifacts = Join-Path $OutputRoot "_acceptance_artifacts"
$acceptanceSummaryJson = Join-Path $acceptanceArtifacts "packaged_acceptance_summary.json"
$acceptanceSummaryTxt = Join-Path $acceptanceArtifacts "packaged_acceptance_summary.txt"
$publishedAcceptanceJsonName = "PACKAGED_ACCEPTANCE_SUMMARY.json"
$publishedAcceptanceTxtName = "PACKAGED_ACCEPTANCE_SUMMARY.txt"
$verifiedReleaseManifestName = "latest_verified_release_v1.json"
$versionAuditJsonName = "PACKAGE_VERSION_AUDIT.json"
$versionAuditTxtName = "PACKAGE_VERSION_AUDIT.txt"
$immutableAuditJsonName = "IMMUTABLE_PACKAGE_AUDIT.json"
$immutableAuditTxtName = "IMMUTABLE_PACKAGE_AUDIT.txt"
$verifiedReleaseManifestPath = Join-Path $OutputRoot $verifiedReleaseManifestName
$shareVerifiedReleaseManifestPath = Join-Path $installRoot $verifiedReleaseManifestName
$versionAuditJsonPath = Join-Path $OutputRoot $versionAuditJsonName
$versionAuditTxtPath = Join-Path $OutputRoot $versionAuditTxtName
$shareVersionAuditJsonPath = Join-Path $installRoot $versionAuditJsonName
$shareVersionAuditTxtPath = Join-Path $installRoot $versionAuditTxtName
$immutableAuditJsonPath = Join-Path $OutputRoot $immutableAuditJsonName
$immutableAuditTxtPath = Join-Path $OutputRoot $immutableAuditTxtName
$shareImmutableAuditJsonPath = Join-Path $installRoot $immutableAuditJsonName
$shareImmutableAuditTxtPath = Join-Path $installRoot $immutableAuditTxtName
$stableChannelManifestPath = $null
try {
    $outputParent = Split-Path -Parent $OutputRoot
    if ($outputParent) {
        $stableChannelManifestPath = Join-Path $outputParent $verifiedReleaseManifestName
    }
}
catch {
    $stableChannelManifestPath = $null
}

function Publish-PackagedAcceptanceSummary {
    param(
        [Parameter(Mandatory = $true)][string]$SourceJson,
        [Parameter(Mandatory = $true)][string]$SourceTxt,
        [Parameter(Mandatory = $true)][string[]]$TargetRoots
    )

    foreach ($targetRoot in $TargetRoots) {
        New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null
        Copy-Item -LiteralPath $SourceJson -Destination (Join-Path $targetRoot $publishedAcceptanceJsonName) -Force
        Copy-Item -LiteralPath $SourceTxt -Destination (Join-Path $targetRoot $publishedAcceptanceTxtName) -Force
    }
}

function Get-ReadmeBundleLabel {
    param([string]$PathValue)
    if (-not $PathValue -or -not (Test-Path -LiteralPath $PathValue)) {
        return ""
    }
    try {
        foreach ($line in Get-Content -LiteralPath $PathValue) {
            if ($line -match '^\s*Bundle label:\s*(.+?)\s*$') {
                return $Matches[1].Trim()
            }
        }
    }
    catch {}
    return ""
}

function Get-FileHashValue {
    param([string]$PathValue)
    if (-not $PathValue) {
        return ""
    }
    if (-not (Test-Path -LiteralPath $PathValue)) {
        return ""
    }
    try {
        return (Get-FileHash -LiteralPath $PathValue -Algorithm SHA256).Hash
    }
    catch {
        return ""
    }
}

function Write-PackageVersionAudit {
    param(
        [Parameter(Mandatory = $true)][string]$ExpectedBundleLabel,
        [Parameter(Mandatory = $true)][string]$RootPackagePath,
        [Parameter(Mandatory = $true)][string]$SharePackagePath,
        [string]$StableManifestPath
    )

    $rootBuildIdentityPath = Join-Path $RootPackagePath "runtime\config\mole_build_identity_v1.json"
    $rootAcceptancePath = Join-Path $RootPackagePath $publishedAcceptanceJsonName
    $rootVerifiedManifestPath = Join-Path $RootPackagePath $verifiedReleaseManifestName
    $rootReadmePath = Join-Path $RootPackagePath "README_EXECUTABLE_BUNDLE.txt"
    $shareBuildIdentityPath = Join-Path $SharePackagePath "runtime\config\mole_build_identity_v1.json"
    $shareAcceptancePath = Join-Path $SharePackagePath $publishedAcceptanceJsonName
    $shareVerifiedManifestPath = Join-Path $SharePackagePath $verifiedReleaseManifestName
    $shareReadmePath = Join-Path $SharePackagePath "README_EXECUTABLE_BUNDLE.txt"

    $rootBuildIdentity = if (Test-Path -LiteralPath $rootBuildIdentityPath) { Get-Content -LiteralPath $rootBuildIdentityPath -Raw | ConvertFrom-Json } else { $null }
    $rootAcceptance = if (Test-Path -LiteralPath $rootAcceptancePath) { Get-Content -LiteralPath $rootAcceptancePath -Raw | ConvertFrom-Json } else { $null }
    $rootVerifiedManifest = if (Test-Path -LiteralPath $rootVerifiedManifestPath) { Get-Content -LiteralPath $rootVerifiedManifestPath -Raw | ConvertFrom-Json } else { $null }
    $shareBuildIdentity = if (Test-Path -LiteralPath $shareBuildIdentityPath) { Get-Content -LiteralPath $shareBuildIdentityPath -Raw | ConvertFrom-Json } else { $null }
    $shareAcceptance = if (Test-Path -LiteralPath $shareAcceptancePath) { Get-Content -LiteralPath $shareAcceptancePath -Raw | ConvertFrom-Json } else { $null }
    $shareVerifiedManifest = if (Test-Path -LiteralPath $shareVerifiedManifestPath) { Get-Content -LiteralPath $shareVerifiedManifestPath -Raw | ConvertFrom-Json } else { $null }
    $stableManifest = if ($StableManifestPath -and (Test-Path -LiteralPath $StableManifestPath)) { Get-Content -LiteralPath $StableManifestPath -Raw | ConvertFrom-Json } else { $null }

    $checks = @(
        [ordered]@{ name = "root_build_identity_bundle_label"; expected = $ExpectedBundleLabel; actual = if ($rootBuildIdentity) { [string]$rootBuildIdentity.bundle_label } else { "" }; match = ($rootBuildIdentity -and [string]$rootBuildIdentity.bundle_label -eq $ExpectedBundleLabel); path = $rootBuildIdentityPath }
        [ordered]@{ name = "root_acceptance_package_label"; expected = $ExpectedBundleLabel; actual = if ($rootAcceptance) { [string]$rootAcceptance.package_label } else { "" }; match = ($rootAcceptance -and [string]$rootAcceptance.package_label -eq $ExpectedBundleLabel); path = $rootAcceptancePath }
        [ordered]@{ name = "root_verified_release_package_label"; expected = $ExpectedBundleLabel; actual = if ($rootVerifiedManifest) { [string]$rootVerifiedManifest.package_label } else { "" }; match = ($rootVerifiedManifest -and [string]$rootVerifiedManifest.package_label -eq $ExpectedBundleLabel); path = $rootVerifiedManifestPath }
        [ordered]@{ name = "root_readme_bundle_label"; expected = $ExpectedBundleLabel; actual = (Get-ReadmeBundleLabel $rootReadmePath); match = ((Get-ReadmeBundleLabel $rootReadmePath) -eq $ExpectedBundleLabel); path = $rootReadmePath }
        [ordered]@{ name = "share_build_identity_bundle_label"; expected = $ExpectedBundleLabel; actual = if ($shareBuildIdentity) { [string]$shareBuildIdentity.bundle_label } else { "" }; match = ($shareBuildIdentity -and [string]$shareBuildIdentity.bundle_label -eq $ExpectedBundleLabel); path = $shareBuildIdentityPath }
        [ordered]@{ name = "share_acceptance_package_label"; expected = $ExpectedBundleLabel; actual = if ($shareAcceptance) { [string]$shareAcceptance.package_label } else { "" }; match = ($shareAcceptance -and [string]$shareAcceptance.package_label -eq $ExpectedBundleLabel); path = $shareAcceptancePath }
        [ordered]@{ name = "share_verified_release_package_label"; expected = $ExpectedBundleLabel; actual = if ($shareVerifiedManifest) { [string]$shareVerifiedManifest.package_label } else { "" }; match = ($shareVerifiedManifest -and [string]$shareVerifiedManifest.package_label -eq $ExpectedBundleLabel); path = $shareVerifiedManifestPath }
        [ordered]@{ name = "share_readme_bundle_label"; expected = $ExpectedBundleLabel; actual = (Get-ReadmeBundleLabel $shareReadmePath); match = ((Get-ReadmeBundleLabel $shareReadmePath) -eq $ExpectedBundleLabel); path = $shareReadmePath }
        [ordered]@{ name = "root_installer_zip_name"; expected = "$ExpectedBundleLabel`_installer_exe_bundle.zip"; actual = [System.IO.Path]::GetFileName($installerZip); match = ([System.IO.Path]::GetFileName($installerZip) -eq "$ExpectedBundleLabel`_installer_exe_bundle.zip"); path = $installerZip }
        [ordered]@{ name = "root_portable_zip_name"; expected = "$ExpectedBundleLabel`_portable_exe_bundle.zip"; actual = [System.IO.Path]::GetFileName($shareZip); match = ([System.IO.Path]::GetFileName($shareZip) -eq "$ExpectedBundleLabel`_portable_exe_bundle.zip"); path = $shareZip }
    )

    if ($StableManifestPath) {
        $checks += [ordered]@{
            name = "stable_verified_release_package_label"
            expected = $ExpectedBundleLabel
            actual = if ($stableManifest) { [string]$stableManifest.package_label } else { "" }
            match = ($stableManifest -and [string]$stableManifest.package_label -eq $ExpectedBundleLabel)
            path = $StableManifestPath
        }
    }

    $status = if (($checks | Where-Object { -not $_.match }).Count -eq 0) { "PASS" } else { "FAIL" }
    $payload = [ordered]@{
        schema = "mole_package_version_audit_v1"
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        expected_bundle_label = $ExpectedBundleLabel
        status = $status
        checks = $checks
    }
    $summaryLines = @(
        "MOLE-DAS Package Version Audit",
        "==============================",
        "",
        "Expected bundle label: $ExpectedBundleLabel",
        "Status: $status",
        ""
    )
    foreach ($check in $checks) {
        $summaryLines += ("[{0}] {1}`n  expected: {2}`n  actual:   {3}`n  path:     {4}`n" -f ($(if ($check.match) { "PASS" } else { "FAIL" })), $check.name, $check.expected, $check.actual, $check.path)
    }

    [System.IO.File]::WriteAllText($versionAuditJsonPath, ($payload | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))
    [System.IO.File]::WriteAllText($versionAuditTxtPath, ($summaryLines -join [Environment]::NewLine), (New-Object System.Text.UTF8Encoding($false)))
    [System.IO.File]::WriteAllText($shareVersionAuditJsonPath, ($payload | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))
    [System.IO.File]::WriteAllText($shareVersionAuditTxtPath, ($summaryLines -join [Environment]::NewLine), (New-Object System.Text.UTF8Encoding($false)))

    if ($status -ne "PASS") {
        throw "Package version audit failed. See $versionAuditTxtPath"
    }
}

function Write-ImmutablePackageAudit {
    param(
        [Parameter(Mandatory = $true)][string]$ExpectedBundleLabel,
        [Parameter(Mandatory = $true)][string]$RootPackagePath,
        [Parameter(Mandatory = $true)][string]$SharePackagePath
    )

    $probes = @()
    foreach ($scope in @(
        @{ name = "root"; path = $RootPackagePath },
        @{ name = "share"; path = $SharePackagePath }
    )) {
        $runtimePath = Join-Path $scope.path "runtime"
        $probes += @(
            @{ scope = $scope.name; label = "mutable_logs"; path = Join-Path $runtimePath "mole_das_data\logs" }
            @{ scope = $scope.name; label = "mutable_backups"; path = Join-Path $runtimePath "mole_das_data\backups" }
            @{ scope = $scope.name; label = "mutable_sessions"; path = Join-Path $runtimePath "mole_das_data\sessions" }
            @{ scope = $scope.name; label = "mutable_daq_runs"; path = Join-Path $runtimePath "mole_das_data\daq_runs" }
            @{ scope = $scope.name; label = "mutable_exports"; path = Join-Path $runtimePath "mole_das_data\exports" }
            @{ scope = $scope.name; label = "mutable_validation"; path = Join-Path $runtimePath "mole_das_data\validation" }
            @{ scope = $scope.name; label = "mutable_inbox_archive"; path = Join-Path $runtimePath "mole_das_data\inbox_archive" }
            @{ scope = $scope.name; label = "mutable_inbox_packages"; path = Join-Path $runtimePath "mole_das_data\inbox_packages" }
            @{ scope = $scope.name; label = "mutable_cache"; path = Join-Path $runtimePath "mole_das_data\cache" }
            @{ scope = $scope.name; label = "mutable_training_sessions"; path = Join-Path $runtimePath "mole_das_data\training\sessions" }
            @{ scope = $scope.name; label = "mutable_root_config"; path = Join-Path $scope.path "mole_config.json" }
            @{ scope = $scope.name; label = "mutable_runtime_config"; path = Join-Path $runtimePath "config\mole_config.json" }
            @{ scope = $scope.name; label = "mutable_runtime_training_config"; path = Join-Path $runtimePath "config\mole_config_training.json" }
            @{ scope = $scope.name; label = "mutable_seed_config"; path = Join-Path $runtimePath "mole_das_data\configs\mole_config.json" }
            @{ scope = $scope.name; label = "mutable_seed_training_config"; path = Join-Path $runtimePath "mole_das_data\configs\mole_config_training.json" }
        )
    }

    $violations = @()
    foreach ($probe in $probes) {
        if (-not (Test-Path -LiteralPath $probe.path)) {
            continue
        }
        $sample = @()
        try {
            $sample = Get-ChildItem -LiteralPath $probe.path -Recurse -Force -ErrorAction SilentlyContinue | Select-Object -First 10 -ExpandProperty FullName
        }
        catch {
            $sample = @()
        }
        $violations += [ordered]@{
            scope = $probe.scope
            label = $probe.label
            path = $probe.path
            sample = $sample
        }
    }

    $status = if ($violations.Count -eq 0) { "PASS" } else { "FAIL" }
    $payload = [ordered]@{
        schema = "mole_immutable_package_audit_v1"
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        package_label = $ExpectedBundleLabel
        status = $status
        violations = $violations
    }
    $summaryLines = @(
        "MOLE-DAS Immutable Package Audit",
        "================================",
        "",
        "Package label: $ExpectedBundleLabel",
        "Status: $status",
        ""
    )
    if ($violations.Count -eq 0) {
        $summaryLines += "No mutable runtime artifacts were shipped inside the package payload."
    }
    else {
        foreach ($violation in $violations) {
            $summaryLines += ("[FAIL] {0}:{1}`n  path:   {2}`n  sample: {3}`n" -f $violation.scope, $violation.label, $violation.path, (($violation.sample | ForEach-Object { $_ }) -join "; "))
        }
    }

    [System.IO.File]::WriteAllText($immutableAuditJsonPath, ($payload | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))
    [System.IO.File]::WriteAllText($immutableAuditTxtPath, ($summaryLines -join [Environment]::NewLine), (New-Object System.Text.UTF8Encoding($false)))
    [System.IO.File]::WriteAllText($shareImmutableAuditJsonPath, ($payload | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))
    [System.IO.File]::WriteAllText($shareImmutableAuditTxtPath, ($summaryLines -join [Environment]::NewLine), (New-Object System.Text.UTF8Encoding($false)))

    if ($status -ne "PASS") {
        throw "Immutable package audit failed. See $immutableAuditTxtPath"
    }
}

function Write-VerifiedReleaseManifest {
    param(
        [Parameter(Mandatory = $true)][string]$DestinationPath,
        [Parameter(Mandatory = $true)][string]$ManifestKind,
        [Parameter(Mandatory = $true)][string]$PackageRootRef,
        [switch]$IncludeBundleHashes
    )

    $acceptanceSummary = $null
    if (Test-Path -LiteralPath $acceptanceSummaryJson) {
        try {
            $acceptanceSummary = Get-Content -LiteralPath $acceptanceSummaryJson -Raw | ConvertFrom-Json
        }
        catch {
            $acceptanceSummary = $null
        }
    }

    $payload = [ordered]@{
        schema = "mole_latest_verified_release_v1"
        manifest_kind = $ManifestKind
        channel_name = "LOCAL_VERIFIED"
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        package_label = $BundleLabel
        git_commit = $gitCommit
        git_branch = $gitBranch
        built_at = $buildIdentity.built_at
        package_root = $PackageRootRef
        runtime_root = "runtime"
        runtime_code_root = "runtime\\MOLE_code"
        build_identity_path = "runtime\\config\\mole_build_identity_v1.json"
        acceptance_status = [string]($acceptanceSummary.status)
        acceptance_generated_at = [string]($acceptanceSummary.generated_at)
        acceptance_summary_path = $publishedAcceptanceTxtName
        acceptance_summary_json_path = $publishedAcceptanceJsonName
        installer_script_path = "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
        version_audit_json_path = $versionAuditJsonName
        version_audit_txt_path = $versionAuditTxtName
        launcher_path = "LAUNCH_MOLE_DAS_EXE.bat"
        wizard_exe_path = "runtime\\MOLE_code\\MOLE_DAS_Wizard.exe"
        runner_exe_path = "runtime\\MOLE_code\\MOLE_DAQ_Runner.exe"
        script_runner_exe_path = "runtime\\MOLE_code\\MOLE_ScriptRunner.exe"
        installer_bundle_path = ""
        portable_bundle_path = ""
        hashes = [ordered]@{
            build_identity_sha256 = Get-FileHashValue $buildIdentityPath
            acceptance_summary_txt_sha256 = Get-FileHashValue $acceptanceSummaryTxt
            acceptance_summary_json_sha256 = Get-FileHashValue $acceptanceSummaryJson
            installer_script_sha256 = Get-FileHashValue (Join-Path $OutputRoot "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1")
            launcher_batch_sha256 = Get-FileHashValue (Join-Path $OutputRoot "LAUNCH_MOLE_DAS_EXE.bat")
            wizard_exe_sha256 = Get-FileHashValue (Join-Path $runtimeCodeRoot "MOLE_DAS_Wizard.exe")
            runner_exe_sha256 = Get-FileHashValue (Join-Path $runtimeCodeRoot "MOLE_DAQ_Runner.exe")
            script_runner_exe_sha256 = Get-FileHashValue (Join-Path $runtimeCodeRoot "MOLE_ScriptRunner.exe")
            installer_bundle_sha256 = ""
            portable_bundle_sha256 = ""
        }
    }

    if ($IncludeBundleHashes) {
        $payload.installer_bundle_path = [System.IO.Path]::GetFileName($installerZip)
        $payload.portable_bundle_path = [System.IO.Path]::GetFileName($shareZip)
        $payload.hashes.installer_bundle_sha256 = Get-FileHashValue $installerZip
        $payload.hashes.portable_bundle_sha256 = Get-FileHashValue $shareZip
    }

    [System.IO.File]::WriteAllText(
        $DestinationPath,
        ($payload | ConvertTo-Json -Depth 6),
        (New-Object System.Text.UTF8Encoding($false))
    )
}

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
if (Test-Path -LiteralPath $buildRoot) {
    Remove-Item -LiteralPath $buildRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $buildRoot, $distRoot, $workRoot, $specRoot -Force | Out-Null

Write-Host ""
Write-Host "==> Ensure PyInstaller is installed"
Invoke-Native -FilePath $python -ArgumentList @("-m", "pip", "install", "pyinstaller>=6.0") -WorkingDirectory $RepoRoot

Write-Host ""
Write-Host "==> Build strict runtime ZIP"
Invoke-Native -FilePath $python -ArgumentList @($packager, "--root", $RepoRoot, "--out", $runtimeZip, "--strict-hash") -WorkingDirectory $RepoRoot

Write-Host ""
Write-Host "==> Extract runtime ZIP"
if (Test-Path -LiteralPath $runtimeRoot) {
    Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
}
Invoke-Native -FilePath $python -ArgumentList @(
    "-c",
    @"
from pathlib import Path
import shutil
import zipfile

zip_path = Path(r'''$runtimeZip''')
dst = Path(r'''$runtimeRoot''')
if dst.exists():
    shutil.rmtree(dst)
dst.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path, 'r') as zf:
    zf.extractall(dst)
"@
) -WorkingDirectory $RepoRoot

$buildIdentityPath = Join-Path $runtimeConfigRoot "mole_build_identity_v1.json"
if (-not $gitCommit) {
    try {
        $gitCommit = (git -C $RepoRoot rev-parse --short HEAD 2>$null | Select-Object -First 1).Trim()
    }
    catch {}
}
if (-not $gitBranch) {
    try {
        $gitBranch = (git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null | Select-Object -First 1).Trim()
    }
    catch {}
}
$buildManifestGeneratedAt = $null
try {
    $repoBuildManifestPath = Join-Path $RepoRoot "BUILD_MANIFEST.json"
    if (Test-Path -LiteralPath $repoBuildManifestPath) {
        $repoBuildManifest = Get-Content -LiteralPath $repoBuildManifestPath -Raw | ConvertFrom-Json
        $buildManifestGeneratedAt = $repoBuildManifest.generated_at
    }
}
catch {}
$buildIdentity = [ordered]@{
    schema = "mole_build_identity_v1"
    bundle_label = $BundleLabel
    built_at = (Get-Date).ToUniversalTime().ToString("o")
    git_commit = $gitCommit
    git_branch = $gitBranch
    build_manifest_generated_at = $buildManifestGeneratedAt
    runtime_root = $runtimeRoot
    runtime_code_root = $runtimeCodeRoot
}
[System.IO.File]::WriteAllText(
    $buildIdentityPath,
    ($buildIdentity | ConvertTo-Json -Depth 4),
    (New-Object System.Text.UTF8Encoding($false))
)

$welcomeManifestPath = Join-Path $runtimeConfigRoot "mole_welcome_asset_manifest_v1.json"
$welcomeAssetApproved = $false
if (Test-Path -LiteralPath $welcomeManifestPath) {
    try {
        $welcomeManifest = Get-Content -LiteralPath $welcomeManifestPath -Raw | ConvertFrom-Json
        $welcomeAssetApproved = [bool]$welcomeManifest.approved
        $welcomeManifest.packaged_build_version = $BundleLabel
        $welcomeManifest.packaged_build_at = (Get-Date).ToUniversalTime().ToString("o")
        [System.IO.File]::WriteAllText(
            $welcomeManifestPath,
            ($welcomeManifest | ConvertTo-Json -Depth 8),
            (New-Object System.Text.UTF8Encoding($false))
        )
    }
    catch {
        $welcomeAssetApproved = $false
    }
}
if (-not $welcomeAssetApproved) {
    Get-ChildItem -Path (Join-Path $runtimeRoot "mole_assets\sprites") -Filter "mole_welcome_master_sheet_*.png" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path (Join-Path $runtimeCodeRoot "mole_assets\sprites") -Filter "mole_welcome_master_sheet_*.png" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
}

# The older scene-based welcome reels are deprecated. Strip them from every
# executable bundle so only the approved master reel family ships.
Get-ChildItem -Path (Join-Path $runtimeRoot "mole_assets\sprites") -Filter "mole_welcome_scene_wrench_wave_sheet_*.png" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path (Join-Path $runtimeCodeRoot "mole_assets\sprites") -Filter "mole_welcome_scene_wrench_wave_sheet_*.png" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path (Join-Path $runtimeRoot "mole_assets\sprites") -Filter "mole_idle_wrench_wave_brand_sheet_*.png" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path (Join-Path $runtimeCodeRoot "mole_assets\sprites") -Filter "mole_idle_wrench_wave_brand_sheet_*.png" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path (Join-Path $runtimeRoot "mole_assets\sprites") -Filter "mole_idle_wrench_wave_sheet_*.png" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path (Join-Path $runtimeCodeRoot "mole_assets\sprites") -Filter "mole_idle_wrench_wave_sheet_*.png" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

function Build-Executable {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$EntryScript,
        [Parameter(Mandatory = $true)][string]$ContentsDirectory,
        [switch]$Windowed
    )

    $exeWorkRoot = Join-Path $workRoot $Name
    $exeSpecRoot = Join-Path $specRoot $Name
    New-Item -ItemType Directory -Path $exeWorkRoot, $exeSpecRoot -Force | Out-Null

    $args = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name", $Name,
        "--distpath", $distRoot,
        "--workpath", $exeWorkRoot,
        "--specpath", $exeSpecRoot,
        "--paths", $codeRoot,
        "--contents-directory", $ContentsDirectory,
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.filedialog",
        "--hidden-import", "tkinter.messagebox",
        "--collect-submodules", "numpy",
        "--collect-submodules", "pandas",
        "--collect-submodules", "openpyxl",
        "--collect-submodules", "reportlab",
        "--collect-submodules", "pygame",
        $EntryScript
    )
    if ($Windowed) {
        $args = @($args[0..1] + @("--windowed") + $args[2..($args.Length - 1)])
    }
    Invoke-Native -FilePath $python -ArgumentList $args -WorkingDirectory $RepoRoot

    $appDir = Join-Path $distRoot $Name
    Require-Path $appDir "$Name dist folder"
    Copy-Item -LiteralPath (Join-Path $appDir "$Name.exe") -Destination (Join-Path $runtimeCodeRoot "$Name.exe") -Force
    Copy-Item -LiteralPath (Join-Path $appDir $ContentsDirectory) -Destination (Join-Path $runtimeCodeRoot $ContentsDirectory) -Recurse -Force
}

Write-Host ""
Write-Host "==> Build Wizard executable"
Build-Executable -Name "MOLE_DAS_Wizard" -EntryScript $wizardScript -ContentsDirectory "wizard_internal" -Windowed

Write-Host ""
Write-Host "==> Build Runner executable"
Build-Executable -Name "MOLE_DAQ_Runner" -EntryScript $runnerScript -ContentsDirectory "runner_internal" -Windowed

Write-Host ""
Write-Host "==> Build ScriptRunner executable"
Build-Executable -Name "MOLE_ScriptRunner" -EntryScript $scriptRunnerEntry -ContentsDirectory "script_runner_internal"

Write-Host ""
Write-Host "==> Prepare trimmed distributable"
New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
$shareRuntimeRoot = Join-Path $installRoot "runtime"
Copy-TreeRobust -Source $runtimeRoot -Destination $shareRuntimeRoot

$shareRuntimeCodeRoot = Join-Path $installRoot "runtime\MOLE_code"
if (Test-Path -LiteralPath (Join-Path $shareRuntimeCodeRoot ".venv")) {
    Remove-Item -LiteralPath (Join-Path $shareRuntimeCodeRoot ".venv") -Recurse -Force
}

$launcher = @'
@echo off
setlocal
set "ROOT=%~dp0runtime\MOLE_code"
if not exist "%ROOT%\MOLE_DAS_Wizard.exe" (
  echo Missing executable bundle at %ROOT%
  pause
  exit /b 1
)
start "" /D "%ROOT%" "%ROOT%\MOLE_DAS_Wizard.exe"
'@

$installerBatch = @'
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_MOLE_DAS_EXE_BUNDLE.ps1" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%
'@

$uninstallerBatch = @'
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0UNINSTALL_MOLE_DAS_EXE_BUNDLE.ps1" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%
'@

$installerPs1 = @'
param(
    [string]$InstallRoot = "",
    [switch]$NoLaunch,
    [switch]$NoDesktopShortcut,
    [switch]$NoStartMenuShortcut,
    [switch]$NoUninstallRegistration,
    [switch]$BootstrapPackageVerification,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message)
    if (-not $Quiet) {
        Write-Host $Message
    }
}

function Copy-TreeRobust {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $log = Join-Path $env:TEMP ("mole_install_robocopy_" + [guid]::NewGuid().ToString("N") + ".log")
    try {
        & robocopy $Source $Destination /E /NFL /NDL /NJH /NJS /NC /NS /NP /R:2 /W:1 /LOG:$log | Out-Null
        $code = $LASTEXITCODE
        if ($code -ge 8) {
            $detail = ""
            if (Test-Path -LiteralPath $log) {
                $detail = Get-Content -LiteralPath $log -Tail 40 | Out-String
            }
            throw "robocopy failed ($code) from $Source to $Destination`n$detail"
        }
    }
    finally {
        if (Test-Path -LiteralPath $log) {
            Remove-Item -LiteralPath $log -Force -ErrorAction SilentlyContinue
        }
    }
}

function Assert-ProcessesClosed {
    param([string]$TargetRoot)
    $names = @("MOLE_DAS_Wizard", "MOLE_DAQ_Runner", "MOLE_ScriptRunner")
    $running = foreach ($name in $names) {
        Get-Process -Name $name -ErrorAction SilentlyContinue
    }
    foreach ($proc in $running) {
        $procPath = $null
        try {
            $procPath = $proc.Path
        }
        catch {}
        if ($procPath -and $procPath.StartsWith($TargetRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Close MOLE-DAS before installing or upgrading. Running process: $($proc.ProcessName)"
        }
    }
}

function New-ShortcutFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$IconLocation
    )
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $TargetPath
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.IconLocation = $IconLocation
    $shortcut.Save()
}

function Get-FileHashValue {
    param([string]$PathValue)
    if (-not $PathValue -or -not (Test-Path -LiteralPath $PathValue)) {
        return ""
    }
    return (Get-FileHash -LiteralPath $PathValue -Algorithm SHA256).Hash
}

function Resolve-ManifestPath {
    param(
        [string]$BaseRoot,
        [string]$PathValue
    )
    if (-not $PathValue) {
        return $null
    }
    try {
        $candidate = [System.IO.Path]::GetFullPath((Join-Path $BaseRoot $PathValue))
    }
    catch {
        return $null
    }
    return $candidate
}

function Assert-VersionAuditPass {
    param([string]$AuditPath)
    if (-not (Test-Path -LiteralPath $AuditPath)) {
        throw "Package version audit not found: $AuditPath"
    }
    $audit = Get-Content -LiteralPath $AuditPath -Raw | ConvertFrom-Json
    if (-not $audit -or [string]$audit.schema -ne "mole_package_version_audit_v1") {
        throw "Package version audit schema is invalid: $AuditPath"
    }
    if ([string]$audit.status -ne "PASS") {
        throw "Package version audit is not PASS: $AuditPath"
    }
}

function Assert-ImmutablePackageAuditPass {
    param([string]$AuditPath)
    if (-not (Test-Path -LiteralPath $AuditPath)) {
        throw "Immutable package audit not found: $AuditPath"
    }
    $audit = Get-Content -LiteralPath $AuditPath -Raw | ConvertFrom-Json
    if (-not $audit -or [string]$audit.schema -ne "mole_immutable_package_audit_v1") {
        throw "Immutable package audit schema is invalid: $AuditPath"
    }
    if ([string]$audit.status -ne "PASS") {
        throw "Immutable package audit is not PASS: $AuditPath"
    }
}

function Assert-VerifiedReleasePackage {
    param([string]$PackageRoot)
    $manifestPath = Join-Path $PackageRoot "latest_verified_release_v1.json"
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "Verified release manifest not found: $manifestPath"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if (-not $manifest -or [string]$manifest.schema -ne "mole_latest_verified_release_v1") {
        throw "Verified release manifest schema is invalid: $manifestPath"
    }
    if ([string]$manifest.acceptance_status -ne "PASS") {
        throw "Verified release manifest acceptance_status is not PASS: $manifestPath"
    }
    $packageLabel = [string]$manifest.package_label
    if (-not $packageLabel) {
        throw "Verified release manifest package_label is missing: $manifestPath"
    }
    $packageBase = Resolve-ManifestPath -BaseRoot $PackageRoot -PathValue ([string]$manifest.package_root)
    if (-not $packageBase -or -not (Test-Path -LiteralPath $packageBase)) {
        throw "Verified release package_root is invalid: $manifestPath"
    }
    $versionAuditPath = Resolve-ManifestPath -BaseRoot $packageBase -PathValue ([string]$manifest.version_audit_json_path)
    Assert-VersionAuditPass -AuditPath $versionAuditPath
    Assert-ImmutablePackageAuditPass -AuditPath (Join-Path $packageBase "IMMUTABLE_PACKAGE_AUDIT.json")

    $hashes = $manifest.hashes
    $buildIdentityPath = Resolve-ManifestPath -BaseRoot $packageBase -PathValue ([string]$manifest.build_identity_path)
    $acceptanceTextPath = Resolve-ManifestPath -BaseRoot $packageBase -PathValue ([string]$manifest.acceptance_summary_path)
    $acceptanceJsonPath = Resolve-ManifestPath -BaseRoot $packageBase -PathValue ([string]$manifest.acceptance_summary_json_path)
    $installerScriptPath = Resolve-ManifestPath -BaseRoot $packageBase -PathValue ([string]$manifest.installer_script_path)
    $launcherPath = Resolve-ManifestPath -BaseRoot $packageBase -PathValue ([string]$manifest.launcher_path)
    $wizardExePath = Resolve-ManifestPath -BaseRoot $packageBase -PathValue ([string]$manifest.wizard_exe_path)
    $runnerExePath = Resolve-ManifestPath -BaseRoot $packageBase -PathValue ([string]$manifest.runner_exe_path)
    $scriptRunnerExePath = Resolve-ManifestPath -BaseRoot $packageBase -PathValue ([string]$manifest.script_runner_exe_path)

    $targets = @(
        @{ Label = "Build identity manifest"; Path = $buildIdentityPath; Hash = [string]$hashes.build_identity_sha256 }
        @{ Label = "Packaged acceptance summary"; Path = $acceptanceTextPath; Hash = [string]$hashes.acceptance_summary_txt_sha256 }
        @{ Label = "Packaged acceptance summary JSON"; Path = $acceptanceJsonPath; Hash = [string]$hashes.acceptance_summary_json_sha256 }
        @{ Label = "Installer script"; Path = $installerScriptPath; Hash = [string]$hashes.installer_script_sha256 }
        @{ Label = "Launcher batch"; Path = $launcherPath; Hash = [string]$hashes.launcher_batch_sha256 }
        @{ Label = "Wizard executable"; Path = $wizardExePath; Hash = [string]$hashes.wizard_exe_sha256 }
        @{ Label = "Runner executable"; Path = $runnerExePath; Hash = [string]$hashes.runner_exe_sha256 }
        @{ Label = "ScriptRunner executable"; Path = $scriptRunnerExePath; Hash = [string]$hashes.script_runner_exe_sha256 }
    )
    foreach ($target in $targets) {
        if (-not $target.Path -or -not (Test-Path -LiteralPath $target.Path)) {
            throw "$($target.Label) is missing: $($target.Path)"
        }
        if (-not $target.Hash) {
            throw "Verified release manifest is missing $($target.Label) SHA256."
        }
        $actualHash = Get-FileHashValue -PathValue $target.Path
        if (-not $actualHash) {
            throw "$($target.Label) SHA256 could not be computed: $($target.Path)"
        }
        if ($actualHash -ne $target.Hash) {
            throw "$($target.Label) SHA256 mismatch. Expected $($target.Hash), got $actualHash."
        }
    }

    $buildIdentity = Get-Content -LiteralPath $buildIdentityPath -Raw | ConvertFrom-Json
    if ([string]$buildIdentity.bundle_label -ne $packageLabel) {
        throw "Build identity bundle_label does not match verified release package_label."
    }
    $acceptanceSummary = Get-Content -LiteralPath $acceptanceJsonPath -Raw | ConvertFrom-Json
    if ([string]$acceptanceSummary.status -ne "PASS") {
        throw "Packaged acceptance summary JSON is not PASS."
    }
    if ([string]$acceptanceSummary.package_label -ne $packageLabel) {
        throw "Packaged acceptance summary package_label does not match verified release package_label."
    }
}

if (-not $InstallRoot) {
    $InstallRoot = Join-Path $env:LOCALAPPDATA "Programs\MOLE_DAS"
}
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceRuntime = Join-Path $PackageRoot "runtime"
$SourceWizard = Join-Path $SourceRuntime "MOLE_code\MOLE_DAS_Wizard.exe"
if (-not (Test-Path -LiteralPath $SourceWizard)) {
    throw "Missing runtime payload in package: $SourceWizard"
}

$SourceSupportFiles = @(
    "LAUNCH_MOLE_DAS_EXE.bat",
    "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1",
    "INSTALL_MOLE_DAS_EXE_BUNDLE.bat",
    "UNINSTALL_MOLE_DAS_EXE_BUNDLE.ps1",
    "UNINSTALL_MOLE_DAS_EXE_BUNDLE.bat",
    "README_EXECUTABLE_BUNDLE.txt",
    "MOLE_DAS.ico",
    "latest_verified_release_v1.json",
    "PACKAGE_VERSION_AUDIT.json",
    "PACKAGE_VERSION_AUDIT.txt",
    "IMMUTABLE_PACKAGE_AUDIT.json",
    "IMMUTABLE_PACKAGE_AUDIT.txt",
    "PACKAGED_ACCEPTANCE_SUMMARY.json",
    "PACKAGED_ACCEPTANCE_SUMMARY.txt"
)

$IncomingRuntime = Join-Path $InstallRoot "_incoming_runtime"
$PreviousRuntime = Join-Path $InstallRoot "_previous_runtime"
$ActiveRuntime = Join-Path $InstallRoot "runtime"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\MOLE-DAS"
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "MOLE-DAS.lnk"
$StartMenuLaunch = Join-Path $StartMenuDir "MOLE-DAS.lnk"
$StartMenuUninstall = Join-Path $StartMenuDir "Uninstall MOLE-DAS.lnk"
$InstallManifestPath = Join-Path $InstallRoot "mole_install_manifest_v1.json"
$BuildIdentityPath = Join-Path $ActiveRuntime "config\mole_build_identity_v1.json"
$InstalledLauncher = Join-Path $InstallRoot "LAUNCH_MOLE_DAS_EXE.bat"
$InstalledUninstallPs1 = Join-Path $InstallRoot "UNINSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
$InstalledUninstallBat = Join-Path $InstallRoot "UNINSTALL_MOLE_DAS_EXE_BUNDLE.bat"
$InstalledIcon = Join-Path $InstallRoot "MOLE_DAS.ico"
$InstalledWizard = Join-Path $ActiveRuntime "MOLE_code\MOLE_DAS_Wizard.exe"
$InstalledRunner = Join-Path $ActiveRuntime "MOLE_code\MOLE_DAQ_Runner.exe"

Write-Status ""
Write-Status "Installing MOLE-DAS executable bundle"
Write-Status "  Package root: $PackageRoot"
Write-Status "  Install root: $InstallRoot"

if (-not $BootstrapPackageVerification) {
    Assert-VerifiedReleasePackage -PackageRoot $PackageRoot
}

New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
Assert-ProcessesClosed -TargetRoot $InstallRoot

if (Test-Path -LiteralPath $IncomingRuntime) {
    Remove-Item -LiteralPath $IncomingRuntime -Recurse -Force
}
if (Test-Path -LiteralPath $PreviousRuntime) {
    Remove-Item -LiteralPath $PreviousRuntime -Recurse -Force
}

Write-Status "Staging runtime payload..."
Copy-TreeRobust -Source $SourceRuntime -Destination $IncomingRuntime

$swapped = $false
try {
    if (Test-Path -LiteralPath $ActiveRuntime) {
        Write-Status "Archiving previous runtime..."
        Move-Item -LiteralPath $ActiveRuntime -Destination $PreviousRuntime -Force
    }
    Write-Status "Promoting staged runtime..."
    Move-Item -LiteralPath $IncomingRuntime -Destination $ActiveRuntime -Force
    $swapped = $true
}
catch {
    if ($swapped -and (Test-Path -LiteralPath $ActiveRuntime)) {
        Remove-Item -LiteralPath $ActiveRuntime -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $PreviousRuntime) {
        Move-Item -LiteralPath $PreviousRuntime -Destination $ActiveRuntime -Force
    }
    throw
}

if (Test-Path -LiteralPath $PreviousRuntime) {
    Remove-Item -LiteralPath $PreviousRuntime -Recurse -Force
}

foreach ($name in $SourceSupportFiles) {
    $src = Join-Path $PackageRoot $name
    if (Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $InstallRoot $name) -Force
    }
}

$buildIdentity = $null
if (Test-Path -LiteralPath $BuildIdentityPath) {
    $buildIdentity = Get-Content -LiteralPath $BuildIdentityPath -Raw | ConvertFrom-Json
}
$displayVersion = "MOLE_DAS"
if ($buildIdentity -and $buildIdentity.bundle_label) {
    $displayVersion = [string]$buildIdentity.bundle_label
}

$installManifest = [ordered]@{
    schema = "mole_install_manifest_v1"
    installed_at = (Get-Date).ToUniversalTime().ToString("o")
    install_root = $InstallRoot
    install_source = $PackageRoot
    runtime_root = $ActiveRuntime
    wizard_exe = $InstalledWizard
    runner_exe = $InstalledRunner
    launcher = $InstalledLauncher
    uninstall_script = $InstalledUninstallPs1
    bundle_label = $displayVersion
    git_commit = if ($buildIdentity) { $buildIdentity.git_commit } else { $null }
    git_branch = if ($buildIdentity) { $buildIdentity.git_branch } else { $null }
}
[System.IO.File]::WriteAllText(
    $InstallManifestPath,
    ($installManifest | ConvertTo-Json -Depth 6),
    (New-Object System.Text.UTF8Encoding($false))
)

if (-not $NoStartMenuShortcut) {
    New-Item -ItemType Directory -Path $StartMenuDir -Force | Out-Null
    New-ShortcutFile -Path $StartMenuLaunch -TargetPath $InstalledLauncher -WorkingDirectory $InstallRoot -IconLocation $InstalledIcon
    New-ShortcutFile -Path $StartMenuUninstall -TargetPath $InstalledUninstallBat -WorkingDirectory $InstallRoot -IconLocation $InstalledIcon
}

if (-not $NoDesktopShortcut) {
    New-ShortcutFile -Path $DesktopShortcut -TargetPath $InstalledLauncher -WorkingDirectory $InstallRoot -IconLocation $InstalledIcon
}

if (-not $NoUninstallRegistration) {
    $key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MOLE_DAS"
    New-Item -Path $key -Force | Out-Null
    New-ItemProperty -Path $key -Name "DisplayName" -PropertyType String -Value "MOLE-DAS" -Force | Out-Null
    New-ItemProperty -Path $key -Name "Publisher" -PropertyType String -Value "Encino Environmental Services, LLC" -Force | Out-Null
    New-ItemProperty -Path $key -Name "InstallLocation" -PropertyType String -Value $InstallRoot -Force | Out-Null
    New-ItemProperty -Path $key -Name "DisplayVersion" -PropertyType String -Value $displayVersion -Force | Out-Null
    New-ItemProperty -Path $key -Name "DisplayIcon" -PropertyType String -Value $InstalledIcon -Force | Out-Null
    New-ItemProperty -Path $key -Name "UninstallString" -PropertyType String -Value ('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + $InstalledUninstallPs1 + '"') -Force | Out-Null
    New-ItemProperty -Path $key -Name "QuietUninstallString" -PropertyType String -Value ('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + $InstalledUninstallPs1 + '" -Quiet') -Force | Out-Null
    New-ItemProperty -Path $key -Name "NoModify" -PropertyType DWord -Value 1 -Force | Out-Null
    New-ItemProperty -Path $key -Name "NoRepair" -PropertyType DWord -Value 1 -Force | Out-Null
    New-ItemProperty -Path $key -Name "InstallDate" -PropertyType String -Value (Get-Date -Format "yyyyMMdd") -Force | Out-Null
}

Write-Status "Install complete."
Write-Status "  Wizard: $InstalledWizard"
Write-Status "  Install manifest: $InstallManifestPath"

if (-not $NoLaunch) {
    Start-Process -FilePath $InstalledWizard -WorkingDirectory (Split-Path -Parent $InstalledWizard)
}
'@

$uninstallerPs1 = @'
param(
    [string]$InstallRoot = "",
    [switch]$Quiet,
    [switch]$FromTemp
)

$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message)
    if (-not $Quiet) {
        Write-Host $Message
    }
}

function Assert-ProcessesClosed {
    param([string]$TargetRoot)
    $names = @("MOLE_DAS_Wizard", "MOLE_DAQ_Runner", "MOLE_ScriptRunner")
    $running = foreach ($name in $names) {
        Get-Process -Name $name -ErrorAction SilentlyContinue
    }
    foreach ($proc in $running) {
        $procPath = $null
        try {
            $procPath = $proc.Path
        }
        catch {}
        if ($procPath -and $procPath.StartsWith($TargetRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Close MOLE-DAS before uninstalling. Running process: $($proc.ProcessName)"
        }
    }
}

function Remove-ShortcutIfExists {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    }
}

if (-not $InstallRoot) {
    $InstallRoot = $PSScriptRoot
}
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)

if (-not $FromTemp) {
    $tempScript = Join-Path $env:TEMP ("mole_uninstall_runner_" + [guid]::NewGuid().ToString("N") + ".ps1")
    Copy-Item -LiteralPath $MyInvocation.MyCommand.Path -Destination $tempScript -Force
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $tempScript,
        "-InstallRoot", $InstallRoot,
        "-FromTemp"
    )
    if ($Quiet) {
        $arguments += "-Quiet"
    }
    Start-Process -FilePath "powershell.exe" -ArgumentList $arguments -WorkingDirectory $env:TEMP -WindowStyle Hidden
    return
}

Write-Status ""
Write-Status "Uninstalling MOLE-DAS"
Write-Status "  Install root: $InstallRoot"

Assert-ProcessesClosed -TargetRoot $InstallRoot
Start-Sleep -Seconds 2

$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\MOLE-DAS"
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "MOLE-DAS.lnk"
Remove-ShortcutIfExists -Path (Join-Path $StartMenuDir "MOLE-DAS.lnk")
Remove-ShortcutIfExists -Path (Join-Path $StartMenuDir "Uninstall MOLE-DAS.lnk")
if (Test-Path -LiteralPath $StartMenuDir) {
    try {
        Remove-Item -LiteralPath $StartMenuDir -Force -ErrorAction SilentlyContinue
    }
    catch {}
}
Remove-ShortcutIfExists -Path $DesktopShortcut

Remove-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MOLE_DAS" -Recurse -Force -ErrorAction SilentlyContinue

if (Test-Path -LiteralPath $InstallRoot) {
    $deleteArgs = '/d /c rmdir /s /q "' + $InstallRoot + '"'
    $deleteProc = Start-Process -FilePath "cmd.exe" -ArgumentList $deleteArgs -WorkingDirectory $env:TEMP -WindowStyle Hidden -PassThru
    $deleteProc.WaitForExit()
}

Write-Status "Uninstall complete."
Write-Status "  Root removed: $InstallRoot"
'@

foreach ($targetRoot in @($OutputRoot, $installRoot)) {
    Set-Content -LiteralPath (Join-Path $targetRoot "LAUNCH_MOLE_DAS_EXE.bat") -Value $launcher -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $targetRoot "INSTALL_MOLE_DAS_EXE_BUNDLE.bat") -Value $installerBatch -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $targetRoot "UNINSTALL_MOLE_DAS_EXE_BUNDLE.bat") -Value $uninstallerBatch -Encoding ASCII
    [System.IO.File]::WriteAllText(
        (Join-Path $targetRoot "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1"),
        $installerPs1,
        (New-Object System.Text.UTF8Encoding($false))
    )
    [System.IO.File]::WriteAllText(
        (Join-Path $targetRoot "UNINSTALL_MOLE_DAS_EXE_BUNDLE.ps1"),
        $uninstallerPs1,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

$notes = @"
MOLE-DAS Windows Executable Bundle
==================================

Bundle label: $BundleLabel
Repo root: $RepoRoot

Portable launch:
- LAUNCH_MOLE_DAS_EXE.bat
- or runtime\MOLE_code\MOLE_DAS_Wizard.exe

Installer launch:
- INSTALL_MOLE_DAS_EXE_BUNDLE.bat
- default install root: %LOCALAPPDATA%\Programs\MOLE_DAS
- creates Start Menu and Desktop shortcuts
- upgrades an existing user install in place
- writes uninstall entry under HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MOLE_DAS

Uninstall:
- UNINSTALL_MOLE_DAS_EXE_BUNDLE.bat from the installed root
- or Windows Installed Apps entry for MOLE-DAS

Included executables:
- MOLE_DAS_Wizard.exe
- MOLE_DAQ_Runner.exe
- MOLE_ScriptRunner.exe

Packaged acceptance:
- PACKAGED_ACCEPTANCE_SUMMARY.txt
- PACKAGED_ACCEPTANCE_SUMMARY.json

Layout requirement:
- Keep the runtime folder structure intact.
- The executables depend on sibling runtime content in runtime\MOLE_code and the package root data/assets/docs folders.
"@
Set-Content -LiteralPath (Join-Path $OutputRoot "README_EXECUTABLE_BUNDLE.txt") -Value $notes -Encoding ASCII
Set-Content -LiteralPath (Join-Path $installRoot "README_EXECUTABLE_BUNDLE.txt") -Value $notes -Encoding ASCII

$iconPath = Join-Path $OutputRoot "MOLE_DAS.ico"
Invoke-Native -FilePath $python -ArgumentList @(
    "-c",
    @"
from pathlib import Path
from PIL import Image
candidates = [
    Path(r'''$OutputRoot''') / 'runtime' / 'MOLE_code' / 'mole_logo_130.png',
    Path(r'''$OutputRoot''') / 'runtime' / 'MOLE_code' / 'mole_logo.png',
    Path(r'''$OutputRoot''') / 'runtime' / 'mole_assets' / 'branding' / 'mole_logo_130.png',
    Path(r'''$OutputRoot''') / 'runtime' / 'mole_assets' / 'branding' / 'mole_logo.png',
]
dst = Path(r'''$iconPath''')
for src in candidates:
    if src.exists():
        img = Image.open(src)
        img.save(dst, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        print(dst)
        break
else:
    raise SystemExit('MOLE logo source not found for icon generation')
"@
) -WorkingDirectory $RepoRoot
Copy-Item -LiteralPath $iconPath -Destination (Join-Path $installRoot "MOLE_DAS.ico") -Force

$shell = New-Object -ComObject WScript.Shell
foreach ($targetRoot in @($OutputRoot, $installRoot)) {
    $targetIcon = Join-Path $targetRoot "MOLE_DAS.ico"
    $launchShortcut = $shell.CreateShortcut((Join-Path $targetRoot "Launch MOLE-DAS.lnk"))
    $launchShortcut.TargetPath = (Join-Path $targetRoot "LAUNCH_MOLE_DAS_EXE.bat")
    $launchShortcut.WorkingDirectory = $targetRoot
    $launchShortcut.IconLocation = $targetIcon
    $launchShortcut.Save()

    $installShortcut = $shell.CreateShortcut((Join-Path $targetRoot "Install MOLE-DAS.lnk"))
    $installShortcut.TargetPath = (Join-Path $targetRoot "INSTALL_MOLE_DAS_EXE_BUNDLE.bat")
    $installShortcut.WorkingDirectory = $targetRoot
    $installShortcut.IconLocation = $targetIcon
    $installShortcut.Save()
}

if (-not $SkipPackagedAcceptance) {
    $acceptanceScript = Join-Path $RepoRoot "scripts\run_packaged_acceptance.ps1"
    Require-Path $acceptanceScript "Packaged acceptance runner"

    Write-Host ""
    Write-Host "==> Run packaged acceptance"
    Invoke-Native -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $acceptanceScript,
        "-PackageRoot", $OutputRoot,
        "-ArtifactOutDir", $acceptanceArtifacts
    ) -WorkingDirectory $RepoRoot

    Require-Path $acceptanceSummaryJson "Packaged acceptance summary JSON"
    Require-Path $acceptanceSummaryTxt "Packaged acceptance summary text"
    Publish-PackagedAcceptanceSummary -SourceJson $acceptanceSummaryJson -SourceTxt $acceptanceSummaryTxt -TargetRoots @($OutputRoot, $installRoot)
    Write-VerifiedReleaseManifest -DestinationPath $verifiedReleaseManifestPath -ManifestKind "package_root" -PackageRootRef "."
    Write-VerifiedReleaseManifest -DestinationPath $shareVerifiedReleaseManifestPath -ManifestKind "package_root" -PackageRootRef "."
    Write-PackageVersionAudit -ExpectedBundleLabel $BundleLabel -RootPackagePath $OutputRoot -SharePackagePath $installRoot
    Write-ImmutablePackageAudit -ExpectedBundleLabel $BundleLabel -RootPackagePath $OutputRoot -SharePackagePath $installRoot
}

if (Test-Path -LiteralPath $shareZip) {
    Remove-Item -LiteralPath $shareZip -Force
}
if (Test-Path -LiteralPath $installerZip) {
    Remove-Item -LiteralPath $installerZip -Force
}
Initialize-CleanDirectory -PathValue $zipStageRoot
Initialize-CleanDirectory -PathValue $portableStageRoot
Initialize-CleanDirectory -PathValue $installerStageRoot

# Portable zip: direct-run payload only. No installer or uninstaller scripts.
Copy-VariantPaths -SourceRoot $installRoot -DestinationRoot $portableStageRoot -RelativePaths @(
    "runtime",
    "LAUNCH_MOLE_DAS_EXE.bat",
    "README_EXECUTABLE_BUNDLE.txt",
    "MOLE_DAS.ico",
    "Launch MOLE-DAS.lnk",
    $publishedAcceptanceJsonName,
    $publishedAcceptanceTxtName,
    $verifiedReleaseManifestName,
    $versionAuditJsonName,
    $versionAuditTxtName,
    $immutableAuditJsonName,
    $immutableAuditTxtName
)

Copy-TreeRobust -Source $installRoot -Destination $installerStageRoot

Write-ZipFromDirectory -SourceRoot $portableStageRoot -DestinationZip $shareZip
Write-ZipFromDirectory -SourceRoot $installerStageRoot -DestinationZip $installerZip

if (-not $SkipPackagedAcceptance) {
    Write-VerifiedReleaseManifest -DestinationPath $verifiedReleaseManifestPath -ManifestKind "release_channel" -PackageRootRef "." -IncludeBundleHashes
    if ($stableChannelManifestPath) {
        Write-VerifiedReleaseManifest -DestinationPath $stableChannelManifestPath -ManifestKind "release_channel" -PackageRootRef ([System.IO.Path]::GetFileName($OutputRoot)) -IncludeBundleHashes
    }
    Write-PackageVersionAudit -ExpectedBundleLabel $BundleLabel -RootPackagePath $OutputRoot -SharePackagePath $installRoot -StableManifestPath $stableChannelManifestPath
}

Write-Host ""
Write-Host "Executable bundle ready:"
Write-Host "  $OutputRoot"
