"""The pass funnel: Tebex payments matched to the server's join logs.

    python tools/funnel.py PAYMENTS.csv PATH/TO/server/logs [--as-of YYYY-MM-DD]

Follows everyone who bought an access pass through five steps: the purchase, their first join after it,
30 minutes played, coming back 7 or more days after that first join (D7), and the pass renewed. Prints
the month-2 renewal rate (the headline: it is what pays for the server), a table by month of first
purchase, and the buyers who never joined, who need install help more than anything.

PAYMENTS.csv is Tebex's payments export (Payments, Export). It holds buyers' names and emails: keep it on
the server or your own machine and never commit it (.gitignore skips *.csv outside tests/fixtures).
Tebex doesn't publish the export's columns, so this finds them by name and says which it used; if it
guesses wrong, name the column with --col, e.g. --col username="Minecraft Username". Tebex dates are UTC;
log times are the server's clock, UTC unless TZ is set in package/docker/.env (then pass --log-tz).

Stdlib only; nothing leaves the machine.
"""
import argparse
import csv
import datetime as dt
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo

from retention import logs_by_day

UTC = dt.UTC
LINE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\] \[[^\]]*\]: (.*)$")
JOINED = re.compile(r"^(?:System chat: )?([A-Za-z0-9_]{1,16})(?: \(formerly known as [A-Za-z0-9_]+\))? "
                    r"(joined|left) the game$")
UUID_LINE = re.compile(r"^UUID of player ([A-Za-z0-9_]{1,16}) is ([0-9a-fA-F-]{32,36})$")

# Column names to look for, per field, compared without case, spaces or punctuation.
COLUMNS = {
    "username": ["username", "ign", "playername", "player", "minecraftusername", "minecraftname", "customerusername"],
    "uuid": ["uuid", "useruuid", "playeruuid", "minecraftuuid", "customeruuid"],
    "date": ["date", "datetime", "createdat", "created", "datecreated", "paymentdate", "purchasedate", "time",
             "timestamp"],
    "package": ["packages", "package", "packagename", "packagenames", "items", "item", "products", "product"],
    "status": ["status", "paymentstatus", "state"],
}
REQUIRED = ("username", "date", "package")
PAID = {"complete", "completed", "paid", "success", "succeeded"}
DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
                "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%d/%m/%Y", "%m/%d/%Y", "%b %d, %Y %H:%M", "%d %b %Y %H:%M"]
MONTH = dt.timedelta(days=30)
GRACE = dt.timedelta(days=3)    # a renewal a few days late (a failed card retried) still counts
EARLY = dt.timedelta(days=7)    # a second pass within a week of the first is a top-up, not a renewal
ENOUGH_PLAY = dt.timedelta(minutes=30)


class Payment(NamedTuple):
    name: str
    uuid: str
    time: dt.datetime
    package: str
    months: int


class Buyer(NamedTuple):
    name: str
    first: dt.datetime
    months: int
    joined: dt.datetime | None
    played: dt.timedelta
    d7: bool | None         # None: not due yet (or never joined)
    renewed: bool | None    # None: not due yet
    came_back_later: bool   # bought another pass after the renewal window had passed


def key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def find_columns(header: list[str], overrides: dict[str, str]) -> dict[str, str]:
    """field -> the header cell that holds it."""
    found = {}
    by_key = {key(h): h for h in header}
    for field, names in COLUMNS.items():
        if field in overrides:
            if overrides[field] not in header:
                raise SystemExit(f"--col {field}={overrides[field]!r}: no such column (columns: {', '.join(header)})")
            found[field] = overrides[field]
            continue
        hit = next((by_key[n] for n in names if n in by_key), None)
        if hit:
            found[field] = hit
    missing = [f for f in REQUIRED if f not in found]
    if missing:
        raise SystemExit(f"can't find the {', '.join(missing)} column in the export (columns: {', '.join(header)}); "
                         f"name it with --col {missing[0]}=COLUMN")
    return found


def date_format(cells: list[str]) -> str | None:
    """The first format that reads every date: None for ISO 8601. Trying them in order settles day/month
    order as soon as one date has a day above 12."""
    try:
        for c in cells:
            dt.datetime.fromisoformat(c.strip())
        return None
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            for c in cells:
                dt.datetime.strptime(c.strip(), fmt)
            return fmt
        except ValueError:
            continue
    raise SystemExit(f"can't read the dates (e.g. {cells[0]!r}); give the format with --date-format, "
                     "e.g. --date-format '%d/%m/%Y %H:%M'")


def parse_date(cell: str, fmt: str | None) -> dt.datetime:
    when = dt.datetime.fromisoformat(cell.strip()) if fmt is None else dt.datetime.strptime(cell.strip(), fmt)
    return when.replace(tzinfo=UTC) if when.tzinfo is None else when.astimezone(UTC)


def read_payments(path: Path, overrides: dict[str, str], pass_re: re.Pattern,
                  fmt: str | None = None) -> tuple[list[Payment], list[str]]:
    """The paid pass payments, oldest first, and notes on how the export was read."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"{path} has no rows")
    cols = find_columns(list(rows[0]), overrides)
    fmt = fmt or date_format([r[cols["date"]] for r in rows])
    statuses = Counter(r[cols["status"]].strip() for r in rows) if "status" in cols else Counter()
    notes = ["columns: " + ", ".join(f"{field} = {col!r}" for field, col in cols.items()),
             f"dates read as {fmt or 'ISO 8601'}, UTC"]
    if statuses:
        counted = sorted(s for s in statuses if s.lower() in PAID)
        notes.append("statuses: " + ", ".join(f"{s} {n}" for s, n in statuses.most_common())
                     + f" (counted: {', '.join(counted) or 'none'})")
    else:
        notes.append("no status column: every row counts as paid")
    out = []
    for r in rows:
        if statuses and r[cols["status"]].strip().lower() not in PAID:
            continue
        package = r[cols["package"]]
        if not pass_re.search(package):
            continue
        months = re.search(r"(\d+)[- ]?months?", package, re.IGNORECASE)
        out.append(Payment(r[cols["username"]].strip(), norm_uuid(r.get(cols.get("uuid", ""), "")),
                           parse_date(r[cols["date"]], fmt), package, int(months.group(1)) if months else 1))
    return sorted(out, key=lambda p: p.time), notes


def norm_uuid(text: str) -> str:
    return text.strip().replace("-", "").lower()


def sessions(logs: Path, tz: dt.tzinfo) -> tuple[dict[str, list[tuple[dt.datetime, dt.datetime]]],
                                                 dict[str, set[str]], dt.date | None, dt.date | None]:
    """{lowercase name: [(start, end) in UTC]}, {uuid: names}, and the first and last day the logs cover.

    A session ends when the player leaves, the server stops or the log ends. Someone still online when the
    log rolls over at midnight shows up in the next log as leaving, and counts from that log's start."""
    out: dict[str, list[tuple[dt.datetime, dt.datetime]]] = defaultdict(list)
    names: dict[str, set[str]] = defaultdict(set)
    first_day = last_day = None
    for day, text in logs_by_day(logs):
        first_day, last_day = min(first_day or day, day), max(last_day or day, day)
        online: dict[str, dt.datetime] = {}
        start = now = None
        prev = None
        for line in text.splitlines():
            m = LINE.match(line)
            if not m:
                continue
            secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            if prev is not None and secs + 43200 < prev:   # the clock went past midnight
                day += dt.timedelta(days=1)
                last_day = max(last_day, day)
            prev = secs
            now = dt.datetime.combine(day, dt.time(secs // 3600, secs // 60 % 60, secs % 60), tz).astimezone(UTC)
            start = start or now
            msg = m.group(4)
            if j := JOINED.match(msg):
                who = j.group(1).lower()
                if j.group(2) == "joined":
                    online.setdefault(who, now)
                else:
                    out[who].append((online.pop(who, start), now))
            elif u := UUID_LINE.match(msg):
                names[norm_uuid(u.group(2))].add(u.group(1).lower())
            elif msg.startswith("Stopping server"):
                for who, since in online.items():
                    out[who].append((since, now))
                online.clear()
        if now:
            for who, since in online.items():
                out[who].append((since, now))
    return dict(out), dict(names), first_day, last_day


def follow(payments: list[Payment], played: dict[str, list[tuple[dt.datetime, dt.datetime]]],
           uuid_names: dict[str, set[str]], as_of: dt.date) -> list[Buyer]:
    by_buyer: dict[str, list[Payment]] = defaultdict(list)
    for p in payments:
        by_buyer[p.uuid or p.name.lower()].append(p)
    buyers = []
    for pays in by_buyer.values():
        first = pays[0]
        names = {p.name.lower() for p in pays} | uuid_names.get(first.uuid, set())
        after = sorted(s for n in names for s in played.get(n, []) if s[1] >= first.time - dt.timedelta(minutes=10))
        joined = after[0][0] if after else None
        total = sum((end - begin for begin, end in after), dt.timedelta())
        d7 = None
        if joined and (joined + dt.timedelta(days=7)).date() <= as_of:
            d7 = any(begin.date() >= (joined + dt.timedelta(days=7)).date() for begin, _ in after)
        window = first.time + first.months * MONTH + GRACE
        later = [p for p in pays[1:] if p.time > first.time + EARLY]
        # Judged only once the window has passed: counting early renewers sooner would flatter the rate.
        renewed = any(p.time <= window for p in later) if window.date() <= as_of else None
        buyers.append(Buyer(pays[-1].name, first.time, first.months, joined, total, d7, renewed,
                            any(p.time > window for p in later)))
    return sorted(buyers, key=lambda b: b.first)


def report(buyers: list[Buyer], as_of: dt.date, logs_from: dt.date | None) -> list[str]:
    lines = []
    for months, label in ((1, "Month-2 renewal, monthly passes"), (3, "Renewal, 3-month passes")):
        group = [b for b in buyers if b.months == months]
        if not group and months != 1:
            continue
        due = [b for b in group if b.renewed is not None]
        renewed = sum(1 for b in due if b.renewed)
        result = f"{renewed} of {len(due)} renewed ({100 * renewed // len(due)}%)" if due else "none due yet"
        lines.append(f"{label}: {result}; {len(group) - len(due)} not due yet")
    back = sum(1 for b in buyers if b.came_back_later)
    if back:
        lines.append(f"Came back later: {back} bought again after their pass had lapsed")
    lines += ["", "by month of first purchase (D7 and renewed: of those due)",
              f"{'first bought':<14}{'buyers':>7}{'joined':>8}{'30 min':>8}{'D7':>8}{'renewed':>9}"]
    cohorts: dict[str, list[Buyer]] = defaultdict(list)
    for b in buyers:
        cohorts[b.first.strftime("%Y-%m")].append(b)

    def ratio(hits: list[bool | None]) -> str:
        due = [h for h in hits if h is not None]
        return f"{sum(due)}/{len(due)}" if due else "-"
    for month, group in sorted(cohorts.items()):
        lines.append(f"{month:<14}{len(group):>7}{sum(1 for b in group if b.joined):>8}"
                     f"{sum(1 for b in group if b.played >= ENOUGH_PLAY):>8}"
                     f"{ratio([b.d7 for b in group]):>8}{ratio([b.renewed for b in group]):>9}")
    never = [b for b in buyers if not b.joined and (logs_from is None or b.first.date() >= logs_from)]
    if never:
        lines += ["", "bought a pass but never joined (send install help):"]
        lines += [f"  {b.name:<17}bought {b.first.date().isoformat()} ({(as_of - b.first.date()).days} days ago)"
                  for b in never]
    early = sum(1 for b in buyers if logs_from and b.first.date() < logs_from)
    if early:
        lines += ["", f"{early} buyers bought before the logs start ({logs_from}): their joins may be missing"]
    return lines


def log_zone(text: str) -> dt.tzinfo:
    if m := re.fullmatch(r"([+-])(\d{2}):?(\d{2})", text):
        offset = dt.timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
        return dt.timezone(-offset if m.group(1) == "-" else offset)
    return UTC if text.upper() == "UTC" else ZoneInfo(text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The pass funnel: Tebex payments matched to the join logs.")
    ap.add_argument("payments", type=Path, help="Tebex's payments export (CSV)")
    ap.add_argument("logs", type=Path, help="the server's logs/ folder")
    ap.add_argument("--as-of", type=dt.date.fromisoformat, help="judge as of this day (default: newest data)")
    ap.add_argument("--log-tz", default="UTC", help="the server clock's zone, e.g. America/Los_Angeles (default UTC)")
    ap.add_argument("--pass", dest="pass_re", default=r"\bpass\b",
                    help=r"regex that picks access-pass packages by name (default: \bpass\b)")
    ap.add_argument("--col", action="append", default=[], metavar="FIELD=COLUMN",
                    help=f"name the column for a field ({', '.join(COLUMNS)})")
    ap.add_argument("--date-format", help="strptime format for the date column, if it isn't read right")
    args = ap.parse_args(argv)
    overrides = dict(c.split("=", 1) for c in args.col)
    payments, notes = read_payments(args.payments, overrides, re.compile(args.pass_re, re.IGNORECASE),
                                    args.date_format)
    if not payments:
        print("\n".join(notes + ["no paid pass payments in the export (check --pass and the status column)"]))
        return 1
    played, uuid_names, logs_from, logs_to = sessions(args.logs, log_zone(args.log_tz))
    as_of = args.as_of or max(filter(None, [logs_to, payments[-1].time.date()]))
    payments = [p for p in payments if p.time.date() <= as_of]
    played = {n: [s for s in spans if s[0].date() <= as_of] for n, spans in played.items()}
    buyers = follow(payments, played, uuid_names, as_of)
    print("\n".join([f"pass funnel as of {as_of}: {len(buyers)} buyers, {len(payments)} paid pass payments",
                     *notes, f"logs: {logs_from} to {logs_to}" if logs_from else f"logs: none in {args.logs}",
                     "", *report(buyers, as_of, logs_from)]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
