"""The staff page's look-ups, what the hosts' panels and the staff tools servers pair with have and this one lacked:
the console for moderators, limited to the commands an owner allows (BisectHosting's per-subuser command list);
who changed a block or a chest, from Ledger's database (CoreProtect's lookup, on the page); which mods Modrinth has
a newer file of (the hosts' "updates available"); and one player's history on one page (LiteBans' and Plan's player
page). tools/staff_panel.py registers them (register()), with the same login, role and change checks as every other
control; docs/LIVE.md, "The staff page", says what each one does.

    GET  /api/mod-commands                     the commands a moderator login may run in the console      moderator
    PUT  /api/mod-commands {"commands": [..]}  replaces that list                                          owner
    GET  /api/block-history?x=&y=&z=&radius=&world=&hours=&player=&kind=
                                               Ledger's rows at and around a block, newest first          moderator
    GET  /api/mod-updates?fresh=1              the mods Modrinth has a newer file of, for this game version  admin
    GET  /api/player-history?name=N            one player: their lists, ban, notes and every staff change
                                               that names them                                             moderator

The safety rules:
- A moderator's console command goes through the console's own checks first (no seed, no stop, one line), then
  must start with the words of one allowed entry ("whitelist add" allows `whitelist add NAME`, not `whitelist off`).
  The owner picks entries only from CAN_ALLOW, known commands that can't run others, make operators, place a
  command block or send a click, so the list can't lift a moderator to admin. Admins and owners use the console as
  before.
- Block history opens Ledger's database read-only (mode=ro), only through its location index, one (x, y) column at a
  time, inside a box of at most RADIUS_MAX blocks each way, for at most HOURS_MAX hours, and stops after
  LOOKUP_SECONDS or LOOKUP_ROWS rows, saying so. Rows from the `command` source (Dynamic Lights' light blocks) are
  left out. Without the location index it refuses rather than read the whole table. It only reads: a rollback stays
  Ledger's own in-game command.
- The update check sends Modrinth only the sha512 of each enabled jar, the loader and the game version, never a
  name or an address, and keeps the answer for UPDATES_KEEP seconds. It installs nothing: an owner updates a mod
  with the Mods tab's own install, which checks the file's hash as before.
- A player's history only reads: usercache.json, the lists, banned-players.json, the notes, tempbans.json and the end
  of actions.log (what staff_desk's search reads). A line counts when a whole word of it is the name.

Stdlib only, Python 3.10 or newer.
"""
import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sp = None   # tools/staff_panel.py (register)

ENTRY = re.compile(r"[a-z0-9_.:-]{1,40}(?: [a-z0-9_.:-]{1,40}){0,2}")
ENTRIES_MAX = 40
DEFAULT_COMMANDS = ["list", "say", "msg", "tell", "w", "kick", "whitelist add", "whitelist remove", "whitelist list"]
# The only first words the owner can give moderators. A fixed list of known commands, not a list of forbidden ones:
# a forbidden list always misses one, and many commands can make a moderator an operator by the back door (setblock,
# give, data or summon make a command block, which runs as the server; tellraw, team, bossbar and scoreboard take
# text with a click that runs a command as whoever clicks it, an operator too). None of these take such text or NBT.
# `minecraft:` in front is the same command. `ledger` is Ledger's own look-ups and rollbacks.
CAN_ALLOW = {"list", "say", "msg", "tell", "w", "me", "teammsg", "tm", "kick", "ban", "pardon", "whitelist",
             "tp", "teleport", "spectate", "gamemode", "effect", "clear", "kill", "weather", "time", "difficulty",
             "gamerule", "xp", "experience", "enchant", "playsound", "stopsound", "spawnpoint", "worldborder",
             "locate", "ledger"}

RADIUS_MAX = 8
HOURS = (1, 24 * 30)
COORD_MAX = 30_000_000
Y_RANGE = (-2048, 2048)
LOOKUP_SECONDS = 3.0
LOOKUP_ROWS = 500
KINDS = {"all": None, "blocks": ("block-place", "block-break", "block-change"),
         "containers": ("item-insert", "item-remove"), "kills": ("entity-kill",)}

MODRINTH = "https://api.modrinth.com/v2"
UPDATES_KEEP = 30 * 60
ANSWER_MAX = 4 * 1024 * 1024
JARS_MAX = 500
_SHA512 = re.compile(r"[0-9a-f]{128}")
_ID = re.compile(r"[A-Za-z0-9]{1,16}")
_SLUG = re.compile(r"[A-Za-z0-9._-]{1,64}")

HISTORY_ROWS = 200
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- the console for moderators

def checked_entries(value) -> list[str]:
    """The allowed list as sent, cleaned: lowercase, single spaces, no repeats, or Refused."""
    if not isinstance(value, list) or len(value) > ENTRIES_MAX:
        raise sp.Refused(400, f"Send a list of at most {ENTRIES_MAX} commands.")
    out = []
    for raw in value:
        if not isinstance(raw, str):
            raise sp.Refused(400, "Each allowed command is text.")
        entry = " ".join(raw.strip().lstrip("/").lower().split())
        if not entry:
            continue
        if not ENTRY.fullmatch(entry):
            raise sp.Refused(400, f"{entry[:40]!r}: one to three words of letters, digits and _ . : -")
        first = entry.split()[0].removeprefix("minecraft:")
        if first not in CAN_ALLOW:
            raise sp.Refused(400, f"{first} can't be given to moderators. These can: {', '.join(sorted(CAN_ALLOW))}.")
        if entry not in out:
            out.append(entry)
    return out


def allows(entries: list[str], command: str) -> bool:
    """Whether a command (as checked_command left it) starts with the words of an allowed entry."""
    words = command.lower().split()
    if not words:
        return False
    words[0] = words[0].removeprefix("minecraft:")
    if words[0] not in CAN_ALLOW:
        return False
    for entry in entries:
        want = entry.split()
        want[0] = want[0].removeprefix("minecraft:")
        if words[:len(want)] == want:
            return True
    return False


class ModCommands:
    def __init__(self, panel):
        self.p = panel
        self._lock = threading.Lock()

    @property
    def file(self) -> Path:
        return self.p.staff / "mod-commands.json"

    def entries(self) -> tuple[list[str], dict]:
        """(the allowed list, who set it and when). No file: the defaults. A file that can't be read: nothing, so a
        broken file never allows more than was meant."""
        if not self.file.exists():
            return list(DEFAULT_COMMANDS), {"default": True}
        data = _json(self.file)
        rows = data.get("commands") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return [], {"broken": True}
        kept = [r for r in rows if isinstance(r, str) and ENTRY.fullmatch(r)
                and r.split()[0].removeprefix("minecraft:") in CAN_ALLOW]
        return kept, {"by": data.get("by"), "at": data.get("at")}

    def listed(self) -> dict:
        rows, about = self.entries()
        return {"commands": rows, **about, "can_allow": sorted(CAN_ALLOW)}

    def save(self, user: str, body: dict) -> dict:
        rows = checked_entries(body.get("commands"))
        with self._lock:
            sp_desk()._save_json(self.file, {"version": 1, "commands": rows, "by": user, "at": sp.stamp()})
        self.p.record(user, "mod-commands", ", ".join(rows) or "none")
        return {"commands": rows}

    def guard(self, body: dict) -> None:
        """Called for a moderator's POST /api/command before it runs: Refused unless the list allows it."""
        command = sp.Panel.checked_command(body.get("command"))
        rows, _ = self.entries()
        if not allows(rows, command):
            shown = ", ".join(rows) if rows else "none"
            raise sp.Refused(403, f"A moderator login can run only these commands: {shown}. Ask an admin for others.")


def sp_desk():
    import staff_desk
    return staff_desk


# ---------------------------------------------------------------- block history (Ledger)

def _int(query: dict, key: str, low: int, high: int, default=None) -> int:
    raw = query.get(key)
    if raw in (None, ""):
        if default is None:
            raise sp.Refused(400, f"Type {key}.")
        return default
    if not re.fullmatch(r"-?\d{1,9}", str(raw)):
        raise sp.Refused(400, f"{key} must be a whole number.")
    value = int(raw)
    if not low <= value <= high:
        raise sp.Refused(400, f"{key} must be from {low} to {high}.")
    return value


def block_history(panel, query: dict, now: dt.datetime | None = None) -> dict:
    import staff_report
    x = _int(query, "x", -COORD_MAX, COORD_MAX)
    y = _int(query, "y", *Y_RANGE)
    z = _int(query, "z", -COORD_MAX, COORD_MAX)
    radius = _int(query, "radius", 0, RADIUS_MAX, 0)
    hours = _int(query, "hours", *HOURS, 72)
    kind = query.get("kind") or "all"
    if kind not in KINDS:
        raise sp.Refused(400, "kind is all, blocks, containers or kills.")
    player = query.get("player") or ""
    if player and not sp.PLAYER.fullmatch(player):
        raise sp.Refused(400, "A player name is 3 to 16 letters, digits or _.")
    try:
        ledger = staff_report.Ledger(panel.root / "world" / "ledger.sqlite")
    except FileNotFoundError:
        raise sp.Refused(404, "Ledger's database isn't there (world/ledger.sqlite): is Ledger installed?") from None
    except sqlite3.Error:
        raise sp.Refused(503, "Ledger's database can't be opened right now: try again in a minute.") from None
    try:
        if "actions_by_location" not in ledger.indexes:
            raise sp.Refused(503, "Ledger's database has no location index, and reading the whole table would slow "
                                  "the game: look it up in game with Ledger's own commands.")
        world_label = query.get("world") or ("Overworld" if "Overworld" in ledger.worlds.values()
                                             else next(iter(ledger.worlds.values()), "Overworld"))
        world = next((i for i, name in ledger.worlds.items() if name == world_label), None)
        if world is None:
            raise sp.Refused(400, f"world is one of: {', '.join(sorted(ledger.worlds.values()))}.")
        who = None
        if player:
            who = next((i for i, name in ledger.players.items() if str(name).lower() == player.lower()), None)
            if who is None:
                return {"rows": [], "more": False, "stopped": False, "note": f"Ledger has never seen {player}."}
        actions = KINDS[kind]
        wanted = None if actions is None else {ledger.act(a) for a in actions}
        skip = ledger.sources.get("command", -1)
        now = now or dt.datetime.now(staff_report.calendar.PACIFIC).replace(tzinfo=None)
        since = staff_report.stamp(now - dt.timedelta(hours=hours))
        rows, stopped = _lookup(ledger, x, y, z, radius, world, since, skip, wanted, who)
    finally:
        with contextlib.suppress(sqlite3.Error):
            ledger.db.close()
    rows.sort(key=lambda r: (r[0], r[-1]), reverse=True)     # newest first; id breaks ties
    more = len(rows) > LOOKUP_ROWS
    out = []
    names = {v: k for k, v in ledger.actions.items()}
    sources = {v: k for k, v in ledger.sources.items()}
    for t, a, rx, ry, rz, o, oo, p, s, back, _ in rows[:LOOKUP_ROWS]:
        out.append({"time": t[:19], "action": names.get(a, str(a)),
                    "who": ledger.players.get(p) if p and p >= 1 else f"({sources.get(s, 'world')})",
                    "object": ledger.objects.get(o, ""), "old": ledger.objects.get(oo, ""), "x": rx, "y": ry, "z": rz,
                    "rolled_back": bool(back)})
    return {"rows": out, "more": more, "stopped": stopped, "zone": "Pacific",
            "box": {"x": x, "y": y, "z": z, "radius": radius, "world": world_label, "hours": hours}}


def _lookup(ledger, x, y, z, radius, world, since, skip, wanted, who) -> tuple[list[tuple], bool]:
    """Ledger's rows in the box, one indexed (x, y) column at a time, at most LOOKUP_ROWS + 1 of them and
    LOOKUP_SECONDS of the database's time."""
    deadline = time.monotonic() + LOOKUP_SECONDS
    ledger.db.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10000)
    query = ("select time, action_id, x, y, z, object_id, old_object_id, player_id, source, rolled_back, id "
             "from actions indexed by actions_by_location "
             "where x = ? and y = ? and z between ? and ? and world_id = ? and time >= ?")
    rows, stopped = [], False
    try:
        # From the asked block outward, so a cap or the time limit keeps the rows nearest to it.
        columns = sorted(((cx, cy) for cx in range(x - radius, x + radius + 1)
                          for cy in range(y - radius, y + radius + 1)),
                         key=lambda c: max(abs(c[0] - x), abs(c[1] - y)))
        for cx, cy in columns:
            for row in ledger.db.execute(query, (cx, cy, z - radius, z + radius, world, since)):
                if row[8] == skip or (wanted is not None and row[1] not in wanted) \
                        or (who is not None and row[7] != who):
                    continue
                rows.append(row)
            if len(rows) > LOOKUP_ROWS * 4 or time.monotonic() > deadline:
                return rows, True
    except sqlite3.OperationalError as e:
        if "interrupt" not in str(e).lower():
            raise sp.Refused(503, "Ledger's database is busy: try again in a minute.") from None
        stopped = True
    finally:
        ledger.db.set_progress_handler(None, 0)
    return rows, stopped


# ---------------------------------------------------------------- mod updates (Modrinth)

def post_json(url: str, body: dict, most: int = ANSWER_MAX):
    """POST JSON to Modrinth's API (https only), its answer as JSON, or Refused(502)."""
    if not url.startswith(MODRINTH + "/"):
        raise sp.Refused(502, "Only Modrinth's API is asked.")
    import staff_host
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"User-Agent": staff_host.USER_AGENT, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as answer:   # noqa: S310 (Modrinth's https API, checked above)
            data = answer.read(most + 1)
    except (urllib.error.URLError, OSError, ValueError):
        raise sp.Refused(502, "Modrinth didn't answer: try again in a minute.") from None
    if len(data) > most:
        raise sp.Refused(502, "Modrinth's answer was too big.")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise sp.Refused(502, "Modrinth's answer was not JSON: try again in a minute.") from None


def get_json(url: str):
    import staff_host
    try:
        return json.loads(staff_host.fetch(url, ANSWER_MAX).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise sp.Refused(502, "Modrinth's answer was not JSON: try again in a minute.") from None


class Updates:
    def __init__(self, panel):
        self.p = panel
        self.post = post_json
        self.get = get_json
        self._hashes: dict[str, tuple[tuple, str]] = {}
        self._kept: tuple[float, dict] | None = None
        self._lock = threading.Lock()

    def _sha512(self, path: Path) -> str | None:
        try:
            st = path.stat()
        except OSError:
            return None
        mark = (st.st_mtime, st.st_size)
        kept = self._hashes.get(path.name)
        if kept and kept[0] == mark:
            return kept[1]
        digest = hashlib.sha512()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            return None
        self._hashes[path.name] = (mark, digest.hexdigest())
        return digest.hexdigest()

    def check(self, query: dict) -> dict:
        kept = self._kept
        if kept and query.get("fresh") != "1" and time.time() - kept[0] < UPDATES_KEEP:
            return {**kept[1], "cached": True}
        # One question to Modrinth at a time: a second asker gets the last answer or is told to wait, and never holds
        # a request thread for as long as a slow Modrinth takes.
        if not self._lock.acquire(blocking=False):
            if kept:
                return {**kept[1], "cached": True}
            raise sp.Refused(409, "The page is asking Modrinth already: try again in a minute.")
        try:
            result = self._check()
            self._kept = (time.time(), result)
            return {**result, "cached": False}
        finally:
            self._lock.release()

    def _check(self) -> dict:
        import staff_apex
        import staff_host
        version = staff_host.host(self.p).game_version()
        folder = self.p.root / "mods"
        jars = {}
        with contextlib.suppress(FileNotFoundError), os.scandir(folder) as it:
            for e in it:
                if e.name.endswith(".jar") and e.is_file(follow_symlinks=False) and len(jars) < JARS_MAX:
                    digest = self._sha512(Path(e.path))
                    if digest:
                        jars[digest] = e.name
        if not jars:
            return {"updates": [], "checked": 0, "unknown": 0, "game": version, "at": sp.stamp()}
        answer = self.post(f"{MODRINTH}/version_files/update",
                           {"hashes": sorted(jars), "algorithm": "sha512", "loaders": ["fabric"],
                            "game_versions": [version]})
        if not isinstance(answer, dict):
            raise sp.Refused(502, "Modrinth's answer was not what this page expects.")
        pinned = staff_apex.extras(self.p).pinned()
        found = []
        for digest, jar in jars.items():
            newest = answer.get(digest)
            if not isinstance(newest, dict):
                continue
            files = [f for f in newest.get("files") or [] if isinstance(f, dict)]
            primary = next((f for f in files if f.get("primary")), files[0] if files else None)
            # The newest file for this game version is the jar that is here already: nothing to update.
            if not primary or any((f.get("hashes") or {}).get("sha512") == digest for f in files):
                continue
            project = newest.get("project_id")
            vid = newest.get("id")
            if not all(isinstance(v, str) and _ID.fullmatch(v) for v in (project, vid)):
                continue
            found.append({"jar": jar, "project": project, "version": _text(newest.get("version_number"), 64),
                          "name": _text(newest.get("name"), 120), "type": _text(newest.get("version_type"), 16),
                          "published": _text(newest.get("date_published"), 40),
                          "file": _text(primary.get("filename"), 120), "pinned": jar in pinned})
        slugs = self._slugs([r["project"] for r in found])
        for row in found:
            slug = slugs.get(row["project"])
            row["slug"] = slug
            row["url"] = f"https://modrinth.com/mod/{slug or row['project']}/changelog"
        found.sort(key=lambda r: r["jar"].lower())
        return {"updates": found, "checked": len(jars), "unknown": len(jars) - sum(1 for d in jars if d in answer),
                "game": version, "at": sp.stamp()}

    def _slugs(self, ids: list[str]) -> dict[str, str]:
        if not ids:
            return {}
        import urllib.parse
        try:
            rows = self.get(f"{MODRINTH}/projects?" + urllib.parse.urlencode({"ids": json.dumps(sorted(set(ids)))}))
        except sp.Refused:
            return {}
        return {r["id"]: r["slug"] for r in rows if isinstance(r, dict) and isinstance(r.get("id"), str)
                and isinstance(r.get("slug"), str) and _SLUG.fullmatch(r["slug"])} if isinstance(rows, list) else {}


def _text(value, most: int) -> str:
    if not isinstance(value, str):
        return ""
    value = "".join(c if c.isprintable() else " " for c in value).strip()
    return value[:most]


# ---------------------------------------------------------------- one player's history

def player_history(panel, name) -> dict:
    import staff_desk
    name = staff_desk.checked_player(name)
    desk = staff_desk.desk(panel)
    low = name.lower()
    names = desk._names()
    uuid = next((u for u, n in names.items() if n.lower() == low), None)
    shown = names.get(uuid, name) if uuid else name

    def listed(file: str) -> dict | None:
        rows = _json(panel.root / file)
        if not isinstance(rows, list):
            return None
        for r in rows:
            if isinstance(r, dict) and (str(r.get("name", "")).lower() == low or (uuid and r.get("uuid") == uuid)):
                return r
        return None

    ban = listed("banned-players.json")
    temp = (_json(panel.staff / "tempbans.json") or {})
    temp = temp.get("bans", temp) if isinstance(temp, dict) else {}
    temp = temp.get(low) if isinstance(temp, dict) else None
    word = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", re.I)
    rows, cut = desk._action_rows()
    changes = [{"time": r["time"], "user": r["user"], "action": r["action"], "target": r["target"]}
               for r in rows if word.search(r["target"])][-HISTORY_ROWS:][::-1]
    notes = desk.notes(name)["notes"]
    seen = ticks = None
    if uuid and _UUID.fullmatch(uuid):      # a name goes in a file path only when it is a real UUID
        with contextlib.suppress(OSError):
            seen = (panel.root / "world" / "players" / "data" / f"{uuid}.dat").stat().st_mtime
        ticks = desk._play_time(panel.root / "world" / "players" / "stats" / f"{uuid}.json")
    return {"name": shown, "known": uuid is not None, "last_seen": seen,
            "hours": None if ticks is None else round(ticks / staff_desk.TICKS_PER_HOUR, 1),
            "whitelisted": listed("whitelist.json") is not None, "op": listed("ops.json") is not None,
            "ban": {k: _text(ban.get(k), 200) for k in ("reason", "source", "created", "expires")} if ban else None,
            "tempban": {k: temp.get(k) for k in ("until", "by", "at", "reason")} if isinstance(temp, dict) else None,
            "notes": notes, "changes": changes, "cut": cut}


# ---------------------------------------------------------------- wiring

_lock = threading.Lock()


def _one(panel, attr: str, kind):
    with _lock:
        found = getattr(panel, attr, None)
        if found is None:
            found = kind(panel)
            setattr(panel, attr, found)
        return found


def mod_commands(panel) -> ModCommands:
    return _one(panel, "_mod_commands", ModCommands)


def updates(panel) -> Updates:
    return _one(panel, "_updates", Updates)


ROUTES = {
    ("GET", "/api/mod-commands"): lambda p, u, q, b: mod_commands(p).listed(),
    ("PUT", "/api/mod-commands"): lambda p, u, q, b: mod_commands(p).save(u, b),
    ("GET", "/api/block-history"): lambda p, u, q, b: block_history(p, q),
    ("GET", "/api/mod-updates"): lambda p, u, q, b: updates(p).check(q),
    ("GET", "/api/player-history"): lambda p, u, q, b: player_history(p, q.get("name")),
}
NEEDS = {
    ("GET", "/api/mod-commands"): "moderator",
    ("PUT", "/api/mod-commands"): "owner",
    ("GET", "/api/block-history"): "moderator",
    ("GET", "/api/mod-updates"): "admin",
    ("GET", "/api/player-history"): "moderator",
    ("POST", "/api/command"): "moderator",      # below admin, a command is checked against the list: ROLE_GUARDS
}


def register(module) -> None:
    """Adds these routes to staff_panel's (`module` is staff_panel itself, as it runs)."""
    global sp
    sp = module
    module.ROUTES.update(ROUTES)
    module.NEEDS.update(NEEDS)
    module.PATHS.update(path for _, path in ROUTES)
    module.ROLE_GUARDS[("POST", "/api/command")] = guard_command


def guard_command(panel, role: str, body: dict) -> None:
    """Every role below admin (moderator today, any new one later) runs only the commands on the list."""
    if sp.ROLES.index(role) < sp.ROLES.index("admin"):
        mod_commands(panel).guard(body)
