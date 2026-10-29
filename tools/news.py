"""Monkey SMP news: one plain line in the Discord channel when something notable happens on the live server.

    python tools/news.py found WORLD                  every news item the saved world holds now; changes nothing
    python tools/news.py preview WORLD --state DIR    what the next run would post, and what waits; changes nothing
    python tools/news.py post WORLD --state DIR       posts what is due to NEWS_WEBHOOK_URL (deploy/realms-news.sh)

What gets posted, at most once a season each (docs/ADMIN.md, "Monkey SMP news"):
  - a Server First from FIRST_LINES (tools/firsts.py's milestones, not all of them): "Steve killed the Ender
    Dragon. First this season." The firsts pack decides who holds it (after the launch, not in the arena, not
    in creative...), so this only reads its claims (firsts.holders).
  - the first on the server this season to finish one of CHALLENGES, rare vanilla advancements the firsts don't
    cover: "Steve completed Monsters Hunted. First this season." Read from each player's saved advancements
    (players/advancements/<uuid>.json), which keep the time each was done, so the first is the earliest one done
    since the season's launch, whoever's file was saved first.
  - new factions (Open Parties and Claims parties), several in one line: "New faction: Red Wolves, led by Steve."

Everything comes from the files the server saves (every 5 minutes, ServerCore's autosave-interval-seconds), so a
post lands 5 to 25 minutes after the moment. Nothing posts before the launch (`#launched rw.day`, set by
realms:rules/launch). No RCON and no log: the firsts pack announces in game with tellraw, which never reaches
the server log, and the saved files are the record the pack and the season already keep.

The rules that keep it rare, all in LIMITS and the constants below it: per kind and in all, at most so many posts
in any 24 hours, and a few per run; what is over a limit waits for a later run, in the order it happened, and is
dropped (never posted) once it is STALE days old. A challenge waits SETTLE minutes first, so a player whose file
was saved later but who did it earlier still gets it.

The state is one JSON file per season in DIR (season-<n>.json, n being the world's `#season rw.day`, 1 when
unset): every item seen and whether it was posted. A new season is a new world and a new file, so "first this
season" starts again by itself. The file is written whole before and after each post, and an item found marked
"sending" (the run was killed mid-post) counts as posted: a post can be lost that way, never made twice. The
first run of a season makes the file; if that is later than LATE after the season's launch (the feed was turned
on mid-season), everything already in the world is kept as "baseline" and never posted, so old news doesn't
flood the channel.

The webhook is NEWS_WEBHOOK_URL in the environment (deploy/realms-news.sh reads it from /etc/realms-deploy.env);
it is never printed. Posts ping nobody. Stdlib only, Python 3.11 or newer (party names are TOML).
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import firsts
import saved_world
import season_calendar
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

FIRST, CHALLENGE, FACTION = "first", "challenge", "faction"
KINDS = [FIRST, CHALLENGE, FACTION]             # found at the same time: posted in this order
LIMITS = {FIRST: 4, CHALLENGE: 2, FACTION: 2}   # posts of each kind in any 24 hours
DAILY = 6                                        # posts in all in any 24 hours
PER_RUN = 2                                      # posts per run (the timer runs every 10 minutes)
STALE = dt.timedelta(days=3)                     # waiting longer than this: dropped, never posted
SETTLE = dt.timedelta(minutes=15)                # a challenge waits this long after it is first seen
LATE = dt.timedelta(hours=3)                     # a season's file made later than this after its launch: baseline
FACTIONS_LISTED = 8                              # names in one faction line, then "and N more"
GAP_SECONDS = 1.0                                # between two posts in a run (Discord's webhook rate limit)
DAY = dt.timedelta(days=1)

PENDING, SENDING, POSTED, DROPPED, BASELINE = "pending", "sending", "posted", "dropped", "baseline"

# ---------------------------------------------------------------- reading the saved world


@dataclass(frozen=True)
class Item:
    key: str               # "first:dragon", "challenge:minecraft:adventure/kill_all_mobs", "faction:<party id>"
    kind: str              # FIRST, CHALLENGE or FACTION
    text: str              # the line (a faction: its name and leader, joined into a line when posted)
    at: str | None = None  # when it happened, when the world says (a challenge); ISO
    order: int = 0         # a first's claim order, so firsts found in the same run post in the order claimed


def warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


def season_of(world: Path) -> tuple[int, bool]:
    """The world's season number (`#season rw.day`, 1 when unset) and whether it has launched."""
    board = saved_world.scoreboard(world)
    day = board.scores.get("rw.day", {}) if board else {}
    holder, objective = LAUNCHED.split()
    launched = board.scores.get(objective, {}).get(holder, 0) >= 1 if board else False
    return day.get("#season", 0) or 1, launched


def first_items(world: Path) -> list[Item]:
    return [Item(f"{FIRST}:{f.id}", FIRST, FIRST_LINES[f.id].format(p=md(f.player)), order=f.order)
            for f in firsts.holders(world) if f.id in FIRST_LINES]


def challenge_items(world: Path, since: dt.datetime) -> list[Item]:
    """For each of CHALLENGES, the player who finished it earliest at or after `since` (a player not in
    usercache.json is passed over: no name to post)."""
    done = saved_world.advancements(world, set(CHALLENGES))
    names = standings.usernames(world)
    found = []
    for adv, title in CHALLENGES.items():
        times = sorted((when, uuid) for uuid, have in done.items() if (when := have.get(adv)) and when >= since
                       and uuid.lower() in names)
        if times:
            when, uuid = times[0]
            found.append(Item(f"{CHALLENGE}:{adv}", CHALLENGE,
                              CHALLENGE_LINE.format(p=md(names[uuid.lower()]), title=title),
                              at=when.astimezone(UTC).isoformat()))
    return found


def faction_items(world: Path) -> list[Item]:
    if saved_world.parties(world) is None:
        return []
    return [Item(f"{FACTION}:{p.id}", FACTION, json.dumps({"name": p.name, "leader": p.owner}))
            for p in standings.read_parties(world, standings.usernames(world))]


def found(world: Path, since: dt.datetime) -> tuple[list[Item], list[str]]:
    """Every news item the saved world holds now, and the sources that couldn't be read (a damaged or half-saved
    file: the next run tries again)."""
    items, failed = [], []
    for name, read in ((FIRST, lambda: first_items(world)), (CHALLENGE, lambda: challenge_items(world, since)),
                       (FACTION, lambda: faction_items(world))):
        try:
            items += read()
        except ValueError as e:
            warn(f"could not read the {name}s: {e}")
            failed.append(name)
    return items, failed


# ---------------------------------------------------------------- the season's state


def state_file(state_dir: Path, season: int) -> Path:
    return state_dir / f"season-{season}.json"


def read_state(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def write_state(path: Path, state: dict) -> None:
    standings.write_json(path, state)


def iso(when: dt.datetime) -> str:
    return when.astimezone(UTC).isoformat()


def parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text)


def new_state(season: int, now: dt.datetime, launch: dt.datetime, state_dir: Path | None) -> dict:
    """A season's file as its first launched run makes it. "since" is when challenges count from: the launch
    (Season I's is season_calendar.LAUNCH), so test play before it never counts, or for a late start an hour
    before this run, so old finishes don't post. Later seasons' launch dates aren't in the calendar: their file
    is on time when the last season's file is there (the feed ran through the change, so this run is within
    minutes of the launch), and counts from an hour before it."""
    if season == 1:
        late = now > launch + LATE
        since = now - dt.timedelta(hours=1) if late else launch
    else:
        late = not (state_dir and state_file(state_dir, season - 1).exists())
        since = now - dt.timedelta(hours=1)
    return {"season": season, "started": iso(now), "since": iso(since), "late": late, "items": {}, "posts": []}


def cutoff(state: dict) -> dt.datetime:
    return parse(state["since"])


def merge(state: dict, items: list[Item], now: dt.datetime, failed: list[str] = ()) -> list[str]:
    """Adds the items not seen before (pending, or baseline in a late season file's first run) and updates a
    pending one whose line changed. A pending item the world no longer has (a first staff reopened, a faction
    disbanded) is marked gone and waits, unless its source couldn't be read this run. Returns what it noted."""
    notes = []
    first_run = not state["items"]
    keys = {item.key for item in items}
    for key, entry in state["items"].items():
        if entry["status"] == PENDING and entry["kind"] not in failed:
            entry["gone"] = key not in keys
    for item in items:
        old = state["items"].get(item.key)
        if old is None:
            status = BASELINE if first_run and state.get("late") else PENDING
            state["items"][item.key] = {"kind": item.kind, "text": item.text, "at": item.at, "order": item.order,
                                        "seen": iso(now), "status": status}
        elif old["status"] == PENDING and item.text != old["text"]:
            # not posted yet: an earlier finish saved late, a first reopened and claimed again, a faction renamed
            notes.append(f"{item.key}: changed before it posted, now: {item.text}")
            old.update(text=item.text, at=item.at)
    return notes


def recover(state: dict) -> list[str]:
    """An item left "sending" (the run was killed mid-post) counts as posted: never post twice."""
    notes = []
    for key, entry in state["items"].items():
        if entry["status"] == SENDING:
            entry["status"] = POSTED
            notes.append(f"{key} was being posted when a run stopped: counted as posted, not sent again")
    return notes


def expire(state: dict, now: dt.datetime) -> list[str]:
    notes = []
    for key, entry in state["items"].items():
        if entry["status"] == PENDING and now - parse(entry["seen"]) > STALE:
            entry["status"] = DROPPED
            notes.append(f"{key} waited over {STALE.days} days: dropped, never posted")
    return notes


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
        if f["name"] == f"{f['leader']}'s faction":   # an unnamed party (standings.read_parties names it so)
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


# ---------------------------------------------------------------- the commands


def webhook() -> str:
    return os.environ.get("NEWS_WEBHOOK_URL", "")


def load(world: Path, state_dir: Path | None, now: dt.datetime,
         launch: dt.datetime) -> tuple[int, bool, dict, Path | None]:
    season, launched = season_of(world)
    path = state_file(state_dir, season) if state_dir else None
    state = (read_state(path) if path else None) or new_state(season, now, launch, state_dir)
    return season, launched, state, path


def show_found(world: Path, launch: dt.datetime) -> int:
    season, launched = season_of(world)
    items, failed = found(world, launch if season == 1 else dt.datetime.min.replace(tzinfo=UTC))
    print(f"Season {season}, {'launched' if launched else 'not launched yet: nothing posts'}")
    for item in items:
        text = faction_line([{"text": item.text}]) if item.kind == FACTION else item.text
        print(f"  {item.key}: {text}")
    if not items:
        print("  nothing yet")
    return 1 if failed else 0


def preview(world: Path, state_dir: Path | None, now: dt.datetime, launch: dt.datetime) -> int:
    season, launched, state, path = load(world, state_dir, now, launch)
    if not launched:
        print(f"Season {season} hasn't launched (#launched rw.day): nothing posts")
        return 0
    items, failed = found(world, cutoff(state))
    notes = recover(state) + merge(state, items, now, failed) + expire(state, now)
    posts, waiting = due(state, now)
    if not path or not path.exists():
        print(f"no news file for season {season} yet: the next run makes it"
              + (" and keeps what is already there as baseline (a late start)" if state.get("late") else ""))
    for note in notes:
        print(note)
    print("would post now:" if posts else "would post nothing now")
    for p in posts:
        print(f"  {p.text}")
    for w in waiting:
        print(f"  waiting: {w}")
    return 1 if failed else 0


def post(world: Path, state_dir: Path, now: dt.datetime, launch: dt.datetime, url: str,
         urlopen=None, sleep=time.sleep) -> int:
    if not url:
        print("no NEWS_WEBHOOK_URL set: not posting")
        return 0
    season, launched, state, path = load(world, state_dir, now, launch)
    if not launched:
        print(f"season {season} hasn't launched: nothing to post")
        return 0
    items, failed = found(world, cutoff(state))
    if failed and not path.exists():
        print("not making the season's news file until every source can be read (the next run tries again)",
              file=sys.stderr)
        return 1
    notes = recover(state) + merge(state, items, now, failed) + expire(state, now)
    for note in notes:
        print(note)
    if not path.exists() and state.get("late"):
        print(f"late start: {len(state['items'])} item(s) already in the world kept as baseline, not posted")
    write_state(path, state)
    posts, waiting = due(state, now)
    for w in waiting:
        print(f"waiting: {w}")
    status = 1 if failed else 0
    for i, p in enumerate(posts):
        if i:
            sleep(GAP_SECONDS)
        for key in p.keys:
            state["items"][key]["status"] = SENDING
        write_state(path, state)
        problem = standings.post_discord(url, p.text, **({"urlopen": urlopen} if urlopen else {}))
        for key in p.keys:
            entry = state["items"][key]
            entry["status"] = PENDING if problem else POSTED
            if not problem:
                entry["posted"] = iso(now)
        if not problem:
            state["posts"] = [*[q for q in state["posts"] if now - parse(q["at"]) < 7 * DAY],
                              {"at": iso(now), "kind": p.kind, "keys": p.keys}]
        write_state(path, state)
        if problem:
            print(f"could not post to Discord: {problem}", file=sys.stderr)
            return 1
        print(f"posted: {p.text}")
    if not posts:
        print("nothing to post")
    return status


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
    now, launch = dt.datetime.now(UTC), season_calendar.LAUNCH
    if args.command == "found":
        return show_found(args.world, launch)
    if args.command == "preview":
        return preview(args.world, args.state, now, launch)
    return post(args.world, args.state, now, launch, webhook())


if __name__ == "__main__":
    sys.exit(main())
