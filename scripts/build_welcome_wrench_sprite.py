from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw


def _draw_wrench_frame(frame: Image.Image, phase: float) -> Image.Image:
    img = frame.copy().convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Anchor around the mole's right-side paw/shoulder in the shipped idle-watch sprite.
    pivot_x = 80
    pivot_y = 55

    # Arm / glove colors borrowed from the shipped palette.
    fur_dark = (44, 54, 66, 255)
    fur_fill = (71, 83, 95, 255)
    glove_fill = (226, 155, 108, 255)
    glove_shadow = (176, 116, 77, 255)
    wrench_outline = (10, 84, 132, 255)
    wrench_fill = (52, 163, 226, 255)
    wrench_highlight = (161, 230, 255, 255)
    accent = (255, 157, 26, 210)

    angle = math.radians(-55.0 + (36.0 * phase))
    handle_len = 26.0
    head_len = 10.0
    tail_len = 5.0

    hx = pivot_x + math.cos(angle) * handle_len
    hy = pivot_y - math.sin(angle) * handle_len

    tx = pivot_x - math.cos(angle) * tail_len
    ty = pivot_y + math.sin(angle) * tail_len

    def pt(x: float, y: float) -> tuple[int, int]:
        return (int(round(x)), int(round(y)))

    # Forearm
    arm_end_x = pivot_x + math.cos(angle) * 8.0
    arm_end_y = pivot_y - math.sin(angle) * 8.0
    draw.line([pt(pivot_x - 6, pivot_y + 4), pt(arm_end_x, arm_end_y)], fill=fur_dark, width=8)
    draw.line([pt(pivot_x - 6, pivot_y + 4), pt(arm_end_x, arm_end_y)], fill=fur_fill, width=5)

    # Glove / paw
    glove_box = [pivot_x - 5, pivot_y - 4, pivot_x + 8, pivot_y + 8]
    draw.ellipse(glove_box, fill=glove_fill, outline=glove_shadow, width=1)
    draw.ellipse([pivot_x - 1, pivot_y - 6, pivot_x + 6, pivot_y + 1], fill=glove_fill, outline=None)

    # Wrench handle
    draw.line([pt(tx, ty), pt(hx, hy)], fill=wrench_outline, width=7)
    draw.line([pt(tx, ty), pt(hx, hy)], fill=wrench_fill, width=4)
    draw.line([pt(tx, ty), pt(hx, hy)], fill=wrench_highlight, width=1)

    # Wrench open head
    jaw_angle = angle + math.radians(26)
    jaw_angle_2 = angle - math.radians(26)
    hx2 = hx + math.cos(jaw_angle) * head_len
    hy2 = hy - math.sin(jaw_angle) * head_len
    hx3 = hx + math.cos(jaw_angle_2) * head_len
    hy3 = hy - math.sin(jaw_angle_2) * head_len
    head_back_x = hx - math.cos(angle) * 5.0
    head_back_y = hy + math.sin(angle) * 5.0

    draw.line([pt(head_back_x, head_back_y), pt(hx2, hy2)], fill=wrench_outline, width=6)
    draw.line([pt(head_back_x, head_back_y), pt(hx3, hy3)], fill=wrench_outline, width=6)
    draw.line([pt(head_back_x, head_back_y), pt(hx2, hy2)], fill=wrench_fill, width=3)
    draw.line([pt(head_back_x, head_back_y), pt(hx3, hy3)], fill=wrench_fill, width=3)

    # Small jaw notch for readability.
    notch_x = hx + math.cos(angle) * 4.0
    notch_y = hy - math.sin(angle) * 4.0
    draw.line([pt(notch_x, notch_y), pt(hx, hy)], fill=(0, 0, 0, 0), width=3)

    # Motion accent lines on the outer arc.
    if abs(phase) > 0.45:
        lift = 1 if phase > 0 else -1
        arc_x = hx + math.cos(angle) * 9.0
        arc_y = hy - math.sin(angle) * 9.0
        draw.line([pt(arc_x + 1, arc_y - 6 * lift), pt(arc_x + 6, arc_y - 11 * lift)], fill=accent, width=2)
        draw.line([pt(arc_x + 8, arc_y - 4 * lift), pt(arc_x + 12, arc_y - 8 * lift)], fill=(255, 204, 51, 220), width=2)

    return img


def build_sheet(base_sheet: Path, out_dir: Path) -> None:
    src = Image.open(base_sheet).convert("RGBA")
    frame_side = src.height
    frame_count = max(1, src.width // frame_side)
    frames = [src.crop((i * frame_side, 0, (i + 1) * frame_side, frame_side)) for i in range(frame_count)]

    normalized: list[Image.Image] = []
    last_nonblank: Image.Image | None = None
    for frame in frames:
        px = frame.load()
        nonblank = 0
        for y in range(frame.height):
            for x in range(frame.width):
                r, g, b, a = px[x, y]
                if a > 8 and (r + g + b) > 48:
                    nonblank += 1
                    if nonblank > 40:
                        break
            if nonblank > 40:
                break
        if nonblank <= 250 and last_nonblank is not None:
            normalized.append(last_nonblank.copy())
            continue
        normalized.append(frame)
        if nonblank > 250:
            last_nonblank = frame
    frames = normalized

    animated: list[Image.Image] = []
    for idx, frame in enumerate(frames):
        phase = math.sin((idx / float(frame_count)) * math.tau)
        animated.append(_draw_wrench_frame(frame, phase))

    sheet_128 = Image.new("RGBA", (frame_side * len(animated), frame_side), (0, 0, 0, 0))
    for idx, frame in enumerate(animated):
        sheet_128.paste(frame, (idx * frame_side, 0), frame)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_128 = out_dir / "mole_idle_wrench_wave_sheet_128.png"
    out_64 = out_dir / "mole_idle_wrench_wave_sheet_64.png"
    out_192 = out_dir / "mole_idle_wrench_wave_sheet_192.png"

    sheet_128.save(out_128)
    sheet_128.resize((sheet_128.width // 2, sheet_128.height // 2), Image.NEAREST).save(out_64)
    sheet_128.resize((sheet_128.width * 3 // 2, sheet_128.height * 3 // 2), Image.NEAREST).save(out_192)

    print(out_128)
    print(out_64)
    print(out_192)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    build_sheet(
        root / "mole_assets" / "sprites" / "mole_idle_watch_sheet_128.png",
        root / "mole_assets" / "sprites",
    )
