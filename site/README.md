# Monkey SMP site

The public site at monkeysmp.lscaturchio.xyz: what the server is, how to join, pricing and the rules (`/`), the
player guide (`/guide`), the player changelog (`/changes`) and the creator code terms (`/creators`).

## Stack

The same as lscaturchio.xyz: Next.js (App Router) with React and TypeScript, MDX for the long prose, Tailwind CSS
v4 (wired in, but nothing uses its classes yet), ESLint, and bun. It is built as a static site
(`output: "export"` in `next.config.mjs`): `bun run build` writes plain HTML, CSS and JS to `out/`, and every page
reads in full with JavaScript off. JavaScript adds the countdown, the server status, the copy button, the
trailer's autoplay and the stepped reveal of blocks as they scroll in (motion is off under reduced motion;
printing shows everything).

```sh
bun install        # once, and after package.json changes
bun dev            # http://localhost:3000, reloads as you edit
bun run build      # the site in out/ (check it with: bunx serve out)
bun run lint
bun run typecheck
```

`python tools/checks.py site` (from the repo root) runs install, lint, typecheck and build, then
`tools/site_links.py --built site/out`, which checks every built link and launch time against `config.json`. CI
runs it with the other checks.

## Where things live

| What | Where |
| --- | --- |
| Links, the server address, the launch time | `config.json` (below) |
| The look | `src/app/style.css`, the one stylesheet (`DESIGN.md` at the repo root says why it looks as it does). `/guide` and `/changes` add `src/app/guide/guide.css` and `src/app/changes/changes.css` |
| The front page's copy | `src/app/page.tsx`; its lists (the world, gallery, pass, supporter tiers, invite ladder, FAQ) in `src/content/front.tsx` |
| The rules (front page) and creator terms | `src/content/rules.tsx` |
| The guide | A docs layout: `src/app/guide/layout.tsx` puts the sidebar (`src/components/guide-nav.tsx`) beside each page under `src/app/guide/`. The pages, their order and sidebar headings are in `src/content/guide/pages.ts`; the prose in `src/content/guide/*.mdx`, the week in `week.ts`, commands by rank in `commands.tsx` (one page per rank) |
| The player changelog | `src/content/changes.mdx`, newest first (docs/ADMIN.md, "Telling players what changed") |
| The creator code page | `src/app/creators/page.tsx` |
| The header and footer | `src/components/chrome.tsx`. The footer adds "Season I Wrapped" (`src/lib/wrapped.ts`) once a season's `public/wrapped/season-<n>/index.html` is there at build time |
| The server status (front page under the ways in, and one line on `/guide`) | `src/components/status.tsx`: it fetches `STATUS_URL` in the browser every 2 minutes and shows online or offline, the player count, the next event and the border. The page is built with a quiet fallback for the season's phase, which also shows without JavaScript and when the file is missing, more than 10 minutes old, or blocked; every state takes the same room |
| Search and link previews | Each page's title, description and canonical address through `pageMetadata` in `src/lib/seo.ts`, which also holds the structured data (the site, Season I's launch as an event, the guide's breadcrumbs); `src/app/sitemap.ts`, `robots.ts` and `manifest.ts` build `/sitemap.xml`, `/robots.txt` and `/manifest.webmanifest`. A new page gets its own `pageMetadata` and a line in `sitemap.ts` (guide pages come from `pages.ts`); `tools/site_links.py --built` fails the build check when a built page is missing from `sitemap.xml` |
| The page for a missing address | `src/app/not-found.tsx` (built as `out/404.html`) |
| Images, fonts, video, the press kit, the modpack | `public/` (served as they are: `public/img/og.jpg` is `/img/og.jpg`) |
| Season Wrapped | `public/wrapped/season-<n>/`, made by `tools/wrapped.py` (docs/SEASONS.md, "Ending a season"): build it again rather than edit it. Its pages load `public/wrapped/site.css`, a copy of `src/app/style.css` that `python tools/site_links.py` refreshes (validate.py fails while it is stale) |

## config.json

The one place the site's links, the server address and the launch time live. The site reads it when it is
built and writes them into the pages; `tools/site_links.py` checks it from the Python side (validate.py runs it),
and `tools/rules.py` and `tools/season_calendar.py` have tests that it agrees with them. An empty URL makes its
buttons point at the Discord with a "Coming soon" title.

| Key | What |
| --- | --- |
| `ADDRESS` | The Minecraft server address, shown on the copy plaque and in the join steps |
| `DISCORD_INVITE` | The Discord invite |
| `STORE_URL` | The Tebex webstore (passes and supporter tiers). Fill it in only once the store can take payments and run its commands on the server (docs/LIVE.md, "The store"). While it is empty, the pages say passes are arranged in the Discord; once it is set, they say what the store does |
| `MODPACK_URL` | The player modpack. Until the Modrinth project is up, the site serves the release's own `.mrpack` from `public/pack/` (docs/MAINTAINING.md, "Releasing"), and validate.py checks it is the version the manifest pins |
| `INSTALLER_URL` | The player zip: the installer for the regular Minecraft Launcher on Windows, plus the same `.mrpack`, also in `public/pack/` |
| `MAP_URL` | The live map (BlueMap behind Caddy on the VPS, docs/LIVE.md), open to everyone |
| `STATUS_URL` | The server's status file (`tools/status.py`), served beside the live map with a short cache and an allow-origin header (docs/LIVE.md, "The website's status"). Empty: no status block |
| `LAUNCH_AT` | When the season opens: ISO 8601 with its offset (`2026-11-08T01:00:00Z` is Saturday 7 November 2026, 5 PM Pacific). The pages spell it out in Pacific and Eastern time; the countdown adds the visitor's own time, then says the season is live once it has passed (docs/LAUNCH.md). It must match `tools/season_calendar.py`'s launch |

A change to it is a commit like any other: the next deploy builds it into the pages.

## Deploy

A Vercel project on this repo with **Root Directory** `site` and the domain `monkeysmp.lscaturchio.xyz`.
`vercel.json` sets the framework to Next.js (Vercel installs with bun, since `bun.lock` is here, and serves
`out/`), turns on clean URLs (`/guide`, not `/guide.html`; an old `.html` link redirects), and skips every build
except a production push that changes `site/` (exit 0 skips, 1 builds), so commits to the rest of the repo cost
no builds. The Minecraft address uses the SRV record in docs/LIVE.md, so the website and the game share the name.
