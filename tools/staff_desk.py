"""The staff page's everyday tools, the ones other hosts' panels have and this one lacked: everyone who has joined,
staff notes on a player, saved commands, and the record of changes with a search. tools/staff_panel.py registers them
(register()), so they get the same login, role and change checks as every other control; docs/LIVE.md, "The staff
page", says what each one does.

    GET  /api/known-players                    everyone who has joined: last seen, play time, lists, notes  moderator
    GET  /api/player-notes?name=N              staff's notes on one player, newest first                    moderator
    POST /api/player-notes {"name", "text"}    adds a note, signed with the login and the time              moderator
    POST /api/player-note-delete {"name", "id"}  takes one note away                                         admin
    GET  /api/saved-commands                   the commands staff saved for the console                     admin
    POST /api/saved-commands {"label", "command"}  saves one (the console's own checks first)               admin
    POST /api/saved-command-delete {"id"}                                                                   admin
    GET  /api/activity?user=&action=&q=&before=  the record of changes, newest first, 100 at a time         moderator
    GET  /api/activity-export?user=&action=&q=   the same search as a .csv file                             moderator
    GET  /api/tempbans                         the bans that lift by themselves, and when                  moderator
    POST /api/tempban {"name", "hours", "reason"?}  `ban NAME Banned until ...`, then `pardon NAME` at that time  admin
    POST /api/tempban-end {"name"}             lifts one now (pardon), or forgets it if the ban is gone     admin
    GET  /api/file-search?q=&text=1            files under server/ whose name has q, or (text=1) whose text does  admin

The safety rules:
- Everyone who has joined is read from files the server writes itself: usercache.json (names), the world's
  players/data/UUID.dat (only its time: when the server last saved that player) and players/stats/UUID.json (only
  minecraft:play_time). Nothing else of the world is opened, and nothing is asked over RCON. A name is shown only
  when it is a real player name.
- A note is plain text of at most NOTE_MAX characters, never a command. It is kept by the player's UUID when the
  server knows one, so it follows a player through a change of name. A deleted note stays in the file's "deleted"
  list (the newest DELETED_KEPT), so nothing written about a player is lost by a click. actions.log says who wrote
  a note about whom, never the text: a note can say why someone was banned, and the log is also posted to Discord.
- A saved command goes through the console's own checks when it is saved (no seed, no stop, one line) and again
  when it is run: running one is an ordinary POST /api/command, with its own line in actions.log.
- A temporary ban is the game's own ban, its reason starting TEMP_REASON and the time it ends. At that time (the
  scheduler's thread looks every 20 seconds: staff_panel.SCHEDULER_LOOKS) the page pardons the player, but only if
  the ban in banned-players.json is still that one, word for word: a staff member who pardoned them, or banned them
  again, decides. While the server is off it waits, sending nothing, and pardons once it is back. A player banned
  already can't be banned for a time: the game would keep the first ban's words and end.
- The file search walks server/ under the Files tab's own rules (no worlds, libraries, versions, map files or
  databases), at most SEARCH_FILES files and SEARCH_SECONDS seconds. A text search reads only plain-text config files
  under SEARCH_TEXT_MAX, never logs/ or crash-reports/, and it searches the text as the editor shows it, secrets
  masked, so a search can't find (or guess) a secret value.
- The record of changes is only read here. A search reads at most ACTIVITY_READ of the end of actions.log. In the
  .csv a cell that a spreadsheet would run as a formula (it starts with = + - or @) gets a ' in front.

Stdlib only, Python 3.10 or newer.
"""
import contextlib
import csv
import datetime as dt
import io
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

sp = None   # tools/staff_panel.py (register)

PLAYERS_MAX = 2000                  # the most players listed, the last seen first
NOTE_MAX = 500
NOTES_EACH = 50                     # the most notes on one player
DELETED_KEPT = 200                  # deleted notes kept in the file, for putting one back by hand
LABEL_MAX = 40
COMMANDS_MAX = 40
ACTIVITY_READ = 8 * 1024 * 1024     # the most of actions.log a search reads, from its end
ACTIVITY_PAGE = 100
ACTIVITY_EXPORT = 5000              # the most rows in one .csv
TICKS_PER_HOUR = 20 * 3600
TEMP_REASON = "Banned until"        # the start of a temporary ban's reason, as players see it
TEMP_HOURS = (1, 24 * 30)
SEARCH_FILES = 20000
SEARCH_SECONDS = 5.0
SEARCH_SHOWN = 200
SEARCH_TEXT_MAX = 1024 * 1024
TEXT_SUFFIXES = {".toml", ".json", ".json5", ".properties", ".yml", ".yaml", ".txt", ".cfg", ".conf", ".ini", ".snbt",
                 ".mcmeta", ".md", ".csv", ".zs", ".js", ".mcfunction"}
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_WORD = re.compile(r"[A-Za-z0-9_-]{1,64}")
_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _json(path: Path):
    """The file as JSON, None when it is missing or can't be read."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save_json(path: Path, data: dict) -> None:
    """Writes the file whole: a temporary file beside it, flushed to disk, renamed over it. Mode 600: notes are
    about people."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}-{secrets.token_hex(4)}.tmp")
    try:
        with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def checked_text(value, most: int, what: str) -> str:
    """One line of plain text, its runs of spaces made one, or Refused."""
    if not isinstance(value, str):
        raise sp.Refused(400, f"{what} must be text.")
    value = " ".join(value.split())
    if not value:
        raise sp.Refused(400, f"Type {what}.")
    if len(value) > most:
        raise sp.Refused(400, f"{what[0].upper()}{what[1:]} can be at most {most} characters.")
    if any(not c.isprintable() for c in value):
        raise sp.Refused(400, f"{what[0].upper()}{what[1:]} has a control character in it.")
    return value


def checked_player(value) -> str:
    if not isinstance(value, str) or not sp.PLAYER.fullmatch(value):
        raise sp.Refused(400, "A player name is 3 to 16 letters, digits or _.")
    return value


class Desk:
    def __init__(self, panel):
        self.p = panel
        self._notes = threading.Lock()
        self._commands = threading.Lock()
        self._played: dict[str, tuple[tuple, int | None]] = {}    # stats file -> ((mtime, size), ticks played)
        self._cache = threading.Lock()

    # ------------------------------------------------ everyone who has joined

    def _names(self) -> dict[str, str]:
        """uuid -> name, from usercache.json: every player the server has looked up, so everyone who has joined."""
        rows = _json(self.p.root / "usercache.json")
        if not isinstance(rows, list):
            return {}
        return {r["uuid"].lower(): r["name"] for r in rows
                if isinstance(r, dict) and isinstance(r.get("uuid"), str) and _UUID.fullmatch(r["uuid"].lower())
                and isinstance(r.get("name"), str) and sp.PLAYER.fullmatch(r["name"])}

    def _listed(self, file: str) -> set[str]:
        rows = _json(self.p.root / file)
        return {r["name"].lower() for r in rows if isinstance(r, dict) and isinstance(r.get("name"), str)} \
            if isinstance(rows, list) else set()

    def _play_time(self, path: Path) -> int | None:
        """Ticks played, from the game's own stats file; read again only when the file has changed."""
        try:
            st = path.stat()
        except OSError:
            return None
        key, mark = str(path), (st.st_mtime, st.st_size)
        with self._cache:
            kept = self._played.get(key)
        if kept and kept[0] == mark:
            return kept[1]
        data = _json(path)
        custom = (data.get("stats") or {}).get("minecraft:custom") if isinstance(data, dict) else None
        ticks = custom.get("minecraft:play_time") if isinstance(custom, dict) else None
        ticks = ticks if isinstance(ticks, int) and not isinstance(ticks, bool) and ticks >= 0 else None
        with self._cache:
            if len(self._played) > PLAYERS_MAX * 2:
                self._played.clear()
            self._played[key] = (mark, ticks)
        return ticks

    def known_players(self) -> dict:
        names = self._names()
        players = self.p.root / "world" / "players"
        seen: dict[str, float] = {}
        with contextlib.suppress(OSError), os.scandir(players / "data") as it:
            for d in it:
                uuid = d.name[:-4].lower()
                if d.name.endswith(".dat") and _UUID.fullmatch(uuid):
                    with contextlib.suppress(OSError):
                        seen[uuid] = d.stat().st_mtime
        lists = {key: self._listed(file) for key, file in (("whitelisted", "whitelist.json"), ("op", "ops.json"),
                                                            ("banned", "banned-players.json"))}
        notes = self._load_notes()
        rows = []
        for uuid, name in names.items():
            ticks = self._play_time(players / "stats" / f"{uuid}.json")
            row = {"name": name, "last_seen": seen.get(uuid),
                   "hours": None if ticks is None else round(ticks / TICKS_PER_HOUR, 1),
                   "notes": len(notes.get(uuid, [])) + len(notes.get(f"name:{name.lower()}", []))}
            row.update({key: name.lower() in found for key, found in lists.items()})
            rows.append(row)
        # Whoever was on last comes first; a name the server only looked up (never joined) has no time and goes last.
        rows.sort(key=lambda r: (r["last_seen"] is None, -(r["last_seen"] or 0), r["name"].lower()))
        # The game keeps the names of its 1000 most recent players only: those who joined before them have a file but
        # no name here, and are counted rather than left out without a word.
        return {"players": rows[:PLAYERS_MAX], "total": len(rows), "world": (players / "data").is_dir(),
                "unnamed": len(set(seen) - set(names))}

    # ------------------------------------------------ notes on a player

    @property
    def notes_file(self) -> Path:
        return self.p.staff / "player-notes.json"

    def _load_notes(self) -> dict:
        data = _json(self.notes_file)
        notes = data.get("notes") if isinstance(data, dict) else None
        return {k: [n for n in v if isinstance(n, dict)] for k, v in notes.items() if isinstance(v, list)} \
            if isinstance(notes, dict) else {}

    def _notes_for_writing(self) -> tuple[dict, list]:
        """(the notes, the deleted ones), or Refused when the file is there but can't be read: a save would then lose
        every note."""
        data = _json(self.notes_file) if self.notes_file.exists() else {"notes": {}}
        if not isinstance(data, dict) or not isinstance(data.get("notes"), dict):
            raise sp.Refused(500, "player-notes.json can't be read: fix or move it (STAFF_DIR) and reload.")
        deleted = data.get("deleted")
        return self._load_notes(), [d for d in deleted if isinstance(d, dict)] if isinstance(deleted, list) else []

    def _key(self, name: str) -> str:
        """Where a player's notes are kept: under the UUID when the server knows the name, else under the name."""
        for uuid, known in self._names().items():
            if known.lower() == name.lower():
                return uuid
        return f"name:{name.lower()}"

    @staticmethod
    def _shown_note(note: dict) -> dict:
        return {k: note.get(k) for k in ("id", "by", "at", "text")}

    def notes(self, name) -> dict:
        name = checked_player(name)
        key = self._key(name)
        found = self._load_notes()
        rows = [*found.get(key, []), *(found.get(f"name:{name.lower()}", []) if not key.startswith("name:") else [])]
        rows.sort(key=lambda n: str(n.get("at")), reverse=True)
        return {"name": name, "notes": [self._shown_note(n) for n in rows]}

    def add_note(self, user: str, body: dict) -> dict:
        name = checked_player(body.get("name"))
        text = checked_text(body.get("text"), NOTE_MAX, "a note")
        note = {"id": secrets.token_hex(6), "by": user, "at": sp.stamp(), "text": text}
        with self._notes:
            notes, deleted = self._notes_for_writing()
            rows = notes.setdefault(self._key(name), [])
            if len(rows) >= NOTES_EACH:
                raise sp.Refused(409, f"A player can have at most {NOTES_EACH} notes: delete an old one first.")
            rows.append(note)
            _save_json(self.notes_file, {"version": 1, "notes": notes, "deleted": deleted})
        self.p.record(user, "player-note", name)
        return {"name": name, "note": self._shown_note(note)}

    def delete_note(self, user: str, body: dict) -> dict:
        name, nid = checked_player(body.get("name")), body.get("id")
        if not isinstance(nid, str):
            raise sp.Refused(400, "Say which note.")
        with self._notes:
            notes, deleted = self._notes_for_writing()
            for key in (self._key(name), f"name:{name.lower()}"):
                rows = notes.get(key, [])
                kept = [n for n in rows if n.get("id") != nid]
                if len(kept) != len(rows):
                    if kept:
                        notes[key] = kept
                    else:
                        del notes[key]
                    # Kept in the same file, so a note deleted by mistake can be put back by hand (its text is in no
                    # log). The newest DELETED_KEPT stay.
                    gone = next(n for n in rows if n.get("id") == nid)
                    deleted = [*deleted, {"player": key, "name": name, "deleted_by": user, "deleted_at": sp.stamp(),
                                          **gone}][-DELETED_KEPT:]
                    _save_json(self.notes_file, {"version": 1, "notes": notes, "deleted": deleted})
                    break
            else:
                raise sp.Refused(404, "There is no such note.")
        self.p.record(user, "player-note-delete", name)
        return {"name": name, "deleted": nid}

    # ------------------------------------------------ saved commands

    @property
    def commands_file(self) -> Path:
        return self.p.staff / "commands.json"

    def _load_commands(self) -> list | None:
        """The saved commands, [] when there are none yet, None when the file can't be read (then nothing is saved)."""
        if not self.commands_file.exists():
            return []
        data = _json(self.commands_file)
        rows = data.get("commands") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return None
        return [r for r in rows if isinstance(r, dict) and isinstance(r.get("id"), str)
                and isinstance(r.get("label"), str) and isinstance(r.get("command"), str)]

    def _commands_for_writing(self) -> list:
        rows = self._load_commands()
        if rows is None:
            raise sp.Refused(500, "commands.json can't be read: fix or move it (STAFF_DIR) and reload.")
        return rows

    def saved_commands(self) -> dict:
        rows = self._load_commands() or []
        return {"commands": [{k: r.get(k) for k in ("id", "label", "command", "by")} for r in rows]}

    def save_command(self, user: str, body: dict) -> dict:
        label = checked_text(body.get("label"), LABEL_MAX, "a label")
        command = sp.Panel.checked_command(body.get("command"))
        row = {"id": secrets.token_hex(6), "label": label, "command": command, "by": user}
        with self._commands:
            rows = self._commands_for_writing()
            if len(rows) >= COMMANDS_MAX:
                raise sp.Refused(409, f"There can be at most {COMMANDS_MAX} saved commands.")
            if any(r["label"].lower() == label.lower() for r in rows):
                raise sp.Refused(409, "A saved command already has that label.")
            rows.append(row)
            _save_json(self.commands_file, {"version": 1, "commands": rows})
        self.p.record(user, "saved-command-add", f"{label}: {sp.masked(command)}")
        return {"command": row}

    def delete_command(self, user: str, body: dict) -> dict:
        cid = body.get("id")
        if not isinstance(cid, str):
            raise sp.Refused(400, "Say which saved command.")
        with self._commands:
            rows = self._commands_for_writing()
            gone = next((r for r in rows if r["id"] == cid), None)
            if gone is None:
                raise sp.Refused(404, "There is no such saved command.")
            _save_json(self.commands_file, {"version": 1, "commands": [r for r in rows if r is not gone]})
        self.p.record(user, "saved-command-delete", gone["label"])
        return {"deleted": cid}

    # ------------------------------------------------ the record of changes, searched

    def _action_rows(self) -> tuple[list[dict], bool]:
        """(every line of actions.log this reads, oldest first, each with its place in the file; whether the file is
        longer than what was read)."""
        try:
            with open(self.p.staff / "actions.log", "rb") as f:
                size = f.seek(0, os.SEEK_END)
                start = max(0, size - ACTIVITY_READ)
                f.seek(start)
                data = f.read()
        except FileNotFoundError:
            return [], False
        if start:                                   # started mid-line: from the next whole one
            cut = data.find(b"\n") + 1
            start, data = start + cut, data[cut:]
        rows, at = [], start
        for raw in data.split(b"\n"):
            parts = raw.decode("utf-8", "replace").split(" ", 3)
            if len(parts) >= 3:
                rows.append({"at": at, "time": parts[0], "user": parts[1], "action": parts[2],
                             "target": parts[3] if len(parts) > 3 else ""})
            at += len(raw) + 1
        return rows, start > 0

    @staticmethod
    def _wanted(query: dict):
        """A test for one row, from the search's user, action and q."""
        user, action, text = (query.get(k) or "" for k in ("user", "action", "q"))
        for value, what in ((user, "user"), (action, "action")):
            if value and not _WORD.fullmatch(value):
                raise sp.Refused(400, f"{what} is one word of letters, digits, _ and -.")
        if len(text) > 100:
            raise sp.Refused(400, "Search for at most 100 characters.")
        text = text.lower()
        return lambda r: ((not user or r["user"] == user) and (not action or r["action"] == action)
                          and (not text or text in f"{r['action']} {r['target']}".lower()))

    def activity(self, query: dict) -> dict:
        wanted = self._wanted(query)
        before = query.get("before") or ""
        if before and not before.isdigit():
            raise sp.Refused(400, "before must be a whole number.")
        rows, cut = self._action_rows()
        users, actions = sorted({r["user"] for r in rows}), sorted({r["action"] for r in rows})
        found = [r for r in rows if wanted(r) and (not before or r["at"] < int(before))]
        page = found[-ACTIVITY_PAGE:][::-1]
        more = len(found) > len(page)
        return {"actions": page, "more": page[-1]["at"] if more else None, "users": users, "kinds": actions,
                "cut": cut}

    def activity_export(self, query: dict) -> tuple[str, bytes, int]:
        wanted = self._wanted(query)
        rows = [r for r in self._action_rows()[0] if wanted(r)][-ACTIVITY_EXPORT:][::-1]
        out = io.StringIO()
        sheet = csv.writer(out, lineterminator="\r\n")
        sheet.writerow(["time (UTC)", "login", "action", "what"])
        for r in rows:
            sheet.writerow([f"'{cell}" if cell.startswith(_FORMULA) else cell
                            for cell in (r["time"], r["user"], r["action"], r["target"])])
        data = out.getvalue().encode("utf-8")
        return "staff-changes.csv", data, len(data)


class TempBans:
    """The bans that lift by themselves (tempbans.json: lowercase name -> {name, until, by, at, reason})."""

    def __init__(self, panel):
        self.p = panel
        self._lock = threading.Lock()
        self.clock = time.time

    @property
    def file(self) -> Path:
        return self.p.staff / "tempbans.json"

    def _load(self) -> dict | None:
        if not self.file.exists():
            return {}
        data = _json(self.file)
        rows = data.get("bans") if isinstance(data, dict) else None
        return {k: v for k, v in rows.items() if isinstance(v, dict) and isinstance(v.get("until"), int | float)} \
            if isinstance(rows, dict) else None

    def _rows(self) -> dict:
        rows = self._load()
        if rows is None:
            raise sp.Refused(500, "tempbans.json can't be read: fix or move it (STAFF_DIR) and reload.")
        return rows

    def _game_ban(self, name: str) -> dict | None:
        rows = _json(self.p.root / "banned-players.json")
        return next((r for r in rows if isinstance(r, dict) and str(r.get("name", "")).lower() == name.lower()), None) \
            if isinstance(rows, list) else None

    @staticmethod
    def _until_words(until: float) -> str:
        return dt.datetime.fromtimestamp(until, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")  # noqa: UP017 (3.10)

    def listed(self) -> dict:
        rows = self._rows()
        return {"bans": sorted(({k: v.get(k) for k in ("name", "until", "by", "at", "reason")} for v in rows.values()),
                               key=lambda r: r["until"]), "now": self.clock()}

    def add(self, user: str, body: dict) -> dict:
        name = checked_player(body.get("name"))
        hours = body.get("hours")
        low, high = TEMP_HOURS
        if not isinstance(hours, int) or isinstance(hours, bool) or not low <= hours <= high:
            raise sp.Refused(400, f"A temporary ban lasts {low} to {high} hours.")
        why = body.get("reason") or ""
        if not isinstance(why, str):
            raise sp.Refused(400, "a reason must be text.")
        why = checked_text(why, 120, "a reason") if why.strip() else ""
        until = self.clock() + hours * 3600
        reason = f"{TEMP_REASON} {self._until_words(until)}" + (f": {why}" if why else "")
        with self._lock:
            rows = self._rows()
            # The game doesn't change a ban that is there ("Nothing changed"), so a second one would keep the first's
            # end and words: staff lift or pardon first.
            if self._game_ban(name):
                raise sp.Refused(409, f"{name} is banned already. Lift or pardon that ban first, then ban them again.")
            done = self.p.command(user, {"command": f"ban {name} {reason}"})
            if done.get("refused") or "Nothing changed" in str(done.get("output")) or not self._game_ban(name):
                raise sp.Refused(502, "The server didn't ban them (is it running?): nothing was saved. "
                                      f"It said: {done.get('output') or 'nothing'}")
            rows[name.lower()] = {"name": name, "until": until, "by": user, "at": sp.stamp(), "reason": why,
                                  "game_reason": reason}
            _save_json(self.file, {"version": 1, "bans": rows})
        self.p.record(user, "tempban", f"{name} for {hours} hours")
        return {"name": name, "until": until}

    def _lift(self, who: str, key: str, row: dict, rows: dict) -> str:
        """Pardons the player if the game's ban is still this one, then forgets it. What happened, in words."""
        ban = self._game_ban(row["name"])
        # Only the very ban this page made: one changed by hand (new words, or banned again for good) is staff's.
        said_now = str(ban.get("reason", "")) if ban is not None else None
        if said_now is None:
            same = False
        elif row.get("game_reason"):
            same = said_now == row["game_reason"]
        else:                                   # saved before the exact words were kept
            same = said_now.startswith(TEMP_REASON)
        if same:
            done = self.p.command(who, {"command": f"pardon {row['name']}"})
            if done.get("refused"):
                raise sp.Refused(502, "The server didn't take the pardon: is it running?")
            said = "pardoned"
        else:
            said = "forgotten: the ban was already lifted or changed by hand"
        del rows[key]
        _save_json(self.file, {"version": 1, "bans": rows})
        return said

    def end(self, user: str, body: dict) -> dict:
        name = checked_player(body.get("name"))
        with self._lock:
            rows = self._rows()
            if name.lower() not in rows:
                raise sp.Refused(404, "That player has no temporary ban.")
            said = self._lift(user, name.lower(), rows[name.lower()], rows)
        self.p.record(user, "tempban-end", f"{name}: {said}")
        return {"name": name, "result": said}

    def expire(self) -> list[str]:
        """Lifts every ban whose time has come; one that can't be lifted now (the server is off) waits."""
        now, ended = self.clock(), []
        with self._lock:
            rows = self._load()
            if rows is None:
                raise RuntimeError("tempbans.json can't be read")     # the scheduler says so in the journal
            if not any(row["until"] <= now for row in rows.values()):
                return []
            # No command while the server is off: each would fail, and still be a line in actions.log and a post.
            if self.p.who_is_on() is None:
                return []
            for key, row in list(rows.items()):
                if row["until"] > now or not isinstance(row.get("name"), str):
                    continue
                try:
                    said = self._lift("temp-ban", key, row, rows)
                except (sp.Refused, sp.server.RconError):
                    continue
                self.p.record("temp-ban", "tempban-end", f"{row['name']}: {said}")
                ended.append(row["name"])
        return ended


def search_files(panel, query: dict) -> dict:
    """Files under server/ whose name has the text, or with text=1 whose lines do, under the Files tab's rules."""
    q = query.get("q") or ""
    if not 2 <= len(q) <= 100 or any(not c.isprintable() for c in q):
        raise sp.Refused(400, "Search for 2 to 100 characters.")
    by_text, wanted = query.get("text") == "1", q.lower()
    root = os.path.realpath(panel.root)
    started, seen, found, cut = time.monotonic(), 0, [], False
    for folder, dirs, names in os.walk(root):
        rel = Path(os.path.relpath(folder, root)).parts if folder != root else ()
        dirs[:] = sorted(d for d in dirs if panel._rules((*rel, d)) != "refused"
                         and not os.path.islink(os.path.join(folder, d)))
        for name in sorted(names):
            parts = (*rel, name)
            seen += 1
            if seen > SEARCH_FILES or time.monotonic() - started > SEARCH_SECONDS or len(found) >= SEARCH_SHOWN:
                cut = True
                break
            rule = panel._rules(parts)
            path = os.path.join(folder, name)
            if rule == "refused" or os.path.islink(path) or name.startswith(".staff-"):
                continue
            if not by_text:
                if wanted in name.lower():
                    found.append({"path": "/".join(parts)})
                continue
            if rule != "writable" or os.path.splitext(name)[1].lower() not in TEXT_SUFFIXES:
                continue
            try:
                if os.path.getsize(path) > SEARCH_TEXT_MAX:
                    continue
                text = Path(path).read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            # Matched against the text as the editor shows it, secrets masked: matching the real text would let a
            # search for "rcon.password=a", "=ab"... spell out a password from whether it finds anything.
            for number, line in enumerate(sp.mask_secrets(text)[0].splitlines(), 1):
                if wanted in line.lower():
                    found.append({"path": "/".join(parts), "line": number, "text": line.strip()[:200]})
                    if len(found) >= SEARCH_SHOWN:
                        break
        if cut:
            break
    return {"results": found, "cut": cut, "text": by_text}


_desk_lock = threading.Lock()


def desk(panel) -> Desk:
    with _desk_lock:
        found = getattr(panel, "_desk", None)
        if found is None:
            found = panel._desk = Desk(panel)
        return found


def tempbans(panel) -> TempBans:
    with _desk_lock:
        found = getattr(panel, "_tempbans", None)
        if found is None:
            found = panel._tempbans = TempBans(panel)
        return found


ROUTES = {
    ("GET", "/api/known-players"): lambda p, u, q, b: desk(p).known_players(),
    ("GET", "/api/player-notes"): lambda p, u, q, b: desk(p).notes(q.get("name")),
    ("POST", "/api/player-notes"): lambda p, u, q, b: desk(p).add_note(u, b),
    ("POST", "/api/player-note-delete"): lambda p, u, q, b: desk(p).delete_note(u, b),
    ("GET", "/api/saved-commands"): lambda p, u, q, b: desk(p).saved_commands(),
    ("POST", "/api/saved-commands"): lambda p, u, q, b: desk(p).save_command(u, b),
    ("POST", "/api/saved-command-delete"): lambda p, u, q, b: desk(p).delete_command(u, b),
    ("GET", "/api/activity"): lambda p, u, q, b: desk(p).activity(q),
    ("GET", "/api/activity-export"): lambda p, u, q, b: desk(p).activity_export(q),
    ("GET", "/api/tempbans"): lambda p, u, q, b: tempbans(p).listed(),
    ("POST", "/api/tempban"): lambda p, u, q, b: tempbans(p).add(u, b),
    ("POST", "/api/tempban-end"): lambda p, u, q, b: tempbans(p).end(u, b),
    ("GET", "/api/file-search"): lambda p, u, q, b: search_files(p, q),
}
NEEDS = {
    ("GET", "/api/known-players"): "moderator",
    ("GET", "/api/player-notes"): "moderator",
    ("POST", "/api/player-notes"): "moderator",
    ("POST", "/api/player-note-delete"): "admin",
    ("GET", "/api/saved-commands"): "admin",
    ("POST", "/api/saved-commands"): "admin",
    ("POST", "/api/saved-command-delete"): "admin",
    ("GET", "/api/activity"): "moderator",
    ("GET", "/api/activity-export"): "moderator",
    ("GET", "/api/tempbans"): "moderator",
    ("POST", "/api/tempban"): "admin",
    ("POST", "/api/tempban-end"): "admin",
    ("GET", "/api/file-search"): "admin",
}


def register(module) -> None:
    """Adds these routes to staff_panel's (`module` is staff_panel itself, as it runs)."""
    global sp
    sp = module
    module.ROUTES.update(ROUTES)
    module.NEEDS.update(NEEDS)
    module.PATHS.update(path for _, path in ROUTES)
    module.SCHEDULER_LOOKS.append(lambda panel: tempbans(panel).expire())
