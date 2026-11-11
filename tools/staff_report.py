"""The staff page's weekly rule check: per player, which of the server's rules the logs show they broke that week.

    python3 tools/staff_report.py show LIVE_DIR [--week 2026-W45] [--reports DIR]
                                                  prints a week's report, the week so far by default (changes nothing)
    python3 tools/staff_report.py write LIVE_DIR --out DIR [--week 2026-W45]
                                                  writes DIR/2026-W45.json for the last whole week, and the players'
                                                  stats as they are now as DIR/stats/2026-W45.json; a week already
                                                  written is skipped (deploy/monkey-report.sh, Mondays)

LIVE_DIR is the running release's folder. The staff page's Reports tab shows the files (GET /api/reports and
/api/report?week=, tools/staff_panel.py); docs/LIVE.md, "The staff page", says how to read them. A week is an ISO week,
Monday 12 AM to the next Monday 12 AM Pacific: Ledger's and the game log's times are both Pacific.

It only reports. It never punishes, messages a player or rolls anything back: every cell is something for staff to
look at, with the rows it came from. Each finding has a confidence, said in a word and shown by the cell's look:

    clear     the logs show it plainly (an ender pearl thrown, bedrock broken)
    likely    the logs show it, but something they can't see could explain it (the exact launch minute, a trade)
    unclear   worth a look, no more (a pickup, a shared connection, a high x-ray ratio)

What it reads, all read-only:
- Ledger's world/ledger.sqlite, opened with mode=ro. Only the week's rows are asked for, and never by scanning the
  table (18 minutes on 7.8 GB): the players' own rows through Ledger's player_id index (a few hundred thousand a
  season), and portal blocks through the old_object_id index, each with the week's times. The time index alone is no
  good here: Dynamic Lights writes about 40 million light/air rows a day (source "command"), which are left out.
- world/players/stats/*.json. These count from the player's first join, so each write also keeps the counts as they
  are then (DIR/stats/WEEK.json); a week's numbers are the change from the newest earlier copy. With none, they are
  everything so far, and the report says so. The copy is taken when the job runs, a little after the week ends.
- Open Parties and Claims' parties (world/data/openpartiesandclaims/parties/*.nbt, tools/nbt.py), usercache.json, and
  the game's logs (logs/*.log.gz and latest.log).
Accounts that share one connection come out as names only: each address is hashed with a key made for this run and
forgotten with it, so no address, nor anything that could lead back to one, is ever written or shown.

    {"version": 1, "week": "2026-W45", "from": "2026-11-02 00:00", "to": "2026-11-09 00:00", "made": "...Z",
     "checks": [{"id": "pearls", "title": "Ender pearls", "rule": "B3"}, ...],
     "players": [{"name": "Alpha", "cells": {"pearls": {"count": 3, "level": "clear", "what": "thrown",
                  "evidence": [{"time": null, "world": null, "pos": null, "what": "...", "level": "clear"}],
                  "more": 0}}}],
     "clean": [{"id": "theft", "title": "Chest takes", "rule": "rule 39", "result": "none from another faction"}],
     "skipped": [{"id": "...", "title": "...", "why": "..."}], "notes": ["..."], "mining": [...],
     "sources": {"ledger": "read", "stats": "...", "parties": 4, "logs": 3}}

Stdlib only (plus tools/), Python 3.10 or newer, so it runs on the VPS from the checkout.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import secrets
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import status as public

import nbt
import rcon as server
import season_calendar as calendar

VERSION = 1
WEEK = re.compile(r"(\d{4})-W(\d{2})")
CLEAR, LIKELY, UNCLEAR = "clear", "likely", "unclear"
RANK = {UNCLEAR: 1, LIKELY: 2, CLEAR: 3}
EVIDENCE_KEPT = 40
SPAWN_RADIUS = 160          # blocks from the world spawn that count as spawn for B11
GRACE = dt.timedelta(hours=48)
LAUNCH_HOUR = dt.timedelta(hours=1)
CAGE_AFTER = dt.timedelta(minutes=3)
CAGE_BLOCKS = {"obsidian", "crying_obsidian", "netherrack"}
DROP_WITHIN = dt.timedelta(seconds=30)    # a time-out this soon before dying of cowardice: a network drop
TRADE_WITHIN = dt.timedelta(seconds=60)
TRADE_BLOCKS = 6
FACTION_MAX = 4
GROUP_LINK = 3              # uses of the other's chests or drops, each way, that tie two factions together
STONE = {"stone", "deepslate", "netherrack", "tuff", "andesite", "diorite", "granite", "basalt", "blackstone",
         "cobblestone", "cobbled_deepslate"}
DIAMOND = {"diamond_ore", "deepslate_diamond_ore"}
XRAY_STONE = 500            # mined at least this much stone to be compared
XRAY_ORES = 10
XRAY_TIMES = 3              # times the median rate
XRAY_RATE = 15.0            # per 1,000 stone, when too few players mined to compare
WORLD_NAMES = {"minecraft:overworld": "Overworld", "minecraft:the_nether": "Nether", "minecraft:the_end": "End"}
NETHERITE = ("netherite_helmet", "netherite_chestplate", "netherite_leggings", "netherite_boots")
# The stats kept in a copy: (stat kind, item), each without its minecraft: prefix.
STATS = [("used", "ender_pearl"), ("used", "enchanted_golden_apple"), ("used", "totem_of_undying"),
         ("used", "end_crystal"), *(("crafted", n) for n in NETHERITE),
         *(("picked_up", n) for n in ("ender_pearl", "enchanted_golden_apple", "totem_of_undying", "end_crystal",
                                      *NETHERITE))]

# id, column title, the rule, and what a week with none of it says.
CHECKS = [
    ("portal", "Portal trap", "rules 4, 7", "no portal broken and caged"),
    ("pearls", "Ender pearls", "B3", "none thrown"),
    ("gapples", "Enchanted gapples", "B5", "none eaten"),
    ("totems", "Totems", "B4", "none used"),
    ("crystals", "End crystals", "B7", "none placed"),
    ("netherite", "Netherite armor", "rule 24", "none crafted"),
    ("launch", "Kill in launch hour", "rule 23", "no player kills in the launch hour"),
    ("grace", "Kill in first 48 h", "rule 26", "no kills on a player in their first 48 hours"),
    ("combatlog", "Combat logging", "rule 3", "nobody died of cowardice"),
    ("theft", "Chest takes", "rule 39", "nothing taken from another faction's chests"),
    ("faction", "Faction over 4", "rule 29", "every party has 4 or fewer"),
    ("group", "Group over 4", "rule 32", "no group of more than 4 shares chests or trades"),
    ("sharing", "Shared connection", "rule 21", "each account on its own connection"),
    ("xray", "X-ray ratio", "B15", "no outliers"),
    ("tnt", "TNT at spawn", "B11", "no TNT placed near spawn"),
    ("bedrock", "Bedrock broken", "rules 44, 45", "none broken"),
    ("roof", "Nether roof", "rule 46", "nobody above the roof"),
]
TITLES = {c[0]: c for c in CHECKS}
STAT_CHECKS = {"pearls", "gapples", "totems", "crystals", "netherite"}
LEDGER_CHECKS = {"portal", "theft", "group", "xray", "tnt", "bedrock", "roof"}
LOG_CHECKS = {"launch", "grace", "combatlog", "sharing"}

_LOG_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})-(\d+)\.log\.gz")
_LOG_LINE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\] \[Server thread/INFO\]: (.*)$")
_LOGIN = re.compile(r"^([A-Za-z0-9_]{3,16})\[/(.+):\d+\] logged in with entity id")
_LOST = re.compile(r"^([A-Za-z0-9_]{3,16}) lost connection: (.*)$")
_COWARD = re.compile(r"^([A-Za-z0-9_]{3,16}) has died of cowardice$")
_EXTRA = re.compile(r'count:(\d+)\b.*?id:"([^"]+)"|id:"([^"]+)".*?count:(\d+)\b')


# ---------------------------------------------------------------- weeks and times


def week_name(day: dt.date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def week_bounds(name: str) -> tuple[dt.datetime, dt.datetime]:
    """The week's Monday 12 AM and the next one's, Pacific, without a time zone (as Ledger and the log write them)."""
    m = WEEK.fullmatch(name)
    if not m:
        raise ValueError(f"{name!r} is not a week like 2026-W45")
    start = dt.datetime.combine(dt.date.fromisocalendar(int(m[1]), int(m[2]), 1), dt.time())
    return start, start + dt.timedelta(days=7)


def pacific_now(now: dt.datetime) -> dt.datetime:
    return now.astimezone(calendar.PACIFIC).replace(tzinfo=None)


def launch() -> dt.datetime:
    return calendar.LAUNCH.astimezone(calendar.PACIFIC).replace(tzinfo=None)


def stamp(when: dt.datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M:%S")


def ledger_time(text: str) -> dt.datetime:
    return dt.datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- the grid


class Grid:
    """The cells: (player, check) -> counts per confidence and the rows they came from."""

    def __init__(self):
        self.cells: dict[tuple[str, str], dict] = {}

    def add(self, player: str, check: str, level: str, what: str, rows: list[dict], count: int = 1) -> None:
        cell = self.cells.setdefault((player, check), {"counts": Counter(), "what": {}, "evidence": []})
        cell["counts"][level] += count
        cell["what"].setdefault(level, what)
        for row in rows:
            cell["evidence"].append({**row, "level": level})

    def flagged(self, check: str) -> bool:
        return any(c == check for _, c in self.cells)

    def players(self) -> list[dict]:
        rows: dict[str, dict] = defaultdict(dict)
        for (player, check), cell in self.cells.items():
            level = max(cell["counts"], key=RANK.__getitem__)
            evidence = sorted(cell["evidence"], key=lambda r: (-RANK[r["level"]], r.get("time") or ""))
            also = {lv: cell["counts"][lv] for lv in sorted(cell["counts"], key=RANK.__getitem__, reverse=True)
                    if lv != level and cell["counts"][lv]}
            rows[player][check] = {"count": cell["counts"][level], "level": level, "what": cell["what"][level],
                                   "also": also, "evidence": evidence[:EVIDENCE_KEPT],
                                   "more": max(0, len(evidence) - EVIDENCE_KEPT)}

        def weight(item):
            cells = item[1].values()
            return (-sum(RANK[c["level"]] ** 2 for c in cells), item[0].lower())

        return [{"name": name, "cells": cells} for name, cells in sorted(rows.items(), key=weight)]


def row(what: str, time: str | None = None, world: str | None = None, pos=None) -> dict:
    return {"time": time[:19] if time else None, "world": world, "pos": list(pos) if pos else None, "what": what}


# ---------------------------------------------------------------- what it reads


def usercache(server_dir: Path) -> dict[str, str]:
    """uuid -> name."""
    try:
        rows = json.loads((server_dir / "usercache.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {r["uuid"]: r["name"] for r in rows if isinstance(r, dict) and isinstance(r.get("name"), str)
            and isinstance(r.get("uuid"), str)}


def parties(server_dir: Path) -> dict[str, list[str]] | None:
    """Open Parties and Claims' parties: file name -> member names, owner first. None when there are none to read."""
    folder = server_dir / "world" / "data" / "openpartiesandclaims" / "parties"
    if not folder.is_dir():
        return None
    out = {}
    for path in sorted(folder.glob("*.nbt")):
        try:
            data = nbt.read(path)
        except (OSError, ValueError):
            continue
        names = []
        for member in [data.get("owner"), *(data.get("members") or [])]:
            name = member.get("username") if isinstance(member, dict) else None
            if isinstance(name, str) and name not in names:
                names.append(name)
        if names:
            out[path.stem] = names
    return out


def stats_now(server_dir: Path, names: dict[str, str]) -> dict[str, dict] | None:
    """uuid -> {"name", "stat/item": count} for the STATS kept. None when the folder can't be read."""
    folder = server_dir / "world" / "players" / "stats"
    if not folder.is_dir():
        return None
    try:
        files = sorted(folder.glob("*.json"))
    except OSError:
        return None
    out = {}
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8")).get("stats", {})
        except (OSError, ValueError, AttributeError):
            continue
        counts = {}
        for kind, item in STATS:
            value = (data.get(f"minecraft:{kind}") or {}).get(f"minecraft:{item}")
            if isinstance(value, int) and value > 0:
                counts[f"{kind}/{item}"] = value
        out[path.stem] = {"name": names.get(path.stem, path.stem), **counts}
    return out


def baseline(reports: Path | None, week: str) -> tuple[str | None, dict]:
    """The newest kept copy of the stats from before `week`: (its week, its counts)."""
    if reports is None:
        return None, {}
    found = sorted(p.stem for p in (reports / "stats").glob("*.json") if WEEK.fullmatch(p.stem) and p.stem < week)
    for name in reversed(found):
        try:
            data = json.loads((reports / "stats" / f"{name}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data.get("players"), dict):
            return name, data["players"]
    return None, {}


class Ledger:
    """Ledger's database, read-only, and the names its numbers stand for."""

    def __init__(self, path: Path):
        if not path.is_file():
            raise FileNotFoundError(path)
        self.db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        self.objects = {i: name.removeprefix("minecraft:")
                        for i, name in self.db.execute("select id, identifier from ObjectIdentifiers")}
        self.object_ids = {name: i for i, name in self.objects.items()}
        self.actions = {name: i for i, name in self.db.execute("select id, action_identifier from ActionIdentifiers")}
        self.sources = {name: i for i, name in self.db.execute('select id, "name" from sources')}
        self.worlds = {i: WORLD_NAMES.get(name, name)
                       for i, name in self.db.execute("select id, identifier from worlds")}
        self.players = {}
        self.first_join = {}
        for i, name, first in self.db.execute("select id, player_name, first_join from players"):
            self.players[i] = name
            self.first_join[name] = first
        self.indexes = {r[0] for r in self.db.execute("select name from sqlite_master where type='index'")}

    def act(self, name: str) -> int:
        return self.actions.get(name, -1)

    def world_id(self, label: str) -> int:
        return next((i for i, n in self.worlds.items() if n == label), -1)

    def player_rows(self, start: str, end: str) -> list[tuple]:
        """The week's rows done by a player, without Dynamic Lights' (source command)."""
        hint = "indexed by actions_player_id" if "actions_player_id" in self.indexes else ""
        query = (f"select time, action_id, x, y, z, world_id, object_id, old_object_id, player_id, extra_data "
                 f"from actions {hint} where player_id >= 1 and time >= ? and time < ? and source != ?")
        return self.db.execute(query, (start, end, self.sources.get("command", -1))).fetchall()

    def portal_breaks(self, start: str, end: str) -> list[tuple]:
        """Every portal block that went in the week, by a player or by itself (source gravity)."""
        portal = self.object_ids.get("nether_portal")
        if portal is None:
            return []
        hint = "indexed by actions_old_object_id" if "actions_old_object_id" in self.indexes else ""
        return self.db.execute(
            f"select time, x, y, z, world_id, player_id, source from actions {hint} "
            "where old_object_id = ? and action_id = ? and time >= ? and time < ?",
            (portal, self.act("block-break"), start, end)).fetchall()

    def placer(self, x: int, y: int, z: int, world: int, before: str, cache: dict) -> tuple[str, str] | None:
        """Who last placed the block at a spot before a time, and what it was (the container's owner)."""
        key = (x, y, z, world)
        if key not in cache:
            cache[key] = self.db.execute(
                "select time, player_id, object_id from actions where x = ? and y = ? and z = ? and world_id = ? "
                "and action_id = ? and player_id >= 1 order by time", (*key, self.act("block-place"))).fetchall()
        best = None
        for t, p, o in cache[key]:
            if t <= before:
                best = (self.players.get(p, str(p)), self.objects.get(o, str(o)))
        return best


def log_files(logs: Path, start: dt.datetime, end: dt.datetime) -> list[tuple[Path, dt.date]]:
    """The logs that can hold lines from the week, oldest first, each with the day it starts on."""
    found = []
    try:
        entries = list(os.scandir(logs))
    except OSError:
        return []
    for e in entries:
        m = _LOG_NAME.fullmatch(e.name)
        if m:
            day = dt.date.fromisoformat(m[1])
            if start.date() - dt.timedelta(days=1) <= day < end.date():
                found.append(((day, int(m[2])), Path(e.path), day))
    found.sort()
    out = [(path, day) for _, path, day in found]
    latest = logs / "latest.log"
    if latest.is_file():
        out.append((latest, None))
    return out


def xray_rule(rates: dict[str, tuple[int, float]]) -> tuple[float | None, set[str]]:
    """The x-ray test on {name: (diamond ore and ancient debris, per 1,000 stone)} for players who mined at least
    XRAY_STONE stone: (the median rate, or None with fewer than 3 players; the names that stand out). A median of 0
    compares with XRAY_RATE, or any ore at all would stand out. tools/staff_trends.py uses it too."""
    median = statistics.median(r for _, r in rates.values()) if len(rates) >= 3 else None
    flagged = {who for who, (n, per_k) in rates.items()
               if n >= XRAY_ORES and per_k >= 2 and (per_k >= XRAY_TIMES * median if median else per_k >= XRAY_RATE)}
    return median, flagged


def read_log(path: Path, day: dt.date | None) -> list[tuple[dt.datetime, str]]:
    """The server thread's lines with their Pacific times. A time earlier than the line before is the next day.
    latest.log has no date in its name: it ends on the day it was last written."""
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="replace") as f:
            raw = [(m[1], m[2], m[3], m[4]) for m in map(_LOG_LINE.match, f) if m]
    except (OSError, EOFError):
        return []
    if day is None:
        wraps = sum(1 for a, b in zip(raw, raw[1:], strict=False) if b[:3] < a[:3])
        written = dt.datetime.fromtimestamp(path.stat().st_mtime, calendar.PACIFIC).date()
        day = written - dt.timedelta(days=wraps)
    out, last = [], None
    for h, m, s, text in raw:
        if last is not None and (h, m, s) < last:
            day += dt.timedelta(days=1)
        last = (h, m, s)
        out.append((dt.datetime.combine(day, dt.time(int(h), int(m), int(s))), text.rstrip()))
    return out


# ---------------------------------------------------------------- the checks


class Week:
    def __init__(self, live: Path, week: str, reports: Path | None = None, now: dt.datetime | None = None):
        self.live, self.week, self.reports = live, week, reports
        self.server = live / "server"
        self.start, self.end = week_bounds(week)
        self.launch = launch()
        self.since = min(max(self.start, self.launch), self.end)     # before the launch is staff test play
        self.lo, self.hi = stamp(self.since), stamp(self.end)
        self.now = now
        self.grid = Grid()
        self.notes: list[str] = []
        self.skipped: dict[str, str] = {}
        self.sources: dict = {}
        self.mining: list[dict] = []
        self.names = usercache(self.server)
        self.parties = parties(self.server)
        self.party_of = {n.lower(): key for key, names in (self.parties or {}).items() for n in names}

    def party(self, name: str) -> str:
        return self.party_of.get(name.lower(), f"solo:{name}")

    def size(self, key: str) -> int:
        return len(self.parties.get(key, [])) if self.parties and not key.startswith("solo:") else 1

    def same_party(self, a: str, b: str) -> bool:
        return self.party(a) == self.party(b)

    # ------------------------------------------------ stats

    def check_stats(self) -> dict | None:
        now = stats_now(self.server, self.names)
        if now is None:
            for c in STAT_CHECKS:
                self.skipped[c] = "the players' stats couldn't be read"
            self.sources["stats"] = "missing"
            return None
        since, before = baseline(self.reports, self.week)
        if since:
            self.sources["stats"] = f"change since the copy kept after {since}"
        else:
            self.sources["stats"] = "everything since each player's first join"
            self.notes.append("The item counts (pearls, gapples, totems, crystals, netherite) are everything since "
                              "each player first joined: no copy of the stats from an earlier week was kept.")
        for uuid, counts in now.items():
            old = before.get(uuid, {})
            name = counts["name"]

            def week_count(key, counts=counts, old=old):
                new, was = counts.get(key, 0), old.get(key, 0)
                return new - was if new >= was else new     # a count that went down was reset: take it whole

            span = "the week" if since else "so far"
            for check, item, what in (("pearls", "ender_pearl", "thrown"),
                                      ("gapples", "enchanted_golden_apple", "eaten"),
                                      ("totems", "totem_of_undying", "used"),
                                      ("crystals", "end_crystal", "placed")):
                used, picked = week_count(f"used/{item}"), week_count(f"picked_up/{item}")
                if used:
                    self.grid.add(name, check, CLEAR, what, [row(f"{what}: {used} {plural(item, used)} "
                                                                 f"(the game's stats, {span})")], used)
                if picked:
                    self.grid.add(name, check, UNCLEAR, "picked up",
                                  [row(f"picked up {picked} {plural(item, picked)}, none {what} "
                                       f"(the game's stats, {span})" if not used else
                                       f"picked up {picked} {plural(item, picked)} (the game's stats, {span})")],
                                  picked)
            crafted = sum(week_count(f"crafted/{n}") for n in NETHERITE)
            picked = sum(week_count(f"picked_up/{n}") for n in NETHERITE)
            if crafted:
                self.grid.add(name, "netherite", CLEAR, "crafted",
                              [row(f"crafted {crafted} netherite armor pieces (the game's stats, {span})")], crafted)
            if picked:
                self.grid.add(name, "netherite", UNCLEAR, "picked up",
                              [row(f"picked up {picked} netherite armor pieces (the game's stats, {span}); rule 24 "
                                   "is about crafting or using it")], picked)
        return {"week": self.week, "players": now}

    # ------------------------------------------------ parties

    def check_parties(self) -> None:
        if self.parties is None:
            self.skipped["faction"] = "no Open Parties and Claims parties to read"
            self.sources["parties"] = "missing"
            return
        self.sources["parties"] = len(self.parties)
        for names in self.parties.values():
            if len(names) > FACTION_MAX:
                for name in names:
                    self.grid.add(name, "faction", CLEAR, "in the party",
                                  [row(f"party of {len(names)}: {', '.join(names)}")], len(names))

    # ------------------------------------------------ Ledger

    def check_ledger(self) -> None:
        try:
            ledger = Ledger(self.server / "world" / "ledger.sqlite")
            rows = ledger.player_rows(self.lo, self.hi)
            portals = ledger.portal_breaks(self.lo, self.hi)
        except (OSError, sqlite3.Error) as e:
            for c in LEDGER_CHECKS:
                self.skipped[c] = "Ledger's database couldn't be read"
            self.skipped["grace"] = "Ledger's database (the players' first joins) couldn't be read"
            self.sources["ledger"] = f"missing ({type(e).__name__})"
            return
        self.sources["ledger"] = f"{len(rows)} player rows"
        self.ledger = ledger
        place, brk, take, put = (ledger.act(a) for a in ("block-place", "block-break", "item-remove", "item-insert"))
        drop, pick = ledger.act("item-drop"), ledger.act("item-pick-up")
        nether, overworld = ledger.world_id("Nether"), ledger.world_id("Overworld")
        spawn = world_spawn(self.server)
        stone, ores = Counter(), defaultdict(Counter)
        named = []
        for t, a, x, y, z, w, o, oo, p, extra in rows:
            who = ledger.players.get(p, str(p))
            world = ledger.worlds.get(w, str(w))
            obj = ledger.objects.get(oo if a == brk else o, "")
            named.append((t, a, x, y, z, w, obj, who, extra))
            if a == brk:
                if obj in STONE:
                    stone[who] += 1
                elif obj in DIAMOND or obj == "ancient_debris":
                    ores[who][obj] += 1
                if obj == "bedrock":
                    self.grid.add(who, "bedrock", CLEAR, "broken", [row("broke bedrock", t, world, (x, y, z))])
            far = max(abs(x - spawn[0]), abs(z - spawn[1])) if spawn else None
            if a == place and obj == "tnt" and w == overworld and far is not None and far <= SPAWN_RADIUS:
                self.grid.add(who, "tnt", LIKELY, "placed",
                              [row(f"placed TNT {far} blocks from spawn", t, world, (x, y, z))])
            if w == nether and y >= 128 and a in (place, brk):
                self.grid.add(who, "roof", CLEAR, "blocks", [row(f"{'placed' if a == place else 'broke'} {obj} "
                                                                 "above the Nether roof", t, world, (x, y, z))])
        if not spawn:
            self.skipped["tnt"] = "the world spawn couldn't be read from level.dat"
        self.check_xray(stone, ores)
        self.check_portals(ledger, portals, named, place, brk)
        self.check_containers(ledger, named, take, put, drop, pick)

    def check_xray(self, stone: Counter, ores: dict) -> None:
        rates = {}
        for who in set(stone) | set(ores):
            d = ores[who]["diamond_ore"] + ores[who]["deepslate_diamond_ore"]
            debris = ores[who]["ancient_debris"]
            per_k = round(1000 * (d + debris) / stone[who], 1) if stone[who] else None
            self.mining.append({"name": who, "stone": stone[who], "diamond": d, "debris": debris, "per_k": per_k})
            if stone[who] >= XRAY_STONE:
                rates[who] = (d + debris, per_k)
        self.mining.sort(key=lambda r: (-(r["diamond"] + r["debris"]), r["name"].lower()))
        median, flagged = xray_rule(rates)
        for who, (n, per_k) in rates.items():
            if who in flagged:
                compared = f"{XRAY_TIMES} times the median {median}" if median else f"{XRAY_RATE} per 1,000"
                self.grid.add(who, "xray", UNCLEAR, "per 1,000 stone",
                              [row(f"{n} diamond ore or ancient debris in {stone_word(who, self.mining)} stone: "
                                   f"{per_k} per 1,000, over {compared}")], int(per_k))

    def check_portals(self, ledger: Ledger, portals: list[tuple], named: list[tuple], place: int, brk: int) -> None:
        """A portal that went, then obsidian or netherrack put in its place: portal trapping (rules 4 and 7)."""
        events: list[dict] = []
        for t, x, y, z, w, _player, _src in sorted(portals):
            e = next((e for e in events if e["time"] == t[:19] and e["w"] == w and e["x0"] - 4 <= x <= e["x1"] + 4
                      and e["z0"] - 4 <= z <= e["z1"] + 4 and e["y0"] - 4 <= y <= e["y1"] + 4), None)
            if e is None:
                events.append({"time": t[:19], "w": w, "x0": x, "x1": x, "y0": y, "y1": y, "z0": z, "z1": z})
                continue
            e["x0"], e["y0"], e["z0"] = min(e["x0"], x), min(e["y0"], y), min(e["z0"], z)
            e["x1"], e["y1"], e["z1"] = max(e["x1"], x), max(e["y1"], y), max(e["z1"], z)
        # Only the rows that can matter, once: breaks in a second a portal went, and cage blocks placed.
        seconds = {e["time"] for e in events}
        breaks = [r for r in named if r[1] == brk and r[0][:19] in seconds]
        cages = [r for r in named if r[1] == place and r[6] in CAGE_BLOCKS]
        for e in events:
            when = ledger_time(e["time"])
            after = stamp(when + CAGE_AFTER)
            world = ledger.worlds.get(e["w"], str(e["w"]))

            def near(r, e=e):
                return (r[5] == e["w"] and e["x0"] - 3 <= r[2] <= e["x1"] + 3 and e["z0"] - 3 <= r[4] <= e["z1"] + 3
                        and e["y0"] - 3 <= r[3] <= e["y1"] + 3)

            breakers = sorted({r[7] for r in breaks if r[0][:19] == e["time"] and near(r)})
            cage = [r for r in cages if e["time"] <= r[0][:19] <= after and near(r)]
            cagers = Counter(r[7] for r in cage)
            pos = (e["x0"], e["y0"], e["z0"])
            caged = ", ".join(f"{n} {k}" for k, n in cagers.items())
            for who in breakers:
                if who in cagers:
                    self.grid.add(who, "portal", CLEAR, "portals caged",
                                  [row(f"broke a portal, then put {cagers[who]} obsidian/netherrack in it", e["time"],
                                       world, pos)])
                elif cagers:
                    self.grid.add(who, "portal", LIKELY, "portals caged",
                                  [row(f"broke a portal; then caged by {caged}", e["time"], world, pos)])
                else:
                    self.grid.add(who, "portal", UNCLEAR, "portals broken",
                                  [row("broke a portal (not caged after)", e["time"], world, pos)])
            for who, n in cagers.items():
                if who in breakers:
                    continue
                what = (f"put {n} obsidian/netherrack in a portal that "
                        f"{'collapsed by itself' if not breakers else 'was broken by ' + ', '.join(breakers)}")
                self.grid.add(who, "portal", UNCLEAR if breakers else LIKELY, "on a cage",
                              [row(what, e["time"], world, pos)])

    def check_containers(self, ledger: Ledger, named: list[tuple], take: int, put: int, drop: int,
                         pick: int) -> None:
        """Takes from a container another faction placed (rule 39), and groups of more than 4 that share containers
        or trade (rule 32). A pair that goes both ways (one also took from the other's, or put into it) is a shared
        base, not theft."""
        cache: dict = {}
        takes = defaultdict(list)       # (taker, owner) -> rows
        uses = Counter()                # (player, owner): cross-party takes and puts
        for t, a, x, y, z, w, _obj, who, extra in named:
            if a not in (take, put):
                continue
            placed = ledger.placer(x, y, z, w, t, cache)
            if not placed or placed[0] == who or placed[1] == "ender_chest" or self.same_party(who, placed[0]):
                continue
            owner, box = placed
            uses[(who, owner)] += 1
            if a == take:
                count, item = items(extra)
                takes[(who, owner)].append(row(f"took {count} {item} from {owner}'s {box.replace('_', ' ')}", t,
                                               ledger.worlds.get(w, str(w)), (x, y, z)))
        put_into = {(who, owner) for t, a, x, y, z, w, _o, who, _e in named if a == put
                    for owner in [(ledger.placer(x, y, z, w, t, cache) or ("", ""))[0]] if owner}
        for (taker, owner), rows in takes.items():
            if (owner, taker) in takes or (taker, owner) in put_into:
                continue
            self.grid.add(taker, "theft", LIKELY if len(rows) >= 3 else UNCLEAR, "from another faction", rows,
                          len(rows))
        # Trades: a drop picked up by someone from another party within a minute and a few blocks.
        drops = defaultdict(list)
        for r in named:
            if r[1] == drop:
                drops[(r[5], r[6])].append(r)
        for t, a, x, y, z, w, obj, who, _e in named:
            if a != pick:
                continue
            when = ledger_time(t)
            for d in drops.get((w, obj), ()):
                if (d[7] != who and not self.same_party(who, d[7])
                        and dt.timedelta() <= when - ledger_time(d[0]) <= TRADE_WITHIN
                        and max(abs(d[2] - x), abs(d[3] - y), abs(d[4] - z)) <= TRADE_BLOCKS):
                    uses[(who, d[7])] += 1
                    break
        self.check_groups(uses)

    def check_groups(self, uses: Counter) -> None:
        parent: dict[str, str] = {}

        def root(k):
            while parent.setdefault(k, k) != k:
                k = parent[k]
            return k

        # Two factions are together when it goes both ways between two of their players, often enough: a raid or a
        # dropped kill only goes one way.
        links = {(a, b) for (a, b), n in uses.items() if n >= GROUP_LINK and uses[(b, a)] >= GROUP_LINK}
        for a, b in links:
            parent[root(self.party(a))] = root(self.party(b))
        groups = defaultdict(set)
        for key in parent:
            groups[root(key)].add(key)
        for members in groups.values():
            size = sum(self.size(k) for k in members)
            if len(members) < 2 or size <= FACTION_MAX:
                continue
            names = sorted({n for k in members for n in (self.parties or {}).get(k, [k.removeprefix("solo:")])},
                           key=str.lower)
            self.notes.append(f"Rule 32: {size} players use each other's chests or pick up each other's drops, both "
                              f"ways, across {len(members)} factions or solo players: {', '.join(names)}. A shop or a "
                              "shared farm looks the same in the logs.")
            for a, b in sorted(links):
                if self.party(a) in members:
                    self.grid.add(a, "group", UNCLEAR, "times with another faction",
                                  [row(f"used {b}'s chests or picked up {b}'s drops {times(uses[(a, b)])}, and "
                                       f"{b} theirs {times(uses[(b, a)])}; the group comes to {size} players")],
                                  uses[(a, b)])

    # ------------------------------------------------ logs

    def check_logs(self) -> None:
        files = log_files(self.server / "logs", self.start, self.end)
        self.sources["logs"] = len(files)
        if not files:
            for c in LOG_CHECKS:
                self.skipped.setdefault(c, "no game logs from the week")
            return
        lines = []
        for path, day in files:
            lines += read_log(path, day)
        known = set(self.names.values()) | set(getattr(getattr(self, "ledger", None), "players", {}).values())
        first_join = dict(getattr(getattr(self, "ledger", None), "first_join", {}))
        name = "|".join(sorted(map(re.escape, known), key=len, reverse=True)) or "(?!)"
        kill = re.compile(rf"^({name}) (.*?\b(?:by|escape|fighting)) ({name})(?: using \[.*\])?$")
        launch_end = self.launch + LAUNCH_HOUR
        key = secrets.token_bytes(16)       # this run's only: the hashes can't be matched with anything else
        connections = defaultdict(set)
        timed_out: dict[str, dt.datetime] = {}    # name -> when they last lost connection by timing out
        for when, text in lines:
            m = _LOST.match(text)
            if m:
                if m[2] == "Timed out":
                    timed_out[m[1]] = when
                else:
                    timed_out.pop(m[1], None)
            if not self.since <= when < self.end:
                continue
            seen = stamp(when)
            m = _LOGIN.match(text)
            if m:
                connections[hashlib.blake2b(m[2].encode(), key=key, digest_size=12).digest()].add(m[1])
            m = _COWARD.match(text)
            if m:
                out = timed_out.get(m[1])
                drop = out is not None and dt.timedelta() <= when - out <= DROP_WITHIN
                self.grid.add(m[1], "combatlog", UNCLEAR if drop else CLEAR, "deaths",
                              [row("died of cowardice (logged out in combat)" +
                                   ("; the line before is a time-out, so likely a network drop" if drop else ""),
                                   seen)])
            m = kill.match(text)
            if m and m[1] != m[3]:
                victim, how, killer = m[1], m[2], m[3]
                if when < launch_end:
                    mate = self.same_party(victim, killer)
                    self.grid.add(killer, "launch", UNCLEAR if mate else LIKELY, "kills",
                                  [row(f"{victim} {how} {killer}" + (" (a teammate)" if mate else "") +
                                       f", {minutes(when - self.launch)} after the planned launch", seen)])
                elif victim in first_join:
                    start = max(ledger_time(first_join[victim]), self.launch)
                    if start <= when < start + GRACE:
                        self.grid.add(killer, "grace", UNCLEAR, "kills",
                                      [row(f"{victim} {how} {killer}, {hours(when - start)} after {victim}'s "
                                           "first join (the log can't show who hit first)", seen)])
        for names in connections.values():
            if len(names) > 1:
                for who in sorted(names):
                    others = ", ".join(sorted(names - {who}))
                    self.grid.add(who, "sharing", UNCLEAR, "shares with",
                                  [row(f"logged in from the same connection as {others}")], len(names) - 1)
        if self.start < self.launch < self.end:
            self.notes.append(f"Everything before the launch, {clock(self.launch)} Pacific, is staff test play and is "
                              "left out, except in the item counts: the game's stats can't be split by time.")
        if self.start <= self.launch < self.end:
            self.notes.append(f"Rule 23: the launch hour is counted from the planned launch, {clock(self.launch)} "
                              "Pacific; a kill a few minutes after it depends on the exact minute the server opened.")
        self.notes.append("Rule 26: while the monkey-rules data pack's grace is off, the logs show who died, not who "
                          "hit first, so a kill in someone's first 48 hours is only ever unclear.")

    # ------------------------------------------------ the report

    def report(self, made: dt.datetime) -> tuple[dict, dict | None]:
        snapshot = self.check_stats()
        self.check_parties()
        self.check_ledger()
        self.check_logs()
        launch_week = self.start <= self.launch + LAUNCH_HOUR and self.launch < self.end
        checks = [c for c in CHECKS if c[0] != "launch" or launch_week]
        clean = [{"id": c, "title": t, "rule": r, "result": ok} for c, t, r, ok in checks
                 if not self.grid.flagged(c) and c not in self.skipped]
        report = {
            "version": VERSION, "week": self.week, "from": stamp(self.start)[:16], "to": stamp(self.end)[:16],
            "made": public.iso(made),
            "checks": [{"id": c, "title": t, "rule": r} for c, t, r, _ in checks],
            "players": self.grid.players(), "clean": clean,
            "skipped": [{"id": c, "title": TITLES[c][1], "why": why} for c, why in sorted(self.skipped.items())],
            "notes": self.notes, "mining": self.mining[:30], "sources": self.sources,
        }
        if self.end <= self.launch:
            report["notes"].insert(0, "This week is before the launch: it was all staff test play.")
        if self.now and self.now < self.end:
            report["partial"] = f"the week so far, to {stamp(self.now)[:16]}"
        return report, snapshot


def world_spawn(server_dir: Path) -> tuple[int, int] | None:
    """The world spawn's x and z from level.dat: Data.spawn.pos since 1.21.9, Data.SpawnX/SpawnZ before."""
    try:
        data = nbt.read(server_dir / "world" / "level.dat")
    except (OSError, ValueError):
        return None
    data = data.get("Data", data)
    pos = (data.get("spawn") or {}).get("pos") if isinstance(data.get("spawn"), dict) else None
    if isinstance(pos, list) and len(pos) == 3:
        return int(pos[0]), int(pos[2])
    if isinstance(data.get("SpawnX"), int) and isinstance(data.get("SpawnZ"), int):
        return data["SpawnX"], data["SpawnZ"]
    return None


def items(extra) -> tuple[int, str]:
    """Ledger's item text, {count:16,id:"minecraft:stone"}, as (16, "stone")."""
    m = _EXTRA.search(extra or "")
    if not m:
        return 1, "items"
    count, item = (m[1], m[2]) if m[1] else (m[4], m[3])
    return int(count), item.removeprefix("minecraft:").replace("_", " ")


def stone_word(who: str, mining: list[dict]) -> int:
    return next((r["stone"] for r in mining if r["name"] == who), 0)


PLURALS = {"ender_pearl": "ender pearls", "enchanted_golden_apple": "enchanted golden apples",
           "totem_of_undying": "totems of undying", "end_crystal": "end crystals"}


def plural(item: str, n: int) -> str:
    return item.replace("_", " ") if n == 1 else PLURALS.get(item, item.replace("_", " "))


def times(n: int) -> str:
    return "once" if n == 1 else "twice" if n == 2 else f"{n} times"


def clock(when: dt.datetime) -> str:
    """Sat 7 Nov 5:00 PM."""
    return f"{when:%a} {when.day} {when:%b} {when.hour % 12 or 12}:{when:%M} {'AM' if when.hour < 12 else 'PM'}"


def minutes(delta: dt.timedelta) -> str:
    return f"{int(delta.total_seconds() // 60)} min"


def hours(delta: dt.timedelta) -> str:
    return f"{delta.total_seconds() / 3600:.0f} h"


# ---------------------------------------------------------------- the staff page (tools/staff_panel.py)

sp = None   # tools/staff_panel.py (register)


def reports_dir(panel) -> Path:
    return panel.staff / "reports"


def read_report(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("week") == path.stem else None


def list_reports(panel) -> dict:
    """The weeks written, newest first, each with how many players have something to look at."""
    folder = reports_dir(panel)
    weeks = []
    for path in sorted(folder.glob("*.json"), reverse=True) if folder.is_dir() else ():
        if not WEEK.fullmatch(path.stem):
            continue
        data = read_report(path)
        if data is None:
            continue
        cells = [c for p in data.get("players", []) for c in p.get("cells", {}).values()]
        weeks.append({"week": data["week"], "from": data.get("from"), "to": data.get("to"), "made": data.get("made"),
                      "players": len(data.get("players", [])),
                      "clear": sum(1 for c in cells if c.get("level") == CLEAR),
                      "likely": sum(1 for c in cells if c.get("level") == LIKELY)})
    return {"weeks": weeks}


def get_report(panel, week) -> dict:
    if not isinstance(week, str) or not WEEK.fullmatch(week):
        raise sp.Refused(400, "week must be a week like 2026-W45.")
    data = read_report(reports_dir(panel) / f"{week}.json")
    if data is None:
        raise sp.Refused(404, f"No report for {week}: the weekly job writes one each Monday for the week before.")
    return {"report": data}


ROUTES = {
    ("GET", "/api/reports"): lambda p, u, q, b: list_reports(p),
    ("GET", "/api/report"): lambda p, u, q, b: get_report(p, q.get("week")),
}
NEEDS = {key: "moderator" for key in ROUTES}


def register(module) -> None:
    """Adds these routes to staff_panel's (`module` is staff_panel itself, as it runs)."""
    global sp
    sp = module
    module.ROUTES.update(ROUTES)
    module.NEEDS.update(NEEDS)
    module.PATHS.update(path for _, path in ROUTES)


# ---------------------------------------------------------------- the commands


def make(live: Path, week: str, reports: Path | None, now: dt.datetime) -> tuple[dict, dict | None]:
    return Week(live, week, reports, pacific_now(now)).report(now)


def write(live: Path, out: Path, week: str, now: dt.datetime) -> str:
    """Writes the week's report and the stats copy; a week already written is left as it is."""
    target = out / f"{week}.json"
    if target.exists():
        return f"{target}: already written, skipped"
    if pacific_now(now) < week_bounds(week)[1]:
        # A part week would be kept as it is: every later run skips a week already written.
        raise ValueError(f"{week} isn't over yet, so nothing was written: use show for the week so far")
    report, snapshot = make(live, week, out, now)
    if snapshot is not None:
        snapshot["taken"] = public.iso(now)
        public.write(out / "stats" / f"{week}.json", snapshot)
    public.write(target, report)
    flagged = len(report["players"])
    return f"{target}: {flagged} players with something to look at, {len(report['clean'])} checks clean"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    sub = ap.add_subparsers(dest="command", required=True)
    for name, about in (("show", "prints a week's report (changes nothing)"),
                        ("write", "writes the last whole week's report, unless it is there already")):
        p = sub.add_parser(name, help=about)
        p.add_argument("live", type=Path, help="the running release's folder (LIVE_DIR)")
        p.add_argument("--week", help="the ISO week, like 2026-W45")
        p.add_argument("--at", type=server.parse_time, help="pretend it is this time (ISO 8601; UTC if no offset)")
        if name == "write":
            p.add_argument("--out", type=Path, required=True, help="the reports folder (/srv/monkey/staff/reports)")
        else:
            p.add_argument("--reports", type=Path, help="the reports folder, for the stats copy to count from")
    args = ap.parse_args(argv)
    now = server.job_time(args)
    today = pacific_now(now).date()
    if args.week and not WEEK.fullmatch(args.week):
        ap.error(f"--week {args.week!r}: give a week like 2026-W45")
    if args.command == "show":
        report, _ = make(args.live, args.week or week_name(today), args.reports, now)
        print(json.dumps(report, indent=2))
        return 0
    try:
        print(write(args.live, args.out, args.week or week_name(today - dt.timedelta(days=7)), now))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
