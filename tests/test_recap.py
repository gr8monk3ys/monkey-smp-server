import datetime as dt
import io
import json
import urllib.error
import uuid

import pytest
from fake_world import OVERWORLD, FakeWorld, member

import rcon
import recap
import season_calendar
import standings

PACIFIC = season_calendar.PACIFIC
BEFORE = dt.datetime(2026, 11, 1, 19, 0, tzinfo=PACIFIC)     # the Sunday before the launch: test play
LAUNCH_SUNDAY = dt.datetime(2026, 11, 8, 19, 0, tzinfo=PACIFIC)   # the first close after it: week 0
WEEK_ONE = dt.datetime(2026, 11, 15, 19, 0, tzinfo=PACIFIC)
WEBHOOK = "https://discord.com/api/webhooks/1/made-up-secret-token"
LAUNCHED = ("rw.day", "#launched", 1)
SEASON_ONE = ("rw.day", "#season", 1)

PLAYERS = {name: str(uuid.uuid5(uuid.NAMESPACE_DNS, "recap-" + name)) for name in
           ("AlexFake", "SamFake", "RiaFake", "TomFake", "LoneFake")}
LAND = {"AlexFake": 4, "RiaFake": 1, "LoneFake": 2}


def make_world(root, *rows, land=None):
    """Red Monkeys (Alex, Sam), Blue Herons (Ria, Tom) and LoneFake's faction; Red holds 30 Cup points."""
    fake = FakeWorld(root / "server" / "world").scores(("ev.cup", "red", 30, {"display": "Red Monkeys"}), *rows)
    for pid, owner, members in (("p-red", "AlexFake", ["SamFake"]), ("p-blue", "RiaFake", ["TomFake"]),
                                ("p-lone", "LoneFake", [])):
        fake.party(pid, member(PLAYERS[owner], owner), [member(PLAYERS[m], m) for m in members])
    fake.party_name(PLAYERS["AlexFake"], "Red Monkeys").party_name(PLAYERS["RiaFake"], "Blue Herons")
    for name, chunks in (land or LAND).items():
        fake.claims(PLAYERS[name], {OVERWORLD: [(i, 0) for i in range(chunks)]})
    (fake.path.parent / "usercache.json").write_text(json.dumps([{"name": n, "uuid": u} for n, u in PLAYERS.items()]))
    return fake.path


class FakeDiscord:
    def __init__(self, fail=0):
        self.posts, self.fail = [], fail

    def __call__(self, request, timeout):
        if self.fail:
            self.fail -= 1
            raise urllib.error.HTTPError(request.full_url, 503, "Service Unavailable", {}, None)
        self.posts.append(json.loads(request.data)["content"])
        return io.BytesIO(b"")


def closed_week(state, when):
    return json.loads((state / "weeks" / f"{when:%Y-%m-%d}.json").read_text(encoding="utf-8"))


@pytest.fixture
def season(tmp_path):
    """A week started in test play, the launch (which clears test play's challenges), week 0's close, then a
    busy week 1. Returns (world, state, the posts)."""
    state, discord = tmp_path / "state", FakeDiscord()
    world = make_world(tmp_path, ("rw.challenges", "AlexFake", 1))           # test play: a challenge done
    assert standings.start(world, state, BEFORE) == 0
    make_world(tmp_path, LAUNCHED, SEASON_ONE, ("rw.challenges", "AlexFake", 2),   # cleared at launch, then 2
               ("st.kills", "LoneFake", 1))                                   # a kill, maybe in test play
    assert standings.close(world, state, rcon.Recorder(), LAUNCH_SUNDAY, WEBHOOK, discord) == 0
    make_world(tmp_path, LAUNCHED,
               ("rw.challenges", "AlexFake", 3), ("rw.challenges", "SamFake", 2),
               ("st.kills", "RiaFake", 3), ("st.kills", "TomFake", 2),
               ("st.bounty", "riafake", 1),                                   # typed in lower case by staff
               ("ev.state", "#event", 1), ("ev.seen", "AlexFake", 1), ("ev.seen", "RiaFake", 1),
               ("rw.events", "AlexFake", 1), ("rw.events", "RiaFake", 1),
               land={"AlexFake": 4, "RiaFake": 4, "TomFake": 2, "LoneFake": 2})
    assert standings.close(world, state, rcon.Recorder(), WEEK_ONE, WEBHOOK, discord) == 0
    return world, state, discord.posts


# ---------------------------------------------------------------- what it says


def test_week_zero_reads_sensibly(season):
    _, state, posts = season
    week0 = posts[0]
    assert week0.startswith("**Monkey SMP Weekly**, the launch weekend: Sun 1 Nov to Sun 8 Nov\n```\n")
    assert "Red Monkeys" in week0 and standings.FORMULA in week0
    # No last week to move up from. The week began in test play, which the launch cleared of challenges only:
    # both done since the launch count, and the kill (it may be test play's) isn't told.
    assert "Biggest mover" not in week0 and "Top fighter" not in week0
    assert f"```\n{recap.LAUNCH}\n**Challenges:** 2 done, by 1 player.\n" in week0
    assert "**Next Saturday:** Faction Raid I, Saturday 14 November, 6 PM Pacific (9 PM Eastern)." in week0
    assert closed_week(state, LAUNCH_SUNDAY)["launched"] is True


def test_a_busy_week(season):
    _, state, posts = season
    week1 = posts[1]
    lines = week1.splitlines()
    assert lines[0] == "**Monkey SMP Weekly**, week 1: Sun 8 Nov to Sun 15 Nov"
    after = lines[lines.index("```", 2) + 1:]
    assert after == [
        "**Biggest mover:** Blue Herons, up 1 place to 2nd.",
        "**Top fighter:** RiaFake (Blue Herons), 3 PvP kills.",
        "**Bounties claimed:** 1, by RiaFake.",
        "**Land:** 5 chunks claimed, the most by Blue Herons (+5).",
        "**Challenges:** 3 done, by 2 players.",
        "**Event turnout:** 2 players came.",
        "**Next Saturday:** The border breaks, from 2500 to 4000 blocks, Saturday 21 November, 6 PM Pacific "
        "(9 PM Eastern).",
        f"Scored as {standings.FORMULA} `/trigger standings` shows the board in game.",
    ]
    # the lines are kept with the closed week, for a retry
    assert closed_week(state, WEEK_ONE)["recap"][0] == ["**Biggest mover:** Blue Herons, up 1 place to 2nd."]


def test_a_quiet_week(tmp_path):
    state, discord = tmp_path / "state", FakeDiscord()
    world = make_world(tmp_path, LAUNCHED)
    standings.start(world, state, LAUNCH_SUNDAY)
    assert standings.close(world, state, rcon.Recorder(), WEEK_ONE, WEBHOOK, discord) == 0
    [post] = discord.posts
    assert recap.QUIET in post and "**Next Saturday:**" in post
    assert "Biggest mover" not in post   # no last week


def test_no_factions_yet(tmp_path):
    world = FakeWorld(tmp_path / "server" / "world").scores(LAUNCHED).path
    state, discord = tmp_path / "state", FakeDiscord()
    standings.start(world, state, LAUNCH_SUNDAY)
    assert standings.close(world, state, rcon.Recorder(), WEEK_ONE, WEBHOOK, discord) == 0
    [post] = discord.posts
    assert "no factions yet" in post and recap.QUIET in post and len(post) <= 2000


# ---------------------------------------------------------------- the launch


def test_nothing_posts_before_the_launch_and_test_play_is_no_last_week(tmp_path, capsys):
    state, discord = tmp_path / "state", FakeDiscord()
    world = make_world(tmp_path, ("st.kills", "RiaFake", 9))
    standings.start(world, state, BEFORE - dt.timedelta(days=7))
    assert standings.close(world, state, rcon.Recorder(), BEFORE, WEBHOOK, discord) == 0
    assert discord.posts == [] and "before the launch (test play): not posting" in capsys.readouterr().out
    closed = closed_week(state, BEFORE)
    assert closed["launched"] is False and "recap" not in closed and not closed["posted"]
    # A retry still posts nothing.
    standings.close(world, state, rcon.Recorder(), BEFORE + dt.timedelta(minutes=10), WEBHOOK, discord)
    assert discord.posts == []
    # After the launch, the test week's table is no "last week": nobody moved up from it.
    make_world(tmp_path, LAUNCHED, land={"AlexFake": 1, "RiaFake": 4, "LoneFake": 2})
    standings.close(world, state, rcon.Recorder(), LAUNCH_SUNDAY, WEBHOOK, discord)
    [post] = discord.posts
    assert "Biggest mover" not in post


def test_a_later_seasons_launch_keeps_its_carried_challenges(tmp_path):
    # Season 2's world starts with challenges carried from Season I, and its launch doesn't clear them: only
    # what was done since the week began counts.
    state, discord = tmp_path / "state", FakeDiscord()
    world = make_world(tmp_path, ("rw.day", "#season", 2), ("rw.challenges", "AlexFake", 9))
    standings.start(world, state, BEFORE)
    make_world(tmp_path, LAUNCHED, ("rw.day", "#season", 2), ("rw.challenges", "AlexFake", 10))
    standings.close(world, state, rcon.Recorder(), LAUNCH_SUNDAY, WEBHOOK, discord)
    [post] = discord.posts
    assert "**Challenges:** 1 done, by 1 player." in post and recap.LAUNCH in post


def test_launched_reads_the_launch_score(tmp_path):
    assert not recap.launched(standings.read_world(make_world(tmp_path / "a")))
    assert recap.launched(standings.read_world(make_world(tmp_path / "b", LAUNCHED)))


# ---------------------------------------------------------------- retries and old weeks


def test_a_retry_posts_what_the_close_worked_out(tmp_path):
    state, discord = tmp_path / "state", FakeDiscord(fail=1)
    world = make_world(tmp_path, LAUNCHED)
    standings.start(world, state, LAUNCH_SUNDAY)
    make_world(tmp_path, LAUNCHED, ("st.kills", "RiaFake", 3))
    assert standings.close(world, state, rcon.Recorder(), WEEK_ONE, WEBHOOK, discord) == 1
    make_world(tmp_path, LAUNCHED, ("st.kills", "RiaFake", 8))   # the world moves on before the retry
    assert standings.close(world, state, rcon.Recorder(), WEEK_ONE + dt.timedelta(minutes=10), WEBHOOK,
                           discord) == 0
    [post] = discord.posts
    assert "3 PvP kills" in post and "8 PvP kills" not in post


def test_a_week_closed_before_the_recap_posts_its_table_alone():
    old = {"start": "2026-11-08T19:00:00-08:00", "end": "2026-11-15T19:00:00-08:00", "rows": [
        vars(r) for r in standings.rank([standings.Row("Red Monkeys", ["AlexFake"], cup=30)])]}
    lines = standings.discord_message(old).splitlines()
    assert lines[0].startswith("**Monkey SMP Weekly**, week 1") and lines[-1].startswith("Scored as")
    assert lines.count("```") == 2 and len(lines) == 6


def test_a_week_begun_before_the_recap_skips_what_it_cant_count(tmp_path):
    state, discord = tmp_path / "state", FakeDiscord()
    world = make_world(tmp_path, LAUNCHED, ("rw.challenges", "AlexFake", 5), ("st.kills", "AlexFake", 2))
    state.mkdir()
    (state / "week.json").write_text(json.dumps({"start": LAUNCH_SUNDAY.isoformat(), "kills": {}, "bounty": {}}))
    assert standings.close(world, state, rcon.Recorder(), WEEK_ONE, WEBHOOK, discord) == 0
    [post] = discord.posts
    assert "**Challenges:**" not in post and "**Land:**" not in post   # no starting point for them
    assert "**Top fighter:** AlexFake (Red Monkeys), 2 PvP kills." in post
    assert "recap" in json.loads((state / "week.json").read_text())   # the next week has one


# ---------------------------------------------------------------- the post's length and names


def test_the_post_stays_under_discords_limit():
    names = ["\U0001F412" * 40, "[click](https://example.invalid)", "@everyone"] + [f"Faction {'X' * 30} {i}"
                                                                                  for i in range(12)]
    rows = standings.rank([standings.Row(n, ["SomePlayer_123"], cup=1000 - i, kills=999, bounties=9)
                           for i, n in enumerate(names)])
    sections = [[f"**Section {i}:** " + "words " * 50] for i in range(12)] + [["**Next Saturday:** soon."]]
    week = {"start": None, "end": WEEK_ONE.isoformat(), "rows": [vars(r) for r in rows], "recap": sections}
    message = standings.discord_message(week)
    assert recap.size(message) <= recap.DISCORD_LIMIT and message.count("```") == 2
    assert "**Section 0:**" in message and "**Section 11:**" not in message   # the last sections go first
    assert message.endswith("shows the board in game.")
    # one that fits keeps every faction the table shows
    short = {**week, "recap": sections[:2]}
    assert "and 5 more" in standings.discord_message(short)


def test_names_cannot_format_the_post():
    assert recap.md("[free](https://x.invalid)") == "\\[free\\]\\(https\\://x.invalid\\)"
    assert recap.md("**Bold** _it_ `code` <@123> # h") == "\\*\\*Bold\\*\\* \\_it\\_ \\`code\\` \\<@123\\> \\# h"
    assert recap.md("two\nlines") == "two lines"
    assert len(recap.md("x" * 80)) == recap.NAME_LIMIT and recap.md("") == "?"


# ---------------------------------------------------------------- adding a section


def test_a_new_section_is_one_function(season, monkeypatch):
    world, state, _ = season

    def firsts(week: recap.Week) -> list[str]:
        return [f"**Server firsts:** {week.number} this week."]
    monkeypatch.setattr(recap, "SECTIONS", [*recap.SECTIONS, firsts])
    week = recap.Week([], standings.read_world(world), {}, None, WEEK_ONE, world)
    assert recap.blocks(week)[-2] == ["**Server firsts:** 1 this week."]


def test_a_broken_section_is_left_out(monkeypatch):
    def broken(week):
        raise KeyError("oops")
    monkeypatch.setattr(recap, "SECTIONS", [broken, lambda week: ["**Fine:** yes."]])
    logged = []
    week = recap.Week([], standings.World([], {}, {}, {}), {}, None, WEEK_ONE)
    assert recap.blocks(week, logged.append)[0] == ["**Fine:** yes."]
    assert "broken section failed (KeyError" in logged[0]


def test_next_saturday_after_the_last_week():
    end = dt.datetime.combine(season_calendar.saturday(12) + dt.timedelta(days=1), dt.time(19), PACIFIC)
    week = recap.Week([], standings.World([], {}, {}, {}), {}, None, end)
    assert recap.next_saturday(week) == ["**Next:** Season II is planned for Saturday 6 February."]


def test_ordinals_and_lists():
    assert [recap.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 101)] == \
        ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "101st"]
    assert recap.listed(["A"]) == "A" and recap.listed(["A", "B", "C"]) == "A, B and C"
    assert recap.listed([str(i) for i in range(8)]) == "0, 1, 2, 3, 4 and 3 more"


# ---------------------------------------------------------------- the review of #66


def empty_world(**claims):
    return standings.World([], claims, {}, {})


def test_a_week_begun_in_test_play_before_the_recap_is_still_test_play(tmp_path):
    # week.json from before the recap (no "recap" baseline), started before the launch: its kills may be test
    # play's, so they aren't told, and the post opens the season.
    state, discord = tmp_path / "state", FakeDiscord()
    world = make_world(tmp_path, LAUNCHED, ("st.kills", "AlexFake", 4))
    state.mkdir()
    (state / "week.json").write_text(json.dumps({"start": BEFORE.isoformat(), "kills": {}, "bounty": {}}))
    assert standings.close(world, state, rcon.Recorder(), LAUNCH_SUNDAY, WEBHOOK, discord) == 0
    [post] = discord.posts
    assert recap.LAUNCH in post and "Top fighter" not in post and recap.QUIET not in post


def test_an_old_closed_week_from_test_play_is_no_last_week(tmp_path):
    state = tmp_path / "state"
    weeks = state / "weeks"
    weeks.mkdir(parents=True)
    old = {"start": None, "end": BEFORE.isoformat(), "rows": []}   # closed by the old code: no "launched"
    (weeks / "2026-11-01.json").write_text(json.dumps(old))
    assert standings.last_launched(state) is None
    (weeks / "2026-11-08.json").write_text(json.dumps({**old, "end": LAUNCH_SUNDAY.isoformat()}))
    assert standings.last_launched(state)["end"] == LAUNCH_SUNDAY.isoformat()
    (weeks / "2026-11-15.json").write_text(json.dumps({**old, "end": WEEK_ONE.isoformat(), "launched": False}))
    assert standings.last_launched(state) is None


def test_a_quiet_week_is_only_one_the_recap_could_count(monkeypatch):
    def broken(week):
        raise KeyError("oops")
    week = recap.Week([], empty_world(), {"start": LAUNCH_SUNDAY.isoformat()}, None, WEEK_ONE)
    for sections, quiet in (([lambda w: [], lambda w: []], True), ([lambda w: [], lambda w: None], False),
                            ([lambda w: [], broken], False)):
        monkeypatch.setattr(recap, "SECTIONS", sections)
        assert ([recap.QUIET] in recap.blocks(week, lambda msg: None)) is quiet
    # A week without a baseline can't count land, challenges or turnout: no "quiet week" for it.
    monkeypatch.undo()
    assert [recap.QUIET] not in recap.blocks(week, lambda msg: None)


def test_next_saturday_and_the_launch_check_cannot_stop_the_close(monkeypatch):
    def broken(week):
        raise ValueError("no calendar")
    monkeypatch.setattr(recap, "next_saturday", broken)
    logged = []
    week = recap.Week([], empty_world(), {"start": "not a date"}, None, WEEK_ONE)
    assert recap.blocks(week, logged.append) == []
    assert any("launch check failed" in m for m in logged) and any("next Saturday failed" in m for m in logged)


def test_the_biggest_mover_is_matched_by_party_id():
    # Blue renamed itself to what Red was called, and Red took a new name: matched by id, Blue climbed 2.
    previous = {"rows": [{"id": "p-red", "name": "Monkeys", "rank": 1}, {"id": "p-x", "name": "X", "rank": 2},
                         {"id": "p-blue", "name": "Herons", "rank": 3}]}
    rows = [{"id": "p-blue", "name": "Monkeys", "rank": 1}, {"id": "p-x", "name": "X", "rank": 2},
            {"id": "p-red", "name": "Herons", "rank": 3}]
    week = recap.Week(rows, empty_world(), {}, previous, WEEK_ONE)
    assert recap.mover(week) == ["**Biggest mover:** Monkeys, up 2 places to 1st."]
    # A file from before the ids matches by name, and only a name that was unique.
    week.previous = {"rows": [{"name": "Herons", "rank": 3}, {"name": "X", "rank": 2}, {"name": "X", "rank": 1}]}
    week.rows = [{"id": "p-blue", "name": "Herons", "rank": 1}, {"id": "p-x", "name": "X", "rank": 2}]
    assert recap.mover(week) == ["**Biggest mover:** Herons, up 2 places to 1st."]


def test_the_player_of_the_week_is_the_top_factions_best_from_season_two():
    rows = [{"id": "p-red", "name": "Red Monkeys", "rank": 1, "members": ["AlexFake", "SamFake"]},
            {"id": "p-blue", "name": "Blue Herons", "rank": 2, "members": ["RiaFake"]}]
    scores = {"rw.day": {"#season": 2}, "st.kills": {"AlexFake": 2, "SamFake": 2, "RiaFake": 9},
              "rw.challenges": {"AlexFake": 4, "SamFake": 5}}
    start = {"start": WEEK_ONE.isoformat(), "kills": {}, "recap": {"launched": True, "scores": {"rw.challenges": {}}}}
    week = recap.Week(rows, standings.World([], {}, scores, {}), start, None, WEEK_ONE + dt.timedelta(weeks=1))
    # Ria has the most kills, but Blue isn't first: Red's two are tied on kills, and Sam did more challenges.
    assert recap.player_of_the_week(week) == [
        "**Player of the Week:** SamFake (Red Monkeys, 1st), 2 PvP kills and 5 challenges."]
    scores["st.kills"] = {"RiaFake": 9}
    scores["rw.challenges"] = {}
    assert recap.player_of_the_week(week) == []   # nobody in the top faction did either
    scores["rw.day"]["#season"] = 1
    scores["st.kills"] = {"AlexFake": 3}
    assert recap.player_of_the_week(week) == []   # Season I: never
    assert recap.player_of_the_week in recap.SECTIONS


def test_the_player_of_the_week_comes_from_every_faction_sharing_first():
    rows = [{"id": "p-red", "name": "Red Monkeys", "rank": 1, "members": ["AlexFake"]},
            {"id": "p-blue", "name": "Blue Herons", "rank": 1, "members": ["RiaFake"]},
            {"id": "p-gold", "name": "Gold Apes", "rank": 3, "members": ["SamFake"]}]
    scores = {"rw.day": {"#season": 2}, "st.kills": {"AlexFake": 1, "RiaFake": 4, "SamFake": 9}}
    start = {"start": WEEK_ONE.isoformat(), "kills": {}, "recap": {"launched": True, "scores": {"rw.challenges": {}}}}
    week = recap.Week(rows, standings.World([], {}, scores, {}), start, None, WEEK_ONE + dt.timedelta(weeks=1))
    assert recap.player_of_the_week(week) == ["**Player of the Week:** RiaFake (Blue Herons, 1st), 4 PvP kills."]


def test_land_counts_chunks_claimed_not_the_net_change(tmp_path):
    then = {PLAYERS["AlexFake"]: 4, PLAYERS["RiaFake"]: 1}
    world = standings.read_world(make_world(tmp_path, LAUNCHED, land={"AlexFake": 1, "RiaFake": 4}))
    week = recap.Week([], world, {"recap": {"launched": True, "claims": then}}, None, WEEK_ONE)
    assert recap.land(week) == ["**Land:** 3 chunks claimed, the most by Blue Herons (+3)."]


def test_a_late_close_names_the_week_that_closed():
    late = dt.datetime(2026, 11, 16, 1, 30, tzinfo=PACIFIC)   # week 1's close, run after Monday 12 AM
    week = recap.Week([], empty_world(), {"start": LAUNCH_SUNDAY.isoformat()}, None, late)
    assert week.number == 1 and recap.next_saturday(week)[0].endswith(
        "Saturday 21 November, 6 PM Pacific (9 PM Eastern).")
    closed = {"start": LAUNCH_SUNDAY.isoformat(), "end": late.isoformat()}
    assert recap.heading(closed) == "**Monkey SMP Weekly**, week 1: Sun 8 Nov to Mon 16 Nov"
    assert recap.heading({"start": None, "end": late.isoformat()}).startswith("**Monkey SMP Weekly**, week 1:")


def test_long_lists_drop_whole_names():
    rows = [{"name": "[" * 40, "members": [f"Player{i}_" + "*" * 20]} for i in range(8)]
    world = standings.World([], {}, {"st.kills": {f"Player{i}_" + "*" * 20: 2 for i in range(8)}}, {})
    week = recap.Week(rows, world, {"start": LAUNCH_SUNDAY.isoformat(), "kills": {}}, None, WEEK_ONE)
    [line] = recap.fighter(week)
    assert len(line) <= recap.LINE_LIMIT and line.endswith(" more, 2 PvP kills each.")
    assert "\\[" in line and "Player7" not in line
    # a line cut short never ends on half an escape
    for n in range(recap.LINE_LIMIT - 5, recap.LINE_LIMIT + 5):
        cut = recap.clip("x" * n + "\\*" * 50)
        assert len(cut) <= recap.LINE_LIMIT and (len(cut[:-1]) - len(cut[:-1].rstrip("\\"))) % 2 == 0


# ---------------------------------------------------------------- preview


def test_preview_changes_nothing(tmp_path, capsys):
    state = tmp_path / "state"
    world = make_world(tmp_path)
    standings.start(world, state, BEFORE)
    make_world(tmp_path, ("st.kills", "RiaFake", 2))
    before = (state / "week.json").read_text()
    assert standings.main(["preview", str(world), "--state", str(state)]) == 0
    out = capsys.readouterr().out
    assert "Before the launch" in out and "**Monkey SMP Weekly**" in out and "**Top fighter:** RiaFake" in out
    assert (state / "week.json").read_text() == before and not (state / "weeks").exists()


def test_the_top_bounty_hunter_counts_both_kinds_once_players_post_bounties():
    rows = [{"id": "p-red", "name": "Red Monkeys", "rank": 1, "members": ["AlexFake", "SamFake"]},
            {"id": "p-blue", "name": "Blue Herons", "rank": 2, "members": ["RiaFake"]}]
    scores = {"st.hunts": {"AlexFake": 3, "RiaFake": 2}, "st.bounty": {"riafake": 2}}
    start = {"start": WEEK_ONE.isoformat(), "bounty": {"riafake": 1},
             "recap": {"launched": True, "scores": {"st.hunts": {"AlexFake": 1}}}}
    week = recap.Week(rows, standings.World([], {}, scores, {}), start, None, WEEK_ONE + dt.timedelta(weeks=1))
    # Alex claimed 2 player bounties this week; Ria 2 player bounties and 1 staff one (named in lower case).
    assert recap.hunter(week) == ["**Top bounty hunter:** RiaFake (Blue Herons), 3 bounties."]
    scores["st.hunts"] = {"AlexFake": 1}
    assert recap.hunter(week) == []   # only a staff bounty this week: the bounties line names its hunter
    del start["recap"]["scores"]["st.hunts"]
    assert recap.hunter(week) is None   # a week begun before the wanted board: it can't tell
    assert recap.SECTIONS.index(recap.hunter) == recap.SECTIONS.index(recap.bounties) + 1
