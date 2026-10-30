"""The Sunday recap, "Monkey SMP Weekly": the week's final standings, then a few short lines on the week.

    import recap
    recap.launched(world)        whether the season has launched (#launched rw.day, set by monkey:rules/launch)
    recap.baseline(world)        what a new week starts from, for the sections (kept in STATE/week.json)
    recap.blocks(week)           every section's lines for a closing Week, worked out once, at the close
    recap.message(head, table, blocks, footer, limit)
                                 the Discord post, kept under Discord's 2000 characters

tools/standings.py close is the only caller: it works the sections out when the week closes and keeps their
lines in the closed week's file (STATE/weeks/<date>.json, "recap"), so a retry posts the same words even
though the world has moved on. Before the launch it keeps no recap and posts nothing. The week the launch
falls in began in test play (Week.test_play: it began before season_calendar.LAUNCH): monkey:rules/launch
clears test play's challenges, so those count from the launch, but not its kills, bounties, claims or events,
so those sections wait a week.

A section is a function in SECTIONS that takes the closing Week and returns its lines: [] when nothing
happened, None when it can't tell (no starting point for it, say). "A quiet week" shows only when every
section returned [], so it never claims a quiet week the recap couldn't count. To add one (server firsts,
wars, outposts):

    def firsts(week: Week) -> list[str] | None:
        ...
        return [f"**Server firsts:** {md(name)} ..."]

and put it in SECTIONS where it should show. The order there is the order in the post, and the order lines
are dropped in when the post is too long (the last first). A section reads what it needs from the Week: the
final rows (with each faction's party id), the saved world at the close (`week.world`, `week.folder` for
another tool's reader), the week's starting point (`week.start`) and last week's closed file (`week.previous`).
One that needs a starting point for a scoreboard score adds the objective to COUNTERS; for anything else, to
baseline(). A section that fails is logged and left out: it never stops the standings. A list of names goes
through fit(), which shows fewer names ("and 3 more") rather than cutting a line short.

Names come from players (party names, player names), so every name goes through md() before it is written
outside the table's code block, and the post pings nobody (standings.post_discord).

The week's counters (KILLS, BOUNTY, gained, folded) live here and standings.py imports them, so both count a
week the same way. Stdlib only, no imports from standings.py (it imports this), and Python 3.10 or newer.
"""
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path

import goal
import npcs
import season_calendar
from challenges import LAUNCHED, TEST_PLAY
from events import STATE

DISCORD_LIMIT = 2000
TABLE_ROWS = (10, 8, 5, 3)   # factions in the post's table, fewer when the post would be too long
LINE_LIMIT = 300             # characters of one section line, at most
NAME_LIMIT = 32              # characters of one name in a section line
LISTED = 5                   # names in a list (bounty hunters) before "and N more"
KILLS, BOUNTY = "st.kills", "st.bounty"   # the standings' kills and bounties, with their starting points in week.json
HUNTS = "st.hunts"                 # player-posted bounties claimed (the wanted board, tools/wanted.py)
CHALLENGES, SEEN = "rw.challenges", "ev.seen"
COUNTERS = (CHALLENGES, HUNTS)     # scores whose starting point baseline() keeps
EVENT = "#event"                    # events begun so far, in ev.state (monkey:events/begin)


# ---------------------------------------------------------------- counting a week


def gained(now: int, then: int) -> int:
    """What a counter gained since the week began. One below its starting point was restarted (a new season's
    world, or staff reset it), so all of it is new."""
    return max(0, now - then if now >= then else now)


def folded(scores: dict[str, int]) -> dict[str, int]:
    """Scores by lower-case name: staff type a bounty hunter's name by hand, and the scoreboard keeps it as typed."""
    out: dict[str, int] = {}
    for name, value in scores.items():
        out[name.lower()] = out.get(name.lower(), 0) + value
    return out


def launched(world) -> bool:
    """Whether monkey:rules/launch has run on this world: test play before it never posts."""
    holder, objective = LAUNCHED.split()
    return world.scores.get(objective, {}).get(holder, 0) >= 1


def baseline(world) -> dict:
    """What the sections count from, kept in a new week's snapshot (standings.snapshot)."""
    return {"launched": launched(world),
            "scores": {o: dict(sorted(world.scores.get(o, {}).items())) for o in COUNTERS},
            "event": world.scores.get(STATE, {}).get(EVENT, 0),
            "claims": dict(sorted(world.claims.items()))}


def season_week(start: str | None, end: dt.datetime) -> int:
    """The season week a closed week was (0 is the launch weekend), from its middle: a close that runs late,
    past Monday 12 AM Pacific, still names the week it closed. Without a start, from the day before the end."""
    begun = dt.datetime.fromisoformat(start) if start else end - dt.timedelta(days=2)
    return season_calendar.week_at(begun + (end - begun) / 2)


# ---------------------------------------------------------------- the week


@dataclass
class Week:
    rows: list[dict]           # the final table, best first: id (the party's), name, members, cup, land, kills, ...
    world: object              # standings.World at the close: parties, claims (UUID -> chunks), scores
    start: dict                # the week's starting point (STATE/week.json): start, kills, bounty, "recap" (baseline())
    previous: dict | None      # last week's closed file, if it closed after the launch
    end: dt.datetime           # when the week closed
    folder: Path | None = None  # the world folder, for sections that read it with another tool
    assume_launched: bool = False   # standings preview: read the week as if it began after the launch

    @property
    def test_play(self) -> bool:
        """Whether the week began before the launch (the launch weekend's week): the launch clears test play's
        challenges, but not its kills, bounties, claims or events, so those sections say nothing this week. Its
        start against season_calendar.LAUNCH, or its baseline's launch flag, if either says so."""
        if self.assume_launched:
            return False
        base = self.start.get("recap")
        begun = self.start.get("start")
        return (bool(begun) and dt.datetime.fromisoformat(begun) < season_calendar.LAUNCH) or \
            (bool(base) and not base.get("launched"))

    @property
    def number(self) -> int:
        """The season week that is ending: 0 is the launch weekend (season_calendar)."""
        return season_week(self.start.get("start"), self.end)

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
            if then is not None and objective in TEST_PLAY and self.test_play and \
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


# ---------------------------------------------------------------- words


MARKDOWN = set("\\*_~`|>#[]()<:-")
ELLIPSIS = "…"   # not "~", which is markdown


def md(name: str) -> str:
    """A player-chosen name, safe outside a code block: one line, at most NAME_LIMIT characters, and Discord's
    markdown escaped, so a faction can't be a link, a heading or a mention."""
    text = " ".join(str(name).split())
    if len(text) > NAME_LIMIT:
        text = text[:NAME_LIMIT - 1].rstrip() + ELLIPSIS
    return "".join("\\" + c if c in MARKDOWN else c for c in text) or "?"


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def count(n: int, thing: str) -> str:
    return f"{n} {thing}" + ("" if n == 1 else "s")


def listed(items: list[str], shown: int = LISTED) -> str:
    """'A', 'A and B', 'A, B and C', with 'and N more' past the first `shown`."""
    first, rest = items[:max(1, shown)], len(items) - max(1, shown)
    if rest > 0:
        return ", ".join(first) + f" and {rest} more"
    return first[0] if len(first) == 1 else ", ".join(first[:-1]) + " and " + first[-1]


def clip(line: str) -> str:
    """A line cut to LINE_LIMIT, if it must be, ending in an ellipsis and never on half a markdown escape."""
    if len(line) <= LINE_LIMIT:
        return line
    cut = line[:LINE_LIMIT - 1]
    if (len(cut) - len(cut.rstrip("\\"))) % 2:   # an odd run of backslashes at the end: one escapes the ellipsis
        cut = cut[:-1]
    return cut + ELLIPSIS


def fit(line, items: list[str]) -> str:
    """line(names) with as many of `items` as fit in LINE_LIMIT, the rest as 'and N more'."""
    for shown in range(min(LISTED, len(items)), 1, -1):
        text = line(listed(items, shown))
        if len(text) <= LINE_LIMIT:
            return text
    return clip(line(listed(items, 1)))


def who(week: Week, name: str) -> str:
    faction = week.faction(name)
    return md(name) + (f" ({md(faction)})" if faction else "")


def heading(closed: dict) -> str:
    """'**Monkey SMP Weekly**, week 3: Sun 6 Dec to Sun 13 Dec'."""
    end = dt.datetime.fromisoformat(closed["end"])
    week = season_week(closed.get("start"), end)
    name = "the launch weekend" if week == 0 else f"week {week}"
    day = season_calendar.short_day
    dates = day(end) if not closed.get("start") else f"{day(dt.datetime.fromisoformat(closed['start']))} to {day(end)}"
    return f"**Monkey SMP Weekly**, {name}: {dates}"


# ---------------------------------------------------------------- the sections


def mover(week: Week) -> list[str] | None:
    """The faction that climbed the most places since last week's final table, matched by party id (names
    change, and two factions can share one). A file from before the ids matches by name, where it is unique."""
    if not week.previous:
        return []   # nothing to move up from (week 0): no mover, and nothing "A quiet week" claims
    rows = week.previous.get("rows", [])
    by_id = {r["id"]: r["rank"] for r in rows if r.get("id")}
    names = [r["name"] for r in rows if not r.get("id")]
    by_name = {r["name"]: r["rank"] for r in rows if not r.get("id") and names.count(r["name"]) == 1}
    best = None
    for r in week.rows:   # best first, so a tie goes to the higher rank
        then = by_id.get(r["id"]) if r.get("id") and by_id else by_name.get(r["name"])
        if then is not None and then - r["rank"] > 0 and (best is None or then - r["rank"] > best[0]):
            best = (then - r["rank"], r)
    if best is None:
        return []
    up, r = best
    return [f"**Biggest mover:** {md(r['name'])}, up {count(up, 'place')} to {ordinal(r['rank'])}."]


def fighter(week: Week) -> list[str] | None:
    """Whoever got the most PvP kills this week, outside the arena (st.kills: the standings' kills)."""
    kills = None if week.test_play else week.gains(KILLS)
    if not kills:
        return None if kills is None else []
    top = max(kills.values())
    names = sorted((n for n, k in kills.items() if k == top), key=str.casefold)
    each = " each" if len(names) > 1 else ""
    return [fit(lambda them: f"**Top fighter:** {them}, {count(top, 'PvP kill')}{each}.",
                [who(week, n) for n in names])]


def bounties(week: Week) -> list[str] | None:
    claimed = None if week.test_play else week.gains(BOUNTY, fold=True)
    if not claimed:
        return None if claimed is None else []
    hunters = sorted(claimed.items(), key=lambda item: (-item[1], item[0]))
    names = [md(week.player(name)) + (f" ({n})" if n > 1 else "") for name, n in hunters]
    total = sum(claimed.values())
    return [fit(lambda them: f"**Bounties claimed:** {total}, by {them}.", names)]


def hunter(week: Week) -> list[str] | None:
    """The week's top bounty hunter, once players have claimed bounties players posted (the wanted board,
    tools/wanted.py): the most bounties claimed this week, staff-posted (st.bounty) and player-posted (st.hunts)
    together. A week with only staff bounties has none: the bounties line names those hunters already."""
    hunts = None if week.test_play else week.gains(HUNTS, fold=True)
    if not hunts:
        return None if hunts is None else []
    total = dict(hunts)
    for name, n in (week.gains(BOUNTY, fold=True) or {}).items():
        total[name] = total.get(name, 0) + n
    top = max(total.values())
    names = sorted((n for n, k in total.items() if k == top), key=str.casefold)
    each = " each" if len(names) > 1 else ""
    return [fit(lambda them: f"**Top bounty hunter:** {them}, {top} {'bounty' if top == 1 else 'bounties'}{each}.",
                [who(week, week.player(n)) for n in names])]


def land(week: Week) -> list[str] | None:
    """Chunks claimed this week, all told, and the faction that claimed the most: each player's claims that
    grew, so land a player gave up doesn't hide land another claimed."""
    base = week.start.get("recap")
    if not base or week.test_play:
        return None
    then, now = base.get("claims", {}), week.world.claims
    grew = {u: n - then.get(u, 0) for u, n in now.items() if n > then.get(u, 0)}
    total = sum(grew.values())
    if total <= 0:
        return []
    best = None
    for party in week.world.parties:
        claimed = sum(grew.get(u, 0) for u in party.uuids)
        if claimed > 0 and (best is None or claimed > best[0] or (claimed == best[0] and party.name < best[1])):
            best = (claimed, party.name)
    most = f", the most by {md(best[1])} (+{best[0]})" if best else ""
    return [f"**Land:** {count(total, 'chunk')} claimed{most}."]


def challenges(week: Week) -> list[str] | None:
    done = week.gains(CHALLENGES)
    if not done:
        return None if done is None else []
    return [f"**Challenges:** {sum(done.values())} done, by {count(len(done), 'player')}."]


def turnout(week: Week) -> list[str] | None:
    """Events begun this week (monkey:events/begin), and how many came to the last one (ev.seen holds the last
    event each player came to)."""
    base = week.start.get("recap")
    if not base or week.test_play:
        return None
    now = week.scores(STATE).get(EVENT, 0)
    begun = gained(now, base.get("event", 0))
    if begun <= 0:
        return []
    came = sum(1 for name, seen in week.scores(SEEN).items() if not name.startswith("#") and seen == now)
    if came == 0:   # nobody marked as there (events/attend not run): no turnout to tell
        return None
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


def player_of_the_week(week: Week) -> list[str] | None:
    """From Season II on (#season rw.day 2 or more): from the faction at the top of the week's table (every
    faction sharing 1st, when tied), the member with the most PvP kills this week, then the most challenges done
    this week, then by name (docs/SEASONS.md, "Player of the Week"). Nobody there with either: no line."""
    if week.scores("rw.day").get("#season", 0) < 2 or not week.rows:
        return []
    kills = None if week.test_play else week.gains(KILLS)
    done = week.gains(CHALLENGES)
    if kills is None and done is None:
        return None
    kills, done = kills or {}, done or {}
    first = week.rows[0]["rank"]
    picks = sorted(((kills.get(m, 0), done.get(m, 0), m, row) for row in week.rows if row["rank"] == first
                    for m in row.get("members", [])),
                   key=lambda p: (-p[0], -p[1], p[2].casefold()))
    if not picks or picks[0][:2] == (0, 0):
        return []
    k, c, name, top = picks[0]
    did = " and ".join(part for part in (count(k, "PvP kill") if k else "", count(c, "challenge") if c else "") if part)
    return [f"**Player of the Week:** {md(name)} ({md(top['name'])}, 1st), {did}."]


# The week's sections, in the order they show. Add a new one here (see the top of this file).
def server_goal(week: Week) -> list[str] | None:
    """The weekly server goal (tools/goal.py): reached, or how far it got. Nothing while it is off. It counts
    only after the launch (goal/second), so the launch weekend's line is the season's own play."""
    return goal.recap_line(week.world.scores, week.number)


SECTIONS = [mover, fighter, bounties, hunter, land, challenges, server_goal, turnout, player_of_the_week]
QUIET = "A quiet week: no PvP kills, bounties, new land or challenges."
LAUNCH = "**The season is open.** Fights, bounties, land and events show here from next Sunday."


def guarded(what: str, log, work, *args):
    """work(*args), or None (logged) when it fails: nothing in the recap may stop the Sunday close."""
    try:
        return work(*args)
    except Exception as e:
        log(f"the recap's {what} failed ({type(e).__name__}: {e}): left out")
        return None


def blocks(week: Week, log=lambda msg: print(f"warning: {msg}", file=sys.stderr)) -> list[list[str]]:
    """Every section's lines, then next Saturday. A section that fails is logged and left out."""
    out, unsure = [], False
    for section in SECTIONS:
        got = guarded(f"{section.__name__} section", log, section, week)
        unsure = unsure or got is None
        if got:
            out.append([clip(line) for line in got])
    play = guarded("launch check", log, getattr, week, "test_play")
    if play:
        out.insert(0, [LAUNCH])
    elif play is False and not out and not unsure:
        out.append([QUIET])
    upcoming = guarded("next Saturday", log, next_saturday, week)
    if upcoming:
        out.append([clip(line) for line in upcoming])
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
