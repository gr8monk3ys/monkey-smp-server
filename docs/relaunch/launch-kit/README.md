# Season 1 launch kit

Domain, social accounts, launch videos and the posting plan for the Season 1 relaunch (Saturday 6 Feb 2027, 5 PM
Pacific). Builds on the brand work in `docs/relaunch/marketing/` (PR #211).

| File | What |
| --- | --- |
| `domain.md` | Which domain to buy, where, and what it costs |
| `socials.md` | Handle check, what each sign-up needs, bios, image map, pinned posts |
| `calendar.md` | What to post where, from now to launch day |
| `recording.md` | In-game shot list, OBS and Minecraft settings, edit notes for the real trailer |

## The files

Made by `marketing/season1/` (Pillow and ffmpeg, no footage). Renders are kept out of git; the current set is in
the Claude Duet project folder `marketing/`.

- `teaser-season1-1080x1920.mp4`: 24 s vertical teaser for TikTok, Shorts and Reels, and its cover frame.
- `logo-sting-1920x1080.mp4` and `logo-sting-1080x1920.mp4`: 4 s logo sting.
- `thumbnail-template-1280x720.png`, `thumbnail-overlay-1280x720.png` (transparent, put over any screenshot) and an
  example in gold.
- `avatar-800.png`, `avatar-400.png`, and banners for YouTube, X, Twitch, Reddit and Discord.
- `announce-post-1080x1350.png` and `announce-story-1080x1920.png`.

The mark is the existing pixel monkey from `marketing/logo.py` with the brand brief's additions drawn in
`marketing/season1/art.py`: a stolen heart in heart red, a paw holding it, and a stone S1 tab. `logo.py` itself is
unchanged.

## Rebuilding

Needs Python 3.11+ with Pillow, numpy and scipy, and ffmpeg.

```sh
mkdir -p marketing/season1/fonts && cd marketing/season1/fonts
curl -L -o "PixelifySans[wght].ttf" "https://raw.githubusercontent.com/google/fonts/main/ofl/pixelifysans/PixelifySans%5Bwght%5D.ttf"
curl -LO https://raw.githubusercontent.com/google/fonts/main/ofl/atkinsonhyperlegible/AtkinsonHyperlegible-Bold.ttf
curl -LO https://raw.githubusercontent.com/google/fonts/main/ofl/atkinsonhyperlegible/AtkinsonHyperlegible-Regular.ttf
cd ../../..
python marketing/season1/kit.py                       # stills
python marketing/season1/teaser.py                    # teaser and sting (about 30 s)
python marketing/season1/teaser.py --preview          # contact sheet, one frame per section
python marketing/season1/kit.py thumb --bg shot.png --title "STEAL HEARTS" --out thumb.png
```

Addresses and the handle come from environment variables, so a new domain is a re-run, not an edit:
`MONKEY_JAVA`, `MONKEY_BEDROCK`, `MONKEY_HANDLE`. Output goes to `marketing/season1/out/` (or `MONKEY_KIT_OUT`).

## Credits and licences

- **Fonts:** Pixelify Sans (Stefie Justprince) and Atkinson Hyperlegible (Braille Institute), both SIL Open Font
  Licence 1.1, from google/fonts. Free for commercial use.
- **Music:** synthesised from scratch by `marketing/music.py` (additive saws and synthesised drums, no samples), so
  there is nothing to license and no Content ID claim to fear. If you'd rather use a trending TikTok sound, add it in
  the app; the video works without its own audio.
- **Art:** all drawn in code. No Minecraft logo, Mojang art, creeper or cape-like shapes, per Mojang's usage
  guidelines. Descriptions carry "Not an official Minecraft product".
