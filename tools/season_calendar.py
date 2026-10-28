"""The season calendar: when the season's weeks, Saturdays and drop nights fall, in Pacific time.

    import season_calendar
    season_calendar.PACIFIC           # the server's time zone (America/Los_Angeles); now() is the time there
    season_calendar.LAUNCH            # Season I opens: Saturday 21 November 2026, 5 PM Pacific
    season_calendar.LAUNCH_END        # the launch weekend ends as week 1 starts: Monday 23 November, 12 AM
    season_calendar.week_at(when)     # the week a moment falls in: 0 (the launch weekend), then 1, 2, ...
    season_calendar.week_start(n)     # the Monday week n starts (week 0: the launch day)
    season_calendar.saturday(n)       # week n's Saturday, event night
    season_calendar.drop_night(day)   # whether supply drops run that evening: Monday to Thursday from week 1

The one place the tools keep Season I's dates: challenges, drops, npcs, wardrobe, standings and
site_links all ask it, so moving the season here moves every generated pack and VPS job with it (then run
`python tools/datapacks.py`). site/config.js's LAUNCH_AT is the website's copy; a test checks they agree.
Week 1 starts on Monday WEEK_ONE at 12 AM Pacific, and a new week every Monday at 12 AM Pacific (Sunday
night, after the Saturday event); everything before week 1 is week 0.

Every time is Pacific, so the time zone database is needed: without it (no `tzdata` on Windows or a bare
Python), importing this module stops with a message saying to install tzdata, rather than any tool
quietly using the machine's own time.
Stdlib only, no imports from the other tools, and Python 3.10 or newer: challenges.py and drops.py run on the
VPS straight from the checkout.
"""
import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = dt.timezone.utc   # noqa: UP017 (datetime.UTC is 3.11+, and the VPS may have 3.10)


def zone(name: str) -> ZoneInfo:
    """A time zone from the time zone database; without the database, a SystemExit saying to install tzdata."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, OSError, ValueError) as e:
        raise SystemExit(
            f"no time zone data for {name} ({type(e).__name__}): install tzdata "
            "(`python -m pip install tzdata`, or the system's tzdata package) and run it again") from None


PACIFIC = zone("America/Los_Angeles")

WEEK_ONE = dt.date(2026, 11, 23)   # a Monday: week 1 starts at 12 AM Pacific; everything before it is week 0
LAUNCH = dt.datetime(2026, 11, 21, 17, 0, tzinfo=PACIFIC).astimezone(UTC)   # Saturday 21 November, 5 PM
SEASON_TWO = dt.date(2027, 2, 20)  # proposed (docs/SEASONS.md); the owners confirm it by 23 January
DROP_NIGHTS = (0, 1, 2, 3)         # Monday to Thursday: Saturday is event night, so none Friday to Sunday


def now() -> dt.datetime:
    return dt.datetime.now(PACIFIC)


def week_at(when: dt.datetime) -> int:
    """The week a moment falls in: 0 until week 1 starts (Monday WEEK_ONE, 12 AM Pacific), then 1, 2, ..."""
    day = when.astimezone(PACIFIC).date()
    return max(0, (day - WEEK_ONE).days // 7 + 1)


def week_start(week: int) -> dt.date:
    """The Monday a week starts (week 0, the launch weekend, starts on the launch day)."""
    return LAUNCH.astimezone(PACIFIC).date() if week <= 0 else WEEK_ONE + dt.timedelta(weeks=week - 1)


def week_begins(week: int) -> dt.datetime:
    """The moment week `week` (1 or later) starts: its Monday at 12 AM Pacific, in UTC."""
    return dt.datetime.combine(week_start(week), dt.time(), PACIFIC).astimezone(UTC)


def saturday(week: int) -> dt.date:
    """Week N's Saturday, event night (week 0's is the launch day)."""
    return WEEK_ONE + dt.timedelta(weeks=week - 1, days=5)


LAUNCH_END = week_begins(1)   # the launch weekend runs to the end of Sunday: Monday 23 November, 12 AM
LAUNCH_SECONDS = int((LAUNCH_END - LAUNCH).total_seconds())   # 31 hours
FIRST_DROP_NIGHT = week_start(1)   # supply drops start with week 1


def drop_night(day: dt.date) -> bool:
    """Whether supply drops run on the evening of `day` (a Pacific date)."""
    return day >= FIRST_DROP_NIGHT and day.weekday() in DROP_NIGHTS
