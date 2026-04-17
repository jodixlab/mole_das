# Welcome Animation Prompt Pack

## Purpose

This prompt pack is for producing the final Welcome-screen master reel referenced by:

- `mole_assets/sprites/mole_welcome_master_sheet_512.png`

The resulting asset should replace the branded fallback reel without requiring new UI logic.

## Asset Contract

- final deliverable:
  - `mole_welcome_master_sheet_512.png`
- optional derived deliverables:
  - `mole_welcome_master_sheet_384.png`
  - `mole_welcome_master_sheet_256.png`
  - `mole_welcome_master_sheet_192.png`
- transparent background sheet or card-contained scene with clean edges
- 8 to 16 frames
- 512 x 512 per frame preferred

## Prompt 1: Key Art

Use case: illustration-story  
Asset type: software welcome-screen hero character  
Primary request: original MOLE-DAS mascot illustrated as a confident field crew chief, wearing a clean white hardhat and holding a wrench naturally in-hand, designed for a premium welcome-screen animation  
Scene/backdrop: arcade-inspired framed workshop scene with simple depth cues, dark-friendly composition, minimal clutter  
Subject: one original mole character only, 3/4 facing the viewer, friendly and technically competent expression  
Style/medium: polished digital illustration, crisp raster finish, premium game UI character art, not low-resolution pixel art  
Composition/framing: centered hero subject with safe margins, clear silhouette, readable face, readable wrench, readable hardhat  
Lighting/mood: clean high-contrast studio/game lighting, subtle highlight on helmet and wrench, welcoming but serious  
Color palette: MOLE-DAS blue, orange, white, charcoal, restrained accent glow  
Constraints: original character art; wrench clearly gripped in the hand; no deformation; no logo reuse as the main composition; no chunky arcade pixelation; no meme styling  
Avoid: distorted anatomy, oversized props, crowded scene, exaggerated clouds, novelty humor, muddy edges, flat placeholder look

## Prompt 2: Animation Frames

Use case: stylized-concept  
Asset type: frame sequence for welcome-screen sprite sheet  
Primary request: create a short premium animation loop from the approved MOLE-DAS crew chief key art, with a subtle body bob, a believable wrench wave, and an occasional blink, suitable for a desktop software welcome screen  
Input images: approved key art as the visual source of truth  
Scene/backdrop: preserve the approved hero framing and scene layout  
Subject: same original mole crew chief, same outfit, same hardhat, same wrench, same silhouette  
Style/medium: polished 2D game/UI animation frames, crisp high-resolution raster finish  
Composition/framing: locked framing across frames, no camera drift, no character cropping, safe margins preserved  
Lighting/mood: consistent across all frames  
Constraints: preserve identity exactly; subtle motion only; wrench must stay visibly in hand; loop must be seamless; expression must remain appealing and readable  
Avoid: pose drift, face drift, hand drift, inconsistent helmet shape, inconsistent tool size, jitter, random frame noise

## Prompt 3: Cleanup / Final Sheet

Use case: precise-object-edit  
Asset type: final sprite sheet cleanup  
Primary request: assemble the approved animation frames into a clean 512x512 sprite sheet for software UI use, preserving the exact character design and scene, with transparent or cleanly bounded edges  
Constraints: keep all approved character and scene details unchanged; preserve frame-to-frame consistency; no artifacting; no extra text baked in unless explicitly approved  
Avoid: blur, halo artifacts, dirty alpha edges, uneven frame spacing, color drift

## Review Checklist

- hardhat is readable at first glance
- wrench is clearly in-hand
- face reads cleanly at welcome-screen size
- character looks original, not logo-derived
- loop motion is subtle and believable
- scene reads as polished software art
- no frame-to-frame identity drift
- works on dark UI background
