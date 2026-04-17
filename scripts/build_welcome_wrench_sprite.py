from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def _draw_wrench(canvas: Image.Image, pivot: tuple[float, float], angle_deg: float) -> None:
    scale = 6
    big = Image.new("RGBA", (canvas.width * scale, canvas.height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)

    px = pivot[0] * scale
    py = pivot[1] * scale
    angle = math.radians(angle_deg)

    handle_len = 78 * scale
    head_len = 24 * scale
    grip_back = 12 * scale

    hx = px + math.cos(angle) * handle_len
    hy = py - math.sin(angle) * handle_len
    tx = px - math.cos(angle) * grip_back
    ty = py + math.sin(angle) * grip_back

    def pt(x: float, y: float) -> tuple[int, int]:
        return (int(round(x)), int(round(y)))

    outline = (14, 58, 91, 255)
    fill = (99, 198, 255, 255)
    fill2 = (61, 156, 224, 255)
    hi = (231, 247, 255, 255)
    glove = (221, 162, 119, 255)
    glove_shadow = (184, 122, 82, 255)
    arc1 = (255, 159, 26, 230)
    arc2 = (255, 204, 51, 210)

    draw.line([pt(tx, ty), pt(hx, hy)], fill=outline, width=30)
    draw.line([pt(tx, ty), pt(hx, hy)], fill=fill2, width=20)
    draw.line([pt(tx, ty), pt(hx, hy)], fill=fill, width=14)
    draw.line([pt(tx, ty), pt(hx, hy)], fill=hi, width=5)

    jaw_angle_1 = angle + math.radians(26)
    jaw_angle_2 = angle - math.radians(26)
    j1x = hx + math.cos(jaw_angle_1) * head_len
    j1y = hy - math.sin(jaw_angle_1) * head_len
    j2x = hx + math.cos(jaw_angle_2) * head_len
    j2y = hy - math.sin(jaw_angle_2) * head_len
    backx = hx - math.cos(angle) * (12 * scale)
    backy = hy + math.sin(angle) * (12 * scale)
    draw.line([pt(backx, backy), pt(j1x, j1y)], fill=outline, width=28)
    draw.line([pt(backx, backy), pt(j2x, j2y)], fill=outline, width=28)
    draw.line([pt(backx, backy), pt(j1x, j1y)], fill=fill2, width=18)
    draw.line([pt(backx, backy), pt(j2x, j2y)], fill=fill2, width=18)
    draw.line([pt(backx, backy), pt(j1x, j1y)], fill=fill, width=10)
    draw.line([pt(backx, backy), pt(j2x, j2y)], fill=fill, width=10)
    draw.ellipse([backx - 10 * scale, backy - 10 * scale, backx + 10 * scale, backy + 10 * scale], fill=fill2, outline=outline, width=5)

    glove_box = [px - 16 * scale, py - 13 * scale, px + 14 * scale, py + 14 * scale]
    glove_outline = (118, 74, 47, 255)
    draw.ellipse(glove_box, fill=glove_shadow, outline=glove_outline, width=4)
    draw.ellipse([glove_box[0] + 6, glove_box[1] + 3, glove_box[2] - 3, glove_box[3] - 4], fill=glove, outline=None)
    for dx, dy in ((-4, -4), (4, 0), (8, 5)):
        cx = px + dx * scale
        cy = py + dy * scale
        draw.ellipse([cx - 6 * scale, cy - 5 * scale, cx + 4 * scale, cy + 5 * scale], fill=glove, outline=glove_outline, width=3)

    if angle_deg < -42 or angle_deg > -16:
        ax = hx + math.cos(angle) * 14 * scale
        ay = hy - math.sin(angle) * 14 * scale
        draw.arc([ax - 18 * scale, ay - 24 * scale, ax + 18 * scale, ay + 24 * scale], start=220, end=300, fill=arc1, width=8)
        draw.arc([ax - 30 * scale, ay - 34 * scale, ax + 30 * scale, ay + 34 * scale], start=225, end=295, fill=arc2, width=6)

    anti = big.resize(canvas.size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.2))
    canvas.alpha_composite(anti)


def build_brand_sheet(logo_path: Path, out_dir: Path) -> None:
    src = Image.open(logo_path).convert("RGBA")
    mascot = src.crop((0, 0, 286, 252))
    mascot = mascot.resize((438, 386), Image.LANCZOS)

    frame_w = 512
    frame_h = 512
    frames: list[Image.Image] = []
    count = 18

    for idx in range(count):
        phase = math.sin((idx / float(count)) * math.tau)
        canvas = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))

        bob_y = int(round(4 * math.sin((idx / float(count)) * math.tau)))
        drift_x = int(round(2 * math.sin((idx / float(count)) * math.tau * 0.5)))

        char = mascot
        if abs(phase) > 0.45:
            rot = -1.2 if phase > 0 else 1.2
            char = mascot.rotate(rot, resample=Image.BICUBIC, expand=False)

        canvas.alpha_composite(char, (34 + drift_x, 56 + bob_y))

        pivot = (380 + drift_x, 282 + bob_y)
        angle = 106 + (28 * ((phase + 1.0) / 2.0))
        _draw_wrench(canvas, pivot, angle)

        frames.append(canvas)

    out_dir.mkdir(parents=True, exist_ok=True)
    base = Image.new("RGBA", (frame_w * count, frame_h), (0, 0, 0, 0))
    for idx, frame in enumerate(frames):
        base.paste(frame, (idx * frame_w, 0), frame)

    out_512 = out_dir / "mole_idle_wrench_wave_brand_sheet_512.png"
    out_384 = out_dir / "mole_idle_wrench_wave_brand_sheet_384.png"
    out_256 = out_dir / "mole_idle_wrench_wave_brand_sheet_256.png"
    out_192 = out_dir / "mole_idle_wrench_wave_brand_sheet_192.png"

    base.save(out_512)
    base.resize((384 * count, 384), Image.LANCZOS).save(out_384)
    base.resize((256 * count, 256), Image.LANCZOS).save(out_256)
    base.resize((192 * count, 192), Image.LANCZOS).save(out_192)

    print(out_512)
    print(out_384)
    print(out_256)
    print(out_192)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    build_brand_sheet(
        root / "mole_assets" / "branding" / "mole_logo.png",
        root / "mole_assets" / "sprites",
    )
