from __future__ import annotations

from pathlib import Path

from PIL import Image


FRAME_COUNT = 8
FRAME_SIZE = 512


def assemble(input_dir: Path, output_dir: Path) -> None:
    frames: list[Image.Image] = []
    for idx in range(FRAME_COUNT):
        path = input_dir / f"frame_{idx:02d}.png"
        if not path.exists():
            raise FileNotFoundError(f"Missing frame: {path}")
        frame = Image.open(path).convert("RGBA").resize((FRAME_SIZE, FRAME_SIZE), Image.LANCZOS)
        frames.append(frame)

    output_dir.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGBA", (FRAME_SIZE * FRAME_COUNT, FRAME_SIZE), (0, 0, 0, 0))
    for idx, frame in enumerate(frames):
        sheet.paste(frame, (idx * FRAME_SIZE, 0), frame)

    variants = {
        "mole_welcome_master_sheet_512.png": sheet,
        "mole_welcome_master_sheet_384.png": sheet.resize((384 * FRAME_COUNT, 384), Image.LANCZOS),
        "mole_welcome_master_sheet_256.png": sheet.resize((256 * FRAME_COUNT, 256), Image.LANCZOS),
        "mole_welcome_master_sheet_192.png": sheet.resize((192 * FRAME_COUNT, 192), Image.LANCZOS),
    }
    for name, image in variants.items():
        out = output_dir / name
        image.save(out)
        print(out)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    assemble(
        root / "output" / "imagegen" / "welcome_master" / "frames",
        root / "mole_assets" / "sprites",
    )
