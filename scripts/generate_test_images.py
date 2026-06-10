"""Generate SYNTHETIC test images + Takeout-style sidecars.

No real photographs are used anywhere in this project's development.
Produces, under the target dir (default tests/fixtures/generated):

  takeout/   8 distinct scenes, JSON sidecars (timestamps + GPS on some)
  icloud/    4 distinct scenes with EXIF DateTime, no sidecars
  variants/  duplicates of takeout/scene_00: exact copy, resize,
             re-encode, brightness shift  (near-dupe targets)
             plus one heavy-crop (should NOT match at default threshold)

Scenes are deterministic (seeded) gradient/shape/noise compositions —
distinct enough that dHash separates them, and recognisable enough
("red circle on yellow") that a vision model can be sanity-checked.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

BASE_TS = 1700000000  # 2023-11-14 UTC, arbitrary fixed epoch for sidecars

SCENES = [
    # (background, shape colour, shape, label)
    ((250, 220, 40), (200, 30, 30), "circle", "red circle on yellow"),
    ((30, 60, 160), (240, 240, 240), "circle", "white circle on blue"),
    ((20, 120, 60), (250, 160, 20), "rect", "orange square on green"),
    ((90, 30, 120), (60, 220, 200), "rect", "teal square on purple"),
    ((230, 230, 230), (20, 20, 20), "tri", "black triangle on white"),
    ((10, 10, 30), (250, 60, 140), "tri", "pink triangle on dark"),
    ((180, 90, 40), (40, 90, 180), "circle", "blue circle on brown"),
    ((140, 200, 230), (30, 130, 50), "rect", "green square on sky"),
    ((60, 60, 60), (220, 200, 60), "tri", "yellow triangle on grey"),
    ((245, 200, 200), (120, 40, 200), "circle", "violet circle on pink"),
    ((40, 160, 150), (250, 250, 250), "tri", "white triangle on teal"),
    ((200, 60, 30), (250, 220, 40), "rect", "yellow square on red"),
]


def make_scene(idx: int, size=(640, 480)) -> Image.Image:
    """Structurally distinct scene: directional gradient background plus
    randomly placed shapes. A centred-shape-on-flat-colour design collapses
    to near-identical dHashes across scenes; gradients + varied layout keep
    inter-scene hamming distances realistic."""
    bg, fg, shape, _ = SCENES[idx]
    rng = random.Random(idx)  # deterministic per scene
    w, h = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    horizontal = idx % 2 == 0
    invert = (idx // 2) % 2 == 0
    span = w if horizontal else h
    for i in range(span):
        t = i / span
        if invert:
            t = 1 - t
        col = tuple(int(c * (0.35 + 0.65 * t)) for c in bg)
        if horizontal:
            d.line([(i, 0), (i, h)], fill=col)
        else:
            d.line([(0, i), (w, i)], fill=col)
    for _ in range(2 + idx % 3):
        sw = rng.randrange(w // 8, w // 3)
        x0 = rng.randrange(0, w - sw)
        y0 = rng.randrange(0, h - sw)
        box = (x0, y0, x0 + sw, y0 + sw)
        if shape == "circle":
            d.ellipse(box, fill=fg)
        elif shape == "rect":
            d.rectangle(box, fill=fg)
        else:
            d.polygon([(x0 + sw // 2, y0), (x0, y0 + sw), (x0 + sw, y0 + sw)], fill=fg)
    # speckle so re-encodes differ at byte level but not perceptually
    for _ in range(300):
        d.point((rng.randrange(w), rng.randrange(h)), fill=(rng.randrange(256),) * 3)
    return img


def write_sidecar(img_path: Path, ts: int, gps: tuple[float, float] | None) -> None:
    data = {
        "title": img_path.name,
        "photoTakenTime": {"timestamp": str(ts)},
        "geoData": {
            "latitude": gps[0] if gps else 0.0,
            "longitude": gps[1] if gps else 0.0,
            "altitude": 0.0,
        },
    }
    img_path.with_name(img_path.name + ".json").write_text(json.dumps(data, indent=2))


def exif_with_datetime(dt: str) -> Image.Exif:
    exif = Image.Exif()
    exif[0x0132] = dt  # IFD0 DateTime
    return exif


def main(out: Path) -> None:
    takeout, icloud, variants = out / "takeout", out / "icloud", out / "variants"
    for d in (takeout, icloud, variants):
        d.mkdir(parents=True, exist_ok=True)

    for i in range(8):
        p = takeout / f"scene_{i:02d}.jpg"
        make_scene(i).save(p, quality=95)
        gps = (51.5 + i * 0.01, -0.12 - i * 0.01) if i % 2 == 0 else None
        write_sidecar(p, BASE_TS + i * 86400, gps)

    for i in range(8, 12):
        p = icloud / f"export_{i:02d}.jpg"
        make_scene(i).save(p, quality=95,
                           exif=exif_with_datetime(f"2024:03:{i - 7:02d} 10:00:00"))

    # variants of scene_00 for dedup tests
    src = takeout / "scene_00.jpg"
    base = Image.open(src)
    (variants / "exact_copy.jpg").write_bytes(src.read_bytes())
    base.resize((320, 240), Image.Resampling.LANCZOS).save(variants / "resized.jpg", quality=95)
    base.save(variants / "reencoded.jpg", quality=55)
    ImageEnhance.Brightness(base).enhance(1.15).save(variants / "brighter.jpg", quality=95)
    w, h = base.size  # heavy crop — should NOT near-match at threshold 8
    base.crop((w // 3, h // 3, w, h)).save(variants / "heavy_crop.jpg", quality=95)

    n = len(list(out.rglob("*.jpg")))
    print(f"generated {n} synthetic images under {out}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        __file__).resolve().parent.parent / "tests" / "fixtures" / "generated"
    main(target)
