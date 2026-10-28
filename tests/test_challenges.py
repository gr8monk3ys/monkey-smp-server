import datetime as dt
import json
import re

import pytest

import challenges
import rcon
import rules
import season
import site_links
import wardrobe
from repo import REPO

UTC = dt.timezone.utc  # noqa: UP017 (the module under test keeps to 3.10)
FN = "data/realms/function/challenges"


def at(text: str) -> dt.datetime:
    return rcon.parse_time(text)


def pacific(*args) -> dt.datetime:
    return dt.datetime(*args, tzinfo=challenges.PACIFIC)


# ---------------------------------------------------------------- the pool


def test_the_pool_is_well_formed():
    ids = [c["id"] for c in challenges.POOL]
    assert len(ids) == len(set(ids))
    for c in challenges.POOL:
        assert re.fullmatch(r"[a-z]+", c["id"]), c["id"]
        assert c["kind"] in challenges.KINDS
        assert 0 < len(c["name"]) <= challenges.NAME_MAX, c["name"]
        assert c["goal"] > 0 and c["about"]
        assert [way for way in challenges.WAYS if way in c] != [] and sum(way in c for way in challenges.WAYS) == 1
    for kind in challenges.KINDS:
        # Two or more of each, so no kind repeats the same challenge two weeks running.
        assert len(challenges.of_kind(kind)) >= 2, kind


def test_the_rotation_is_one_of_each_kind_and_never_repeats_a_week_running():
    for week in range(0, 60):
        this, last = challenges.picks(week), challenges.picks(week - 1) if week else None
        assert set(this) == set(challenges.KINDS)
        for kind, c in this.items():
            assert c["kind"] == kind
            assert c is challenges.of_kind(kind)[week % len(challenges.of_kind(kind))]
            if last:
                assert c is not last[kind]
    assert challenges.picks(0) == {kind: challenges.of_kind(kind)[0] for kind in challenges.KINDS}
    assert challenges.picks(-1) == challenges.picks(0)
    # The same week always gives the same three.
    assert [challenges.picks(w) for w in range(30)] == [challenges.picks(w) for w in range(30)]


def test_a_season_shows_most_of_the_pool():
    seen = {c["id"] for week in range(1, 13) for c in challenges.picks(week).values()}
    assert seen == {c["id"] for c in challenges.POOL}


def run_pick(week: int) -> dict[str, int]:
    """Runs pick.mcfunction the way the server would, for one #week."""
    scores = {"#week": week}
    for line in datapack(f"{FN}/pick.mcfunction").splitlines():
        if line.startswith("#"):
            continue
        if m := re.fullmatch(r"scoreboard players operation (#\w+) rc\.week = (#\w+) rc\.week", line):
            scores[m[1]] = scores[m[2]]
        elif m := re.fullmatch(r"execute if score (#\w+) rc\.week matches \.\.-1 run "
                               r"scoreboard players set (#\w+) rc\.week 0", line):
            if scores[m[1]] <= -1:
                scores[m[2]] = 0
        elif m := re.fullmatch(r"scoreboard players set (#\w+) rc\.week (\d+)", line):
            scores[m[1]] = int(m[2])
        elif m := re.fullmatch(r"scoreboard players operation (#\w+) rc\.week %= (#\w+) rc\.week", line):
            scores[m[1]] %= scores[m[2]]
        else:
            raise AssertionError(line)
    return {kind: scores[f"#{kind}"] for kind in challenges.KINDS}


def datapack(path: str) -> str:
    return wardrobe.datapack_files()[path]


@pytest.mark.parametrize("week", [-1, 0, 1, 2, 3, 4, 5, 9, 10, 11, 12, 13, 40])
def test_the_server_picks_what_the_schedule_says(week):
    indexes = run_pick(week)
    show = datapack(f"{FN}/lines.mcfunction")
    second = datapack(f"{FN}/second.mcfunction")
    for kind, c in challenges.picks(week).items():
        assert challenges.of_kind(kind)[indexes[kind]] is c
        i = indexes[kind]
        assert (f"execute if score #{kind} rc.week matches {i} run function realms:challenges/line/{c['id']}"
                in show.splitlines())
        assert (f"execute if score #{kind} rc.week matches {i} as @a run function realms:challenges/progress/"
                f"{c['id']}" in second.splitlines())


def test_the_schedule_command_prints_the_weeks():
    out = challenges.schedule(0, 13).splitlines()
    assert len(out) == 13
    assert out[0].startswith("week 0   from launch, 21 Nov 2026")
    assert out[1].startswith("week 1   from Mon 23 Nov 2026")
    for week, line in enumerate(out):
        for c in challenges.picks(week).values():
            assert c["name"] in line


# ---------------------------------------------------------------- the clock


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
    assert challenges.week_at(when) == week
    assert challenges.week_at(when.astimezone(UTC)) == week


def test_the_week_turns_on_pacific_time_through_daylight_saving():
    # Standard time: Sunday 23:59:59 PST is 07:59:59 UTC on Monday.
    assert challenges.week_at(at("2026-11-23T07:59:59Z")) == 0
    assert challenges.week_at(at("2026-11-23T08:00:00Z")) == 1
    # Daylight time from 14 March 2027: Monday 15 March starts at 07:00 UTC, not 08:00.
    assert challenges.week_at(at("2027-03-15T06:59:59Z")) == 16
    assert challenges.week_at(at("2027-03-15T07:00:00Z")) == 17
    assert challenges.week_at(at("2027-03-15T07:30:00Z")) == 17


def test_week_starts_are_mondays():
    assert challenges.WEEK_ONE.weekday() == 0
    for week in range(1, 30):
        assert challenges.week_start(week).weekday() == 0
        assert challenges.week_at(pacific(*challenges.week_start(week).timetuple()[:3])) == week
    assert challenges.week_start(0) == dt.date(2026, 11, 21)


# ---------------------------------------------------------------- the launch weekend


def test_the_launch_weekend_is_saturday_5_pm_to_the_end_of_sunday_pacific():
    assert challenges.LAUNCH.astimezone(challenges.PACIFIC) == pacific(2026, 11, 21, 17, 0)
    assert challenges.LAUNCH_END.astimezone(challenges.PACIFIC) == pacific(2026, 11, 23, 0, 0)
    assert at("2026-11-22T01:00:00Z") == challenges.LAUNCH
    assert challenges.LAUNCH_SECONDS == 31 * 3600 == 111600
    assert challenges.week_at(challenges.LAUNCH_END) == 1   # the window ends as week 1 starts


def test_seconds_left_in_the_launch_weekend():
    assert challenges.founder_left(challenges.LAUNCH) == challenges.LAUNCH_SECONDS
    assert challenges.founder_left(at("2026-11-23T07:59:59Z")) == 1
    assert challenges.founder_left(at("2026-11-23T07:59:59.5Z")) == 1   # rounds up: never ends early
    assert challenges.founder_left(at("2026-11-23T08:00:00Z")) == 0
    assert challenges.founder_left(at("2026-12-01T00:00:00Z")) == 0


def test_send_skips_a_stopped_server_and_reports_a_refusal():
    when = at("2026-11-23T08:00:30Z")
    log = []
    assert challenges.send(rcon.Recorder(running=False), when, log.append) == 0
    assert log == ["server not running: nothing sent (the next hour catches up)"]
    server = rcon.Recorder()
    assert challenges.send(server, when, log.append) == 0 and server.sent == challenges.commands(when)
    refusing = rcon.Recorder({"function realms:challenges/": "Unknown function realms:challenges/sync"})
    assert challenges.send(refusing, when, log.append) == 1
    assert refusing.sent == challenges.commands(when)[1:]   # the refused one is logged; the rest still go


def test_the_hourly_commands():
    assert challenges.commands(at("2026-11-22T01:00:30Z")) == [
        "function realms:challenges/sync {week:0}", "function realms:wardrobe/founder/sync {seconds:111570}"]
    assert challenges.commands(at("2026-11-23T08:00:30Z")) == [
        "function realms:challenges/sync {week:1}", "function realms:wardrobe/founder/sync {seconds:0}"]
    # A day after the window there is nothing left to keep in step: only the week.
    assert challenges.commands(at("2026-11-24T07:59:59Z"))[1:] == ["function realms:wardrobe/founder/sync {seconds:0}"]
    assert challenges.commands(at("2026-11-24T08:00:00Z")) == ["function realms:challenges/sync {week:1}"]
    assert challenges.commands(at("2027-01-04T08:00:30Z")) == ["function realms:challenges/sync {week:7}"]
    assert challenges.main(["commands", "--at", "2026-11-30T08:00:00Z"]) == 0


def founder(name: str) -> list[str]:
    return datapack(f"data/realms/function/wardrobe/founder/{name}.mcfunction").splitlines()


def test_the_launch_opens_the_window_for_season_one_only():
    launch = rules.rules_files()["data/realms/function/rules/launch.mcfunction"].splitlines()
    assert "execute unless score #launched rw.day matches 1 run function realms:wardrobe/founder/open" in launch
    opening = founder("open")
    guard = next(i for i, line in enumerate(opening) if not line.startswith("#"))
    assert opening[guard].startswith("execute unless score #season rw.day matches 1 run return run tellraw @s ")
    assert "scoreboard players set #founder.open rw.day 1" in opening
    assert "scoreboard players set #founder.auto rw.day 1" in opening
    # It closes on its own after the launch weekend's length of game time, even if nothing on the VPS runs.
    assert "execute store result score #founder.until rw.day run time query gametime" in opening
    assert f"scoreboard players add #founder.until rw.day {challenges.LAUNCH_SECONDS * 20}" in opening
    for name in ("open", "open_for"):
        assert founder(name)[[i for i, line in enumerate(founder(name)) if not line.startswith("#")][0]] == \
            opening[guard]


def test_ten_minutes_online_while_the_window_is_open_earns_the_circlet():
    second = founder("second")
    body = [line for line in second if not line.startswith("#")]
    assert body[0] == "execute unless score #founder.open rw.day matches 1 run return 0"
    assert ("execute if score #founder.now rw.day >= #founder.until rw.day run return run "
            "function realms:wardrobe/founder/close") in body
    assert "scoreboard players add @a rw.launchtime 1" in body
    assert f"scoreboard players set @a[scores={{rw.launchtime={challenges.FOUNDER_MINUTES * 60}..}}] rw.launch 1" \
        in body
    # Counted for whoever is online, so players who join after the launch hour count the same.
    assert body.index("scoreboard players add @a rw.launchtime 1") > body.index(
        "execute unless score #founder.open rw.day matches 1 run return 0")
    wardrobe_second = datapack("data/realms/function/wardrobe/second.mcfunction").splitlines()
    assert "function realms:wardrobe/founder/second" in wardrobe_second


def test_the_wall_clock_moves_only_a_window_the_launch_opened():
    sync = [line for line in founder("sync") if not line.startswith("#")]
    assert sync[0] == "execute unless score #founder.auto rw.day matches 1 run return 0"
    assert "$scoreboard players set #founder.left rw.day $(seconds)" in sync
    assert ("execute if score #founder.left rw.day matches ..0 run return run function realms:wardrobe/founder/close"
            in sync)
    assert "scoreboard players operation #founder.left rw.day *= #second rw.const" in sync
    assert "scoreboard players set #second rw.const 20" in datapack("data/realms/function/wardrobe/load.mcfunction")
    # Staff's open_for is manual: the wall clock leaves it alone. close stops both.
    assert "scoreboard players set #founder.auto rw.day 0" in founder("open_for")
    assert "$scoreboard players set #founder.until rw.day $(hours)" in founder("open_for")
    assert "scoreboard players operation #founder.until rw.day *= #hour rw.const" in founder("open_for")
    close = founder("close")
    assert "scoreboard players set #founder.open rw.day 0" in close
    assert "scoreboard players set #founder.auto rw.day 0" in close


def test_the_launch_weekend_score_carries_and_its_counter_does_not():
    assert "rw.launchtime" in season.NOT_CARRIED
    assert "rw.launch" not in season.NOT_CARRIED and "rw.challenges" not in season.NOT_CARRIED
    load = datapack("data/realms/function/wardrobe/load.mcfunction")
    for objective in ("rw.launch", "rw.launchtime", "rw.challenges"):
        assert f"scoreboard objectives add {objective} dummy" in load


# ---------------------------------------------------------------- the week on the server


def test_sync_starts_a_new_week_once_and_keeps_a_fresh_world():
    sync = [line for line in datapack(f"{FN}/sync.mcfunction").splitlines() if not line.startswith("#")]
    assert sync == [
        "$execute if score #week rc.week matches $(week) run return 0",
        "execute unless score #week rc.week matches -1 run function realms:challenges/restart",
        "$scoreboard players set #week rc.week $(week)",
        "function realms:challenges/pick",
    ]
    load = datapack(f"{FN}/load.mcfunction")
    # Only a world with no week yet gets -1; a restart keeps the week it had.
    assert ("execute unless score #week rc.week matches -2147483648.. run scoreboard players set #week rc.week -1"
            in load.splitlines())
    assert "function realms:challenges/load" in datapack("data/realms/function/wardrobe/load.mcfunction")


def test_a_new_week_clears_every_challenge_score_and_nothing_else():
    restart = datapack(f"{FN}/restart.mcfunction").splitlines()
    cleared = {line.split()[-1] for line in restart if line.startswith("scoreboard players reset * ")}
    made = {o for o, _ in challenges.objectives()}
    assert cleared == made - {"challenges", "rc.week", "rc.seen"}
    for c in challenges.POOL:
        assert f"rc.{c['id']}.done" in cleared
        assert {o for o, _, _ in challenges.counters(c)} <= cleared
    assert {"rc.days", "rc.lastday", *(f"rc.{k}" for k in challenges.KINDS)} <= cleared
    assert not any(o.startswith("rw.") for o in cleared)   # the challenges done, and the skins, stay
    # Events from the restart on count for the event challenge.
    assert "scoreboard players operation #firstevent rc.week = #event ev.state" in restart
    assert "scoreboard players add #firstevent rc.week 1" in restart


def test_challenge_scores_are_never_carried_to_the_next_season():
    # tools/season.py carries rw.* only.
    assert all(o.startswith("rc.") or o == "challenges" for o, _ in challenges.objectives())


def test_the_launch_clears_test_play():
    launch = rules.rules_files()["data/realms/function/rules/launch.mcfunction"].splitlines()
    assert "function realms:challenges/launch" in launch
    clear = datapack(f"{FN}/launch.mcfunction").splitlines()
    assert "function realms:challenges/restart" in clear
    # Challenges done and Founder's Circlet earned before Season I's launch were test play, however many weeks
    # the timer counted before it. A later season's launch keeps the carried count, and a launch run again by
    # mistake wipes nothing: #launched is set after the first.
    for objective in ("rw.challenges", "rw.challenges.seen", "rw.launch", "rw.launch.seen", "rw.launchtime"):
        assert ("execute if score #season rw.day matches 1 unless score #launched rw.day matches 1 run "
                f"scoreboard players reset * {objective}") in clear
    assert not [line for line in clear if "reset * rw." in line and "#season rw.day matches 1 " not in line]
    assert clear[-1] == "scoreboard players set #launched rw.day 1"
    # rules/launch opens the window first, so the reset clears only the minutes from before it. It reads the same
    # score before it opens Founder's Circlet's window, so only the first launch opens it.
    opening = "execute unless score #launched rw.day matches 1 run function realms:wardrobe/founder/open"
    assert launch.index(opening) < launch.index("function realms:challenges/launch")


# ---------------------------------------------------------------- no farming


ALLOWED_STATS = {"fish_caught", "animals_bred", "traded_with_villager", "enchant_item", "raid_win"}


def test_stat_challenges_use_only_stats_that_take_real_play():
    """No movement (an AFK water stream, a boat, a minecart or a horse in a loop counts it), no time online,
    and nothing about other players: kills, deaths or damage."""
    for c in challenges.POOL:
        for stat in c.get("stat", []):
            assert stat in ALLOWED_STATS, stat
            assert not stat.endswith("_one_cm") and "time" not in stat and "player" not in stat


def test_mining_counts_blocks_mined_minus_the_same_blocks_placed():
    for c in challenges.POOL:
        if "mine" not in c:
            continue
        counted = challenges.counters(c)
        mined = [crit.split(":", 1)[1] for _, crit, sign in counted if sign > 0]
        placed = [crit.split(":", 1)[1] for _, crit, sign in counted if sign < 0]
        assert all(crit.startswith("minecraft.mined:") for _, crit, sign in counted if sign > 0)
        assert all(crit.startswith("minecraft.used:") for _, crit, sign in counted if sign < 0)
        assert mined == placed == [f"minecraft.{b}" for b in c["mine"]]
        progress = datapack(f"{FN}/progress/{c['id']}.mcfunction")
        for objective, _, sign in counted:
            assert f"@s rc.{c['kind']} {'+=' if sign > 0 else '-='} @s {objective}" in progress
        assert f"execute if score @s rc.{c['kind']} matches ..-1 run scoreboard players set @s rc.{c['kind']} 0" \
            in progress


def test_kill_challenges_never_count_players():
    for c in challenges.POOL:
        if "kill" not in c:
            continue
        assert "player" not in c["kill"]
        tag = json.loads(datapack(f"data/realms/tags/entity_type/challenges/{c['id']}.json"))
        ids = [v if isinstance(v, str) else v["id"] for v in tag["values"]]
        assert "minecraft:player" not in ids
        assert set(ids) >= {f"minecraft:{m}" for m in c["kill"]}
        optional = [v for v in tag["values"] if isinstance(v, dict)]
        assert all(v["required"] is False for v in optional)
        advancement = json.loads(datapack(f"data/realms/advancement/challenges/{c['id']}.json"))
        criterion = advancement["criteria"]["kill"]
        assert criterion["trigger"] == "minecraft:player_killed_entity"
        assert criterion["conditions"]["entity"] == {
            "type": "minecraft:entity_properties", "entity": "this",
            "predicate": {"minecraft:entity_type": f"#realms:challenges/{c['id']}"}}


def test_loot_counts_a_structure_chest_once_from_any_table():
    loot = next(c for c in challenges.POOL if c.get("loot"))
    advancement = json.loads(datapack(f"data/realms/advancement/challenges/{loot['id']}.json"))
    assert len(advancement["requirements"]) == 1   # any one criterion fires it (OR)
    assert set(advancement["requirements"][0]) == set(advancement["criteria"])
    tables = [c["conditions"]["loot_tables"] for c in advancement["criteria"].values()]
    assert all(t.startswith("minecraft:chests/") for t in tables)
    assert len(tables) == len(set(tables)) == len(challenges.LOOT_TABLES)
    assert "minecraft:chests/spawn_bonus_chest" not in tables


def test_rewards_count_one_and_take_the_advancement_back():
    data = wardrobe.datapack_files()
    for path, text in data.items():
        if path.startswith("data/realms/advancement/challenges/"):
            reward = json.loads(text)["rewards"]["function"]
            name = path.removeprefix("data/realms/advancement/").removesuffix(".json")
            body = data[f"data/{reward.replace(':', '/function/', 1)}.mcfunction"]
            assert f"advancement revoke @s only realms:{name}" in body


def test_visits_are_checked_only_while_the_challenge_is_on():
    for c in challenges.POOL:
        for group, structures in c.get("visit", {}).items():
            advancement = json.loads(datapack(f"data/realms/advancement/challenges/{c['id']}/{group}.json"))
            player = advancement["criteria"]["visit"]["conditions"]["player"]
            assert player["type"] == "minecraft:all_of"
            week, flag, place = player["terms"]
            index = challenges.of_kind(c["kind"]).index(c)
            assert week["type"] == "minecraft:int_value_check"
            assert week["test"] == {"min": index, "max": index}
            assert week["value"] == {"type": "minecraft:score", "score": "rc.week",
                                     "target": {"type": "minecraft:fixed", "name": f"#{c['kind']}"}}
            assert flag["type"] == "minecraft:inverted"
            assert flag["term"] == {"type": "minecraft:entity_scores", "entity": "this",
                                    "scores": {f"rc.{c['id']}.{group}": {"min": 1}}}
            assert place["predicate"] == {"minecraft:location": {"structures": [f"minecraft:{s}" for s in structures]}}
            assert len(c["visit"]) >= c["goal"]


def test_advancements_use_the_26_condition_shapes():
    """26.x reads a condition's kind from "type", takes one condition (not a list) per criterion field, and keys
    entity predicates as components; any pre-26 shape fails the whole datapack load (seen in a boot)."""
    old_keys = {"condition", "loot_table", "range", "location", "type_specific"}

    def walk(node, path):
        if isinstance(node, dict):
            assert not old_keys & set(node), f"{path}: pre-26 key in {sorted(old_keys & set(node))}"
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")

    for path, text in wardrobe.datapack_files().items():
        if path.startswith("data/realms/advancement/challenges/"):
            advancement = json.loads(text)
            walk(advancement, path)
            for criterion in advancement["criteria"].values():
                for field in ("player", "entity"):
                    assert not isinstance(criterion.get("conditions", {}).get(field), list), path


def test_events_count_only_from_this_week():
    event = next(c for c in challenges.POOL if c.get("event"))
    progress = datapack(f"{FN}/progress/{event['id']}.mcfunction")
    assert f"execute if score @s ev.seen >= #firstevent rc.week run scoreboard players set @s rc.{event['kind']} 1" \
        in progress


def test_each_challenge_finishes_once_a_week():
    for c in challenges.POOL:
        progress = datapack(f"{FN}/progress/{c['id']}.mcfunction")
        assert (f"execute if score @s rc.{c['kind']} matches {c['goal']}.. unless score @s rc.{c['id']}.done "
                f"matches 1 run function realms:challenges/done/{c['id']}") in progress
        done = datapack(f"{FN}/done/{c['id']}.mcfunction").splitlines()
        assert f"scoreboard players set @s rc.{c['id']}.done 1" in done
        assert done.count("scoreboard players add @s rw.challenges 1") == 1


# ---------------------------------------------------------------- the pack as a whole


def test_every_function_the_wardrobe_pack_calls_exists():
    data = wardrobe.datapack_files()
    defined = {p.removeprefix("data/realms/function/").removesuffix(".mcfunction")
               for p in data if p.startswith("data/realms/function/")}
    other_packs = {p.removeprefix("data/realms/function/").removesuffix(".mcfunction")
                   for p in rules.rules_files() if p.startswith("data/realms/function/")}
    called = set()
    for path, text in data.items():
        if path.endswith(".mcfunction"):
            called |= set(re.findall(r"function realms:([a-z0-9_/.]+)", text))
        elif "/advancement/" in path:
            called.add(json.loads(text)["rewards"]["function"].removeprefix("realms:"))
    assert called - defined - other_packs == set()


def test_the_trigger_is_enabled_and_opens_the_page():
    second = datapack(f"{FN}/second.mcfunction").splitlines()
    assert "scoreboard players enable @a challenges" in second
    use = datapack(f"{FN}/use.mcfunction").splitlines()
    assert use == ["# Runs as a player who just used /trigger challenges: the wardrobe's challenges page.",
                   "function realms:wardrobe/menu_challenges", "scoreboard players set @s challenges 0",
                   "scoreboard players enable @s challenges"]


def test_the_weekly_hello_lists_the_three():
    greet = datapack(f"{FN}/greet.mcfunction").splitlines()
    assert "scoreboard players operation @s rc.seen = #week rc.week" in greet
    assert "function realms:challenges/lines" in greet
    assert '"command":"/trigger challenges"' in greet[2]


# ---------------------------------------------------------------- the VPS


def test_the_week_script_sends_the_commands_hourly():
    script = (REPO.root / "deploy" / "realms-week.sh").read_bytes()
    assert b"\r" not in script and script.isascii()
    text = script.decode()
    assert text.startswith("#!/bin/sh\n")
    # A timed job: it names its tool, and deploy/lib.sh's timed_job runs `commands` and `send`.
    assert "JOB_TOOL=challenges.py\n" in text and text.endswith('\ntimed_job "$@"\n')
    lib = (REPO.root / "deploy" / "lib.sh").read_text(encoding="utf-8")
    assert 'python3 -B "$lib_tool" commands "$@"' in lib
    # Python sends and reads the answers (tools/rcon.py); the shell keeps no copy of the refusals.
    assert '"$lib_tool" send "$@" --docker "$LIVE_DIR/docker"' in lib and "Unknown function" not in text + lib
    assert "--check" in text and "--install" in text
    # Its three settings are read without sourcing the env file (which holds the webhooks), and never a password.
    assert "realms-deploy.env" in text and "realms-deploy.env" in lib
    assert re.findall(r"^\s*(?:\.|source)\s.*", text, re.M) == ['. "$(dirname -- "$0")/lib.sh"']
    assert "WEBHOOK_URL" not in text and "rcon.password" not in text and "RCON_PASSWORD" not in text
    service = (REPO.root / "deploy" / "realms-week.service").read_text(encoding="utf-8")
    assert "User=realms" in service and "ExecStart=/bin/sh /srv/realms/repo/deploy/realms-week.sh" in service
    timer = (REPO.root / "deploy" / "realms-week.timer").read_text(encoding="utf-8")
    assert "Persistent=true" in timer
    assert re.search(r"^OnCalendar=\*-\*-\* \*:00:30$", timer, re.M)
    for unit in ("realms-week.service", "realms-week.timer"):
        assert b"\r" not in (REPO.root / "deploy" / unit).read_bytes()


def test_the_launch_weekend_starts_at_the_sites_launch_time():
    # Season I's launch time is in site/config.js (LAUNCH_AT, the countdown) and here (the Founder's Circlet
    # window): moving one without the other would open the window at the wrong time.
    config = (site_links.site() / "config.js").read_text(encoding="utf-8")
    assert site_links.launch_time(site_links.load_links(config)["LAUNCH_AT"]) == challenges.LAUNCH
