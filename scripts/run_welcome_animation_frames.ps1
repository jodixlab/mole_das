param(
    [string]$SourceImage = "output/imagegen/welcome_master/welcome_master_keyart_v3.png",
    [string]$FramesDir = "output/imagegen/welcome_master/frames",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$skillRoot = "C:\Users\User\.codex\skills\.system\imagegen"
$imageGenCli = Join-Path $skillRoot "scripts\image_gen.py"
$venvPython = Join-Path $repoRoot "MOLE_code\.venv\Scripts\python.exe"
$sourcePath = Join-Path $repoRoot $SourceImage
$framesPath = Join-Path $repoRoot $FramesDir

if (-not (Test-Path $imageGenCli)) { throw "Image generation CLI not found: $imageGenCli" }
if (-not (Test-Path $venvPython)) { throw "Project python not found: $venvPython" }
if (-not (Test-Path $sourcePath)) { throw "Source key art not found: $sourcePath" }
if (-not $DryRun -and -not $env:OPENAI_API_KEY) { throw "OPENAI_API_KEY is not set." }

New-Item -ItemType Directory -Force -Path $framesPath | Out-Null

$basePrompt = @"
Create one frame for a premium Welcome-screen animation loop using the provided approved key art as the identity source of truth.
Keep the exact same mole character, same hardhat, same workshop frame, same clothing, same lighting, same facial identity, and same art style.
Only make a subtle animation change for this frame.
The wrench must stay clearly in the hand.
The frame must remain tightly consistent with the source art and suitable for sprite-sheet assembly.
No camera change, no scene redesign, no added props, no text, no layout shift, no extra characters, no species drift.
"@

$framePrompts = @(
    "Neutral start frame. Slight relaxed body bob. Wrench raised near shoulder. Eyes open.",
    "Very small upward body lift. Wrench hand rises slightly and tilts outward a few degrees. Eyes open.",
    "Peak wave frame. Wrench hand slightly higher with a clean outward tilt. Friendly confident expression. Eyes open.",
    "Settle from the wave. Wrench hand returning slightly toward the neutral position. Eyes open.",
    "Mid-loop blink frame. Same pose as neutral with only a subtle blink and tiny body bob.",
    "Small lift again, mirrored subtly from earlier motion. Wrench tilts outward slightly. Eyes open.",
    "Second peak wave frame. Wrench highest in the loop but still subtle and believable. Eyes open.",
    "Return-to-neutral frame. Body and wrench settle cleanly back to the starting pose. Eyes open."
)

for ($i = 0; $i -lt $framePrompts.Count; $i++) {
    $frameName = ("frame_{0:D2}.png" -f $i)
    $outPath = Join-Path $framesPath $frameName
    $prompt = $basePrompt + "`nAnimation instruction: " + $framePrompts[$i]
    $args = @(
        $imageGenCli,
        "edit",
        "--image", $sourcePath,
        "--prompt", $prompt,
        "--model", "gpt-image-1.5",
        "--size", "1024x1024",
        "--quality", "high",
        "--input-fidelity", "high",
        "--out", $outPath,
        "--force",
        "--no-augment"
    )
    if ($DryRun) { $args += "--dry-run" }
    Write-Host ("Generating " + $frameName + " ...")
    & $venvPython @args
}

if (-not $DryRun) {
    Write-Host "Assembling master sheet ..."
    & $venvPython (Join-Path $repoRoot "scripts\assemble_welcome_master_sheet.py")
}
