#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Draw the tab-strip artwork (STATUS / BEAT FX, KEY / STEMS, SAMPLES / BEAT FX) from scratch.

Zadry's own drawing, reproducible: every pixel comes from this script, the palette below and one open-licence typeface (Inter, SIL Open Font
License 1.1). Nothing is read from, copied from or traced over the player's own artwork, and no commercial typeface is involved. The palette is a
set of plain colours chosen to sit beside the player's dark and light interfaces; it is data, not a reproduction of any image.

Each file is 180 x 50 pixels of little-endian RGB565 (18,000 bytes), the size the core's loader expects for a tab image.

    python build_tabs.py --font Inter.ttf [--font-size 22] [--output-root <mod/modules>] [--preview sheet.png]
"""

from __future__ import annotations

import argparse
import pathlib
import struct

WIDTH, HEIGHT = 180, 50
FRAME = 2          # border thickness
INSET = 2          # selected fill sits this far inside the frame

# (ground, frame, inactive ink, selected fill, selected ink)
THEMES = {
    "dark": ((0, 0, 0), (100, 100, 100), (100, 100, 100), (128, 128, 128), (0, 0, 0)),
    "light": ((222, 219, 222), (82, 81, 82), (82, 81, 82), (41, 40, 41), (222, 219, 222)),
}

# name -> (owner module, cells as ((label, selected), ...)); one cell = the whole strip, two cells = left and right halves
ARTWORK = {
    "status-none-selected": ("core", (("STATUS", False), ("BEAT FX", False))),
    "single-stems-none": ("stems", (("STEMS", False),)),
    "single-stems-selected": ("stems", (("STEMS", True),)),
    "stems-selected": ("stems", (("KEY", False), ("STEMS", True))),
    "samples-selected": ("samples", (("SAMPLES", True), ("BEAT FX", False))),
    "samples-beatfx-selected": ("samples", (("SAMPLES", False), ("BEAT FX", True))),
    "samples-none-selected": ("samples", (("SAMPLES", False), ("BEAT FX", False))),
}


def to_rgb565(image) -> bytes:
    out = bytearray()
    for red, green, blue in image.convert("RGB").getdata():
        out += struct.pack("<H", ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3))
    return bytes(out)


def draw(name: str, theme: str, font):
    from PIL import Image, ImageDraw

    ground, frame, ink, fill, fill_ink = THEMES[theme]
    image = Image.new("RGB", (WIDTH, HEIGHT), ground)
    pen = ImageDraw.Draw(image)
    pen.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), fill=frame)
    pen.rectangle((FRAME, FRAME, WIDTH - 1 - FRAME, HEIGHT - 1 - FRAME), fill=ground)
    cells = ARTWORK[name][1]
    span = (WIDTH - 2 * FRAME) // len(cells)
    for index, (label, selected) in enumerate(cells):
        left = FRAME + index * span
        right = left + span - 1
        if selected:
            pen.rectangle((left + INSET, FRAME + INSET, right - INSET, HEIGHT - 1 - FRAME - INSET), fill=fill)
        box = pen.textbbox((0, 0), label, font=font)
        x = left + (span - (box[2] - box[0])) // 2 - box[0]
        y = (HEIGHT - (box[3] - box[1])) // 2 - box[1]
        pen.text((x, y), label, font=font, fill=fill_ink if selected else ink)
    return image


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--font", required=True, help="path to Inter (SIL OFL 1.1) as TrueType")
    parser.add_argument("--font-size", type=int, default=22)
    parser.add_argument("--output-root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1],
                        help="the modules folder; each file lands in <root>/<module>/assets/")
    parser.add_argument("--preview", type=pathlib.Path, help="also write a contact sheet")
    arguments = parser.parse_args(argv)

    from PIL import Image, ImageFont

    # one size for every tab so the lettering matches from strip to strip: the largest at which the widest label still fits its half of the strip
    half = (WIDTH - 2 * FRAME) // 2 - 2 * (INSET + 3)
    size = arguments.font_size
    while size > 8:
        font = ImageFont.truetype(arguments.font, size)
        widest = max(font.getbbox(label)[2] - font.getbbox(label)[0] for _, cells in ARTWORK.values() for label, _ in cells)
        if widest <= half:
            break
        size -= 1
    print(f"lettering at {size} px (widest label {widest} px of {half})")
    sheet = []
    for name, (module, _) in ARTWORK.items():
        for theme in ("dark", "light"):
            image = draw(name, theme, font)
            suffix = "-light" if theme == "light" else ""
            target = arguments.output_root / module / "assets"
            target.mkdir(parents=True, exist_ok=True)
            (target / f"{name}{suffix}.rgb565").write_bytes(to_rgb565(image))
            sheet.append(image)
            print(f"{module}/assets/{name}{suffix}.rgb565  ({WIDTH}x{HEIGHT})")
    if arguments.preview:
        columns = 2
        rows = (len(sheet) + 1) // 2
        board = Image.new("RGB", (columns * (WIDTH + 8), rows * (HEIGHT + 8)), (60, 60, 60))
        for i, image in enumerate(sheet):
            board.paste(image, ((i % columns) * (WIDTH + 8) + 4, (i // columns) * (HEIGHT + 8) + 4))
        board.resize((board.width * 2, board.height * 2), Image.NEAREST).save(arguments.preview)
        print(f"preview -> {arguments.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
