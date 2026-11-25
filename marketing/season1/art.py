"""Shared drawing for the Season 1 launch kit: palette, fonts, the pixel monkey with its stolen heart,
the wordmark, the S1 badge and the pixel canopy background. Pillow only.

The monkey face and the letter grids come from ../logo.py, so the mark stays the one players know.
The heart, the paw and the S1 tab are new here (docs/relaunch/marketing/brand.md, "Logo brief").
"""

import os
import sys
from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import logo  # noqa: E402  (the pixel grids)

FONTS = Path(os.environ.get("MONKEY_FONTS", HERE / "fonts"))
OUT = Path(os.environ.get("MONKEY_KIT_OUT", HERE / "out"))

# --- Facts. Change here, re-run kit.py and teaser.py. -------------------------------------------
JAVA = os.environ.get("MONKEY_JAVA", "monkeysmp.lscaturchio.xyz")
BEDROCK = os.environ.get("MONKEY_BEDROCK", "play.monkeysmp.lscaturchio.xyz")
BEDROCK_PORT = "19132"
HANDLE = os.environ.get("MONKEY_HANDLE", "@playmonkeysmp")
DATE_LONG = "SAT 6 FEB · 5 PM PT"
TAGLINE = "Survive, trade, steal hearts."


# --- Palette (brand.md) ----------------------------------------------------------------------------
def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


SHADE = rgb("#0e3122")
GROUND = rgb("#133f2b")
LEAF1 = rgb("#184e35")
LEAF2 = rgb("#1f6142")
LEAF3 = rgb("#2b7a4b")
BONE = rgb("#f9f8f5")
BONE2 = rgb("#e2dcce")
GOLD = rgb("#e8b23a")
GOLD_HI = rgb("#f3cb6b")
GOLD_SHADE = rgb("#c98f1f")
HEART = rgb("#f05a4f")
HEART_SHADE = rgb("#b83a31")
STONE = rgb("#b6bcad")
INK = rgb("#1a1f23")


# --- Fonts (OFL; see README.md for the download) ---------------------------------------------------
@cache
def display(size):
    """Press Start 2P, scaled so a line sets about as wide as the old Pixelify Sans 700 at `size`.

    Pixelify Sans was dropped because its B reads as a G, its C as an O and its Z as a 2; Jersey 15
    was tried next, but its K reads as an H and its V as a U. Press Start 2P keeps every letter apart.
    """
    return ImageFont.truetype(str(FONTS / "PressStart2P-Regular.ttf"), round(size * 0.6))


@cache
def body(size, bold=True):
    name = "AtkinsonHyperlegible-Bold.ttf" if bold else "AtkinsonHyperlegible-Regular.ttf"
    return ImageFont.truetype(str(FONTS / name), size)


# --- Pixel grids -----------------------------------------------------------------------------------
# The heart the monkey has just stolen, with an ink outline (O) and a glint (W).
HEART_GRID = """
.OOO.OOO.
ORWRORRRO
ORRRRRRHO
ORRRRRRHO
.ORRRRHO.
..ORRHO..
...ORO...
....O....
"""
HEART_COLORS = {"O": INK, "R": HEART, "H": HEART_SHADE, "W": BONE}

# Paw gripping the heart from below (fur tones from logo.py).
PAW_GRID = """
.OOOO.
OBHBHO
OBBBBO
.OOOO.
"""

S1_GLYPHS = {
    "S": [".XXX", "X...", ".XX.", "...X", "XXX."],  # rounded, so it can't read as a 5
    "1": ["XX", ".X", ".X", ".X", ".X"],
}


def _grid(art):
    return logo.rows(art)


def draw_cells(draw, grid, colors, x0, y0, cell):
    for y, line in enumerate(grid):
        for x, c in enumerate(line):
            col = colors.get(c)
            if col is not None:
                draw.rectangle(
                    [x0 + x * cell, y0 + y * cell, x0 + (x + 1) * cell - 1, y0 + (y + 1) * cell - 1], fill=col
                )


FACE_RGB = {k: rgb(v) for k, v in logo.FACE_COLORS.items()}


def mark(cell, heart=True, badge=True, tile=True):
    """The monkey on a green tile, holding a stolen heart, with an S1 tab. Grid is 26 x 22 cells.

    The heart, the paw and the tab sit beside the face, never on it, so no face pixel is covered."""
    W, H = 26, 22
    im = Image.new("RGBA", (W * cell, H * cell), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if tile:  # green tile with two-step corners and an ink edge
        _stepped(d, 0, 2, 18, 19, cell, INK)
        _stepped(d, 1, 3, 16, 17, cell, LEAF2)
        d.rectangle([2 * cell, 4 * cell, 16 * cell - 1, 4 * cell + cell - 1], fill=LEAF3)
    draw_cells(d, _grid(logo.FACE), FACE_RGB, 1 * cell, 3 * cell, cell)
    if heart:
        paw = {"O": FACE_RGB["O"], "B": FACE_RGB["B"], "H": FACE_RGB["H"]}
        draw_cells(d, _grid(PAW_GRID), paw, 18 * cell, 17 * cell, cell)
        draw_cells(d, _grid(HEART_GRID), HEART_COLORS, 17 * cell, 10 * cell, cell)
    if badge:
        s1_badge(d, 16 * cell, 0, max(1, cell * 2 // 3))
    return im


def _stepped(d, x, y, w, h, cell, color):
    """A w x h cell block with corners cut in two steps."""
    c = cell
    d.rectangle([(x + 2) * c, y * c, (x + w - 2) * c - 1, (y + h) * c - 1], fill=color)
    d.rectangle([x * c, (y + 2) * c, (x + w) * c - 1, (y + h - 2) * c - 1], fill=color)
    d.rectangle([(x + 1) * c, (y + 1) * c, (x + w - 1) * c - 1, (y + h - 1) * c - 1], fill=color)


def s1_badge(d, x0, y0, cell, label="S1"):
    """Stone tab, ink outline, ink pixel letters. 11 x 9 of its own cells."""
    d.rectangle([x0, y0, x0 + 11 * cell - 1, y0 + 9 * cell - 1], fill=INK)
    d.rectangle([x0 + cell, y0 + cell, x0 + 10 * cell - 1, y0 + 8 * cell - 1], fill=STONE)
    x = x0 + 2 * cell
    for ch in label:
        glyph = S1_GLYPHS[ch]
        for gy, line in enumerate(glyph):
            for gx, c in enumerate(line):
                if c == "X":
                    d.rectangle(
                        [x + gx * cell, y0 + (gy + 2) * cell, x + (gx + 1) * cell - 1, y0 + (gy + 3) * cell - 1],
                        fill=INK,
                    )
        x += (len(glyph[0]) + 1) * cell


# The brand's redrawn K (relaunch/brand-site, "Logo: redraw K so it doesn't read as H at small sizes"):
# seven wide like M, so its notch stays open at small sizes. Drop this once that branch is merged.
logo.GLYPHS["K"] = """
XX...XX
XX..XX.
XX.XX..
XXXX...
XX.XX..
XX..XX.
XX...XX
"""


def wordmark(text, cell, fill=BONE2, top=BONE, extrude=LEAF1):
    """The pixel wordmark from logo.py: ink outline, one-cell green extrusion, lighter top half."""
    cells, width = logo.text_cells(text)
    cells = {(x + 1, y + 1) for x, y in cells}
    depth = logo.grow(cells, [(0, 1)]) - cells
    shape = cells | depth
    ring = logo.grow(shape, logo.NEIGHBOURS) - shape
    im = Image.new("RGBA", ((width + 2) * cell, 10 * cell), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for group, col in ((ring, INK), (depth, extrude)):
        for x, y in group:
            d.rectangle([x * cell, y * cell, (x + 1) * cell - 1, (y + 1) * cell - 1], fill=col)
    for x, y in cells:
        col = fill if y >= 4 else top
        d.rectangle([x * cell, y * cell, (x + 1) * cell - 1, (y + 1) * cell - 1], fill=col)
    return im


def lockup(cell):
    """MONKEY over SMP (SMP in gold), stacked and centred."""
    a = wordmark("MONKEY", cell)
    b = wordmark("SMP", cell, fill=GOLD_SHADE, top=GOLD, extrude=rgb("#7a5410"))
    w = max(a.width, b.width)
    im = Image.new("RGBA", (w, a.height + b.height - 2 * cell), (0, 0, 0, 0))
    im.alpha_composite(a, ((w - a.width) // 2, 0))
    im.alpha_composite(b, ((w - b.width) // 2, a.height - 2 * cell))
    return im


def wide_lockup(cell):
    """Mark beside MONKEY SMP on one line."""
    m = mark(cell, badge=False)
    words = wordmark("MONKEY", cell)
    smp = wordmark("SMP", cell, fill=GOLD_SHADE, top=GOLD, extrude=rgb("#7a5410"))
    gap = 2 * cell
    w = m.width + gap + words.width + 2 * cell + smp.width
    h = max(m.height, words.height)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    im.alpha_composite(m, (0, (h - m.height) // 2))
    y = (h - words.height) // 2
    im.alpha_composite(words, (m.width + gap, y))
    im.alpha_composite(smp, (m.width + gap + words.width + 2 * cell, y))
    return im


def heart_icon(cell):
    grid = _grid(HEART_GRID)  # sized from the grid, so no edge of the heart is cut off
    im = Image.new("RGBA", (len(grid[0]) * cell, len(grid) * cell), (0, 0, 0, 0))
    draw_cells(ImageDraw.Draw(im), grid, HEART_COLORS, 0, 0, cell)
    return im


def coin_icon(cell):
    grid = """
.OOOO.
OGHGGO
OHGGGO
OGGGSO
OGGSSO
.OOOO.
"""
    im = Image.new("RGBA", (6 * cell, 6 * cell), (0, 0, 0, 0))
    draw_cells(ImageDraw.Draw(im), _grid(grid), {"O": INK, "G": GOLD, "H": GOLD_HI, "S": GOLD_SHADE}, 0, 0, cell)
    return im


# --- Background ------------------------------------------------------------------------------------
def canopy(size, cell=24, seed=7, depth=0.32, floor=True):
    """Stepped green ground with leaf bands hanging from the top (and growing from the bottom).
    Flat colours only, no gradients (DESIGN.md)."""
    import random

    W, H = size
    rnd = random.Random(seed)
    im = Image.new("RGB", size, GROUND)
    d = ImageDraw.Draw(im)
    cols = W // cell + 2
    bands = [(SHADE, 0.0), (LEAF1, 0.35), (LEAF2, 0.6), (LEAF3, 0.82)]
    reach = int(H * depth / cell)
    for color, start in bands:
        # each band hangs a little less far than the last
        base = max(1, int(reach * (1 - start)))
        h = base
        for c in range(cols):
            h = max(1, min(base + 2, h + rnd.choice([-1, 0, 0, 1])))
            if rnd.random() < 0.08:
                h += 2  # a vine
            d.rectangle([c * cell, 0, (c + 1) * cell - 1, h * cell - 1], fill=color)
    if floor:
        fr = max(2, reach // 3)
        for color, start in ((LEAF1, 0.0), (SHADE, 0.5)):
            base = max(1, int(fr * (1 - start)))
            h = base
            for c in range(cols):
                h = max(1, min(base + 1, h + rnd.choice([-1, 0, 1])))
                d.rectangle([c * cell, H - h * cell, (c + 1) * cell - 1, H - 1], fill=color)
    return im


# --- Text ------------------------------------------------------------------------------------------
def outlined(draw, xy, text, font, fill, outline=INK, width=None, anchor="mm", spacing=8):
    """Text with a hard ink outline (no blur, no shadow)."""
    width = width if width is not None else max(2, font.size // 14)
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        anchor=anchor,
        stroke_width=width,
        stroke_fill=outline,
        spacing=spacing,
        align="center",
    )


def plate(draw, box, fill, outline=INK, cut=None):
    """A flat block with an ink edge and corners cut in two steps."""
    x0, y0, x1, y1 = box
    c = max(1, min(cut or max(4, (y1 - y0) // 10), (y1 - y0) // 6, (x1 - x0) // 6))
    for col, inset in ((outline, 0), (fill, c)):
        a, b, e, f = x0 + inset, y0 + inset, x1 - inset, y1 - inset
        cc = c
        draw.rectangle([a + 2 * cc, b, e - 2 * cc, f], fill=col)
        draw.rectangle([a, b + 2 * cc, e, f - 2 * cc], fill=col)
        draw.rectangle([a + cc, b + cc, e - cc, f - cc], fill=col)


def fit(font_fn, text, max_w, start, min_size=10):
    size = start
    while size > min_size:
        f = font_fn(size)
        if f.getbbox(text)[2] - f.getbbox(text)[0] <= max_w:
            return f
        size -= 2
    return font_fn(min_size)
