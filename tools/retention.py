"""Retention from the server's own logs: who came back, and how many play each week.

    python tools/retention.py PATH/TO/server/logs

Reads every `YYYY-MM-DD-N.log.gz` (and `latest.log`, dated by its modification time) for
"NAME joined the game". Prints, for players new in each week, the share who came back at least 1, 7
and 30 days after their first day (a player counts once the window has passed), and the number of
different players each week. Stdlib only; nothing leaves the machine.
"""
import argparse
import datetime as dt
import gzip
import re
import sys
from collections import defaultdict
from pathlib import Path

JOIN = re.compile(r"\]: ([A-Za-z0-9_]{1,16}) joined the game")
DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})-\d+\.log\.gz$")
WINDOWS = (1, 7, 30)


def play_days(logs: Path) -> tuple[dict[str, set[dt.date]], dt.date | None]:
    """{player: days they joined}, and the last day the logs cover."""
    days: dict[str, set[dt.date]] = defaultdict(set)
    last = None
    for path in sorted(logs.iterdir()):
        if m := DATED.match(path.name):
            day = dt.date.fromisoformat(m.group(1))
            text = gzip.open(path, "rt", encoding="utf-8", errors="replace").read()
        elif path.name == "latest.log":
            day = dt.date.fromtimestamp(path.stat().st_mtime)
            text = path.read_text(encoding="utf-8", errors="replace")
        else:
            continue
        last = max(last or day, day)
        for name in JOIN.findall(text):
            days[name].add(day)
    return dict(days), last


def week(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def report(days: dict[str, set[dt.date]], last: dt.date) -> list[str]:
    cohorts: dict[dt.date, list[str]] = defaultdict(list)
    for name, played in days.items():
        cohorts[week(min(played))].append(name)
    lines = ["new players by week, and the share who came back after 1 / 7 / 30 days",
             f"{'week of':<12}{'new':>5}" + "".join(f"{'D' + str(n):>8}" for n in WINDOWS)]
    for start in sorted(cohorts):
        names = cohorts[start]
        cells = []
        for n in WINDOWS:
            due = [p for p in names if min(days[p]) + dt.timedelta(days=n) <= last]
            back = [p for p in due if any(d >= min(days[p]) + dt.timedelta(days=n) for d in days[p])]
            cells.append(f"{100 * len(back) // len(due)}%" if due else "-")
        lines.append(f"{start.isoformat():<12}{len(names):>5}" + "".join(f"{c:>8}" for c in cells))
    weekly: dict[dt.date, set[str]] = defaultdict(set)
    for name, played in days.items():
        for d in played:
            weekly[week(d)].add(name)
    lines += ["", "different players each week", *(f"{w.isoformat():<12}{len(weekly[w]):>5}" for w in sorted(weekly))]
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Retention from the server logs.")
    ap.add_argument("logs", type=Path, help="the server's logs/ folder")
    args = ap.parse_args(argv)
    days, last = play_days(args.logs)
    if not days or last is None:
        print(f"no joins found in {args.logs}")
        return 1
    print("\n".join(report(days, last)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
