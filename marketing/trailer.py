"""Renders the Monkey SMP trailer: slow pans over the in-game screenshots, staged gameplay footage of the
events, a title card per hook, the self-made music from music.py, and a call to action. Frames are drawn
with Pillow and piped to ffmpeg.

    python marketing/trailer.py              # 1920 x 1080, 30 fps, about 60 s
    python marketing/trailer.py --preview    # contact sheet of one frame per section, no video

Every section is two bars of the music (4.8 s at 100 BPM), so cuts land on the downbeat.

The footage (FOOTAGE, 1080p30 mp4s, not in git) was filmed on a throwaway copy of the server with
Carpet fake players standing in for real ones, driven by the real event functions: the raid timer and
flags, the arena kit, the Cup sidebar and the wardrobe items.
"""

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import music
from PIL import Image, ImageDraw, ImageFilter

from build import (
    ADDRESS,
    GOLD,
    INK,
    OUT,
    PAPER,
    PEN,
    SHOTS,
    TAGLINE,
    body,
    display,
    mono,
    shade,
    svg_png,
    text,
    with_glow,
)

W, H, FPS = 1920, 1080, 30
SECTION = 2 * music.BAR
FADE = 0.5  # crossfade between sections, seconds
DISCORD = "discord.gg/C25hy9Ca9W"
SOFT = (226, 221, 210)
FOOTAGE = Path(r"D:\DevData\monkey-smp-marketing\footage")


@dataclass
class Section:
    shots: list  # [(screenshot, (zoom from, zoom to), (centre from), (centre to))]
    kicker: str = ""
    headline: str = ""
    sub: str = ""
    bars: int = 2
    clip: tuple = ()  # (footage name, start in the file, playback speed) instead of shots
    start: float = 0.0
    layers: dict = field(default_factory=dict)

    @property
    def end(self):
        return self.start + self.bars * music.BAR


SECTIONS = [
    Section([("ancient_city", (1.15, 1.05), (0.5, 0.5), (0.52, 0.5))]),  # logo reveal
    Section(
        [("mountains", (1.0, 1.12), (0.5, 0.6), (0.5, 0.5))],
        "MINECRAFT JAVA 26.3  ·  FABRIC",
        "A modded factions server.",
        "PvP, politics and a world worth fighting over.",
    ),
    Section(
        [("fortified_village", (1.08, 1.2), (0.42, 0.55), (0.55, 0.55))],
        "01  ·  FACTIONS OF FOUR",
        "Four to a faction.",
        "Raise a banner. Choose your three carefully.",
    ),
    Section(
        [("castle_ruins", (1.05, 1.18), (0.55, 0.6), (0.45, 0.55))],
        "02  ·  ALLIANCES AND TERRITORY",
        "Claim land. Make allies.",
        "2 × 2 chunks a player under your banner. Everything outside it is contested.",
    ),
    Section(
        [("nether_castle", (1.2, 1.05), (0.6, 0.45), (0.5, 0.5))],
        "03  ·  STRENGTH SMP",
        "Every fight has stakes.",
        "Win and your Strength grows. Lose and it drains away.",
    ),
    Section(
        [
            ("end_citadel", (1.05, 1.15), (0.35, 0.5), (0.45, 0.5)),
            ("ancient_city", (1.1, 1.2), (0.45, 0.5), (0.55, 0.45)),
        ],
        "04  ·  MODDED TERRAIN AND DUNGEONS",
        "Land worth fighting over.",
        "Tectonic, Terralith, Incendium and Nullscape. Castles, citadels and deep dark cities.",
    ),
    Section(
        [],
        "05  ·  SEASON I LAUNCH WEEKEND",
        "Build Battle.",
        "A wheel picks bonus blocks. Factions build until judging night.",
        clip=("build", 1.4, 2.4),
    ),
    Section(
        [],
        "06  ·  FACTION RAID",
        "Capture the flag.",
        "Carry a rival's flag home and plant it beside your own.",
        clip=("raid", 3.42, 0.68),
    ),
    Section(
        [],
        "07  ·  ARENA GLORY",
        "Same kit. Best fighter wins.",
        "Kit duels, then the 4v4 faction bracket.",
        clip=("arena", 2.4, 1.0),
    ),
    Section(
        [],
        "08  ·  THE SEASON CUP",
        "Every event scores.",
        "A new event every Saturday, 6 PM Pacific. Twelve weeks, one champion faction.",
        clip=("cup", 0.4, 1.0),
    ),
    Section(
        [],
        "09  ·  ONE PASS",
        "Same price for everyone.",
        "$5 a month. Supporter perks are cosmetic only.",
        clip=("wardrobe", 3.6, 1.0),
    ),
    Section([("mountains", (1.25, 1.15), (0.5, 0.45), (0.5, 0.42))], bars=3),  # call to action
]

_shots = {}


class Clip:
    """One section's footage, read in order from a single ffmpeg process.

    Frame k is the file at start + (k / FPS - FADE) * speed, so the crossfade into the section already
    has footage to show. Asking for an earlier frame restarts the reader; past the end, the last frame holds.
    """

    def __init__(self, name, start, speed):
        self.path, self.start, self.speed = FOOTAGE / f"{name}.mp4", start, speed
        self.proc, self.pos, self.last = None, -1, None

    def open(self):
        self.close()
        ss = max(self.start - FADE * self.speed, 0.0)
        vf = f"setpts=PTS/{self.speed},fps={FPS},scale={W}:{H}"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{ss:.3f}", "-i", str(self.path),
            "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ]  # fmt: skip
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        self.pos = -1

    def frame(self, local):
        k = max(0, round((local + FADE) * FPS))
        if self.proc is None or k < self.pos:
            self.open()
        while self.pos < k:
            buf = self.proc.stdout.read(W * H * 3)
            if len(buf) < W * H * 3:
                break
            self.last = Image.frombytes("RGB", (W, H), buf)
            self.pos += 1
        if self.last is None:
            sys.exit(f"no frames from {self.path}")
        return self.last

    def close(self):
        if self.proc:
            self.proc.kill()
            self.proc.wait()
            self.proc.stdout.close()
            self.proc = None


def source(name):
    if name not in _shots:
        _shots[name] = Image.open(SHOTS / f"{name}.png").convert("RGB")
    return _shots[name]


def ease(u):
    return u * u * (3 - 2 * u)


def pan(name, zoom, c0, c1, u):
    """A frame of a slow push/pull across one shot; `u` runs 0..1 over the section."""
    im = source(name)
    u = min(max(u, -0.2), 1.2)
    z = zoom[0] + (zoom[1] - zoom[0]) * u
    cx = (c0[0] + (c1[0] - c0[0]) * u) * im.width
    cy = (c0[1] + (c1[1] - c0[1]) * u) * im.height
    # The crop is the 16:9 box that fills the frame at zoom 1, shrunk by z, kept inside the shot.
    bw = min(im.width, im.height * W / H) / z
    bh = bw * H / W
    x0 = min(max(cx - bw / 2, 0), im.width - bw)
    y0 = min(max(cy - bh / 2, 0), im.height - bh)
    return im.transform((W, H), Image.Transform.EXTENT, (x0, y0, x0 + bw, y0 + bh), Image.Resampling.BILINEAR)


def card_layer(sec):
    """The section's title card, drawn once: kicker, headline, sub, lower left."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x, y = 140, H - 330
    text(d, (x, y), sec.kicker, mono(34), GOLD)
    text(d, (x, y + 52), sec.headline, display(104), PAPER)
    text(d, (x, y + 192), sec.sub, body(40), SOFT)
    return layer


def bug_layer():
    """The small logo in the top-left corner during the hooks."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    logo, pad = with_glow(svg_png("logo", 4), 8)
    layer.alpha_composite(logo, (90 - pad, 70 - pad))
    return layer


def legibility_layer():
    """Darkens the lower left, where the cards sit, plus a soft vignette."""
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lower = shade(base, side="bottom", strength=0.8, reach=0.55, base=0.0)
    left = shade(base, side="left", strength=0.55, reach=0.7, base=0.0)
    out = Image.alpha_composite(lower, left)
    vignette = shade(base, side="center", strength=0.5, base=0.0)
    return Image.alpha_composite(out, vignette)


def faded(layer, alpha):
    if alpha >= 0.999:
        return layer
    out = layer.copy()
    out.putalpha(layer.getchannel("A").point(lambda v: round(v * alpha)))
    return out


def ramp(t, a, b):
    return min(max((t - a) / (b - a), 0.0), 1.0)


def logo_reveal(frame, t, sec):
    """Section 0: the stacked logo eases in over a dark shot, landing with the first downbeat."""
    frame = Image.blend(frame, Image.new("RGB", (W, H), INK), 0.72).convert("RGBA")
    logo = sec.layers["logo"]
    a = ease(ramp(t, 0.15, 1.3))
    s = 0.9 + 0.1 * ease(ramp(t, 0.15, 1.6))
    lw, lh = round(logo.width * s), round(logo.height * s)
    im = faded(logo.resize((lw, lh), Image.Resampling.LANCZOS), a)
    frame.alpha_composite(im, ((W - lw) // 2, (H - lh) // 2 - 40))
    tag = faded(sec.layers["tag"], ease(ramp(t, music.BAR, music.BAR + 0.8)))
    frame.alpha_composite(tag)
    return frame


def cta(frame, t, sec):
    """Last section: blurred shot, logo, the Discord and the website."""
    frame = frame.filter(ImageFilter.GaussianBlur(14))
    frame = Image.blend(frame, Image.new("RGB", (W, H), PEN), 0.4)
    frame = Image.blend(frame, Image.new("RGB", (W, H), INK), 0.5).convert("RGBA")
    local = t - sec.start
    frame.alpha_composite(faded(sec.layers["cta"], ease(ramp(local, 0.0, 0.6))))
    # Fade to black over the last 1.2 s.
    out = ramp(t, sec.end - 1.2, sec.end - 0.1)
    if out > 0:
        frame = Image.blend(frame, Image.new("RGBA", (W, H), (0, 0, 0, 255)), out)
    return frame


def cta_layer():
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    logo, pad = with_glow(svg_png("logo-stacked", 9), 18)
    top = 120
    layer.alpha_composite(logo, ((W - logo.width) // 2, top - pad))
    y = top + logo.height - 2 * pad + 50
    text(d, (W / 2, y), "Season I. Join the Discord.", display(72), PAPER, anchor="mt")
    y += 110
    text(d, (W / 2, y), DISCORD, mono(50), GOLD, anchor="mt")
    y += 80
    text(d, (W / 2, y), ADDRESS, mono(38), SOFT, anchor="mt")
    text(
        d,
        (W / 2, H - 50),
        "Minecraft Java Edition with mods. Not an official Minecraft product.",
        body(24),
        (170, 176, 186),
        anchor="mb",
    )
    return layer


def prepare():
    t = 0.0
    for sec in SECTIONS:
        sec.start = t
        t += sec.bars * music.BAR
        if sec.headline:
            sec.layers["card"] = card_layer(sec)
        if sec.clip:
            sec.layers["clip"] = Clip(*sec.clip)
    first, last = SECTIONS[0], SECTIONS[-1]
    logo, pad = with_glow(svg_png("logo-stacked", 11), 22)
    first.layers["logo"] = logo
    tag = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    text(
        ImageDraw.Draw(tag),
        (W / 2, H - 170),
        TAGLINE,
        display(56),
        PAPER,
        anchor="mt",
    )
    first.layers["tag"] = tag
    last.layers["cta"] = cta_layer()
    return t


def section_frame(sec, t, shared):
    u = (t - sec.start) / (sec.end - sec.start)
    # Sections with two shots switch halfway, with a short crossfade.
    if sec.clip:
        frame = sec.layers["clip"].frame(t - sec.start)
    elif len(sec.shots) == 1:
        name, zoom, c0, c1 = sec.shots[0]
        frame = pan(name, zoom, c0, c1, u)
    else:
        half = 0.5
        mix = ramp(u, half - 0.05, half + 0.05)
        a = pan(*sec.shots[0], u / half) if mix < 1 else None
        b = pan(*sec.shots[1], (u - half) / half) if mix > 0 else None
        frame = a if b is None else b if a is None else Image.blend(a, b, mix)
    if sec is SECTIONS[0]:
        return logo_reveal(frame, t, sec)
    if sec is SECTIONS[-1]:
        return cta(frame, t, sec)
    frame = frame.convert("RGBA")
    frame.alpha_composite(shared["legibility"])
    frame.alpha_composite(shared["bug"])
    local = t - sec.start
    card = sec.layers["card"]
    a = ease(ramp(local, 0.25, 0.85)) * (1 - ease(ramp(local, SECTION - 0.55, SECTION - 0.15)))
    if a > 0:
        rise = round(24 * (1 - ease(ramp(local, 0.25, 0.95))))
        shifted = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        shifted.alpha_composite(faded(card, a), (0, rise))
        frame.alpha_composite(shifted)
    return frame


def frame_at(t, shared):
    i = max(k for k, s in enumerate(SECTIONS) if s.start <= t or k == 0)
    sec = SECTIONS[i]
    img = section_frame(sec, t, shared)
    # Crossfade into the next section across its downbeat.
    if i + 1 < len(SECTIONS) and t > sec.end - FADE / 2:
        nxt = section_frame(SECTIONS[i + 1], t, shared)
        img = Image.blend(img, nxt, ramp(t, sec.end - FADE / 2, sec.end + FADE / 2))
    elif i > 0 and t < sec.start + FADE / 2:
        prev = section_frame(SECTIONS[i - 1], t, shared)
        img = Image.blend(prev, img, ramp(t, sec.start - FADE / 2, sec.start + FADE / 2))
    return img.convert("RGB")


def close_clips():
    for sec in SECTIONS:
        if sec.clip:
            sec.layers["clip"].close()


def main():
    total = prepare()
    shared = {"legibility": legibility_layer(), "bug": bug_layer()}
    OUT.mkdir(parents=True, exist_ok=True)
    if "--preview" in sys.argv:
        thumbs = [frame_at(s.start + 2.4, shared).resize((640, 360)) for s in SECTIONS]
        sheet = Image.new("RGB", (640 * 3, 360 * ((len(thumbs) + 2) // 3)))
        for k, im in enumerate(thumbs):
            sheet.paste(im, ((k % 3) * 640, (k // 3) * 360))
        close_clips()
        sheet.save(OUT / "trailer-preview.jpg", quality=88)
        print("wrote", OUT / "trailer-preview.jpg")
        return
    wav = OUT / "trailer-music.wav"
    music.write(wav, music.render())
    mp4 = OUT / "monkey-smp-trailer-1080p.mp4"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart", str(mp4),
    ]  # fmt: skip
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = round(total * FPS)
    for n in range(frames):
        proc.stdin.write(frame_at(n / FPS, shared).tobytes())
        if n % FPS == 0:
            print(f"\r{n / FPS:5.1f} / {total:.1f} s", end="", flush=True)
    proc.stdin.close()
    close_clips()
    if proc.wait():
        sys.exit("ffmpeg failed")
    print("\nwrote", mp4)


if __name__ == "__main__":
    main()
