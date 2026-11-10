import copy
import datetime as dt
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import uuid
from dataclasses import asdict

import pytest
import status
from fake_world import OVERWORLD, FakeWorld, member, score_rows
from nbt_writer import nbt

import events
import news
import rcon
import recap
import saved_world
import season_calendar
import standings
from repo import REPO

FILES = standings.datapack_files()
FUNCTIONS = {k for k in FILES if k.endswith(".mcfunction")}
PT = dt.timezone(dt.timedelta(hours=-7))
SUNDAY = dt.datetime(2026, 11, 1, 19, 0, tzinfo=PT)
WEBHOOK = "https://discord.com/api/webhooks/1/made-up-secret-token"


# ---------------------------------------------------------------- a made-up world


PLAYERS = {name: str(uuid.uuid5(uuid.NAMESPACE_DNS, name)) for name in
           ("AlexFake", "SamFake", "RiaFake", "TomFake", "LoneFake")}


SCOREBOARD = {"DataVersion": 5023, "data": {"PlayerScores": score_rows(
    ("ev.cup", "red", 30, {"display": "Red Monkeys"}),
    ("ev.cup", "blue", 10, {"display": {"text": "Blue", "extra": [" Herons"]}}),
    ("ev.cup", "green", 5, {"display": "Green Team"}),
    ("ev.cup", "#total", 99),
    (events.LEVEL, "AlexFake", 4), (events.LEVEL, "SamFake", 3), (events.LEVEL, "RiaFake", 5),
    (events.LEVEL, "TomFake", 3), (events.LEVEL, "LoneFake", -2),
    ("ev.strength", "TomFake", 1),   # Tom is in the arena: his own Strength is 1, held at +3 in there
    ("st.kills", "AlexFake", 7), ("st.kills", "SamFake", 2), ("st.kills", "RiaFake", 10),
    ("st.kills", "LoneFake", 1), ("st.bounty", "SamFake", 1),
    ("rw.day", "#launched", 1))}}   # monkey:rules/launch has run: the recap posts
BASELINE = {"start": "2026-10-25T19:00:00-07:00", "kills": {"AlexFake": 5, "RiaFake": 4}, "bounty": {}}


def make_world(root, scoreboard=SCOREBOARD):
    fake = FakeWorld(root / "server" / "world").scoreboard(scoreboard)
    parties = {"p-red": ("AlexFake", ["SamFake"]), "p-blue": ("RiaFake", ["TomFake"]), "p-lone": ("LoneFake", [])}
    for pid, (owner, members) in parties.items():
        # the party file still has Sam's old name; usercache has the new one
        fake.party(pid, member(PLAYERS[owner], owner),
                   [member(PLAYERS[m], "OldSam" if m == "SamFake" else m) for m in members])
    for owner, name in (("AlexFake", "Red Monkeys"), ("RiaFake", "Blue Herons")):
        fake.party_name(PLAYERS[owner], name)
    for name, chunks in (("AlexFake", {OVERWORLD: 4}), ("SamFake", {OVERWORLD: 2, "minecraft:the_nether": 1}),
                         ("RiaFake", {OVERWORLD: 4}), ("LoneFake", {OVERWORLD: 1})):
        fake.claims(PLAYERS[name], {dim: [(i, 0) for i in range(n)] for dim, n in chunks.items()})
    world = fake.path
    (world.parent / "usercache.json").write_text(json.dumps(
        [{"name": n, "uuid": u, "expiresOn": "2026-12-01 00:00:00 -0700"} for n, u in PLAYERS.items()]))
    return world


@pytest.fixture
def world(tmp_path):
    return make_world(tmp_path)


def by_name(rows):
    return {r.name: r for r in rows}


# ---------------------------------------------------------------- reading and scoring


def test_reads_parties_names_and_claims(world):
    data = standings.read_world(world)
    parties = {p.id: p for p in data.parties}
    assert parties["p-red"].name == "Red Monkeys"
    assert parties["p-red"].members == ["AlexFake", "SamFake"]   # usercache's name over the party file's
    assert parties["p-lone"].name == "LoneFake's faction"       # no party name set: the owner's
    assert data.claims[PLAYERS["SamFake"]] == 3                 # every dimension counts
    assert data.labels == {"red": "Red Monkeys", "blue": "Blue Herons", "green": "Green Team"}


def test_what_the_world_lacks(world, tmp_path, capsys):
    # A party with no owner is left out, with a warning; a claims file not named by a UUID doesn't count.
    fake = FakeWorld(world).party("p-ghost", None, [member(PLAYERS["TomFake"], "TomFake")])
    fake.claims("server-claims", {OVERWORLD: [(0, 0)]})
    data = standings.read_world(world)
    assert "p-ghost" not in {p.id for p in data.parties} and "server-claims" not in data.claims
    assert "p-ghost.nbt has no owner: left out" in capsys.readouterr().err
    # No parties folder yet: no factions, with a warning. No scoreboard: an error.
    bare = FakeWorld(tmp_path / "bare" / "world").scores().path
    assert standings.read_world(bare).parties == []
    assert "no factions (has a party been made with /openpac?)" in capsys.readouterr().err
    with pytest.raises(SystemExit, match="no scoreboard at .*: give the world folder"):
        standings.read_world(tmp_path / "bare")


def test_a_claim_saved_oddly_in_another_dimension_still_counts(world):
    # Claims are counted, not read: a Nether position with no x/z never stops the weekly standings.
    path = world / f"data/openpartiesandclaims/player-claims/{PLAYERS['LoneFake']}.nbt"
    path.write_bytes(nbt({"dimensions": {OVERWORLD: {"claims": [{"positions": [{"x": 0, "z": 0}]}]},
                                         "minecraft:the_nether": {"claims": [{"positions": [{"y": 1}, {}]}]}}}))
    assert standings.read_world(world).claims[PLAYERS["LoneFake"]] == 3


def test_a_party_file_with_a_bad_member_stops_standings_naming_it(world):
    # As before saved_world.py: a faction can't be ranked without its members, so it stops, now naming the file.
    FakeWorld(world).party("p-bad", member(PLAYERS["TomFake"], "TomFake"), [{"uuid": "nope", "rank": "MEMBER"}])
    with pytest.raises(ValueError, match=re.escape(str(world / "data/openpartiesandclaims/parties/p-bad.nbt"))):
        standings.read_world(world)


def test_the_formula(world, capsys):
    rows = standings.table(standings.read_world(world), BASELINE, standings.warn)
    got = [(r.rank, r.name, r.cup, r.land, r.strength, r.kills, r.bounties, r.points) for r in rows]
    # Leaders: Cup 30, land 7, Strength 7, kills 6.
    assert got == [
        # 40 + 20 + 20 + round(20 * 4/6) = 93, + 5 for Sam's bounty
        (1, "Red Monkeys", 30, 7, 7, 4, 1, 98),
        # round(40 * 10/30) + round(20 * 4/7) + round(20 * 6/7) + 20; Tom's Strength is his real 1
        (2, "Blue Herons", 10, 4, 6, 6, 0, 13 + 11 + 17 + 20),
        # a Cup entry no faction is named like: a row of its own, with a warning
        (3, "Green Team", 5, 0, 0, 0, 0, 7),
        # negative Strength scores nothing (and isn't negative points)
        (4, "LoneFake's faction", 0, 1, -2, 1, 0, 3 + 3),
    ]
    assert "Green Team" in capsys.readouterr().err


def test_no_baseline_counts_every_kill(world):
    rows = by_name(standings.table(standings.read_world(world), None))
    assert rows["Red Monkeys"].kills == 9 and rows["Blue Herons"].kills == 10


def test_a_restarted_counter_counts_in_full(world):
    # A new season's world starts st.kills at 0, under last season's baseline: the new kills still count.
    old_season = {"start": "2026-10-25T19:00:00-07:00", "kills": {"AlexFake": 40, "SamFake": 30}, "bounty": {}}
    rows = by_name(standings.table(standings.read_world(world), old_season))
    assert rows["Red Monkeys"].kills == 7 + 2
    assert standings.gained(5, 3) == 2 and standings.gained(3, 5) == 3 and standings.gained(-1, 0) == 0


def test_a_bounty_counts_however_staff_cased_the_name(tmp_path):
    board = copy.deepcopy(SCOREBOARD)
    board["data"]["PlayerScores"].extend(score_rows(("st.bounty", "alexfake", 1)))
    rows = by_name(standings.table(standings.read_world(make_world(tmp_path, board)), BASELINE))
    assert rows["Red Monkeys"].bounties == 2   # SamFake's, and AlexFake's typed as "alexfake"
    then = {**BASELINE, "bounty": {"ALEXFAKE": 1}}
    assert by_name(standings.table(standings.read_world(make_world(tmp_path / "b", board)), then))[
        "Red Monkeys"].bounties == 1


def test_share_rounds_half_up_and_an_empty_column_scores_nothing():
    assert standings.share(1, 2, 20) == 10
    assert standings.share(1, 8, 20) == 3     # 2.5 rounds up
    assert standings.share(5, 0, 20) == 0
    assert standings.share(-3, 4, 20) == 0
    assert sum(w for _, w in standings.WEIGHTS) == 100


def test_ties_go_to_cup_then_kills_then_share_the_rank():
    rows = standings.rank([standings.Row("A", cup=10, kills=0), standings.Row("B", cup=10, kills=0),
                           standings.Row("C", cup=5, kills=10), standings.Row("D", cup=10, kills=0, land=0)])
    assert [(r.name, r.rank) for r in rows][:3] == [("A", 1), ("B", 1), ("D", 1)]
    assert rows[3].name == "C" and rows[3].rank == 4


def test_cup_matches_on_the_owner_name_too(tmp_path):
    board = json.loads(json.dumps(SCOREBOARD))
    board["data"]["PlayerScores"].append({"Objective": "ev.cup", "Name": "lonefake", "Score": 12})
    rows = by_name(standings.table(standings.read_world(make_world(tmp_path, board)), BASELINE))
    assert rows["LoneFake's faction"].cup == 12


# ---------------------------------------------------------------- the board


def long_rows(n=15):
    names = ['Ünïcödé "Quoted" \\ Faction With A Very Long Name', "@everyone", "§cColor"] + \
            [f"Faction {'X' * 30} {i}" for i in range(n - 3)]
    return standings.rank([standings.Row(name, ["SomePlayer_123"], cup=1000 - i, land=64, strength=-20,
                                         kills=999, bounties=9) for i, name in enumerate(names)])


def test_board_commands_fit_rcon_and_stay_plain_ascii():
    rows = long_rows()
    last = {"start": "2026-10-18T19:00:00-07:00", "end": "2026-10-25T19:00:00-07:00",
            "rows": [vars(r) for r in rows]}
    commands = standings.board_commands(rows, BASELINE, last, SUNDAY)
    assert commands[-1] == "function monkey:standings/publish"
    for c in commands:
        assert len(c.encode()) <= rcon.LIMIT
        assert c.isascii() and "\n" not in c and not c.startswith("-")
    assert commands[0].startswith("data modify storage monkey:standings week set value {")
    assert commands[1].startswith("data modify storage monkey:standings last set value {")
    assert "1. Unicode Quoted Fact~: " in commands[0]   # quotes and backslashes never reach SNBT
    assert '\\"' not in commands[0] and "\\\\" not in commands[0]
    assert "since Sun 25 Oct, updated Sun 1 Nov, 7 PM" in commands[0]
    assert "Final standings, week of Sun 18 Oct to Sun 25 Oct" in commands[1]
    assert "...and 10 more" in commands[1] and "...and 5 more" in commands[0]


def test_board_names():
    assert standings.board_name("Ünïcödé Monkeys") == "Unicode Monkeys"
    assert standings.board_name('Bad "quote" \\ name') == "Bad quote name"
    assert standings.board_name("§cRed") == "cRed"
    assert len(standings.board_name("x" * 50)) == standings.NAME_LIMIT


def test_snbt():
    assert standings.snbt({"text": 'a"b\\c\nd', "bold": True, "extra": [{"text": ""}]}) == \
        '{text:"a\\"b\\\\c\\nd",bold:1b,extra:[{text:""}]}'


# ---------------------------------------------------------------- the week: start, close, retries


def FakeRcon(fail=0):  # noqa: N802 (reads as the class it was)
    return rcon.Recorder(fail=fail)


class FakeDiscord:
    def __init__(self, fail=0):
        self.posts, self.fail = [], fail

    def __call__(self, request, timeout):
        if self.fail:
            self.fail -= 1
            raise urllib.error.HTTPError(request.full_url, 503, "Service Unavailable", {}, None)
        self.posts.append((request.full_url, request.get_header("Content-type"), json.loads(request.data)))
        return io.BytesIO(b"")


def test_start_takes_the_first_snapshot_once(world, tmp_path):
    state = tmp_path / "state"
    assert standings.start(world, state, SUNDAY) == 0
    week = json.loads((state / "week.json").read_text())
    assert week["kills"] == {"AlexFake": 7, "LoneFake": 1, "RiaFake": 10, "SamFake": 2}
    assert week["start"] == "2026-11-01T19:00:00-07:00"
    assert standings.start(world, state, SUNDAY + dt.timedelta(days=1)) == 0
    assert json.loads((state / "week.json").read_text()) == week


def test_close_keeps_the_week_starts_the_next_and_posts_once(world, tmp_path, capsys):
    state = tmp_path / "state"
    state.mkdir()
    (state / "week.json").write_text(json.dumps(BASELINE))
    rcon, discord = FakeRcon(), FakeDiscord()
    assert standings.close(world, state, rcon, SUNDAY, WEBHOOK, discord) == 0
    closed = json.loads((state / "weeks" / "2026-11-01.json").read_text())
    assert [r["name"] for r in closed["rows"]][:2] == ["Red Monkeys", "Blue Herons"]
    assert closed["start"] == BASELINE["start"] and closed["posted"] and closed["announced"]
    # the next week starts from everyone's kills now
    assert json.loads((state / "week.json").read_text())["kills"]["RiaFake"] == 10
    # the board shows the new week (no kills yet) and the closed one, then it is announced
    assert rcon.sent[-3] == "function monkey:standings/announce"
    assert rcon.sent[-4] == "function monkey:standings/publish"
    # then the week's wars end (tools/diplomacy.py week_end)
    assert rcon.sent[-2] == 'data modify storage monkey:diplomacy batch set value [{f:"week_over",seq:0}]'
    assert rcon.sent[-1] == "function monkey:diplomacy/batch/run"
    assert rcon.sent[0] == "save-all flush"   # the world is on disk before the close reads it
    assert "kills 0" in rcon.sent[1] and "kills 4" in rcon.sent[2]
    [(url, kind, body)] = discord.posts
    assert url == WEBHOOK and kind == "application/json"
    assert body["allowed_mentions"] == {"parse": []}
    assert "Red Monkeys" in body["content"] and len(body["content"]) <= 2000
    assert "Sun 25 Oct to Sun 1 Nov" in body["content"] and body["content"].startswith("**Monkey SMP Weekly**")
    first = capsys.readouterr()
    assert "board updated and announced in chat" in first.out
    # run again (a retry, a re-run): nothing is closed or posted twice
    assert standings.close(world, state, rcon, SUNDAY + dt.timedelta(minutes=20), WEBHOOK, discord) == 0
    assert len(list((state / "weeks").iterdir())) == 1 and len(discord.posts) == 1
    assert rcon.sent.count("function monkey:standings/announce") == 1
    out = capsys.readouterr()
    # and it says so, not that it announced again
    assert "already announced in chat" in out.out and "and announced in chat" not in out.out
    assert "made-up-secret-token" not in first.out + first.err + out.out + out.err


def test_close_saves_the_world_before_it_reads_it(world, tmp_path, monkeypatch):
    """The timer's close must not read a world up to 5 minutes old: a kill just before 7 PM would land in the next
    week. It asks the running server to write everything first, as the staff page's board button does."""
    state, server, order = tmp_path / "state", FakeRcon(), []
    reads = standings.read_world
    monkeypatch.setattr(standings, "read_world", lambda w: (order.append(list(server.sent)), reads(w))[1])
    assert standings.close(world, state, server, SUNDAY, "", FakeDiscord()) == 0
    assert order and all(sent == ["save-all flush"] for sent in order)


def test_close_with_a_running_server_that_will_not_save_closes_nothing_and_fails(world, tmp_path, capsys):
    state, server = tmp_path / "state", FakeRcon(fail=99)
    assert standings.close(world, state, server, SUNDAY, WEBHOOK, FakeDiscord()) == 1   # the unit retries
    assert not (state / "weeks").exists() and "save-all flush" in capsys.readouterr().err


def test_close_with_a_stopped_server_reads_what_the_stop_saved(world, tmp_path):
    state, server = tmp_path / "state", rcon.Recorder(running=False, fail=99)
    assert standings.close(world, state, server, SUNDAY, "", FakeDiscord()) == 1   # the board can't go up
    assert (state / "weeks" / "2026-11-01.json").exists()


class SavesThenFails(rcon.Recorder):
    """Saves the world, then is down for the next `fail` commands: a board or wars that fail after the close."""

    def __call__(self, command):
        if command == "save-all flush":
            self.sent.append(command)
            return ""
        return super().__call__(command)


def test_a_failed_post_or_board_is_retried_without_closing_again(world, tmp_path, capsys):
    state = tmp_path / "state"
    rcon, discord = SavesThenFails(fail=1), FakeDiscord(fail=1)
    assert standings.close(world, state, rcon, SUNDAY, WEBHOOK, discord) == 1
    closed = json.loads((state / "weeks" / "2026-11-01.json").read_text())
    assert not closed["posted"] and not closed["announced"]
    out = capsys.readouterr()
    assert "HTTP 503" in out.err and "made-up-secret-token" not in out.out + out.err
    assert standings.close(world, state, rcon, SUNDAY + dt.timedelta(minutes=10), WEBHOOK, discord) == 0
    closed = json.loads((state / "weeks" / "2026-11-01.json").read_text())
    assert closed["posted"] and closed["announced"] and len(discord.posts) == 1
    assert len(list((state / "weeks").iterdir())) == 1


def test_no_webhook_posts_nothing(world, tmp_path, capsys):
    assert standings.close(world, tmp_path / "state", FakeRcon(), SUNDAY, "", FakeDiscord()) == 0
    assert "not posting" in capsys.readouterr().out


def test_post_never_shows_the_url():
    def broken(request, timeout):
        raise urllib.error.URLError(f"cannot reach {request.full_url}")
    assert standings.post_discord(WEBHOOK, "hi", broken) == "could not reach Discord (URLError)"
    assert standings.post_discord("http://example.invalid/x", "hi", broken) == \
        "the webhook setting is not an https:// URL"


def test_webhook_falls_back_to_the_main_channel(monkeypatch):
    monkeypatch.delenv("STANDINGS_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://main")
    assert standings.webhook() == "https://main"
    monkeypatch.setenv("STANDINGS_WEBHOOK_URL", "https://standings")
    assert standings.webhook() == "https://standings"


def test_discord_message_is_a_table():
    rows = long_rows(14)
    message = standings.discord_message({"start": None, "end": SUNDAY.isoformat(), "rows": [vars(r) for r in rows]})
    assert len(message) <= standings.DISCORD_LIMIT
    assert message.count("```") == 2 and "and 4 more" in message
    assert "Bounty" in message and standings.FORMULA in message


def test_the_recap_carries_the_weeks_war_and_pacts_first():
    # A week with wars is not "a quiet week": the war and pacts lines come first, then the recap's own lines.
    week = {"start": None, "end": SUNDAY.isoformat(), "rows": [vars(r) for r in long_rows(3)],
            "diplomacy": ["- Red Monkeys declared war on Blue Jays"],
            "recap": [[recap.QUIET], ["**Next Saturday:** Faction Raid I."]]}
    message = standings.discord_message(week)
    assert recap.QUIET not in message
    assert message.index("declared war") < message.index("**Next Saturday:**")
    assert recap.QUIET in standings.discord_message({**week, "diplomacy": []})


def test_main_show(world, capsys):
    assert standings.main(["show", str(world)]) == 0
    assert "Red Monkeys" in capsys.readouterr().out


# ---------------------------------------------------------------- the data pack


def fn(path: str) -> str:
    return FILES[f"{standings.FN}/{path}.mcfunction"]


def test_kills_count_outside_the_arena_only():
    tick = fn("tick")
    assert "scoreboard objectives add st.pk playerKillCount" in fn("load")
    assert "execute as @a[scores={st.pk=1..},tag=!ev.arena] run scoreboard players operation @s st.kills += @s st.pk" \
        in tick
    assert tick.index("st.kills += @s st.pk") < tick.index("scoreboard players set @a[scores={st.pk=1..}] st.pk 0")


def test_the_bounty_title_never_replaces_another_title():
    claim = fn("bounty/claim").splitlines()
    joins = [line for line in claim if "run team " in line]
    assert joins == ["$execute as $(hunter) if entity @s[team=] run team join bounty_hunter @s"]
    assert "$scoreboard players add $(hunter) st.bounty 1" in claim
    # cosmetic only: nothing given, nothing for combat
    assert not any(line.startswith(("give", "$give", "effect", "$effect", "attribute", "$attribute")) for line in claim)
    assert 'team modify bounty_hunter prefix {"text":"[Bounty Hunter] ","color":"red"}' in fn("load")
    # hunters from rival factions share the team: it must not show them each other while invisible
    assert "team modify bounty_hunter seeFriendlyInvisibles false" in fn("load")


def test_the_board_follows_the_storage():
    assert "tellraw @s {\"nbt\":\"board\",\"storage\":\"monkey:standings\",\"interpret\":true}" in fn("use")
    assert "data modify entity @s text set from storage monkey:standings board" in fn("refresh")
    assert "scoreboard players add #board st.ver 1" in fn("publish")
    assert "unless score @s st.ver = #board st.ver run function monkey:standings/refresh" in fn("second")


def test_help_lists_only_real_functions():
    assert fn("help").count("suggest_command") == len(standings.HELP)


# ---------------------------------------------------------------- the VPS scripts


DEPLOY = REPO.root / "deploy"
SCRIPTS = ["monkey-standings.sh", "install-standings.sh"]
UNITS = ["monkey-standings.service", "monkey-standings.timer", "monkey-standings-board.service",
         "monkey-standings-board.timer"]


@pytest.mark.parametrize("name", SCRIPTS + UNITS)
def test_deploy_files_are_plain_ascii_with_lf(name):
    data = (DEPLOY / name).read_bytes()
    assert data.isascii() and b"\r" not in data


@pytest.mark.parametrize("name", SCRIPTS)
def test_scripts_are_posix_sh_and_never_print_the_webhook(name):
    text = (DEPLOY / name).read_text()
    assert text.startswith("#!/bin/sh\n") and "set -eu" in text
    for line in text.splitlines():
        # a webhook's value is only ever passed on, never expanded where it could be printed
        if re.search(r"\$\{?\w*WEBHOOK_URL", line):
            assert re.match(r"\s*\w+_WEBHOOK_URL=\$\{\w+_WEBHOOK_URL:-\$?\w*\}$", line), line
    shell = shutil.which("dash")
    if shell:
        subprocess.run([shell, "-n", str(DEPLOY / name)], check=True)


def test_install_script_reads_no_secret():
    text = (DEPLOY / "install-standings.sh").read_text()
    assert ". \"$ENV_FILE\"" not in text and "rcon.password" not in text and "WEBHOOK_URL=" not in text
    assert set(re.findall(r"\$\(setting (\w+)", text)) == {"REPO_DIR", "LIVE_DIR", "STANDINGS_DIR"}
    for unit in UNITS:
        assert unit in text


def test_units_run_the_script_as_monkey_on_sunday_evening():
    service = (DEPLOY / "monkey-standings.service").read_text()
    assert "User=monkey" in service and "ExecStart=/bin/sh /srv/monkey/repo/deploy/monkey-standings.sh close" in service
    assert "OnCalendar=Sun *-*-* 19:00:00 America/Los_Angeles" in (DEPLOY / "monkey-standings.timer").read_text()
    board = (DEPLOY / "monkey-standings-board.service").read_text()
    assert "ExecStart=/bin/sh /srv/monkey/repo/deploy/monkey-standings.sh board" in board
    script = (DEPLOY / "monkey-standings.sh").read_text()
    assert "deploy_lock 1800" in script and "export STANDINGS_WEBHOOK_URL" in script
    assert "STANDINGS_WEBHOOK_URL=" in (DEPLOY / "monkey-deploy.env.example").read_text()


# ---------------------------------------------------------------- the website's file


NOW = dt.datetime(2026, 11, 14, 18, 0, tzinfo=season_calendar.PACIFIC)   # Saturday, 02:00 UTC on the 15th
STOLEN = (*PLAYERS, "OldSam", *PLAYERS.values(), "p-red", "p-blue", "p-lone", "members", "kills", "bounties", "land",
          "strength", "cup", "claims", "uuid", "owner", "recap", "outposts")


def unlaunched(scoreboard=SCOREBOARD):
    board = copy.deepcopy(scoreboard)
    board["data"]["PlayerScores"] = [r for r in board["data"]["PlayerScores"] if r["Name"] != "#launched"]
    return board


def public_board(world, tmp_path, now=NOW, server=None):
    """The hourly run with a website file: (its exit status, the file, the state folder)."""
    state, out = tmp_path / "state", tmp_path / "status" / "standings.json"
    code = standings.board(world, state, server or FakeRcon(), now, out)
    return code, out, state


def closed_week(state, day="2026-11-08", end="2026-11-08T19:00:00-08:00", **fields):
    path = state / "weeks" / f"{day}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"start": None, "end": end, "launched": True, "rows": [
        {"rank": 1, "name": "Red Monkeys", "points": 87, "members": ["AlexFake", "SamFake"], "kills": 3, "id": "p-red"},
        {"rank": 2, "name": "LoneFake's faction", "points": 5, "members": ["LoneFake"], "kills": 1, "id": "p-lone"},
    ], **fields}), encoding="utf-8")
    return path


def test_the_file_is_the_contract(world, tmp_path):
    code, out, state = public_board(world, tmp_path)
    assert code == 0
    data = json.loads(out.read_bytes())
    assert list(data) == ["version", "checked", "season", "week_closes", "factions", "last_week"]
    assert data == {
        "version": 1, "checked": "2026-11-15T02:00:00Z", "season": 1, "week_closes": "2026-11-16T03:00:00Z",
        "factions": [{"rank": 1, "name": "Red Monkeys", "points": 103},
                     {"rank": 2, "name": "Blue Herons", "points": 61},
                     {"rank": 3, "name": "Green Team", "points": 7},
                     {"rank": 4, "name": None, "points": 5}],
        "last_week": None}
    closed_week(state)
    public_board(world, tmp_path)
    assert json.loads(out.read_bytes())["last_week"] == {
        "closed": "2026-11-09T03:00:00Z",
        "factions": [{"rank": 1, "name": "Red Monkeys", "points": 87}, {"rank": 2, "name": None, "points": 5}]}


def only_allowed_keys(value):
    if isinstance(value, dict):
        assert set(value) <= {"version", "checked", "season", "week_closes", "factions", "last_week", "closed", "rank",
                              "name", "points"}
        for v in value.values():
            only_allowed_keys(v)
    elif isinstance(value, list):
        for v in value:
            only_allowed_keys(v)


def test_only_names_ranks_and_points_get_out(world, tmp_path):
    state, out = tmp_path / "state", tmp_path / "status" / "standings.json"
    state.mkdir()
    (state / "week.json").write_text(json.dumps({**BASELINE, "start": "2026-11-01T19:00:00-08:00"}))
    # A close, whose week's file holds every player's name and count (the recap too), then an hour, then a retry.
    close_at = dt.datetime(2026, 11, 8, 19, 0, tzinfo=season_calendar.PACIFIC)
    for run in (lambda: standings.close(world, state, FakeRcon(), close_at, "", FakeDiscord(), out=out),
                lambda: standings.board(world, state, FakeRcon(), close_at + dt.timedelta(hours=1), out),
                lambda: standings.close(world, state, FakeRcon(), close_at + dt.timedelta(hours=2), "", FakeDiscord(),
                                        out=out)):
        assert run() == 0
        raw = out.read_bytes()
        for secret in STOLEN:
            assert secret.lower().encode() not in raw.lower(), secret
        data = json.loads(raw)
        only_allowed_keys(data)
        assert data["last_week"]["factions"][0] == {"rank": 1, "name": "Red Monkeys", "points": 98}
    # The week's own file really did hold them: the test would catch them getting out.
    kept = next((state / "weeks").glob("*.json")).read_text()
    assert "AlexFake" in kept and "kills" in kept


def test_a_close_shows_the_closed_week_and_the_new_one(world, tmp_path):
    state, out = tmp_path / "state", tmp_path / "status" / "standings.json"
    state.mkdir()
    (state / "week.json").write_text(json.dumps({**BASELINE, "start": "2026-11-01T19:00:00-08:00"}))
    close_at = dt.datetime(2026, 11, 8, 19, 0, tzinfo=season_calendar.PACIFIC)
    assert standings.close(world, state, FakeRcon(), close_at, "", FakeDiscord(), out=out) == 0
    data = json.loads(out.read_bytes())
    assert data["last_week"]["closed"] == "2026-11-09T03:00:00Z"
    assert data["week_closes"] == "2026-11-16T03:00:00Z"
    # The new week has no kills or bounties yet, so it has fewer points than the week it follows.
    assert data["factions"][0] == {"rank": 1, "name": "Red Monkeys", "points": 80}


def test_nothing_is_written_before_the_launch(tmp_path, capsys):
    world = make_world(tmp_path, unlaunched())
    state, out = tmp_path / "state", tmp_path / "status" / "standings.json"
    assert standings.board(world, state, FakeRcon(), NOW, out) == 0
    assert standings.close(world, state, FakeRcon(), NOW, "", FakeDiscord(), out=out) == 0
    assert not out.exists() and not out.parent.exists()
    assert "before the launch" in capsys.readouterr().out


def test_a_week_closed_in_test_play_is_no_last_week(world, tmp_path):
    state = tmp_path / "state"
    closed_week(state, day="2026-11-01", end="2026-11-01T19:00:00-08:00", launched=False)
    assert json.loads(public_board(world, tmp_path)[1].read_bytes())["last_week"] is None
    # From before the launch flag was kept: its end tells.
    path = closed_week(state, day="2026-11-02", end="2026-11-02T19:00:00-08:00")
    week = json.loads(path.read_text())
    del week["launched"]
    path.write_text(json.dumps(week))
    assert json.loads(public_board(world, tmp_path)[1].read_bytes())["last_week"] is None


def test_the_write_is_atomic_in_the_same_folder(world, tmp_path, monkeypatch):
    made = []
    real = tempfile.mkstemp

    def mkstemp(**kw):
        made.append(kw["dir"])
        return real(**kw)
    monkeypatch.setattr(tempfile, "mkstemp", mkstemp)
    code, out, _ = public_board(world, tmp_path)
    assert code == 0 and made == [out.parent] and [p.name for p in out.parent.iterdir()] == ["standings.json"]
    # A rename that fails leaves the old file whole, and no temporary file.
    before = out.read_bytes()

    def no_rename(src, dst):
        raise PermissionError("no")
    monkeypatch.setattr(os, "replace", no_rename)
    assert public_board(world, tmp_path, NOW + dt.timedelta(hours=1))[0] == 1
    assert out.read_bytes() == before and [p.name for p in out.parent.iterdir()] == ["standings.json"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX modes")
def test_caddy_can_read_the_file_whatever_the_umask(world, tmp_path):
    """mkstemp makes 0600 files and the timers run as monkey, so without the chmod Caddy (as caddy) gets a 403."""
    old = os.umask(0o077)
    try:
        code, out, _ = public_board(world, tmp_path)
    finally:
        os.umask(old)
    assert code == 0 and stat.S_IMODE(out.stat().st_mode) == 0o644


def failing_write(monkeypatch):
    def write(path, data):
        raise PermissionError(13, "Permission denied", str(path))
    monkeypatch.setattr(standings, "write_public", write)


def test_a_bad_folder_never_stops_the_board(world, tmp_path, capsys):
    state = tmp_path / "state"
    (tmp_path / "a-file").write_text("x")
    for out in (tmp_path / "a-file" / "standings.json", tmp_path):   # a file for a folder; a folder for the file
        server = FakeRcon()
        assert standings.board(world, state, server, NOW, out) == 1
        assert "function monkey:standings/publish" in server.sent
        assert "could not write the public standings" in capsys.readouterr().err
    assert (tmp_path / "a-file").read_text() == "x"


def test_bad_permissions_never_stop_the_board(world, tmp_path, monkeypatch, capsys):
    failing_write(monkeypatch)
    server = FakeRcon()
    assert standings.board(world, tmp_path / "state", server, NOW, tmp_path / "standings.json") == 1
    assert "function monkey:standings/publish" in server.sent
    assert "Permission denied" in capsys.readouterr().err


def test_a_failed_write_never_stops_the_close_which_stays_idempotent(world, tmp_path, monkeypatch, capsys):
    failing_write(monkeypatch)
    state, out = tmp_path / "state", tmp_path / "status" / "standings.json"
    server, discord = FakeRcon(), FakeDiscord()
    assert standings.close(world, state, server, SUNDAY, WEBHOOK, discord, out=out) == 1   # so the unit's retries run
    assert "could not write the public standings" in capsys.readouterr().err
    week = (state / "week.json").read_text()
    closed = json.loads((state / "weeks" / "2026-11-01.json").read_text())
    assert closed["posted"] and closed["announced"] and len(discord.posts) == 1
    # A retry closes nothing twice, and once the folder is back the file goes out with the closed week.
    monkeypatch.undo()
    later = SUNDAY + dt.timedelta(minutes=10)
    assert standings.close(world, state, server, later, WEBHOOK, discord, out=out) == 0
    assert (state / "week.json").read_text() == week and len(discord.posts) == 1
    assert len(list((state / "weeks").iterdir())) == 1
    assert server.sent.count("function monkey:standings/announce") == 1
    assert json.loads(out.read_bytes())["last_week"]["closed"] == "2026-11-02T02:00:00Z"


def test_anything_going_wrong_in_the_file_stops_nothing(world, tmp_path, monkeypatch, capsys):
    def broken(*args):
        raise RuntimeError("a bug in the public file")
    monkeypatch.setattr(standings, "public_standings", broken)
    server = FakeRcon()
    assert standings.board(world, tmp_path / "state", server, NOW, tmp_path / "standings.json") == 1
    assert "function monkey:standings/publish" in server.sent and "a bug" in capsys.readouterr().err


def test_a_server_that_is_down_still_gets_the_file_written(world, tmp_path):
    code, out, _ = public_board(world, tmp_path, server=FakeRcon(fail=99))
    assert code == 1 and json.loads(out.read_bytes())["factions"]    # the board's failure stays the board's


@pytest.mark.parametrize(("raw", "shown"), [
    ("Red Wolves", "Red Wolves"),
    ("§cRed §lWolves§r", "Red Wolves"),
    ("§", None),
    ("§c§l", None),
    ("Red\x00\x07\x1b[31m Wolves\n\t", "Red[31m Wolves"),
    ("‮Red​ Wolves﻿", "Red Wolves"),
    ("§​cRed", "Red"),
    ("  many   spaces  ", "many spaces"),
    ("Café サル \U0001f412", "Café サル \U0001f412"),
    ("x" * 200, "x" * standings.PUBLIC_NAME_LIMIT),
    ("x" * (standings.PUBLIC_NAME_LIMIT - 1) + " yy", "x" * (standings.PUBLIC_NAME_LIMIT - 1)),
    ("", None),
    ("   ", None),
    ("\u3164", None),                                # draws nothing, though it counts as a letter
    ("\u115f\u1160\uffa0 \u2800", None),
    ("\u3164Red\u2800", "Red"),
    ("!!!", None),                                   # no letter or digit
    ("\U0001f412", None),
    ("\u200d\ufe0f", None),
    ("!" * standings.PUBLIC_NAME_LIMIT + "a", None),  # the letter was past the cut
    ("R\u00aded\u034f\ufe00\U000e0041", "Red"),      # soft hyphen, grapheme joiner, variation selector, tag
    ("\u2066Red\u2069\u200e", "Red"),                # bidi controls
    ("Red \U000effff", "Red \U000effff"),            # no data for it: stays, as a new emoji would
    ("Red \U0001f468\u200d\U0001f469\ufe0f", "Red \U0001f468\u200d\U0001f469\ufe0f"),   # one emoji, built of two
    ("Se\u0301n", "Se\u0301n"),
    ("a" + "\u0301" * 9 + "b", "a\u0301\u0301\u0301b"),   # no tower of marks
    ("a" + "\u0301\u200d" * 9, "a\u0301\u200d\u0301\u200d\u0301" + "\u200d" * 7),   # nor one with joiners between
    (None, None),
    (7, None),
    (["Red"], None),
    ({"text": "Red"}, None),
    (True, None),
])
def test_names_are_cleaned_and_capped(raw, shown):
    assert standings.public_name(raw) == shown


def test_rows_of_any_shape_in_a_closed_week(world, tmp_path):
    state, out = tmp_path / "state", tmp_path / "status" / "standings.json"
    path = closed_week(state)
    week = json.loads(path.read_text())
    week["rows"] = [{"rank": 1, "points": 9}, {"rank": 2, "name": 5, "points": 8},
                    {"rank": True, "name": "no", "points": 7}, {"rank": 3, "name": "no", "points": "many"}, "not a row",
                    {"rank": 4, "name": "§eFine", "points": 1, "members": "not a list"}]
    path.write_text(json.dumps(week))
    standings.publish(out, world, standings.read_world(world), None, state, NOW)
    assert json.loads(out.read_bytes())["last_week"]["factions"] == [
        {"rank": 1, "name": None, "points": 9}, {"rank": 2, "name": None, "points": 8},
        {"rank": 4, "name": "Fine", "points": 1}]


@pytest.mark.parametrize("damage", [
    "{broken", "[]", json.dumps({"launched": True}), json.dumps({"launched": True, "end": 7}),
    json.dumps({"launched": True, "end": "2026-11-08T19:00:00"})])
def test_a_damaged_closed_week_leaves_last_week_out_and_nothing_else(world, tmp_path, damage, capsys):
    state, out = tmp_path / "state", tmp_path / "status" / "standings.json"
    closed_week(state).write_text(damage)
    standings.publish(out, world, standings.read_world(world), None, state, NOW)
    assert "left out of the public standings" in capsys.readouterr().err
    written = json.loads(out.read_bytes())
    assert written["last_week"] is None and len(written["factions"]) == 4


def write_hidden(state, text, encoding="utf-8"):
    state.mkdir(parents=True, exist_ok=True)
    (state / standings.HIDDEN_NAMES).write_bytes(text.encode(encoding))


@pytest.mark.parametrize("line", ["red monkeys", "RED MONKEYS", "  Red   Monkeys  ", "§cRed §lMonkeys",
                                  "red-monkeys"])
def test_a_hidden_name_is_null_in_any_case_or_colour(world, tmp_path, line):
    state = tmp_path / "state"
    write_hidden(state, f"Something Else\n\n{line}\n")
    closed_week(state)
    _, out, _ = public_board(world, tmp_path)
    data = json.loads(out.read_bytes())
    assert data["factions"][0] == {"rank": 1, "name": None, "points": 103}
    assert data["factions"][1]["name"] == "Blue Herons"
    # At read time: hiding a name fixes old weeks too.
    assert data["last_week"]["factions"][0] == {"rank": 1, "name": None, "points": 87}
    assert b"Red" not in out.read_bytes()


@pytest.mark.parametrize("name", ["§cBad §nName", "BAD§r NAME", "B​ad‮ Name", "b.a.d n.a.m.e",
                                  "Bàd Name", "Ｂａｄ Name", "B\u200dad Name", "§\u200dcBad Name", "\u3164Bad Name"])
def test_colour_codes_and_tricks_cant_dodge_a_hidden_name(name):
    hidden = frozenset({standings.name_key("Bad Name")})
    assert standings.shown_name({"name": name}, hidden, frozenset()) is None
    assert standings.shown_name({"name": "Good Name"}, hidden, frozenset()) == "Good Name"


def test_a_long_name_hides_copied_whole_or_cut_short(tmp_path):
    state, long = tmp_path / "state", "A" * 40 + " end"
    for line in (long, standings.public_name(long)):
        write_hidden(state, line + "\n")
        assert standings.shown_name({"name": long}, standings.hidden_names(state), frozenset()) is None


def test_a_name_of_symbols_alone_shows_as_no_name_and_hides_nothing(tmp_path):
    state = tmp_path / "state"
    write_hidden(state, "!!!\n\u3164\n")
    hidden = standings.hidden_names(state)
    assert hidden == frozenset()
    assert standings.shown_name({"name": "!!!"}, hidden, frozenset()) is None
    assert standings.shown_name({"name": "Red"}, hidden, frozenset()) == "Red"


def test_comment_lines_in_the_hidden_list(tmp_path):
    state = tmp_path / "state"
    write_hidden(state, "# Red Monkeys was renamed\n  # so was Blue Herons\nTeam #1\n1 Up\n")
    assert standings.hidden_names(state) == {standings.name_key("Team #1"), standings.name_key("1 Up")}
    assert standings.shown_name({"name": "#1 Up"}, standings.hidden_names(state), frozenset()) is None


def test_a_bad_byte_spoils_only_its_own_line_and_says_so(world, tmp_path, capsys):
    state = tmp_path / "state"
    state.mkdir()
    (state / standings.HIDDEN_NAMES).write_bytes(b"caf\xe9\nRed Monkeys\n")
    code, out, _ = public_board(world, tmp_path)
    assert code == 0 and json.loads(out.read_bytes())["factions"][0]["name"] is None
    assert "not all UTF-8" in capsys.readouterr().err


def test_the_hidden_list_from_a_windows_editor(tmp_path):
    state = tmp_path / "state"
    write_hidden(state, "Red Monkeys\r\nBlue Herons\r\n", "utf-8-sig")
    assert standings.hidden_names(state) == {standings.name_key("Red Monkeys"), standings.name_key("Blue Herons")}


def test_no_hidden_file_is_fine(tmp_path):
    assert standings.hidden_names(tmp_path) == frozenset()


def test_a_hidden_list_that_cant_be_read_writes_nothing(world, tmp_path, capsys):
    """Showing a name staff hid is worse than an old file, so the old file stays, and the board goes on."""
    state = tmp_path / "state"
    state.mkdir()
    _, out, _ = public_board(world, tmp_path)
    before = out.read_bytes()
    (state / standings.HIDDEN_NAMES).mkdir()
    server = FakeRcon()
    assert standings.board(world, state, server, NOW + dt.timedelta(hours=1), out) == 1
    assert "function monkey:standings/publish" in server.sent
    assert out.read_bytes() == before and "could not write the public standings" in capsys.readouterr().err


@pytest.mark.parametrize("cache", [None, "[]", "not json", '[{"uuid": "x", "name": 7}]'])
def test_no_player_names_to_check_against_writes_nothing(world, tmp_path, cache, capsys):
    """Without them, a faction named after a player would show."""
    state = tmp_path / "state"
    _, out, _ = public_board(world, tmp_path)
    before = out.read_bytes()
    path = world.parent / "usercache.json"
    path.unlink()
    if cache is not None:
        path.write_text(cache)
    server = FakeRcon()
    assert standings.board(world, state, server, NOW + dt.timedelta(hours=1), out) == 1
    assert out.read_bytes() == before and "usercache.json is missing or empty" in capsys.readouterr().err


def test_a_players_name_never_shows_as_a_faction():
    people = frozenset({standings.name_key("RiaFake")})
    show = standings.shown_name
    # read_parties' name for a party with none, however its case reads
    assert show({"name": "AlexFake's faction", "members": ["AlexFake"]}, frozenset(), frozenset()) is None
    assert show({"name": "ALEXFAKE'S FACTION", "members": ["AlexFake"]}, frozenset(), frozenset()) is None
    assert show({"name": "RiaFake's faction", "members": []}, frozenset(), people) is None
    # a faction, or a loose Cup entry, called just what a player is called
    assert show({"name": "RiaFake", "members": []}, frozenset(), people) is None
    assert show({"name": "§cAlex_Fake", "members": ["AlexFake"]}, frozenset(), frozenset()) is None
    # a name that merely has a word in common is the faction's own
    assert show({"name": "Ria's Fake Army", "members": ["AlexFake"]}, frozenset(), people) == "Ria's Fake Army"


def test_a_cup_entry_named_for_a_player_stays_out(tmp_path):
    board = copy.deepcopy(SCOREBOARD)
    board["data"]["PlayerScores"] += score_rows(("ev.cup", "TomFake", 7),
                                                ("ev.cup", "gold", 6, {"display": "§eGold Team"}))
    world = make_world(tmp_path, board)
    raw = public_board(world, tmp_path)[1].read_bytes()
    assert b"TomFake" not in raw and b'"Gold Team"' in raw and b"u00a7" not in raw


def test_ties_share_a_rank_as_on_the_board():
    rows = standings.rank([standings.Row("B", cup=5, land=5), standings.Row("A", cup=5, land=5), standings.Row("C")])
    assert standings.public_rows([asdict(r) for r in rows], frozenset(), frozenset()) == [
        {"rank": 1, "name": "A", "points": 60}, {"rank": 1, "name": "B", "points": 60},
        {"rank": 3, "name": "C", "points": 0}]
    # A tie on points alone goes to Cup, then kills, as on the board and in Discord; the public file keeps that rank.
    rows = standings.rank([standings.Row("Land", land=10, strength=10), standings.Row("Cup", cup=10)])
    assert standings.public_rows([asdict(r) for r in rows], frozenset(), frozenset()) == [
        {"rank": 1, "name": "Cup", "points": 40}, {"rank": 2, "name": "Land", "points": 40}]


def pacific(*when):
    return dt.datetime(*when, tzinfo=season_calendar.PACIFIC)


def utc(when):
    return when.astimezone(season_calendar.UTC).isoformat().replace("+00:00", "Z")


@pytest.mark.parametrize(("now", "closes"), [
    (pacific(2026, 11, 7, 17), "2026-11-09T03:00:00Z"),                 # the launch: the launch weekend's close first
    (pacific(2026, 11, 8, 19), "2026-11-16T03:00:00Z"),                 # at that close: week 1's
    (pacific(2026, 11, 14, 18), "2026-11-16T03:00:00Z"),                # the contract's example
    (pacific(2026, 11, 15, 18, 59, 59), "2026-11-16T03:00:00Z"),        # a second before
    (pacific(2026, 11, 15, 19), "2026-11-23T03:00:00Z"),                # at the close: the next week's
    (pacific(2026, 11, 16, 0), "2026-11-23T03:00:00Z"),                 # Monday
    (pacific(2027, 1, 24, 18, 59), "2027-01-25T03:00:00Z"),             # the finale's week
])
def test_week_closes_at_7_pm_pacific(now, closes):
    assert utc(standings.next_close(now)) == closes
    assert utc(standings.next_close(now.astimezone(season_calendar.UTC))) == closes


@pytest.mark.parametrize("now", [pacific(2027, 1, 24, 19), pacific(2027, 1, 25, 0), pacific(2027, 3, 14, 12)])
def test_no_close_after_the_last(now):
    assert standings.next_close(now) is None


def test_the_closes_are_the_calendars_and_the_launch_weekends():
    closes = standings.season_closes()
    assert closes[1:] == [when for when, what, _ in status.dates() if what == status.CLOSE]
    assert utc(closes[0]) == "2026-11-09T03:00:00Z"
    assert all(when.astimezone(season_calendar.PACIFIC).weekday() == 6 for when in closes)


def test_a_week_too_young_to_close_on_sunday_closes_the_sunday_after():
    friday = pacific(2026, 11, 13, 12)
    assert utc(standings.next_close(friday, friday)) == "2026-11-23T03:00:00Z"
    # Three days and more is old enough (close: MIN_WEEK_DAYS).
    thursday = pacific(2026, 11, 12, 19)
    assert utc(standings.next_close(thursday, thursday)) == "2026-11-16T03:00:00Z"


def test_the_board_gives_the_file_its_weeks_start(world, tmp_path):
    state, out = tmp_path / "state", tmp_path / "status" / "standings.json"
    friday = pacific(2026, 11, 13, 12)
    state.mkdir()
    (state / "week.json").write_text(json.dumps({**BASELINE, "start": friday.isoformat()}))
    assert standings.board(world, state, FakeRcon(), friday + dt.timedelta(hours=1), out) == 0
    assert json.loads(out.read_bytes())["week_closes"] == "2026-11-23T03:00:00Z"


def test_the_file_has_no_close_after_the_last(world, tmp_path):
    code, out, _ = public_board(world, tmp_path, now=pacific(2027, 1, 25, 0))
    assert code == 0 and json.loads(out.read_bytes())["week_closes"] is None


def test_last_weeks_table_keeps_a_players_name_out_too(world, tmp_path):
    """TomFake isn't in this row's members: only the roster from usercache can catch it."""
    state = tmp_path / "state"
    closed_week(state, rows=[{"rank": 1, "name": "TomFake", "points": 9, "members": []},
                             {"rank": 2, "name": "Red Monkeys", "points": 8, "members": []}])
    _, out, _ = public_board(world, tmp_path)
    assert [row["name"] for row in json.loads(out.read_bytes())["last_week"]["factions"]] == [None, "Red Monkeys"]


def test_an_unnamed_faction_is_called_one_thing_everywhere(world):
    party = next(p for p in standings.read_parties(world, standings.usernames(world)) if p.id == "p-lone")
    assert party.name == saved_world.faction_name("", "LoneFake") == "LoneFake" + saved_world.UNNAMED_PARTY
    assert standings.shown_name({"name": party.name}, frozenset(), frozenset({standings.name_key("LoneFake")})) is None
    line = news.faction_line([{"text": json.dumps({"name": party.name, "leader": "LoneFake"})}])
    assert line == "New faction: LoneFake's faction."   # no "led by" for one named after its leader
    assert "led by" in news.faction_line([{"text": json.dumps({"name": "Red", "leader": "LoneFake"})}])


def test_main_passes_the_file_on(world, tmp_path, monkeypatch):
    monkeypatch.delenv("STANDINGS_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(standings, "Docker", lambda folder: FakeRcon())
    monkeypatch.setattr(standings.season_calendar, "now", lambda: NOW)
    out, state = tmp_path / "status" / "standings.json", tmp_path / "state"
    assert standings.main(["board", str(world), "--state", str(state), "--docker", "d", "--out", str(out)]) == 0
    assert json.loads(out.read_bytes())["checked"] == "2026-11-15T02:00:00Z"
    out.unlink()
    assert standings.main(["board", str(world), "--state", str(state), "--docker", "d"]) == 0   # no --out, no file
    assert not out.exists()
    assert standings.main(["close", str(world), "--state", str(state), "--docker", "d", "--out", str(out)]) == 0
    assert json.loads(out.read_bytes())["last_week"] is not None


def test_the_script_writes_next_to_the_status_and_nothing_new_runs():
    script = (DEPLOY / "monkey-standings.sh").read_text()
    assert "STATUS_DIR=${STATUS_DIR:-/srv/monkey/status}\n" in script
    assert '--docker "$LIVE_DIR/docker" --out "$STATUS_DIR/standings.json"\n' in script
    assert script.count("--out") == 1   # never from show or preview, which change nothing
    # The same folder as the status's, with the same default.
    assert "$(setting STATUS_DIR /srv/monkey/status)" in (DEPLOY / "monkey-status.sh").read_text()
    # Both timers' services run as monkey, the status folder's owner, so the file can be replaced.
    for unit in ("monkey-standings.service", "monkey-standings-board.service", "monkey-status.service"):
        assert "User=monkey\n" in (DEPLOY / unit).read_text()
    assert (status.CLOSE_TIME.hour, status.CLOSE_TIME.minute) == (19, 0)   # monkey-standings.timer


def caddy_block(caddy, head):
    block = caddy[caddy.index(head):]
    return block[len(head):block.index("\n\t}")]


def test_caddy_serves_the_standings_as_it_serves_the_status():
    caddy = (DEPLOY / "Caddyfile").read_text()
    block = caddy_block(caddy, "handle /standings.json {")
    assert block == caddy_block(caddy, "handle /status.json {")
    assert "root * /srv/monkey/status" in block and "file_server" in block
    assert 'Access-Control-Allow-Origin "*"' in block and 'Cache-Control "public, max-age=60"' in block
    assert caddy.index("handle /standings.json {") < caddy.index("\thandle {\n")   # before the map's catch-all
