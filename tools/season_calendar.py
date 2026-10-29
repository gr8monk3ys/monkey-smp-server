"""The season calendar: when the season's weeks, Saturdays and drop nights fall, in Pacific time.

    import season_calendar
    season_calendar.PACIFIC           # the server's time zone (America/Los_Angeles); now() is the time there
    season_calendar.LAUNCH            # Season I opens: Saturday 7 November 2026, 5 PM Pacific
    season_calendar.WEEK_ONE          # the Monday after the launch: week 1 starts there at 12 AM Pacific
    season_calendar.LAUNCH_END        # the launch weekend ends as week 1 starts
    season_calendar.week_at(when)     # the week a moment falls in: 0 (the launch weekend), then 1, 2, ...
    season_calendar.week_start(n)     # the Monday week n starts (week 0: the launch day)
    season_calendar.saturday(n)       # week n's Saturday, event night (week 0: the launch day)
    season_calendar.drop_night(day)   # whether supply drops run that evening: Monday to Thursday from week 1
    season_calendar.words(when)       # "Saturday 7 November 2026", "5 PM Pacific", "8 PM Eastern"

The one place the tools keep Season I's dates: challenges, drops, npcs, wardrobe, standings and site_links
all ask it. Every date follows from LAUNCH (Season(launch) works the rest out), so moving the season is one
edit here, then `python tools/datapacks.py`. site/config.js's LAUNCH_AT is the website's copy; a test checks
they agree. Week 1 starts on the Monday after the launch at 12 AM Pacific, and a new week every Monday at
12 AM Pacific (Sunday night, after the Saturday event); everything before week 1 is week 0.

Every time is Pacific, so the time zone database is needed: without it (no `tzdata` on Windows or a bare
Python), importing this module stops with a message saying to install tzdata, rather than any tool
quietly using the machine's own time.
Stdlib only, no imports from the other tools, and Python 3.10 or newer: challenges.py and drops.py run on the
VPS straight from the checkout.
"""
import datetime as dt
import zoneinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = dt.timezone.utc   # noqa: UP017 (datetime.UTC is 3.11+, and the VPS may have 3.10)


def zone(name: str) -> ZoneInfo:
    """A time zone from the time zone database. No database at all is a SystemExit saying to install tzdata; a
    name the database doesn't have is a ValueError (a typo, not a missing package)."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, OSError, ValueError) as e:
        if not zoneinfo.available_timezones():
            raise SystemExit(
                f"no time zone data for {name} ({type(e).__name__}): install tzdata "
                "(`python -m pip install tzdata`, or the system's tzdata package) and run it again") from None
        raise ValueError(f"no time zone called {name!r} in the time zone database") from None


PACIFIC = zone("America/Los_Angeles")
EASTERN = zone("America/New_York")   # shown next to Pacific, for the East Coast

DROP_NIGHTS = (0, 1, 2, 3)   # Monday to Thursday: Saturday is event night, so none Friday to Sunday


class Season:
    """Every date of a season, worked out from its launch (an aware time; kept in UTC)."""

    def __init__(self, launch: dt.datetime):
        self.launch = launch.astimezone(UTC)
        self.launch_day = launch.astimezone(PACIFIC).date()
        self.week_one = self.launch_day + dt.timedelta(days=7 - self.launch_day.weekday())   # the Monday after
        self.launch_end = self.week_begins(1)   # the launch weekend runs until week 1 starts
        self.launch_seconds = int((self.launch_end - self.launch).total_seconds())

    def week_at(self, when: dt.datetime) -> int:
        """The week a moment falls in: 0 until week 1 starts (Monday week_one, 12 AM Pacific), then 1, 2, ..."""
        day = when.astimezone(PACIFIC).date()
        return max(0, (day - self.week_one).days // 7 + 1)

    def week_start(self, week: int) -> dt.date:
        """The Monday a week starts (week 0, the launch weekend, starts on the launch day)."""
        return self.launch_day if week <= 0 else self.week_one + dt.timedelta(weeks=week - 1)

    def week_begins(self, week: int) -> dt.datetime:
        """The moment a week starts, in UTC: its Monday at 12 AM Pacific, and week 0's the launch itself."""
        if week <= 0:
            return self.launch
        return dt.datetime.combine(self.week_start(week), dt.time(), PACIFIC).astimezone(UTC)

    def saturday(self, week: int) -> dt.date:
        """Week N's Saturday, event night. Week 0's is the launch day."""
        return self.launch_day if week <= 0 else self.week_start(week) + dt.timedelta(days=5)

    def drop_night(self, day: dt.date) -> bool:
        """Whether supply drops run on the evening of `day` (a Pacific date): Monday to Thursday from week 1."""
        return day >= self.week_one and day.weekday() in DROP_NIGHTS


SEASON = Season(dt.datetime(2026, 11, 7, 17, 0, tzinfo=PACIFIC))   # Season I: Saturday 7 November, 5 PM
SEASON_TWO = dt.date(2027, 2, 6)   # proposed (docs/SEASONS.md); the owners confirm it by 9 January

LAUNCH = SEASON.launch
WEEK_ONE = SEASON.week_one
LAUNCH_END = SEASON.launch_end
LAUNCH_SECONDS = SEASON.launch_seconds   # 31 hours: Saturday 5 PM to Monday 12 AM Pacific
week_at = SEASON.week_at
week_start = SEASON.week_start
week_begins = SEASON.week_begins
saturday = SEASON.saturday
drop_night = SEASON.drop_night


def now() -> dt.datetime:
    return dt.datetime.now(PACIFIC)


# ---------------------------------------------------------------- in words

# Written out here rather than with strftime, which follows the machine's locale.
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def day_words(day: dt.date) -> str:
    """'Saturday 7 November'."""
    return f"{DAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}"


def short_day(when: dt.datetime) -> str:
    """'Sun 29 Nov', the Pacific day of a moment."""
    local = when.astimezone(PACIFIC)
    return f"{DAYS[local.weekday()][:3]} {local.day} {MONTHS[local.month - 1][:3]}"


def clock(local: dt.datetime) -> str:
    """A time of day as players read it: '5 PM', '8:30 PM', '12 AM'."""
    hour = local.hour % 12 or 12
    minutes = f":{local.minute:02}" if local.minute else ""
    return f"{hour}{minutes} {'AM' if local.hour < 12 else 'PM'}"


def words(when: dt.datetime) -> dict[str, str]:
    """A moment in words: {date} the Pacific day with its year, {pacific} '5 PM Pacific' and {eastern}
    '8 PM Eastern' (with the day in front when the East Coast is already on the next one)."""
    west, east = when.astimezone(PACIFIC), when.astimezone(EASTERN)
    eastern = f"{clock(east)} Eastern"
    if east.date() != west.date():
        eastern = f"{DAYS[east.weekday()]} {eastern}"
    return {"date": f"{day_words(west.date())} {west.year}", "pacific": f"{clock(west)} Pacific", "eastern": eastern}
