import copy
import datetime as dt
import gzip
import io
import json
import re
import shutil
import struct
import subprocess
import urllib.error
import uuid

import pytest

import events
import standings
from repo import REPO

FILES = standings.datapack_files()
FUNCTIONS = {k for k in FILES if k.endswith(".mcfunction")}
PT = dt.timezone(dt.timedelta(hours=-7))
SUNDAY = dt.datetime(2026, 11, 1, 19, 0, tzinfo=PT)
WEBHOOK = "https://discord.com/api/webhooks/1/made-up-secret-token"


# ---------------------------------------------------------------- a made-up world


class Ints(list):
    """An NBT int array (how Minecraft saves a UUID)."""


class Long(int):
    pass


def nbt(value, name="") -> bytes:
    """A tiny NBT writer: dicts, lists, strings, ints (TAG_Int), Long and Ints."""
    def tag(v) -> int:
        return (10 if isinstance(v, dict) else 11 if isinstance(v, Ints) else 9 if isinstance(v, list)
                else 8 if isinstance(v, str) else 4 if isinstance(v, Long) else 3)

    def payload(v) -> bytes:
        if isinstance(v, dict):
            return b"".join(bytes([tag(x)]) + string(k) + payload(x) for k, x in v.items()) + b"\x00"
        if isinstance(v, Ints):
            return struct.pack(f">i{len(v)}i", len(v), *v)
        if isinstance(v, list):
            return bytes([tag(v[0]) if v else 0]) + struct.pack(">i", len(v)) + b"".join(payload(x) for x in v)
        if isinstance(v, str):
            return string(v)
        return struct.pack(">q" if isinstance(v, Long) else ">i", v)

    def string(s: str) -> bytes:
        raw = s.encode()
        return struct.pack(">H", len(raw)) + raw
    return bytes([10]) + string(name) + payload(value)


PLAYERS = {name: str(uuid.uuid5(uuid.NAMESPACE_DNS, name)) for name in
           ("AlexFake", "SamFake", "RiaFake", "TomFake", "LoneFake")}


def ints(name: str) -> Ints:
    return Ints(struct.unpack(">4i", uuid.UUID(PLAYERS[name]).bytes))


def person(name: str, username: str | None = None) -> dict:
    return {"uuid": ints(name), "username": username or name, "rank": "MEMBER"}


def claim_file(chunks: dict[str, int]) -> dict:
    return {"username": "x", "confirmedActivity": Long(0), "dimensions": {
        dim: {"claims": [{"state": {"subConfigIndex": -1}, "positions": [{"x": i, "z": 0} for i in range(n)]}]}
        for dim, n in chunks.items()}}


def scores(*rows):
    out = []
    for objective, name, score, *extra in rows:
        # 26.3 leaves Score out when it is 0
        out.append({"Objective": objective, "Name": name} | ({"Score": score} if score else {})
                   | (extra[0] if extra else {}))
    return out


SCOREBOARD = {"DataVersion": 5023, "data": {"PlayerScores": scores(
    ("ev.cup", "red", 30, {"display": "Red Monkeys"}),
    ("ev.cup", "blue", 10, {"display": {"text": "Blue", "extra": [" Herons"]}}),
    ("ev.cup", "green", 5, {"display": "Green Team"}),
    ("ev.cup", "#total", 99),
    (events.LEVEL, "AlexFake", 4), (events.LEVEL, "SamFake", 3), (events.LEVEL, "RiaFake", 5),
    (events.LEVEL, "TomFake", 3), (events.LEVEL, "LoneFake", -2),
    ("ev.strength", "TomFake", 1),   # Tom is in the arena: his own Strength is 1, held at +3 in there
    ("st.kills", "AlexFake", 7), ("st.kills", "SamFake", 2), ("st.kills", "RiaFake", 10),
    ("st.kills", "LoneFake", 1), ("st.bounty", "SamFake", 1))}}
BASELINE = {"start": "2026-10-25T19:00:00-07:00", "kills": {"AlexFake": 5, "RiaFake": 4}, "bounty": {}}


def make_world(root, scoreboard=SCOREBOARD):
    world = root / "server" / "world"
    opac = world / "data" / "openpartiesandclaims"
    for folder in ("parties", "player-claims", "player-configs"):
        (opac / folder).mkdir(parents=True)
    (world / "data" / "minecraft").mkdir(parents=True)
    (world / "data" / "minecraft" / "scoreboard.dat").write_bytes(gzip.compress(nbt(scoreboard)))
    parties = {"p-red": ("AlexFake", ["SamFake"]), "p-blue": ("RiaFake", ["TomFake"]), "p-lone": ("LoneFake", [])}
    for pid, (owner, members) in parties.items():
        data = {"owner": person(owner), "confirmedActivity": Long(1), "invites": [], "allies": [],
                # the party file still has Sam's old name; usercache has the new one
                "members": [person(m, "OldSam" if m == "SamFake" else None) for m in members]}
        (opac / "parties" / f"{pid}.nbt").write_bytes(nbt(data))
    for owner, name in (("AlexFake", "Red Monkeys"), ("RiaFake", "Blue Herons")):
        (opac / "player-configs" / f"{PLAYERS[owner]}.toml").write_text(
            f'[playerConfig]\n\t[playerConfig.parties]\n\t\tname = "{name}"\n\t\tshareLocationWithParty = true\n')
    for name, chunks in (("AlexFake", {"minecraft:overworld": 4}),
                         ("SamFake", {"minecraft:overworld": 2, "minecraft:the_nether": 1}),
                         ("RiaFake", {"minecraft:overworld": 4}), ("LoneFake", {"minecraft:overworld": 1})):
        (opac / "player-claims" / f"{PLAYERS[name]}.nbt").write_bytes(nbt(claim_file(chunks)))
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
    board["data"]["PlayerScores"].extend(scores(("st.bounty", "alexfake", 1)))
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
    assert commands[-1] == "function realms:standings/publish"
    for c in commands:
        assert len(c.encode()) <= standings.RCON_LIMIT
        assert c.isascii() and "\n" not in c and not c.startswith("-")
    assert commands[0].startswith("data modify storage realms:standings week set value {")
    assert commands[1].startswith("data modify storage realms:standings last set value {")
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


class FakeRcon:
    def __init__(self, fail=0):
        self.sent, self.fail = [], fail

    def __call__(self, command):
        if self.fail:
            self.fail -= 1
            raise standings.RconError("the server is down")
        self.sent.append(command)
        return "ok"


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
    assert rcon.sent[-1] == "function realms:standings/announce"
    assert rcon.sent[-2] == "function realms:standings/publish"
    assert "kills 0" in rcon.sent[0] and "kills 4" in rcon.sent[1]
    [(url, kind, body)] = discord.posts
    assert url == WEBHOOK and kind == "application/json"
    assert body["allowed_mentions"] == {"parse": []}
    assert "Red Monkeys" in body["content"] and len(body["content"]) <= 2000
    assert "week of Sun 25 Oct to Sun 1 Nov" in body["content"]
    first = capsys.readouterr()
    assert "board updated and announced in chat" in first.out
    # run again (a retry, a re-run): nothing is closed or posted twice
    assert standings.close(world, state, rcon, SUNDAY + dt.timedelta(minutes=20), WEBHOOK, discord) == 0
    assert len(list((state / "weeks").iterdir())) == 1 and len(discord.posts) == 1
    assert rcon.sent.count("function realms:standings/announce") == 1
    out = capsys.readouterr()
    # and it says so, not that it announced again
    assert "already announced in chat" in out.out and "and announced in chat" not in out.out
    assert "made-up-secret-token" not in first.out + first.err + out.out + out.err


def test_a_failed_post_or_board_is_retried_without_closing_again(world, tmp_path, capsys):
    state = tmp_path / "state"
    rcon, discord = FakeRcon(fail=1), FakeDiscord(fail=1)
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


def test_main_show(world, capsys):
    assert standings.main(["show", str(world)]) == 0
    assert "Red Monkeys" in capsys.readouterr().out


# ---------------------------------------------------------------- the data pack


def fn(path: str) -> str:
    return FILES[f"{standings.FN}/{path}.mcfunction"]


def test_committed_pack_matches_the_generator():
    assert standings.differences(REPO) == [], "run python tools/standings.py pack"


def test_pack_uses_the_events_pack_format():
    pack = json.loads(FILES["pack.mcmeta"])["pack"]
    assert pack["min_format"] == pack["max_format"] == events.DATA_FORMAT


def test_every_called_function_exists():
    for path, body in FILES.items():
        for name in re.findall(rf"function {standings.NS}:([\w/]+)", body):
            assert f"data/{standings.NS}/function/{name}.mcfunction" in FUNCTIONS, f"{path} calls {name}"


def test_macro_lines_are_marked_and_marked_lines_are_macros():
    for path in FUNCTIONS:
        for line in FILES[path].splitlines():
            if not line.startswith("#"):
                assert ("$(" in line) == line.startswith("$"), f"{path}: {line}"


def test_json_files_parse():
    for path, body in FILES.items():
        if path.endswith((".json", ".mcmeta")):
            json.loads(body)


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
    assert "tellraw @s {\"nbt\":\"board\",\"storage\":\"realms:standings\",\"interpret\":true}" in fn("use")
    assert "data modify entity @s text set from storage realms:standings board" in fn("refresh")
    assert "scoreboard players add #board st.ver 1" in fn("publish")
    assert "unless score @s st.ver = #board st.ver run function realms:standings/refresh" in fn("second")


def test_help_lists_only_real_functions():
    assert fn("help").count("suggest_command") == len(standings.HELP)


# ---------------------------------------------------------------- the VPS scripts


DEPLOY = REPO.root / "deploy"
SCRIPTS = ["realms-standings.sh", "install-standings.sh"]
UNITS = ["realms-standings.service", "realms-standings.timer", "realms-standings-board.service",
         "realms-standings-board.timer"]


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


def test_units_run_the_script_as_realms_on_sunday_evening():
    service = (DEPLOY / "realms-standings.service").read_text()
    assert "User=realms" in service and "ExecStart=/bin/sh /srv/realms/repo/deploy/realms-standings.sh close" in service
    assert "OnCalendar=Sun *-*-* 19:00:00 America/Los_Angeles" in (DEPLOY / "realms-standings.timer").read_text()
    board = (DEPLOY / "realms-standings-board.service").read_text()
    assert "ExecStart=/bin/sh /srv/realms/repo/deploy/realms-standings.sh board" in board
    script = (DEPLOY / "realms-standings.sh").read_text()
    assert "flock -w 1800 9" in script and "export STANDINGS_WEBHOOK_URL" in script
    assert "STANDINGS_WEBHOOK_URL=" in (DEPLOY / "realms-deploy.env.example").read_text()
