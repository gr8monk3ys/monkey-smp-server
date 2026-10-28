"""Builds the wardrobe: cosmetic skins for swords and helmets, earned by playing or by supporting.

    python tools/datapacks.py          regenerate it with every other generated pack (--check: only compare)

It writes two folders, both generated (edit this file, not them):
  package/realms/datapacks/realms-wardrobe/       the server side: /trigger wardrobe, unlock scores, the skins
  client/overrides/resourcepacks/Monkey SMP Wardrobe/ the client side: models and pixel art

A skin only changes how an item looks (`item_model`, and `equippable.asset_id` for helmets). Damage,
durability, armor and enchantments stay exactly as they were, so nothing here is pay-to-win (Mojang's
usage guidelines: paid perks must be cosmetic). See docs/RETENTION.md for the unlock ladder and why.

Unlock scores (all per player name, so the store and staff can set them while the player is offline):
  rw.days     days played (one per real day the player logs in; never resets, so no streak anxiety)
  rw.hours    hours played (from the play_time statistic, plus rw.playbase: play carried from earlier worlds)
  rw.months   months of access pass bought in total
  rw.invites  friends invited who bought a pass
  rw.tier     supporter tier: 1 Ember, 2 Banner, 3 Crown (0 when it lapses)
  rw.founder  1 for everyone who played during the first season
  rw.events   events attended (the realms-events pack counts it, once per event)
  rw.<holiday>  1 for coming to that holiday's event (staff set it at the event; never sold)
  rw.challenges  weekly challenges done, in all seasons together (tools/challenges.py; never sold)
  rw.launch   1 for being online FOUNDER_MINUTES in Season I's launch weekend (never sold); rw.launchtime
              counts their seconds online while that window is open (`function realms:wardrobe/founder/...`)
`function realms:wardrobe/day` starts a new day; deploy/realms-day.timer runs it at midnight UTC.
The weekly challenges (tools/challenges.py) go in the same data pack, and have a page of the menu:
`/trigger challenges`, or page MENU_CHALLENGES of `/trigger wardrobe`.
Every rw.* score lives in the world's scoreboard, so a new season's world starts without them:
tools/season.py carries them over (docs/SEASONS.md, "Ending a season").
"""
import json
import math
import struct
import zlib
from pathlib import Path

import challenges
from challenges import FOUNDER_MINUTES, LAUNCH_SECONDS
from datapacks import NS, function_tag, mcmeta, text
from repo import Repo

RESOURCE_FORMAT = 97
DATAPACK = "realms-wardrobe"
RESOURCEPACK = "Monkey SMP Wardrobe"

# What each unlock score means, for the menu and the "locked" message: objective -> (singular, plural).
SCORES = {
    "rw.days": ("day played", "days played"),
    "rw.hours": ("hour played", "hours played"),
    "rw.months": ("pass month", "pass months"),
    "rw.invites": ("friend invited", "friends invited"),
    "rw.events": ("event attended", "events attended"),
    "rw.challenges": ("weekly challenge", "weekly challenges"),
}
TIERS = {1: "Ember", 2: "Banner", 3: "Crown"}
# Holiday overlays (docs/SEASONS.md): objective -> (name, when). A skin is earned by coming to the event.
HOLIDAYS = {
    "rw.hallowtide": ("Hallowtide", "late October"),
    "rw.midwinter": ("Midwinter", "late December"),
    "rw.midsummer": ("Midsummer", "late June"),
}
# Scores that can jump while a player is online (the store, staff, an event): crossing a skin's threshold
# says so in chat. Days say so in new_day; hours and tiers don't.
NOTIFY = ["rw.months", "rw.events", *HOLIDAYS, "rw.challenges", "rw.launch"]
# The scores the Tebex store sets (docs/RETENTION.md). Event, holiday, challenge and launch skins must never
# use them.
SOLD = {"rw.months", "rw.tier"}

# ---------------------------------------------------------------- the skins

# Blade palettes: o outline, L light edge, M blade, D dark edge, R rune, G/g guard, H/h grip, P pommel.
BLADES = [
    dict(id="wayfarer", name="Wayfarer", unlock=("rw.days", 3),
         pal="o1f2329 Le6eef2 Ma9b6bf D6f7c86 G8a6b45 g5e4630 H6b4a2e h4a321f Pa9b6bf"),
    dict(id="emberfang", name="Emberfang", unlock=("rw.hours", 10), teeth=True, runes=(7, 9, 11),
         pal="o2a0d06 Lffd27a Me2621f D8f2a10 Rfff1a8 G3b2a26 g241816 H3b2a26 h241816 Pe2621f"),
    dict(id="frostbite", name="Frostbite", unlock=("rw.days", 15), broad=True,
         pal="o10263a Lf4fdff Ma8e4f5 D5aa9cf Gd8f3fb g7fc3e0 H2f5d80 h1d3d57 Pa8e4f5"),
    dict(id="verdant", name="Verdant", unlock=("rw.invites", 1),
         pal="o13240f Lc9f29b M6cbf3a D3a7d22 Ge7c14a ga8842a H5a3d22 h3d2914 Pe7c14a"),
    dict(id="starfall", name="Starfall", unlock=("rw.days", 30), broad=True, runes=(6, 9, 12),
         pal="o070a1c L5866b8 M2b3478 D171d4d Rffe98a Gc9ced8 g8a90a0 H20253f h13172a Pffe98a"),
    dict(id="rallier", name="Rallier", unlock=("rw.events", 3), broad=True, runes=(8, 12),
         pal="o2a0b0d Lfaf6ee Me2ddd2 Db0262f Rb0262f Ge7c14a ga8842a H8a1c22 h5a1016 Pe7c14a"),
    dict(id="founders_edge", name="Founder's Edge", unlock=("rw.founder", 1), runes=(8, 10, 12),
         pal="o1b1430 Lf3e9ff Mb9a3e8 D7b62c0 Rffffff Ge7c14a ga8842a H3a2b5c h251b3d Pff6fb1"),
    dict(id="gravelight", name="Gravelight", unlock=("rw.hallowtide", 1), teeth=True, runes=(7, 10, 13),
         pal="o0c0810 Lff9a2e M3b2a45 D20162a R9dff8a Gff9a2e gb85e12 H2a1f33 h19121f P9dff8a"),
    dict(id="solstice", name="Solstice", unlock=("rw.midsummer", 1), broad=True, runes=(8, 11),
         pal="o2a2205 Lfffbe0 Mf6d743 Dc79a14 Rff7a1a G3f9a4a g24652c H3f9a4a h24652c Pff7a1a"),
    # The tenure ladder: one step a month for the first three, so a new buyer has something by renewal day.
    dict(id="oath_i", name="Oathblade I", unlock=("rw.months", 1),
         pal="o15171c L9aa3ad M5d6670 D3b424c G9c6b3a g6b4826 H2c4a7a h1c3054 P9c6b3a"),
    dict(id="oath_ii", name="Oathblade II", unlock=("rw.months", 2), runes=(8, 11),
         pal="o141a24 Le9eef5 Mb3bccb D6e7a8c R5ab0ff G9aa4b4 g5f6878 H2c4a7a h1c3054 P5ab0ff"),
    dict(id="oath_iii", name="Oathblade III", unlock=("rw.months", 3), broad=True, runes=(7, 9, 11, 13),
         pal="o1d1a10 Lfffdf2 Me3e6ee D9aa3b5 R4aa8ff Ge7c14a ga8842a H2c4a7a h1c3054 Pe7c14a"),
    dict(id="old_guard", name="Old Guard", unlock=("rw.months", 6), broad=True,
         pal="o2a1a0c Lf0c58a Mb8803f D7a4f22 G5c5c64 g3c3c44 H3d2a1a h2a1c10 Pb8803f"),
    dict(id="lantern", name="Lantern", unlock=("rw.tier", 1), runes=(7, 11),
         pal="o2b1505 Lffe0a3 Mf0a23b Db5651a Rfff4c2 G4a3a2a g2e2219 H4a3a2a h2e2219 Pffcf5a"),
    dict(id="standard", name="Standard", unlock=("rw.tier", 2),
         pal="o0b1636 L9fb9ff M3d63d6 D22388a Ge7c14a ga8842a H7a1c1c h521212 Pe7c14a"),
    dict(id="regalia", name="Regalia", unlock=("rw.tier", 3), broad=True,
         pal="o3a2605 Lfff3b0 Mf1c232 Db88a12 Gfafafa gb8b8c8 H5a1a6e h3c1049 Pe0115f"),
    # The weekly challenge ladder (tools/challenges.py): one week, three weeks and six weeks of all three.
    dict(id="trailblazer", name="Trailblazer", unlock=("rw.challenges", 3), runes=(7, 10, 13),
         pal="o0b2226 Lc9fbf2 M4fc9b8 D23887a Rfff1a8 Gc0612a g7d3b17 H6b4a2e h4a321f Pfff1a8"),
    dict(id="pinnacle", name="Pinnacle", unlock=("rw.challenges", 18), broad=True, runes=(7, 10, 13),
         pal="o1d0b26 Lffe3f6 Mf0a6d8 Dae4f9c Rfff7c2 Gfff7c2 gd1b05a H3b1d4f h26112f Pfff7c2"),
]

# Helm icons are drawn as text; '.' is clear, and an outline is added around everything else.
HELMS = [
    dict(id="laurel", name="Laurel", unlock=("rw.days", 7), sound="leather",
         pal="o14260f G7fc24a g3f7d24 rd23a3a"),
    dict(id="horned", name="Horned Helm", unlock=("rw.invites", 3), sound="iron",
         pal="o1a1a1e Ma7adb5 Ld9dee3 D5f656d d2c3036 Wefe6cf wb9ab8a",
         icon=["................",
               ".W............W.",
               ".W............W.",
               ".WW..........WW.",
               "..wW.MMMMMM.Ww..",
               "...wMLLMMMMDw...",
               "....MLMMMMMD....",
               "....MMMMMMMD....",
               "....MMddddMD....",
               "....MDdMMdMD....",
               "....MDdMMdMD....",
               "....DD.DD.DD....",
               "................",
               "................",
               "................",
               "................"]),
    dict(id="plumed", name="Plumed Helm", unlock=("rw.events", 10), sound="iron",
         pal="o1a1a1e Ma7adb5 Ld9dee3 D5f656d d2c3036 Rd8262f r8f1820",
         icon=["................",
               "....R..RR..R....",
               "....RR.RR.RR....",
               ".....RRrrRR.....",
               "......RrrR......",
               ".....MMLLMM.....",
               "....MLLMMMMD....",
               "....MLMMMMMD....",
               "....MMMMMMMD....",
               "....MMddddMD....",
               "....MDdMMdMD....",
               "....MDdMMdMD....",
               "....DD.DD.DD....",
               "................",
               "................",
               "................"]),
    dict(id="midwinter_cap", name="Midwinter Cap", unlock=("rw.midwinter", 1), sound="leather",
         pal="o3a0a0e Kc8102e k8a0b1f Wf4f4f4 wc9d1d9",
         icon=["................",
               "................",
               ".......WW.......",
               "......WWwW......",
               ".......Ww.......",
               ".....KKKKKK.....",
               "....KKKKKKKk....",
               "...KKKKKKKKkk...",
               "...KWKKWKKWkk...",
               "..KKKKKKKKKKkk..",
               "..WWWWWWWWWWWW..",
               "..wWwWwWwWwWww..",
               "................",
               "................",
               "................",
               "................"]),
    dict(id="wanderers_hood", name="Wanderer's Hood", unlock=("rw.months", 12), sound="leather",
         pal="o1c1a14 C4b5d3a c33422a x0e0d0a Tc9a75a",
         icon=["................",
               "................",
               "......CCC.......",
               ".....CCCCC......",
               "....CCCCCCC.....",
               "...CCCcccCCC....",
               "...CCcxxxcCC....",
               "..CCCcxxxcCCC...",
               "..CCCcxxxcCCC...",
               "..CCCCcxcCCCC...",
               ".CCCCCCcCCCCCC..",
               ".TTTTTTTTTTTTT..",
               "................",
               "................",
               "................",
               "................"]),
    dict(id="crown", name="Crown", unlock=("rw.tier", 3), sound="gold",
         pal="o3a2605 Yf6d04d yb88a12 Re0115f B2a6fe0",
         icon=["................",
               "................",
               "................",
               "................",
               "..Y....YY....Y..",
               "..YY..YRRY..YY..",
               "..YYYYYYYYYYYY..",
               "..YRYYYBBYYYRY..",
               "..YYYYYYYYYYYY..",
               "..yyyyyyyyyyyy..",
               "................",
               "................",
               "................",
               "................",
               "................",
               "................"]),
    dict(id="vanguard", name="Vanguard Helm", unlock=("rw.challenges", 9), sound="iron",
         pal="o1a1a1e Ma7adb5 Ld9dee3 D5f656d d2c3036 Ge7c14a Wf4f4f4 wc9d1d9",
         icon=["................",
               "................",
               ".W............W.",
               ".WW..........WW.",
               ".wWW.MMMMMM.WWw.",
               "..wWMLLMMMMDWw..",
               "...wMLMMMMMDw...",
               "....GGGGGGGG....",
               "....MMddddMD....",
               "....MDdMMdMD....",
               "....MDdMMdMD....",
               "....DD.DD.DD....",
               "................",
               "................",
               "................",
               "................"]),
    # Season I's launch weekend only, in the colors of Founder's Edge (tools/challenges.py has the dates).
    dict(id="founders_circlet", name="Founder's Circlet", unlock=("rw.launch", 1), sound="gold",
         pal="o1b1430 Se3e6ee s9aa3b5 Vb9a3e8 v7b62c0 Pff6fb1",
         icon=["................",
               "................",
               "................",
               "................",
               ".....ssssss.....",
               "...ss......ss...",
               "..s....VV....s..",
               "..S...VPPV...S..",
               "..SS..vVVv..SS..",
               "...SSSSvvSSSS...",
               ".....SSSSSS.....",
               "................",
               "................",
               "................",
               "................",
               "................"]),
]

# Vanilla items a skin can go on, and what each looks like without one (used by "reset").
SWORDS = ["wooden", "stone", "copper", "iron", "golden", "diamond", "netherite"]
HELMETS = {  # item -> (equipment asset, equip sound)
    "leather_helmet": ("leather", "leather"), "chainmail_helmet": ("chainmail", "chain"),
    "copper_helmet": ("copper", "copper"), "iron_helmet": ("iron", "iron"),
    "golden_helmet": ("gold", "gold"), "diamond_helmet": ("diamond", "diamond"),
    "netherite_helmet": ("netherite", "netherite"), "turtle_helmet": ("turtle_scute", "turtle"),
}

FIRST_BLADE, FIRST_HELM = 101, 201  # trigger values: 1 menu, 2 reset blade, 3 reset helm, 4 and 5 other pages
MENU_SUPPORT = 4
MENU_CHALLENGES = 5
MENUS = (1, MENU_SUPPORT, MENU_CHALLENGES)


def palette(spec: str) -> dict[str, tuple[int, int, int, int]]:
    out = {}
    for part in spec.split():
        key, hexcode = part[0], part[1:]
        out[key] = (int(hexcode[0:2], 16), int(hexcode[2:4], 16), int(hexcode[4:6], 16), 255)
    return out


# ---------------------------------------------------------------- pixel art


def outlined(grid: list[list[str | None]]) -> list[list[str | None]]:
    """Adds an 'o' outline on every clear pixel that touches a filled one (4-neighbour)."""
    h, w = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    for y in range(h):
        for x in range(w):
            if grid[y][x] is None and any(
                    0 <= y + dy < h and 0 <= x + dx < w and grid[y + dy][x + dx] is not None
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                out[y][x] = "o"
    return out


def blade_pixels(skin: dict) -> list[list[str | None]]:
    """A sword on the diagonal like vanilla's: grip bottom left, tip top right. t runs along the blade."""
    g: list[list[str | None]] = [[None] * 16 for _ in range(16)]

    def put(x, y, c):
        if 0 <= x < 16 and 0 <= y < 16:
            g[y][x] = c
    runes = set(skin.get("runes", ()))
    for t in range(5, 15):
        put(t, 15 - t, "R" if t in runes else "M")
        if t <= 13:
            put(t, 14 - t, "L")
        if t <= 13 and (skin.get("broad") or (skin.get("teeth") and t % 2 == 0)):
            put(t + 1, 15 - t, "D")
    for x, y, c in ((4, 11, "G"), (3, 10, "G"), (5, 12, "G"), (2, 9, "g"), (6, 13, "g"),
                    (3, 12, "H"), (2, 13, "h"), (1, 14, "P")):
        put(x, y, c)
    return outlined(g)


def icon_pixels(skin: dict) -> list[list[str | None]]:
    if "icon" in skin:
        rows = skin["icon"]
        assert len(rows) == 16 and all(len(r) == 16 for r in rows), skin["id"]
        return outlined([[None if c == "." else c for c in r] for r in rows])
    # The laurel: a ring of leaves, open at the bottom, with a few berries.
    g: list[list[str | None]] = [[None] * 16 for _ in range(16)]
    for y in range(16):
        for x in range(16):
            d = math.hypot(x - 7.5, y - 7.5)
            if 4.2 <= d <= 6.6 and not (y > 10 and abs(x - 7.5) < 3):
                angle = math.atan2(y - 7.5, x - 7.5)
                g[y][x] = "r" if (x, y) in ((3, 4), (12, 4), (2, 9), (13, 9)) else ("G" if int(angle * 4) % 2 else "g")
    return outlined(g)


def equipment_pixels(skin: dict) -> list[list[str | None]]:
    """The 64x32 humanoid layer. Only the head is drawn: the head cube at (0,0) and the hat cube at (32,0).

    Each cube's sides are one 32x8 strip starting 8 rows down (right, front, left, back faces, 8 wide each);
    its top face is the 8x8 square at (u+8, v).
    """
    g: list[list[str | None]] = [[None] * 64 for _ in range(32)]

    def side(u, row, col, c):  # row 0 is the top of the head; col 0..31 runs right, front, left, back
        g[8 + row][u + col] = c

    def top(u, x, y, c):
        g[y][u + 8 + x] = c

    def shade(x, y, light, dark):  # a steady, hand-placed-looking dither instead of flat fill
        return dark if ((x * 73856093) ^ (y * 19349663)) % 7 < 2 else light

    kind = skin["id"]
    if kind == "crown":
        for col in range(32):
            f = col % 8
            side(32, 3, col, "y")
            side(32, 2, col, "B" if f in (3, 4) and col // 8 != 1 else "R" if f in (3, 4) else "Y")
            if f in (0, 3, 4, 7):
                side(32, 1, col, "Y")
            if f in (3, 4):
                side(32, 0, col, "Y")
    elif kind == "laurel":
        for col in range(32):
            side(32, 2, col, "r" if col % 8 == 5 else shade(col, 2, "G", "g"))
            if col % 2 == 0:
                side(32, 1, col, "G")
            else:
                side(32, 3, col, "g")
    elif kind == "horned":
        for x in range(8):
            for y in range(8):
                top(0, x, y, shade(x, y, "M", "D") if 0 < x < 7 and 0 < y < 7 else "D")
        for col in range(32):
            for row in range(3):
                side(0, row, col, "L" if row == 0 else shade(col, row, "M", "D"))
            side(0, 3, col, "W" if col % 4 == 1 else "d")
        for row in range(4, 7):  # nose guard down the middle of the front face
            side(0, row, 11, "M")
            side(0, row, 12, "D")
        for face in (0, 16):  # horns curl up the right and left faces of the hat layer
            for col, row in ((1, 3), (2, 2), (3, 2), (4, 1), (5, 1), (5, 0), (6, 0)):
                side(32, row, face + (col if face == 16 else 7 - col), "W")
            side(32, 3, face + (2 if face == 16 else 5), "w")
    elif kind == "plumed":
        for x in range(8):
            for y in range(8):
                top(0, x, y, shade(x, y, "M", "D") if 0 < x < 7 and 0 < y < 7 else "D")
                if x in (3, 4):  # the crest runs front to back over the top of the hat layer
                    top(32, x, y, "R" if x == 3 else "r")
        for col in range(32):
            for row in range(3):
                side(0, row, col, "L" if row == 0 else shade(col, row, "M", "D"))
            side(0, 3, col, "L" if col % 4 == 1 else "d")
        for row in range(4, 7):
            side(0, row, 11, "M")
            side(0, row, 12, "D")
        side(32, 0, 11, "R")  # the crest's front edge, then its tail down the back
        side(32, 0, 12, "r")
        for row in range(4):
            side(32, row, 27, "R")
            side(32, row, 28, "r")
    elif kind == "midwinter_cap":
        for x in range(8):
            for y in range(8):
                top(0, x, y, shade(x, y, "K", "k"))
        for x, y in ((3, 3), (4, 3), (3, 4), (4, 4)):  # the pompom
            top(32, x, y, "W")
        for x, y in ((2, 3), (5, 4), (3, 2), (4, 5)):
            top(32, x, y, "w")
        for col in range(32):
            for row in range(3):
                side(0, row, col, "W" if row == 1 and col % 4 == 2 else shade(col, row, "K", "k"))
            side(0, 3, col, "W")
            side(32, 3, col, "W" if col % 2 else "w")  # the brim, turned up on the outer layer
    elif kind == "vanguard":
        for x in range(8):
            for y in range(8):
                top(0, x, y, shade(x, y, "M", "D") if 0 < x < 7 and 0 < y < 7 else "D")
        for col in range(32):
            for row in range(3):
                side(0, row, col, "L" if row == 0 else shade(col, row, "M", "D"))
            side(0, 3, col, "G")  # a gold band where the helmet meets the face
        for row in range(4, 7):
            side(0, row, 11, "M")
            side(0, row, 12, "D")
        for face in (0, 16):  # wings swept back and up the right and left faces of the hat layer
            for col, row, c in ((1, 3, "w"), (2, 2, "W"), (2, 3, "w"), (3, 1, "W"), (3, 2, "W"), (4, 0, "W"),
                                (4, 1, "W"), (4, 2, "w"), (5, 0, "W"), (5, 1, "w"), (6, 0, "w")):
                side(32, row, face + (col if face == 16 else 7 - col), c)
    elif kind == "founders_circlet":
        for col in range(32):  # a thin silver band on the hat layer, shaded underneath
            side(32, 2, col, "S")
            side(32, 3, col, "s")
        for col, row, c in ((11, 0, "V"), (12, 0, "V"), (11, 1, "P"), (12, 1, "V"), (10, 2, "V"), (11, 2, "v"),
                            (12, 2, "v"), (13, 2, "V")):  # the gem, at the front
            side(32, row, col, c)
    elif kind == "wanderers_hood":
        for x in range(8):
            for y in range(8):
                top(0, x, y, shade(x, y, "C", "c"))
        for col in range(32):
            for row in range(8):
                face_opening = 9 <= col <= 14 and row >= 2
                if not face_opening:
                    side(0, row, col, "T" if row == 7 else shade(col, row, "C", "c"))
    else:
        raise SystemExit(f"no equipment art for helm {kind!r}")
    return g


def png(grid: list[list[str | None]], pal: dict) -> bytes:
    h, w = len(grid), len(grid[0])
    raw = b"".join(b"\x00" + b"".join(bytes(pal[c]) if c else b"\x00\x00\x00\x00" for c in row) for row in grid)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def scaled(grid, factor):
    return [[c for c in row for _ in range(factor)] for row in grid for _ in range(factor)]


# ---------------------------------------------------------------- the data pack


def condition(unlock) -> str:
    objective, n = unlock
    return f"score @s {objective} matches {n}.."


def how_to_unlock(unlock) -> str:
    objective, n = unlock
    if objective == "rw.tier":
        return f"Supporters at {TIERS[n]} or above"
    if objective == "rw.founder":
        return "Played during the first season"
    if objective == "rw.launch":
        return "Played on Season I's launch weekend"
    if objective in HOLIDAYS:
        name, when = HOLIDAYS[objective]
        return f"From the {name} event ({when})"
    return earned_for(unlock)


def earned_for(unlock) -> str:
    """What the player did, for "Unlocked X for ..." in chat."""
    objective, n = unlock
    if objective in HOLIDAYS:
        return f"coming to {HOLIDAYS[objective][0]}"
    if objective == "rw.launch":
        return "playing on launch weekend"
    one, many = SCORES[objective]
    return f"{n} {one if n == 1 else many}"


# Skins on the challenges page: the challenge ladder and the founders' keepsakes.
KEEPSAKES = {"rw.challenges", "rw.launch", "rw.founder"}


def page(unlock) -> int:
    """The menu page a skin is on: 1 for skins earned in game, MENU_SUPPORT for the pass and supporter tiers,
    MENU_CHALLENGES for the challenge ladder and the founders' skins."""
    return MENU_SUPPORT if unlock[0] in SOLD else MENU_CHALLENGES if unlock[0] in KEEPSAKES else 1


def skins():
    for i, s in enumerate(BLADES):
        yield FIRST_BLADE + i, "blade", s
    for i, s in enumerate(HELMS):
        yield FIRST_HELM + i, "helm", s


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    fn = f"data/{NS}/function/wardrobe"
    f["pack.mcmeta"] = mcmeta("Monkey SMP wardrobe: cosmetic skins, no stats (generated by tools/wardrobe.py)")
    f["data/minecraft/tags/function/load.json"] = function_tag(f"{NS}:wardrobe/load")
    f["data/minecraft/tags/function/tick.json"] = function_tag(f"{NS}:wardrobe/tick")
    f[f"data/{NS}/tags/item/wardrobe_blades.json"] = json.dumps(
        {"values": [f"minecraft:{m}_sword" for m in SWORDS]}, indent=2)
    f[f"data/{NS}/tags/item/wardrobe_helms.json"] = json.dumps(
        {"values": [f"minecraft:{h}" for h in HELMETS]}, indent=2)

    objectives = ["wardrobe trigger", "rw.play minecraft.custom:minecraft.play_time", "rw.hours dummy",
                  "rw.days dummy", "rw.lastday dummy", "rw.months dummy", "rw.invites dummy", "rw.tier dummy",
                  "rw.founder dummy", "rw.day dummy", "rw.const dummy", "rw.events dummy", "rw.playbase dummy",
                  "rw.challenges dummy", "rw.launch dummy", "rw.launchtime dummy",
                  *(f"{o} dummy" for o in HOLIDAYS), *(f"{o}.seen dummy" for o in NOTIFY)]
    f[f"{fn}/load.mcfunction"] = "\n".join([
        "# Generated by tools/wardrobe.py. Scores are created once and kept across restarts.",
        *(f"scoreboard objectives add {o}" for o in objectives),
        "scoreboard players set #hour rw.const 72000",
        "scoreboard players set #second rw.const 20",
        "scoreboard players add #today rw.day 0",
        "# The first season runs until staff set #season to 2; everyone who plays in it is a founder.",
        "execute unless score #season rw.day matches -2147483648.. run scoreboard players set #season rw.day 1",
        f"function {NS}:challenges/load",
        f"schedule function {NS}:wardrobe/second 20t replace",
    ]) + "\n"
    f[f"{fn}/tick.mcfunction"] = (f"execute as @a[scores={{wardrobe=1..}}] run function {NS}:wardrobe/use\n"
                                  f"execute as @a[scores={{challenges=1..}}] run function {NS}:challenges/use\n")
    f[f"{fn}/second.mcfunction"] = "\n".join([
        "# Once a second: let everyone use the trigger, count days and hours, mark founders, keep the launch",
        "# weekend's window and the weekly challenges going, announce unlocks.",
        "scoreboard players enable @a wardrobe",
        *(f"scoreboard players add @a {o} 0" for o in (
            "rw.days", "rw.months", "rw.invites", "rw.tier", "rw.founder", "rw.events", *HOLIDAYS, "rw.playbase",
            "rw.challenges", "rw.launch")),
        "execute as @a run scoreboard players operation @s rw.hours = @s rw.play",
        "execute as @a run scoreboard players operation @s rw.hours += @s rw.playbase",
        "scoreboard players operation @a rw.hours /= #hour rw.const",
        "execute if score #season rw.day matches 1 run scoreboard players set @a rw.founder 1",
        f"execute as @a unless score @s rw.lastday = #today rw.day run function {NS}:wardrobe/new_day",
        f"function {NS}:wardrobe/founder/second",
        f"function {NS}:challenges/second",
        *(f"execute as @a unless score @s {o}.seen = @s {o} run function {NS}:wardrobe/notice/{o[3:]}"
          for o in NOTIFY),
        f"schedule function {NS}:wardrobe/second 20t replace",
    ]) + "\n"

    def unlocked(s) -> str:
        command = "/trigger wardrobe" if page(s["unlock"]) == 1 else f"/trigger wardrobe set {page(s['unlock'])}"
        return "tellraw @s " + text(
            {"text": "Unlocked ", "color": "gold"}, {"text": s["name"], "color": "yellow"},
            {"text": f" for {earned_for(s['unlock'])}. ", "color": "gold"},
            {"text": "[Open the wardrobe]", "color": "aqua", "underlined": True,
             "click_event": {"action": "run_command", "command": command}})
    f[f"{fn}/day.mcfunction"] = (
        "# A new real day (deploy/realms-day.timer runs this at midnight UTC). Players online get it within a second.\n"
        "scoreboard players add #today rw.day 1\n")
    lines = ["# This player's first login of the day.", "scoreboard players add @s rw.days 1",
             "scoreboard players operation @s rw.lastday = #today rw.day"]
    for _, _kind, s in skins():
        objective, n = s["unlock"]
        if objective == "rw.days":
            lines.append(f"execute if score @s rw.days matches {n} run " + unlocked(s))
    f[f"{fn}/new_day.mcfunction"] = "\n".join(lines) + "\n"
    for objective in NOTIFY:
        lines = [f"# {objective} moved (the store, staff or an event set it): say which skins it just unlocked."]
        for _, _kind, s in skins():
            o, n = s["unlock"]
            if o == objective:
                lines.append(f"execute if score @s {o} matches {n}.. unless score @s {o}.seen matches {n}.. run "
                             + unlocked(s))
        lines.append(f"scoreboard players operation @s {objective}.seen = @s {objective}")
        f[f"{fn}/notice/{objective[3:]}.mcfunction"] = "\n".join(lines) + "\n"

    use = ["# Runs as a player who just used /trigger wardrobe.",
           f"execute if score @s wardrobe matches 1 run function {NS}:wardrobe/menu",
           f"execute if score @s wardrobe matches 2 run function {NS}:wardrobe/reset_blade",
           f"execute if score @s wardrobe matches 3 run function {NS}:wardrobe/reset_helm",
           f"execute if score @s wardrobe matches {MENU_SUPPORT} run function {NS}:wardrobe/menu_support",
           f"execute if score @s wardrobe matches {MENU_CHALLENGES} run function {NS}:wardrobe/menu_challenges"]
    use += [f"execute if score @s wardrobe matches {value} run function {NS}:wardrobe/skin/{s['id']}"
            for value, _, s in skins()]
    use += ["scoreboard players set @s wardrobe 0", "scoreboard players enable @s wardrobe"]
    f[f"{fn}/use.mcfunction"] = "\n".join(use) + "\n"

    # Three pages, so each fits the 20 lines of open chat: skins earned in game, the pass and supporter skins,
    # and this week's challenges with the challenge and founders' skins. Each page links to the other two.
    labels = {1: "[Earned in game]", MENU_SUPPORT: "[Pass & supporter]", MENU_CHALLENGES: "[Challenges]"}
    pages = [(1, "menu", "skins earned in game", ("Wardrobe", "looks only, never stats"),
              ["rw.days", "rw.hours", "rw.invites", "rw.events"]),
             (MENU_SUPPORT, "menu_support", "pass and supporter skins", ("Wardrobe", "looks only, never stats"),
              ["rw.months"]),
             (MENU_CHALLENGES, "menu_challenges", "this week's challenges and their skins",
              ("Weekly challenges", "new every Monday, 12 AM Pacific"), ["rw.challenges"])]
    counted = {"rw.days": "days", "rw.hours": "hours", "rw.invites": "friends invited", "rw.events": "events",
               "rw.months": "pass months", "rw.challenges": "challenges done in all seasons"}
    for number, name, about, (title, subtitle), counts in pages:
        line: list = [{"text": "", "color": "gray"}]
        for i, o in enumerate(counts):
            line += [{"score": {"name": "@s", "objective": o}, "color": "white"},
                     f" {counted[o]}" + (", " if i < len(counts) - 1 else "")]
        menu = [f"# The wardrobe menu, {about}: owned skins are green and clickable, locked ones say how to get them.",
                "tellraw @s " + text("", {"text": f"\n{title}", "color": "gold", "bold": True},
                                     {"text": f"  {subtitle}", "color": "gray"}),
                "tellraw @s " + text(*line)]
        if number == MENU_CHALLENGES:
            menu.append(f"function {NS}:challenges/lines")
        last = None
        for value, kind, s in skins():
            if page(s["unlock"]) != number:
                continue
            if kind != last:
                heading = "Blades (hold the sword)" if kind == "blade" else "Helms (wear the helmet)"
                menu.append("tellraw @s " + text({"text": heading, "color": "gold"}))
                last = kind
            how = how_to_unlock(s["unlock"])
            target = "the sword in your hand" if kind == "blade" else "the helmet you're wearing"
            menu.append(f"execute if {condition(s['unlock'])} run tellraw @s " + text(
                " ", {"text": f"[{s['name']}]", "color": "green",
                      "click_event": {"action": "run_command", "command": f"/trigger wardrobe set {value}"},
                      "hover_event": {"action": "show_text", "value": f"Put {s['name']} on {target}"}},
                {"text": f"  {how}", "color": "dark_gray"}))
            menu.append(f"execute unless {condition(s['unlock'])} run tellraw @s " + text(
                " ", {"text": s["name"], "color": "gray",
                      "hover_event": {"action": "show_text", "value": f"Locked: {how}"}},
                {"text": f"  {how}", "color": "dark_gray"}))
        menu.append("tellraw @s " + text(
            " ", {"text": "[Reset blade]", "color": "aqua",
                  "click_event": {"action": "run_command", "command": "/trigger wardrobe set 2"}},
            "  ", {"text": "[Reset helm]", "color": "aqua",
                   "click_event": {"action": "run_command", "command": "/trigger wardrobe set 3"}}))
        links: list = []
        for other in MENUS:
            if other != number:
                links += ["  " if links else " ", {"text": labels[other], "color": "aqua",
                                                   "click_event": {"action": "run_command",
                                                                   "command": f"/trigger wardrobe set {other}"}}]
        menu.append("tellraw @s " + text(*links))
        f[f"{fn}/{name}.mcfunction"] = "\n".join(menu) + "\n"

    f.update(founder_files())
    f.update(challenges.datapack_files())

    def refuse(msg):
        return "return run tellraw @s " + text({"text": msg, "color": "red"})

    for _value, kind, s in skins():
        slot, tag, what = (("weapon.mainhand", "wardrobe_blades", "Hold an ordinary sword in your main hand first.")
                           if kind == "blade" else
                           ("armor.head", "wardrobe_helms", "Wear an ordinary helmet first."))
        f[f"{fn}/skin/{s['id']}.mcfunction"] = "\n".join([
            f"execute unless {condition(s['unlock'])} run "
            + refuse(f"{s['name']} is locked: {how_to_unlock(s['unlock'])}."),
            f"execute unless items entity @s {slot} #{NS}:{tag} run " + refuse(what),
            f"item modify entity @s {slot} {NS}:wardrobe/{s['id']}",
            "playsound minecraft:item.armor.equip_chain player @s ~ ~ ~ 1 1.4",
            "tellraw @s " + text({"text": f"{s['name']} on. ", "color": "green"},
                                 {"text": "It changes the look only.", "color": "gray"}),
        ]) + "\n"
        components: dict[str, object] = {"minecraft:item_model": f"{NS}:{s['id']}"}
        if kind == "helm":
            components["minecraft:equippable"] = {"slot": "head", "asset_id": f"{NS}:{s['id']}",
                                                  "equip_sound": f"minecraft:item.armor.equip_{s['sound']}"}
        f[f"data/{NS}/item_modifier/wardrobe/{s['id']}.json"] = json.dumps(
            {"type": "minecraft:set_components", "components": components}, indent=2)

    reset_blade = ["# Puts the item's own look back."]
    for m in SWORDS:
        item = f"{m}_sword"
        reset_blade.append(f"execute if items entity @s weapon.mainhand minecraft:{item} run item modify entity @s "
                           f"weapon.mainhand {NS}:wardrobe/reset/{item}")
        f[f"data/{NS}/item_modifier/wardrobe/reset/{item}.json"] = json.dumps(
            {"type": "minecraft:set_components", "components": {"minecraft:item_model": f"minecraft:{item}"}},
            indent=2)
    f[f"{fn}/reset_blade.mcfunction"] = "\n".join(reset_blade) + "\n"
    reset_helm = ["# Puts the helmet's own look back."]
    for item, (asset, sound) in HELMETS.items():
        reset_helm.append(f"execute if items entity @s armor.head minecraft:{item} run item modify entity @s "
                          f"armor.head {NS}:wardrobe/reset/{item}")
        f[f"data/{NS}/item_modifier/wardrobe/reset/{item}.json"] = json.dumps(
            {"type": "minecraft:set_components", "components": {
                "minecraft:item_model": f"minecraft:{item}",
                "minecraft:equippable": {"slot": "head", "asset_id": f"minecraft:{asset}",
                                         "equip_sound": f"minecraft:item.armor.equip_{sound}"}}}, indent=2)
    f[f"{fn}/reset_helm.mcfunction"] = "\n".join(reset_helm) + "\n"
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


def founder_files() -> dict[str, str]:
    """The launch weekend's window for Founder's Circlet (docs/RETENTION.md, "The launch weekend").

    While it is open, everyone online counts seconds in rw.launchtime; FOUNDER_MINUTES of them set rw.launch.
    It shuts when game time passes #founder.until. Game time stops while the server is empty, so
    deploy/realms-week.sh sends `founder/sync` every hour with the seconds left on the wall clock (from
    tools/challenges.py), and the window ends at the end of Sunday, Pacific, even after a quiet night. State is in
    rw.day: #founder.open, #founder.auto (1 while the clock may move the end) and #founder.until.
    """
    fn = f"data/{NS}/function/wardrobe/founder"
    ticks = LAUNCH_SECONDS * 20
    season_one = ("execute unless score #season rw.day matches 1 run return run tellraw @s "
                  + text({"text": "Founder's Circlet is only for Season I's launch weekend.", "color": "red"}))
    gold = "gold"
    return {
        f"{fn}/open.mcfunction": "\n".join([
            "# Opens the launch weekend: realms:rules/launch runs this (staff can too, if the launch didn't). Season I",
            f"# only. It lasts {LAUNCH_SECONDS // 3600} hours of game time; deploy/realms-week.sh moves the end to "
            "the end of Sunday,",
            "# Pacific, on the wall clock.",
            season_one,
            "scoreboard players set #founder.open rw.day 1",
            "scoreboard players set #founder.auto rw.day 1",
            "execute store result score #founder.until rw.day run time query gametime",
            f"scoreboard players add #founder.until rw.day {ticks}",
            "tellraw @a " + text({"text": "Launch weekend: ", "color": gold},
                                 {"text": f"play {FOUNDER_MINUTES} minutes before the end of Sunday (Pacific) to keep "
                                          "Founder's Circlet, a helm skin, for good.", "color": "yellow"}),
        ]) + "\n",
        f"{fn}/open_for.mcfunction": "\n".join([
            "# Macro {hours:N}, staff only: opens the window (or keeps it open) for N hours of game time from now.",
            "# The wall clock no longer moves its end; founder/close shuts it early. Season I only.",
            season_one,
            "$scoreboard players set #founder.until rw.day $(hours)",
            "scoreboard players operation #founder.until rw.day *= #hour rw.const",
            "execute store result score #founder.now rw.day run time query gametime",
            "scoreboard players operation #founder.until rw.day += #founder.now rw.day",
            "scoreboard players set #founder.open rw.day 1",
            "scoreboard players set #founder.auto rw.day 0",
            "$tellraw @a " + text({"text": "Launch weekend: ", "color": gold},
                                  {"text": f"Founder's Circlet is open for $(hours) more hours. Play {FOUNDER_MINUTES} "
                                           "minutes to keep it.", "color": "yellow"}),
        ]) + "\n",
        f"{fn}/close.mcfunction": "\n".join([
            "# Shuts the window: by itself when the time is up, from founder/sync at the end of Sunday, or staff.",
            "scoreboard players set #founder.open rw.day 0",
            "scoreboard players set #founder.auto rw.day 0",
            "tellraw @a " + text({"text": "The launch weekend is over. ", "color": gold},
                                 {"text": "Founder's Circlet stays with everyone who earned it.", "color": "yellow"}),
        ]) + "\n",
        f"{fn}/sync.mcfunction": "\n".join([
            "# Macro {seconds:N}, from deploy/realms-week.sh every hour: N seconds of the launch weekend are left on",
            "# the wall clock. An open window the launch opened ends then (0 shuts it now); otherwise nothing.",
            "execute unless score #founder.auto rw.day matches 1 run return 0",
            "$scoreboard players set #founder.left rw.day $(seconds)",
            f"execute if score #founder.left rw.day matches ..0 run return run function {NS}:wardrobe/founder/close",
            "scoreboard players operation #founder.left rw.day *= #second rw.const",
            "execute store result score #founder.until rw.day run time query gametime",
            "scoreboard players operation #founder.until rw.day += #founder.left rw.day",
        ]) + "\n",
        f"{fn}/second.mcfunction": "\n".join([
            "# Once a second, from the wardrobe's: while the window is open, count everyone online.",
            "execute unless score #founder.open rw.day matches 1 run return 0",
            "execute store result score #founder.now rw.day run time query gametime",
            "execute if score #founder.now rw.day >= #founder.until rw.day run return run "
            f"function {NS}:wardrobe/founder/close",
            "scoreboard players add @a rw.launchtime 1",
            "tellraw @a[scores={rw.launchtime=1}] " + text(
                {"text": "Launch weekend: ", "color": gold},
                {"text": f"stay {FOUNDER_MINUTES} minutes in all to keep Founder's Circlet, a helm skin.",
                 "color": "yellow"}),
            f"scoreboard players set @a[scores={{rw.launchtime={FOUNDER_MINUTES * 60}..}}] rw.launch 1",
        ]) + "\n",
    }


# ---------------------------------------------------------------- the resource pack


def resourcepack_files() -> dict[str, bytes]:
    f: dict[str, bytes] = {}

    def js(obj) -> bytes:
        return (json.dumps(obj, indent=2) + "\n").encode()
    f["pack.mcmeta"] = js({"pack": {"description": "Monkey SMP wardrobe skins",
                                    "min_format": RESOURCE_FORMAT, "max_format": RESOURCE_FORMAT}})
    for _, kind, s in skins():
        sid, pal = s["id"], palette(s["pal"])
        f[f"assets/{NS}/items/{sid}.json"] = js({"model": {"type": "minecraft:model", "model": f"{NS}:item/{sid}"}})
        parent = "minecraft:item/handheld" if kind == "blade" else "minecraft:item/generated"
        f[f"assets/{NS}/models/item/{sid}.json"] = js({"parent": parent, "textures": {"layer0": f"{NS}:item/{sid}"}})
        art = blade_pixels(s) if kind == "blade" else icon_pixels(s)
        f[f"assets/{NS}/textures/item/{sid}.png"] = png(art, pal)
        if kind == "helm":
            f[f"assets/{NS}/equipment/{sid}.json"] = js({"layers": {"humanoid": [{"texture": f"{NS}:{sid}"}]}})
            f[f"assets/{NS}/textures/entity/equipment/humanoid/{sid}.png"] = png(equipment_pixels(s), pal)
    crown = next(s for s in HELMS if s["id"] == "crown")
    f["pack.png"] = png(scaled(icon_pixels(crown), 4), palette(crown["pal"]))
    return f


# ---------------------------------------------------------------- writing


OPTION = f'"file/{RESOURCEPACK}"'


def enable_in_options(options: Path) -> None:
    """Turns the wardrobe resource pack on in a client options.txt (last, so it sits on top)."""
    lines = options.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("resourcePacks:[") and OPTION not in line:
            lines[i] = line[:-1] + ("," if line != "resourcePacks:[]" else "") + OPTION + "]"
            break
    else:
        if not any(line.startswith("resourcePacks:") for line in lines):
            lines.append(f'resourcePacks:["vanilla",{OPTION}]')
    raw = options.read_bytes()
    eol = b"\r\n" if b"\r\n" in raw else b"\n"
    options.write_bytes(eol.join(line.encode("utf-8") for line in lines) + eol)


def packs(repo: Repo) -> dict[Path, dict[str, str | bytes]]:
    return {repo.realms / "datapacks" / DATAPACK: datapack_files(),
            repo.client / "overrides" / "resourcepacks" / RESOURCEPACK: resourcepack_files()}


def after_write(repo: Repo) -> None:
    options = repo.client / "overrides" / "options.txt"
    if options.is_file():
        enable_in_options(options)
