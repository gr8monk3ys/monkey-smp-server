"""The server's private status for the staff page: how it is running now, and over the last day.

    python3 tools/staff_status.py show LIVE_DIR               prints the status (changes nothing)
    python3 tools/staff_status.py write LIVE_DIR --out FILE   writes it (deploy/monkey-staff.sh, every 2 min)

LIVE_DIR is the running release's folder. https://staff.monkeysmp.lscaturchio.xyz serves the file behind a password
(deploy/Caddyfile.staff, docs/LIVE.md, "The staff page"). tools/status.py is the public file, with counts only; this
one has the names of who is online and the machine's numbers, so it never goes next to the map or into the website.

    {"version": 1, "checked": "2026-11-15T02:00:00Z", "online": true,
     "container": {"state": "running", "uptime": "3 hours", "health": "healthy"},
     "tick": {"state": "The game is running normally", "target": 20.0, "tps": 20.0, "avg": 12.4, "p50": 11.9,
              "p95": 18.7, "p99": 31.0, "sample": 100},
     "players": {"count": 3, "max": 30, "names": ["Alpha", "Bravo", "Charlie"]},
     "host": {"memory": {"total": 16777216, "available": 4194304}, "swap": {"total": 2097152, "free": 2097152},
              "load": [1.2, 1.1, 0.9], "threads": 2, "disk": {"total": 322122547200, "free": 161061273600}},
     "release": "3.1.0",
     "backups": {"local": "2026-11-15T12:02:11Z", "offsite": "not set up"},
     "problems": {"read": true, "log": {"size": 52310, "head": "3f2a9c04e1b7d856", "up": true, "startup": 12},
                  "errors": [{"text": "Error sending packet", "count": 2, "first": "2026-11-15T01:10:00Z",
                              "last": "2026-11-15T01:40:00Z"}],
                  "lag": {"count": 1, "worst": 2034, "first": "2026-11-15T01:20:00Z", "last": "2026-11-15T01:20:00Z"},
                  "crashes": [{"when": "2026-11-14T22:00:00Z", "text": "Exception in server tick loop"}]},
     "history": [[1794621600, 12.4, 18.7, 3, 75.0, 60.0]]}

- online: the container is running and the server answered. container is null when docker itself failed; state is
  "not created" when there is no container. Memory and swap are in KiB, as /proc/meminfo gives them; disk in bytes.
- tick is one reading, what `tick query` says about the last few seconds (Sample: ticks, 100 is 5 seconds). It says
  nothing about the two minutes between readings, and a server with nobody on looks perfect. tps is what the average
  allows, never above the target.
- backups: local is when the newest copy in LIVE_DIR/backups was made. offsite is "not set up" (no settings file),
  "failing" (monkey-backup.sh's marker) or "on".
- problems is what has gone wrong lately, from LIVE_DIR/server/logs/latest.log and LIVE_DIR/server/crash-reports:
  errors logged since the server finished starting (the first line of each, no stack trace), the times it fell at
  least 2 seconds behind ("Can't keep up!"), and crash reports. Warnings aren't kept, nor errors from while it starts:
  every start logs the same dozen, so startup only counts them. Log lines carry no date, so first and last are the
  readings that saw a line, up to 2 minutes late; what is logged just before a restart, after the last reading, is
  missed. The very first reading can't say when anything in the log happened, so what it finds is marked older.
  A group goes once a day has passed since its last line. log is where the reader got to, so that a reading
  only reads what is new. read is false when the log couldn't be read and crashes is null when the reports couldn't,
  which says nothing about whether anything went wrong.
- history is the last day's readings, oldest first, as [unix time, avg, p95, players, memory, cpu], with nulls for a
  reading the server didn't answer. memory is the share of the machine's memory in use, and cpu the share of its CPU
  in use since the reading before (from /proc/stat, host.cpu keeping the counters), both in percent. They are the
  machine's, so they are there while the server is off too. It is carried over from the file before, so a restart of
  this job loses nothing (a row from before memory and load were kept gets nulls for them), and it holds counts,
  never names.

- advice is what the problems probably are, in plain words (tools/staff_watch.py), and alerts what it last told the
  staff channel. With STAFF_WEBHOOK_URL in the environment, `write` posts a problem worth it there when it first shows
  (then at most once in 6 hours while it lasts), says when a number is back to normal, and posts each new crash.

It only reads: the release's version from the manifest (only that key: the manifest also holds the seed, which must
never reach this file), the container's own `monkey rcon`, the log, and one line of each crash report (the rest of a
report can hold the seed). Log text goes through plain() first: a line that mentions a secret is left out whole, and
addresses, links and long numbers are masked. Stdlib only (plus tools/), Python 3.10 or newer, so it runs on the VPS
from the checkout.
"""
import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.request
from pathlib import Path

import staff_watch
import status as public

import rcon as server

VERSION = 2         # 2: a reading's sixth number is CPU in use; in 1 it was the load average, so it is dropped
HISTORY = dt.timedelta(hours=24)
READING = 6                     # a row of the history: time, average, P95, players, memory, load
BACKUP_NAME = re.compile(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}")
BACKUP_SETTINGS = Path("/etc/monkey-backup.env")
BACKUP_FAILING = Path("/var/lib/monkey-backup/failing")
MEMINFO = Path("/proc/meminfo")
PROC_STAT = Path("/proc/stat")
LOG_READ = 8 * 1024 * 1024      # the most of the log one reading takes; a flood is caught up with over the next ones
ERRORS_KEPT = 30
CRASHES_KEPT = 5
TEXT_KEPT = 160
LEFT_OUT = "A message that may hold something private was left out. It is in the server's log."

_TICK = re.compile(r"(?P<state>.*?)Target tick rate: (?P<target>[\d.]+) per second.*?"
                   r"Average time per tick: (?P<avg>[\d.]+)ms.*?"
                   r"P50: (?P<p50>[\d.]+)ms P95: (?P<p95>[\d.]+)ms P99: (?P<p99>[\d.]+)ms\. "
                   r"Sample: (?P<sample>\d+)", re.S)
_LIST = re.compile(r"There are (\d+) of a max of (\d+) players online:?(.*)", re.S)
_UP = re.compile(r"Up (.+?)(?: \(.*\))?$")
# Anchored to the whole line, so nothing a player says can pass for one: chat is always the text of an INFO line.
_LOG_LINE = re.compile(rb"^\[\d\d:\d\d:\d\d\] \[([^\]\n]*)/(ERROR|FATAL|WARN|INFO)\](?: \[[^\]\n]*\])?: ([^\n]*)$",
                       re.M)
_BEHIND = re.compile(rb"Can't keep up! .*?Running (\d+)ms")
_SECRET = re.compile(r"seed|secret|pass.?w|\bpass\b|\bpwd\b|token|api.?key|\bkey\b|key\s*[=:]|webhook|authorization"
                     r"|bearer|tebex|credential", re.I)
_LINK = re.compile(r"[a-z][a-z0-9+.-]*://\S+", re.I)
_ADDRESS = re.compile(r"\[[0-9a-f.%]*:[0-9a-f.%]*:[0-9a-f:.%]*\](?::\d+)?"                  # [2001:db8::1]:5678
                      r"|(?<![\w:.])(?=[0-9a-f:]*(?:::|(?:[0-9a-f]{1,4}:){4}))[0-9a-f:]{3,}(?![\w:.])"  # 2001:db8::1
                      r"|(?<![\w.])\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?(?![\w.])", re.I)         # 1.2.3.4:5678
_LONG_NUMBER = re.compile(r"\d{7,}")
_VARIES = re.compile(r"\b[0-9a-f-]{8,}\b|\d+", re.I)
_DESCRIPTION = re.compile(rb"^Description: ([^\r\n]*)", re.M)
_ERROR_FIELDS = {"text": str, "count": int, "first": str, "last": str}
_LAG_FIELDS = {"worst": int, "count": int, "first": str, "last": str}


def tick(answer: str) -> dict | None:
    """`tick query`'s answer in numbers, None when it isn't what the server normally says."""
    m = _TICK.search(answer)
    if not m:
        return None
    target, avg = float(m["target"]), float(m["avg"])
    return {"state": m["state"].strip(), "target": target, "tps": round(min(target, 1000 / avg), 1) if avg else target,
            "avg": avg, "p50": float(m["p50"]), "p95": float(m["p95"]), "p99": float(m["p99"]),
            "sample": int(m["sample"])}


def players(answer: str) -> dict | None:
    """`list`'s answer: how many, the most there can be, and who."""
    m = _LIST.search(answer)
    if not m:
        return None
    return {"count": int(m[1]), "max": int(m[2]), "names": [n.strip() for n in m[3].split(",") if n.strip()]}


def container(docker) -> dict | None:
    """What docker says about the server's container, None when docker failed. `--all`, so a stopped container
    reads as stopped rather than as no container."""
    try:
        done = docker.compose("ps", "--all", "--format", "json", "monkey", timeout=60)
    except server.RconError:
        return None
    if done.returncode != 0:
        return None
    rows: list[dict] = []
    try:
        for line in done.stdout.splitlines():   # one object a line since compose 2.21, one array before it
            row = json.loads(line)
            rows += row if isinstance(row, list) else [row]
    except ValueError:
        return None
    if not rows:
        return {"state": "not created", "uptime": None, "health": None}
    up = _UP.match(rows[0].get("Status", ""))
    return {"state": rows[0].get("State", "unknown"), "uptime": up[1] if up else None,
            "health": rows[0].get("Health") or None}


def ask(docker, command: str) -> str:
    """The server's answer, "" when it didn't give one: a server still starting isn't an error here, it is the news."""
    try:
        return docker(command)
    except server.RconError:
        return ""


def memory(meminfo: Path = MEMINFO) -> tuple[dict | None, dict | None]:
    """(memory, swap) in KiB, from /proc/meminfo; None for what it doesn't say."""
    try:
        text = meminfo.read_text(encoding="ascii")
    except OSError:
        return None, None
    kib = {m[1]: int(m[2]) for m in re.finditer(r"^(\w+):\s+(\d+) kB$", text, re.M)}
    if "MemTotal" not in kib or "SwapTotal" not in kib:
        return None, None
    mem = {"total": kib["MemTotal"], "available": kib["MemAvailable"]} if "MemAvailable" in kib else None
    swap = {"total": kib["SwapTotal"], "free": kib["SwapFree"]} if "SwapFree" in kib else None
    return mem, swap


def cpu_times(proc_stat: Path = PROC_STAT) -> dict | None:
    """The machine's CPU time so far, all of it and the idle part (idle and waiting on the disk), in the kernel's
    ticks; None when /proc/stat can't be read (Windows, the tests)."""
    try:
        with open(proc_stat, encoding="ascii") as f:
            first = f.readline().split()
    except OSError:
        return None
    if len(first) < 6 or first[0] != "cpu" or not all(n.isdigit() for n in first[1:]):
        return None
    ticks = [int(n) for n in first[1:9]]       # user nice system idle iowait irq softirq steal; guest is in user
    return {"total": sum(ticks), "idle": ticks[3] + ticks[4]}


def cpu_busy(now: dict | None, before) -> float | None:
    """The share of the CPU in use between two cpu_times() readings, in percent with one decimal."""
    if not now or not isinstance(before, dict) or not all(isinstance(before.get(k), int) for k in ("total", "idle")):
        return None
    total, idle = now["total"] - before["total"], now["idle"] - before["idle"]
    if total <= 0 or idle < 0 or idle > total:     # a reboot in between starts the counters again
        return None
    return round((total - idle) / total * 100, 1)


def host(live: Path, meminfo: Path = MEMINFO, proc_stat: Path = PROC_STAT) -> dict:
    mem, swap = memory(meminfo)
    try:
        used = shutil.disk_usage(live)
        disk = {"total": used.total, "free": used.free}
    except OSError:
        disk = None
    try:
        load = [round(n, 2) for n in os.getloadavg()]
    except (OSError, AttributeError):   # Windows has no load average, and the tests run there too
        load = None
    return {"memory": mem, "swap": swap, "load": load, "threads": os.cpu_count(), "disk": disk,
            "cpu": cpu_times(proc_stat)}


def release(live: Path) -> str | None:
    """The running release. Only the version leaves this function: the manifest also holds the world's seed."""
    try:
        version = json.loads((live / "monkey" / "manifest.json").read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError, AttributeError):
        return None
    return version if isinstance(version, str) else None


def last_backup(live: Path) -> str | None:
    """When the newest copy in LIVE_DIR/backups was made: its folder's time, which needs no guess at the time zone
    its name was written in."""
    try:
        names = [e.name for e in os.scandir(live / "backups") if e.is_dir() and BACKUP_NAME.fullmatch(e.name)]
        if not names:
            return None
        made = (live / "backups" / max(names)).stat().st_mtime
    except OSError:
        return None
    return public.iso(dt.datetime.fromtimestamp(made, server.UTC))


def offsite(settings: Path = BACKUP_SETTINGS, failing: Path = BACKUP_FAILING) -> str:
    """Whether the off-site copy is set up and working. Only asks whether the files exist; root alone can read them."""
    if not settings.exists():
        return "not set up"
    return "failing" if failing.exists() else "on"


def plain(text: str) -> str:
    """A line from the server's log fit for the page. One that mentions a secret is left out whole, not cut around."""
    if _SECRET.search(text):
        return LEFT_OUT
    text = _LONG_NUMBER.sub("<number>", _ADDRESS.sub("an address", _LINK.sub("<link>", text)))
    text = "".join(c if c.isprintable() else " " for c in text).strip()
    return text if len(text) <= TEXT_KEPT else text[:TEXT_KEPT - 3] + "..."


def new_lines(log: Path, reader) -> tuple[bytes, dict]:
    """The complete lines written since the last reading, and where that leaves the reader. Another first line, or a
    file shorter than the last reading got to, is a new log: the server starts one each time it starts."""
    with log.open("rb") as f:
        head = hashlib.sha256(f.readline(4096)).hexdigest()[:16]    # a hash, so no log text sits in the state
        size = f.seek(0, os.SEEK_END)
        same = (isinstance(reader, dict) and reader.get("head") == head and isinstance(reader.get("size"), int)
                and 0 <= reader["size"] <= size)
        start = reader["size"] if same else 0
        f.seek(start)
        chunk = f.read(LOG_READ)
    end = chunk.rfind(b"\n") + 1
    if not end and len(chunk) == LOG_READ:      # a line this long never fits: step over it
        end = LOG_READ
    startup = reader.get("startup") if same else 0
    return chunk[:end], {"size": start + end, "head": head, "up": same and reader.get("up") is True,
                         "startup": startup if isinstance(startup, int) else 0}


def recent_crashes(folder: Path, since: float) -> list[dict] | None:
    """The newest crash reports from the last day, None when the folder can't be read. Only the Description line is
    taken: the rest of a report describes the server, the seed included."""
    found = []
    try:
        for e in os.scandir(folder):
            if e.name.endswith(".txt"):
                with contextlib.suppress(FileNotFoundError):    # removed since the listing: the others still count
                    found.append((e.stat().st_mtime, e.path))
    except FileNotFoundError:   # the game makes the folder at its first crash
        return []
    except OSError:
        return None
    out = []
    for made, path in sorted(found, reverse=True)[:CRASHES_KEPT]:
        if made <= since:
            break
        try:
            with open(path, "rb") as f:
                said = _DESCRIPTION.search(f.read(4096))
        except OSError:
            said = None
        out.append({"when": public.iso(dt.datetime.fromtimestamp(made, server.UTC)),
                    "text": plain(said[1].decode("utf-8", "replace")) if said else None})
    return out


def is_current(row, fields: dict, since: str) -> bool:
    """A group from the file before: the right shape, and its last line within the day."""
    return (isinstance(row, dict) and all(isinstance(row.get(k), kind) for k, kind in fields.items())
            and row["last"] > since)


def mark_older(group: dict, first: bool) -> None:
    """A group the first reading found may be from any time before it; a line seen after that is known to be new."""
    if first:
        group["older"] = True
    else:
        group.pop("older", None)


def problems(live: Path, now: dt.datetime, old) -> dict:
    """What has gone wrong lately: the log's new lines added to the groups from the reading before."""
    old = old if isinstance(old, dict) else {}
    since, stamp = public.iso(now - HISTORY), public.iso(now)
    rows = old.get("errors") if isinstance(old.get("errors"), list) else []
    errors = {_VARIES.sub("#", row["text"])[:100]: row for row in rows if is_current(row, _ERROR_FIELDS, since)}
    lag = old.get("lag") if is_current(old.get("lag"), _LAG_FIELDS, since) else None
    reader, read = old.get("log"), True
    first = not isinstance(reader, dict)    # nothing says when these lines were written, only that it was by now
    chunk = b""
    try:
        chunk, reader = new_lines(live / "server" / "logs" / "latest.log", reader)
    except OSError:
        read = False
    for line in _LOG_LINE.finditer(chunk):
        thread, level, said = line[1], line[2], line[3]
        if level == b"INFO":
            if thread == b"Server thread" and said.startswith(b"Done ("):
                reader["up"] = True
        elif level == b"WARN":
            behind = _BEHIND.match(said) if reader["up"] else None
            if behind:
                lag = lag or {"worst": 0, "count": 0, "first": stamp, "last": stamp}
                lag.update(worst=max(lag["worst"], int(behind[1])), count=lag["count"] + 1, last=stamp)
                mark_older(lag, first)
        elif reader["up"] or level == b"FATAL" or staff_watch.blocks_start(said.decode("utf-8", "replace")):
            # A FATAL before the start finishes is why it didn't, and so is an error staff_watch knows stops a start
            # (a mod missing a dependency, the port taken); the dozen errors every start logs are only counted.
            text = plain(said.decode("utf-8", "replace"))
            row = errors.setdefault(_VARIES.sub("#", text)[:100], {"text": text, "count": 0, "first": stamp})
            row.update(text=text, count=row["count"] + 1, last=stamp)
            mark_older(row, first)
        else:
            reader["startup"] += 1
    newest = sorted(errors.values(), key=lambda row: row["last"], reverse=True)[:ERRORS_KEPT]
    return {"read": read, "log": reader, "errors": newest, "lag": lag,
            "crashes": recent_crashes(live / "server" / "crash-reports", (now - HISTORY).timestamp())}


def earlier(previous: Path | None) -> dict:
    """The file before. An unreadable one starts afresh: it is a picture of the last day, and it is written whole, so
    this is only ever the first run or someone's hand."""
    if previous is None:
        return {}
    try:
        old = json.loads(previous.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return old if isinstance(old, dict) else {}


def carried_over(old: dict, now: dt.datetime) -> list[list]:
    """The readings in the file before, without those older than a day. A file from before version 2 had the load
    average where CPU in use now goes: that number is dropped, not drawn as CPU."""
    rows = old.get("history")
    if not isinstance(rows, list):
        return []
    since = (now - HISTORY).timestamp()
    if old.get("version") != VERSION:
        rows = [[*row[:5], None] if isinstance(row, list) and len(row) == READING else row for row in rows]
    return [[*row, *[None] * (READING - len(row))] for row in rows
            if isinstance(row, list) and len(row) in (4, READING) and isinstance(row[0], int | float)
            and row[0] > since]


def shares(machine: dict, before: dict | None = None) -> tuple[float | None, float | None]:
    """(memory in use, CPU in use since the reading before), each in percent with one decimal, None for what isn't
    known: the first reading has no CPU number, since it needs two."""
    mem = machine.get("memory")
    used = round((mem["total"] - mem["available"]) / mem["total"] * 100, 1) if mem and mem["total"] > 0 else None
    old = before.get("cpu") if isinstance(before, dict) else None
    return used, cpu_busy(machine.get("cpu"), old)


def status(live: Path, now: dt.datetime, docker, previous: Path | None = None, meminfo: Path = MEMINFO,
           settings: Path = BACKUP_SETTINGS, failing: Path = BACKUP_FAILING, proc_stat: Path = PROC_STAT,
           alerting: bool = False) -> tuple[dict, list[str]]:
    """(the status as of `now`, with the readings in the file `previous` carried over; the lines to post to the staff
    channel). With `alerting` off there are none and the alert state carries over as it was. The caller writes the
    file before it posts, so a post is never sent again for want of the state that says it was."""
    now = now.astimezone(server.UTC)
    old = earlier(previous)
    box = container(docker)
    up = box is not None and box["state"] == "running"
    ticking = tick(ask(docker, "tick query")) if up else None
    who = players(ask(docker, "list")) if up else None
    online = ticking is not None or who is not None
    machine = host(live, meminfo, proc_stat)
    reading = [int(now.timestamp()), ticking["avg"] if ticking else None, ticking["p95"] if ticking else None,
               who["count"] if who else None, *shares(machine, old.get("host"))]
    data = {
        "version": VERSION, "checked": public.iso(now), "online": online, "container": box, "tick": ticking,
        "players": who, "host": machine, "release": release(live),
        "backups": {"local": last_backup(live), "offsite": offsite(settings, failing)},
        "problems": problems(live, now, old.get("problems")),
        "history": [*carried_over(old, now), reading],
    }
    data["advice"] = staff_watch.advice(data)
    data["alerts"] = old.get("alerts") if isinstance(old.get("alerts"), dict) else {}
    lines: list[str] = []
    if alerting:
        lines, data["alerts"] = staff_watch.alerts(data["alerts"], data["advice"], data["problems"].get("crashes"), now)
    return data, lines


def post_webhook(url: str, line: str) -> None:
    """One line to the staff channel, mentioning nobody. A post that fails changes nothing: the page still shows it."""
    body = json.dumps({"content": line[:1900], "allowed_mentions": {"parse": []}}).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json",
                                                              "User-Agent": "monkey-staff"})
    with contextlib.suppress(OSError, ValueError):
        urllib.request.urlopen(request, timeout=10).close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="command", required=True)
    for name, about in (("show", "prints the status (changes nothing)"), ("write", "writes the status file")):
        p = sub.add_parser(name, help=about)
        p.add_argument("live", type=Path, help="the running release's folder (LIVE_DIR)")
        p.add_argument("--at", type=server.parse_time, help="pretend it is this time (ISO 8601; UTC if no offset)")
        if name == "write":
            p.add_argument("--out", type=Path, required=True, help="the file to write (/srv/monkey/staff/staff.json)")
    args = ap.parse_args(argv)

    docker = server.Docker(args.live / "docker")
    now = server.job_time(args)
    if args.command == "show":
        print(json.dumps(status(args.live, now, docker)[0], indent=2))
        return 0
    # The staff channel only (deploy/monkey-staff.sh passes it in the environment, never on the command line), and
    # never the public webhook: these messages name what is wrong on the machine.
    hook = os.environ.get("STAFF_WEBHOOK_URL", "").strip()
    data, lines = status(args.live, now, docker, previous=args.out, alerting=bool(hook))
    try:
        public.write(args.out, data)
    except OSError:
        # Not written (a full disk, most likely), so the state that says what was posted isn't either, and the next
        # run would post the same again: post only in the first run of each hour, which needs no memory.
        if lines and now.minute < 2:
            post_webhook(hook, "\n".join(lines))
        raise
    if lines:
        post_webhook(hook, "\n".join(lines))
    count = data["players"]["count"] if data["players"] else "no"
    print(f"{args.out}: {'online' if data['online'] else 'offline'}, {count} player count, "
          f"{len(data['history'])} readings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
