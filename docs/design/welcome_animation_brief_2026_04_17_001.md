# MOLE-DAS Welcome Animation Brief

## Purpose

Replace the current Welcome-screen mascot loop with a production-quality first-impression animation.

This asset sits on the first screen the operator sees. It cannot read as improvised code art, distorted character geometry, or recycled branding fragments. The final result needs to look intentional, premium, and product-grade.

## Creative Direction

- Character: original MOLE mascot, not a crop of the existing square logo
- Role: crew chief / field technician
- Mood: competent, welcoming, mechanically capable
- Pose: facing user at a slight 3/4 angle
- Action: holding and waving a wrench naturally in-hand
- Visual tone: arcade-inspired, but polished and modern
- Palette: stay within the established MOLE blue / orange / white / dark-charcoal family

## Hard Requirements

- Hardhat clearly visible
- Wrench clearly gripped in the hand
- Face readable at Welcome-screen size
- Silhouette readable on a dark UI background
- No deformation, no uncanny anatomy, no stretched helmet or muzzle
- No direct reuse of the square MOLE logo composition as the scene art
- No heavy pixelation treatment
- No obvious low-resolution scaling artifacts

## Scene Direction

Preferred scene language:

- framed like a polished arcade attract card
- simple environment, not cluttered
- one primary character only
- strong foreground/background separation
- subtle environmental depth, not full illustration overload
- optional support elements:
  - tool-bench edge
  - control console glow
  - workshop bay framing
  - minimal badge/title text

Avoid:

- oversized clouds
- novelty meme framing
- exaggerated cartoon distortion
- busy backgrounds that compete with the mascot
- logo-card composition reused as the full animation scene

## Motion Direction

Primary loop:

- idle body bob
- subtle helmet / shoulder settling
- controlled wrench wave
- optional blink every few cycles

Motion quality requirements:

- smooth and deliberate
- no jittery oscillation
- no random limb drift
- wrench arc should feel physically plausible
- loop should feel seamless over repeated cycles

## Rendering Requirements

- crisp high-resolution raster finish
- target source art at 512 px frame minimum
- anti-aliased edges
- controlled highlights and shadows
- no deliberate scanline overlay unless extremely subtle
- Welcome display should render cleanly around 320 to 380 px on screen

## Deliverable Spec

Preferred:

- 8 to 16 authored frames
- transparent-background sprite sheet
- frame size: 512 x 512 recommended
- naming:
  - `mole_welcome_master_sheet_512.png`
  - optional derived sizes: `384`, `256`, `192`

Fallback acceptable:

- short high-quality APNG or GIF converted into sheet frames for runtime use

## UI Integration Notes

- animation must work on the current dark Welcome panel
- keep safe margins so hat/wrench do not touch the frame edges
- title/subtitle text should remain secondary to the character
- if text is embedded in the art, it must remain minimal and product-appropriate

## Acceptance Standard

Ship only if all are true:

- character looks professionally illustrated
- wrench reads immediately and naturally
- hardhat reads immediately
- face is clean and appealing
- scene feels like product art, not generated placeholder art
- first impression supports production software quality

If any of those fail, the correct action is to hold on the branded fallback reel until the replacement asset is genuinely ready.
