param(
    [Parameter(Mandatory = $true)]
    [string]$PackageRoot,

    [string]$InstallRoot = "",

    [string]$ArtifactOutDir = "",

    [switch]$KeepInstall
)

$ErrorActionPreference = "Stop"

function Require-Path {
    param(
        [Parameter(Mandatory = $true)][string]$PathValue,
        [Parameter(Mandatory = $true)][string]$Label
    )
    if (-not (Test-Path -LiteralPath $PathValue)) {
        throw "$Label not found: $PathValue"
    }
}

function Write-JsonUtf8 {
    param(
        [Parameter(Mandatory = $true)][string]$PathValue,
        [Parameter(Mandatory = $true)]$Payload
    )
    [System.IO.File]::WriteAllText(
        $PathValue,
        ($Payload | ConvertTo-Json -Depth 10),
        (New-Object System.Text.UTF8Encoding($false))
    )
}

function Remove-TreeRobust {
    param(
        [Parameter(Mandatory = $true)][string]$PathValue
    )
    if (-not (Test-Path -LiteralPath $PathValue)) {
        return
    }
    $fullPath = [System.IO.Path]::GetFullPath($PathValue)
    & cmd.exe /d /c "rmdir /s /q `"$fullPath`""
    if (Test-Path -LiteralPath $fullPath) {
        throw "Failed to remove tree: $fullPath"
    }
}

function Add-StepResult {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][string]$Detail,
        [hashtable]$Extra = @{}
    )
    $row = [ordered]@{
        name = $Name
        status = $Status
        detail = $Detail
    }
    foreach ($key in ($Extra.Keys | Sort-Object)) {
        $row[$key] = $Extra[$key]
    }
    $script:StepResults.Add([pscustomobject]$row) | Out-Null
}

function Save-SummaryFiles {
    param(
        [Parameter(Mandatory = $true)][string]$JsonPath,
        [Parameter(Mandatory = $true)][string]$TextPath,
        [Parameter(Mandatory = $true)]$Summary
    )
    $Summary["steps"] = [object[]]$script:StepResults.ToArray()
    Write-JsonUtf8 -PathValue $JsonPath -Payload $Summary

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("MOLE Packaged Acceptance Summary")
    $lines.Add("==============================")
    $lines.Add("")
    $lines.Add("Status: $($Summary.status)")
    $lines.Add("Generated: $($Summary.generated_at)")
    $lines.Add("Package root: $($Summary.package_root)")
    $lines.Add("Install root: $($Summary.install_root)")
    $lines.Add("Artifacts: $($Summary.artifact_dir)")
    $lines.Add("Package label: $($Summary.package_label)")
    $lines.Add("Git commit: $($Summary.git_commit)")
    $lines.Add("")
    $lines.Add("Steps")
    $lines.Add("-----")
    foreach ($step in $script:StepResults) {
        $lines.Add("[$($step.status)] $($step.name): $($step.detail)")
    }
    $lines.Add("")
    $lines.Add("Key outputs")
    $lines.Add("-----------")
    foreach ($key in @(
        "wizard_startup_path",
        "runner_startup_path",
        "session_dir",
        "runner_config_path",
        "session_profile_path",
        "report_pack_summary_path",
        "final_report_path",
        "final_report_index_path",
        "upgrade_report_txt_path",
        "upgrade_report_json_path",
        "rollback_report_txt_path",
        "rollback_report_json_path",
        "support_bundle_path"
    )) {
        $value = $Summary[$key]
        if ($value) {
            $lines.Add("${key}: $value")
        }
    }
    [System.IO.File]::WriteAllLines($TextPath, $lines, (New-Object System.Text.UTF8Encoding($false)))
}

function Invoke-CapturedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory = "",
        [switch]$AllowNonZeroExit
    )

    $stdoutPath = Join-Path $script:ArtifactOutDir ($Label + "_stdout.txt")
    $stderrPath = Join-Path $script:ArtifactOutDir ($Label + "_stderr.txt")
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue

    $proc = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -Wait `
        -PassThru

    $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { "" }
    $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { "" }

    if ((-not $AllowNonZeroExit) -and ($proc.ExitCode -ne 0)) {
        throw "Command failed ($($proc.ExitCode)): $FilePath $($ArgumentList -join ' ')`nSTDERR:`n$stderr"
    }

    return [pscustomobject]@{
        exit_code = $proc.ExitCode
        stdout_path = $stdoutPath
        stderr_path = $stderrPath
        stdout = $stdout
        stderr = $stderr
    }
}

function Wait-ForFile {
    param(
        [Parameter(Mandatory = $true)][string]$PathValue,
        [int]$TimeoutSec = 60
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $PathValue) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Wait-ForPathRemoval {
    param(
        [Parameter(Mandatory = $true)][string]$PathValue,
        [int]$TimeoutSec = 120
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (-not (Test-Path -LiteralPath $PathValue)) {
            return $true
        }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Stop-ProcessIfRunning {
    param($ProcessObject)
    if ($null -eq $ProcessObject) {
        return
    }
    try {
        if (-not $ProcessObject.HasExited) {
            Stop-Process -Id $ProcessObject.Id -Force -ErrorAction SilentlyContinue
        }
    }
    catch {}
}

function Invoke-EmbeddedPythonJson {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Source
    )

    $scriptPath = Join-Path $WorkingDirectory ("_mole_acceptance_" + $Label + ".py")
    [System.IO.File]::WriteAllText($scriptPath, $Source, (New-Object System.Text.UTF8Encoding($false)))
    try {
        $result = Invoke-CapturedProcess -Label $Label -FilePath $PythonExe -ArgumentList @($scriptPath) -WorkingDirectory $WorkingDirectory
        try {
            return [pscustomobject](ConvertFrom-Json -InputObject ($result.stdout.Trim()))
        }
        catch {
            throw "Failed to parse JSON output from $Label`nSTDOUT:`n$($result.stdout)`nSTDERR:`n$($result.stderr)"
        }
    }
    finally {
        Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
    }
}

$PackageRoot = (Resolve-Path $PackageRoot).Path
if (-not $InstallRoot) {
    $InstallRoot = Join-Path $PackageRoot "_acceptance_install"
}
if (-not $ArtifactOutDir) {
    $ArtifactOutDir = Join-Path $PackageRoot "_acceptance_artifacts"
}
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$ArtifactOutDir = [System.IO.Path]::GetFullPath($ArtifactOutDir)

$script:ArtifactOutDir = $ArtifactOutDir
$script:StepResults = New-Object 'System.Collections.Generic.List[object]'

$installerPs1 = Join-Path $PackageRoot "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
Require-Path -PathValue $installerPs1 -Label "Package installer"

if (Test-Path -LiteralPath $ArtifactOutDir) {
    Remove-TreeRobust -PathValue $ArtifactOutDir
}
New-Item -ItemType Directory -Path $ArtifactOutDir -Force | Out-Null

$summaryJsonPath = Join-Path $ArtifactOutDir "packaged_acceptance_summary.json"
$summaryTextPath = Join-Path $ArtifactOutDir "packaged_acceptance_summary.txt"

$summary = [ordered]@{
    schema = "mole_packaged_acceptance_v1"
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    status = "RUNNING"
    package_root = $PackageRoot
    install_root = $InstallRoot
    artifact_dir = $ArtifactOutDir
    package_label = ""
    git_commit = ""
    git_branch = ""
    build_identity_path = ""
    welcome_manifest_path = ""
    wizard_startup_path = ""
    runner_startup_path = ""
    session_dir = ""
    runner_config_path = ""
    session_profile_path = ""
    report_pack_summary_path = ""
    final_report_path = ""
    final_report_index_path = ""
    upgrade_report_txt_path = ""
    upgrade_report_json_path = ""
    rollback_report_txt_path = ""
    rollback_report_json_path = ""
    support_bundle_path = ""
    uninstall_validated = $false
}

$wizardProc = $null
$runnerProc = $null

try {
    if (Test-Path -LiteralPath $InstallRoot) {
        Remove-TreeRobust -PathValue $InstallRoot
    }

    $installResult = Invoke-CapturedProcess `
        -Label "install_bundle" `
        -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $installerPs1,
            "-InstallRoot", $InstallRoot,
            "-NoStartMenuShortcut",
            "-NoDesktopShortcut",
            "-NoUninstallRegistration",
            "-BootstrapPackageVerification",
            "-NoLaunch",
            "-Quiet"
        ) `
        -WorkingDirectory $PackageRoot
    Add-StepResult -Name "install_bundle" -Status "PASS" -Detail "Installed package into disposable acceptance root." -Extra @{
        stdout_path = $installResult.stdout_path
        stderr_path = $installResult.stderr_path
    }

    $runtimeRoot = Join-Path $InstallRoot "runtime"
    $codeRoot = Join-Path $runtimeRoot "MOLE_code"
    $dataRoot = Join-Path $InstallRoot "data"
    $logsDir = Join-Path $dataRoot "logs"
    $dataRootManifestPath = Join-Path $dataRoot "data_root_manifest_v1.json"
    $runtimeLogsDir = Join-Path $runtimeRoot "mole_das_data\\logs"
    $installedPython = Join-Path $codeRoot ".venv\\Scripts\\python.exe"
    $installedWizard = Join-Path $codeRoot "MOLE_DAS_Wizard.exe"
    $installedRunner = Join-Path $codeRoot "MOLE_DAQ_Runner.exe"
    $installedInstallClient = Join-Path $InstallRoot "MOLE_DAS_INSTALL_CLIENT.py"
    $buildIdentityPath = Join-Path $runtimeRoot "config\\mole_build_identity_v1.json"
    $welcomeManifestPath = Join-Path $runtimeRoot "config\\mole_welcome_asset_manifest_v1.json"
    $wizardStampPath = Join-Path $logsDir "wizard_startup__latest.json"
    $runnerStampPath = Join-Path $logsDir "runner_startup__latest.json"
    $installManifestPath = Join-Path $InstallRoot "mole_install_manifest_v1.json"

    foreach ($item in @(
        @{ path = $runtimeRoot; label = "Installed runtime root" },
        @{ path = $codeRoot; label = "Installed runtime code root" },
        @{ path = $installedPython; label = "Installed runtime Python" },
        @{ path = $installedWizard; label = "Installed Wizard executable" },
        @{ path = $installedRunner; label = "Installed Runner executable" },
        @{ path = $installedInstallClient; label = "Installed install client" },
        @{ path = $buildIdentityPath; label = "Installed build identity" },
        @{ path = $installManifestPath; label = "Installed install manifest" }
    )) {
        Require-Path -PathValue $item.path -Label $item.label
    }

    $buildIdentity = Get-Content -LiteralPath $buildIdentityPath -Raw | ConvertFrom-Json
    $summary.package_label = [string]$buildIdentity.bundle_label
    $summary.git_commit = [string]$buildIdentity.git_commit
    $summary.git_branch = [string]$buildIdentity.git_branch
    $summary.build_identity_path = $buildIdentityPath
    $summary.data_root = $dataRoot
    $summary.logs_dir = $logsDir
    if (Test-Path -LiteralPath $welcomeManifestPath) {
        $summary.welcome_manifest_path = $welcomeManifestPath
    }

    Add-StepResult -Name "validate_install_layout" -Status "PASS" -Detail "Validated installed runtime, executables, and manifests." -Extra @{
        installed_python = $installedPython
        build_identity_path = $buildIdentityPath
        install_manifest_path = $installManifestPath
    }

    $legacyRuntimeLogsDir = Join-Path $runtimeRoot "mole_das_data\\logs"
    $legacyRuntimeExportsDir = Join-Path $runtimeRoot "mole_das_data\\exports"
    $legacyRuntimeLogPath = Join-Path $legacyRuntimeLogsDir "legacy_runtime_probe.log"
    $legacyRuntimeExportPath = Join-Path $legacyRuntimeExportsDir "legacy_report_probe.txt"
    New-Item -ItemType Directory -Path $legacyRuntimeLogsDir -Force | Out-Null
    New-Item -ItemType Directory -Path $legacyRuntimeExportsDir -Force | Out-Null
    [System.IO.File]::WriteAllText($legacyRuntimeLogPath, "legacy log payload", (New-Object System.Text.UTF8Encoding($false)))
    [System.IO.File]::WriteAllText($legacyRuntimeExportPath, "legacy export payload", (New-Object System.Text.UTF8Encoding($false)))
    Add-StepResult -Name "seed_legacy_runtime_payload" -Status "PASS" -Detail "Seeded legacy mutable runtime payload to validate migration into the external data root." -Extra @{
        legacy_log_path = $legacyRuntimeLogPath
        legacy_export_path = $legacyRuntimeExportPath
    }

    Remove-Item -LiteralPath $wizardStampPath -Force -ErrorAction SilentlyContinue
    $wizardProc = Start-Process -FilePath $installedWizard -WorkingDirectory $codeRoot -PassThru
    if (-not (Wait-ForFile -PathValue $wizardStampPath -TimeoutSec 75)) {
        throw "Wizard startup stamp was not written: $wizardStampPath"
    }
    Require-Path -PathValue $dataRoot -Label "External writable data root"
    Require-Path -PathValue $dataRootManifestPath -Label "External data root manifest"
    $migratedLegacyLogPath = Join-Path $dataRoot "logs\\legacy_runtime_probe.log"
    $migratedLegacyExportPath = Join-Path $dataRoot "exports\\legacy_report_probe.txt"
    Require-Path -PathValue $migratedLegacyLogPath -Label "Migrated legacy runtime log"
    Require-Path -PathValue $migratedLegacyExportPath -Label "Migrated legacy runtime export"
    if (Test-Path -LiteralPath $legacyRuntimeLogPath) {
        throw "Legacy runtime log was not removed from the immutable runtime payload: $legacyRuntimeLogPath"
    }
    if (Test-Path -LiteralPath $legacyRuntimeExportPath) {
        throw "Legacy runtime export was not removed from the immutable runtime payload: $legacyRuntimeExportPath"
    }
    $dataRootManifest = Get-Content -LiteralPath $dataRootManifestPath -Raw | ConvertFrom-Json
    if ([string]$dataRootManifest.schema -ne "mole_data_root_manifest_v1") {
        throw "Data root manifest schema is invalid: $dataRootManifestPath"
    }
    if (-not $dataRootManifest.migration.performed) {
        throw "Data root manifest did not record the legacy runtime migration."
    }
    if (-not $dataRootManifest.migration.backup_path) {
        throw "Data root manifest did not record a migration backup path."
    }
    Require-Path -PathValue ([string]$dataRootManifest.migration.backup_path) -Label "Data root migration backup"
    $summary.wizard_startup_path = $wizardStampPath
    Copy-Item -LiteralPath $wizardStampPath -Destination (Join-Path $ArtifactOutDir "wizard_startup__latest.json") -Force
    Add-StepResult -Name "launch_wizard" -Status "PASS" -Detail "Installed Wizard launched and wrote startup diagnostics." -Extra @{
        startup_stamp = $wizardStampPath
        data_root = $dataRoot
    }
    Add-StepResult -Name "validate_data_root_manifest" -Status "PASS" -Detail "Validated data-root manifest creation, legacy payload migration, and migration backup." -Extra @{
        data_root_manifest_path = $dataRootManifestPath
        migrated_legacy_log_path = $migratedLegacyLogPath
        migrated_legacy_export_path = $migratedLegacyExportPath
        migration_backup_path = [string]$dataRootManifest.migration.backup_path
    }
    Start-Sleep -Seconds 2
    Stop-ProcessIfRunning -ProcessObject $wizardProc
    $wizardProc = $null

    $seedInfo = Invoke-EmbeddedPythonJson `
        -Label "seed_integration_session" `
        -PythonExe $installedPython `
        -WorkingDirectory $codeRoot `
        -Source @"
import json
from pathlib import Path
from mole_smoketest import _seed_integration_session

root = Path(r'''$runtimeRoot''')
session_dir = _seed_integration_session(root)
if session_dir is None:
    raise SystemExit("Failed to seed integration session")
runner_config = session_dir / "runner_config.json"
session_profile = session_dir / "session_profile.json"
payload = {
    "session_dir": str(session_dir),
    "runner_config_path": str(runner_config),
    "session_profile_path": str(session_profile),
}
print(json.dumps(payload))
"@
    $summary.session_dir = [string]$seedInfo.session_dir
    $summary.runner_config_path = [string]$seedInfo.runner_config_path
    $summary.session_profile_path = [string]$seedInfo.session_profile_path
    Require-Path -PathValue $summary.session_dir -Label "Seeded acceptance session"
    Require-Path -PathValue $summary.runner_config_path -Label "Seeded runner config"
    Require-Path -PathValue $summary.session_profile_path -Label "Seeded session profile"
    if (-not ([string]$summary.session_dir).StartsWith([System.IO.Path]::GetFullPath($dataRoot), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Seeded acceptance session was not written under the external data root: $($summary.session_dir)"
    }
    Add-StepResult -Name "seed_session" -Status "PASS" -Detail "Seeded deterministic session fixture inside the installed runtime." -Extra @{
        session_dir = $summary.session_dir
        runner_config_path = $summary.runner_config_path
    }

    Remove-Item -LiteralPath $runnerStampPath -Force -ErrorAction SilentlyContinue
    $runnerProc = Start-Process -FilePath $installedRunner -ArgumentList @("--config", $summary.runner_config_path, "--ui", "--driver", "SIM") -WorkingDirectory $codeRoot -PassThru
    if (-not (Wait-ForFile -PathValue $runnerStampPath -TimeoutSec 75)) {
        throw "Runner startup stamp was not written: $runnerStampPath"
    }
    $summary.runner_startup_path = $runnerStampPath
    Copy-Item -LiteralPath $runnerStampPath -Destination (Join-Path $ArtifactOutDir "runner_startup__latest.json") -Force
    Add-StepResult -Name "launch_runner" -Status "PASS" -Detail "Installed Runner launched in SIM UI mode and wrote startup diagnostics." -Extra @{
        startup_stamp = $runnerStampPath
        runner_config_path = $summary.runner_config_path
    }
    Start-Sleep -Seconds 3
    Stop-ProcessIfRunning -ProcessObject $runnerProc
    $runnerProc = $null

    if (Test-Path -LiteralPath $runtimeLogsDir) {
        $runtimeLogFiles = Get-ChildItem -LiteralPath $runtimeLogsDir -Filter "*startup*.json" -ErrorAction SilentlyContinue
        if ($runtimeLogFiles) {
            throw "Packaged runtime wrote startup diagnostics into the immutable runtime payload: $runtimeLogsDir"
        }
    }
    Add-StepResult -Name "validate_external_data_root" -Status "PASS" -Detail "Installed runtime wrote mutable data into the external data root, not the runtime payload." -Extra @{
        data_root = $dataRoot
        logs_dir = $logsDir
        runtime_logs_dir = $runtimeLogsDir
    }

    $reportResult = Invoke-CapturedProcess `
        -Label "report_pack_export" `
        -FilePath $installedPython `
        -ArgumentList @((Join-Path $codeRoot "mole_report_pack_v1.py"), "--session-dir", $summary.session_dir) `
        -WorkingDirectory $codeRoot

    $reportSummaryPath = Join-Path $summary.session_dir "exports\\report_pack_v1\\summary.json"
    Require-Path -PathValue $reportSummaryPath -Label "Report pack summary"
    $reportSummary = Get-Content -LiteralPath $reportSummaryPath -Raw | ConvertFrom-Json
    $finalReportPath = [string]$reportSummary.final_report.markdown_path
    $finalReportIndexPath = [string]$reportSummary.final_report.index_path
    Require-Path -PathValue $finalReportPath -Label "Final report markdown"
    Require-Path -PathValue $finalReportIndexPath -Label "Final report index"
    $summary.report_pack_summary_path = $reportSummaryPath
    $summary.final_report_path = $finalReportPath
    $summary.final_report_index_path = $finalReportIndexPath
    Copy-Item -LiteralPath $reportSummaryPath -Destination (Join-Path $ArtifactOutDir "report_pack_summary.json") -Force
    Copy-Item -LiteralPath $finalReportPath -Destination (Join-Path $ArtifactOutDir ([System.IO.Path]::GetFileName($finalReportPath))) -Force
    Copy-Item -LiteralPath $finalReportIndexPath -Destination (Join-Path $ArtifactOutDir ([System.IO.Path]::GetFileName($finalReportIndexPath))) -Force
    Add-StepResult -Name "export_report_pack" -Status "PASS" -Detail "Installed runtime exported a report pack from the seeded session." -Extra @{
        stdout_path = $reportResult.stdout_path
        stderr_path = $reportResult.stderr_path
        summary_path = $reportSummaryPath
    }

    $upgradeReportDir = Join-Path $dataRoot "backups\\upgrade_reviews"
    $upgradeReportArtifactDir = Join-Path $ArtifactOutDir "upgrade_reports"
    New-Item -ItemType Directory -Path $upgradeReportArtifactDir -Force | Out-Null
    $upgradeReportResult = Invoke-CapturedProcess `
        -Label "export_upgrade_report" `
        -FilePath $installedPython `
        -ArgumentList @($installedInstallClient, "--package-root", $InstallRoot, "--install-root", $InstallRoot, "--headless-export-upgrade-report", $upgradeReportDir) `
        -WorkingDirectory $InstallRoot
    try {
        $upgradeReportInfo = $upgradeReportResult.stdout | ConvertFrom-Json
    }
    catch {
        throw "Failed to parse upgrade report export output.`nSTDOUT:`n$($upgradeReportResult.stdout)`nSTDERR:`n$($upgradeReportResult.stderr)"
    }
    $summary.upgrade_report_txt_path = [string]($(if ($upgradeReportInfo.latest_txt_path) { $upgradeReportInfo.latest_txt_path } else { $upgradeReportInfo.txt_path }))
    $summary.upgrade_report_json_path = [string]($(if ($upgradeReportInfo.latest_json_path) { $upgradeReportInfo.latest_json_path } else { $upgradeReportInfo.json_path }))
    Require-Path -PathValue $summary.upgrade_report_txt_path -Label "Upgrade report text"
    Require-Path -PathValue $summary.upgrade_report_json_path -Label "Upgrade report JSON"
    Copy-Item -LiteralPath $summary.upgrade_report_txt_path -Destination (Join-Path $upgradeReportArtifactDir "upgrade_report__latest.txt") -Force
    Copy-Item -LiteralPath $summary.upgrade_report_json_path -Destination (Join-Path $upgradeReportArtifactDir "upgrade_report__latest.json") -Force
    Add-StepResult -Name "export_upgrade_report" -Status "PASS" -Detail "Installed bundle exported the upgrade preview report from the shipped install client." -Extra @{
        stdout_path = $upgradeReportResult.stdout_path
        stderr_path = $upgradeReportResult.stderr_path
        upgrade_report_txt_path = $summary.upgrade_report_txt_path
        upgrade_report_json_path = $summary.upgrade_report_json_path
    }

    $rollbackProbePath = Join-Path $dataRoot "configs\\rollback_restore_probe.json"
    New-Item -ItemType Directory -Path (Split-Path -Parent $rollbackProbePath) -Force | Out-Null
    $rollbackBaseline = [ordered]@{
        state = "baseline_before_restore"
        package_label = $summary.package_label
        git_commit = $summary.git_commit
    }
    Write-JsonUtf8 -PathValue $rollbackProbePath -Payload $rollbackBaseline
    Add-StepResult -Name "seed_rollback_probe" -Status "PASS" -Detail "Seeded rollback probe file in the external data root." -Extra @{
        rollback_probe_path = $rollbackProbePath
    }

    $repairResult = Invoke-CapturedProcess `
        -Label "repair_bundle_for_rollback" `
        -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", (Join-Path $InstallRoot "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1"),
            "-InstallRoot", $InstallRoot,
            "-NoStartMenuShortcut",
            "-NoDesktopShortcut",
            "-NoUninstallRegistration",
            "-BootstrapPackageVerification",
            "-NoLaunch",
            "-Quiet"
        ) `
        -WorkingDirectory $InstallRoot
    $restorePointsRoot = Join-Path $InstallRoot "_data_restore_points"
    $restorePointManifest = Get-ChildItem -LiteralPath $restorePointsRoot -Filter "restore_point_manifest_v1.json" -Recurse -File -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $restorePointManifest) {
        throw "Repair pass did not create a restore point under $restorePointsRoot"
    }
    Add-StepResult -Name "capture_restore_point" -Status "PASS" -Detail "Repair pass captured a rollback restore point before reapplying the installed payload during bootstrap acceptance validation." -Extra @{
        stdout_path = $repairResult.stdout_path
        stderr_path = $repairResult.stderr_path
        restore_point_manifest_path = $restorePointManifest.FullName
    }

    $rollbackMutated = [ordered]@{
        state = "mutated_after_restore_point"
        package_label = $summary.package_label
        git_commit = $summary.git_commit
    }
    Write-JsonUtf8 -PathValue $rollbackProbePath -Payload $rollbackMutated
    Add-StepResult -Name "mutate_rollback_probe" -Status "PASS" -Detail "Mutated rollback probe after restore-point capture so rollback can prove restoration." -Extra @{
        rollback_probe_path = $rollbackProbePath
    }

    $rollbackReportDir = Join-Path $InstallRoot "_rollback_reports"
    $rollbackReportArtifactDir = Join-Path $ArtifactOutDir "rollback_reports"
    New-Item -ItemType Directory -Path $rollbackReportArtifactDir -Force | Out-Null
    $rollbackReportResult = Invoke-CapturedProcess `
        -Label "export_rollback_report" `
        -FilePath $installedPython `
        -ArgumentList @($installedInstallClient, "--package-root", $InstallRoot, "--install-root", $InstallRoot, "--headless-export-rollback-report", $rollbackReportDir) `
        -WorkingDirectory $InstallRoot
    try {
        $rollbackReportInfo = $rollbackReportResult.stdout | ConvertFrom-Json
    }
    catch {
        throw "Failed to parse rollback report export output.`nSTDOUT:`n$($rollbackReportResult.stdout)`nSTDERR:`n$($rollbackReportResult.stderr)"
    }
    $summary.rollback_report_txt_path = [string]($(if ($rollbackReportInfo.latest_txt_path) { $rollbackReportInfo.latest_txt_path } else { $rollbackReportInfo.txt_path }))
    $summary.rollback_report_json_path = [string]($(if ($rollbackReportInfo.latest_json_path) { $rollbackReportInfo.latest_json_path } else { $rollbackReportInfo.json_path }))
    Require-Path -PathValue $summary.rollback_report_txt_path -Label "Rollback report text"
    Require-Path -PathValue $summary.rollback_report_json_path -Label "Rollback report JSON"
    Copy-Item -LiteralPath $summary.rollback_report_txt_path -Destination (Join-Path $rollbackReportArtifactDir "rollback_report__latest.txt") -Force
    Copy-Item -LiteralPath $summary.rollback_report_json_path -Destination (Join-Path $rollbackReportArtifactDir "rollback_report__latest.json") -Force
    Add-StepResult -Name "export_rollback_report" -Status "PASS" -Detail "Installed bundle exported the rollback preview report from the shipped install client." -Extra @{
        stdout_path = $rollbackReportResult.stdout_path
        stderr_path = $rollbackReportResult.stderr_path
        rollback_report_txt_path = $summary.rollback_report_txt_path
        rollback_report_json_path = $summary.rollback_report_json_path
    }

    $rollbackApplyResult = Invoke-CapturedProcess `
        -Label "apply_rollback_restore" `
        -FilePath $installedPython `
        -ArgumentList @($installedInstallClient, "--package-root", $InstallRoot, "--install-root", $InstallRoot, "--headless-apply-rollback") `
        -WorkingDirectory $InstallRoot
    try {
        $rollbackApplyInfo = $rollbackApplyResult.stdout | ConvertFrom-Json
    }
    catch {
        throw "Failed to parse rollback apply output.`nSTDOUT:`n$($rollbackApplyResult.stdout)`nSTDERR:`n$($rollbackApplyResult.stderr)"
    }
    Require-Path -PathValue $rollbackProbePath -Label "Rollback probe after restore"
    $rollbackProbePayload = Get-Content -LiteralPath $rollbackProbePath -Raw | ConvertFrom-Json
    if ([string]$rollbackProbePayload.state -ne "baseline_before_restore") {
        throw "Rollback did not restore the expected probe state."
    }
    Add-StepResult -Name "apply_rollback_restore" -Status "PASS" -Detail "Rollback restored the external data root from the latest restore point." -Extra @{
        stdout_path = $rollbackApplyResult.stdout_path
        stderr_path = $rollbackApplyResult.stderr_path
        rollback_probe_path = $rollbackProbePath
        restore_point_manifest_path = [string]$rollbackApplyInfo.restore_point_manifest_path
        pre_restore_point_manifest_path = [string]$rollbackApplyInfo.pre_restore_point_manifest_path
    }

    $supportBundleRoot = Join-Path $ArtifactOutDir "support_bundles"
    New-Item -ItemType Directory -Path $supportBundleRoot -Force | Out-Null
    $supportInfo = Invoke-EmbeddedPythonJson `
        -Label "export_support_bundle" `
        -PythonExe $installedPython `
        -WorkingDirectory $codeRoot `
        -Source @"
import json
from pathlib import Path
from mole_runtime_durability_v1 import create_support_bundle

bundle_root = Path(r'''$supportBundleRoot''')
manifest = {
    "schema": "mole_packaged_acceptance_support_bundle_v1",
    "package_label": r'''$($summary.package_label)''',
    "git_commit": r'''$($summary.git_commit)''',
    "git_branch": r'''$($summary.git_branch)''',
    "session_dir": r'''$($summary.session_dir)''',
}
artifacts = {
    "build_identity": Path(r'''$buildIdentityPath'''),
    "welcome_manifest": Path(r'''$welcomeManifestPath''') if r'''$welcomeManifestPath''' else None,
    "data_root_manifest": Path(r'''$dataRootManifestPath'''),
    "restore_point_manifest": Path(r'''$($restorePointManifest.FullName)''') if r'''$($restorePointManifest.FullName)''' else None,
    "wizard_startup": Path(r'''$wizardStampPath'''),
    "runner_startup": Path(r'''$runnerStampPath'''),
    "runner_config": Path(r'''$($summary.runner_config_path)'''),
    "session_profile": Path(r'''$($summary.session_profile_path)'''),
    "report_pack_summary": Path(r'''$reportSummaryPath'''),
    "final_report_markdown": Path(r'''$finalReportPath'''),
    "final_report_index": Path(r'''$finalReportIndexPath'''),
    "upgrade_report_txt": Path(r'''$($summary.upgrade_report_txt_path)'''),
    "upgrade_report_json": Path(r'''$($summary.upgrade_report_json_path)'''),
    "rollback_report_txt": Path(r'''$($summary.rollback_report_txt_path)'''),
    "rollback_report_json": Path(r'''$($summary.rollback_report_json_path)'''),
}
zip_path = create_support_bundle(
    bundle_root,
    label="packaged_acceptance_bundle",
    manifest=manifest,
    artifacts=artifacts,
    keep=5,
)
print(json.dumps({"zip_path": str(zip_path)}))
"@
    $summary.support_bundle_path = [string]$supportInfo.zip_path
    Require-Path -PathValue $summary.support_bundle_path -Label "Acceptance support bundle"
    Add-StepResult -Name "export_support_bundle" -Status "PASS" -Detail "Exported support bundle from installed runtime outputs." -Extra @{
        support_bundle_path = $summary.support_bundle_path
    }

    if ($KeepInstall) {
        Add-StepResult -Name "uninstall_bundle" -Status "SKIP" -Detail "Install root was retained by request."
    }
    else {
        $uninstallPs1 = Join-Path $InstallRoot "UNINSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
        Require-Path -PathValue $uninstallPs1 -Label "Installed uninstaller"
        $uninstallResult = Invoke-CapturedProcess `
            -Label "uninstall_bundle" `
            -FilePath "powershell.exe" `
            -ArgumentList @(
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", $uninstallPs1,
                "-InstallRoot", $InstallRoot,
                "-Quiet"
            ) `
            -WorkingDirectory $InstallRoot
        if (-not (Wait-ForPathRemoval -PathValue $InstallRoot -TimeoutSec 120)) {
            throw "Installed root still exists after uninstall wait window: $InstallRoot"
        }
        $summary.uninstall_validated = $true
        Add-StepResult -Name "uninstall_bundle" -Status "PASS" -Detail "Installed bundle uninstalled cleanly." -Extra @{
            stdout_path = $uninstallResult.stdout_path
            stderr_path = $uninstallResult.stderr_path
        }
    }

    $summary.status = "PASS"
}
catch {
    $summary.status = "FAIL"
    $summary["error"] = $_.Exception.Message
    Add-StepResult -Name "fatal" -Status "FAIL" -Detail $_.Exception.Message
}
finally {
    Stop-ProcessIfRunning -ProcessObject $wizardProc
    Stop-ProcessIfRunning -ProcessObject $runnerProc
    Save-SummaryFiles -JsonPath $summaryJsonPath -TextPath $summaryTextPath -Summary $summary
}

if ($summary.status -ne "PASS") {
    throw $summary.error
}

Write-Host ""
Write-Host "Packaged acceptance passed."
Write-Host "  Summary: $summaryJsonPath"
Write-Host "  Artifacts: $ArtifactOutDir"
