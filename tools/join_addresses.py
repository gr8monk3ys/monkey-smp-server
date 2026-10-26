"""Joins per join address, from the server's own logs: which promotion channel brings players in.

    python tools/join_addresses.py PATH/TO/server/logs [--since YYYY-MM-DD]

Hostname Catcher logs "Player NAME connected via: ADDRESS" for every join. ADDRESS is the hostname the
player's client connected to after following the SRV record, so `yt.monkeysmp.lscaturchio.xyz` for a player
who typed the YouTube join address (docs/PROMOTION.md). Reads every `YYYY-MM-DD-N.log.gz` (and `latest.log`,
dated by its modification time) and prints, per address, the joins, the different players, and the new
players: those whose first logged join came through that address. With --since, joins and players count from
that day on, and a player is new if their first logged join was on or after it. Players who joined before
the mod was installed count as new on their first logged join. Stdlib only; nothing leaves the machine.
"""
import argparse
import datetime as dt
import gzip
import re
import sys
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

# The mod prints with System.out, which Minecraft logs as "[STDOUT]: ...". Anchored to the start of the line,
# so chat or /say text that quotes the message doesn't count.
JOIN = re.compile(r"^\[[^\]]*\] \[[^\]]*\]: \[STDOUT\]: Player ([A-Za-z0-9_]{1,16}) connected via: (\S+)\s*$")
DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d+)\.log\.gz$")


def logs_by_day(logs: Path) -> Iterator[tuple[dt.date, str]]:
    """Each log's day and text, oldest first; latest.log, dated by its modification time, comes last."""
    dated = sorted(((dt.date.fromisoformat(m.group(1)), int(m.group(2))), path)
                   for path in logs.iterdir() if (m := DATED.match(path.name)))
    for (day, _), path in dated:
        yield day, gzip.open(path, "rt", encoding="utf-8", errors="replace").read()
    latest = logs / "latest.log"
    if latest.is_file():
        yield dt.date.fromtimestamp(latest.stat().st_mtime), latest.read_text(encoding="utf-8", errors="replace")


def joins(logs: Path) -> list[tuple[dt.date, str, str]]:
    """Every logged join as (day, player, address), oldest first. Addresses are lowercased, without a final dot."""
    found = []
    for day, text in logs_by_day(logs):
        for line in text.splitlines():
            if m := JOIN.match(line):
                found.append((day, m.group(1), m.group(2).lower().rstrip(".")))
    return found


def report(found: list[tuple[dt.date, str, str]], since: dt.date | None = None) -> list[str]:
    first: dict[str, tuple[dt.date, str]] = {}
    for day, name, address in found:
        first.setdefault(name, (day, address))
    count: dict[str, int] = defaultdict(int)
    players: dict[str, set[str]] = defaultdict(set)
    new: dict[str, int] = defaultdict(int)
    for day, name, address in found:
        if since is None or day >= since:
            count[address] += 1
            players[address].add(name)
    for day, address in first.values():
        if since is None or day >= since:
            new[address] += 1
    width = max([len("address"), *map(len, count)])
    lines = [f"joins per join address, {found[0][0]} to {found[-1][0]}"
             + (f" (counting from {since})" if since else ""),
             f"{'address':<{width}}{'joins':>7}{'players':>9}{'new':>5}"]
    for address in sorted(count, key=lambda a: (-new[a], -count[a], a)):
        lines.append(f"{address:<{width}}{count[address]:>7}{len(players[address]):>9}{new[address]:>5}")
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Joins per join address, from the server logs.")
    ap.add_argument("logs", type=Path, help="the server's logs/ folder")
    ap.add_argument("--since", type=dt.date.fromisoformat, help="count from this day on (YYYY-MM-DD)")
    args = ap.parse_args(argv)
    found = joins(args.logs)
    if not any(args.since is None or day >= args.since for day, _, _ in found):
        print(f"no Hostname Catcher joins found in {args.logs}" + (f" since {args.since}" if args.since else ""))
        return 1
    print("\n".join(report(found, args.since)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
