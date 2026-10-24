"""Synthesises the trailer's music from scratch (numpy + scipy): no samples, no third-party audio.

    python marketing/music.py [out.wav]

100 BPM in A minor (Am F C G), 25 bars = 60 s, laid out to match trailer.py's two-bar sections:
bars 0-1 pad and arp alone, drums in from bar 2, 16th hats from bar 12 (where the event footage
starts), a snare roll and riser in the bar before the call to action, an impact on it (bar 22), then
the pad rings out.
"""

import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
BPM = 100
BEAT = 60 / BPM
BAR = 4 * BEAT
BARS = 25
CTA = BARS - 3  # the call to action's first bar: the impact lands here
LIFT = 12  # the event footage starts here, and the hats double
LENGTH = BARS * BAR
CHORDS = [  # (bass root, pad voicing) as MIDI notes
    (45, [57, 60, 64, 69]),  # Am
    (41, [57, 60, 65, 69]),  # F
    (48, [55, 60, 64, 67]),  # C
    (43, [55, 59, 62, 67]),  # G
]
rng = np.random.default_rng(26)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def t_of(seconds):
    return np.arange(int(seconds * SR)) / SR


def saw(freq, seconds, rolloff=8.0, detune=0.0):
    """Band-limited saw by additive synthesis; `rolloff` (in harmonics) darkens it like a low-pass."""
    t = t_of(seconds)
    out = np.zeros_like(t)
    f = freq * (1 + detune)
    n = 1
    while n * f < SR / 2 and n < 40:
        out += np.sin(2 * np.pi * n * f * t + n) / n * np.exp(-n / rolloff)
        n += 1
    return out


def env(n, attack, release, total):
    e = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[max(0, int(total * SR) - r) :] *= np.linspace(1, 0, n - max(0, int(total * SR) - r))
    return e


def lowpass(x, cutoff, order=2):
    return sosfilt(butter(order, cutoff, "low", fs=SR, output="sos"), x)


def highpass(x, cutoff, order=2):
    return sosfilt(butter(order, cutoff, "high", fs=SR, output="sos"), x)


def kick():
    t = t_of(0.45)
    freq = 45 + 95 * np.exp(-t * 28)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 7)
    click = highpass(rng.standard_normal(len(t)), 2000) * np.exp(-t * 300) * 0.3
    return np.tanh(1.6 * (body + click))


def snare():
    t = t_of(0.3)
    noise = highpass(rng.standard_normal(len(t)), 1200) * np.exp(-t * 18)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 35)
    return 0.55 * noise + 0.5 * tone


def hat(open_=False):
    t = t_of(0.25 if open_ else 0.06)
    return highpass(rng.standard_normal(len(t)), 7000, 4) * np.exp(-t * (14 if open_ else 70)) * 0.35


def crash():
    t = t_of(2.5)
    return highpass(rng.standard_normal(len(t)), 4000, 2) * np.exp(-t * 1.6) * 0.5


def boom():
    t = t_of(2.0)
    freq = 38 + 60 * np.exp(-t * 6)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 1.8)


def pluck(midi, seconds=0.5):
    f = hz(midi)
    t = t_of(seconds)
    x = saw(f, seconds, rolloff=5) + 0.5 * np.sign(np.sin(2 * np.pi * f * t)) * 0.3
    return lowpass(x, 3500) * np.exp(-t * 9)


def place(track, clip, at, gain=1.0):
    i = int(at * SR)
    j = min(len(track), i + len(clip))
    if i < len(track):
        track[i:j] += gain * clip[: j - i]


def reverb(x, seconds=1.6, mix=0.28):
    t = t_of(seconds)
    ir = rng.standard_normal(len(t)) * np.exp(-t * 4.0)
    ir = lowpass(ir, 6000)
    wet = fftconvolve(x, ir)[: len(x)]
    wet *= np.max(np.abs(x)) / (np.max(np.abs(wet)) + 1e-9)
    return (1 - mix) * x + mix * wet


def render():
    n = int(LENGTH * SR) + SR
    drums = np.zeros(n)
    bass = np.zeros(n)
    pad = np.zeros(n)
    arp = np.zeros(n)
    fx = np.zeros(n)
    k, s = kick(), snare()

    for bar in range(BARS):
        root, voicing = CHORDS[bar % 4]
        start = bar * BAR
        full = 2 <= bar < CTA + 2
        # Pad: detuned saws, slow swell; the last bar rings out.
        length = BAR * (2.5 if bar == BARS - 1 else 1.05)
        chord = sum(saw(hz(m), length, rolloff=4, detune=d) for m in voicing for d in (-0.004, 0.0, 0.004))
        chord *= env(len(chord), 0.35, 0.4, length)
        place(pad, chord, start, 0.06 if bar < CTA else 0.08)
        # Arp: chord tones up an octave in 16ths, quieter in the intro.
        if bar < CTA + 2:
            pattern = [0, 1, 2, 3, 2, 1, 2, 3]
            for step in range(16):
                note = voicing[pattern[step % 8]] + 12
                place(arp, pluck(note), start + step * BEAT / 4, 0.16 if full else 0.1)
        if not full:
            continue
        # Drums: kick on 1 and 3 (plus the "and" of 4), snare on 2 and 4, hats in 8ths.
        for beat in range(4):
            at = start + beat * BEAT
            if beat in (0, 2):
                place(drums, k, at, 0.9)
            else:
                place(drums, s, at, 0.55)
            place(drums, hat(), at + BEAT / 2, 1.0)
            place(drums, hat(), at, 0.6)
            if LIFT <= bar < CTA:
                for q in (0.25, 0.75):
                    place(drums, hat(), at + q * BEAT, 0.35)
        place(drums, k, start + 3.5 * BEAT, 0.6)
        if bar % 4 == 3:
            place(drums, hat(open_=True), start + 3.5 * BEAT, 1.0)
        # Bass: root in 8ths, octave jump on the last eighth.
        for eighth in range(8):
            note = root + (12 if eighth == 7 else 0)
            b = saw(hz(note), BEAT / 2, rolloff=6)
            b = lowpass(b, 900) * env(len(b), 0.005, 0.06, BEAT / 2)
            place(bass, b, start + eighth * BEAT / 2, 0.32)

    # Build into the call to action: snare roll and noise riser through the bar before it, impact on it.
    roll_start = (CTA - 1) * BAR
    for i in range(16):
        place(drums, s, roll_start + i * BEAT / 4, 0.25 + 0.35 * i / 15)
    riser_t = t_of(BAR)
    riser = highpass(rng.standard_normal(len(riser_t)), 3000) * (riser_t / BAR) ** 2 * 0.3
    place(fx, riser, roll_start)
    place(fx, crash(), CTA * BAR, 0.8)
    place(fx, boom(), CTA * BAR, 0.9)
    place(fx, crash(), LIFT * BAR, 0.45)
    # The opening hit, when the logo lands.
    place(fx, boom(), 0.0, 0.5)
    place(fx, crash(), BAR, 0.35)

    mix = reverb(drums, 0.8, 0.12) * 0.9 + bass + reverb(pad, 2.2, 0.35) + reverb(arp, 1.4, 0.3) + reverb(fx, 1.8, 0.25)
    mix = np.tanh(mix / np.max(np.abs(mix)) * 1.2)  # gentle saturation, not a brick wall
    mix = mix[: int(LENGTH * SR)]
    fade = int(1.5 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade) ** 2
    mix *= 0.89 / np.max(np.abs(mix))  # about -1 dBFS
    # A little width: delay one side by 8 ms on the pad-heavy high end.
    hi = highpass(mix, 2500)
    d = int(0.008 * SR)
    left = mix
    right = mix - hi + np.concatenate([np.zeros(d), hi[:-d]])
    return np.stack([left, right], axis=1)


def write(path, audio):
    pcm = np.int16(np.clip(audio, -1, 1) * 32767)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else r"D:\DevData\monkey-smp-marketing\out\trailer-music.wav")
    out.parent.mkdir(parents=True, exist_ok=True)
    write(out, render())
    print("wrote", out, f"{LENGTH:.1f} s")
