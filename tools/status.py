"""The server's public status for the website: online or not, how many are playing, what is next and the border.

    python3 tools/status.py schedule                                 the season's dates the status counts down to
    python3 tools/status.py show WORLD [--at TIME] [--docker DIR]    prints the status (changes nothing)
    python3 tools/status.py write WORLD --docker DIR --out FILE      writes it (deploy/monkey-status.sh, every 2 min)

The front page and the guide read it from https://map.monkeysmp.lscaturchio.xyz/status.json (site/config.json's
STATUS_URL): Caddy serves the file next to the live map, with an allow-origin header for the site, so no new
port opens (deploy/Caddyfile, docs/LIVE.md, "The website's status"). The file is public, so it holds counts and
the published schedule only: never a player's name, an address or anything from the settings.

    {"version": 1, "checked": "2026-11-15T02:00:00Z", "season": 1, "phase": "live", "opens": "2026-11-08T01:00:00Z",
     "online": true, "players": 3,
     "next": {"what": "Faction Raid I", "at": "2026-11-15T02:00:00Z"},
     "border": {"size": 2500, "growing_to": null, "next": {"size": 4000, "at": "2026-11-22T02:00:00Z"}}}

- phase: "preseason" before the launch, "live" from it, "offseason" once the season's last week is over (week 12,
  the locked world). players is null unless the season is live and the server answered `list`: before the launch
  the only people on are staff testing.
- next: the season's next Saturday event (docs/SEASONS.md, "Season I calendar") or Sunday's standings close,
  whichever comes first; null once the season is over.
- border: the Overworld's saved border (the server saves every 5 minutes), growing_to while it grows, and the
  next border act on the calendar that makes it bigger. null when the world has no border saved.

SCHEDULE is the calendar's events in words, a copy of the table in docs/SEASONS.md (a test keeps them in step);
the dates come from tools/season_calendar.py, so moving the season moves them. Stdlib only (plus tools/), Python
3.10 or newer, so it runs on the VPS from the checkout.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import rcon as server
import saved_world
import season_calendar as calendar

VERSION = 1
SEASON = 1
EVENT_TIME = dt.time(18, 0)   # Saturday's event, Pacific (the launch itself is at 5 PM)
CLOSE_TIME = dt.time(19, 0)   # Sunday's standings close, Pacific (deploy/monkey-standings.timer)
LAST_WEEK = 11                # the finale; the world locks after it, and week 12 is the off-season

# Season I's Saturdays: (week, the event in words, the Overworld border it grows to, if it is a border act).
SCHEDULE: tuple[tuple[int, str, int | None], ...] = (
    (0, "Season I opens", None),
    (1, "Faction Raid I", None),
    (2, "The border breaks", 4000),
    (3, "Dragon Night", None),
    (4, "Faction Raid II", None),
    (5, "Netherite age", None),
    (6, "Midwinter", None),
    (7, "The border breaks again", 6000),
    (8, "Build Battle II", None),
    (9, "Arena Glory II", None),
    (10, "Faction Raid III", None),
    (11, "The finale", None),
)
CLOSE = "Weekly standings close"
_LIST = re.compile(r"There are (\d+) of a max")


def iso(when: dt.datetime) -> str:
    """'2026-11-08T01:00:00Z': UTC, to the second."""
    return when.astimezone(calendar.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def pacific(day: dt.date, time: dt.time) -> dt.datetime:
    return dt.datetime.combine(day, time, calendar.PACIFIC)


def dates() -> list[tuple[dt.datetime, str, int | None]]:
    """Every dated item of the season, first first: (when, what, the border it grows to)."""
    out = [(calendar.LAUNCH if week == 0 else pacific(calendar.saturday(week), EVENT_TIME), what, size)
           for week, what, size in SCHEDULE]
    out += [(pacific(calendar.week_start(week) + dt.timedelta(days=6), CLOSE_TIME), CLOSE, None)
            for week in range(1, LAST_WEEK + 1)]
    return sorted(out, key=lambda item: item[0])


def phase(now: dt.datetime) -> str:
    if now < calendar.LAUNCH:
        return "preseason"
    return "offseason" if calendar.week_at(now) > LAST_WEEK else "live"


def players(answer: str) -> int | None:
    """How many are online, from `list`'s answer ("There are 3 of a max of 30 players online: ..."). Only the
    count is read: the names after it never leave this function."""
    m = _LIST.search(answer)
    return int(m[1]) if m else None


def online_count(rcon) -> tuple[bool, int | None]:
    """(online, players): online when the server is running and answers `list`."""
    try:
        if not rcon.running():
            return False, None
        return True, players(rcon("list"))
    except server.RconError:
        return False, None


def border(world: Path, now: dt.datetime) -> dict | None:
    try:
        saved = saved_world.border(world)
    except (OSError, ValueError):   # a save half-written as it was read: leave the border out this time
        saved = None
    if saved is None:
        return None
    target = max(saved.size, saved.target)
    nxt = next(({"size": size, "at": iso(when)} for when, _, size in dates()
                if size is not None and when > now and size > target), None)
    return {"size": round(saved.size), "growing_to": round(saved.target) if saved.target != saved.size else None,
            "next": nxt}


def status(world: Path, now: dt.datetime, rcon=None) -> dict:
    """The status as of `now`. rcon None: the server isn't asked, and counts as offline."""
    now = now.astimezone(calendar.UTC)
    stage = phase(now)
    online, count = online_count(rcon) if rcon is not None else (False, None)
    upcoming = next(({"what": what, "at": iso(when)} for when, what, _ in dates() if when > now), None)
    return {
        "version": VERSION, "checked": iso(now), "season": SEASON, "phase": stage, "opens": iso(calendar.LAUNCH),
        "online": online, "players": count if stage == "live" else None,
        "next": upcoming, "border": border(world, now),
    }


def write(path: Path, data: dict) -> None:
    """Writes the file whole (a temporary file renamed over it), readable by everyone, so Caddy never serves half
    of one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".status-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
            f.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("schedule", help="the season's dates the status counts down to")
    for name, about in (("show", "prints the status (changes nothing)"), ("write", "writes the status file")):
        p = sub.add_parser(name, help=about)
        p.add_argument("world", type=Path, help="the world folder (server/world)")
        p.add_argument("--at", type=server.parse_time, help="pretend it is this time (ISO 8601; UTC if no offset)")
        p.add_argument("--docker", type=Path, required=name == "write",
                       help="the release's docker folder (asks the server through it; left out: offline)")
        if name == "write":
            p.add_argument("--out", type=Path, required=True, help="the file to write (/srv/monkey/status/status.json)")
    args = ap.parse_args(argv)

    if args.command == "schedule":
        for when, what, size in dates():
            words = calendar.words(when)
            print(f"{calendar.short_day(when)}, {words['pacific']}: {what}{f' (to {size})' if size else ''}")
        return 0
    now = server.job_time(args)
    data = status(args.world, now, server.Docker(args.docker) if args.docker else None)
    if args.command == "show":
        print(json.dumps(data, indent=2))
        return 0
    write(args.out, data)
    print(f"{args.out}: {data['phase']}, {'online' if data['online'] else 'offline'}, "
          f"{data['players'] if data['players'] is not None else 'no'} player count")
    return 0


if __name__ == "__main__":
    sys.exit(main())
