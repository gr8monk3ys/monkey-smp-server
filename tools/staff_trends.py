"""The staff page's longer trends: a month of the server's readings, players per day, and Ledger's counts per hour.

    python3 tools/staff_trends.py show LIVE_DIR --staff STAFF_DIR     prints what a run would keep (changes nothing)
    python3 tools/staff_trends.py update LIVE_DIR --staff STAFF_DIR   updates STAFF_DIR/trends/ (deploy/monkey-staff.sh,
                                                                      every 2 minutes, after tools/staff_status.py)

tools/staff_panel.py registers the routes (register()), with the same login, role and header checks as every other
request; docs/LIVE.md, "The staff page", says what each one answers. Nothing here is public: the files hold names.

    GET /api/trend-history?days=30      the server's readings, one row an hour, up to 30 days        moderator
    GET /api/trend-players?days=30      players per day (unique, new, hours, sessions), session
                                        lengths, and how many new players came back                   moderator
    GET /api/trend-world?days=7         blocks broken and placed per hour, and this week's top miners  moderator
    GET /api/trend-ores?days=7          diamond ore and ancient debris mined per player, per 1,000
                                        stone, with the weekly report's x-ray outliers marked          moderator
    GET /api/trend-standings            each closed week's faction table (STANDINGS_DIR/weeks)        moderator

Every logged-in role is staff, so all five are open to moderators: the ore counts are an x-ray hint for the people
who handle a report, the same as the Reports tab's x-ray column.

What a run keeps, each file written whole (a temporary file renamed over it, mode 600):
- trends/history.json: staff.json's two-minute readings folded into hours, kept 30 days, as
  [hour (unix), tick average, tick P95 at most, players on average, players at most, memory %, CPU %, readings]
  with null for what no reading in the hour knew. The hours staff.json still holds are worked out again each run, so a
  restart loses nothing; its oldest hour, which it holds only part of, is kept as it was. About 50 KB a month.
- trends/players.json, at most every PLAYERS_EVERY: who played each day and for how long, from the game's own
  "NAME joined the game" and "NAME left the game" lines in logs/*.log.gz (each read once, in order) and latest.log
  (kept apart in "live", read as a stream from where the last run stopped: latest_lines). A session that a log ends
  without a leave line ends at the server's "Stopping server", its next "Starting minecraft server", or (latest.log)
  now, which counts its minutes but no finished session. Days are Pacific, as the log's times. Everyone in the first
  log looks new: retention leaves that day out and marks its week partial ("start").
  The stats files' play_time counts too, but only all-time, so the logs are the one source that says when.
  A name is the name at the time: a player who renames counts as new under the new name.
- trends/world.json, at most every WORLD_EVERY: Ledger's block-break and block-place rows by players, counted per
  hour, and per player per day (broken, placed, stone, diamond ore, ancient debris). Read-only (mode=ro), only through
  Ledger's player_id index, one player at a time from the row after the last one counted (that index holds the row id
  too, so it goes straight there), at most WORLD_ROWS rows and WORLD_SECONDS of the database's time a run; what is
  left is read the next hour. Dynamic Lights' rows (source "command") never come up: they have no player. The first
  run reads each player's rows once, keeping the last 30 days.

The VPS has 2 threads and the game needs them, so the job runs under nice (deploy/monkey-staff.sh) and its reads are
capped; a failed part leaves its file as it was and the others go on. Stdlib only (plus tools/), Python 3.10 or newer.
"""
import argparse
import contextlib
import datetime as dt
import json
import os
import re
import secrets
import sqlite3
import statistics
import sys
import time
from pathlib import Path

import staff_report
from status import iso

import rcon as server
import season_calendar as calendar

sp = None   # tools/staff_panel.py (register)

VERSION = 1
KEEP = dt.timedelta(days=30)
KEEP_PLAYERS = dt.timedelta(days=45)     # a week's cohort needs its 7 days after it
KEEP_FIRST = dt.timedelta(days=365)      # a first day older than this is forgotten: back after a year counts as new
PLAYERS_EVERY = dt.timedelta(minutes=10)
WORLD_EVERY = dt.timedelta(hours=1)
WORLD_ROWS = 300_000
WORLD_SECONDS = 4.0
WORLD_CHUNK = 20_000
LOGS_A_RUN = 60                          # .log.gz files read in one run; the rest the next
SESSIONS_A_DAY = 500
LATEST_MAX = 64 * 1024 * 1024            # a latest.log bigger than this is left for when it is rotated
TOP = 10
DAYS = {"history": (1, 30, 30), "players": (1, 45, 30), "world": (1, 30, 7), "ores": (1, 30, 7)}
SESSION_BUCKETS = (10, 30, 60, 120, 240)  # minutes: under 10, 10-30, 30-60, 1-2 h, 2-4 h, 4 h and more

_JOIN = re.compile(r"^(?:System chat: )?([A-Za-z0-9_]{1,16})(?: \(formerly known as [A-Za-z0-9_]+\))? joined the game$")
_LEFT = re.compile(r"^(?:System chat: )?([A-Za-z0-9_]{1,16}) left the game$")
_START = "Starting minecraft server"
_STOP = "Stopping server"


# ---------------------------------------------------------------- files

def load(path: Path) -> dict:
    """A trends file, {} when there is none or it can't be read: it is rebuilt from what the server still has."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) and data.get("version") == VERSION else {}


def save(path: Path, data: dict) -> None:
    """Written whole: a temporary file beside it, flushed, renamed over it. Mode 600: it holds names."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}-{secrets.token_hex(4)}.tmp")
    try:
        with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _date(value) -> dt.date | None:
    """An ISO day (YYYY-MM-DD), or None for anything else."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def due(data: dict, every: dt.timedelta, now: dt.datetime) -> bool:
    """Whether a part runs now: `every` after its last run, or at once while its last run left work for the next
    (a first read of a big Ledger database goes on every 2 minutes, a slice at a time, until it has caught up)."""
    if data.get("caught_up") is False:
        return True
    try:
        last = dt.datetime.fromisoformat(str(data.get("at")).replace("Z", "+00:00"))
    except ValueError:
        return True
    return not (dt.timedelta(0) <= now - last < every)


# ---------------------------------------------------------------- a month of readings

def _mean(values: list) -> float | None:
    kept = [v for v in values if isinstance(v, int | float)]
    return round(sum(kept) / len(kept), 1) if kept else None


def _most(values: list):
    kept = [v for v in values if isinstance(v, int | float)]
    return max(kept) if kept else None


def hours_of(readings: list) -> dict[int, list]:
    """staff.json's readings ([time, avg, p95, players, memory, cpu]) folded into hours."""
    groups: dict[int, list[list]] = {}
    for row in readings:
        if isinstance(row, list) and len(row) >= 4 and isinstance(row[0], int | float):
            groups.setdefault(int(row[0]) // 3600 * 3600, []).append([*row, *[None] * (6 - len(row))])
    return {hour: [hour, _mean([r[1] for r in rows]), _most([r[2] for r in rows]), _mean([r[3] for r in rows]),
                   _most([r[3] for r in rows]), _mean([r[4] for r in rows]), _mean([r[5] for r in rows]), len(rows)]
            for hour, rows in groups.items()}


def history(old: dict, status: dict, now: dt.datetime) -> dict:
    """The hours kept before, with those staff.json holds worked out again, and none older than KEEP. Its oldest hour
    may have lost readings off the end: a row kept from more readings than staff.json still has for it stays."""
    since = (now - KEEP).timestamp()
    kept = {int(r[0]): r for r in old.get("hours") or [] if isinstance(r, list) and len(r) == 8
            and isinstance(r[0], int) and r[0] >= since}
    readings = status.get("history") if isinstance(status, dict) else None
    fresh = hours_of(readings if isinstance(readings, list) else [])
    for hour, row in fresh.items():
        was = kept.get(hour)
        if not (was and isinstance(was[7], int) and was[7] > row[7]):
            kept[hour] = row
    return {"version": VERSION, "at": iso(now), "hours": [kept[h] for h in sorted(kept) if h >= since]}


# ---------------------------------------------------------------- players per day (the game's log)

def _day(when: dt.datetime) -> str:
    return when.date().isoformat()


class Sessions:
    """Folds a log's join, leave, start and stop lines into days: day -> {"minutes": {name: n}, "sessions": [n]}."""

    def __init__(self, days: dict, first: dict, open_: dict, last: str | None):
        self.days, self.first = days, first
        self.open = {n: dt.datetime.fromisoformat(t) for n, t in open_.items() if isinstance(t, str)}
        self.last = dt.datetime.fromisoformat(last) if isinstance(last, str) else None

    def _end(self, name: str, until: dt.datetime, finished: bool = True) -> None:
        start = self.open.pop(name)
        if until < start:
            return
        whole = round((until - start).total_seconds() / 60)
        sessions = self.days.setdefault(_day(start), {"minutes": {}, "sessions": [], "joined": []})["sessions"]
        if finished and len(sessions) < SESSIONS_A_DAY:   # one still going is no short session
            sessions.append(whole)
        at = start
        while at < until:       # minutes go to the day they were played on
            midnight = dt.datetime.combine(at.date() + dt.timedelta(days=1), dt.time())
            step = min(until, midnight)
            minutes = self.days.setdefault(_day(at), {"minutes": {}, "sessions": [], "joined": []})["minutes"]
            minutes[name] = round(minutes.get(name, 0) + (step - at).total_seconds() / 60, 1)
            at = step

    def _seen(self, name: str, when: dt.datetime) -> None:
        day = self.days.setdefault(_day(when), {"minutes": {}, "sessions": [], "joined": []})
        day["minutes"].setdefault(name, 0)
        joined = day.setdefault("joined", [])
        if name not in joined:
            joined.append(name)
        if name not in self.first or self.first[name] > _day(when):
            self.first[name] = _day(when)

    def end_all(self, until: dt.datetime, finished: bool = True) -> None:
        for name in list(self.open):
            self._end(name, until, finished)

    def feed(self, lines: list[tuple[dt.datetime, str]]) -> None:
        for when, text in lines:
            if text.startswith(_START):
                self.end_all(self.last or when)     # it stopped without a word: they left when it last spoke
            elif text.startswith(_STOP):
                self.end_all(when)
            elif m := _JOIN.match(text):
                if m[1] in self.open:
                    self._end(m[1], when)
                self.open[m[1]] = when
                self._seen(m[1], when)
            elif (m := _LEFT.match(text)) and m[1] in self.open:
                self._end(m[1], when)
            self.last = when

    def state(self) -> tuple[dict, str | None]:
        return {n: t.isoformat() for n, t in self.open.items()}, self.last.isoformat() if self.last else None


def _order(name: str) -> tuple[str, int]:
    """A rotated log's place in time: its day, then its number (2026-11-09-10 comes after 2026-11-09-9)."""
    m = staff_report._LOG_NAME.fullmatch(name)
    return (m[1], int(m[2])) if m else ("", 0)


def _logs(folder: Path) -> list[tuple[str, Path, dt.date]]:
    found = []
    with contextlib.suppress(OSError), os.scandir(folder) as it:
        for e in it:
            m = staff_report._LOG_NAME.fullmatch(e.name)
            if m:
                found.append(((m[1], int(m[2])), e.name, Path(e.path), dt.date.fromisoformat(m[1])))
    return [(name, path, day) for _, name, path, day in sorted(found)]


def _wanted(text: str) -> bool:
    return text.startswith((_START, _STOP)) or bool(_JOIN.match(text) or _LEFT.match(text))


def latest_lines(path: Path, mark: dict | None) -> tuple[list[tuple[dt.datetime, str]], dict, bool] | None:
    """latest.log's join, leave, start and stop lines, read as a stream from where `mark` (the last run's) stopped
    when it is still the same file, else from its start: (lines, the new mark, whether it went on from `mark`).
    Only those lines are kept, with an empty one for the line before each start and for the last line (Sessions
    ends a crash's sessions when the log last spoke). A line not finished yet is read next time. None: too big to
    read from its start (LATEST_MAX), left for when it is rotated."""
    size = path.stat().st_size
    with open(path, "rb") as f:
        # The same file: it starts with the bytes it started with last time (up to 256; a short one grows).
        on = (isinstance(mark, dict) and isinstance(mark.get("head"), str) and isinstance(mark.get("offset"), int)
              and 0 < mark["offset"] <= size and isinstance(mark.get("day"), str)
              and isinstance(mark.get("hms"), list) and f.read(len(mark["head"]) // 2).hex() == mark["head"])
        if not on and size > LATEST_MAX:
            return None
        offset = mark["offset"] if on else 0
        prev = tuple(mark["hms"]) if on else None
        f.seek(offset)
        kept, wraps, at = [], 0, None
        for raw in f:
            if not raw.endswith(b"\n"):
                break
            offset += len(raw)
            m = staff_report._LOG_LINE.match(raw.decode("utf-8", "replace").rstrip("\r\n"))
            if not m:
                continue
            hms = (m[1], m[2], m[3])
            if prev is not None and hms < prev:
                wraps += 1
            text = m[4].rstrip()
            if text.startswith(_START) and at:
                kept.append((*at, ""))
            if _wanted(text):
                kept.append((wraps, hms, text))
            prev, at = hms, (wraps, hms)
        f.seek(0)
        head = f.read(min(256, offset)).hex()
    if at and (not kept or kept[-1][:2] != at):
        kept.append((*at, ""))
    if on:
        day = dt.date.fromisoformat(mark["day"])
    else:
        day = dt.datetime.fromtimestamp(path.stat().st_mtime, calendar.PACIFIC).date() - dt.timedelta(days=wraps)
    lines = [(dt.datetime.combine(day + dt.timedelta(days=k), dt.time(*map(int, hms))), text) for k, hms, text in kept]
    return lines, {"head": head, "offset": offset, "day": (day + dt.timedelta(days=wraps)).isoformat(),
                   "hms": list(prev) if prev else None}, on


def _copy(data):
    return json.loads(json.dumps(data))


def players(live: Path, old: dict, now: dt.datetime) -> dict:
    """The finished logs not read yet added to what was kept ("base"), then latest.log on top of that ("live")."""
    folder = live / "server" / "logs"
    base = old.get("base") if isinstance(old.get("base"), dict) else {}
    read = [n for n in base.get("read") or [] if isinstance(n, str)]
    days = base.get("days") if isinstance(base.get("days"), dict) else {}
    first = base.get("first") if isinstance(base.get("first"), dict) else {}
    folded = Sessions(days, first, base.get("open") or {}, base.get("last"))
    done = set(read)
    newest = max(read, key=_order, default="")
    took = 0
    for name, path, day in _logs(folder):
        # A file older than one read already is left out: its sessions would land out of order.
        if name in done or _order(name) < _order(newest) or took >= LOGS_A_RUN:
            continue
        folded.feed(staff_report.read_log(path, day))
        read.append(name)
        newest = name
        took += 1
    open_, last = folded.state()
    pacific_now = now.astimezone(calendar.PACIFIC).replace(tzinfo=None)
    cutoff = _day(pacific_now - KEEP_PLAYERS)
    days = {d: v for d, v in days.items() if d >= cutoff}
    read = [n for n in read if n[:10] >= cutoff or n == newest]
    # The day the logs begin: everyone in the first one looks new, so retention marks that week (see retention()).
    start = base.get("start") if _date(base.get("start")) else min(
        (d for d in first.values() if _date(d)), default=None)
    first_cutoff = _day(pacific_now - KEEP_FIRST)
    first = {n: d for n, d in first.items() if _date(d) and d >= first_cutoff}
    base = {"read": read, "days": days, "first": first, "open": open_, "last": last, "start": start}

    live_days: dict = {}
    live_first: dict = {}
    mark = state = None
    caught_up = took < LOGS_A_RUN
    if caught_up:
        was = old.get("live") if isinstance(old.get("live"), dict) else {}
        # Going on from the last run's place needs the same base under it: no finished log read this time.
        cached = was.get("state") if took == 0 and isinstance(was.get("state"), dict) else None
        try:
            got = latest_lines(folder / "latest.log", was.get("mark") if cached else None)
        except OSError:
            got = None
        if got is not None:
            lines, mark, went_on = got
            if went_on:
                on_top = Sessions(cached["days"], cached["first"], cached["open"], cached["last"])
            else:
                on_top = Sessions({}, {}, open_, last)
            on_top.feed(lines)
            o, la = on_top.state()
            state = {"days": on_top.days, "first": on_top.first, "open": o, "last": la}
            live_days = _copy(on_top.days)
            ended = Sessions(live_days, {}, o, la)     # those still on, up to now: minutes, not finished sessions
            ended.end_all(max(pacific_now, ended.last) if ended.last else pacific_now, finished=False)
            live_first = {n: d for n, d in on_top.first.items() if n not in first}
    return {"version": VERSION, "at": iso(now), "base": base, "start": start or min(live_first.values(), default=None),
            "live": {"days": live_days, "first": live_first, "mark": mark, "state": state}, "caught_up": caught_up}


# ---------------------------------------------------------------- Ledger's counts

def world(live: Path, old: dict, now: dt.datetime, seconds: float = WORLD_SECONDS, most: int = WORLD_ROWS) -> dict:
    """Ledger's rows since the last run, one player at a time through its player_id index, counted per hour and per
    player per day."""
    cursors = {str(k): v for k, v in (old.get("cursors") or {}).items() if isinstance(v, int)}
    hours = old.get("hours") if isinstance(old.get("hours"), dict) else {}
    days = old.get("days") if isinstance(old.get("days"), dict) else {}
    pacific_now = now.astimezone(calendar.PACIFIC).replace(tzinfo=None)
    since = staff_report.stamp(pacific_now - KEEP)
    out = {"version": VERSION, "at": iso(now), "cursors": cursors, "hours": hours, "days": days, "caught_up": False,
           "zone": "Pacific"}
    ledger = staff_report.Ledger(live / "server" / "world" / "ledger.sqlite")
    try:
        if "actions_player_id" not in ledger.indexes:
            out["note"] = "Ledger's database has no player_id index: nothing was counted"
            out["caught_up"] = True      # nothing to go on with: the hourly gate applies
            return out
        brk, place = ledger.act("block-break"), ledger.act("block-place")
        skip = ledger.sources.get("command", -1)
        query = ("select id, time, action_id, old_object_id, source from actions "
                 "indexed by actions_player_id where player_id = ? and id > ? order by id limit ?")
        deadline = time.monotonic() + seconds
        ledger.db.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10000)
        counted, stopped = 0, False
        try:
            for pid, name in sorted(ledger.players.items()):
                if not isinstance(pid, int) or pid < 1 or not isinstance(name, str):
                    continue
                key = str(pid)
                while not stopped:
                    rows = ledger.db.execute(query, (pid, cursors.get(key, 0), WORLD_CHUNK)).fetchall()
                    for rid, t, a, oo, source in rows:
                        cursors[key] = rid
                        if source == skip or a not in (brk, place) or not isinstance(t, str) or t < since:
                            continue
                        hour = hours.setdefault(t[:13], [0, 0])
                        cell = days.setdefault(t[:10], {}).setdefault(name, [0, 0, 0, 0, 0])
                        if a == brk:
                            hour[0] += 1
                            cell[0] += 1
                            what = ledger.objects.get(oo, "")
                            if what in staff_report.STONE:
                                cell[2] += 1
                            elif what in staff_report.DIAMOND:
                                cell[3] += 1
                            elif what == "ancient_debris":
                                cell[4] += 1
                        else:
                            hour[1] += 1
                            cell[1] += 1
                    counted += len(rows)
                    if len(rows) < WORLD_CHUNK:
                        break
                    if counted >= most or time.monotonic() > deadline:
                        stopped = True
                if stopped:
                    break
        except sqlite3.OperationalError as e:
            # Out of time, or the game holding the database: what was counted stays, the rest is read next time.
            if "interrupt" not in str(e).lower():
                out["note"] = f"Ledger's database was busy ({e}): the rest next time"
            stopped = True
        finally:
            ledger.db.set_progress_handler(None, 0)
        out["caught_up"] = not stopped
        out["rows"] = counted
    finally:
        with contextlib.suppress(sqlite3.Error):
            ledger.db.close()
    out["hours"] = {h: v for h, v in hours.items() if h >= since[:13]}
    out["days"] = {d: v for d, v in days.items() if d >= since[:10]}
    return out


# ---------------------------------------------------------------- the job

def update(live: Path, staff: Path, now: dt.datetime, write: bool = True) -> list[str]:
    """Each part in turn; one that fails says so and leaves its file as it was."""
    folder = staff / "trends"
    said = []
    parts = (("history", lambda old: history(old, read_json(staff / "staff.json") or {}, now), None),
             ("players", lambda old: players(live, old, now), PLAYERS_EVERY),
             ("world", lambda old: world(live, old, now), WORLD_EVERY))
    for name, make, every in parts:
        path = folder / f"{name}.json"
        old = load(path)
        restart = ""
        if old and not readable(name, old, now):
            old, restart = {}, ", started again (what was kept was not in the shape expected)"
        if every and not due(old, every, now):
            said.append(f"{name}: not due yet")
            continue
        try:
            try:
                data = make(old)
            except _SHAPE:
                if not old:
                    raise
                old, restart = {}, ", started again (what was kept was not in the shape expected)"
                data = make(old)
        except FileNotFoundError:
            said.append(f"{name}: its source isn't there yet")
            continue
        except (OSError, sqlite3.Error, *_SHAPE) as e:
            said.append(f"{name}: not updated ({type(e).__name__})")
            continue
        if write:
            try:
                save(path, data)
            except OSError as e:
                said.append(f"{name}: not written ({type(e).__name__})")
                continue
        said.append(f"{name}: {summary(name, data)}{restart}")
    return said


# What a file of the wrong shape (hand-edited, cut short, an older layout) raises when it is read.
_SHAPE = (KeyError, TypeError, AttributeError, ValueError, IndexError)


def readable(name: str, data: dict, now: dt.datetime) -> bool:
    """Whether the page can answer from a kept file: one it can't is started again rather than kept for ever."""
    try:
        for answer in ANSWERS[name]:
            answer(data, None, now)
    except _SHAPE:
        return False
    return True


def summary(name: str, data: dict) -> str:
    if name == "history":
        return f"{len(data['hours'])} hours"
    if name == "players":
        return f"{len(data['base']['days'])} days, {len(data['base']['read'])} logs read" + \
            ("" if data["caught_up"] else ", more next time")
    return f"{data.get('rows', 0)} rows counted" + ("" if data["caught_up"] else ", more next time") + \
        (f" ({data['note']})" if data.get("note") else "")


# ---------------------------------------------------------------- what the page asks

def _days(query: dict, part: str) -> int:
    low, high, default = DAYS[part]
    raw = query.get("days")
    if raw in (None, ""):
        return default
    if not re.fullmatch(r"\d{1,3}", str(raw)) or not low <= int(raw) <= high:
        raise sp.Refused(400, f"days must be a whole number from {low} to {high}.")
    return int(raw)


def _file(panel, name: str) -> dict:
    data = load(panel.staff / "trends" / f"{name}.json")
    if not data:
        raise sp.Refused(404, "No trends yet: deploy/monkey-staff.sh writes them, the first within minutes of the "
                              "update going live.")
    return data


def _pacific_today(now: dt.datetime | None) -> dt.date:
    return (now or dt.datetime.now(server.UTC)).astimezone(calendar.PACIFIC).date()


def _span(part: str, days: int | None) -> int:
    return DAYS[part][2] if days is None else days


def _answer(panel, part: str, query: dict, now: dt.datetime | None, *answers) -> dict:
    days = _days(query, part)
    data = _file(panel, "world" if part == "ores" else part)
    try:
        return answers[0](data, days, now)
    except _SHAPE:
        raise sp.Refused(503, "The trends file is damaged: the staff job's next run starts it again.") from None


def trend_history(panel, query: dict, now: dt.datetime | None = None) -> dict:
    return _answer(panel, "history", query, now, history_answer)


def trend_players(panel, query: dict, now: dt.datetime | None = None) -> dict:
    return _answer(panel, "players", query, now, players_answer)


def trend_world(panel, query: dict, now: dt.datetime | None = None) -> dict:
    return _answer(panel, "world", query, now, world_answer)


def trend_ores(panel, query: dict, now: dt.datetime | None = None) -> dict:
    return _answer(panel, "ores", query, now, ores_answer)


def history_answer(data: dict, days: int | None, now: dt.datetime | None) -> dict:
    days = _span("history", days)
    since = (now or dt.datetime.now(server.UTC)).timestamp() - days * 86400
    return {"columns": ["hour", "avg", "p95", "players", "players_max", "memory", "cpu", "readings"],
            "hours": [r for r in data.get("hours", []) if r[0] >= since], "at": data.get("at"), "days": days}


def merged_days(data: dict) -> tuple[dict, dict]:
    """(day -> {name: minutes}, with the day's sessions; name -> first day) from the finished logs and latest.log."""
    days: dict = {}
    for layer in (data["base"]["days"], data["live"]["days"]):
        for day, v in layer.items():
            if not _date(day):
                continue
            into = days.setdefault(day, {"minutes": {}, "sessions": [], "joined": []})
            for name, minutes in v.get("minutes", {}).items():
                into["minutes"][name] = round(into["minutes"].get(name, 0) + minutes, 1)
            into["sessions"] += v.get("sessions", [])
            into["joined"] = sorted({*into["joined"], *v.get("joined", [])})
    first = {**data["live"]["first"], **data["base"]["first"]}
    return days, {n: d for n, d in first.items() if _date(d)}


def retention(days: dict, first: dict, today: dt.date, logs_start: str | None = None) -> list[dict]:
    """For players new in each week (Monday to Sunday, Pacific): how many played again a day or more after their
    first day, and 7 days or more after it. A player counts towards a share once that much time has passed.
    Everyone in the first log looks new, players from before the logs began too: those seen first on its day are
    left out, and that week's row says "partial"."""
    played: dict[str, set[dt.date]] = {}
    for day, v in days.items():
        for name in v.get("joined", []):    # the days they joined: a session that runs past midnight is no return
            if _date(day):
                played.setdefault(name, set()).add(dt.date.fromisoformat(day))
    began = _date(logs_start)
    weeks: dict[dt.date, list[str]] = {}
    for name, day in first.items():
        start = _date(day)
        if start and day in days and start != began:    # first seen within the days kept: a cohort can be followed
            weeks.setdefault(start - dt.timedelta(days=start.weekday()), []).append(name)
    began_week = began - dt.timedelta(days=began.weekday()) if began else None
    out = []
    for week in sorted(weeks):
        names = weeks[week]
        row = {"week": week.isoformat(), "new": len(names), "partial": week == began_week}
        for n in (1, 7):
            ready = [p for p in names if dt.date.fromisoformat(first[p]) + dt.timedelta(days=n) <= today]
            back = [p for p in ready
                    if any(d >= dt.date.fromisoformat(first[p]) + dt.timedelta(days=n) for d in played.get(p, ()))]
            row[f"due_{n}d"], row[f"back_{n}d"] = len(ready), len(back)
        out.append(row)
    return out


def players_answer(data: dict, span: int | None, now: dt.datetime | None) -> dict:
    span = _span("players", span)
    days, first = merged_days(data)
    began = data.get("start") if _date(data.get("start")) else None
    today = _pacific_today(now)
    since = (today - dt.timedelta(days=span - 1)).isoformat()
    rows, lengths = [], [0] * (len(SESSION_BUCKETS) + 1)
    for day in sorted(d for d in days if d >= since):
        v = days[day]
        sessions = v["sessions"]
        for s in sessions:
            lengths[sum(1 for edge in SESSION_BUCKETS if s >= edge)] += 1
        # On the day the logs begin, "new" can't be told: everyone in that log looks it.
        new = None if day == began else sum(1 for n in v["minutes"] if first.get(n) == day)
        rows.append({"day": day, "unique": len(v["minutes"]), "new": new,
                     "hours": round(sum(v["minutes"].values()) / 60, 1), "sessions": len(sessions),
                     "median_minutes": round(statistics.median(sessions)) if sessions else None})
    edges = ["under 10 min", "10-30 min", "30-60 min", "1-2 h", "2-4 h", "4 h and more"]
    return {"days": rows, "session_lengths": [{"bucket": e, "count": c} for e, c in zip(edges, lengths, strict=True)],
            "retention": retention(days, first, today, began), "logs_start": began, "zone": "Pacific",
            "at": data.get("at"), "complete": bool(data.get("caught_up"))}


def _week_start(today: dt.date) -> str:
    return (today - dt.timedelta(days=today.weekday())).isoformat()


def world_answer(data: dict, span: int | None, now: dt.datetime | None) -> dict:
    span = _span("world", span)
    today = _pacific_today(now)
    since = (today - dt.timedelta(days=span - 1)).isoformat()
    hours = [[h, *v] for h, v in sorted(data.get("hours", {}).items()) if h[:10] >= since]
    week = _week_start(today)
    miners: dict[str, list[int]] = {}
    for day, cells in data.get("days", {}).items():
        if day >= week:
            for name, cell in cells.items():
                total = miners.setdefault(name, [0, 0])
                total[0] += cell[0]
                total[1] += cell[1]
    top = sorted(miners.items(), key=lambda kv: (-kv[1][0], kv[0].lower()))[:TOP]
    return {"columns": ["hour", "broken", "placed"], "hours": hours, "week": week,
            "top_miners": [{"name": n, "broken": b, "placed": p} for n, (b, p) in top],
            "zone": "Pacific", "at": data.get("at"), "complete": bool(data.get("caught_up")), "note": data.get("note")}


def ores_answer(data: dict, span: int | None, now: dt.datetime | None) -> dict:
    """Diamond ore and ancient debris per 1,000 stone, per player, with the weekly report's x-ray test
    (staff_report.xray_rule): enough stone and ores, and well above the others' median."""
    span = _span("ores", span)
    since = (_pacific_today(now) - dt.timedelta(days=span - 1)).isoformat()
    totals: dict[str, list[int]] = {}
    for day, cells in data.get("days", {}).items():
        if day >= since:
            for name, cell in cells.items():
                total = totals.setdefault(name, [0, 0, 0])
                for i in range(3):
                    total[i] += cell[2 + i]
    rows = []
    for name, (stone, diamond, debris) in totals.items():
        if stone or diamond or debris:
            rows.append({"name": name, "stone": stone, "diamond": diamond, "debris": debris,
                         "per_k": round(1000 * (diamond + debris) / stone, 1) if stone else None})
    median, flagged = staff_report.xray_rule({r["name"]: (r["diamond"] + r["debris"], r["per_k"]) for r in rows
                                              if r["stone"] >= staff_report.XRAY_STONE})
    for r in rows:
        r["outlier"] = r["name"] in flagged
    rows.sort(key=lambda r: (-(r["per_k"] or 0), r["name"].lower()))
    return {"players": rows, "median_per_k": median, "since": since, "zone": "Pacific", "at": data.get("at"),
            "complete": bool(data.get("caught_up")),
            "about": "A hint, never proof: strip-mining at diamond level or trading for ores shows high too."}


ANSWERS = {"history": (history_answer,), "players": (players_answer,), "world": (world_answer, ores_answer)}

STANDINGS_KEPT = 52
_WEEK_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.json")


def trend_standings(panel, query: dict) -> dict:
    """Each closed week's table, oldest first: rank, points and the columns behind them, never the members."""
    folder = Path(getattr(panel, "standings", None) or "/srv/monkey/standings") / "weeks"
    try:
        names = sorted(e.name for e in os.scandir(folder) if _WEEK_FILE.fullmatch(e.name))[-STANDINGS_KEPT:]
    except OSError:
        return {"weeks": [], "note": "No closed weeks to read yet (STANDINGS_DIR/weeks)."}
    weeks = []
    for name in names:
        week = read_json(folder / name)
        if not isinstance(week, dict) or not isinstance(week.get("rows"), list):
            continue
        rows = [{k: r.get(k) for k in ("name", "id", "rank", "points", "cup", "strength", "kills", "bounties",
                                       "outposts")}
                for r in week["rows"] if isinstance(r, dict) and isinstance(r.get("name"), str)]
        weeks.append({"end": week.get("end"), "start": week.get("start"), "launched": week.get("launched"),
                      "rows": rows})
    return {"weeks": weeks}


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- wiring

ROUTES = {
    ("GET", "/api/trend-history"): lambda p, u, q, b: trend_history(p, q),
    ("GET", "/api/trend-players"): lambda p, u, q, b: trend_players(p, q),
    ("GET", "/api/trend-world"): lambda p, u, q, b: trend_world(p, q),
    ("GET", "/api/trend-ores"): lambda p, u, q, b: trend_ores(p, q),
    ("GET", "/api/trend-standings"): lambda p, u, q, b: trend_standings(p, q),
}
NEEDS = dict.fromkeys(ROUTES, "moderator")


def register(module) -> None:
    """Adds these routes to staff_panel's (`module` is staff_panel itself, as it runs)."""
    global sp
    sp = module
    module.ROUTES.update(ROUTES)
    module.NEEDS.update(NEEDS)
    module.PATHS.update(path for _, path in ROUTES)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="command", required=True)
    for name, about in (("show", "prints what a run would keep (changes nothing)"), ("update", "updates the files")):
        p = sub.add_parser(name, help=about)
        p.add_argument("live", type=Path, help="the running release's folder (LIVE_DIR)")
        p.add_argument("--staff", type=Path, required=True, help="the staff page's folder (STAFF_DIR)")
        p.add_argument("--at", type=server.parse_time, help="pretend it is this time (ISO 8601; UTC if no offset)")
    args = ap.parse_args(argv)
    now = server.job_time(args)
    for line in update(args.live, args.staff, now, write=args.command == "update"):
        print(f"trends: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
