# Product

<!-- impeccable:product-schema 1 -->

This record is for the public website in `site/` (monkeysmp.lscaturchio.xyz). The rest of the repo is the
server package; its own docs are `README.md`, `docs/` and `GLOSSARY.md`.

## Platform

web

## Users

- **Newcomers first** (owner, 2026-10-26): Minecraft Java players who arrive from creator videos, TikTok and
  server lists (each source has its own join address, `docs/PROMOTION.md`), often on a phone, deciding whether
  this server is worth $5 a month and an evening's install. Many are under 18 (the server and Discord are
  all-ages; the FAQ asks them to check with a parent before buying).
- **Members coming back**: players who already have a pass and need the server address, the current modpack,
  the rules, the live map or what changed in the last update, quickly and on any device.
- Smaller audiences with their own pages: creators looking at creator-code terms (`creators.html`), and anyone
  taking the logo and banners from the press kit.

## Product Purpose

Monkey SMP is a small, paid, whitelisted, modded Minecraft Java factions server (Fabric, Minecraft 26.3),
hosted by Diego and Lorenzo Scaturchio for a crowd that plays evenings, Pacific time, up to 30 online. The site
exists to turn a curious visitor into a player: explain what the server is, show the world, and take them
through the three steps (get a pass, install the modpack, connect). For members it is the reference for the
address, the pack, the rules and the changes. Success is a visitor who joins the Discord or gets a pass, then
connects without needing help.

## Positioning

- Factions of up to four under their own banners, alliances, protected territory (2 x 2 chunks a player) and
  contested land everywhere else, with Strength SMP (win fights and your strength grows, lose and it drains)
  as the centerpiece.
- Reworked terrain and new dungeons, mobs and magic (Tectonic, Terralith, Incendium, Endercon and others),
  proximity voice chat and a public live 3D map.
- Seasons: each season is a new world with its own rules and a twist players vote on. Season I opens
  Saturday 7 November 2026, 5 PM Pacific, everyone let in at once.
- One price to play, the same for everyone; supporter tiers are cosmetic only, and priority or reserved slots
  are never for sale. Cosmetics are earned by playing too (wardrobe skins, weekly challenges, the Founder's
  Circlet for launch weekend only, never sold).

## Operating Context

- Next.js (the same stack as lscaturchio.xyz) built as a static site with bun; every page reads in full
  without JavaScript. Deployed on Vercel from `site/` (`site/README.md`).
- `site/config.json` holds every link, the server address and the launch time. The build writes them into
  the pages, and `tools/site_links.py --built` fails when a built page drifts from it. Links keep `data-link`
  and launch times `data-launch` for that check; the page scripts (`site/src/components/`) rely on the ids
  `address`, `copy`, `countdown`, `launch-label` and `trailer`.
- While `STORE_URL` is empty, every buy button points at the Discord and the pages say passes are arranged
  there by hand; once the Tebex store opens the "open" copy shows instead.
- The modpack (`.mrpack`, about 560 MB) and the Windows installer zip are served from `site/public/pack/`,
  versioned with each release. `site/src/content/changes.mdx` gets a players' entry with each release (tests check its shape).
- Pages: `/` (the server), `/guide` (how it works: a sidebar of pages, from the first hour to commands by rank and the Discord), `/changes` (what changed), `/creators` (creator codes),
  in `site/src/app/`.

## Capabilities and Constraints

- Prices on the page: Server Pass $5 a month or $14 for 3 months; supporter tiers Ember $3, Banner $7,
  Crown $15 a month; the invite ladder (1, 3, 5, 10 friends). Refund if the pack won't run in the first
  48 hours. Running cost about $50 a month, reported monthly in the Discord.
- Needs Minecraft Java Edition on a computer (Windows, macOS or Linux) with 16 GB of RAM; no Bedrock, console
  or mobile play.
- Mojang's rules: one price for access, no paid advantages; the footer disclaimer ("Not an official Minecraft
  product...") stays on every page.
- Factual copy (rules, prices, requirements, the launch time) changes only with the owner; design work keeps it.

## Brand Commitments

- The name is Monkey SMP (players' name; internal names keep `monkey`, see `GLOSSARY.md`).
- The logo: a pixel-art monkey on a green tile beside the words MONKEY SMP (`site/public/kit/`, `site/public/favicon.svg`).
- The site gets its own identity built from the server (owner, 2026-10-26). It no longer matches
  lscaturchio.xyz's "Field Notebook" look.
- Voice: plain, direct, specific; second person; facts over hype. No exclamation marks or superlatives.

## Evidence on Hand

- Six screenshots from the server's own world, taken with the pack's shaders (`site/public/img/*-800.webp`
  and `-1600.webp`): the Painted Mountains, a Nether castle, an End citadel, a fortified village, a floating
  island, a mage tower.
- A one-minute trailer (`site/public/media/trailer-720p.mp4`, poster `trailer-poster.webp`); its event scenes are
  staged on a test server with stand-in players, and the caption says so.
- Logo, stacked logo, mark, server-list banner and Discord banner (`site/public/kit/`); the link-preview
  image `site/public/img/og.jpg`.
- Absent, never to be invented: player counts, reviews or testimonials, press, uptime figures, player names
  beyond the hosts. Season I hasn't opened yet.

## Product Principles

1. Show the world before explaining it: real screenshots and the trailer carry the pitch.
2. The way in is always one step away: the address, the pass and the pack are reachable from the first screen.
3. Every claim is true and checkable; staged footage and unopened features are labelled as such.
4. Fair is the selling point: one price, nothing that buys an edge, and the page says so plainly.
5. Members' reference material stays scannable: rules, steps and changes read in seconds on a phone.

## Accessibility & Inclusion

- An all-ages audience, many on phones: WCAG 2.2 AA contrast, real text (not text in images), keyboard and
  screen-reader use, and a layout that works from 320 px wide.
- Respect reduced motion and data saving (the trailer already stays still for both).
