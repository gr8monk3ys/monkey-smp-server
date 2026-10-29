"""Renders the Monkey SMP logo PNGs and banners from marketing/logo/*.svg and the in-game screenshots.

    python marketing/logo.py     # only after changing the pixel grids
    python marketing/build.py    # needs Inkscape on PATH, Pillow, and the fonts in FONTS (see README.md)

Small outputs land in the repo (marketing/logo/png, marketing/server-icon.png, site/public/img/og.jpg); every
output, big banners included, is also written to OUT.
"""

import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = Path(os.environ.get("MONKEY_MARKETING", r"D:\DevData\monkey-smp-marketing"))
OUT = DATA / "out"
FONTS = DATA / "fonts"
SHOTS = Path(os.environ.get("MONKEY_SHOTS", r"D:\DevData\realms-photos\shots"))
CACHE = DATA / "cache"

INK = (26, 31, 35)
PAPER = (249, 248, 245)
PEN = (24, 78, 53)
PEN_LIGHT = (66, 169, 121)
GOLD = (232, 178, 58)
MUTED = (200, 204, 210)

ADDRESS = "monkeysmp.lscaturchio.xyz"
TAGLINE = "Claim land. Make allies. Keep what you can hold."
HOOKS = "Factions of four  ·  Strength SMP  ·  Modded terrain and dungeons"


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def display(size):
    return font("Fraunces-Bold.ttf", size)


def body(size, bold=False):
    return font("InstrumentSans-SemiBold.ttf" if bold else "InstrumentSans-Regular.ttf", size)


def mono(size):
    return font("IBMPlexMono-Medium.ttf", size)


def svg_png(name, cell):
    """The logo SVG rasterised at `cell` pixels per pixel-art cell (crisp: every edge on a whole pixel)."""
    src = HERE / "logo" / f"{name}.svg"
    cells_w = int(src.read_text(encoding="utf-8").split('viewBox="0 0 ')[1].split()[0])
    dst = CACHE / f"{name}@{cell}.png"
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["inkscape", str(src), "--export-type=png", f"--export-filename={dst}", f"--export-width={cells_w * cell}"],
            check=True,
            capture_output=True,
        )
    return Image.open(dst).convert("RGBA")


def shot(name, size, focus=(0.5, 0.5)):
    """A screenshot scaled to cover `size`, cropped around `focus` (fractions of the image)."""
    im = Image.open(SHOTS / f"{name}.png").convert("RGB")
    w, h = size
    scale = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.Resampling.LANCZOS)
    x = min(max(round(im.width * focus[0] - w / 2), 0), im.width - w)
    y = min(max(round(im.height * focus[1] - h / 2), 0), im.height - h)
    return im.crop((x, y, x + w, y + h)).convert("RGBA")


def shade(im, side="left", strength=0.85, reach=0.75, base=0.15):
    """Darken toward one side (or "center": an even wash plus a vignette) so type reads on any shot."""
    w, h = im.size
    if side == "center":
        x = np.linspace(-1, 1, w)[None, :]
        y = np.linspace(-1, 1, h)[:, None]
        a = base + (strength - base) * np.clip(np.hypot(x, y) - 0.35, 0, None) ** 1.5
    else:
        t = np.linspace(0, 1, h if side == "bottom" else w)
        if side in ("right", "bottom"):
            t = t[::-1]
        ramp = base + (strength - base) * np.clip(1 - t / reach, 0, None) ** 1.6
        a = ramp[:, None].repeat(w, 1) if side == "bottom" else ramp[None, :].repeat(h, 0)
    mask = Image.fromarray(np.uint8(np.clip(a, 0, 1) * 255), "L")
    return Image.composite(Image.new("RGBA", (w, h), INK + (255,)), im, mask)


def text(draw, xy, s, f, fill, anchor="la", shadow=True):
    if shadow:
        x, y = xy
        off = max(2, f.size // 18)
        draw.text((x + off, y + off), s, font=f, fill=INK + (200,), anchor=anchor)
    draw.text(xy, s, font=f, fill=fill, anchor=anchor)


def paste(base, im, xy):
    base.alpha_composite(im, (round(xy[0]), round(xy[1])))


def pill(draw, box, label, f, fg=INK, bg=GOLD):
    x0, y0, x1, y1 = (round(v) for v in box)
    draw.rounded_rectangle((x0, y0, x1, y1), radius=(y1 - y0) // 2 - 1, fill=bg)
    draw.text(((x0 + x1) / 2, (y0 + y1) / 2), label, font=f, fill=fg, anchor="mm")


def soft_glow(im, radius):
    """A dark halo behind an RGBA layer, so the logo separates from a busy shot."""
    a = im.getchannel("A").filter(ImageFilter.GaussianBlur(radius))
    glow = Image.new("RGBA", im.size, INK + (0,))
    glow.putalpha(a.point(lambda v: round(v * 0.7)))
    return glow


def with_glow(im, radius):
    pad = radius * 3
    canvas = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    canvas.alpha_composite(im, (pad, pad))
    out = soft_glow(canvas, radius)
    out.alpha_composite(canvas)
    return out, pad


# --- outputs -------------------------------------------------------------------------------------------------


def logo_pngs():
    dst = HERE / "logo" / "png"
    dst.mkdir(exist_ok=True)
    made = []
    for size in (512, 256, 128, 64):
        im = svg_png("mark", size // 16)
        im.save(dst / f"mark-{size}.png", optimize=True)
        made.append(dst / f"mark-{size}.png")
    for cell in (8, 16):
        im = svg_png("logo", cell)
        im.save(dst / f"logo-{im.width}w.png", optimize=True)
        made.append(dst / f"logo-{im.width}w.png")
    im = svg_png("logo-stacked", 16)
    im.save(dst / f"logo-stacked-{im.width}w.png", optimize=True)
    made.append(dst / f"logo-stacked-{im.width}w.png")
    # Minecraft wants exactly 64 x 64, PNG, no transparency needed.
    icon = svg_png("mark", 4)
    icon.save(HERE / "server-icon.png", optimize=True)
    made.append(HERE / "server-icon.png")
    return made


def centered_card(size, shot_name, focus, cell, tag_size, sub_size, extra=None):
    """Logo, tagline and address centred on a darkened shot (invite splash, Discord banner)."""
    w, h = size
    im = shade(shot(shot_name, size, focus), side="center", strength=0.9, base=0.35)
    d = ImageDraw.Draw(im)
    logo, pad = with_glow(svg_png("logo-stacked", cell), cell * 2)
    block_h = logo.height - pad * 2 + tag_size * 1.6 + sub_size * 2.4
    top = (h - block_h) / 2
    paste(im, logo, ((w - logo.width) / 2, top - pad))
    y = top + logo.height - pad * 2 + tag_size * 0.9
    text(d, (w / 2, y), TAGLINE, display(tag_size), PAPER, anchor="mt")
    y += tag_size * 1.5
    text(d, (w / 2, y), ADDRESS, mono(sub_size), GOLD, anchor="mt")
    if extra:
        extra(im, d)
    return im


def discord_banner():
    # Discord shows the banner at 240 x 135 above the channel list: logo only, big.
    w, h = 960, 540
    im = shade(shot("mountains", (w, h), (0.5, 0.55)), side="center", strength=0.75, base=0.25)
    logo, pad = with_glow(svg_png("logo-stacked", 10), 20)
    paste(im, logo, ((w - logo.width) / 2, (h - logo.height) / 2))
    return im


def invite_splash():
    def season(im, d):
        f = body(30, bold=True)
        label = "SEASON I  ·  FACTIONS PvP  ·  JAVA 26.3"
        tw = d.textlength(label, font=f)
        pill(d, ((1920 - tw) / 2 - 28, 1080 - 150, (1920 + tw) / 2 + 28, 1080 - 96), label, f)

    return centered_card((1920, 1080), "end_citadel", (0.45, 0.5), 14, 56, 34, season)


def side_card(size, shot_name, focus, cell, tag_size, sub_size, side="left", safe=None, pill_text=None, base=0.12):
    """Logo left (or right), tagline and hooks under it, the shot showing on the other side."""
    w, h = size
    im = shade(shot(shot_name, size, focus), side=side, strength=0.92, reach=0.8, base=base)
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = safe or (0, 0, w, h)
    margin = (x1 - x0) * 0.06
    logo, pad = with_glow(svg_png("logo", cell), cell * 2)
    lines = [(TAGLINE, display(tag_size), PAPER), (HOOKS, body(sub_size), MUTED), (ADDRESS, mono(sub_size), GOLD)]
    block_h = logo.height - pad * 2 + tag_size * 0.8 + tag_size * 1.3 + sub_size * 1.6 * 2
    if pill_text:
        block_h += sub_size * 2.6
    y = y0 + ((y1 - y0) - block_h) / 2
    x = x0 + margin if side == "left" else x1 - margin - (logo.width - pad * 2)
    if pill_text:
        f = body(round(sub_size * 0.95), bold=True)
        tw = d.textlength(pill_text, font=f)
        ph = sub_size * 1.8
        px = x if side == "left" else x + (logo.width - pad * 2) - tw - ph
        pill(d, (px, y, px + tw + ph, y + ph), pill_text, f)
        y += sub_size * 2.6
    paste(im, logo, (x - pad, y - pad))
    y += logo.height - pad * 2 + tag_size * 0.8
    anchor = "la" if side == "left" else "ra"
    tx = x if side == "left" else x + (logo.width - pad * 2)
    for s, f, c in lines:
        text(d, (tx, y), s, f, c, anchor=anchor)
        y += f.size * (1.3 if f.size == tag_size else 1.6)
    return im


def og_image():
    return side_card((1200, 630), "nether_castle", (0.62, 0.5), 7, 40, 24, pill_text="SEASON I")


def youtube_header():
    # YouTube crops to 1546 x 423 in the middle on phones; everything that matters sits in there.
    w, h = 2560, 1440
    safe = ((w - 1546) / 2, (h - 423) / 2, (w + 1546) / 2, (h + 423) / 2)
    return side_card((w, h), "fortified_village", (0.5, 0.52), 9, 58, 32, safe=safe, base=0.45)


def twitter_header():
    # The profile picture covers the bottom-left corner: keep the type on the right.
    return side_card((1500, 500), "mage_tower", (0.66, 0.55), 6, 36, 21, side="right", pill_text="SEASON I", base=0.2)


def server_list_banner():
    """468 x 60, the size Minecraft server-list sites take."""
    w, h = 468, 60
    im = shot("mountains", (w, h), (0.5, 0.35))
    im = Image.composite(Image.new("RGBA", (w, h), PEN + (255,)), im, Image.new("L", (w, h), 215))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), outline=INK, width=2)
    mark = svg_png("face", 3)  # 48 px
    paste(im, mark, (8, 6))
    word = svg_png("wordmark", 2)  # 10 cells tall -> 20 px
    paste(im, word, (66, 8))
    d.text((w - 10, 20), ADDRESS, font=mono(12), fill=GOLD, anchor="rs")
    d.text((66, 34), "Factions PvP · Strength SMP · Season I · Java 26.3", font=body(13, bold=True), fill=PAPER)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    made = logo_pngs()
    banners = {
        "discord-banner-960x540.png": discord_banner,
        "discord-invite-splash-1920x1080.png": invite_splash,
        "youtube-header-2560x1440.png": youtube_header,
        "twitter-header-1500x500.png": twitter_header,
        "og-1200x630.png": og_image,
        "server-list-468x60.png": server_list_banner,
    }
    for name, make in banners.items():
        im = make().convert("RGB")
        im.save(OUT / name, optimize=True)
        made.append(OUT / name)
        print(f"{name}: {im.size}")
    # Repo copies of the small ones; the OG image ships on the site as a JPEG.
    (HERE / "banners").mkdir(exist_ok=True)
    shutil.copy(OUT / "server-list-468x60.png", HERE / "banners")
    shutil.copy(OUT / "discord-banner-960x540.png", HERE / "banners")
    Image.open(OUT / "og-1200x630.png").save(REPO / "site" / "public" / "img" / "og.jpg", quality=86, optimize=True)
    for p in made:
        if p.parent != OUT:
            shutil.copy(p, OUT / p.name)


if __name__ == "__main__":
    main()
