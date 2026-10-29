import datetime as dt
import json
import re

import pytest
from fake_world import FakeWorld

import datapacks
import drops
import omens
import rcon
import saved_world
import season_calendar
import standings
from repo import REPO

FILES = omens.datapack_files()
FUNCTIONS = {k for k in FILES if k.endswith(".mcfunction")}
SECRET = "123456789.987654321"
KEY = (("om", "#key1", 123456789), ("om", "#key2", 987654321))
SPAWN = (-80.0, 416.0)


def pacific(*args) -> dt.datetime:
    return dt.datetime(*args, tzinfo=season_calendar.PACIFIC)


def fn(path: str) -> str:
    return FILES[f"{omens.FN}/{path}.mcfunction"]


def make_world(root, *rows, border=True):
    fake = FakeWorld(root / "world")
    if border:
        fake.border(saved_world.OVERWORLD, *SPAWN, 2500.0)
    (fake.path / "data" / "openpartiesandclaims" / "player-claims").mkdir(parents=True)
    if rows:
        fake.scores(*rows)
    return fake.path


def first_evening(secret=SECRET, week=1) -> omens.Evening:
    return omens.plan(secret, week)[0]


# ---------------------------------------------------------------- the plan


def test_a_week_has_two_weekday_evenings_starting_between_6_and_850_pm():
    for week in range(1, 60):
        evenings = omens.plan(SECRET, week)
        assert len(evenings) == omens.PER_WEEK
        days = [e.day for e in evenings]
        assert days == sorted(set(days))
        monday = season_calendar.week_start(week)
        for e in evenings:
            assert e.day.weekday() in omens.EVENINGS and e.day.weekday() < 5   # never Saturday or Sunday
            assert monday <= e.day < monday + dt.timedelta(days=7)
            assert e.start.date() == e.day and e.start.tzinfo is season_calendar.PACIFIC
            assert dt.time(18, 0) <= e.start.time() <= dt.time(20, 50) and e.start.minute % 10 == 0
            assert sorted(e.order) == sorted(omens.OMENS)
        assert evenings[0].order[0] != evenings[1].order[0]   # two evenings, two different first tries


def test_the_plan_is_the_same_for_a_secret_and_another_for_another():
    assert omens.plan(SECRET, 3) == omens.plan(SECRET, 3)
    weeks = range(1, 30)
    assert [omens.plan(SECRET, w) for w in weeks] != [omens.plan("1.2", w) for w in weeks]
    # It moves around: over a season every weekday and every omen comes first sometimes.
    plans = [e for w in range(1, 60) for e in omens.plan(SECRET, w)]
    assert {e.day.weekday() for e in plans} == set(omens.EVENINGS)
    assert {e.order[0] for e in plans} == set(omens.OMENS)
    assert len({e.start.time() for e in plans}) > 8


def test_no_omens_before_week_one():
    assert omens.plan(SECRET, 0) == [] and omens.plan(SECRET, -1) == []
    launch_weekend = pacific(2026, 11, 22, 19, 0)
    assert season_calendar.week_at(launch_weekend) == 0
    assert omens.evening_of(SECRET, launch_weekend) is None


def test_the_secret_comes_from_the_saved_scoreboard_only():
    assert omens.key({"om": {"#key1": 5, "#key2": 7}}) == "5.7"
    assert omens.key({"om": {"#key1": 5}}) is None and omens.key({}) is None
    # Nothing in the repo is the secret: the pack draws it in game.
    load = fn("load")
    assert ("execute unless score #key1 om matches 1.. store result score #key1 om run random value "
            "1..1000000000") in load
    assert ("execute unless score #key2 om matches 1.. store result score #key2 om run random value "
            "1..1000000000") in load


def test_an_evening_runs_from_its_start_until_10_pm():
    e = first_evening()
    assert omens.evening_of(SECRET, e.start) == e
    assert omens.evening_of(SECRET, e.start - dt.timedelta(minutes=1)) is None
    late = dt.datetime.combine(e.day, dt.time(21, 59), season_calendar.PACIFIC)
    assert omens.evening_of(SECRET, late) == e
    assert omens.evening_of(SECRET, late + dt.timedelta(minutes=1)) is None
    # The same evening seen from UTC (the VPS's clock).
    assert omens.evening_of(SECRET, e.start.astimezone(rcon.UTC)) == e


# ---------------------------------------------------------------- the commands


def test_commands_send_the_order_what_it_needs_then_the_try(tmp_path):
    world = make_world(tmp_path, *KEY, ("om.streak", "Alex", 5), ("om.streak", "Steve", 9), ("om.streak", "Low", 2),
                       ("om.streak", "bad name!", 12))
    e = first_evening()
    out = omens.commands(world, e.start)
    assert out[0] == "data modify storage realms:omens order set value [" + ",".join(f'"{o}"' for o in e.order) + "]"
    assert out[-1] == f"function realms:omens/try {{night:{e.night},late:0}}"
    spots = drops.spots(world, "meteor " + drops.slot_of(e.start))
    assert spots and "data modify storage realms:omens spots set value [" + ",".join(
        f"{{x:{x},z:{z}}}" for x, z in spots) + "]" in out
    # Longest streak first; too short and impossible names left out.
    assert 'data modify storage realms:omens hunt set value [{name:"Steve"},{name:"Alex"}]' in out
    for c in out:
        assert c.isascii() and "\n" not in c and len(c.encode()) <= rcon.LIMIT
    # The Meteor's spots are new each slot, as drops' are, and never the supply drop's.
    assert drops.spots(world, "meteor " + drops.slot_of(e.start)) != drops.spots(world, drops.slot_of(e.start))


def test_an_omen_with_nothing_to_work_with_is_left_out(tmp_path):
    world = make_world(tmp_path, *KEY, ("om.streak", "Alex", 2), border=False)
    e = first_evening()
    out = omens.commands(world, e.start)
    left = [o for o in e.order if o not in ("meteor", "hunted")]
    assert out == ["data modify storage realms:omens order set value [" + ",".join(f'"{o}"' for o in left) + "]",
                   f"function realms:omens/try {{night:{e.night},late:0}}"]


def test_no_commands_without_the_secret_or_outside_an_evening(tmp_path):
    e = first_evening()
    assert omens.commands(make_world(tmp_path / "a"), e.start) == []
    assert omens.commands(tmp_path / "nothing", e.start) == []
    world = make_world(tmp_path / "b", *KEY)
    assert omens.commands(world, e.start - dt.timedelta(minutes=10)) == []
    other = next(e.day + dt.timedelta(days=d) for d in range(1, 7)
                 if e.day + dt.timedelta(days=d) not in {x.day for x in omens.plan(SECRET, 1)})
    assert omens.commands(world, dt.datetime.combine(other, dt.time(21, 0), season_calendar.PACIFIC)) == []


def test_the_saved_world_is_only_read_in_an_evenings_hours(tmp_path, monkeypatch):
    def unread(world):
        raise AssertionError("read the saved world")
    monkeypatch.setattr(saved_world, "scoreboard", unread)
    e = first_evening()
    for when in (e.start.replace(hour=17, minute=50), e.start.replace(hour=22, minute=0),
                 pacific(2026, 11, 28, 19, 0),    # a Saturday
                 pacific(2026, 11, 18, 19, 0)):   # before week 1
        assert omens.commands(tmp_path, when) == []


def evening_on_a_drop_night() -> omens.Evening:
    return next(e for w in range(1, 10) for e in omens.plan(SECRET, w) if season_calendar.drop_night(e.day))


def test_a_meteor_late_on_a_drop_night_waits_for_the_nights_drop(tmp_path):
    world = make_world(tmp_path, *KEY)
    e = evening_on_a_drop_night()

    def late_at(hour, minute):
        try_ = omens.commands(world, dt.datetime.combine(e.day, dt.time(hour, minute), season_calendar.PACIFIC))[-1]
        return int(re.fullmatch(rf"function realms:omens/try \{{night:{e.night},late:([01])\}}", try_)[1])
    # The Meteor and its chest take up to 25 minutes, then the drops' timer asks within 10.
    assert dt.timedelta(minutes=35) == omens.METEOR_LATE
    assert late_at(21, 15) == 0 and late_at(21, 24) == 0
    assert late_at(21, 25) == 1 and late_at(21, 55) == 1
    friday = next(e for w in range(1, 30) for e in omens.plan(SECRET, w) if e.day.weekday() == 4)
    out = omens.commands(world, dt.datetime.combine(friday.day, dt.time(21, 45), season_calendar.PACIFIC))
    assert out[-1].endswith(",late:0}")   # no drop on Fridays to keep
    try_ = fn("try")
    assert "$scoreboard players set #late om $(late)" in try_ and "$scoreboard players set #tonight om $(night)" in try_
    begin = fn("meteor/begin")
    assert begin.index("execute if score #late om matches 1 unless score #night dr = #tonight om run return 0") < (
        begin.index("function realms:drops/meteor"))


def test_hunt_choices_are_the_longest_streaks():
    scores = {"om.streak": {f"P{i}": i for i in range(12)} | {"#fake": 99}}
    assert omens.hunt_choices(scores) == ["P11", "P10", "P9", "P8", "P7"]
    assert omens.hunt_choices({}) == []


def test_send_logs_what_the_try_returned(tmp_path):
    world = make_world(tmp_path, *KEY)
    e = first_evening()
    server = rcon.Recorder({"function realms:omens/try": "Function realms:omens/try returned 25"})
    log = []
    assert omens.send(server, world, e.start, log.append) == 0
    assert server.sent == omens.commands(world, e.start)
    assert log[0] == "order sent: ok"
    assert log[-1] == f"function realms:omens/try {{night:{e.night},late:0}}: {omens.TRY_CODES[25]}"


def test_send_is_silent_outside_an_evening_and_skips_a_stopped_server(tmp_path):
    world = make_world(tmp_path, *KEY)
    e = first_evening()
    log = []
    assert omens.send(rcon.Recorder(), world, e.start - dt.timedelta(hours=1), log.append) == 0 and log == []
    stopped = rcon.Recorder(running=False)
    assert omens.send(stopped, world, e.start, log.append) == 0
    assert stopped.sent == [] and log == ["server not running: nothing sent"]


def test_the_try_is_not_sent_when_the_order_does_not_arrive(tmp_path):
    world = make_world(tmp_path, *KEY)
    server, log = rcon.Recorder(fail=1), []
    assert omens.send(server, world, first_evening().start, log.append) == 1
    assert server.sent == []


@pytest.mark.parametrize(("answer", "said"), [
    ("Function realms:omens/try returned 1", omens.TRY_CODES[1]),
    ("Function realms:omens/try returned 99", "Function realms:omens/try returned 99"),
    ("", "ok"),
])
def test_every_try_answer_reads_as_words(answer, said):
    try_ = "function realms:omens/try {night:1}"
    assert omens.meaning(try_, answer) == f"{try_}: {said}"


def test_main_prints_the_commands_and_the_plan(tmp_path, capsys):
    world = make_world(tmp_path, *KEY)
    e = first_evening()
    assert omens.main(["commands", str(world), "--at", e.start.astimezone(rcon.UTC).isoformat()]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == f"function realms:omens/try {{night:{e.night},late:0}}"
    assert omens.main(["plan", str(world), "--at", e.start.isoformat()]) == 0
    out = capsys.readouterr().out
    assert "season week 1:" in out and omens.NAMES[e.order[0]] in out
    assert omens.main(["plan", str(make_world(tmp_path / "x"))]) == 1


# ---------------------------------------------------------------- reading what ran (the recap)


def test_ran_reads_the_evenings_back_by_week():
    scores = {"om": {"#on.20261124": 1, "#on.20261127": 4, "#on.20261201": 3, "#on.20261202": 0, "#key1": 5,
                     "#on.2026112": 2}}
    assert omens.ran(scores) == {dt.date(2026, 11, 24): "blood_moon", dt.date(2026, 11, 27): "hunted",
                                 dt.date(2026, 12, 1): "truce"}
    assert omens.in_week(scores, 1) == {dt.date(2026, 11, 24): "blood_moon", dt.date(2026, 11, 27): "hunted"}
    assert omens.in_week(scores, 2) == {dt.date(2026, 12, 1): "truce"}


def test_the_try_records_the_evening_as_ran_reads_it():
    body = fn("try")
    assert "$data modify storage realms:omens tonight set value {night:$(night)}" in body
    assert body.index("scoreboard players operation #prev om = #night om") < (
        body.index("scoreboard players operation #night om = #tonight om"))
    assert "function realms:omens/record with storage realms:omens tonight" in body
    assert "$scoreboard players operation #on.$(night) om = #state om" in fn("record")
    assert "$scoreboard players reset #on.$(night) om" in fn("unrecord")
    assert [omens.STATES[o] for o in omens.OMENS] == [1, 2, 3, 4]


# ---------------------------------------------------------------- the data pack


def test_the_pack_has_no_problems():
    files = {f"{omens.DATAPACK}/{k}": v for k, v in FILES.items()}
    for gen in datapacks.generators().values():
        for root, pack in gen.packs(REPO).items():
            if root.name != omens.DATAPACK:
                files.update({f"{root.name}/{k}": v for k, v in pack.items() if isinstance(v, str)})
    assert [p for p in datapacks.problems(files) if omens.DATAPACK in p] == []


def test_try_returns_every_code_and_checks_in_order():
    body = [line for line in fn("try").splitlines() if not line.startswith("#")]
    assert set(map(int, re.findall(r"return (\d+)$", "\n".join(body), re.M))) == set(omens.TRY_CODES)
    codes = [int(m[1]) for line in body if (m := re.search(r"return (\d+)$", line))]
    assert codes[:3] == [20, 26, 21] and codes[-1] == 1
    for cond in drops.EVENTS_ON:
        assert f"execute if score {cond} run return 23" in body
    assert "execute if score #state dr matches 1.. run return 24" in body
    assert "execute if score #launched rw.day matches 1" not in "\n".join(body)   # gated with unless: test play
    assert "execute unless score #launched rw.day matches 1 run return 26" in body


def test_pick_tries_each_omen_in_the_order_sent():
    pick = fn("pick")
    assert "execute store result score #r om run function realms:omens/begin with storage realms:omens next" in pick
    assert pick.rstrip().endswith("return run function realms:omens/pick")
    assert fn("begin") == "$return run function realms:omens/$(id)/begin\n"
    for omen in omens.OMENS:
        assert f"{omens.FN}/{omen}/begin.mcfunction" in FILES


def test_an_event_ends_an_omen_and_what_it_changed_comes_back():
    second = fn("second")
    for cond in drops.EVENTS_ON:
        assert f"execute if score {cond} run return run function realms:omens/interrupted" in second
    end = fn("end")
    assert "execute if score #state om matches 1 run function realms:omens/blood_moon/calm" in end
    assert "execute if score #state om matches 3 run function realms:omens/truce/restore" in end
    assert "scoreboard players reset * om.hunt" in end and "scoreboard players set #state om 0" in end
    # Never undo the season lock's Peaceful and no-PvP.
    assert "execute if score #season_locked ev.state matches 1 run return 0" in fn("blood_moon/calm")
    assert "execute if score #season_locked ev.state matches 1 run return 0" in fn("truce/restore")
    assert "execute if score #launching realms.rules matches 1 run return 0" in fn("truce/restore")


def test_blood_moon_waits_for_night_and_gives_back_the_difficulty():
    begin = fn("blood_moon/begin")
    assert "execute if score #diff om matches 0 run return 0" in begin   # Peaceful: no mobs
    second = fn("blood_moon/second")
    assert "execute store result score #now om run time query daytime" in second
    # It rises at the start of a night only, never just before dawn, and waits longer than a Minecraft day.
    assert ("execute if score #phase om matches 0 if score #now om matches 13000..14000 run return run function "
            "realms:omens/blood_moon/rise") in second
    assert omens.BLOOD_WAIT > 20 * 60
    assert "execute unless score #now om matches 13000..22999 run return run function realms:omens/blood_moon/dawn" in (
        second)
    rise = fn("blood_moon/rise")
    assert rise.index("execute store result score #diff om run difficulty") < rise.index("difficulty hard")
    calm = fn("blood_moon/calm")
    assert "execute unless score #now om matches 3 run return 0" in calm   # staff changed it meanwhile: kept
    assert "execute if score #diff om matches 2 run difficulty normal" in calm


def test_a_blood_moon_never_turns_peaceful_into_hard():
    rise = fn("blood_moon/rise")
    # Staff set Peaceful after it was announced: it fades at nightfall instead of rising.
    assert rise.index("execute if score #diff om matches 0 run return run function realms:omens/blood_moon/fade") < (
        rise.index("difficulty hard"))
    calm = fn("blood_moon/calm")
    for n, name in enumerate(("peaceful", "easy", "normal")):
        assert f"execute if score #diff om matches {n} run difficulty {name}" in calm


def test_blood_moon_rouses_only_night_mobs_and_gives_nothing_for_a_fight():
    tag = json.loads(FILES["data/realms/tags/entity_type/omens/blood_moon.json"])["values"]
    names = [v if isinstance(v, str) else v["id"] for v in tag]
    assert "minecraft:warden" not in names and "minecraft:ravager" not in names and "minecraft:player" not in names
    rouse = fn("blood_moon/rouse")
    assert "strength" not in rouse
    for item, weight, lo, hi in omens.BLOOD_LOOT:
        assert weight > 0 and 1 <= lo <= hi <= 8 and not any(w in item for w in FORBIDDEN), item
    kill = fn("blood_moon/kill")
    assert kill.splitlines()[1] == "advancement revoke @s only realms:omens/blood_kill"
    assert f"execute if score @s om.loot matches {omens.BLOOD_CAP}.. run return 0" in kill
    assert "execute unless score #phase om matches 1 run return 0" in kill
    adv = json.loads(FILES["data/realms/advancement/omens/blood_kill.json"])
    assert adv["rewards"]["function"] == "realms:omens/blood_moon/kill"


def test_roused_mobs_calm_by_themselves_and_pay_only_at_their_own_moon():
    rouse = fn("blood_moon/rouse")
    effects = [line for line in rouse.splitlines() if line.startswith("effect give")]
    assert effects == [f"effect give @s minecraft:speed {omens.BLOOD_BUFF} 0 true",
                       f"effect give @s minecraft:resistance {omens.BLOOD_BUFF} 0 true"]
    assert omens.BLOOD_BUFF <= 5   # given again each second: an unloaded mob keeps a few seconds at most
    assert "scoreboard players operation @s om.blood = #moon om" in rouse
    # Every second while it is up, whether roused before or not.
    assert ("as @e[type=#realms:omens/blood_moon,distance=..48] run function realms:omens/blood_moon/rouse" in
            fn("blood_moon/second"))
    assert "om.roused" not in "\n".join(FILES[p] for p in FUNCTIONS)
    # Each moon has its own number, and a kill pays only for a mob carrying the one up now.
    assert "execute unless score #moon om matches 0.. run scoreboard players set #moon om 0" in fn("load")
    rise = fn("blood_moon/rise")
    assert rise.index("scoreboard players add #moon om 1") < rise.index("difficulty hard")
    moon = {"type": "minecraft:score", "target": {"type": "minecraft:fixed", "name": "#moon"}, "score": "om"}
    adv = json.loads(FILES["data/realms/advancement/omens/blood_kill.json"])
    assert adv["criteria"]["kill"]["conditions"]["entity"] == {
        "type": "minecraft:entity_scores", "entity": "this", "scores": {"om.blood": {"min": moon, "max": moon}}}


FORBIDDEN = ("netherite", "diamond", "emerald", "golden_apple", "enchanted", "potion", "totem", "elytra",
             "shulker", "beacon", "strength", "ancient_debris", "trident", "mace", "spawner", "_spawn_egg")


def test_the_meteor_goes_through_drops():
    begin = fn("meteor/begin")
    assert "data modify storage realms:drops spots set from storage realms:omens spots" in begin
    assert "execute store result score #r om run function realms:drops/meteor" in begin
    # The omen ends with the drop, once it was announced.
    second = fn("second").splitlines()
    meteor = "execute if score #state om matches 2 "
    announced = meteor + "if score #state dr matches 2.. run scoreboard players set #phase om 1"
    failed = (meteor + "if score #phase om matches 0 unless score #state dr matches 1.. run "
              "function realms:omens/meteor/failed")
    ended = meteor + "if score #phase om matches 1 unless score #state dr matches 1.. run function realms:omens/end"
    assert second.index(announced) < second.index(failed) < second.index(ended)


def test_a_meteor_with_no_dry_ground_gives_the_evening_to_the_next_omen():
    failed = fn("meteor/failed").splitlines()
    assert failed[2:4] == ["scoreboard players set #state om 0", "scoreboard players set #phase om 0"]
    assert "execute store result score #r om run function realms:omens/pick" in failed
    # The next omen that starts is recorded for the evening; with none, the evening is as if nothing was tried.
    assert ("execute if score #r om matches 1 run return run function realms:omens/record with storage realms:omens "
            "tonight") in failed
    assert failed[-2:] == ["function realms:omens/unrecord with storage realms:omens tonight",
                           "scoreboard players operation #night om = #prev om"]
    # It never touches what drops.py's own end path resets (#meteor dr, in drops/next).
    assert "#meteor" not in "\n".join(failed)


def test_truce_hour_only_turns_pvp_off_when_it_was_on():
    begin = fn("truce/begin")
    assert begin.index("execute unless score #pvp om matches 1 run return 0") < begin.index("gamerule pvp false")
    assert "execute if score #launching realms.rules matches 1 run return 0" in begin
    assert fn("truce/restore").rstrip().endswith("gamerule pvp true")


def test_the_hunts_bounty_is_withdrawn_when_the_hunt_ends_without_a_kill():
    assert "execute if score #state om matches 4 run function realms:omens/hunted/over" in fn("end")
    over = fn("hunted/over")
    assert "execute if score #phase om matches 1 run return 0" in over and "withdrawn" in over
    kill = fn("hunted/kill")
    assert kill.index("scoreboard players set #phase om 1") < kill.index("function realms:omens/end")
    assert "scoreboard players set #phase om 0" in fn("hunted/on")
    assert "it ends with the hunt" in fn("hunted/on")


def test_hunted_posts_the_standings_bounty_and_staff_claim_it():
    on = fn("hunted/on")
    assert '$function realms:standings/bounty/post {target:"$(name)"}' in on
    assert f"{standings.FN}/bounty/post.mcfunction" in standings.datapack_files()
    commands = [line for p in FUNCTIONS for line in FILES[p].splitlines() if not line.startswith("#")]
    assert not any("bounty/claim" in line for line in commands)   # staff check the kill first
    mark = fn("hunted/mark")
    assert "$execute unless entity @a[name=$(name),gamemode=survival,tag=!ev.arena] run return 0" in mark
    assert f"$execute unless score $(name) om.streak matches {omens.HUNT_MIN}.. run return 0" in mark
    kill = fn("hunted/kill")
    assert "execute if entity @s[tag=ev.arena] run return 0" in kill
    adv = json.loads(FILES["data/realms/advancement/omens/hunted_kill.json"])
    terms = adv["criteria"]["kill"]["conditions"]["entity"]["terms"]
    assert {"type": "minecraft:entity_scores", "entity": "this", "scores": {"om.hunt": {"min": 1}}} in terms
    # Nothing shows where they are.
    hunted = "\n".join(FILES[p] for p in FUNCTIONS if "/hunted/" in p)
    assert "glowing" not in hunted and "Pos" not in hunted and "locate" not in hunted


def test_kill_streaks_count_from_the_launch_and_outside_the_arena():
    tick = fn("tick")
    assert ("execute if score #launched rw.day matches 1 as @a[scores={om.pk=1..},tag=!ev.arena] run "
            "scoreboard players operation @s om.streak += @s om.pk") in tick
    assert "scoreboard players set @a[scores={om.deaths=1..},tag=!ev.arena] om.streak 0" in tick
    # The hunted player's death is checked before deaths are cleared.
    assert tick.index("realms:omens/hunted/died") < tick.index("om.deaths 0")
    assert "execute unless score #launched rw.day matches 1 run scoreboard players reset * om.streak" in fn("second")


def test_a_restart_carries_on_and_keeps_the_settings():
    load = fn("load")
    assert "schedule function realms:omens/second 20t replace" in load
    assert "execute unless score #min om matches 1.. run scoreboard players set #min om 4" in load
    assert "execute unless score #auto om matches 0.. run scoreboard players set #auto om 1" in load
    assert "function realms:omens/end" not in load


def test_staff_starts_never_use_up_the_evening():
    for path in ("start/blood_moon", "start/truce", "hunt"):
        body = fn(path)
        assert "#night" not in body and "#on." not in body
        assert body.splitlines()[1].startswith("execute if score #state om matches 1.. run return run tellraw @s")


def test_help_lists_every_staff_command():
    help_ = fn("help")
    assert help_.count("suggest_command") == len(omens.HELP)
    for cmd, _ in omens.HELP:
        assert json.dumps(f"/function realms:omens/{cmd}")[1:-1] in help_


def test_the_generator_is_registered():
    assert "omens" in datapacks.GENERATORS


# ---------------------------------------------------------------- the VPS scripts


DEPLOY = REPO.root / "deploy"


@pytest.mark.parametrize("name", ["realms-omens.sh", "realms-omens.service", "realms-omens.timer"])
def test_deploy_files_are_plain_ascii_with_lf(name):
    data = (DEPLOY / name).read_bytes()
    assert data.isascii() and b"\r" not in data


def test_the_script_is_a_timed_job_that_never_shows_the_plan():
    text = (DEPLOY / "realms-omens.sh").read_text()
    assert text.startswith("#!/bin/sh\n") and "set -eu" in text
    assert "JOB_TOOL=omens.py\n" in text and "JOB_WORLD=1\n" in text and text.endswith('\ntimed_job "$@"\n')
    assert "JOB_SHOW" not in text and "JOB_NONE=" in text


def test_the_timer_runs_five_minutes_after_the_drops():
    timer = (DEPLOY / "realms-omens.timer").read_text()
    assert "OnCalendar=*-*-* *:05/10:30\n" in timer and "Persistent=false\n" in timer
    assert "OnCalendar=*-*-* *:00/10:30\n" in (DEPLOY / "realms-drops.timer").read_text()
    assert "User=realms\n" in (DEPLOY / "realms-omens.service").read_text()
