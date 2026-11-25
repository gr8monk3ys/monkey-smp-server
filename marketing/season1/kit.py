"""Writes the Season 1 social kit: avatars, platform banners, announcement posts and the YouTube
thumbnail template, into $MONKEY_KIT_OUT (default marketing/season1/out, kept out of git).

    python marketing/season1/kit.py
    python marketing/season1/kit.py thumb --bg shot.png --title "STEAL HEARTS" --out thumb.png

Sizes are each platform's own upload size; content sits inside the area every device shows.
"""

import argparse

import art
from art import BONE, BONE2, GOLD, HEART, INK, LEAF1, SHADE, STONE
from PIL import Image, ImageDraw

FACTS = "FREE  ·  JAVA + BEDROCK  ·  NO MODS"
DATE = "SEASON 1  ·  " + art.DATE_LONG


def save(im, name):
    art.OUT.mkdir(parents=True, exist_ok=True)
    path = art.OUT / name
    im.convert("RGB").save(path, optimize=True)
    print("wrote", path.relative_to(art.OUT.parent) if art.OUT.parent in path.parents else path)
    return path


def scaled_cell(target_w, grid_w):
    return max(1, target_w // grid_w)


def avatar(size):
    im = art.canopy((size, size), cell=max(8, size // 25), seed=3, depth=0.22).convert("RGBA")
    cell = scaled_cell(int(size * 0.62), 24)
    m = art.mark(cell)
    im.alpha_composite(m, ((size - m.width) // 2 + cell // 2, (size - m.height) // 2))
    return im


def date_plate(d, cx, cy, text, font, fill=GOLD, fg=INK):
    bb = font.getbbox(text)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    padx, pady = int(h * 0.9), int(h * 0.55)
    box = (cx - w // 2 - padx, cy - h // 2 - pady, cx + w // 2 + padx, cy + h // 2 + pady)
    art.plate(d, box, fill, cut=max(3, h // 6))
    d.text((cx, cy), text, font=font, fill=fg, anchor="mm")
    return box


def date_font(size):
    # Anything with a time or a port uses Atkinson Bold, whose digits can't be misread at a glance.
    return art.body(size)


def text_stack(d, cx, top, width, scale=1.0, tagline=True):
    """SURVIVE, TRADE, / STEAL HEARTS. / gold date plate / facts line. Returns the bottom y."""
    y = top
    if tagline:
        for line, color in (("SURVIVE, TRADE,", BONE), ("STEAL HEARTS.", HEART)):
            f = art.fit(art.display, "SURVIVE, TRADE,", width, int(96 * scale))  # the longer line
            art.outlined(d, (cx, y + f.size // 2), line, f, color)
            y += int(f.size * 1.6)  # f.size is the cap height in Press Start 2P
        y += int(14 * scale)
    f = art.fit(date_font, DATE, int(width * 0.84), int(46 * scale))
    box = date_plate(d, cx, y + f.size // 2 + 6, DATE, f)
    y = box[3] + int(f.size * 0.6)
    f = art.fit(art.body, FACTS, width, int(f.size * 0.8))
    d.text((cx, y + f.size // 2), FACTS, font=f, fill=BONE2, anchor="mm")
    return y + f.size


def banner(size, safe=None, seed=11, tagline=True):
    """Lockup and launch facts inside `safe` (w, h, centred), canopy behind."""
    W, H = size
    sw, sh = safe or size
    x0, y0 = (W - sw) // 2, (H - sh) // 2
    im = art.canopy(size, cell=max(12, H // 30), seed=seed, depth=0.28).convert("RGBA")
    d = ImageDraw.Draw(im)
    if sw / sh > 2.3:  # side by side: lockup left, text right
        cell = max(2, min(int(sh * 0.8) // 22, int(sw * 0.56) // 100))
        lock = art.wide_lockup(cell)
        gap = int(sw * 0.04)
        text_w = sw - lock.width - gap
        lx = x0
        im.alpha_composite(lock, (lx, y0 + (sh - lock.height) // 2))
        cx = lx + lock.width + gap + text_w // 2
        scale = sh / 300
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        while (hgt := text_stack(probe, cx, 0, text_w, scale, tagline)) > sh * 0.94:
            scale *= 0.94
        text_stack(d, cx, y0 + (sh - hgt) // 2, text_w, scale, tagline)
    else:  # stacked: mark, wordmark, text
        cell = max(2, int(sh * 0.32) // 22)
        m = art.mark(cell)
        lock = art.lockup(max(2, cell // 2 + 1))
        top = y0 + int(sh * 0.04)
        im.alpha_composite(m, (W // 2 - m.width // 2 + cell // 2, top))
        top += m.height + int(sh * 0.02)
        im.alpha_composite(lock, (W // 2 - lock.width // 2, top))
        top += lock.height + int(sh * 0.03)
        text_stack(d, W // 2, top, int(sw * 0.9), sh / 900, tagline)
    return im


def announce(size):
    """Portrait post: mark, lockup, the hook, the facts and both join addresses."""
    W, H = size
    im = art.canopy(size, cell=W // 30, seed=21, depth=0.2).convert("RGBA")
    d = ImageDraw.Draw(im)
    cell = min(W // 40, H // 78)
    m = art.mark(cell)
    y = int(H * 0.1)
    im.alpha_composite(m, (W // 2 - m.width // 2 + cell // 2, y))
    y += m.height + cell
    lock = art.lockup(cell // 2 + 2)
    im.alpha_composite(lock, (W // 2 - lock.width // 2, y))
    y += lock.height + int(H * 0.02)
    f = art.display(int(W * 0.075))
    art.outlined(d, (W // 2, y + f.size // 2), "MONKEY SEE,", f, BONE)
    y += int(f.size * 1.6)
    art.outlined(d, (W // 2, y + f.size // 2), "MONKEY STEAL.", f, HEART)
    y += int(f.size * 2.0)
    f = art.fit(date_font, DATE, int(W * 0.8), int(W * 0.05))
    box = date_plate(d, W // 2, y + f.size // 2, DATE, f)
    y = box[3] + int(H * 0.03)
    f = art.fit(art.body, FACTS, int(W * 0.86), int(W * 0.04))
    d.text((W // 2, y), FACTS, font=f, fill=BONE, anchor="mt")
    y += int(f.size * 1.8)
    join(d, W // 2, y, int(W * 0.86), int(W * 0.03))
    return im


def join(d, cx, top, width, size):
    """Stone address plaque: Java and Bedrock lines."""
    lines = [("JAVA", art.JAVA), ("BEDROCK", f"{art.BEDROCK}  port {art.BEDROCK_PORT}")]
    f = art.fit(art.body, lines[1][1], int(width * 0.72), size)
    lab = art.body(int(f.size * 0.8))
    lh = int(f.size * 1.7)
    box = (cx - width // 2, top, cx + width // 2, top + lh * 2 + f.size)
    art.plate(d, box, STONE, cut=max(3, f.size // 4))
    y = top + f.size // 2 + lh // 2
    for label, value in lines:
        d.text((box[0] + f.size, y), label, font=lab, fill=INK, anchor="lm")
        d.text((box[2] - f.size, y), value, font=f, fill=INK, anchor="rm")
        y += lh
    return box[3]


# --- YouTube thumbnail -----------------------------------------------------------------------------
THUMB = (1280, 720)


def thumb_overlay(title="STEAL HEARTS", sub="SEASON 1", red=True):
    """Transparent overlay: a left panel with the title, the mark bottom-left. The right 60 % is left
    clear for a screenshot. YouTube puts the duration over the bottom-right corner, so nothing goes there."""
    W, H = THUMB
    im = Image.new("RGBA", THUMB, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    panel_w = int(W * 0.46)
    # stepped panel edge (pixel diagonal), flat colours
    step = 40
    for i, x in enumerate(range(0, H, step)):
        edge = panel_w + (i % 2) * step // 2
        d.rectangle([0, x, edge, x + step - 1], fill=SHADE + (255,))
        d.rectangle([edge, x, edge + 10, x + step - 1], fill=INK + (255,))
    words = title.split()
    nominal = 150 if max(len(w) for w in words) <= 6 else 120
    y = 120
    for i, w in enumerate(words):
        color = HEART if (red and i == len(words) - 1) else GOLD if i == len(words) - 1 else BONE
        f = art.fit(art.display, w, panel_w - 60, nominal)
        art.outlined(d, (36, y), w, f, color, anchor="lm", width=8)
        y += int(f.size * 1.5)  # f.size is the cap height in Press Start 2P
    y += 10
    sf = art.display(54)
    box = (36, y - 10, 36 + sf.getbbox(sub)[2] + 48, y + 66)
    art.plate(d, box, GOLD, cut=6)
    d.text((box[0] + 24, (box[1] + box[3]) // 2), sub, font=sf, fill=INK, anchor="lm")
    m = art.mark(7)
    im.alpha_composite(m, (30, H - m.height - 24))
    hi = art.heart_icon(10) if red else art.coin_icon(11)
    im.alpha_composite(hi, (panel_w - hi.width - 10, 30))
    return im


def thumb(bg=None, title="STEAL HEARTS", sub="SEASON 1", red=True):
    W, H = THUMB
    if bg:
        shot = Image.open(bg).convert("RGB")
        r = max(W / shot.width, H / shot.height)
        shot = shot.resize((round(shot.width * r), round(shot.height * r)), Image.LANCZOS)
        x = (shot.width - W) // 2 + int(W * 0.18)  # push the subject right, out from behind the panel
        x = min(max(0, x), shot.width - W)
        base = shot.crop((x, (shot.height - H) // 2, x + W, (shot.height - H) // 2 + H)).convert("RGBA")
    else:
        base = placeholder()
    base.alpha_composite(thumb_overlay(title, sub, red))
    return base


def placeholder():
    W, H = THUMB
    im = art.canopy(THUMB, cell=40, seed=5, depth=0.3).convert("RGBA")
    d = ImageDraw.Draw(im)
    f = art.body(34)
    d.text(
        (int(W * 0.74), H // 2),
        "your screenshot here\n1280 x 720, subject right",
        font=f,
        fill=BONE2,
        anchor="mm",
        align="center",
    )
    d.rectangle([int(W * 0.5), 40, W - 40, H - 40], outline=LEAF1, width=6)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", nargs="?", default="all")
    ap.add_argument("--bg")
    ap.add_argument("--title", default="STEAL HEARTS")
    ap.add_argument("--sub", default="SEASON 1")
    ap.add_argument("--gold", action="store_true", help="last title word gold (money) instead of heart red")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.what == "thumb":
        im = thumb(a.bg, a.title.upper(), a.sub.upper(), not a.gold)
        im.convert("RGB").save(a.out or art.OUT / "thumbnail.png")
        return

    save(avatar(800), "avatar-800.png")
    save(avatar(400), "avatar-400.png")
    # YouTube channel art: 2560 x 1440 upload, 1546 x 423 shows on every device.
    save(banner((2560, 1440), safe=(1546, 423)), "youtube-banner-2560x1440.png")
    # X header: the avatar covers the bottom-left, so keep content right of centre-left.
    x = banner((1500, 500), safe=(1100, 330), seed=12)
    save(x, "x-header-1500x500.png")
    save(banner((1200, 480), safe=(1000, 300), seed=13), "twitch-banner-1200x480.png")
    save(banner((1920, 384), safe=(1500, 260), seed=14, tagline=False), "reddit-banner-1920x384.png")
    save(banner((960, 540), safe=(820, 420), seed=15), "discord-server-banner-960x540.png")
    save(banner((1920, 1080), safe=(1500, 900), seed=16), "discord-invite-splash-1920x1080.png")
    save(announce((1080, 1350)), "announce-post-1080x1350.png")
    save(announce((1080, 1920)), "announce-story-1080x1920.png")
    ov = thumb_overlay()
    art.OUT.mkdir(parents=True, exist_ok=True)
    ov.save(art.OUT / "thumbnail-overlay-1280x720.png")
    print("wrote thumbnail-overlay-1280x720.png")
    save(thumb(), "thumbnail-template-1280x720.png")
    save(thumb(None, "GET RICH", "SEASON 1", red=False), "thumbnail-example-gold-1280x720.png")


if __name__ == "__main__":
    main()
