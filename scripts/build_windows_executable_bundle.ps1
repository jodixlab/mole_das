param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,

    [string]$BundleLabel = "MOLE_DAS_WINDOWS_EXE_BUNDLE"
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
Expand-Archive -LiteralPath $runtimeZip -DestinationPath $runtimeRoot -Force

$buildIdentityPath = Join-Path $runtimeConfigRoot "mole_build_identity_v1.json"
$gitCommit = ""
$gitBranch = ""
try {
    $gitCommit = (git -C $RepoRoot rev-parse --short HEAD 2>$null | Select-Object -First 1).Trim()
}
catch {}
try {
    $gitBranch = (git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null | Select-Object -First 1).Trim()
}
catch {}
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
    "MOLE_DAS.ico"
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
    [switch]$Quiet
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

Write-Status ""
Write-Status "Uninstalling MOLE-DAS"
Write-Status "  Install root: $InstallRoot"

Assert-ProcessesClosed -TargetRoot $InstallRoot

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

$cleanupScript = Join-Path $env:TEMP ("mole_uninstall_cleanup_" + [guid]::NewGuid().ToString("N") + ".cmd")
$cleanupBody = @(
    "@echo off",
    "ping 127.0.0.1 -n 4 >nul",
    'rmdir /s /q "' + $InstallRoot + '"',
    'del /f /q "%~f0"'
) -join "`r`n"
[System.IO.File]::WriteAllText(
    $cleanupScript,
    $cleanupBody,
    (New-Object System.Text.ASCIIEncoding)
)
Start-Process -FilePath "cmd.exe" -ArgumentList ('/c "' + $cleanupScript + '"') -WorkingDirectory $env:TEMP -WindowStyle Hidden

Write-Status "Uninstall scheduled."
Write-Status "  Root removal: $InstallRoot"
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

if (Test-Path -LiteralPath $shareZip) {
    Remove-Item -LiteralPath $shareZip -Force
}
if (Test-Path -LiteralPath $installerZip) {
    Remove-Item -LiteralPath $installerZip -Force
}
Invoke-Native -FilePath $python -ArgumentList @(
    "-c",
    @"
from pathlib import Path
import zipfile
src = Path(r'''$installRoot''')
targets = [
    Path(r'''$shareZip'''),
    Path(r'''$installerZip'''),
]
for dst in targets:
    with zipfile.ZipFile(dst, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for path in src.rglob('*'):
            if path.is_file():
                zf.write(path, path.relative_to(src))
"@
) -WorkingDirectory $RepoRoot

Write-Host ""
Write-Host "Executable bundle ready:"
Write-Host "  $OutputRoot"
