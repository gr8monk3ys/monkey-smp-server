"""Season Wrapped: at a season's end, a page for every player about their season, for the site.

    python tools/wrapped.py start WORLD --out START.json
        right after the launch (`function realms:rules/launch`): where everyone's counts stood, so test play
        before it and what earlier seasons carried in don't count as this season's
    python tools/wrapped.py build WORLD --season 1 --standings DIR --start START.json --out site/wrapped/season-1
        [--opt-out FILE]
        after the finale: one page per player, an index, and the skins' pictures

What players see (docs/SEASONS.md, "Ending a season"): monkeysmp.lscaturchio.xyz/wrapped/season-1/ lists everyone
who played, and each player's page has their hours and days played, PvP kills, weekly challenges done and
events attended this season, their faction's best weekly rank, their Server Firsts, and the wardrobe skins they
hold, rarest first (how many of the season's players hold each, and which are new this season). A shared link
shows a preview card in Discord with the player's own line ("84 hours over 31 days, 12 PvP kills...").

Where it comes from, all read, nothing changed:
  WORLD/data/minecraft/scoreboard.dat        rw.play (play time, ticks), rw.days, rw.events, rw.challenges,
                                              st.kills (PvP kills outside the arena) and every skin's unlock score
  WORLD/data/realms/command_storage.dat      the Server Firsts (tools/firsts.py's holders())
  DIR/weeks/*.json                           the weekly standings' closed weeks (tools/standings.py close): each
                                              faction's rank and members that week
  START.json                                 the same scores at the launch, from `start`
A season's count is the end's minus the launch's (a score below where it started was reset, so all of it is
new). Without START.json Season I counts from zero (staff test play before the launch then counts) and a later
season can't be made, since its carried totals would read as one season's. Skins from the pass and supporter
tiers are left out: the page is about play, and nobody's spending is shown.

Players who don't want a page are named in FILE (one name a line, # for a comment): no page, not on the
index, and their name is withheld where a Server First is listed; their play still counts in the totals and
in how rare a skin is. Pages are marked noindex, so search engines leave them out; a link still works.
The pages use the site's own style.css and fonts from two folders up, so --out is site/wrapped/season-<n>
(served at /wrapped/season-<n>/). A re-run replaces what an earlier run wrote there and nothing else.
Stdlib only, and Python 3.10 or newer, so the VPS runs it straight from the checkout.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import firsts
import saved_world
import season_calendar
import site_links
import wardrobe
from challenges import LAUNCHED
from firsts import First
from standings import BOUNTY, KILLS, folded, gained

SITE = "https://monkeysmp.lscaturchio.xyz"    # site/index.html's og:url
ROOT = "../../"                              # from site/wrapped/season-<n>/ back to site/
GENERATOR = "tools/wrapped.py"               # in every page's generator meta: a re-run may replace those
FINALE_WEEK = 11                             # docs/SEASONS.md: the finale is week 11, the world locks after it
PLAY, DAYS, EVENTS, CHALLENGES = "rw.play", "rw.days", "rw.events", "rw.challenges"
TICKS_AN_HOUR = 72000
MIN_TICKS = 10 * 60 * 20                     # 10 minutes this season: less gets no page
COUNTED = (PLAY, DAYS, EVENTS, CHALLENGES, KILLS, BOUNTY)
NAME = re.compile(r"[A-Za-z0-9_]{1,16}")     # a Java name; anything else gets a made-up file name
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


def season_name(n: int) -> str:
    return ROMAN[n - 1] if 1 <= n <= len(ROMAN) else str(n)


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else many or one + 's'}"


def week_words(week: int | None) -> str:
    return "" if week is None else "the launch weekend" if week == 0 else f"week {week}"


# ---------------------------------------------------------------- reading


def scores(world: Path) -> dict[str, dict[str, int]]:
    board = saved_world.scoreboard(world)
    if board is None:
        raise SystemExit(f"no scoreboard at {saved_world.scoreboard_path(world)}: give the world folder (server/world)")
    return board.scores


def kept(board: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    """The scores a snapshot keeps: every rw.* and st.* score of a player (not the # holders)."""
    return {o: {n: s for n, s in sorted(holders.items()) if not n.startswith("#")}
            for o, holders in sorted(board.items()) if o.startswith(("rw.", "st."))}


@dataclass
class Start:
    taken: dt.datetime
    scores: dict[str, dict[str, int]]


def read_start(path: Path) -> Start:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Start(dt.datetime.fromisoformat(data["taken"]),
                     {o: {n: int(s) for n, s in h.items()} for o, h in data["scores"].items()})
    except FileNotFoundError:
        raise SystemExit(f"no {path}: give the file `wrapped.py start` wrote at the launch") from None
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise SystemExit(f"{path} is not a file `wrapped.py start` wrote ({type(e).__name__}: {e})") from None


def closed_weeks(state: Path, season: season_calendar.Season) -> list[dict]:
    """The standings' closed weeks that ended in the season: after the launch, before the week after the finale."""
    where = state / "weeks"
    if not where.is_dir():
        warn(f"no {where}: no weekly ranks (give the standings folder, STANDINGS_DIR)")
        return []
    found = []
    for path in sorted(where.glob("*.json")):
        try:
            week = json.loads(path.read_text(encoding="utf-8"))
            end = dt.datetime.fromisoformat(week["end"])
            rows = [r for r in week.get("rows", []) if isinstance(r, dict) and isinstance(r.get("rank"), int)]
            ended_in_season = season.launch < end < season.week_begins(FINALE_WEEK + 1)   # TypeError: no offset
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            warn(f"{path} left out: not a closed week ({type(e).__name__})")
            continue
        if ended_in_season:
            found.append({"end": end, "rows": rows})
    return found


def read_opt_out(path: Path | None) -> set[str]:
    if path is None:
        return set()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"no {path}: the opt-out list (one name a line; an empty file is fine)") from None
    return {line.split("#")[0].strip().casefold() for line in text.splitlines()} - {""}


# ---------------------------------------------------------------- the cards


@dataclass(frozen=True)
class Rank:
    rank: int
    of: int          # factions ranked that week
    week: int        # the season week it closed in
    faction: str


@dataclass(frozen=True)
class Skin:
    id: str
    name: str
    kind: str        # blade or helm
    holders: int     # the season's players who hold it
    new: bool        # unlocked this season (False when the start is unknown)


@dataclass
class Card:
    name: str
    slug: str
    ticks: int
    days: int
    kills: int
    challenges: int
    events: int
    bounties: int
    faction: str = ""                       # the last faction the standings had them in
    best: Rank | None = None
    firsts: list[First] = field(default_factory=list)
    skins: list[Skin] = field(default_factory=list)

    @property
    def hours(self) -> str:
        h = self.ticks / TICKS_AN_HOUR
        return f"{h:.0f}" if h >= 10 else f"{h:.1f}"


def slug(name: str) -> str:
    """A page's file name: the name in lower case (Java names are unique that way), else a stand-in."""
    if NAME.fullmatch(name):
        return name.lower()
    return "player-" + "".join(f"{ord(c):x}" for c in name)[:24]


def faction_ranks(name: str, weeks: list[dict], season: season_calendar.Season) -> tuple[str, Rank | None]:
    """Their last faction, and their faction's best rank in a week they were in it (an earlier week wins a tie)."""
    who, best, last = name.casefold(), None, ""
    for week in weeks:
        for row in week["rows"]:
            if who in {str(m).casefold() for m in row.get("members", [])}:
                rank = Rank(row["rank"], len(week["rows"]), season.week_at(week["end"]),
                            str(row.get("name", "")))
                last = rank.faction
                if rank.rank > 0 and (best is None or rank.rank < best.rank):
                    best = rank
    return last, best


def skins_held(names: list[str], end: dict, begin: dict | None) -> dict[str, list[Skin]]:
    """Each player's skins, rarest first: those their end scores unlock, not the pass's or supporter tiers'."""
    def holds(board, name, unlock):
        objective, n = unlock
        return board.get(objective, {}).get(name, 0) >= n
    out: dict[str, list[Skin]] = {n: [] for n in names}
    for _, kind, s in wardrobe.skins():
        if s["unlock"][0] in wardrobe.SOLD:
            continue
        have = [n for n in names if holds(end, n, s["unlock"])]
        for n in have:
            out[n].append(Skin(s["id"], s["name"], kind, len(have),
                               begin is not None and not holds(begin, n, s["unlock"])))
    for held in out.values():
        held.sort(key=lambda k: (k.holders, k.name.casefold()))
    return out


def cards(world: Path, start: Start | None, weeks: list[dict], season: season_calendar.Season) -> list[Card]:
    """A card for everyone who played at least MIN_TICKS this season, by name."""
    end = scores(world)
    begin = start.scores if start else {}
    # Staff type a bounty hunter's name by hand, so its case may differ (as in tools/standings.py).
    lower = {BOUNTY: (folded(end.get(BOUNTY, {})), folded(begin.get(BOUNTY, {})))}

    def this_season(objective: str, name: str) -> int:
        if objective in lower:
            now, then = lower[objective]
            return gained(now.get(name.lower(), 0), then.get(name.lower(), 0))
        return gained(end.get(objective, {}).get(name, 0), begin.get(objective, {}).get(name, 0))
    names = sorted((n for n in end.get(PLAY, {}) if not n.startswith("#") and this_season(PLAY, n) >= MIN_TICKS),
                   key=str.casefold)
    claimed = firsts.holders(world)
    held = skins_held(names, end, start.scores if start else None)
    out = []
    for n in names:
        card = Card(n, slug(n), this_season(PLAY, n), this_season(DAYS, n), this_season(KILLS, n),
                    this_season(CHALLENGES, n), this_season(EVENTS, n), this_season(BOUNTY, n), skins=held[n])
        card.faction, card.best = faction_ranks(n, weeks, season)
        card.firsts = [f for f in claimed if f.player.casefold() == n.casefold()]
        out.append(card)
    return out


# ---------------------------------------------------------------- the pages


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def summary(c: Card) -> str:
    """The card's line, for the link preview."""
    parts = [f"{c.hours} hours over {plural(c.days, 'day')}", plural(c.kills, "PvP kill")]
    if c.firsts:
        parts.append(plural(len(c.firsts), "Server First"))
    if c.challenges:
        parts.append(plural(c.challenges, "weekly challenge"))
    return ", ".join(parts) + "."


def head(title: str, description: str, url: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="generator" content="{GENERATOR}">
  <meta name="robots" content="noindex">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(url)}">
  <meta property="og:image" content="{SITE}/img/og.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="The Monkey SMP logo over a Nether castle.">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="theme-color" content="#1f6142">
  <link rel="icon" href="{ROOT}favicon.svg" type="image/svg+xml">
  <link rel="preload" href="{ROOT}fonts/pixelify-sans-monkey-bold.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{ROOT}fonts/atkinson-next-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="{ROOT}style.css">
  <link rel="stylesheet" href="wrapped.css">
</head>
<body class="wrapped">
  <a class="skip" href="#main">Skip to content</a>
  <header class="canopy">
    <a class="brand" href="{ROOT}"><img src="{ROOT}kit/logo-1392w.png" alt="Monkey SMP" width="261" height="48"></a>
    <nav aria-label="Site">
      <a href="./">Everyone</a>
      <a href="{ROOT}#rules">Rules</a>
      <a href="{ROOT}changes.html">What changed</a>
    </nav>
  </header>

  <main id="main">
"""


def foot(links: dict[str, str], made: dt.date) -> str:
    def link(key: str, label: str) -> str:
        url = links.get(key) or links.get("DISCORD_INVITE")
        return f' &middot; <a href="{esc(url)}">{label}</a>' if url else ""
    return f"""  </main>

  <footer class="crown">
    <p><a href="{ROOT}">Monkey SMP</a>{link("DISCORD_INVITE", "Discord")}{link("MAP_URL", "Live map")}</p>
    <p class="small">Made from the server's saved world on {made.day} {season_calendar.MONTHS[made.month - 1]} \
{made.year}. Ask staff in the Discord to take your page down.</p>
    <p class="small">Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.</p>
  </footer>
</body>
</html>
"""


def figures(items: list[tuple[str, str]]) -> str:
    cells = "".join(f'\n        <li><b>{esc(value)}</b> <span>{esc(label)}</span></li>' for value, label in items)
    return f'      <ul class="figures">{cells}\n      </ul>\n'


def season_span(season: season_calendar.Season) -> str:
    first, last = season.launch_day, season.saturday(FINALE_WEEK)
    return (f"{first.day} {season_calendar.MONTHS[first.month - 1]} {first.year} to "
            f"{last.day} {season_calendar.MONTHS[last.month - 1]} {last.year}")


def first_words(f: First) -> str:
    """'week 3, the season's 7th first'."""
    when = week_words(f.week) or "week unknown"
    return f"{when}, the season's {ordinal(f.order)} first" if f.order > 0 else when


def card_page(c: Card, n: int, season: season_calendar.Season, players: int, links, made: dt.date) -> str:
    name = season_name(n)
    url = f"{SITE}/wrapped/season-{n}/{c.slug}.html"
    out = [head(f"{c.name}'s Season {name} - Monkey SMP", f"{c.name} on Monkey SMP, Season {name}: {summary(c)}",
                url)]
    out.append(f"""    <section class="top">
      <p class="kicker">Season {name} Wrapped</p>
      <h1>{esc(c.name)}</h1>
      <p class="lede">Season {name} on Monkey SMP, {season_span(season)}.</p>
""")
    out.append(figures([(c.hours, "hours played"), (str(c.days), "days on the server"),
                        (str(c.kills), "PvP kills"), (str(c.challenges), "weekly challenges done"),
                        (str(c.events), "events attended")]))
    out.append('      <p class="small">Kills count outside the event arena, as in the weekly standings.</p>\n')
    out.append("    </section>\n")

    out.append('    <section id="faction">\n      <h2>Faction</h2>\n')
    if c.best:
        b = c.best
        where = f"with {esc(b.faction)}" if b.faction.casefold() != c.faction.casefold() else ""
        out.append(f'      <p class="note">{esc(c.faction)}. Best weekly rank: <strong>{ordinal(b.rank)} of '
                   f'{b.of}</strong>, {week_words(b.week)}{", " + where if where else ""}.</p>\n')
    elif c.faction:
        out.append(f'      <p class="note">{esc(c.faction)}.</p>\n')
    else:
        out.append('      <p class="note">No faction in the weekly standings this season.</p>\n')
    if c.bounties:
        out.append(f'      <p class="note">{plural(c.bounties, "bounty", "bounties")} claimed.</p>\n')
    out.append("    </section>\n")

    out.append('    <section id="firsts">\n      <h2>Server Firsts</h2>\n')
    if c.firsts:
        items = "".join(f'\n        <li><b>{esc(f.milestone)}</b> <span>{first_words(f)}</span></li>'
                        for f in c.firsts)
        out.append(f'      <ol class="rows">{items}\n      </ol>\n')
    else:
        out.append('      <p class="note">None this season.</p>\n')
    out.append("    </section>\n")

    out.append('    <section id="skins">\n      <h2>Wardrobe</h2>\n')
    if c.skins:
        out.append('      <p class="note">Rarest first: how many of the season\'s '
                   f'{players} players hold each.</p>\n      <ul class="skins">')
        for s in c.skins:
            tag = ' <span class="tag">New this season</span>' if s.new else ""
            rarity = "only them" if s.holders == 1 else f"{s.holders} of {players}"
            out.append(f'\n        <li><img src="skins/{s.id}.png" alt="" width="64" height="64"> '
                       f'<b>{esc(s.name)}</b>{tag} <span class="held">{rarity}</span></li>')
        out.append("\n      </ul>\n")
    else:
        out.append('      <p class="note">No skins yet.</p>\n')
    out.append("    </section>\n")
    out.append(foot(links, made))
    return "".join(out)


def index_page(shown: list[Card], everyone: list[Card], claimed: list[First], hidden: set[str], n: int,
               season: season_calendar.Season, links, made: dt.date) -> str:
    name = season_name(n)
    ticks = sum(c.ticks for c in everyone)
    out = [head(f"Season {name} Wrapped - Monkey SMP",
                f"Monkey SMP's Season {name}, player by player: hours, kills, Server Firsts and wardrobe skins.",
                f"{SITE}/wrapped/season-{n}/")]
    out.append(f"""    <section class="top">
      <p class="kicker">Season {name} Wrapped</p>
      <h1>Season {name}, player by player</h1>
      <p class="lede">{season_span(season)}. Pick a name for that player's season.</p>
""")
    out.append(figures([(str(len(everyone)), "players"), (f"{ticks // TICKS_AN_HOUR}", "hours played"),
                        (str(sum(c.kills for c in everyone)), "PvP kills"),
                        (str(sum(c.challenges for c in everyone)), "weekly challenges done"),
                        (str(len(claimed)), "Server Firsts claimed")]))
    out.append("    </section>\n")

    out.append('    <section id="players">\n      <h2>Players</h2>\n')
    if shown:
        items = "".join(f'\n        <li><a href="{c.slug}.html">{esc(c.name)}</a> <span>{c.hours} h</span></li>'
                        for c in shown)
        out.append(f'      <ul class="players">{items}\n      </ul>\n')
    else:
        out.append('      <p class="note">No pages.</p>\n')
    if len(shown) < len(everyone):
        out.append(f'      <p class="small">{plural(len(everyone) - len(shown), "player")} asked not to have a '
                   'page.</p>\n')
    out.append("    </section>\n")

    if claimed:
        def who(f):
            return "a player who asked not to be named" if f.player.casefold() in hidden else esc(f.player)
        items = "".join(f'\n        <li><b>{esc(f.milestone)}</b> <span>{who(f)}'
                        f'{", " + week_words(f.week) if f.week is not None else ""}</span></li>' for f in claimed)
        out.append(f'    <section id="firsts">\n      <h2>Server Firsts</h2>\n      <ol class="rows">{items}\n'
                   '      </ol>\n')
        best = firsts.champion(claimed)
        if best and best.player.casefold() not in hidden:
            out.append(f'      <p class="note">The most: <strong>{esc(best.player)}</strong>, with '
                       f'{best.count}, and the Pioneer title.</p>\n')
        out.append("    </section>\n")
    out.append(foot(links, made))
    return "".join(out)


CSS = """/* Season Wrapped (generated by tools/wrapped.py): the site's style.css, plus the parts these pages add. */
.wrapped main > section { padding-top: 56px; padding-bottom: 56px; }
.wrapped main > section.top { padding-top: 96px; }
.wrapped main > section + section { border-top: 2px solid var(--leaf-2); }
.kicker { margin: 0 0 8px; font-weight: 700; color: var(--sage); }
.top h1 { overflow-wrap: anywhere; }
.top .lede { margin-bottom: 40px; }
.figures { list-style: none; margin: 0; padding: 0; display: grid; gap: 16px;
  grid-template-columns: repeat(auto-fill, minmax(10.5rem, 1fr)); max-width: 64rem; }
.figures li { display: grid; gap: 6px; padding: 12px 14px 14px;
  background: var(--shade) padding-box; border: 6px solid transparent; border-image: var(--frame-shade) 6 fill / 6px; }
.figures b { font: 700 2.75rem/1 var(--display); color: var(--gold); font-variant-numeric: tabular-nums; }
.figures span { font-size: 0.95rem; font-weight: 700; color: var(--sage); }
.rows { list-style: none; margin: 0; padding: 0; max-width: 40rem; }
.rows li { display: grid; grid-template-columns: minmax(0, 14rem) minmax(0, 1fr); gap: 12px; align-items: baseline;
  padding: 12px 0; border-top: 2px solid var(--leaf-2); }
.rows li:last-child { border-bottom: 2px solid var(--leaf-2); }
.rows b { font: 700 1.2rem/1.2 var(--display); color: var(--bone); }
.rows span { color: var(--sage); }
.skins { list-style: none; margin: 24px 0 0; padding: 0; display: grid; gap: 16px;
  grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr)); max-width: 64rem; }
.skins li { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 2px 14px; align-items: center;
  padding: 12px 14px; background: var(--leaf-2) padding-box; border: 6px solid transparent;
  border-image: var(--frame-leaf) 6 fill / 6px; }
.skins img { grid-row: span 2; image-rendering: pixelated; }
.skins b { font: 700 1.2rem/1.2 var(--display); color: var(--bone); }
.skins .tag { margin: 0; justify-self: start; grid-column: 2; }
.skins .held { grid-column: 2; color: var(--sage); font-size: 0.95rem; }
.players { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px 24px;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr)); }
.players li { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0;
  border-top: 2px solid var(--leaf-2); }
.players a { font-weight: 700; overflow-wrap: anywhere; }
.players span { color: var(--sage); white-space: nowrap; }
@media (max-width: 760px) {
  .wrapped main > section.top { padding-top: 56px; }
  .figures { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .figures b { font-size: 2.25rem; }
  .rows li { grid-template-columns: 1fr; gap: 2px; }
}
"""


def skin_png(skin_id: str) -> bytes:
    for _, kind, s in wardrobe.skins():
        if s["id"] == skin_id:
            art = wardrobe.blade_pixels(s) if kind == "blade" else wardrobe.icon_pixels(s)
            return wardrobe.png(art, wardrobe.palette(s["pal"]))
    raise KeyError(skin_id)


def clear_earlier_run(out: Path) -> None:
    """Removes what an earlier run wrote in `out` (its pages, the style, the skins' pictures). A folder holding
    anything else is refused, so a wrong --out never loses a file."""
    if not out.is_dir():
        if out.exists():
            raise SystemExit(f"{out} is a file: give a folder (site/wrapped/season-<n>)")
        return
    pages = [p for p in out.glob("*.html")
             if f'content="{GENERATOR}"' in p.read_text(encoding="utf-8", errors="replace")]
    pictures = sorted((out / "skins").glob("*.png")) if (out / "skins").is_dir() else []
    ours = {*pages, *pictures, out / "wrapped.css", out / "skins"}
    found = [*out.iterdir(), *((out / "skins").iterdir() if (out / "skins").is_dir() else [])]
    others = [p for p in found if p not in ours]
    if others:
        raise SystemExit(f"{out} holds {others[0].name}, which this tool didn't write: give an empty folder or the "
                         "one an earlier run wrote (site/wrapped/season-<n>)")
    for p in [*pages, *pictures, out / "wrapped.css"]:
        p.unlink(missing_ok=True)


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- the commands


def start(world: Path, out: Path, now: dt.datetime) -> int:
    board = scores(world)
    holder, objective = LAUNCHED.split()
    if board.get(objective, {}).get(holder, 0) != 1:
        print(f"{world} hasn't launched ({LAUNCHED} isn't 1): run this right after function realms:rules/launch, "
              "and `save-all flush` before it", file=sys.stderr)
        return 1
    snapshot = {"taken": now.isoformat(timespec="seconds"), "scores": kept(board)}
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, out)
    print(f"wrote {out}: {len(snapshot['scores'].get(PLAY, {}))} players' counts at {now:%Y-%m-%d %H:%M %Z}")
    return 0


def build(world: Path, n: int, state: Path, start_file: Path | None, out: Path, opt_out: Path | None,
          today: dt.date) -> int:
    if not world.is_dir():
        raise SystemExit(f"{world} is not a folder: give the season's final world folder")
    snap = read_start(start_file) if start_file else None
    if snap is None and n != 1:
        raise SystemExit(f"Season {season_name(n)} needs --start: without it, what earlier seasons carried in "
                         "would read as this season's")
    if snap is None:
        warn("no --start: counting from zero, so staff test play before the launch counts too")
    season = season_calendar.SEASON if n == 1 else season_calendar.Season(snap.taken)
    if snap and not season.launch - dt.timedelta(hours=1) <= snap.taken <= season.launch + dt.timedelta(days=1):
        warn(f"the starting point was kept {snap.taken:%Y-%m-%d %H:%M %z}, not at the launch "
             f"({season.launch.astimezone(season_calendar.PACIFIC):%Y-%m-%d %H:%M %z}): a rehearsal's, or kept "
             "late (play before it doesn't count)")
    hidden = read_opt_out(opt_out)
    everyone = cards(world, snap, closed_weeks(state, season), season)
    shown = [c for c in everyone if c.name.casefold() not in hidden]
    claimed = firsts.holders(world)
    config = site_links.site() / "config.js"
    links = site_links.load_links(config.read_text(encoding="utf-8")) if config.is_file() else {}

    clear_earlier_run(out)
    write(out / "wrapped.css", CSS)
    write(out / "index.html", index_page(shown, everyone, claimed, hidden, n, season, links, today))
    for c in shown:
        write(out / f"{c.slug}.html", card_page(c, n, season, len(everyone), links, today))
    for skin_id in sorted({s.id for c in shown for s in c.skins}):
        write(out / "skins" / f"{skin_id}.png", skin_png(skin_id))
    left = sorted(hidden - {c.name.casefold() for c in everyone})
    print(f"wrote {out}: an index and {plural(len(shown), 'page')} ({len(everyone) - len(shown)} opted out) "
          f"for Season {season_name(n)}")
    if left:
        warn(f"on the opt-out list but not among this season's players: {', '.join(left)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Season Wrapped: a page for every player about their season.")
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("start", help="right after the launch: where everyone's counts start from")
    s.add_argument("world", type=Path, help="the live world folder (server/world), saved just now")
    s.add_argument("--out", type=Path, required=True,
                   help="the file to keep (e.g. /srv/realms/seasons/season-I-wrapped-start.json)")
    b = sub.add_parser("build", help="after the finale: the pages")
    b.add_argument("world", type=Path, help="the season's final world folder")
    b.add_argument("--season", type=int, required=True, help="the season's number (1 for Season I)")
    b.add_argument("--standings", type=Path, required=True, help="the standings folder (STANDINGS_DIR)")
    b.add_argument("--start", type=Path, help="the file `start` wrote at the launch")
    b.add_argument("--opt-out", type=Path, help="players who asked for no page, one name a line")
    b.add_argument("--out", type=Path, required=True, help="site/wrapped/season-<n> in a checkout")
    args = ap.parse_args(argv)
    now = season_calendar.now()
    if args.command == "start":
        return start(args.world, args.out, now)
    return build(args.world, args.season, args.standings, args.start, args.out, args.opt_out, now.date())


if __name__ == "__main__":
    sys.exit(main())

