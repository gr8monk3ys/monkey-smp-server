"""Weekly faction standings: one rank for every faction (an Open Parties and Claims party), from four columns.

Each column gives the faction a share of its weight, in proportion to the column's leader, rounded:

    Cup points (ev.cup, the whole season so far)     40
    land (chunks its members have claimed)           20
    Strength (its members' levels added up)          20
    PvP kills by its members this week               20   (a war enemy's count twice: tools/diplomacy.py)
    + 5 for each bounty a member claimed this week

so the leader of every column would have 100 (plus bounties). Ties on points go to more Cup points, then
more kills; still tied, they share the rank. docs/SEASONS.md, "Weekly standings", says it for players.

    python tools/standings.py show WORLD [--state DIR]   this week so far, printed (changes nothing)
    python tools/standings.py start WORLD --state DIR    starts the first week, if none is running
    python tools/standings.py board WORLD --state DIR --docker DIR
                                                         this week so far and last week's final table on
                                                         the in-game board, and each faction's number in
                                                         game (tools/diplomacy.py)
    python tools/standings.py close WORLD --state DIR --docker DIR
                                                         ends the week: keeps its final table, starts the
                                                         next, updates the board, says so in chat and
                                                         posts the table to Discord
    python tools/datapacks.py                            regenerates the realms-standings data pack (with the others)

WORLD is the live world folder (server/world). Everything is read from the files the server saves (every 5
minutes, and when it stops), never from RCON, which can't list parties or scores:
  data/openpartiesandclaims/parties/*.nbt          each party: its owner and members
  data/openpartiesandclaims/player-claims/*.nbt    each player's claimed chunks
  data/openpartiesandclaims/player-configs/*.toml  the party name (the owner's parties.name setting)
  data/minecraft/scoreboard.dat                     ev.cup, Strength, st.kills, st.warkills and st.bounty
  data/realms/command_storage.dat                    the faction numbers and the week's war and pacts
  ../usercache.json                                  players' current names
Kills and bounties count from a snapshot the week starts with (STATE/week.json); each closed week is kept
in STATE/weeks/. RCON is used only to write the board, through the container's own `realms rcon` (it finds
the password itself) in DIR, the release's docker folder. The Discord webhook is STANDINGS_WEBHOOK_URL in the
environment, else DISCORD_WEBHOOK_URL; it is never printed. deploy/realms-standings.sh runs this on the VPS.

The data pack (package/realms/datapacks/realms-standings/, generated: edit this file, not it) counts PvP
kills outside the event arena (st.kills), holds claimed bounties (st.bounty), shows the board in chat with
/trigger standings and on text displays staff place at spawn, and has the staff bounty commands
(docs/ADMIN.md). Stdlib only (Python 3.11 or newer, for tomllib).
"""
import argparse
import datetime as dt
import json
import os
import sys
import unicodedata
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

import diplomacy
import outposts
import saved_world
import season_calendar
from datapacks import NS, function_tag, lines, mcmeta, text
from events import ARENA_TAG, CUP, LEVEL, STRENGTH
from rcon import LIMIT, Docker, RconError
from repo import Repo

DATAPACK = "realms-standings"
FN = f"data/{NS}/function/standings"
STORE = f"{NS}:standings"   # command storage: week, last (written by this tool) and board (built from them)

WEIGHTS = (("cup", 40), ("land", 20), ("strength", 20), ("kills", 20))
BOUNTY_POINTS = 5
KILLS = "st.kills"
BOUNTY = "st.bounty"
MIN_WEEK_DAYS = 3     # close leaves a week younger than this alone: it was closed already (a retry, or a re-run)
TOP = 10              # factions on the board and in the Discord post
LAST_TOP = 5          # factions in last week's table on the board
NAME_LIMIT = 20       # characters of a faction's name on the board
DISCORD_LIMIT = 2000
FORMULA = ("Cup 40, land 20, Strength 20, kills this week 20 (a war enemy's count twice), each as a share of the "
           "leader; +5 a bounty; +1 an hour holding an outpost (at most 20).")


# ---------------------------------------------------------------- reading the world


def norm(text: str) -> str:
    """What names are matched on: letters and digits, lower case."""
    return "".join(c for c in text.casefold() if c.isalnum())


@dataclass
class Party:
    id: str
    name: str
    owner: str
    members: list[str]   # current names, the owner first
    uuids: list[str]


@dataclass
class World:
    parties: list[Party]
    claims: dict[str, int]                # player UUID -> chunks claimed
    scores: dict[str, dict[str, int]]     # objective -> holder -> score
    labels: dict[str, str]                # Cup holder -> the name staff gave it (cup/faction)
    numbers: dict[str, int] = field(default_factory=dict)   # party id -> faction number (tools/diplomacy.py)


def usernames(world: Path) -> dict[str, str]:
    cache = world.parent / "usercache.json"
    if not cache.is_file():
        return {}
    try:
        entries = json.loads(cache.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {str(e["uuid"]).lower(): e["name"] for e in entries if isinstance(e, dict) and "uuid" in e and "name" in e}


def read_parties(world: Path, names: dict[str, str]) -> list[Party]:
    found = saved_world.parties(world)
    if found is None:
        warn(f"no {world / saved_world.PARTIES}: no factions (has a party been made with /openpac?)")
        return []
    parties = []
    for p in found:
        if p.owner is None:
            warn(f"{p.id}.nbt has no owner: left out")
            continue
        members = [names.get(m.uuid, m.username or m.uuid[:8]) for m in p.members]
        owner = members[0]
        parties.append(Party(p.id, p.name or f"{owner}'s faction", owner, members, [m.uuid for m in p.members]))
    return parties


def read_claims(world: Path) -> dict[str, int]:
    """Chunks claimed by each player, in every dimension; a claims file not named by a UUID is left out."""
    claims = {}
    for name, chunks in saved_world.claim_counts(world).items():
        try:
            claims[saved_world.uuid_text(name)] = chunks
        except ValueError:
            continue
    return claims


def read_scoreboard(world: Path) -> tuple[dict[str, dict[str, int]], dict[str, str]]:
    board = saved_world.scoreboard(world)
    if board is None:
        raise SystemExit(f"no scoreboard at {saved_world.scoreboard_path(world)}: give the world folder (server/world)")
    labels = {holder: name.strip() for holder, name in board.displays.get(CUP, {}).items()}
    return board.scores, labels


def read_world(world: Path) -> World:
    if not world.is_dir():
        raise SystemExit(f"{world} is not a folder: give the world folder (server/world)")
    scores, labels = read_scoreboard(world)
    return World(read_parties(world, usernames(world)), read_claims(world), scores, labels,
                 diplomacy.numbers(world))


# ---------------------------------------------------------------- the table


@dataclass
class Row:
    name: str
    members: list[str] = field(default_factory=list)
    cup: int = 0
    land: int = 0
    strength: int = 0
    kills: int = 0
    bounties: int = 0
    outposts: int = 0     # whole hours an outpost was held this week (tools/outposts.py)
    points: int = 0
    rank: int = 0


def share(value: int, leader: int, weight: int) -> int:
    """weight * value / leader, rounded half up; nothing for a column nobody has anything in."""
    if leader <= 0 or value <= 0:
        return 0
    return (2 * weight * value + leader) // (2 * leader)


def rank(rows: list[Row]) -> list[Row]:
    """Points and rank for every row, best first."""
    leaders = {col: max((max(getattr(r, col), 0) for r in rows), default=0) for col, _ in WEIGHTS}
    for r in rows:
        r.points = sum(share(getattr(r, col), leaders[col], w) for col, w in WEIGHTS) + BOUNTY_POINTS * r.bounties
        r.points += outposts.points(r.outposts)

    def key(r: Row) -> tuple[int, int, int]:
        return (r.points, r.cup, r.kills)
    rows.sort(key=lambda r: (*(-k for k in key(r)), r.name.casefold()))
    for r in rows:
        r.rank = 1 + sum(1 for o in rows if key(o) > key(r))
    return rows


def match_cup(world: World, warn) -> tuple[dict[str, int], list[Row]]:
    """Cup points by party id, matching each Cup entry's id or name to a party's name or its owner's name.
    An entry that matches no party, or more than one, becomes a row of its own with only its Cup points."""
    keys: dict[str, set[str]] = {}
    for p in world.parties:
        for k in {norm(p.name), norm(p.owner)} - {""}:
            keys.setdefault(k, set()).add(p.id)
    matched: dict[str, int] = {}
    loose = []
    for holder, points in sorted(world.scores.get(CUP, {}).items()):
        if holder.startswith("#"):
            continue
        label = world.labels.get(holder) or holder
        hits = set().union(*(keys.get(k, set()) for k in {norm(holder), norm(label)} - {""}))
        if len(hits) == 1:
            pid = hits.pop()
            matched[pid] = matched.get(pid, 0) + points
        elif points:
            why = "matches no faction's name" if not hits else "matches more than one faction"
            warn(f'Cup entry {holder} ("{label}") {why}: listed on its own. Name it as the faction is named '
                 f'in /openpac (function realms:events/cup/faction).')
            loose.append(Row(label, cup=points))
    return matched, loose


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


def table(world: World, baseline: dict | None, warn=lambda msg: None) -> list[Row]:
    """This week's rows: Cup, land and Strength as they are now, kills and bounties since `baseline`."""
    base = baseline or {}
    scores = world.scores
    kills, kills_then = scores.get(KILLS, {}), base.get("kills", {})
    war, war_then = scores.get(diplomacy.WARKILLS, {}), base.get("warkills", {})
    bounty, bounty_then = folded(scores.get(BOUNTY, {})), folded(base.get("bounty", {}))
    cup, rows = match_cup(world, warn)
    for p in world.parties:
        row = Row(p.name, list(p.members), cup=cup.get(p.id, 0), land=sum(world.claims.get(u, 0) for u in p.uuids))
        for name in p.members:
            arena = scores.get(STRENGTH, {})
            row.strength += arena[name] if name in arena else scores.get(LEVEL, {}).get(name, 0)
            row.kills += gained(kills.get(name, 0), kills_then.get(name, 0))
            row.kills += gained(war.get(name, 0), war_then.get(name, 0))   # a war enemy's kill counts twice
            row.bounties += gained(bounty.get(name.lower(), 0), bounty_then.get(name.lower(), 0))
        row.outposts = outposts.hours(scores, base.get("outposts"), world.numbers.get(p.id))
        rows.append(row)
    return rank(rows)


def table_text(rows: list[Row], limit: int | None = None) -> list[str]:
    """The table in fixed-width columns (for a terminal and a Discord code block)."""
    shown = rows if limit is None else rows[:limit]
    bounty = any(r.bounties for r in shown)
    held = any(r.outposts for r in shown)
    head = f"{'#':>2}  {'Faction':<18} {'Points':>6} {'Cup':>5} {'Land':>5} {'Str':>4} {'Kills':>5}"
    out = [head + (f" {'Bounty':>6}" if bounty else "") + (f" {'Hold':>4}" if held else "")]
    for r in shown:
        name = r.name.replace("`", "'")
        name = name if len(name) <= 18 else name[:17] + "~"
        line = f"{r.rank:>2}  {name:<18} {r.points:>6} {r.cup:>5} {r.land:>5} {r.strength:>4} {r.kills:>5}"
        out.append(line + (f" {r.bounties:>6}" if bounty else "") + (f" {r.outposts:>4}" if held else ""))
    if not rows:
        out.append("    no factions yet")
    elif limit is not None and len(rows) > limit:
        out.append(f"    and {len(rows) - limit} more")
    return out


# ---------------------------------------------------------------- the week


def day(when: dt.datetime) -> str:
    return f"{when:%a} {when.day} {when:%b}"


def clock(when: dt.datetime) -> str:
    return f"{day(when)}, {when.strftime('%I %p').lstrip('0')}"


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def write_json(path: Path, data: dict) -> None:
    """Written whole or not at all, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def snapshot(world: World, now: dt.datetime) -> dict:
    """A new week's starting point: every player's kills (and war kills) and bounties so far."""
    return {"start": now.isoformat(timespec="seconds"),
            "kills": dict(sorted(world.scores.get(KILLS, {}).items())),
            "warkills": dict(sorted(world.scores.get(diplomacy.WARKILLS, {}).items())),
            "bounty": dict(sorted(world.scores.get(BOUNTY, {}).items())),
            "outposts": outposts.baseline(world.scores)}


def week_file(state: Path) -> Path:
    return state / "week.json"


def latest_week(state: Path) -> Path | None:
    weeks = sorted((state / "weeks").glob("*.json")) if (state / "weeks").is_dir() else []
    return weeks[-1] if weeks else None


def since(week: dict | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(week["start"]) if week and week.get("start") else None


def span(closed: dict) -> str:
    """'week of Sun 25 Oct to Sun 1 Nov' for a closed week."""
    end, begun = dt.datetime.fromisoformat(closed["end"]), since(closed)
    return f"week of {day(begun)} to {day(end)}" if begun else f"week ending {day(end)}"


# ---------------------------------------------------------------- the in-game board


def board_name(name: str) -> str:
    """A name the board can show: plain ASCII (the RCON path is), no quotes, at most NAME_LIMIT characters."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = " ".join("".join(c if c.isalnum() or c in " _'!?,-&%*():" else " " for c in text).split())
    return text if len(text) <= NAME_LIMIT else text[:NAME_LIMIT - 1].rstrip() + "~"


def board_line(r: Row) -> str:
    name = board_name(r.name) or board_name(r.members[0] if r.members else "") or "?"
    line = f"{r.rank}. {name}: {r.points}  [Cup {r.cup}, land {r.land}, Str {r.strength}, kills {r.kills}"
    line += f", bounties {r.bounties}" if r.bounties else ""
    return line + (f", outposts {r.outposts}h]\n" if r.outposts else "]\n")


def section(head: str, rows: list[Row], top: int) -> dict:
    """A text component: a gray heading, then a line for each of the first `top` rows."""
    extra = [{"text": head + "\n", "color": "gray"}]
    extra += [{"text": board_line(r), "color": "gold" if r.rank == 1 else "white"} for r in rows[:top]]
    if not rows:
        extra.append({"text": "No factions yet.\n", "color": "white"})
    elif len(rows) > top:
        extra.append({"text": f"...and {len(rows) - top} more\n", "color": "gray"})
    return {"text": "", "extra": extra}


def snbt(value) -> str:
    """SNBT for what the board needs: compounds with plain keys, lists, strings, ints and booleans."""
    if isinstance(value, bool):
        return "1b" if value else "0b"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(value, list):
        return "[" + ",".join(snbt(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(f"{k}:{snbt(v)}" for k, v in value.items()) + "}"
    raise TypeError(f"no SNBT for {value!r}")


def store_command(key: str, head: str, rows: list[Row], top: int) -> str:
    """The command that puts one table in the storage, with fewer rows if all of them don't fit RCON."""
    for n in range(min(top, len(rows)), -1, -1):
        command = f"data modify storage {STORE} {key} set value {snbt(section(head, rows, n))}"
        if len(command.encode()) <= LIMIT:
            return command
    raise ValueError("the board heading alone is too long for RCON")


def board_commands(rows: list[Row], week: dict | None, last: dict | None, now: dt.datetime) -> list[str]:
    start = since(week)
    head = f"This week so far ({'since ' + day(start) if start else 'since the standings began'}, " \
           f"updated {clock(now)})"
    commands = [store_command("week", head, rows, TOP)]
    if last:
        commands.append(store_command("last", f"Final standings, {span(last)}", [Row(**r) for r in last["rows"]],
                                      LAST_TOP))
    commands.append(f"function {NS}:standings/publish")
    return commands


def update_board(rcon, rows: list[Row], week: dict | None, last: dict | None, now: dt.datetime) -> None:
    for command in board_commands(rows, week, last, now):
        rcon(command)


# ---------------------------------------------------------------- Discord


def discord_message(week: dict) -> str:
    rows = [Row(**r) for r in week["rows"]]
    head = [f"**Faction standings, {span(week)}**", "```", *table_text(rows, TOP), "```"]
    foot = f"Scored as {FORMULA} `/trigger standings` shows the board in game."
    room = DISCORD_LIMIT - len("\n".join([*head, foot]))   # what's left for the war and pacts lines
    message = "\n".join([*head, *diplomacy.discord_lines(week, room), foot])
    if len(message) <= DISCORD_LIMIT:
        return message
    cut = message[:DISCORD_LIMIT - 4]
    return cut + "\n```" if cut.count("```") % 2 else message[:DISCORD_LIMIT]   # never leave a code block open


def webhook() -> str:
    return os.environ.get("STANDINGS_WEBHOOK_URL") or os.environ.get("DISCORD_WEBHOOK_URL") or ""


def post_discord(url: str, content: str, urlopen=urllib.request.urlopen) -> str | None:
    """Posts `content`, pinging nobody (a faction can be named @everyone). Returns what went wrong, never
    the URL or anything that could hold it."""
    if not url.startswith("https://"):
        return "the webhook setting is not an https:// URL"
    body = json.dumps({"content": content, "allowed_mentions": {"parse": []}}).encode()
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": "MonkeySMP-standings/1"})
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.HTTPError as e:
        return f"Discord answered HTTP {e.code}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return f"could not reach Discord ({type(e).__name__})"
    return None


# ---------------------------------------------------------------- the commands


def warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


def show(world: Path, state: Path | None, now: dt.datetime) -> int:
    week = read_json(week_file(state)) if state else None
    begun = since(week)
    print(f"Faction standings this week so far ({'since ' + clock(begun) if begun else 'no week running'}; "
          f"{clock(now)})")
    print("\n".join(table_text(table(read_world(world), week, warn))))
    print(f"Scored as {FORMULA}")
    return 0


def start(world: Path, state: Path, now: dt.datetime) -> int:
    week = read_json(week_file(state))
    if week:
        begun = since(week)
        print(f"a week is already running{', since ' + clock(begun) if begun else ''}: nothing to do")
        return 0
    write_json(week_file(state), snapshot(read_world(world), now))
    print(f"started the first week at {clock(now)} ({week_file(state)})")
    return 0


def sync_factions(rcon, folder: Path, data: World) -> int:
    """Each faction's number, owner and name in game (tools/diplomacy.py), from the parties as read. A party file
    read_parties left out (no owner) is one diplomacy can't tell about, so it keeps what it has in game."""
    factions = [diplomacy.Faction(p.id, board_name(p.name) or board_name(p.owner) or p.id[:8], p.members)
                for p in data.parties]
    unsure = frozenset(p.id for p in saved_world.parties(folder) or [] if p.owner is None)
    return diplomacy.sync(rcon, factions, data.scores, folder, warn, unsure)


def board(world: Path, state: Path, rcon, now: dt.datetime) -> int:
    week = read_json(week_file(state))
    last_path = latest_week(state)
    data = read_world(world)
    status = 0
    try:   # never in the board's way: the board goes up whatever happens here
        sent = sync_factions(rcon, world, data)
        if sent:
            print(f"factions in game: {sent} change(s) sent")
    except (RconError, OSError, ValueError) as e:
        print(f"could not write the factions in game: {e}", file=sys.stderr)
        status = 1
    try:
        update_board(rcon, table(data, week, warn), week, read_json(last_path) if last_path else None, now)
    except RconError as e:
        print(f"could not update the in-game board: {e}", file=sys.stderr)
        return 1
    print(f"board updated ({clock(now)})")
    return status


def close(world: Path, state: Path, rcon, now: dt.datetime, url: str, urlopen=urllib.request.urlopen) -> int:
    """Ends the week (unless it began under MIN_WEEK_DAYS ago, so a re-run or a retry closes nothing twice), then
    does whatever the newest closed week still lacks: the board, the chat announcement, the Discord post."""
    week = read_json(week_file(state))
    start_ = since(week)
    data = read_world(world)
    rows = table(data, week, warn)
    if start_ is None or now - start_ >= dt.timedelta(days=MIN_WEEK_DAYS):
        before = latest_week(state)
        try:
            storage = diplomacy.saved_storage(world)
        except (OSError, ValueError) as e:   # the war and pacts lines are extra: the close goes on without them
            warn(f"{e}: this week's war and pacts are left out of the post (the next one has them)")
            storage = None
        said = diplomacy.report(storage, data.scores, (read_json(before) or {}) if before else {})
        closed = {"start": week.get("start") if week else None, "end": now.isoformat(timespec="seconds"),
                  "formula": FORMULA, "rows": [asdict(r) for r in rows], "announced": False, "posted": False,
                  **said, "wars_ended": False, "war_ends": diplomacy.week_end(data.scores, said["diplomacy_seq"])}
        path = state / "weeks" / f"{now:%Y-%m-%d}.json"
        write_json(path, closed)
        week = snapshot(data, now)
        write_json(week_file(state), week)
        print(f"closed the week ({path}); a new one starts now")
        print("\n".join(table_text(rows)))
        rows = table(data, week)   # the new week: no kills or bounties yet
    else:
        print(f"this week began {clock(start_)}, under {MIN_WEEK_DAYS} days ago: not closing it (a re-run or a "
              "retry); finishing the last closed week, if anything is left")
    path = latest_week(state)
    last = read_json(path) if path else None
    if path is None or last is None:
        return 0
    status = 0
    try:
        update_board(rcon, rows, week, last, now)
        if last.get("announced"):
            print("board updated (already announced in chat)")
        else:
            rcon(f"function {NS}:standings/announce")
            last["announced"] = True
            write_json(path, last)
            print("board updated and announced in chat")
    except RconError as e:
        print(f"could not update the in-game board: {e}", file=sys.stderr)
        status = 1
    if not last.get("wars_ended", True):   # a week closed before diplomacy has no wars to end
        try:   # the closed week's own wars (war_ends), so a late retry never ends one of the new week
            for command in diplomacy.batch_commands(last.get("war_ends") or []):
                rcon(command)
            last["wars_ended"] = True
            write_json(path, last)
            print("the week's wars are over")
        except RconError as e:
            print(f"could not end the week's wars: {e}", file=sys.stderr)
            status = 1
    if last.get("posted"):
        print("already posted to Discord")
    elif not url:
        print("no STANDINGS_WEBHOOK_URL or DISCORD_WEBHOOK_URL set: not posting to Discord")
    else:
        problem = post_discord(url, discord_message(last), urlopen)
        if problem:
            print(f"could not post to Discord: {problem}", file=sys.stderr)
            status = 1
        else:
            last["posted"] = True
            write_json(path, last)
            print("posted to Discord")
    return status


# ---------------------------------------------------------------- the data pack


HEADER = {"text": "Faction standings\n", "color": "gold", "bold": True}
FOOTER = {"text": f"\nScored as {FORMULA}\n/trigger standings shows this in chat.", "color": "dark_gray"}
EMPTY_WEEK = {"text": "", "extra": [{"text": "No standings yet: the first come out on Sunday evening.\n",
                                     "color": "gray"}]}
BOARD_TAG = "st.board"
DISPLAY = "minecraft:text_display"
TITLE = ("bounty_hunter", "red", "[Bounty Hunter] ")

HELP = [("place", "stand where the board goes, at spawn"), ("remove", "next to the board"),
        ('bounty/post {target:"Alex"}', "one of the top Strength holders"),
        ('bounty/claim {hunter:"Steve",target:"Alex"}', "once staff have checked the kill")]


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    f["pack.mcmeta"] = mcmeta("Monkey SMP weekly faction standings, bounties, war and pacts (generated by "
                              "tools/standings.py and tools/diplomacy.py)")
    f["data/minecraft/tags/function/load.json"] = function_tag(f"{NS}:standings/load", f"{NS}:diplomacy/load")
    f["data/minecraft/tags/function/tick.json"] = function_tag(f"{NS}:standings/tick", f"{NS}:diplomacy/tick")
    team, color, prefix = TITLE
    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/standings.py. Scores, storage and the team are kept across restarts.",
        "scoreboard objectives add st.pk playerKillCount",
        f"scoreboard objectives add {KILLS} dummy",
        f"scoreboard objectives add {BOUNTY} dummy",
        "scoreboard objectives add st.ver dummy",
        "scoreboard objectives add standings trigger",
        "# The bounty title: a team, like the supporter titles (docs/RETENTION.md). It lasts the season.",
        f"team add {team}",
        f"team modify {team} color {color}",
        f"team modify {team} prefix " + text({"text": prefix, "color": color}),
        "# Hunters are often rivals: the title must not let them see each other while invisible.",
        f"team modify {team} seeFriendlyInvisibles false",
        f"execute unless data storage {STORE} week run data modify storage {STORE} week set value {snbt(EMPTY_WEEK)}",
        f'execute unless data storage {STORE} last run data modify storage {STORE} last set value {{text:""}}',
        f"function {NS}:standings/publish",
        f"schedule function {NS}:standings/second 20t replace",
    )
    f[f"{FN}/tick.mcfunction"] = lines(
        "# PvP kills count for the standings, except in the event arena (its fights are for the Cup).",
        f"execute as @a[scores={{st.pk=1..}},tag=!{ARENA_TAG}] run scoreboard players operation @s {KILLS} += @s st.pk",
        "scoreboard players set @a[scores={st.pk=1..}] st.pk 0",
        f"execute as @a[scores={{standings=1..}}] run function {NS}:standings/use",
    )
    f[f"{FN}/second.mcfunction"] = lines(
        f"schedule function {NS}:standings/second 20t replace",
        "scoreboard players enable @a standings",
        "# A board whose chunk was unloaded when the standings changed catches up once it is loaded again.",
        f"execute as @e[type={DISPLAY},tag={BOARD_TAG}] unless score @s st.ver = #board st.ver run function "
        f"{NS}:standings/refresh",
    )
    f[f"{FN}/use.mcfunction"] = lines(
        "# Runs as a player who used /trigger standings.",
        "scoreboard players set @s standings 0",
        "scoreboard players enable @s standings",
        "tellraw @s " + text({"nbt": "board", "storage": STORE, "interpret": True}),
    )
    f[f"{FN}/publish.mcfunction"] = lines(
        "# Builds the board from the two tables tools/standings.py writes (week: this week so far; last: last",
        "# week's final standings), then every board display picks it up within a second.",
        f"data modify storage {STORE} board set value {snbt({'text': '', 'extra': [HEADER]})}",
        f"data modify storage {STORE} board.extra append from storage {STORE} week",
        f'data modify storage {STORE} board.extra append value {{text:"\\n"}}',
        f"data modify storage {STORE} board.extra append from storage {STORE} last",
        f"data modify storage {STORE} board.extra append value {snbt(FOOTER)}",
        "scoreboard players add #board st.ver 1",
    )
    f[f"{FN}/refresh.mcfunction"] = lines(
        "# Runs as a board display that is behind.",
        f"data modify entity @s text set from storage {STORE} board",
        "scoreboard players operation @s st.ver = #board st.ver",
    )
    f[f"{FN}/announce.mcfunction"] = lines(
        "# tools/standings.py close runs this once the week's final table is on the board.",
        "tellraw @a " + text({"text": "The week's faction standings are in.\n", "color": "gold"},
                             {"nbt": "last", "storage": STORE, "interpret": True},
                             {"text": "/trigger standings shows the whole board.", "color": "gray"}),
    )
    f[f"{FN}/place.mcfunction"] = lines(
        "# Run by staff standing where the board goes (spawn). It turns to face whoever reads it.",
        f"summon {DISPLAY} ~ ~1.5 ~ {{Tags:[\"{BOARD_TAG}\"],billboard:\"vertical\",alignment:\"left\","
        "line_width:400}",
        "tellraw @s " + text({"text": "Standings board placed. To move it, run standings/remove next to it and "
                                      "place it again.", "color": "green"}),
    )
    f[f"{FN}/remove.mcfunction"] = lines(
        "# Run by staff next to a board: removes the boards within 5 blocks.",
        f"kill @e[type={DISPLAY},tag={BOARD_TAG},distance=..5]",
    )
    f.update(bounty_files())
    f.update(diplomacy.datapack_files())
    f[f"{FN}/help.mcfunction"] = help_function(f)
    return {k: v if v.endswith("\n") else v + "\n" for k, v in f.items()}


def bounty_files() -> dict[str, str]:
    """The bounty board (docs/SEASONS.md, the event catalog): staff post a bounty on a top Strength holder, and the
    player who kills them in a fair fight gets a title and standings points. Nothing sold, nothing for combat."""
    f: dict[str, str] = {}
    team = TITLE[0]
    f[f"{FN}/bounty/post.mcfunction"] = lines(
        "# Macro {target:\"Alex\"}: posts a bounty in chat.",
        "$tellraw @a " + text({"text": "Bounty posted on ", "color": "gold"}, {"text": "$(target)", "color": "white"},
                              {"text": ". Kill them in a fair fight outside the arena, then tell staff: the Bounty "
                                       f"Hunter title, and +{BOUNTY_POINTS} standings points for your faction this "
                                       "week.", "color": "gray"}),
    )
    f[f"{FN}/bounty/claim.mcfunction"] = lines(
        "# Macro {hunter:\"Steve\",target:\"Alex\"}, once staff have checked the kill: a bounty for Steve's",
        f"# faction this week (+{BOUNTY_POINTS} standings points), and the Bounty Hunter title if Steve shows no",
        "# other (a supporter color or title is never taken away for it). Run by staff in game, so the notes",
        "# reach them; over RCON only the chat line shows.",
        "tag @s add st.staff",
        f"$scoreboard players add $(hunter) {BOUNTY} 1",
        "$tellraw @a " + text({"text": "Bounty claimed: ", "color": "gold"},
                              {"text": "$(hunter)", "color": "white"},
                              {"text": " took the bounty on ", "color": "gray"},
                              {"text": "$(target)", "color": "white"},
                              {"text": f". +{BOUNTY_POINTS} standings points for their faction this week, and the "
                                       "Bounty Hunter title.", "color": "gray"}),
        f"$execute as $(hunter) if entity @s[team=] run team join {team} @s",
        f"$execute as $(hunter) unless entity @s[team={team}] run tellraw @a[tag=st.staff] " + text(
            {"text": "$(hunter) shows another title, so it stays. If they would rather show Bounty Hunter: "
                     f"team join {team} $(hunter)", "color": "yellow"}),
        "$execute unless entity $(hunter) run tellraw @a[tag=st.staff] " + text(
            {"text": "$(hunter) is offline: the points count. For the title, when they are on and show no "
                     f"other: team join {team} $(hunter)", "color": "yellow"}),
        "tag @s remove st.staff",
    )
    return f


def help_function(files: dict[str, str]) -> str:
    out = ["# Lists the staff commands; click one to put it in the chat box.",
           "tellraw @s " + text({"text": "Standings and bounty commands (docs/ADMIN.md):", "color": "gold"})]
    for cmd, note in HELP:
        path = cmd.split(" ")[0]
        assert f"{FN}/{path}.mcfunction" in files, path
        out.append("tellraw @s " + text(
            {"text": f" {cmd}", "color": "aqua",
             "click_event": {"action": "suggest_command", "command": f"/function {NS}:standings/{cmd}"}},
            {"text": f"  {note}", "color": "dark_gray"}))
    return lines(*out)


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.realms / "datapacks" / DATAPACK: datapack_files()}


# ---------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Weekly faction standings.")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, about in (("show", "print this week so far (changes nothing)"),
                        ("start", "start the first week, if none is running"),
                        ("board", "put this week so far and last week's table on the in-game board"),
                        ("close", "end the week: keep its table, start the next, board, chat and Discord")):
        p = sub.add_parser(name, help=about)
        p.add_argument("world", type=Path, help="the world folder (server/world)")
        p.add_argument("--state", type=Path, required=name != "show",
                       help="where the week's snapshot and the closed weeks are kept")
        if name in ("board", "close"):
            p.add_argument("--docker", type=Path, required=True, help="the release's docker folder (for RCON)")
    args = ap.parse_args(argv)
    now = season_calendar.now()
    if args.command == "show":
        return show(args.world, args.state, now)
    if args.command == "start":
        return start(args.world, args.state, now)
    rcon = Docker(args.docker)
    if args.command == "board":
        return board(args.world, args.state, rcon, now)
    return close(args.world, args.state, rcon, now, webhook())


if __name__ == "__main__":
    sys.exit(main())
