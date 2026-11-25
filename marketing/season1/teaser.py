"""Renders the Season 1 teaser videos with no gameplay footage: Pillow frames piped into ffmpeg,
music synthesised by ../music.py (nothing to license).

    python marketing/season1/teaser.py            # everything
    python marketing/season1/teaser.py teaser     # 24 s vertical teaser, 1080 x 1920
    python marketing/season1/teaser.py sting      # 4 s logo sting, 1920 x 1080 and 1080 x 1920
    python marketing/season1/teaser.py --preview  # contact sheet of the teaser, one frame per section

Motion jumps in steps (DESIGN.md: no easing, no glows, no flashes). Everything lands on the beat of
the 100 BPM track: a bar is 2.4 s, a beat 0.6 s.
"""

import argparse
import subprocess
import sys
from functools import cache
from pathlib import Path

import art
import numpy as np
from art import BONE, BONE2, GOLD, HEART, INK, SHADE, STONE
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import music  # noqa: E402

FPS = 30
BEAT = music.BEAT
BAR = music.BAR
TEASER_BARS = 10  # 24 s


# --- Layers ---------------------------------------------------------------------------------------
@cache
def words(text, size, color, font="display", outline=True):
    f = art.display(size) if font == "display" else art.body(size)
    pad = max(6, size // 8)
    bb = f.getbbox(text, stroke_width=pad // 2 if outline else 0)
    im = Image.new("RGBA", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    kw = {"stroke_width": max(2, size // 18), "stroke_fill": INK} if outline else {}
    d.text((pad - bb[0], pad - bb[1]), text, font=f, fill=color, **kw)
    return im


@cache
def gold_plate(text, size):
    f = art.body(size)
    bb = f.getbbox(text)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    im = Image.new("RGBA", (w + int(h * 2.2), h + int(h * 1.3)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    art.plate(d, (0, 0, im.width - 1, im.height - 1), GOLD, cut=max(3, h // 6))
    d.text((im.width // 2, im.height // 2), text, font=f, fill=INK, anchor="mm")
    return im


@cache
def join_plaque(width):
    lines = [("JAVA", art.JAVA), ("BEDROCK", art.BEDROCK), ("PORT", art.BEDROCK_PORT)]
    f = art.fit(art.body, art.BEDROCK, int(width * 0.92), 56)
    lab = art.display(int(f.size * 0.7))
    lh = int(f.size * 1.25)
    h = int(f.size * 0.8) + (lh + int(lab.size * 1.1)) * 2 + lh
    im = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    art.plate(d, (0, 0, width - 1, h - 1), STONE, cut=6)
    y = int(f.size * 0.5)
    x = int(width * 0.04)
    for label, value in lines[:2]:
        d.text((x, y), label, font=lab, fill=INK)
        y += int(lab.size * 1.1)
        d.text((x, y), value, font=f, fill=INK)
        y += lh
    d.text((x, y), "BEDROCK PORT", font=lab, fill=INK)
    d.text(
        (x + lab.getbbox("BEDROCK PORT")[2] + int(f.size * 0.6), y + lab.size // 2),
        art.BEDROCK_PORT,
        font=f,
        fill=INK,
        anchor="lm",
    )  # Atkinson digits: Pixelify's 2 and 5 are ambiguous
    return im


@cache
def mark_img(cell, heart=True, badge=True):
    return art.mark(cell, heart=heart, badge=badge)


@cache
def lock_img(cell):
    return art.lockup(cell)


@cache
def bg(size, kind):
    if kind == "dark":
        return Image.new("RGBA", size, SHADE + (255,))
    return art.canopy(size, cell=size[0] // 27, seed=hash(kind) % 100, depth=0.18).convert("RGBA")


def pop_scale(t, t0):
    """Stepped pop: 0 before t0, then 130 %, 90 %, 100 % for two frames each."""
    if t < t0:
        return 0
    f = int((t - t0) * FPS)
    return 1.3 if f < 2 else 0.9 if f < 4 else 1.0


def put(frame, layer, cx, cy, t, t0, until=None):
    """Paste `layer` centred on (cx, cy), popping in at t0, gone at `until`."""
    if until is not None and t >= until:
        return
    s = pop_scale(t, t0)
    if not s:
        return
    if s != 1.0:
        layer = layer.resize((max(1, int(layer.width * s)), max(1, int(layer.height * s))), Image.NEAREST)
    frame.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


def hearts_row(n, total, cell):
    hi = art.heart_icon(cell)
    gap = cell
    im = Image.new("RGBA", (total * (hi.width + gap), hi.height), (0, 0, 0, 0))
    empty = hi.copy()
    px = empty.load()
    for y in range(empty.height):
        for x in range(empty.width):
            r, g, b, a = px[x, y]
            if a and (r, g, b) != INK:
                px[x, y] = (60, 70, 66, 255)
    for i in range(total):
        im.alpha_composite(hi if i < n else empty, (i * (hi.width + gap), 0))
    return im


# --- Teaser (1080 x 1920) -----------------------------------------------------------------------
TW, TH = 1080, 1920
CX = 500  # a little left of centre: TikTok, Reels and Shorts put their buttons on the right


def teaser_frame(t):
    bar = int(t // BAR)
    b = lambda n: n * BEAT  # noqa: E731  (beats from the start)
    frame = bg((TW, TH), "dark" if bar < 2 else f"canopy{min(bar, 8) // 3}").copy()

    if bar < 2:  # Cold open: the heart beats twice, the monkey grabs it.
        if t < b(2):
            k = 1.25 if (t % BEAT) < 0.1 else 1.0
            h = art.heart_icon(int(26 * k))
            frame.alpha_composite(h, (CX - h.width // 2, 760 - h.height // 2))
        else:
            put(frame, mark_img(24, badge=False), CX + 12, 700, t, b(2))
        put(frame, words("MONKEY SEE,", 104, BONE), CX, 1140, t, b(3))
        put(frame, words("MONKEY STEAL.", 104, HEART), CX, 1270, t, b(4))
        put(frame, lock_img(9), CX, 1470, t, b(6))
    elif bar == 2:  # Fresh start
        put(frame, gold_plate("SEASON 1", 88), CX, 620, t, b(8))
        put(frame, words("A FRESH WORLD.", 96, BONE), CX, 820, t, b(9))
        put(frame, words("EVERYONE STARTS", 84, BONE2), CX, 1040, t, b(10))
        put(frame, words("BROKE.", 150, GOLD), CX, 1190, t, b(11))
    elif bar == 3:  # Grind, sell, trade, with the coin counter running
        for i, w in enumerate(("GRIND.", "SELL.", "TRADE.")):
            put(frame, words(w, 150, BONE if i < 2 else GOLD), CX, 560 + i * 190, t, b(12 + i))
        coins = int(min(1.0, max(0.0, (t - b(12)) / (BAR * 0.9))) ** 2 * 1_250_000)
        c = art.coin_icon(14)
        txt = words(f"{coins:,}", 96, GOLD, font="body")
        row = Image.new("RGBA", (c.width + 24 + txt.width, max(c.height, txt.height)), (0, 0, 0, 0))
        row.alpha_composite(c, (0, (row.height - c.height) // 2))
        row.alpha_composite(txt, (c.width + 24, (row.height - txt.height) // 2))
        put(frame, row, CX, 1240, t, b(12))
    elif bar == 4:  # Get rich, then leave the safe zone
        put(frame, words("GET RICH...", 140, GOLD), CX, 640, t, b(16), until=b(18))
        put(frame, words("...THEN LEAVE", 110, BONE), CX, 860, t, b(18))
        put(frame, words("THE SAFE ZONE.", 110, BONE), CX, 1000, t, b(18) + BEAT / 2)
        if t >= b(19):
            frame.alpha_composite(Image.new("RGBA", (TW, TH), (0, 0, 0, 120)))
            put(frame, words("...", 160, HEART), CX, 1250, t, b(19))
    elif bar == 5:  # The drop
        put(frame, words("STEAL", 230, BONE), CX, 640, t, b(20))
        put(frame, words("HEARTS.", 230, HEART), CX, 880, t, b(20) + BEAT / 2)
        n = 10 + min(5, int((t - b(21)) / (BEAT / 2)) + 1) if t >= b(21) else 10
        put(frame, hearts_row(n, 15, 5), CX, 1180, t, b(21))
        put(frame, words(f"{n} HEARTS", 64, BONE2, font="body", outline=False), CX, 1290, t, b(21))
    elif bar == 6:  # Crossplay, no mods
        put(frame, words("JAVA", 170, BONE), CX, 560, t, b(24))
        put(frame, words("+ BEDROCK", 150, GOLD), CX, 740, t, b(24) + BEAT / 2)
        put(frame, words("PHONE · CONSOLE · PC", 66, BONE2, font="body"), CX, 920, t, b(25))
        put(frame, gold_plate("NO MODS", 110), CX, 1140, t, b(26))
        put(frame, words("Join from the vanilla game", 54, BONE2, font="body", outline=False), CX, 1290, t, b(27))
    elif bar == 7:  # Free, cosmetics only
        put(frame, words("FREE", 260, GOLD), CX, 650, t, b(28))
        put(frame, words("TO PLAY.", 150, BONE), CX, 860, t, b(28) + BEAT / 2)
        put(frame, words("Store is cosmetic only.", 62, BONE2, font="body"), CX, 1060, t, b(30))
        put(
            frame, words("Nothing you can buy wins a fight.", 50, BONE2, font="body", outline=False), CX, 1150, t, b(31)
        )
    else:  # End card
        put(frame, mark_img(15), CX + 8, 430, t, b(32))
        put(frame, lock_img(8), CX, 720, t, b(32) + 2 / FPS)
        put(frame, gold_plate("SEASON 1", 72), CX, 900, t, b(33))
        put(frame, words("SAT 6 FEB · 5 PM PT", 80, BONE, font="body"), CX, 1020, t, b(34))
        put(frame, join_plaque(900), CX, 1250, t, b(35))
        put(frame, words(art.TAGLINE, 54, HEART, font="body"), CX, 1500, t, b(36))
        put(frame, words(art.HANDLE, 50, BONE2, font="body", outline=False), CX, 1580, t, b(37))
    return frame


# --- Sting -----------------------------------------------------------------------------------------
STING_LEN = 4.0


def sting_frame(t, size):
    W, H = size
    vertical = H > W
    frame = bg(size, "dark").copy()
    cx = W // 2
    cell = 22 if not vertical else 20
    mcy = H // 2 - (80 if not vertical else 260)
    if t < 0.6:
        k = 1.3 if (t % 0.3) < 0.08 else 1.0
        h = art.heart_icon(int(cell * 1.1 * k))
        frame.alpha_composite(h, (cx - h.width // 2, mcy - h.height // 2))
    else:
        if vertical:
            put(frame, mark_img(cell, badge=t >= 2.0), cx + cell // 2, mcy, t, 0.6)
            put(frame, lock_img(10), cx, mcy + 380, t, 1.2)
        else:
            m = mark_img(cell, badge=t >= 2.0)
            lock = lock_img(15)
            total = m.width + 60 + lock.width
            x0 = cx - total // 2
            put(frame, m, x0 + m.width // 2, mcy, t, 0.6)
            put(frame, lock, x0 + m.width + 60 + lock.width // 2, mcy, t, 1.2)
        if t >= 2.0:
            ty = mcy + (380 if not vertical else 620)
            put(frame, words(art.TAGLINE, 58 if not vertical else 56, BONE2, font="body"), cx, ty, t, 2.3)
    return frame


def sting_audio(path):
    sr = music.SR
    n = int(STING_LEN * sr)
    track = np.zeros(n + sr)
    k = music.kick()
    music.place(track, k, 0.0, 0.7)
    music.place(track, k, 0.3, 0.7)
    for i, note in enumerate((69, 72, 76, 81)):
        music.place(track, music.pluck(note, 0.6), 0.6 + i * 0.15, 0.35)
    music.place(track, music.boom(), 2.0, 1.0)
    music.place(track, music.crash(), 2.0, 0.7)
    chord = sum(music.saw(music.hz(m), 2.0, rolloff=4, detune=d) for m in (57, 60, 64, 69) for d in (-0.004, 0, 0.004))
    chord *= music.env(len(chord), 0.05, 1.2, 2.0)
    music.place(track, chord, 2.0, 0.07)
    mix = music.reverb(track, 1.6, 0.25)[:n]
    fade = int(0.6 * sr)
    mix[-fade:] *= np.linspace(1, 0, fade) ** 2
    mix *= 0.89 / np.max(np.abs(mix))
    music.write(path, np.stack([mix, mix], axis=1))


def teaser_audio(path):
    music.BARS = TEASER_BARS
    music.CTA = 8  # impact on the end card
    music.LIFT = 5  # crash and doubled hats on STEAL HEARTS
    music.LENGTH = TEASER_BARS * BAR
    music.write(path, music.render())


# --- Encoding --------------------------------------------------------------------------------------
def encode(path, size, seconds, frame_fn, audio):
    W, H = size
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-i",
        str(audio),
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(FPS),
        "-af",
        "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        "-shortest",
        str(path),
    ]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(seconds * FPS)):
        p.stdin.write(frame_fn(i / FPS).convert("RGB").tobytes())
    p.stdin.close()
    if p.wait():
        raise SystemExit(f"ffmpeg failed for {path}")
    print("wrote", path)


def preview(path):
    times = [1.9, 4.5, 7.0, 9.4, 11.6, 14.2, 16.6, 19.0, 23.0]
    thumbs = [teaser_frame(t).convert("RGB").resize((270, 480)) for t in times]
    sheet = Image.new("RGB", (270 * len(thumbs) + 8 * (len(thumbs) - 1), 480), "white")
    for i, th in enumerate(thumbs):
        sheet.paste(th, (i * 278, 0))
    sheet.save(path)
    print("wrote", path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", nargs="?", default="all", choices=["all", "teaser", "sting"])
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    out = art.OUT
    out.mkdir(parents=True, exist_ok=True)
    if a.preview:
        preview(out / "teaser-contact-sheet.png")
        return
    if a.what in ("all", "teaser"):
        wav = out / "teaser-music.wav"
        teaser_audio(wav)
        encode(out / "teaser-season1-1080x1920.mp4", (TW, TH), TEASER_BARS * BAR, teaser_frame, wav)
        teaser_frame(23.0).convert("RGB").save(out / "teaser-cover-1080x1920.png")
    if a.what in ("all", "sting"):
        wav = out / "sting-audio.wav"
        sting_audio(wav)
        encode(out / "logo-sting-1920x1080.mp4", (1920, 1080), STING_LEN, lambda t: sting_frame(t, (1920, 1080)), wav)
        encode(out / "logo-sting-1080x1920.mp4", (1080, 1920), STING_LEN, lambda t: sting_frame(t, (1080, 1920)), wav)


if __name__ == "__main__":
    main()
