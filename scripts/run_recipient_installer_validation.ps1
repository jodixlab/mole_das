param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerZip,

    [string]$ValidationRoot = "",
    [string]$ArtifactOutDir = "",
    [string]$ExpectedPackageLabel = "",
    [string]$ExpectedGitCommit = "",
    [int]$TimeoutSeconds = 120,
    [int]$DiagnosticsSampleCount = 2
)

$ErrorActionPreference = "Stop"

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

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Set-JsonProperty {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$Name,
        $Value
    )

    if ($Object.PSObject.Properties[$Name]) {
        $Object.$Name = $Value
    }
    else {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
    }
}

function Ensure-ObjectProperty {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if (-not $Object.PSObject.Properties[$Name] -or $null -eq $Object.$Name) {
        Set-JsonProperty -Object $Object -Name $Name -Value ([pscustomobject]@{})
    }
    return $Object.$Name
}

function Wait-ForFileOrExit {
    param(
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $Path) {
            return $true
        }
        if ($Process.HasExited) {
            return (Test-Path -LiteralPath $Path)
        }
        Start-Sleep -Milliseconds 500
    }
    return (Test-Path -LiteralPath $Path)
}

function Stop-IfRunning {
    param($Process)

    if ($null -ne $Process -and -not $Process.HasExited) {
        Start-Sleep -Seconds 2
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force
        }
    }
}

function Assert-Path {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Description not found: $Path"
    }
}

$installerPath = (Resolve-Path -LiteralPath $InstallerZip).Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
if (-not $ValidationRoot) {
    $ValidationRoot = Join-Path ([System.IO.Path]::GetTempPath()) "mole_recipient_validation_$stamp"
}
$validationRootPath = $ValidationRoot
if (Test-Path -LiteralPath $validationRootPath) {
    $existing = Get-ChildItem -LiteralPath $validationRootPath -Force -ErrorAction SilentlyContinue
    if ($existing) {
        throw "ValidationRoot must be empty or unique: $validationRootPath"
    }
}
New-Item -ItemType Directory -Force -Path $validationRootPath | Out-Null

if (-not $ArtifactOutDir) {
    $ArtifactOutDir = $validationRootPath
}
New-Item -ItemType Directory -Force -Path $ArtifactOutDir | Out-Null

$packageRoot = Join-Path $validationRootPath "package"
$installRoot = Join-Path $validationRootPath "installed"
$summaryJson = Join-Path $ArtifactOutDir "RECIPIENT_VALIDATION_FROM_INSTALLER.json"
$summaryMd = Join-Path $ArtifactOutDir "RECIPIENT_VALIDATION_FROM_INSTALLER.md"

$summary = [ordered]@{
    schema = "mole_recipient_installer_validation_v1"
    status = "RUNNING"
    started_at = (Get-Date).ToUniversalTime().ToString("o")
    installer_zip = $installerPath
    installer_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $installerPath).Hash
    validation_root = $validationRootPath
    package_root = $packageRoot
    install_root = $installRoot
    expected_package_label = $ExpectedPackageLabel
    expected_git_commit = $ExpectedGitCommit
    steps = @()
}

function Add-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Status,
        [string]$Detail = ""
    )

    $summary.steps += [ordered]@{
        name = $Name
        status = $Status
        detail = $Detail
        at = (Get-Date).ToUniversalTime().ToString("o")
    }
}

try {
    Write-Host "Extracting installer bundle..."
    Expand-Archive -LiteralPath $installerPath -DestinationPath $packageRoot -Force
    $installScript = Get-ChildItem -LiteralPath $packageRoot -Recurse -Filter "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1" |
        Select-Object -First 1
    if ($null -eq $installScript) {
        throw "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1 was not found in extracted package."
    }
    Add-Step -Name "extract_installer_zip" -Status "PASS" -Detail $packageRoot

    Write-Host "Installing into isolated validation root..."
    $installArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $installScript.FullName,
        "-InstallRoot", $installRoot,
        "-NoDesktopShortcut",
        "-NoStartMenuShortcut",
        "-NoUninstallRegistration",
        "-BootstrapPackageVerification",
        "-NoLaunch",
        "-Quiet"
    )
    & powershell.exe @installArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Installer exited with code $LASTEXITCODE"
    }
    Add-Step -Name "install_bundle" -Status "PASS" -Detail $installRoot

    $wizardExe = Join-Path $installRoot "runtime\MOLE_code\MOLE_DAS_Wizard.exe"
    $runnerExe = Join-Path $installRoot "runtime\MOLE_code\MOLE_DAQ_Runner.exe"
    $runtimeCode = Join-Path $installRoot "runtime\MOLE_code"
    $dataRoot = Join-Path $installRoot "data"
    $logsDir = Join-Path $dataRoot "logs"
    $installManifestPath = Join-Path $installRoot "mole_install_manifest_v1.json"
    $buildIdentityPath = Join-Path $installRoot "runtime\config\mole_build_identity_v1.json"
    $latestVerifiedPath = Join-Path $installRoot "latest_verified_release_v1.json"
    Assert-Path -Path $wizardExe -Description "Wizard executable"
    Assert-Path -Path $runnerExe -Description "Runner executable"
    Assert-Path -Path $installManifestPath -Description "Install manifest"
    Assert-Path -Path $buildIdentityPath -Description "Build identity"
    Assert-Path -Path $latestVerifiedPath -Description "Latest verified release manifest"

    $installManifest = Read-JsonFile -Path $installManifestPath
    $buildIdentity = Read-JsonFile -Path $buildIdentityPath
    $latestVerified = Read-JsonFile -Path $latestVerifiedPath
    $summary.install_manifest = [ordered]@{
        path = $installManifestPath
        install_root = $installManifest.install_root
        runtime_root = $installManifest.runtime_root
        data_root = $installManifest.data_root
        bundle_label = $installManifest.bundle_label
        git_commit = $installManifest.git_commit
    }
    $summary.build_identity = [ordered]@{
        path = $buildIdentityPath
        bundle_label = $buildIdentity.bundle_label
        git_commit = $buildIdentity.git_commit
        git_branch = $buildIdentity.git_branch
        built_at = $buildIdentity.built_at
    }
    $summary.latest_verified_release = [ordered]@{
        path = $latestVerifiedPath
        package_label = $latestVerified.package_label
        acceptance_status = $latestVerified.acceptance_status
        trust_check_status = $latestVerified.trust_check_status
    }

    if ($ExpectedPackageLabel -and $buildIdentity.bundle_label -ne $ExpectedPackageLabel) {
        throw "Expected package label $ExpectedPackageLabel but installed $($buildIdentity.bundle_label)"
    }
    if ($ExpectedGitCommit -and $buildIdentity.git_commit -ne $ExpectedGitCommit) {
        throw "Expected git commit $ExpectedGitCommit but installed $($buildIdentity.git_commit)"
    }
    Add-Step -Name "verify_installed_identity" -Status "PASS" -Detail "$($buildIdentity.bundle_label) $($buildIdentity.git_commit)"

    Write-Host "Smoke-launching Wizard..."
    $wizardStamp = Join-Path $logsDir "wizard_startup__latest.json"
    if (Test-Path -LiteralPath $wizardStamp) {
        Remove-Item -LiteralPath $wizardStamp -Force
    }
    $wizardProcess = Start-Process -FilePath $wizardExe -WorkingDirectory $runtimeCode -WindowStyle Hidden -PassThru
    $wizardSeen = Wait-ForFileOrExit -Process $wizardProcess -Path $wizardStamp -TimeoutSeconds $TimeoutSeconds
    Stop-IfRunning -Process $wizardProcess
    if (-not $wizardSeen) {
        throw "Wizard startup stamp was not produced: $wizardStamp"
    }
    $wizardStartup = Read-JsonFile -Path $wizardStamp
    $summary.wizard_launch_smoke = [ordered]@{
        status = "PASS"
        startup_stamp = $wizardStamp
        app = $wizardStartup.app
        launch_mode = $wizardStartup.launch_mode
        package_label = $wizardStartup.package_label
        git_commit = $wizardStartup.git_commit
        package_status = $wizardStartup.package_status
        trust_check_status = $wizardStartup.current_trust_check_status
        active_config_path = $wizardStartup.active_config_path
    }
    Add-Step -Name "wizard_launch_smoke" -Status "PASS" -Detail $wizardStamp

    Write-Host "Preparing diagnostics-only Runner config..."
    $baseConfig = Get-ChildItem -LiteralPath (Join-Path $dataRoot "configs") -Filter "mole_session_*.json" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $baseConfig) {
        throw "No installed session config found under $dataRoot\configs"
    }
    $diagDir = Join-Path $dataRoot "training\sessions\recipient_validation_diagnostics"
    New-Item -ItemType Directory -Force -Path $diagDir | Out-Null
    $diagConfigPath = Join-Path $diagDir "runner_config_diag_training.json"
    $session = Read-JsonFile -Path $baseConfig.FullName
    $sessionMode = Ensure-ObjectProperty -Object $session -Name "session_mode"
    $daqRunner = Ensure-ObjectProperty -Object $session -Name "daq_runner"
    $paths = Ensure-ObjectProperty -Object $session -Name "paths"

    Set-JsonProperty -Object $session -Name "environment" -Value "TRAINING"
    Set-JsonProperty -Object $session -Name "run_id" -Value "recipient_validation_diagnostics"
    Set-JsonProperty -Object $session -Name "run_day" -Value "recipient_validation"
    Set-JsonProperty -Object $sessionMode -Name "diagnostic_only" -Value $true
    Set-JsonProperty -Object $sessionMode -Name "may_support_compliance" -Value $false
    Set-JsonProperty -Object $sessionMode -Name "record_data" -Value $true
    Set-JsonProperty -Object $sessionMode -Name "tokenize" -Value $false
    Set-JsonProperty -Object $sessionMode -Name "mode" -Value "DIAGNOSTICS_TRAINING_SESSION"
    Set-JsonProperty -Object $daqRunner -Name "ui_mode" -Value "DIAGNOSTICS"
    Set-JsonProperty -Object $daqRunner -Name "report_pack_enabled" -Value $false
    Set-JsonProperty -Object $daqRunner -Name "formal_report_enabled" -Value $false
    Set-JsonProperty -Object $daqRunner -Name "diagnostics_export_enabled" -Value $true
    Set-JsonProperty -Object $paths -Name "session_dir" -Value $diagDir
    Set-JsonProperty -Object $paths -Name "daq_run_dir" -Value $diagDir
    Set-JsonProperty -Object $paths -Name "runner_config_path" -Value $diagConfigPath
    Write-Utf8NoBom -Path $diagConfigPath -Text ($session | ConvertTo-Json -Depth 100)
    Add-Step -Name "prepare_runner_diagnostics_config" -Status "PASS" -Detail $diagConfigPath

    Write-Host "Running Runner diagnostics snapshot..."
    $runnerStamp = Join-Path $logsDir "runner_startup__latest.json"
    $diagManifestPath = Join-Path $diagDir "exports\diagnostic_snapshots\diagnostics_snapshot_manifest.json"
    $stdoutPath = Join-Path $diagDir "recipient_runner_stdout.txt"
    $stderrPath = Join-Path $diagDir "recipient_runner_stderr.txt"
    foreach ($target in @($runnerStamp, $diagManifestPath, $stdoutPath, $stderrPath)) {
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Force
        }
    }
    $runnerArgs = @(
        "--config", $diagConfigPath,
        "--driver", "SIM",
        "--diagnostics-export-snapshot",
        "--diagnostics-sample-count", ([string]$DiagnosticsSampleCount),
        "--outdir", $diagDir
    )
    $runnerProcess = Start-Process -FilePath $runnerExe -ArgumentList $runnerArgs -WorkingDirectory $runtimeCode -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
    $diagSeen = Wait-ForFileOrExit -Process $runnerProcess -Path $diagManifestPath -TimeoutSeconds $TimeoutSeconds
    Stop-IfRunning -Process $runnerProcess
    if (-not $diagSeen) {
        $stderrText = ""
        if (Test-Path -LiteralPath $stderrPath) {
            $stderrText = Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue
        }
        throw "Runner diagnostics manifest was not produced: $diagManifestPath`n$stderrText"
    }
    $diagManifest = Read-JsonFile -Path $diagManifestPath
    $runnerStartup = if (Test-Path -LiteralPath $runnerStamp) { Read-JsonFile -Path $runnerStamp } else { $null }

    $diagPass = (
        $diagManifest.status -eq "PASS" -and
        [bool]$diagManifest.diagnostic_only -and
        -not [bool]$diagManifest.may_support_compliance -and
        -not [bool]$diagManifest.report_pack_enabled -and
        -not [bool]$diagManifest.formal_report_enabled -and
        [int]$diagManifest.samples_captured -ge 1
    )
    if (-not $diagPass) {
        throw "Runner diagnostics manifest did not meet recipient validation gates: $diagManifestPath"
    }
    $summary.runner_diagnostics_smoke = [ordered]@{
        status = $diagManifest.status
        startup_stamp = $runnerStamp
        manifest_path = $diagManifestPath
        stdout_path = $stdoutPath
        stderr_path = $stderrPath
        config_path = $diagConfigPath
        diagnostic_only = $diagManifest.diagnostic_only
        may_support_compliance = $diagManifest.may_support_compliance
        report_pack_enabled = $diagManifest.report_pack_enabled
        formal_report_enabled = $diagManifest.formal_report_enabled
        compliance_claimed = $diagManifest.compliance_claimed
        samples_captured = $diagManifest.samples_captured
        driver = $diagManifest.driver
        snapshot_path = $diagManifest.snapshot_path
        calc_audit_json_path = $diagManifest.calc_audit_json_path
        calc_audit_csv_path = $diagManifest.calc_audit_csv_path
        runner_active_config_path = if ($null -ne $runnerStartup) { $runnerStartup.active_config_path } else { "" }
        runner_package_label = if ($null -ne $runnerStartup) { $runnerStartup.package_label } else { "" }
        runner_git_commit = if ($null -ne $runnerStartup) { $runnerStartup.git_commit } else { "" }
        package_status = if ($null -ne $runnerStartup) { $runnerStartup.package_status } else { "" }
        trust_check_status = if ($null -ne $runnerStartup) { $runnerStartup.current_trust_check_status } else { "" }
    }
    Add-Step -Name "runner_diagnostics_smoke" -Status "PASS" -Detail $diagManifestPath

    $summary.status = "PASS"
}
catch {
    $summary.status = "FAIL"
    $summary.error = $_.Exception.Message
    Add-Step -Name "recipient_validation" -Status "FAIL" -Detail $_.Exception.Message
}
finally {
    $summary.completed_at = (Get-Date).ToUniversalTime().ToString("o")
    $json = $summary | ConvertTo-Json -Depth 30
    Write-Utf8NoBom -Path $summaryJson -Text $json

    $lines = @(
        "# MOLE-DAS Recipient Installer Validation",
        "",
        "- Status: ``$($summary.status)``",
        "- Installer ZIP: ``$installerPath``",
        "- Installer SHA256: ``$($summary.installer_sha256)``",
        "- Validation root: ``$validationRootPath``",
        "- Install root: ``$installRoot``",
        "- Expected package: ``$ExpectedPackageLabel``",
        "- Expected commit: ``$ExpectedGitCommit``",
        "",
        "## Steps",
        ""
    )
    foreach ($step in $summary.steps) {
        $lines += "- $($step.name): ``$($step.status)`` $($step.detail)"
    }
    if ($summary.runner_diagnostics_smoke) {
        $r = $summary.runner_diagnostics_smoke
        $lines += ""
        $lines += "## Runner Diagnostics"
        $lines += ""
        $lines += "- Manifest: ``$($r.manifest_path)``"
        $lines += "- Flags: diagnostic_only=``$($r.diagnostic_only)``, may_support_compliance=``$($r.may_support_compliance)``, report_pack_enabled=``$($r.report_pack_enabled)``, formal_report_enabled=``$($r.formal_report_enabled)``"
        $lines += "- Samples captured: ``$($r.samples_captured)``"
    }
    if ($summary.error) {
        $lines += ""
        $lines += "## Error"
        $lines += ""
        $lines += $summary.error
    }
    Write-Utf8NoBom -Path $summaryMd -Text ($lines -join [Environment]::NewLine)
}

if ($summary.status -ne "PASS") {
    throw "Recipient installer validation failed. See $summaryJson"
}

Write-Host "Recipient installer validation PASS"
Write-Host "Summary JSON: $summaryJson"
Write-Host "Summary MD: $summaryMd"
