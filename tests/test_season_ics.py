import datetime as dt
import hashlib
import re
import subprocess
import sys

import pytest
import status

import season_calendar
import season_ics
from repo import REPO

UTC = dt.timezone.utc  # noqa: UP017 (the tools keep to 3.10)
SITE = REPO.root / "site"
COMMITTED = (SITE / "public" / season_ics.NAME).read_bytes()


# ---------------------------------------------------------------- a small RFC 5545 reader, to read the file back


def unfold(raw: bytes) -> list[str]:
    """The content lines of a calendar, after checking what RFC 5545 asks of the bytes: CRLF ends every physical
    line (and nothing else does), none is over 75 octets, and a fold is a CRLF and one space."""
    assert raw.endswith(b"\r\n")
    assert b"\n" not in raw.replace(b"\r\n", b"") and b"\r" not in raw.replace(b"\r\n", b"")
    physical = raw.decode("utf-8").split("\r\n")[:-1]
    assert all(len(p.encode("utf-8")) <= 75 for p in physical), [p for p in physical if len(p.encode()) > 75]
    out: list[str] = []
    for p in physical:
        if p.startswith(" "):
            out[-1] += p[1:]
        else:
            out.append(p)
    return out


def unescape(value: str) -> str:
    return re.sub(r"\\(.)", lambda m: "\n" if m[1] in "nN" else m[1], value)


def parse(raw: bytes) -> tuple[dict[str, str], list[dict[str, str]]]:
    """(the calendar's own properties, each VEVENT's properties): a property's name without parameters."""
    lines = unfold(raw)
    assert lines[0] == "BEGIN:VCALENDAR" and lines[-1] == "END:VCALENDAR"
    calendar_props: dict[str, str] = {}
    events: list[dict[str, str]] = []
    current = None
    for line in lines[1:-1]:
        name, _, value = line.partition(":")
        name = name.split(";")[0]
        if line == "BEGIN:VEVENT":
            assert current is None
            current = {}
        elif line == "END:VEVENT":
            assert current is not None
            events.append(current)
            current = None
        else:
            assert name not in (current if current is not None else calendar_props), f"{name} twice"
            (current if current is not None else calendar_props)[name] = value
    assert current is None
    return calendar_props, events


def instant(value: str) -> dt.datetime:
    assert re.fullmatch(r"\d{8}T\d{6}Z", value), value
    return dt.datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def pacific(when: dt.datetime) -> dt.datetime:
    return when.astimezone(season_calendar.PACIFIC)


# ---------------------------------------------------------------- the committed file


def test_the_committed_file_is_what_the_tool_makes():
    assert season_ics.render() == COMMITTED, "run python tools/season_ics.py"
    assert season_ics.problems(REPO) == []


def test_a_missing_or_stale_file_is_reported(tmp_path):
    class Fake:
        root = tmp_path
    assert "is missing" in season_ics.problems(Fake())[0]
    (tmp_path / "site" / "public").mkdir(parents=True)
    (tmp_path / "site" / "public" / season_ics.NAME).write_bytes(COMMITTED.replace(b"Saturday", b"Sunday"))
    assert "is out of date" in season_ics.problems(Fake())[0]


def test_the_check_flag_changes_nothing_and_fails_on_a_stale_file(tmp_path, capsys):
    class Fake:
        root = tmp_path
    assert season_ics.main(["--check"], Fake()) == 1
    assert not (tmp_path / "site").exists()
    assert season_ics.main([], Fake()) == 0
    assert (tmp_path / "site" / "public" / season_ics.NAME).read_bytes() == COMMITTED
    assert season_ics.main(["--check"], Fake()) == 0


def test_the_script_runs_from_the_command_line():
    run = subprocess.run([sys.executable, str(REPO.root / "tools" / "season_ics.py"), "--check"],
                         capture_output=True, text=True, cwd=REPO.root / "tools")
    assert run.returncode == 0, run.stdout + run.stderr


def test_git_keeps_the_crlf_line_endings():
    # `* text=auto eol=lf` would turn every CRLF into LF on commit: .ics files are left alone.
    assert "*.ics -text" in (REPO.root / ".gitattributes").read_text(encoding="utf-8").splitlines()


# ---------------------------------------------------------------- RFC 5545


def test_the_file_parses_and_has_the_required_properties():
    props, events = parse(COMMITTED)
    assert props["VERSION"] == "2.0" and props["PRODID"] and props["CALSCALE"] == "GREGORIAN"
    assert props["METHOD"] == "PUBLISH"
    assert events
    for e in events:
        for name in ("UID", "DTSTAMP", "DTSTART", "SUMMARY"):
            assert e[name], name
        assert e["DURATION"] == season_ics.LENGTH and "DTEND" not in e   # the site gives no length: one for all
        assert e["SEQUENCE"] == str(season_ics.SEQUENCE)
        instant(e["DTSTART"])


def test_uids_are_unique_stable_and_do_not_depend_on_the_time():
    uids = [e["UID"] for e in parse(COMMITTED)[1]]
    assert len(uids) == len(set(uids)) == 23
    assert all(re.fullmatch(r"season-1-week-\d\d-(launch|event|finale|close)@monkeysmp\.lscaturchio\.xyz", u)
               for u in uids)
    # A season a week later (every moment moves) keeps every UID, so a phone updates its events, not adds copies.
    later = season_calendar.Season(season_calendar.SEASON.launch + dt.timedelta(weeks=1))
    assert [e.uid for e in season_ics.events(later)] == [e.uid for e in season_ics.events()]
    assert [e.start for e in season_ics.events(later)] != [e.start for e in season_ics.events()]


def test_dtstamp_comes_from_the_data_not_the_clock():
    _, events = parse(COMMITTED)
    assert {e["DTSTAMP"] for e in events} == {e["LAST-MODIFIED"] for e in events} == {"20261104T000000Z"}
    assert season_ics.PUBLISHED < season_calendar.LAUNCH
    assert "datetime.now" not in (REPO.root / "tools" / "season_ics.py").read_text(encoding="utf-8")
    assert season_ics.render() == season_ics.render()


# The events as of the last SEQUENCE bump. When this fails: bump SEQUENCE and PUBLISHED in tools/season_ics.py, rerun
# it, then copy the digest and the new values here.
EVENTS_AS_PUBLISHED = ("ffd9f8d0daa24804dba65cc0d6e0715f9b4f7bbea453cbece44ab8df2217d02d", 0, "20261104T000000Z")


def test_changed_events_come_with_a_new_sequence_so_phones_take_them():
    words = "\n".join(f"{e.uid}|{season_ics.utc(e.start)}|{e.summary}|{e.description}|{e.url}"
                      for e in season_ics.events())
    digest = hashlib.sha256(words.encode("utf-8")).hexdigest()
    assert (digest, season_ics.SEQUENCE, season_ics.utc(season_ics.PUBLISHED)) == EVENTS_AS_PUBLISHED


def test_events_are_in_time_order_and_nothing_is_before_the_launch():
    starts = [instant(e["DTSTART"]) for e in parse(COMMITTED)[1]]
    assert starts == sorted(starts)
    assert starts[0] == season_calendar.LAUNCH


def test_text_is_escaped():
    assert season_ics.escape("a, b; c\\d\ne") == "a\\, b\\; c\\\\d\\ne"
    assert unescape(season_ics.escape("a, b; c\\d\r\ne")) == "a, b; c\\d\ne"
    props, events = parse(COMMITTED)
    # Read back, the description is the sentence the tool wrote, commas and all.
    first = events[1]
    assert unescape(first["DESCRIPTION"]) == season_ics.events()[1].description
    assert "," in season_ics.events()[1].description and "\\," in first["DESCRIPTION"]


def test_lines_fold_at_75_octets_and_never_inside_a_character():
    line = "DESCRIPTION:" + "Monkey é中\U0001f412 " * 30
    parts = season_ics.fold(line)
    assert len(parts) > 3
    assert all(len(p.encode("utf-8")) <= 75 for p in parts)
    assert all(p.startswith(" ") for p in parts[1:])
    assert "".join([parts[0], *(p[1:] for p in parts[1:])]) == line
    parts[0].encode("utf-8").decode("utf-8")   # every piece is whole characters
    # A line that fits is left alone, and so is one exactly 75 octets long.
    assert season_ics.fold("A" * 75) == ["A" * 75]
    assert len(season_ics.fold("A" * 76)) == 2


def test_folded_lines_read_back_whole():
    raw = season_ics.render()
    assert any(len(line.encode()) > 75 for line in unfold(raw))   # unfolding joined something that was folded


# ---------------------------------------------------------------- what is in it


def test_it_matches_the_statuss_dates():
    # The same moments status.dates() gives for the season, in the same order: one for the launch, one a Saturday
    # (the finale included) and one a Sunday close for every week.
    expected = [when for when, _, _ in status.dates()]
    got = [instant(e["DTSTART"]) for e in parse(COMMITTED)[1]]
    assert got == sorted(expected)


def test_the_times_are_the_pacific_ones_the_site_gives():
    by_kind: dict[str, list[dt.datetime]] = {"launch": [], "event": [], "finale": [], "close": []}
    for e in parse(COMMITTED)[1]:
        by_kind[e["UID"].split("-")[4].split("@")[0]].append(pacific(instant(e["DTSTART"])))
    assert [(w.weekday(), w.hour, w.minute) for w in by_kind["launch"]] == [(5, 17, 0)]
    assert {(w.weekday(), w.hour, w.minute) for w in by_kind["event"] + by_kind["finale"]} == {(5, 18, 0)}
    assert {(w.weekday(), w.hour, w.minute) for w in by_kind["close"]} == {(6, 19, 0)}
    assert len(by_kind["event"]) == 10 and len(by_kind["finale"]) == 1 and len(by_kind["close"]) == 11
    assert by_kind["launch"][0].date() == dt.date(2026, 11, 7)
    assert by_kind["finale"][0].date() == dt.date(2027, 1, 23)


def test_the_site_says_every_time_and_date_the_file_gives():
    guide = (SITE / "src" / "content" / "guide" / "week.ts").read_text(encoding="utf-8")
    assert 'at: "6 PM", text: "The week\'s event:' in guide
    assert 'at: "7 PM", text: "The week\'s faction standings close' in guide
    changes = (SITE / "src" / "content" / "changes.mdx").read_text(encoding="utf-8")
    assert "the finale is on 23 January" in changes
    assert "Season I opens on Saturday 7 November at 5 PM Pacific" in changes


def test_only_what_the_site_names_is_named():
    props, events = parse(COMMITTED)
    text = " ".join(unescape(e["SUMMARY"] + " " + e["DESCRIPTION"]) for e in events)
    held_back = [what for _, what, _ in status.SCHEDULE if what not in season_ics.ANNOUNCED]
    assert held_back   # the schedule has names to hold back
    assert not [what for what in held_back if what.lower() in text.lower()], "a name the site doesn't give yet"
    assert "Dragon" not in text and "Netherite" not in text and "Midwinter" not in text
    summaries = [unescape(e["SUMMARY"]) for e in events]
    assert summaries.count("Monkey SMP: Season I opens") == 1
    assert summaries.count("Monkey SMP: Season I finale") == 1
    assert summaries.count("Monkey SMP: Saturday event") == 10
    assert summaries.count("Monkey SMP: weekly standings close") == 11


def test_the_announced_names_are_in_the_schedule():
    assert set(season_ics.ANNOUNCED) <= {what for _, what, _ in status.SCHEDULE}
    assert status.SCHEDULE[0][1] == "Season I opens" and status.SCHEDULE[-1][1] == "The finale"


def test_the_address_and_site_are_the_sites_own():
    config = (SITE / "config.json").read_text(encoding="utf-8")
    assert f'"ADDRESS": "{season_ics.ADDRESS}"' in config
    lib = (SITE / "src" / "lib" / "config.ts").read_text(encoding="utf-8")
    assert f'SITE_URL = "{season_ics.SITE}"' in lib
    assert season_ics.DOMAIN == season_ics.ADDRESS


# ---------------------------------------------------------------- daylight saving


def test_six_pm_pacific_stays_six_pm_across_a_daylight_saving_change():
    # Season II (proposed) runs over 14 March 2027, when the clocks go forward: the UTC instants move an hour, the
    # Pacific times don't. (Season I is all standard time.)
    season = season_calendar.SEASON_II
    mine = [e for e in season_ics.events(season, 2) if "-event@" in e.uid or "-finale@" in e.uid]
    assert len(mine) == 11
    offsets = {e.start.astimezone(season_calendar.PACIFIC).utcoffset() for e in mine}
    assert offsets == {dt.timedelta(hours=-8), dt.timedelta(hours=-7)}   # the change really falls inside
    for e in mine:
        local = pacific(e.start)
        assert (local.weekday(), local.hour, local.minute) == (5, 18, 0), e.uid
    utc_hours = {instant(season_ics.utc(e.start)).hour for e in mine}
    assert utc_hours == {1, 2}
    closes = [e for e in season_ics.events(season, 2) if e.uid.endswith("-close@monkeysmp.lscaturchio.xyz")]
    assert {(pacific(e.start).weekday(), pacific(e.start).hour) for e in closes} == {(6, 19)}
    # The UIDs say which season.
    assert all(e.uid.startswith("season-2-") for e in season_ics.events(season, 2))


def test_the_utc_text_of_an_instant():
    assert season_ics.utc(dt.datetime(2026, 11, 7, 17, tzinfo=season_calendar.PACIFIC)) == "20261108T010000Z"
    assert season_ics.utc(dt.datetime(2027, 3, 20, 18, tzinfo=season_calendar.PACIFIC)) == "20270321T010000Z"
    assert season_ics.utc(dt.datetime(2027, 3, 13, 18, tzinfo=season_calendar.PACIFIC)) == "20270314T020000Z"


def test_it_is_linked_from_the_site_config():
    # The week page is where players look for the schedule; the link is a plain anchor, so it works without JS.
    config = (SITE / "config.json").read_text(encoding="utf-8")
    assert f'"CALENDAR_URL": "/{season_ics.NAME}"' in config
    page = (SITE / "src" / "app" / "guide" / "week" / "page.tsx").read_text(encoding="utf-8")
    assert 'ConfigLink to="CALENDAR_URL"' in page


@pytest.mark.parametrize("value", ["a" * 74, "a" * 75, "a" * 76, "é" * 37, "é" * 38])
def test_fold_edges_stay_within_75_octets(value):
    parts = season_ics.fold(value)
    assert all(len(p.encode("utf-8")) <= 75 for p in parts)
    assert "".join([parts[0], *(p[1:] for p in parts[1:])]) == value
