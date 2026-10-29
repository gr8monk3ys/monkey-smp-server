"""Writes the Monkey SMP logo SVGs from the pixel grids below (Python stdlib only).

    python marketing/logo.py          # writes marketing/logo/*.svg

The mark is a 16 x 16 pixel-art monkey, so it lands on whole pixels at 64 (the server-list icon),
128, 256 and 512. The wordmark is a chunky 7-row pixel face with an ink outline and a one-cell green
extrusion, in the spirit of the Minecraft title. Everything is plain <path> geometry: no fonts.
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent / "logo"

# Palette. PEN, PAPER and INK are the site's (site/src/app/style.css); the fur and face tones are the mark's own.
PEN = "#184e35"
PEN_DEEP = "#0f3524"
PAPER = "#f9f8f5"
INK = "#1a1f23"
GOLD = "#e8b23a"
GOLD_SHADE = "#c98f1f"
PAPER_SHADE = "#e2dccf"

FACE_COLORS = {
    "O": "#2e1c10",  # outline, darkest fur
    "B": "#7a4a26",  # fur
    "H": "#9c6334",  # fur highlight
    "S": "#d6aa76",  # face shade, around the eyes
    "T": "#f0cf9f",  # face
    "E": INK,  # eyes
    "W": PAPER,  # eye glint, teeth
}

FACE = """
.....OOOOOO.....
...OOBBBBBBOO...
..OBBHHHBBBBBO..
.OBHHBBBBBBBBBO.
.OBBBBBOOBBBBBO.
OOOBOSSOOSSOBOOO
OSOBSOOSSOOSBOSO
OSOSEEWSSWEESOSO
OSOSEEESSEEESOSO
.OOBSTTTTTTSBOO.
..OBTTOTTOTTBO..
..OBTTTTTTTTBO..
..OBTOWWWWOTBO..
...OBTOOOOTBO...
....OOTTTTOO....
......OOOO......
"""

GLYPHS = {
    "M": """
XX...XX
XXX.XXX
XXXXXXX
XX.X.XX
XX...XX
XX...XX
XX...XX
""",
    "O": """
.XXXX.
XX..XX
XX..XX
XX..XX
XX..XX
XX..XX
.XXXX.
""",
    "N": """
XX..XX
XXX.XX
XXXXXX
XX.XXX
XX..XX
XX..XX
XX..XX
""",
    "K": """
XX..XX
XX.XX.
XXXX..
XXX...
XXXX..
XX.XX.
XX..XX
""",
    "E": """
XXXXXX
XX....
XX....
XXXXX.
XX....
XX....
XXXXXX
""",
    "Y": """
XX..XX
XX..XX
XX..XX
.XXXX.
..XX..
..XX..
..XX..
""",
    "S": """
.XXXXX
XX....
XX....
.XXXX.
....XX
....XX
XXXXX.
""",
    "P": """
XXXXX.
XX..XX
XX..XX
XXXXX.
XX....
XX....
XX....
""",
}


def rows(art):
    lines = art.strip("\n").split("\n")
    assert len({len(line) for line in lines}) == 1, art
    return lines


def path_d(cells, dx=0, dy=0):
    """One path for a set of (x, y) cells: horizontal runs merged into rectangles."""
    by_row = {}
    for x, y in cells:
        by_row.setdefault(y, []).append(x)
    parts = []
    for y in sorted(by_row):
        xs = sorted(by_row[y])
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            parts.append(f"M{start + dx} {y + dy}h{prev - start + 1}v1h-{prev - start + 1}z")
            if x is not None:
                start = prev = x
    return "".join(parts)


def face_paths(dx=0, dy=0):
    grid = rows(FACE)
    out = []
    for key, color in FACE_COLORS.items():
        cells = [(x, y) for y, line in enumerate(grid) for x, c in enumerate(line) if c == key]
        if cells:
            out.append(f'<path fill="{color}" d="{path_d(cells, dx, dy)}"/>')
    return out


def text_cells(text):
    """Cells covered by `text` in the pixel face, one empty column between letters, three for a space."""
    cells, x = set(), 0
    for ch in text:
        if ch == " ":
            x += 3
            continue
        glyph = rows(GLYPHS[ch])
        for y, line in enumerate(glyph):
            for gx, c in enumerate(line):
                if c == "X":
                    cells.add((x + gx, y))
        x += len(glyph[0]) + 1
    return cells, x - 1


def grow(cells, steps):
    out = set(cells)
    for x, y in cells:
        for ox, oy in steps:
            out.add((x + ox, y + oy))
    return out


NEIGHBOURS = [(ox, oy) for ox in (-1, 0, 1) for oy in (-1, 0, 1)]


def wordmark_paths(text, dx=0, dy=0, fill=PAPER_SHADE, top=PAPER, extrude=PEN, outline=INK):
    """Letters at (dx+1, dy+1): an ink outline, a one-cell green extrusion below, the lower half shaded."""
    cells, width = text_cells(text)
    cells = {(x + 1, y + 1) for x, y in cells}
    depth = grow(cells, [(0, 1)]) - cells
    shape = cells | depth
    ring = grow(shape, NEIGHBOURS) - shape
    lower = {(x, y) for x, y in cells if y >= 4}
    paths = [
        f'<path fill="{outline}" d="{path_d(ring, dx, dy)}"/>',
        f'<path fill="{extrude}" d="{path_d(depth, dx, dy)}"/>',
        f'<path fill="{top}" d="{path_d(cells - lower, dx, dy)}"/>',
        f'<path fill="{fill}" d="{path_d(lower, dx, dy)}"/>',
    ]
    # 1 outline + 7 rows + 1 extrusion + 1 outline
    return paths, width + 2, 10


def svg(width, height, body, title):
    inner = "\n  ".join(body)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width * 16}" height="{height * 16}" shape-rendering="crispEdges">\n'
        f"  <title>{title}</title>\n  {inner}\n</svg>\n"
    )


def main():
    OUT.mkdir(exist_ok=True)
    tile = f'<rect width="16" height="16" rx="2" fill="{PEN}"/>'
    files = {
        # The mark on its green tile: favicon, server-list icon, avatars.
        "mark.svg": svg(16, 16, [tile, *face_paths()], "Monkey SMP"),
        # The bare face, for placing over photos or other backgrounds.
        "face.svg": svg(16, 16, face_paths(), "Monkey SMP"),
    }

    # The one-line wordmark: "MONKEY" in paper, "SMP" in gold.
    def wordmark(dx, dy):
        monkey, mw, _ = wordmark_paths("MONKEY", dx=dx, dy=dy)
        smp, sw, _ = wordmark_paths("SMP", dx=dx + mw + 1, dy=dy, fill=GOLD_SHADE, top=GOLD)
        return monkey + smp, mw + 1 + sw

    words, ww = wordmark(0, 0)
    files["wordmark.svg"] = svg(ww, 10, words, "Monkey SMP")
    # Horizontal lockup: tile, then the wordmark centred on it.
    words, ww = wordmark(19, 3)
    files["logo.svg"] = svg(19 + ww, 16, [tile, *face_paths(), *words], "Monkey SMP")
    # Stacked: tile above two lines, for square spaces.
    _, tw, _ = wordmark_paths("MONKEY")
    _, bw, _ = wordmark_paths("SMP")
    w = max(tw, bw, 16)
    stacked = [
        f'<rect x="{(w - 16) // 2}" width="16" height="16" rx="2" fill="{PEN}"/>',
        *face_paths(dx=(w - 16) // 2),
        *wordmark_paths("MONKEY", dx=(w - tw) // 2, dy=18)[0],
        *wordmark_paths("SMP", dx=(w - bw) // 2, dy=28, fill=GOLD_SHADE, top=GOLD)[0],
    ]
    files["logo-stacked.svg"] = svg(w, 38, stacked, "Monkey SMP")
    for name, text in files.items():
        (OUT / name).write_text(text, encoding="utf-8", newline="\n")
        print("wrote", OUT / name)


if __name__ == "__main__":
    main()
