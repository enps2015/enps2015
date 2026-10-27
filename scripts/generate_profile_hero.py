#!/usr/bin/env python3
"""Generate an optimized animated profile banner from the canonical SVG."""
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "assets" / "profile-hero.svg"
OUTPUT = ROOT / "assets" / "profile-hero.gif"
WIDTH, HEIGHT = 900, 270

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    png_path = tmp / "hero.png"
    full_gif = tmp / "hero-full.gif"

    # ImageMagick is preinstalled on GitHub-hosted Ubuntu runners.
    subprocess.run(
        ["magick", "-background", "#07111F", "-density", "120",
         str(SVG), "-resize", f"{WIDTH}x{HEIGHT}", str(png_path)],
        check=True,
    )
    base_rgb = Image.open(png_path).convert("RGB")
    # Share one palette so unchanged background pixels are identical in each frame.
    base = base_rgb.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette_data = base.getpalette()
    palette = [tuple(palette_data[i:i+3]) for i in range(0, len(palette_data), 3)]

    def nearest(rgb):
        return min(
            range(len(palette)),
            key=lambda idx: sum((palette[idx][channel] - rgb[channel]) ** 2 for channel in range(3)),
        )

    cyan = nearest((103, 232, 249))
    teal = nearest((45, 212, 191))
    white = nearest((224, 251, 255))

    # Coordinates follow the signal paths in the hero SVG, scaled to 900x270.
    route_a = [(500, 53), (560, 62), (620, 93), (666, 105), (710, 88), (760, 77), (812, 105), (868, 95)]
    route_b = [(513, 176), (570, 166), (630, 158), (688, 177), (746, 188), (802, 176), (851, 160), (885, 169)]
    frames = []
    for frame_index in range(8):
        frame = base.copy()
        draw = ImageDraw.Draw(frame)
        x, y = route_a[frame_index]
        draw.ellipse((x-6, y-6, x+6, y+6), fill=cyan if frame_index % 2 == 0 else teal)
        draw.ellipse((x-2, y-2, x+2, y+2), fill=white)
        x2, y2 = route_b[(frame_index + 3) % len(route_b)]
        draw.ellipse((x2-4, y2-4, x2+4, y2+4), fill=teal if frame_index % 2 == 0 else cyan)
        frames.append(frame)

    frames[0].save(
        full_gif,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=170,
        loop=0,
        optimize=True,
        disposal=1,
    )

    # Optimize frame rectangles; avoids re-encoding the whole banner per frame.
    subprocess.run(
        ["magick", str(full_gif), "-coalesce", "-layers", "Optimize", str(OUTPUT)],
        check=True,
    )

print(f"Generated {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
