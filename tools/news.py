"""Monkey SMP news: one plain line in the Discord channel when something notable happens on the live server.

    python tools/news.py found WORLD                  every news item the saved world holds now; changes nothing
    python tools/news.py preview WORLD --state DIR    what the next run would post, and what waits; changes nothing
    python tools/news.py post WORLD --state DIR       posts what is due to NEWS_WEBHOOK_URL (deploy/monkey-news.sh)

What gets posted, at most once a season each (docs/ADMIN.md, "Monkey SMP news"):
  - a Server First from FIRST_LINES (tools/firsts.py's milestones, not all of them): "Steve killed the Ender
    Dragon. First this season." The firsts pack decides who holds it (after the launch, not in the arena, not
    in creative...), so this only reads its claims (firsts.holders).
  - the first on the server this season to finish one of CHALLENGES, rare vanilla advancements the firsts don't
    cover: "Steve completed Monsters Hunted. First this season." Read from each player's saved advancements
    (players/advancements/<uuid>.json), which keep the time each was done, so the first is the earliest one done
    since the season's launch, whoever's file was saved first.
  - new factions (Open Parties and Claims parties), several in one line: "New faction: Red Wolves, led by Steve."
  - 7-day wars (tools/diplomacy.py, when staff switch them on): each declaration and each end, from the
    diplomacy log in the saved storage: "War: Red Wolves declared a 7-day war on Blue Herons." and "Red Wolves won
    its war with Blue Herons, 12 kills to 9." Gone factions keep their names (diplomacy.post_names).
  - outpost sieges (tools/sieges.py, when staff switch them on): one when a window opens and one when it closes,
    from the sieges pack's saved scores (#open, #opened, #closed sg). An open post that can't go before the window
    closes doesn't go; a close post waits at most CLOSE_FRESH.
  - Season II's spectacles: the border boss rising, with its rough place, and how it ended (tools/boss.py: slain,
    by whom and their faction, or left), and the finale's winner (tools/finale.py). Read from their packs'
    command storage. A boss that has ended before its rising posted only posts its end.

Everything comes from the files the server saves (every 5 minutes, ServerCore's autosave-interval-seconds), so a
post lands 5 to 25 minutes after the moment. Nothing posts before the launch (`#launched rw.day`, set by
monkey:rules/launch). No RCON and no log: the firsts pack announces in game with tellraw, which never reaches
the server log, and the saved files are the record the pack and the season already keep.

The rules that keep it rare, all in LIMITS and the constants below it: per kind and in all, at most so many posts
in any 24 hours, and a few per run; what is over a limit waits for a later run, in the order it happened, and is
dropped (never posted) once it is STALE days old. A challenge waits SETTLE minutes first, so a player whose file
was saved later but who did it earlier still gets it.

The state is one JSON file per season in DIR (season-<n>.json, n being the world's `#season rw.day`, 1 when
unset): every item seen and whether it was posted. A new season is a new world and a new file, so "first this
season" starts again by itself. Runs before the launch are noted in it too, so the first run that sees the world
launched knows the launch was since the last one: no calendar date is trusted. If no run saw the world before
its launch, or the last was more than LATE before (the feed was turned on mid-season), or the runs stopped for
longer than LATE (the feed was off), whatever turned up meanwhile is kept as "baseline" and never posted, so old
news doesn't post as new. The file is written whole before and after each post; a post found "sending" (the run
was killed mid-post), or one Discord may have taken without answering, counts as posted: a post can be lost
that way, never made twice.

The webhook is NEWS_WEBHOOK_URL in the environment (deploy/monkey-news.sh reads it from /etc/monkey-deploy.env);
it is never printed. Posts ping nobody. Stdlib only, Python 3.11 or newer (party names are TOML).
"""
import argparse
import datetime as dt
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import boss
import finale

import diplomacy
import firsts
import saved_world
import season_calendar
import sieges
import standings
from challenges import LAUNCHED
from recap import listed, md

UTC = dt.UTC

# ---------------------------------------------------------------- what is news: edit here

# Server Firsts that post, by firsts.MILESTONES id. The early, common ones (diamond, fortress, bastion, ancient
# debris, a trial vault) stay in game only: they would all post within the launch hour.
FIRST_LINES = {
    "nether": "{p} reached the Nether. First this season.",
    "raid": "{p} won a raid. First this season.",
    "mace": "{p} got a mace. First this season.",
    "beacon": "{p} lit a beacon. First this season.",
    "wither": "{p} defeated the Wither. First this season.",
    "end": "{p} entered the End. First this season.",
    "dragon": "{p} killed the Ender Dragon. First this season.",
    "elytra": "{p} found an elytra. First this season.",
    "netherite": "{p} is wearing full Netherite. First this season.",
    "boss": "{p} slew the first border boss. First this season.",
}

# Vanilla advancements that post for the first player on the server to finish one, with their English titles,
# as Minecraft 26.3's own files have them (data/minecraft/advancement/ in the server jar; the titles from the
# client jar's en_us.json). Mostly the challenge frames. Left out: what a Server First already posts (Hero of
# the Village, Free the End, Sky's the Limit, Cover Me in Debris), what the rules ban (Postmortal: totems; The
# End... Again...: end crystals), and the easy or lucky ones (It Spreads, Bullseye, Subspace Bubble...).
CHALLENGES = {
    "minecraft:adventure/kill_all_mobs": "Monsters Hunted",
    "minecraft:adventure/adventuring_time": "Adventuring Time",
    "minecraft:adventure/sniper_duel": "Sniper Duel",
    "minecraft:adventure/arbalistic": "Arbalistic",
    "minecraft:adventure/trim_with_all_exclusive_armor_patterns": "Smithing with Style",
    "minecraft:husbandry/balanced_diet": "A Balanced Diet",
    "minecraft:husbandry/bred_all_animals": "Two by Two",
    "minecraft:husbandry/complete_catalogue": "A Complete Catalogue",
    "minecraft:husbandry/whole_pack": "The Whole Pack",
    "minecraft:husbandry/obtain_netherite_hoe": "Serious Dedication",
    "minecraft:nether/all_effects": "How Did We Get Here?",
    "minecraft:nether/all_potions": "A Furious Cocktail",
    "minecraft:nether/explore_nether": "Hot Tourist Destinations",
    "minecraft:nether/uneasy_alliance": "Uneasy Alliance",
    "minecraft:nether/return_to_sender": "Return to Sender",
    "minecraft:nether/create_full_beacon": "Beaconator",
    "minecraft:end/dragon_egg": "The Next Generation",
}
CHALLENGE_LINE = "{p} completed {title}. First this season."

WAR_LINES = {"declare": f"War: {{a}} declared a {diplomacy.WAR_DAYS}-day war on {{b}}.",
             "peace": "{a} and {b} ended their war with a pact, {ka} to {kb}."}
SIEGE_OPEN = ("Outpost siege open until {end} Pacific: capture an outpost for a bonus hour held. Faction claims "
              "stay protected. `/trigger sieges` in game.")
SIEGE_CLOSED = "The outpost siege is over: captures earn no bonus until the next one."

FIRST, CHALLENGE, FACTION, WAR, SIEGE, EVENT = "first", "challenge", "faction", "war", "siege", "event"
KINDS = [EVENT, FIRST, CHALLENGE, FACTION, WAR, SIEGE]   # found at the same time: posted in this order
LIMITS = {FIRST: 4, CHALLENGE: 2, FACTION: 2, WAR: 3, SIEGE: 2, EVENT: 3}   # posts of each kind in any 24 hours
KEPT = {WAR}       # kinds whose item stays news when the world drops it (the log is trimmed at Sunday's close)
DAILY = 8                                        # posts in all in any 24 hours
PER_RUN = 2                                      # posts per run (the timer runs every 10 minutes)
STALE = dt.timedelta(days=3)                     # waiting longer than this: dropped, never posted
SETTLE = dt.timedelta(minutes=15)                # a challenge waits this long after it is first seen
LATE = dt.timedelta(hours=3)                     # a launch or a gap in the runs longer than this: baseline
SAVE_LAG = dt.timedelta(minutes=10)              # how far a saved file can trail the game (5-minute autosave)
FACTIONS_LISTED = 8                              # names in one faction line, then "and N more"
GAP_SECONDS = 1.0                                # between two posts in a run (Discord's webhook rate limit)
DAY = dt.timedelta(days=1)
CLOSE_FRESH = 180                                # minutes a siege window's close stays news

PENDING, SENDING, POSTED, DROPPED, BASELINE = "pending", "sending", "posted", "dropped", "baseline"

# ---------------------------------------------------------------- reading the saved world


@dataclass(frozen=True)
class Item:
    key: str               # "first:dragon", "challenge:minecraft:adventure/kill_all_mobs", "faction:<party id>"
    kind: str              # FIRST, CHALLENGE or FACTION
    text: str              # the line (a faction: its name and leader, joined into a line when posted)
    at: str | None = None  # when it happened, when the world says (a challenge); ISO
    order: int = 0         # a first's claim order, so firsts found in the same run post in the order claimed


@dataclass(frozen=True)
class Saved:
    """What every source needs from the saved world, read once a run."""
    season: int                          # `#season rw.day`, 1 when unset
    launched: bool                       # `#launched rw.day` is 1
    scores: dict[str, dict[str, int]]    # the saved scoreboard
    names: dict[str, str]                # usercache.json: player UUID -> name


def read_saved(world: Path) -> Saved:
    board = saved_world.scoreboard(world)
    scores = board.scores if board else {}
    holder, objective = LAUNCHED.split()
    return Saved(scores.get("rw.day", {}).get("#season", 0) or 1, scores.get(objective, {}).get(holder, 0) >= 1,
                 scores, standings.usernames(world))


def first_items(world: Path, saved: Saved) -> list[Item]:
    return [Item(f"{FIRST}:{f.id}", FIRST, FIRST_LINES[f.id].format(p=md(f.player)), order=f.order)
            for f in firsts.holders(world, saved.scores) if f.id in FIRST_LINES]


def challenge_items(world: Path, since: dt.datetime, saved: Saved) -> list[Item]:
    """For each of CHALLENGES, the player who finished it earliest at or after `since` (a player not in
    usercache.json is passed over: no name to post)."""
    done = saved_world.advancements(world, set(CHALLENGES))
    names = saved.names
    found = []
    for adv, title in CHALLENGES.items():
        times = sorted((when, uuid) for uuid, have in done.items() if (when := have.get(adv)) and when >= since
                       and uuid.lower() in names)
        if times:
            when, uuid = times[0]
            found.append(Item(f"{CHALLENGE}:{adv}", CHALLENGE,
                              CHALLENGE_LINE.format(p=md(names[uuid.lower()]), title=title), at=iso(when)))
    return found


def faction_items(world: Path, saved: Saved) -> list[Item]:
    """Every faction, named as standings.read_parties names it: the party's name, else "<leader>'s faction". A
    party file without an owner is left out."""
    items = []
    for p in saved_world.parties(world) or []:
        if p.owner is None:
            continue
        leader = saved.names.get(p.owner.uuid, p.owner.username or p.owner.uuid[:8])
        items.append(Item(f"{FACTION}:{p.id}", FACTION,
                          json.dumps({"name": p.name or f"{leader}'s faction", "leader": leader})))
    return items


def war_items(world: Path) -> list[Item]:
    """The 7-day wars' declarations and ends in the diplomacy log (the Sunday close trims it, so the saved world
    has each for a week at most)."""
    storage = diplomacy.saved_storage(world)
    every = diplomacy.post_names(storage)

    def name(n) -> str:
        return md(every.get(int(n)) or f"faction {n}")
    items = []
    for e in storage.get("diplomacy", {}).get("log", []):
        if not isinstance(e, dict) or "n" not in e:
            continue
        kind, a, b = e.get("kind"), name(e.get("a", 0)), name(e.get("b", 0))
        if kind == "declare":
            line = WAR_LINES["declare"].format(a=a, b=b)
        elif kind == "war_end" and e.get("how") == "peace":
            line = WAR_LINES["peace"].format(a=a, b=b, ka=diplomacy.kill_count(int(e.get("ka", 0))),
                                          kb=int(e.get("kb", 0)))
        elif kind == "war_end" and (said := diplomacy.war_end_line(e, name)):
            line = f"{said[0].upper()}{said[1:]}."
        else:
            continue
        items.append(Item(f"{WAR}:{int(e['n'])}", WAR, line, order=int(e["n"])))
    return items


def siege_items(saved: Saved) -> list[Item]:
    """A siege window open now (#open sg), and one that closed in the last CLOSE_FRESH minutes of game time
    (#closed sg, the minute; #now sg is the game's minute when the world was saved). Nothing while they're off."""
    sg = saved.scores.get(sieges.OBJ, {})
    if sg.get("#on") != 1:
        return []
    items = []
    if sg.get("#open") == 1 and (opened := sg.get("#opened")):
        # #opened can trail the window's start by a minute (the game's clock counts on between syncs): the
        # window open a minute later is the one, and its scheduled end is the one to say.
        end = sieges.window(dt.datetime.fromtimestamp((opened + 1) * 60, UTC))[1]
        items.append(Item(f"{SIEGE}:open:{opened}", SIEGE, SIEGE_OPEN.format(
            end=season_calendar.clock(end.astimezone(season_calendar.PACIFIC)))))
    closed, now = sg.get("#closed"), sg.get("#now")
    if sg.get("#open") != 1 and closed and now is not None and 0 <= now - closed <= CLOSE_FRESH:
        items.append(Item(f"{SIEGE}:closed:{closed}", SIEGE, SIEGE_CLOSED))


def event_items(world: Path, saved: Saved) -> list[Item]:
    """The border boss (each act's rising and its end) and the finale's winner, from their command storage."""
    outcomes = boss.outcomes(world)
    won = finale.result(world, saved.scores)
    if not outcomes and not won:
        return []
    names = diplomacy.names(world)

    def faction(n: int) -> str:
        return md(names.get(n, f"faction {n}"))
    items = []
    for o in outcomes:
        if o.act < 1:
            continue
        if o.state == "risen":
            items.append(Item(f"{EVENT}:boss{o.act}:rose", EVENT, f"{boss.NAME} has risen near {o.x}, {o.z}, past "
                              "the old border. The first to slay it takes a Server First.", order=o.act))
        elif o.state == "slain":
            by = md(o.player or "A player") + (f" of {faction(o.faction)}" if o.faction else "")
            items.append(Item(f"{EVENT}:boss{o.act}:end", EVENT, f"{by} slew {boss.NAME}.", order=o.act))
        elif o.state == "left":
            items.append(Item(f"{EVENT}:boss{o.act}:end", EVENT, f"{boss.NAME} left: nobody slew it this time.",
                              order=o.act))
    if won and won.faction and not won.tie:
        items.append(Item(f"{EVENT}:finale", EVENT, f"The finale: {faction(won.faction)} held the monument and "
                          f"won, with {won.points} points.", order=99))
    return items


# What reading a source can raise on a half-saved or changing world: saved_world's ValueError, a file gone or
# unreadable mid-read (a party disbanded while it was listed), tomllib missing on an old python.
UNREADABLE = (ValueError, OSError, ImportError)


def found(world: Path, since: dt.datetime, saved: Saved) -> tuple[list[Item], list[str]]:
    """Every news item the saved world holds now, and the sources that couldn't be read (the next run tries
    again)."""
    items, failed = [], []
    for name, read in ((FIRST, lambda: first_items(world, saved)),
                       (CHALLENGE, lambda: challenge_items(world, since, saved)),
                       (FACTION, lambda: faction_items(world, saved)),
                       (WAR, lambda: war_items(world)),
                       (SIEGE, lambda: siege_items(saved)),
                       (EVENT, lambda: event_items(world, saved))):
        try:
            items += read()
        except UNREADABLE as e:
            standings.warn(f"could not read the {name}s: {type(e).__name__}: {e}")
            failed.append(name)
    return items, failed


# ---------------------------------------------------------------- the season's state


def state_file(state_dir: Path, season: int) -> Path:
    return state_dir / f"season-{season}.json"


def write_state(path: Path, state: dict) -> None:
    standings.write_json(path, state)


def iso(when: dt.datetime) -> str:
    return when.astimezone(UTC).isoformat()


def parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text)


def new_state(season: int, now: dt.datetime) -> dict:
    """A season's file as its first run makes it, launched or not. "unlaunched" is the last run that saw the
    world before its launch, "launched" the first that saw it launched, "since" when challenges count from."""
    return {"season": season, "made": iso(now), "last_run": None, "unlaunched": None, "launched": None,
            "since": None, "late": None, "items": {}, "posts": [], "sending": None}


def remember(state: dict, record: dict, now: dt.datetime) -> None:
    """Adds a post to the posts the limits count (kept 7 days)."""
    state["posts"] = [*[q for q in state["posts"] if now - parse(q["at"]) < 7 * DAY], record]


def recover(state: dict, now: dt.datetime) -> list[str]:
    """A post left "sending" (the run was killed mid-post) counts as posted, limits included: never post twice."""
    notes = []
    record = state.get("sending")
    if record:
        for key in record["keys"]:
            state["items"][key].update(status=POSTED, posted=record["at"])
        remember(state, record, now)
        state["sending"] = None
        notes.append(f"{', '.join(record['keys'])} was being posted when a run stopped: counted as posted, "
                     "not sent again")
    for key, entry in state["items"].items():
        if entry["status"] == SENDING:   # a file written without its "sending" record
            entry.update(status=POSTED, posted=iso(now))
            remember(state, {"at": iso(now), "kind": entry["kind"], "keys": [key]}, now)
            notes.append(f"{key} was being posted when a run stopped: counted as posted, not sent again")
    return notes


def merge(state: dict, items: list[Item], now: dt.datetime, failed: list[str], baseline: bool) -> list[str]:
    """Adds the items not seen before (pending, or baseline: never posted) and updates a pending one whose line
    changed. A pending item the world no longer has (a first staff reopened, a faction disbanded) is marked gone
    and waits, unless its source couldn't be read this run. Returns what it noted."""
    notes = []
    keys = {item.key for item in items}
    for key, entry in state["items"].items():
        if entry["status"] == PENDING and entry["kind"] not in failed and entry["kind"] not in KEPT:
            entry["gone"] = key not in keys
    for item in items:
        old = state["items"].get(item.key)
        if old is None:
            state["items"][item.key] = {"kind": item.kind, "text": item.text, "at": item.at, "order": item.order,
                                        "seen": iso(now), "status": BASELINE if baseline else PENDING}
        elif old["status"] == PENDING and item.text != old["text"]:
            # not posted yet: an earlier finish saved late, a first reopened and claimed again, a faction renamed
            notes.append(f"{item.key}: changed before it posted, now: {item.text}")
            old.update(text=item.text, at=item.at)
    return notes


def expire(state: dict, now: dt.datetime) -> list[str]:
    notes = []
    for key, entry in state["items"].items():
        if entry["status"] == PENDING and now - parse(entry["seen"]) > STALE:
            entry["status"] = DROPPED
            notes.append(f"{key} waited over {STALE.days} days: dropped, never posted")
    return notes


def advance(state: dict, world: Path, saved: Saved, now: dt.datetime) -> tuple[list[str], list[str], bool]:
    """One run's look at the world: what it noted, the sources it couldn't read, and whether anything may post.

    Before the launch it only notes the run. The first run that sees the world launched dates the season: on
    time when a run saw it unlaunched less than LATE before (the launch was in between), so challenges count from
    then; otherwise (the feed turned on mid-season) late, and what is already there is baseline. A run more than
    LATE after the last one (the feed was off) keeps what turned up meanwhile as baseline too. Either of those
    waits for a run that can read every source, so nothing old slips through as new."""
    notes = recover(state, now)
    if not saved.launched:
        state.update(unlaunched=iso(now), last_run=iso(now))
        notes.append(f"season {saved.season} hasn't launched (#launched rw.day): nothing posts yet")
        return notes, [], False
    starting = state["launched"] is None
    gap = bool(state["last_run"]) and now - parse(state["last_run"]) > LATE
    if starting:
        late = state["unlaunched"] is None or now - parse(state["unlaunched"]) > LATE
        since = now - SAVE_LAG if late else parse(state["unlaunched"]) - SAVE_LAG
    else:
        late, since = state["late"], parse(state["since"])
    items, failed = found(world, since, saved)
    if (starting or gap) and failed:
        notes.append("waiting for a run that can read every source before deciding what is old news")
        return notes, failed, False
    if starting:
        state.update(launched=iso(now), since=iso(since), late=late)
    baseline = (starting and late) or gap
    count = len(state["items"])
    notes += merge(state, items, now, failed, baseline)
    if baseline:
        why = "a late start" if starting else "the feed was off"
        notes.append(f"{why}: {len(state['items']) - count} item(s) already in the world kept as baseline, "
                     "not posted")
    notes += expire(state, now)
    state["last_run"] = iso(now)
    return notes, failed, True


# ---------------------------------------------------------------- what posts now


@dataclass(frozen=True)
class Post:
    kind: str
    keys: list[str]
    text: str


def faction_line(entries: list[dict]) -> str:
    factions = [json.loads(e["text"]) for e in entries]
    if len(factions) == 1:
        f = factions[0]
        if f["name"] == f"{f['leader']}'s faction":   # an unnamed party
            return f"New faction: {md(f['name'])}."
        return f"New faction: {md(f['name'])}, led by {md(f['leader'])}."
    return f"New factions: {listed([md(f['name']) for f in factions], FACTIONS_LISTED)}."


def recent(state: dict, now: dt.datetime) -> list[dict]:
    return [p for p in state["posts"] if now - parse(p["at"]) < DAY]


def due(state: dict, now: dt.datetime) -> tuple[list[Post], list[str]]:
    """What this run posts, and why the rest of the pending items wait. Pure: changes nothing."""
    last_day = recent(state, now)
    used = {kind: sum(p["kind"] == kind for p in last_day) for kind in LIMITS}
    room = min(PER_RUN, DAILY - len(last_day))

    def happened(key_entry):   # when it happened (a challenge) or was found; same time: by kind, then claim order
        key, entry = key_entry
        return parse(entry["at"] or entry["seen"]), KINDS.index(entry["kind"]), entry.get("order", 0), key
    pending = sorted(((k, e) for k, e in state["items"].items() if e["status"] == PENDING), key=happened)
    posts, waiting = [], []
    factions = [(k, e) for k, e in pending if e["kind"] == FACTION and not e.get("gone")]
    for key, entry in pending:
        kind = entry["kind"]
        if entry.get("gone"):
            waiting.append(f"{key}: no longer in the world (reopened or disbanded): not posted while it isn't")
            continue
        if kind == FACTION and key != factions[0][0]:
            continue   # every pending faction goes in the line of the first
        if kind == CHALLENGE and now - parse(entry["seen"]) < SETTLE:
            waiting.append(f"{key}: settling (an earlier finish may still be saved)")
            continue
        if room <= 0:
            waiting.append(f"{key}: over the limit for now ({PER_RUN} a run, {DAILY} a day)")
            continue
        if used[kind] >= LIMITS[kind]:
            waiting.append(f"{key}: over the limit for {kind}s ({LIMITS[kind]} a day)")
            continue
        if kind == FACTION:
            posts.append(Post(kind, [k for k, _ in factions], faction_line([e for _, e in factions])))
        else:
            posts.append(Post(kind, [key], entry["text"]))
        used[kind] += 1
        room -= 1
    return posts, waiting


def send(url: str, content: str, urlopen=urllib.request.urlopen) -> tuple[str | None, bool]:
    """Posts `content`, pinging nobody (a faction can be named @everyone). Returns what went wrong, never the URL
    or anything that could hold it, and whether Discord may have posted it anyway: once the request is out and
    the answer is lost (a timeout, the connection dropped) or is a server error, it may have, so the caller
    counts it as posted rather than risk posting it twice."""
    if not url.startswith("https://"):
        return "the webhook setting is not an https:// URL", False
    body = json.dumps({"content": content, "allowed_mentions": {"parse": []}}).encode()
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": "MonkeySMP-news/1"})
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.HTTPError as e:   # Discord answered: a 4xx is a refusal, a 5xx may have posted
        return f"Discord answered HTTP {e.code}", e.code >= 500
    except urllib.error.URLError as e:     # while connecting or sending: urllib wraps those
        return f"could not reach Discord ({type(e.reason).__name__})", False
    except (OSError, http.client.HTTPException) as e:   # sent, but no whole answer
        return f"no answer from Discord after sending ({type(e).__name__})", True
    except ValueError as e:
        return f"could not post ({type(e).__name__})", False
    return None, False


# ---------------------------------------------------------------- the commands


def webhook() -> str:
    return os.environ.get("NEWS_WEBHOOK_URL", "")


def look(world: Path) -> Saved | None:
    try:
        return read_saved(world)
    except UNREADABLE as e:
        standings.warn(f"could not read the saved scoreboard or usercache: {type(e).__name__}: {e}")
        return None


def show_found(world: Path) -> int:
    saved = look(world)
    if saved is None:
        return 1
    items, failed = found(world, dt.datetime.min.replace(tzinfo=UTC), saved)
    print(f"Season {saved.season}, {'launched' if saved.launched else 'not launched yet: nothing posts'} "
          "(challenges: the earliest finish in the world, test play included)")
    for item in items:
        text = faction_line([{"text": item.text}]) if item.kind == FACTION else item.text
        print(f"  {item.key}: {text}")
    if not items:
        print("  nothing yet")
    return 1 if failed else 0


def preview(world: Path, state_dir: Path | None, now: dt.datetime) -> int:
    saved = look(world)
    if saved is None:
        return 1
    path = state_file(state_dir, saved.season) if state_dir else None
    state = (standings.read_json(path) if path else None) or new_state(saved.season, now)
    if not path or not path.exists():
        print(f"no news file for season {saved.season} yet: the next run makes it")
    notes, failed, ready = advance(state, world, saved, now)
    for note in notes:
        print(note)
    if not ready:
        return 1 if failed else 0
    posts, waiting = due(state, now)
    print("would post now:" if posts else "would post nothing now")
    for p in posts:
        print(f"  {p.text}")
    for w in waiting:
        print(f"  waiting: {w}")
    return 1 if failed else 0


def post(world: Path, state_dir: Path, now: dt.datetime, url: str, urlopen=urllib.request.urlopen,
         sleep=time.sleep) -> int:
    if not url:
        print("no NEWS_WEBHOOK_URL set: not posting")
        return 0
    saved = look(world)
    if saved is None:
        return 1
    path = state_file(state_dir, saved.season)
    state = standings.read_json(path) or new_state(saved.season, now)
    notes, failed, ready = advance(state, world, saved, now)
    for note in notes:
        print(note)
    write_state(path, state)
    if not ready:
        return 1 if failed else 0
    posts, waiting = due(state, now)
    for w in waiting:
        print(f"waiting: {w}")
    for i, p in enumerate(posts):
        if i:
            sleep(GAP_SECONDS)
        record = {"at": iso(now), "kind": p.kind, "keys": p.keys}
        for key in p.keys:
            state["items"][key]["status"] = SENDING
        state["sending"] = record
        write_state(path, state)
        problem, maybe_sent = send(url, p.text, urlopen)
        state["sending"] = None
        if problem and not maybe_sent:
            for key in p.keys:
                state["items"][key]["status"] = PENDING
            write_state(path, state)
            print(f"could not post to Discord: {problem}; the next run tries again", file=sys.stderr)
            return 1
        for key in p.keys:
            state["items"][key].update(status=POSTED, posted=iso(now))
        remember(state, record, now)
        write_state(path, state)
        if problem:
            print(f"Discord may have posted it ({problem}): counted as posted, never sent again: {p.text}",
                  file=sys.stderr)
            return 1
        print(f"posted: {p.text}")
    if not posts:
        print("nothing to post")
    return 1 if failed else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Monkey SMP news: notable moments to the Discord channel.")
    sub = ap.add_subparsers(dest="command", required=True)
    f = sub.add_parser("found", help="every news item the saved world holds now; changes nothing")
    f.add_argument("world", type=Path, help="the world folder (server/world)")
    for name, about in (("preview", "what the next run would post; changes nothing"),
                        ("post", "posts what is due to NEWS_WEBHOOK_URL")):
        s = sub.add_parser(name, help=about)
        s.add_argument("world", type=Path, help="the world folder (server/world)")
        s.add_argument("--state", type=Path, required=name == "post", help="the folder of season-<n>.json files")
    args = ap.parse_args(argv)
    if not args.world.is_dir():
        print(f"no world folder at {args.world}")
        return 2
    now = dt.datetime.now(UTC)
    if args.command == "found":
        return show_found(args.world)
    if args.command == "preview":
        return preview(args.world, args.state, now)
    return post(args.world, args.state, now, webhook())


if __name__ == "__main__":
    sys.exit(main())
