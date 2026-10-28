import datetime as dt
import re
import subprocess
import sys
import textwrap

import pytest

import drops
import npcs
import season_calendar
import site_links
from repo import REPO

UTC = dt.timezone.utc  # noqa: UP017 (the module under test keeps to 3.10)
PACIFIC = season_calendar.PACIFIC
SEASONS = (REPO.root / "docs" / "SEASONS.md").read_text(encoding="utf-8")


def at(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def pacific(*args) -> dt.datetime:
    return dt.datetime(*args, tzinfo=PACIFIC)


# ---------------------------------------------------------------- the zone


def test_the_zone_is_pacific():
    assert str(PACIFIC) == "America/Los_Angeles"
    assert season_calendar.now().tzinfo is PACIFIC


def test_without_tzdata_every_tool_stops_and_says_so(tmp_path):
    # A Python with no time zone database (Windows without the tzdata package): importing the calendar, and so
    # any tool that keeps time, stops with a message naming tzdata instead of using the machine's own time.
    script = textwrap.dedent(f"""
        import sys, zoneinfo
        sys.path.insert(0, {str(REPO.root / "tools")!r})
        zoneinfo.reset_tzpath([])
        sys.modules["tzdata"] = None
        import {{tool}}
    """)
    for tool in ("season_calendar", "challenges", "drops", "standings", "site_links", "npcs"):
        run = subprocess.run([sys.executable, "-I", "-c", script.format(tool=tool)], capture_output=True, text=True)
        assert run.returncode == 1, (tool, run.stderr)
        assert "install tzdata" in run.stderr and "America/Los_Angeles" in run.stderr, (tool, run.stderr)
        assert "Traceback" not in run.stderr, tool


def test_another_zone_without_tzdata_says_so_too():
    with pytest.raises(SystemExit, match="no time zone data for Nowhere/Atlantis.*install tzdata"):
        season_calendar.zone("Nowhere/Atlantis")


# ---------------------------------------------------------------- weeks


@pytest.mark.parametrize(("when", "week"), [
    (pacific(2026, 10, 26, 12, 0), 0),            # before the launch
    (pacific(2026, 11, 21, 17, 0), 0),            # the launch
    (pacific(2026, 11, 22, 23, 59, 59), 0),       # the end of the launch weekend, Sunday night
    (pacific(2026, 11, 23, 0, 0), 1),             # Monday, 12 AM Pacific
    (pacific(2026, 11, 29, 23, 59, 59), 1),
    (pacific(2026, 11, 30, 0, 0), 2),
    (pacific(2027, 2, 14, 23, 59, 59), 12),
    (pacific(2027, 2, 15, 0, 0), 13),
])
def test_weeks_turn_on_monday_at_midnight_pacific(when, week):
    assert season_calendar.week_at(when) == week
    assert season_calendar.week_at(when.astimezone(UTC)) == week


def test_the_week_turns_on_pacific_time_through_daylight_saving():
    # Standard time: Sunday 23:59:59 PST is 07:59:59 UTC on Monday.
    assert season_calendar.week_at(at("2026-11-23T07:59:59Z")) == 0
    assert season_calendar.week_at(at("2026-11-23T08:00:00Z")) == 1
    # Daylight time from 14 March 2027: Monday 15 March starts at 07:00 UTC, not 08:00.
    assert season_calendar.week_at(at("2027-03-15T06:59:59Z")) == 16
    assert season_calendar.week_at(at("2027-03-15T07:00:00Z")) == 17
    assert season_calendar.week_at(at("2027-03-15T07:30:00Z")) == 17
    assert season_calendar.week_begins(17) == at("2027-03-15T07:00:00Z")


def test_week_starts_are_mondays():
    assert season_calendar.WEEK_ONE.weekday() == 0
    for week in range(1, 30):
        assert season_calendar.week_start(week).weekday() == 0
        assert season_calendar.week_at(pacific(*season_calendar.week_start(week).timetuple()[:3])) == week
    assert season_calendar.week_start(0) == dt.date(2026, 11, 21)


def test_saturdays_are_event_nights_and_week_0s_is_the_launch():
    for week in range(0, 30):
        saturday = season_calendar.saturday(week)
        assert saturday.weekday() == 5
        assert season_calendar.week_at(pacific(*saturday.timetuple()[:3], 18)) == max(week, 0)
    assert season_calendar.saturday(0) == season_calendar.LAUNCH.astimezone(PACIFIC).date()
    assert season_calendar.saturday(1) == season_calendar.WEEK_ONE + dt.timedelta(days=5)


def test_saturdays_match_the_season_calendar_in_seasons_md():
    rows = re.findall(r"^\| (\d+) \| (\d{1,2} \w{3})\w* (\d{4})?", SEASONS, re.M)
    assert len(rows) >= npcs.LAST_WEEK + 1   # every week the Crier talks about
    year = None
    for week, day_month, y in rows:
        year = y or year
        date = dt.datetime.strptime(f"{day_month} {year}", "%d %b %Y").date()
        assert season_calendar.saturday(int(week)) == date, week
    two = season_calendar.SEASON_TWO
    assert f"| | {two.day} {two:%b} |" in SEASONS and two.weekday() == 5


# ---------------------------------------------------------------- the launch weekend


def test_the_launch_weekend_is_saturday_5_pm_to_the_end_of_sunday_pacific():
    assert season_calendar.LAUNCH.astimezone(PACIFIC) == pacific(2026, 11, 21, 17, 0)
    assert season_calendar.LAUNCH_END.astimezone(PACIFIC) == pacific(2026, 11, 23, 0, 0)
    assert at("2026-11-22T01:00:00Z") == season_calendar.LAUNCH
    assert season_calendar.LAUNCH.tzinfo is UTC and season_calendar.LAUNCH_END.tzinfo is UTC
    assert season_calendar.LAUNCH_SECONDS == 31 * 3600 == 111600
    assert season_calendar.week_at(season_calendar.LAUNCH_END) == 1   # the window ends as week 1 starts
    assert season_calendar.week_begins(1) == season_calendar.LAUNCH_END


def test_the_launch_is_the_sites_launch_time():
    # site/config.js's LAUNCH_AT (the countdown) is the website's copy of the launch: moving the calendar
    # without it would open the Founder's Circlet window at another time than the site says.
    config = (site_links.site() / "config.js").read_text(encoding="utf-8")
    assert site_links.launch_time(site_links.load_links(config)["LAUNCH_AT"]) == season_calendar.LAUNCH


# ---------------------------------------------------------------- drop nights


def test_drops_first_night_is_the_start_of_week_one():
    first = season_calendar.week_start(1)
    assert season_calendar.FIRST_DROP_NIGHT == first == season_calendar.WEEK_ONE
    evening = pacific(*first.timetuple()[:3], 18)
    assert drops.night_of(evening) == int(f"{first:%Y%m%d}")
    # Week 0, the launch weekend and the week before it: no drops.
    for days in range(1, 10):
        assert drops.night_of(evening - dt.timedelta(days=days)) is None


def test_drop_nights_are_monday_to_thursday_from_week_one():
    start = season_calendar.week_start(1)
    for week in range(0, 14):
        for offset in range(7):
            day = start + dt.timedelta(weeks=week, days=offset)
            assert season_calendar.drop_night(day) == (offset <= 3), day
    assert not season_calendar.drop_night(start - dt.timedelta(days=4))   # the Thursday before week 1
