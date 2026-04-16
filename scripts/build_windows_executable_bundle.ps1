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

Write-Host ""
Write-Host "Executable bundle ready:"
Write-Host "  $OutputRoot"
