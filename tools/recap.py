"""The Sunday recap, "Monkey SMP Weekly": the week's final standings, then a few short lines on the week.

    import recap
    recap.launched(world)        whether the season has launched (#launched rw.day, set by realms:rules/launch)
    recap.baseline(world)        what a new week starts from, for the sections (kept in STATE/week.json)
    recap.blocks(week)           every section's lines for a closing Week, worked out once, at the close
    recap.message(head, table, blocks, footer)
                                 the Discord post, kept under Discord's 2000 characters

tools/standings.py close is the only caller: it works the sections out when the week closes and keeps their
lines in the closed week's file (STATE/weeks/<date>.json, "recap"), so a retry posts the same words even
though the world has moved on. Before the launch it keeps no recap and posts nothing. The week the launch
falls in began in test play (Week.test_play): realms:rules/launch clears test play's challenges, so those
count from the launch, but not its kills, bounties, claims or events, so those sections wait a week.

A section is a function in SECTIONS that takes the closing Week and returns its lines, or [] when it has
nothing to say. To add one (server firsts, wars, outposts):

    def firsts(week: Week) -> list[str]:
        ...
        return [f"**Server firsts:** {md(name)} ..."]

and put it in SECTIONS where it should show. The order there is the order in the post, and the order lines
are dropped in when the post is too long (the last first). A section reads what it needs from the Week: the
final rows, the saved world at the close (`week.world`, `week.folder` for another tool's reader), the week's
starting point (`week.start`) and last week's closed file (`week.previous`). One that needs a starting point
for a scoreboard score adds the objective to COUNTERS; for anything else, to baseline(). A section that
fails is logged and left out: it never stops the standings.

Names come from players (party names, player names), so every name goes through md() before it is written
outside the table's code block, and the post pings nobody (standings.post_discord).

Stdlib only, no imports from standings.py (it imports this), and Python 3.10 or newer.
"""
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path

import npcs
import season_calendar
from challenges import LAUNCHED, TEST_PLAY
from events import STATE

DISCORD_LIMIT = 2000
TABLE_ROWS = (10, 8, 5, 3)   # factions in the post's table, fewer when the post would be too long
LINE_LIMIT = 300             # characters of one section line, at most
NAME_LIMIT = 32              # characters of one name in a section line
LISTED = 5                   # names in a list (bounty hunters) before "and N more"
KILLS, BOUNTY = "st.kills", "st.bounty"   # standings.py's, with their starting points in week.json
CHALLENGES, SEEN = "rw.challenges", "ev.seen"
COUNTERS = (CHALLENGES,)           # scores whose starting point baseline() keeps
EVENT = "#event"                    # events begun so far, in ev.state (realms:events/begin)


# ---------------------------------------------------------------- the week


def launched(world) -> bool:
    """Whether realms:rules/launch has run on this world: test play before it never posts."""
    holder, objective = LAUNCHED.split()
    return world.scores.get(objective, {}).get(holder, 0) >= 1


def baseline(world) -> dict:
    """What the sections count from, kept in a new week's snapshot (standings.snapshot)."""
    return {"launched": launched(world),
            "scores": {o: dict(sorted(world.scores.get(o, {}).items())) for o in COUNTERS},
            "event": world.scores.get(STATE, {}).get(EVENT, 0),
            "claims": dict(sorted(world.claims.items()))}


def gained(now: int, then: int) -> int:
    """standings.gained: one below its starting point was restarted (a new world, a reset), so all of it is new."""
    return max(0, now - then if now >= then else now)


@dataclass
class Week:
    rows: list[dict]           # the final table, best first: name, members, cup, land, strength, kills, bounties, ...
    world: object              # standings.World at the close: parties, claims (UUID -> chunks), scores
    start: dict                # the week's starting point (STATE/week.json): kills, bounty, and "recap" (baseline())
    previous: dict | None      # last week's closed file, if it closed after the launch
    end: dt.datetime           # when the week closed
    folder: Path | None = None  # the world folder, for sections that read it with another tool

    @property
    def test_play(self) -> bool:
        """Whether the week began before the launch (usually the launch weekend's): the launch clears test play's
        challenges, but not its kills, bounties, claims or events, so those sections say nothing this week."""
        base = self.start.get("recap")
        return bool(base) and not base.get("launched")

    @property
    def number(self) -> int:
        """The season week that is ending: 0 is the launch weekend (season_calendar)."""
        return season_calendar.week_at(self.end)

    def scores(self, objective: str) -> dict[str, int]:
        return self.world.scores.get(objective, {})

    def gains(self, objective: str, fold: bool = False) -> dict[str, int] | None:
        """What each player gained in a score this week (only those who gained), or None when the week has no
        starting point for it (it began before the recap existed). fold: names in lower case (staff type the
        bounty commands' names by hand)."""
        if objective == KILLS:
            then = self.start.get("kills")
        elif objective == BOUNTY:
            then = self.start.get("bounty")
        else:
            base = self.start.get("recap")
            then = base["scores"].get(objective) if base else None
            # A week that began in Season I's test play: the launch cleared these, so all of them came after it.
            # (Later seasons keep what they carried: challenges/launch clears only in season 1.)
            if base and not base.get("launched") and objective in TEST_PLAY and \
                    self.scores("rw.day").get("#season", 0) == 1:
                then = {}
        if then is None:
            return None
        now = self.scores(objective)
        if fold:
            now, then = folded(now), folded(then)
        out = {name: gained(value, then.get(name, 0)) for name, value in now.items() if not name.startswith("#")}
        return {name: n for name, n in out.items() if n > 0}

    def faction(self, player: str) -> str | None:
        """The faction a player is in, by name (any case)."""
        for row in self.rows:
            if player.lower() in (m.lower() for m in row.get("members", [])):
                return row["name"]
        return None

    def player(self, name: str) -> str:
        """A player's name as their faction lists it (the bounty scores keep what staff typed), else as given."""
        for row in self.rows:
            for m in row.get("members", []):
                if m.lower() == name.lower():
                    return m
        return name


def folded(scores: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for name, value in scores.items():
        out[name.lower()] = out.get(name.lower(), 0) + value
    return out


# ---------------------------------------------------------------- words


MARKDOWN = set("\\*_~`|>#[]()<:-")


def md(name: str) -> str:
    """A player-chosen name, safe outside a code block: one line, at most NAME_LIMIT characters, and Discord's
    markdown escaped, so a faction can't be a link, a heading or a mention."""
    text = " ".join(str(name).split())
    if len(text) > NAME_LIMIT:
        text = text[:NAME_LIMIT - 1].rstrip() + "…"   # an ellipsis: "~" is markdown
    return "".join("\\" + c if c in MARKDOWN else c for c in text) or "?"


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def count(n: int, thing: str) -> str:
    return f"{n} {thing}" + ("" if n == 1 else "s")


def listed(items: list[str]) -> str:
    """'A', 'A and B', 'A, B and C', with 'and N more' past LISTED."""
    shown, rest = items[:LISTED], len(items) - LISTED
    if rest > 0:
        return ", ".join(shown) + f" and {rest} more"
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]


def who(week: Week, name: str) -> str:
    faction = week.faction(name)
    return md(name) + (f" ({md(faction)})" if faction else "")


def short_day(when: dt.datetime) -> str:
    """'Sun 29 Nov', the same in any locale."""
    local = when.astimezone(season_calendar.PACIFIC)
    return f"{season_calendar.DAYS[local.weekday()][:3]} {local.day} {season_calendar.MONTHS[local.month - 1][:3]}"


def heading(closed: dict) -> str:
    """'**Monkey SMP Weekly**, week 3: Sun 6 Dec to Sun 13 Dec'."""
    end = dt.datetime.fromisoformat(closed["end"])
    week = season_calendar.week_at(end)
    name = "the launch weekend" if week == 0 else f"week {week}"
    dates = short_day(end) if not closed.get("start") else \
        f"{short_day(dt.datetime.fromisoformat(closed['start']))} to {short_day(end)}"
    return f"**Monkey SMP Weekly**, {name}: {dates}"


# ---------------------------------------------------------------- the sections


def mover(week: Week) -> list[str]:
    """The faction that climbed the most places since last week's final table."""
    if not week.previous:
        return []
    before = {r["name"]: r["rank"] for r in week.previous.get("rows", [])}
    best = None
    for r in week.rows:   # best first, so a tie goes to the higher rank
        up = before.get(r["name"], 0) - r["rank"]
        if r["name"] in before and up > 0 and (best is None or up > best[0]):
            best = (up, r)
    if best is None:
        return []
    up, r = best
    return [f"**Biggest mover:** {md(r['name'])}, up {count(up, 'place')} to {ordinal(r['rank'])}."]


def fighter(week: Week) -> list[str]:
    """Whoever got the most PvP kills this week, outside the arena (st.kills: the standings' kills)."""
    kills = {} if week.test_play else week.gains(KILLS) or {}
    if not kills:
        return []
    top = max(kills.values())
    names = sorted((n for n, k in kills.items() if k == top), key=str.casefold)
    each = " each" if len(names) > 1 else ""
    return [f"**Top fighter:** {listed([who(week, n) for n in names])}, {count(top, 'PvP kill')}{each}."]


def bounties(week: Week) -> list[str]:
    claimed = {} if week.test_play else week.gains(BOUNTY, fold=True) or {}
    if not claimed:
        return []
    hunters = sorted(claimed.items(), key=lambda item: (-item[1], item[0]))
    names = [md(week.player(name)) + (f" ({n})" if n > 1 else "") for name, n in hunters]
    total = sum(claimed.values())
    return [f"**Bounties claimed:** {total}, by {listed(names)}."]


def land(week: Week) -> list[str]:
    """Chunks claimed this week, all told, and the faction that claimed the most."""
    base = week.start.get("recap")
    if not base or week.test_play:
        return []
    then, now = base.get("claims", {}), week.world.claims
    total = sum(now.get(u, 0) - then.get(u, 0) for u in set(now) | set(then))
    if total <= 0:
        return []
    best = None
    for party in week.world.parties:
        grew = sum(now.get(u, 0) - then.get(u, 0) for u in party.uuids)
        if grew > 0 and (best is None or grew > best[0] or (grew == best[0] and party.name < best[1])):
            best = (grew, party.name)
    most = f", the most by {md(best[1])} (+{best[0]})" if best else ""
    return [f"**Land:** {count(total, 'new chunk')} claimed{most}."]


def challenges(week: Week) -> list[str]:
    done = week.gains(CHALLENGES)
    if not done:
        return []
    return [f"**Challenges:** {sum(done.values())} done, by {count(len(done), 'player')}."]


def turnout(week: Week) -> list[str]:
    """Events begun this week (realms:events/begin), and how many came to the last one (ev.seen holds the last
    event each player came to)."""
    base = week.start.get("recap")
    if not base or week.test_play:
        return []
    now = week.scores(STATE).get(EVENT, 0)
    begun = gained(now, base.get("event", 0))
    if begun <= 0:
        return []
    came = sum(1 for name, seen in week.scores(SEEN).items() if not name.startswith("#") and seen == now)
    if came == 0:   # nobody marked as there (events/attend not run): no turnout to tell
        return []
    if begun == 1:
        return [f"**Event turnout:** {count(came, 'player')} came."]
    return [f"**Event turnout:** {begun} events, and {count(came, 'player')} came to the last one."]


def next_saturday(week: Week) -> list[str]:
    """Next Saturday's event, from the season calendar (the Town Crier's list, tools/npcs.py)."""
    n = week.number + 1
    if n > npcs.LAST_WEEK:
        return [f"**Next:** Season II is planned for {season_calendar.day_words(season_calendar.SEASON_TWO)}."]
    event = npcs.EVENTS.get(n)
    if not event:
        return []
    when = season_calendar.day_words(season_calendar.saturday(n))
    return [f"**Next Saturday:** {event[0].upper() + event[1:]}, {when}, {npcs.TIME}."]


# The week's sections, in the order they show. Add a new one here (see the top of this file).
SECTIONS = [mover, fighter, bounties, land, challenges, turnout]
QUIET = "A quiet week: no PvP kills, bounties, new land or challenges."
LAUNCH = "**The season is open.** Fights, bounties, land and events show here from next Sunday."


def blocks(week: Week, log=lambda msg: print(f"warning: {msg}", file=sys.stderr)) -> list[list[str]]:
    """Every section's lines, then next Saturday. A section that fails is logged and left out."""
    out = []
    for section in SECTIONS:
        try:
            got = section(week)
        except Exception as e:   # one broken section must never stop the Sunday close
            log(f"the recap's {section.__name__} section failed ({type(e).__name__}: {e}): left out")
            continue
        if got:
            out.append([line[:LINE_LIMIT] for line in got])
    if week.test_play:
        out.insert(0, [LAUNCH])
    elif not out:
        out.append([QUIET])
    upcoming = next_saturday(week)
    if upcoming:
        out.append(upcoming)
    return out


# ---------------------------------------------------------------- the post


def size(text: str) -> int:
    """Length as Discord counts it (UTF-16 code units, so an emoji in a name counts as two)."""
    return len(text.encode("utf-16-le")) // 2


def message(head: str, table, sections: list[list[str]], footer: str, limit: int = DISCORD_LIMIT) -> str:
    """The post: the heading, the table (table(n) gives its lines for the first n factions) in a code block,
    the sections, the footer. Too long, it shows fewer factions, then drops sections from the end."""
    def render(rows: int, kept: int) -> str:
        return "\n".join([head, "```", *table(rows), "```", *(line for b in sections[:kept] for line in b), footer])

    for rows in TABLE_ROWS:
        text = render(rows, len(sections))
        if size(text) <= limit:
            return text
    for kept in range(len(sections) - 1, -1, -1):
        text = render(TABLE_ROWS[-1], kept)
        if size(text) <= limit:
            return text
    while size(text) > limit - 4:   # only a heading or footer far too long gets here
        text = text[:-1]
    return text + "\n```" if text.count("```") % 2 else text
