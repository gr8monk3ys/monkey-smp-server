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
  (read again each time, kept apart in "live"). A session that a log ends without a leave line ends at the server's
  "Stopping server", its next "Starting minecraft server", or (latest.log) now. Days are Pacific, as the log's times.
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
    """The hours kept before, with those staff.json holds worked out again (but its oldest, which it holds only part
    of), and none older than KEEP."""
    since = (now - KEEP).timestamp()
    kept = {int(r[0]): r for r in old.get("hours") or [] if isinstance(r, list) and len(r) == 8
            and isinstance(r[0], int) and r[0] >= since}
    fresh = hours_of(status.get("history") if isinstance(status.get("history"), list) else [])
    oldest = min(fresh, default=None)
    for hour, row in fresh.items():
        if hour != oldest or hour not in kept:
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

    def _end(self, name: str, until: dt.datetime) -> None:
        start = self.open.pop(name)
        if until < start:
            return
        whole = round((until - start).total_seconds() / 60)
        sessions = self.days.setdefault(_day(start), {"minutes": {}, "sessions": [], "joined": []})["sessions"]
        if len(sessions) < SESSIONS_A_DAY:
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

    def end_all(self, until: dt.datetime) -> None:
        for name in list(self.open):
            self._end(name, until)

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
    base = {"read": read, "days": days, "first": first, "open": open_, "last": last}

    live_days: dict = {}
    live_first: dict = {}
    latest = folder / "latest.log"
    caught_up = took < LOGS_A_RUN
    try:
        small = latest.stat().st_size <= LATEST_MAX
    except OSError:
        small = False
    if caught_up and small:
        on_top = Sessions(live_days, live_first, open_, last)
        on_top.feed(staff_report.read_log(latest, None))
        on_top.end_all(max(pacific_now, on_top.last) if on_top.last else pacific_now)
        live_first = {n: d for n, d in live_first.items() if n not in first}
    return {"version": VERSION, "at": iso(now), "base": base,
            "live": {"days": live_days, "first": live_first}, "caught_up": caught_up}


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
            if "interrupt" not in str(e).lower():
                raise
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
        if every and not due(old, every, now):
            said.append(f"{name}: not due yet")
            continue
        try:
            data = make(old)
        except FileNotFoundError:
            said.append(f"{name}: its source isn't there yet")
            continue
        except (OSError, ValueError, sqlite3.Error) as e:
            said.append(f"{name}: not updated ({type(e).__name__})")
            continue
        if write:
            try:
                save(path, data)
            except OSError as e:
                said.append(f"{name}: not written ({type(e).__name__})")
                continue
        said.append(f"{name}: {summary(name, data)}")
    return said


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


def trend_history(panel, query: dict, now: dt.datetime | None = None) -> dict:
    days = _days(query, "history")
    data = _file(panel, "history")
    since = (now or dt.datetime.now(server.UTC)).timestamp() - days * 86400
    return {"columns": ["hour", "avg", "p95", "players", "players_max", "memory", "cpu", "readings"],
            "hours": [r for r in data.get("hours", []) if r[0] >= since], "at": data.get("at"), "days": days}


def merged_days(data: dict) -> tuple[dict, dict]:
    """(day -> {name: minutes}, with the day's sessions; name -> first day) from the finished logs and latest.log."""
    days: dict = {}
    for layer in (data["base"]["days"], data["live"]["days"]):
        for day, v in layer.items():
            into = days.setdefault(day, {"minutes": {}, "sessions": [], "joined": []})
            for name, minutes in v.get("minutes", {}).items():
                into["minutes"][name] = round(into["minutes"].get(name, 0) + minutes, 1)
            into["sessions"] += v.get("sessions", [])
            into["joined"] = sorted({*into["joined"], *v.get("joined", [])})
    return days, {**data["live"]["first"], **data["base"]["first"]}


def retention(days: dict, first: dict, today: dt.date) -> list[dict]:
    """For players new in each week (Monday to Sunday, Pacific): how many played again a day or more after their
    first day, and 7 days or more after it. A player counts towards a share once that much time has passed."""
    played: dict[str, set[dt.date]] = {}
    for day, v in days.items():
        for name in v["joined"]:    # the days they joined: a session that runs past midnight is no coming back
            played.setdefault(name, set()).add(dt.date.fromisoformat(day))
    weeks: dict[dt.date, list[str]] = {}
    for name, day in first.items():
        start = dt.date.fromisoformat(day)
        if day in days:     # first seen within the days kept: a cohort can be followed
            weeks.setdefault(start - dt.timedelta(days=start.weekday()), []).append(name)
    out = []
    for week in sorted(weeks):
        names = weeks[week]
        row = {"week": week.isoformat(), "new": len(names)}
        for n in (1, 7):
            ready = [p for p in names if dt.date.fromisoformat(first[p]) + dt.timedelta(days=n) <= today]
            back = [p for p in ready
                    if any(d >= dt.date.fromisoformat(first[p]) + dt.timedelta(days=n) for d in played.get(p, ()))]
            row[f"due_{n}d"], row[f"back_{n}d"] = len(ready), len(back)
        out.append(row)
    return out


def trend_players(panel, query: dict, now: dt.datetime | None = None) -> dict:
    span = _days(query, "players")
    data = _file(panel, "players")
    days, first = merged_days(data)
    today = _pacific_today(now)
    since = (today - dt.timedelta(days=span - 1)).isoformat()
    rows, lengths = [], [0] * (len(SESSION_BUCKETS) + 1)
    for day in sorted(d for d in days if d >= since):
        v = days[day]
        sessions = v["sessions"]
        for s in sessions:
            lengths[sum(1 for edge in SESSION_BUCKETS if s >= edge)] += 1
        new = sum(1 for n in v["minutes"] if first.get(n) == day)
        rows.append({"day": day, "unique": len(v["minutes"]), "new": new,
                     "hours": round(sum(v["minutes"].values()) / 60, 1), "sessions": len(sessions),
                     "median_minutes": round(statistics.median(sessions)) if sessions else None})
    edges = ["under 10 min", "10-30 min", "30-60 min", "1-2 h", "2-4 h", "4 h and more"]
    return {"days": rows, "session_lengths": [{"bucket": e, "count": c} for e, c in zip(edges, lengths, strict=True)],
            "retention": retention(days, first, today), "zone": "Pacific", "at": data.get("at"),
            "complete": bool(data.get("caught_up"))}


def _week_start(today: dt.date) -> str:
    return (today - dt.timedelta(days=today.weekday())).isoformat()


def trend_world(panel, query: dict, now: dt.datetime | None = None) -> dict:
    span = _days(query, "world")
    data = _file(panel, "world")
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


def trend_ores(panel, query: dict, now: dt.datetime | None = None) -> dict:
    """Diamond ore and ancient debris per 1,000 stone, per player, with the weekly report's x-ray test
    (staff_report.Week.check_xray): enough stone and ores, and well above the others' median."""
    span = _days(query, "ores")
    data = _file(panel, "world")
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
    rates = [r["per_k"] for r in rows if r["stone"] >= staff_report.XRAY_STONE and r["per_k"] is not None]
    median = statistics.median(rates) if len(rates) >= 3 else None
    for r in rows:
        enough = r["stone"] >= staff_report.XRAY_STONE and r["diamond"] + r["debris"] >= staff_report.XRAY_ORES
        # As the weekly report does it: a median of 0 compares with the fixed rate, or any ore at all would stand out.
        rate = r["per_k"] or 0
        high = rate >= staff_report.XRAY_TIMES * median if median else rate >= staff_report.XRAY_RATE
        r["outlier"] = bool(enough and rate >= 2 and high)
    rows.sort(key=lambda r: (-(r["per_k"] or 0), r["name"].lower()))
    return {"players": rows, "median_per_k": median, "since": since, "zone": "Pacific", "at": data.get("at"),
            "complete": bool(data.get("caught_up")),
            "about": "A hint, never proof: strip-mining at diamond level or trading for ores shows high too."}


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
