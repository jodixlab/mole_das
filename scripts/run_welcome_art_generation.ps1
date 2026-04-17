param(
    [string]$OutputDir = "output/imagegen/welcome_master",
    [string]$OutputName = "welcome_master_keyart_v3.png",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$skillRoot = "C:\Users\User\.codex\skills\.system\imagegen"
$imageGenCli = Join-Path $skillRoot "scripts\image_gen.py"
$venvPython = Join-Path $repoRoot "MOLE_code\.venv\Scripts\python.exe"

if (-not (Test-Path $imageGenCli)) {
    throw "Image generation CLI not found: $imageGenCli"
}
if (-not (Test-Path $venvPython)) {
    throw "Project python not found: $venvPython"
}
if (-not $DryRun -and -not $env:OPENAI_API_KEY) {
    throw "OPENAI_API_KEY is not set. Re-run after exporting the key, or use -DryRun."
}

New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot $OutputDir) | Out-Null

$prompt = @"
Use case: illustration-story
Asset type: software welcome-screen hero animation key art
Primary request: original MOLE-DAS mascot illustrated as a confident field crew chief, very clearly reading as a mole, wearing a clean white hardhat and holding a wrench in a raised hand prepared for a subtle wave animation, designed for a premium welcome-screen animation
Scene/backdrop: arcade-inspired framed workshop scene with simple depth cues, dark-friendly composition, minimal clutter
Subject: one original mole character only, 3/4 facing the viewer, friendly and technically competent expression, distinct mole muzzle and nose, compact head shape, species identity must read immediately as mole rather than otter or badger
Style/medium: polished digital illustration, crisp raster finish, premium game UI character art, not low-resolution pixel art
Composition/framing: centered hero subject with safe margins, clear silhouette, readable face, readable wrench, readable hardhat, lifted tool arm with strong negative space around the wrench hand for later animation, slightly more zoomed out than a poster closeup, arm and wrench must not merge into the torso
Lighting/mood: clean high-contrast studio/game lighting, subtle highlight on helmet and wrench, welcoming but serious
Color palette: MOLE-DAS blue, orange, white, charcoal, restrained accent glow
Constraints: original character art; wrench clearly gripped in the hand; no deformation; no logo reuse as the main composition; no chunky arcade pixelation; no meme styling
Avoid: distorted anatomy, oversized props, crowded scene, exaggerated clouds, novelty humor, muddy edges, flat placeholder look, otter face, badger face, raccoon mask read, generic animal mascot look, cramped arm pose, wrench crossing the face, hand cropped near frame edge
"@

$outPath = Join-Path $repoRoot "$OutputDir\$OutputName"

$args = @(
    $imageGenCli,
    "generate",
    "--prompt", $prompt,
    "--model", "gpt-image-1.5",
    "--size", "1024x1024",
    "--quality", "high",
    "--out", $outPath,
    "--no-augment"
)

if ($DryRun) {
    $args += "--dry-run"
}

Write-Host "Running image generation CLI..."
& $venvPython @args
