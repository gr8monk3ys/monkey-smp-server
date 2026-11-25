# Monkey SMP: brand direction for the Season 1 relaunch

Draft for Lorenzo, 25 Nov 2026. Season 1 opens Saturday 6 Feb 2027. The name stays Monkey SMP.

## The one line

**Survive, trade, steal hearts.**

Everything we make should say, in this order: it's **free**, it's an **economy SMP with lifesteal**, it runs on
**Java and Bedrock with no mods**, and it comes in **seasons** with a real ending.

## Who it's for

- **The DonutSMP crowd who want a fresh start.** They know shops, auction houses and base raids, and they're tired of
  joining a world where everyone is already rich. Season 1 means everyone starts on the same day.
- **Phone and console players.** Most of the big SMPs are Java-first. Bedrock from day one is a reason to pick us.
- **Clip watchers.** People who found lifesteal through TikTok and Shorts and want to be in the clip, not watch it.

## Tone

A cheeky jungle thief. Monkeys steal things; so do you, one heart at a time. The voice is:

- **Short.** Three-word lines beat paragraphs. "Free. No mods. Phone or PC."
- **Playful, never cruel.** We joke about losing hearts, never about players. No slurs, no edgelord stuff: many players
  are under 18 and Mojang's guidelines want all-ages.
- **Straight about money.** Free to join, the store is cosmetic, nothing gives an edge. Say it plainly every time it
  comes up, because players have been burned by pay-to-win servers.
- **Concrete.** Name the thing: "auction house", "10-week season", "48-hour PvP grace". Avoid "epic", "insane",
  "the best server ever".

Words we use: hearts, steal, season, jungle, shop, auction house, safe zone, finale, Founder.
Words we avoid: "pay to win" anything, "ranks with perks", "official", "Minecraft" as part of our name.

## Taglines

Primary: **Survive, trade, steal hearts.**

For different places:

| Where | Line |
| --- | --- |
| Server list headline | Free economy lifesteal SMP. Java and Bedrock, no mods. |
| TikTok and Shorts hook | Monkey see, monkey steal. |
| Trailer end card | Season 1. Saturday 6 February. Free. |
| Bedrock players | Phone, console or PC. Same jungle. |
| Fresh-start pitch | Everyone starts broke on day one. |
| Seasons | 10 weeks. One finale. Then the jungle grows back. |
| Store, honestly | Look rich. Can't buy your way to rich. |
| Discord welcome | Welcome to the jungle. Mind your hearts. |

## Look

Keep what players already recognise and add one new colour for the new game.

- **Keep the pixel jungle.** The canopy, the flat block colours with stepped corners, Pixelify Sans for headings and
  Atkinson Hyperlegible for reading (DESIGN.md has the full system). It already looks like our own thing and not a
  template.
- **Gold means money and action.** Coins, the shop, every button. It was already the action colour, and on an economy
  server it now means money too.
- **New: heart red, for lifesteal only.** `#f05a4f`, with ink `#1a1f23` text on it (4.98:1). Use it for hearts, kills
  and the PvP parts of a page or a thumbnail, and nowhere else, so red always means "you can lose a heart here".
  Against the page green `#133f2b` it is 3.5:1, enough for icons and fills but not for small text.

| Name | Hex | Use |
| --- | --- | --- |
| Ground | `#133f2b` | Page background |
| Leaf | `#184e35` / `#1f6142` / `#2b7a4b` | Panels, the canopy |
| Shade | `#0e3122` | Footer, counters |
| Bone | `#f9f8f5` / `#e2dcce` | Text |
| Gold | `#e8b23a` (hover `#f3cb6b`) | Money, buttons, the SMP in the logo |
| **Heart** | **`#f05a4f`** | **Hearts and PvP only** |
| Stone | `#b6bcad` | Reference: the address plaque, rule tablets |
| Ink | `#1a1f23` | Outlines, text on gold, stone and heart |

## Logo brief

The current pixel monkey and MONKEY SMP wordmark are made by `marketing/logo.py` (a 16 x 16 grid and pixel
letters). Refresh, don't replace:

1. **The monkey holds a stolen heart.** A 4 to 5 pixel heart in heart red in one hand, a sly grin. This is the
   relaunch's whole idea in one picture.
2. **The wordmark stays.** MONKEY in bone, SMP in gold.
3. **A season badge.** A small stone tab reading `S1` that sits on the mark's corner, swapped each season. It lets the
   server icon and thumbnails show which season is live.
4. **Sizes it must work at:** 64 x 64 server icon (the most-seen version, in every player's server list), 512 square
   avatar for Discord, TikTok and YouTube, the wide and stacked lockups, a 468 x 60 list banner, a 960 x 540 Discord
   banner, a 1920 x 1080 trailer end card, and a 1280 x 720 YouTube thumbnail frame.
5. **Rules:** no Minecraft logo, no Mojang art, no creeper or other Mojang character, nothing cape-shaped (Mojang's
   usage guidelines), and nothing that suggests the server is official.

Who makes it: a change to `marketing/logo.py` and a re-run of `marketing/build.py`, which writes every PNG and the
banners. That folder isn't part of this pass, so it is a follow-up.

## Before launch, only Lorenzo can decide

- **The handle.** `@monkeysmp` everywhere if it's free on TikTok, YouTube, Instagram and X, otherwise one variant
  used everywhere. Check each before announcing.
- **A short domain.** The site and the Java address use `monkeysmp.lscaturchio.xyz`. A short domain of its own reads
  better on a trailer end card and in a TikTok caption. It costs money, so it's your call; everything here works with
  the current name too.
- **The Bedrock address.** Bedrock can't follow the SRV record Java uses, so Bedrock players need a name that points
  straight at the server, plus port 19132. The site shows `play.monkeysmp.lscaturchio.xyz` and port `19132`; the
  platform work confirms both.
