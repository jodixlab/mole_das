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

$welcomeManifestPath = Join-Path $runtimeConfigRoot "mole_welcome_asset_manifest_v1.json"
$welcomeAssetApproved = $false
if (Test-Path -LiteralPath $welcomeManifestPath) {
    try {
        $welcomeManifest = Get-Content -LiteralPath $welcomeManifestPath -Raw | ConvertFrom-Json
        $welcomeAssetApproved = [bool]$welcomeManifest.approved
        $welcomeManifest.packaged_build_version = $BundleLabel
        $welcomeManifest.packaged_build_at = (Get-Date).ToUniversalTime().ToString("o")
        $welcomeManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $welcomeManifestPath -Encoding UTF8
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
start "" "%ROOT%\MOLE_DAS_Wizard.exe"
'@
Set-Content -LiteralPath (Join-Path $OutputRoot "LAUNCH_MOLE_DAS_EXE.bat") -Value $launcher -Encoding ASCII
Set-Content -LiteralPath (Join-Path $installRoot "LAUNCH_MOLE_DAS_EXE.bat") -Value $launcher -Encoding ASCII

$installer = @'
@echo off
setlocal
set "SRC=%~dp0runtime"
set "DEST=%LOCALAPPDATA%\MOLE_DAS"
if not exist "%SRC%\MOLE_code\MOLE_DAS_Wizard.exe" (
  echo Missing runtime payload in %SRC%
  pause
  exit /b 1
)
echo Installing MOLE-DAS executable bundle to:
echo   %DEST%
if exist "%DEST%" rmdir /s /q "%DEST%"
mkdir "%DEST%"
xcopy "%SRC%\*" "%DEST%\" /E /I /Y >nul
echo.
echo Installed.
echo Launching Wizard...
start "" "%DEST%\MOLE_code\MOLE_DAS_Wizard.exe"
'@
Set-Content -LiteralPath (Join-Path $installRoot "INSTALL_MOLE_DAS_EXE_BUNDLE.bat") -Value $installer -Encoding ASCII

$notes = @"
MOLE-DAS Windows Executable Bundle
==================================

Bundle label: $BundleLabel
Repo root: $RepoRoot

Primary launch:
- LAUNCH_MOLE_DAS_EXE.bat
- or runtime\MOLE_code\MOLE_DAS_Wizard.exe

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

$iconPath = Join-Path $installRoot "MOLE_DAS.ico"
Invoke-Native -FilePath $python -ArgumentList @(
    "-c",
    @"
from pathlib import Path
from PIL import Image
candidates = [
    Path(r'''$installRoot''') / 'runtime' / 'MOLE_code' / 'mole_logo_130.png',
    Path(r'''$installRoot''') / 'runtime' / 'MOLE_code' / 'mole_logo.png',
    Path(r'''$installRoot''') / 'runtime' / 'mole_assets' / 'branding' / 'mole_logo_130.png',
    Path(r'''$installRoot''') / 'runtime' / 'mole_assets' / 'branding' / 'mole_logo.png',
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

$shell = New-Object -ComObject WScript.Shell
$launchShortcut = $shell.CreateShortcut((Join-Path $installRoot "Launch MOLE-DAS.lnk"))
$launchShortcut.TargetPath = (Join-Path $installRoot "LAUNCH_MOLE_DAS_EXE.bat")
$launchShortcut.WorkingDirectory = $installRoot
$launchShortcut.IconLocation = $iconPath
$launchShortcut.Save()

$installShortcut = $shell.CreateShortcut((Join-Path $installRoot "Install MOLE-DAS.lnk"))
$installShortcut.TargetPath = (Join-Path $installRoot "INSTALL_MOLE_DAS_EXE_BUNDLE.bat")
$installShortcut.WorkingDirectory = $installRoot
$installShortcut.IconLocation = $iconPath
$installShortcut.Save()

if (Test-Path -LiteralPath $shareZip) {
    Remove-Item -LiteralPath $shareZip -Force
}
Invoke-Native -FilePath $python -ArgumentList @(
    "-c",
    @"
from pathlib import Path
import zipfile
src = Path(r'''$installRoot''')
dst = Path(r'''$shareZip''')
with zipfile.ZipFile(dst, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
    for path in src.rglob('*'):
        if path.is_file():
            zf.write(path, path.relative_to(src))
"@
) -WorkingDirectory $RepoRoot

Write-Host ""
Write-Host "Executable bundle ready:"
Write-Host "  $OutputRoot"
