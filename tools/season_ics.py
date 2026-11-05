"""Season I's calendar as a file players can put on their phones: site/public/monkey-smp-season-1.ics.

    python tools/season_ics.py            write the file
    python tools/season_ics.py --check    exit 1 if the committed file differs from what this makes (validate.py
                                          runs the same check)

What goes in is what the site already tells players, and no more:
  - the launch (the front page and the guide): Saturday 7 November, 5 PM Pacific;
  - the week's event, Saturdays at 6 PM Pacific (/guide/week): "a Faction Raid, Arena Glory, a Build Battle, or the
    border breaking open". Which one falls on which Saturday is not on the site (the Town Crier at spawn gives the
    next two), so the calendar says "Saturday event" and not more. Only the finale is named, because the site gives
    its date (What changed, 29 October: "the finale is on 23 January");
  - the week's standings closing, Sundays at 7 PM Pacific (/guide/week).
The other names in status.SCHEDULE stay out until the site publishes them: add one to ANNOUNCED then. A moved event
needs no edit here: the times come from status.event_time() and status.close_time(), which status.dates() uses too.
Bump SEQUENCE and PUBLISHED together whenever the events change (a test holds the two to the events).

The file follows RFC 5545: CRLF line endings, lines folded at 75 octets (never inside a UTF-8 character), text
escaped, one VEVENT a moment, and times as UTC instants worked out from Pacific time with the time zone database,
so 6 PM Pacific stays 6 PM Pacific across a daylight saving change (Season I is all standard time; a later
season's isn't). Nothing reads the clock: DTSTAMP is PUBLISHED, so the output is the same on any day. UIDs come
from the season, the week and the kind of event, never from the time, so moving an event updates it in a phone's
calendar instead of adding a copy, and calendars take the change by SEQUENCE. The site gives no length, so every event
says an hour (LENGTH), for calendars to draw and remind about them alike.

Stdlib only, Python 3.11 or newer, with tools/ on the path like the rest.
"""
import argparse
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path

import status

import season_calendar as calendar
from repo import REPO, Repo

SITE = "https://monkeysmp.lscaturchio.xyz"   # site/src/lib/config.ts's SITE_URL (a test keeps them in step)
ADDRESS = "monkeysmp.lscaturchio.xyz"        # the server address (site/config.json's ADDRESS; a test checks it)
NAME = "monkey-smp-season-1.ics"
DOMAIN = "monkeysmp.lscaturchio.xyz"         # UIDs end @DOMAIN
PRODID = "-//Monkey SMP//Season I calendar//EN"
# The events' revision: bump both when an event moves or its words change, so a phone that has the old file takes the
# new one (calendars rank by SEQUENCE). PUBLISHED, for DTSTAMP, is not the clock: the file has to come out the same
# every time.
SEQUENCE = 0
PUBLISHED = dt.datetime(2026, 11, 4, tzinfo=calendar.UTC)
LENGTH = "PT1H"
# The names the site already gives players (the module docstring); every other Saturday is "Saturday event".
ANNOUNCED = {"Season I opens": "Season I opens", "The finale": "Season I finale"}
SATURDAY = "Saturday event"
LINE = 75   # octets in a line, its CRLF not counted (RFC 5545, 3.1)


@dataclass(frozen=True)
class Event:
    uid: str
    start: dt.datetime   # an aware time
    summary: str
    description: str
    url: str


# ---------------------------------------------------------------- the events


def events(season: calendar.Season = calendar.SEASON, number: int = 1) -> list[Event]:
    """Every event, first first. The kinds and words are Season I's (status.SCHEDULE, whose names are held back unless
    ANNOUNCED): another season moves only the times and UIDs, until its release gives it words of its own."""
    found = []
    for week, what, _ in status.SCHEDULE:
        start = status.event_time(week, season)
        kind = "launch" if week == 0 else "finale" if week == status.LAST_WEEK else "event"
        title = ANNOUNCED.get(what, SATURDAY)
        about = {
            "launch": "Season I opens and everyone is let in at once.",
            "finale": "The finale ends the season, and then the world locks.",
            "event": "The week's event: a Faction Raid, Arena Glory, a Build Battle, or the border breaking open. "
                     "The Town Crier at spawn has the next two.",
        }[kind]
        found.append(Event(f"season-{number}-week-{week:02}-{kind}@{DOMAIN}", start, f"Monkey SMP: {title}",
                           f"{about} {when(start)} Server address: {ADDRESS}.",
                           f"{SITE}/guide" if kind == "launch" else f"{SITE}/guide/week"))
    for week in range(1, status.LAST_WEEK + 1):
        start = status.close_time(week, season)
        found.append(Event(f"season-{number}-week-{week:02}-close@{DOMAIN}", start,
                           "Monkey SMP: weekly standings close",
                           f"The week's faction standings close and go up in the Discord. {when(start)} "
                           f"The standings so far are at {SITE}/guide/standings.", f"{SITE}/guide/standings"))
    return sorted(found, key=lambda e: (e.start, e.uid))


def when(start: dt.datetime) -> str:
    """'6 PM Pacific, 9 PM Eastern. Your calendar shows it in your own time.'"""
    said = calendar.words(start)
    return f"{said['pacific']}, {said['eastern']}. Your calendar shows it in your own time."


# ---------------------------------------------------------------- RFC 5545


def utc(when: dt.datetime) -> str:
    """'20261108T020000Z': an instant in UTC."""
    return when.astimezone(calendar.UTC).strftime("%Y%m%dT%H%M%SZ")


def escape(text: str) -> str:
    """A TEXT value (RFC 5545, 3.3.11): backslash, semicolon and comma escaped, a line break as \\n."""
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"))


def fold(line: str) -> list[str]:
    """A content line as physical lines of at most 75 octets: a break is a CRLF and one space, and never falls
    inside a UTF-8 character."""
    out, current, size = [], "", 0
    for ch in line:
        width = len(ch.encode("utf-8"))
        if size + width > LINE - (1 if out else 0):
            out.append(current)
            current, size = "", 0
        current += ch
        size += width
    out.append(current)
    return [out[0], *(" " + part for part in out[1:])]


def render() -> bytes:
    """The calendar file, as the bytes to commit."""
    stamp = utc(PUBLISHED)
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape('Monkey SMP Season I')}",
        f"X-WR-CALDESC:{escape('The weekly event and standings of Monkey SMP Season I, in your own time zone.')}",
        "REFRESH-INTERVAL;VALUE=DURATION:P1D", "X-PUBLISHED-TTL:P1D",
    ]
    for e in events():
        lines += [
            "BEGIN:VEVENT", f"UID:{e.uid}", f"SEQUENCE:{SEQUENCE}", f"DTSTAMP:{stamp}", f"LAST-MODIFIED:{stamp}",
            f"DTSTART:{utc(e.start)}", f"DURATION:{LENGTH}",
            f"SUMMARY:{escape(e.summary)}", f"DESCRIPTION:{escape(e.description)}",
            f"LOCATION:{escape('Monkey SMP, Minecraft Java: ' + ADDRESS)}", f"URL:{e.url}", "STATUS:CONFIRMED",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "".join(part + "\r\n" for line in lines for part in fold(line)).encode("utf-8")


# ---------------------------------------------------------------- writing and checking


def path(repo: Repo = REPO) -> Path:
    return repo.root / "site" / "public" / NAME


def problems(repo: Repo = REPO) -> list[str]:
    """What is wrong with the committed file: missing, or not what render() makes."""
    file = path(repo)
    if not file.is_file():
        return [f"site/public/{NAME} is missing (run python tools/season_ics.py)"]
    if file.read_bytes() != render():
        return [f"site/public/{NAME} is out of date (run python tools/season_ics.py)"]
    return []


def main(argv=None, repo: Repo = REPO) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="change nothing; exit 1 if the file is out of date")
    a = ap.parse_args(argv)
    if a.check:
        found = problems(repo)
        for e in found:
            print("ERROR", e)
        return 1 if found else 0
    file = path(repo)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(render())
    print(f"wrote site/public/{NAME}: {len(events())} events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
