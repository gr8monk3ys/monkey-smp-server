import datetime as dt
import json
from pathlib import Path

import challenges as challenges_module
import rcon
import wardrobe
from repo import REPO

FN = "data/monkey/function/wardrobe"


def test_store_commands_never_set_an_earned_score():
    """Attendance, holiday, challenge, quest and launch-weekend scores are earned by showing up. No store command
    may set them: the store sets only the pass months and the supporter tier."""
    earned = set(wardrobe.SCORES) - wardrobe.SOLD - {"rw.days", "rw.playbase", "rw.invites"}
    assert {"rw.events", "rw.challenges", "rw.launch", "rw.quest", wardrobe.KIN, wardrobe.CHAMPION} <= earned
    assert set(wardrobe.HOLIDAYS) <= earned
    store = [line for line in (REPO.root / "docs" / "RETENTION.md").read_text(encoding="utf-8").splitlines()
             if "{username}" in line]
    assert store
    for line in store:
        assert not any(objective in line for objective in earned), line


def test_every_retention_score_exists():
    data = wardrobe.datapack_files()
    load = data[f"{FN}/load.mcfunction"]
    second = data[f"{FN}/second.mcfunction"]
    for objective in [*wardrobe.SCORES, "rw.hours", "rw.play", "rw.launchtime"]:
        assert f"scoreboard objectives add {objective} " in load, objective
    for objective in wardrobe.SCORES:
        assert f"scoreboard players add @a {objective} 0" in second, objective


def test_hours_include_play_carried_from_earlier_worlds():
    second = wardrobe.datapack_files()[f"{FN}/second.mcfunction"].splitlines()
    play = second.index("execute as @a run scoreboard players operation @s rw.hours = @s rw.play")
    assert second[play + 1] == "execute as @a run scoreboard players operation @s rw.hours += @s rw.playbase"
    assert second[play + 2] == "scoreboard players operation @a rw.hours /= #hour rw.const"


def test_founders_and_later_seasons_are_marked_from_the_season_number():
    second = wardrobe.datapack_files()[f"{FN}/second.mcfunction"]
    assert "execute if score #season rw.day matches 1 run scoreboard players set @a rw.founder 1" in second
    assert "execute if score #season rw.day matches 2 run scoreboard players set @a rw.s2 1" in second
    for objective in (*wardrobe.SEASON_MARKS, wardrobe.CHAMPION, wardrobe.KIN):
        assert objective not in wardrobe.SOLD


def test_a_new_day_counts_a_day_played_and_says_nothing():
    new_day = wardrobe.datapack_files()[f"{FN}/new_day.mcfunction"]
    body = [line for line in new_day.splitlines() if not line.startswith("#")]
    assert body == ["scoreboard players add @s rw.days 1", "scoreboard players operation @s rw.lastday = #today rw.day"]


def test_the_skins_are_retired():
    """The relaunch dropped the client resource pack the skins' models were in, so a skinned item would show a
    missing model. Nothing in the pack may change how an item looks, and no skin or reset is left to call."""
    data = wardrobe.datapack_files()
    assert not [p for p in data if "/item_modifier/" in p or "/tags/item/" in p]
    assert not [p for p in data if p.startswith((f"{FN}/skin/", f"{FN}/notice/", f"{FN}/reset"))]
    assert not [p for p in data if p.startswith(f"{FN}/menu_support")]
    for path, text in data.items():
        assert "item_model" not in text and "asset_id" not in text and "item modify" not in text, path
        assert ".seen" not in text or path.startswith("data/monkey/function/challenges/"), path
    assert not hasattr(wardrobe, "resourcepack_files") and not hasattr(wardrobe, "skins")


def chat_lines(data: dict, function: str) -> int:
    """How many chat lines a function prints for one player, at most: a tellraw is a line (plus one per newline in
    it), the other half of an if/unless pair is not counted, and a function it calls counts what that prints."""
    shown = 0
    for line in data[f"data/monkey/function/{function}.mcfunction"].splitlines():
        if line.startswith("execute unless ") and " run tellraw @s " in line:
            continue   # the other half of an if/unless pair
        if " tellraw @s " in f" {line}":
            shown += 1 + line.split(" tellraw @s ", 1)[-1].count("\\n")
        elif line.startswith("function monkey:"):
            shown += chat_lines(data, line.split(":", 1)[1])
        elif line.startswith("execute if score #") and " run function monkey:challenges/line/" in line:
            shown += 0   # one challenge per kind is on: counted below, by kind
    return shown


def test_every_trigger_value_opens_the_one_menu_and_it_fits_open_chat():
    """Open chat shows 20 lines. The menu prints a header (two lines), the counts, one line per challenge that is
    on, the weekly server goal's line and the first-week quest's line (an over-count: both of its halves)."""
    data = wardrobe.datapack_files()
    use = [line for line in data[f"{FN}/use.mcfunction"].splitlines() if not line.startswith("#")]
    assert use == ["function monkey:wardrobe/menu", "scoreboard players set @s wardrobe 0",
                   "scoreboard players enable @s wardrobe"]
    menu = data[f"{FN}/menu.mcfunction"]
    for called in ("challenges/lines", "goal/line", "quest/status"):
        assert f"function monkey:{called}" in menu
    challenges = len(challenges_module.KINDS)
    assert chat_lines(data, "wardrobe/menu") + challenges <= 20
    for o in wardrobe.COUNTED:
        assert f'"objective":"{o}"' in menu


def test_the_challenges_trigger_opens_the_same_menu():
    data = wardrobe.datapack_files()
    assert "function monkey:wardrobe/menu_challenges" in data["data/monkey/function/challenges/use.mcfunction"]
    assert "function monkey:wardrobe/menu" in data[f"{FN}/menu_challenges.mcfunction"].splitlines()
    assert "execute as @a[scores={challenges=1..}] run function monkey:challenges/use" in data[
        f"{FN}/tick.mcfunction"]


def commands(function: str) -> set[str]:
    """Every command a function runs, also inside `execute ... run` and `return run`."""
    used = set()
    for line in function.splitlines():
        line = line.removeprefix("$")
        if not line or line.startswith("#"):
            continue
        for part in line.split(" run "):
            word = part.split()[0]
            if word != "return":
                used.add(word)
        used.add(line.split()[0])
    return used - {"return"}


def test_challenge_and_launch_rewards_are_scores_only():
    """What the weekly challenges and the launch weekend give is a score: never an item, an effect, experience or a
    stat. Their functions run only these commands, and their advancements reward only a function."""
    data = wardrobe.datapack_files()
    allowed = {"scoreboard", "tellraw", "playsound", "advancement", "function", "execute", "time"}
    found = [p for p in data
             if p.startswith(("data/monkey/function/challenges/", "data/monkey/function/wardrobe/founder/"))]
    assert len(found) > 40
    for path in found:
        assert commands(data[path]) <= allowed, (path, commands(data[path]) - allowed)
    advancements = [p for p in data if "/advancement/" in p]
    assert advancements
    for path in advancements:
        advancement = json.loads(data[path])
        assert set(advancement["rewards"]) == {"function"}, path
        assert "display" not in advancement, path   # no toast, no chat line, nothing in the advancements screen


def test_the_launch_weekend_names_no_skin():
    data = wardrobe.datapack_files()
    for name in ("open", "open_for", "close", "second"):
        assert "Circlet" not in data[f"{FN}/founder/{name}.mcfunction"], name
    assert "rw.launch 1" in data[f"{FN}/founder/second.mcfunction"]


MIDNIGHT = dt.datetime(2026, 10, 28, tzinfo=rcon.UTC)
DAY_ONCE = "function monkey:wardrobe/day_once {stamp:20261028}"


def test_the_day_is_one_dated_command_and_a_stopped_server_fails_it(capsys):
    assert wardrobe.main(["commands", "--at", "2026-10-28T00:00:00Z"]) == 0
    assert capsys.readouterr().out.splitlines() == [DAY_ONCE]
    # The UTC date, whatever the offset: 5 PM Pacific on the 27th is already the 28th.
    assert wardrobe.day_commands(dt.datetime(2026, 10, 27, 17, tzinfo=dt.timezone(-dt.timedelta(hours=7)))) == [
        DAY_ONCE]
    log = []
    assert wardrobe.send_day(rcon.Recorder(running=False), MIDNIGHT, log=log.append) == rcon.NOT_RUNNING
    assert log == ["server not running: the day isn't started yet"]
    server = rcon.Recorder()
    assert wardrobe.send_day(server, MIDNIGHT, log=log.append) == 0 and server.sent == [DAY_ONCE]
    refusing = rcon.Recorder({DAY_ONCE: "Unknown function monkey:wardrobe/day_once"})
    assert wardrobe.send_day(refusing, MIDNIGHT, log=log.append) == 1


def test_a_date_starts_one_day_however_often_it_is_sent():
    """monkey-day.service retries after a timeout that may have reached the server: the pack keeps the date."""
    files = wardrobe.datapack_files()
    once = files["data/monkey/function/wardrobe/day_once.mcfunction"].splitlines()
    body = [line for line in once if not line.startswith("#")]
    assert body == ["$execute if score #day.sent rw.day matches $(stamp) run return 0",
                    "$scoreboard players set #day.sent rw.day $(stamp)",
                    "function monkey:wardrobe/day"]
    assert "scoreboard players add #today rw.day 1" in files["data/monkey/function/wardrobe/day.mcfunction"]


def test_the_day_gives_up_a_date_after_6_hours_of_tries(tmp_path):
    pending, log = tmp_path / "pending", []
    down = rcon.Recorder(running=False)
    assert wardrobe.send_day(down, MIDNIGHT, pending, log.append) == rcon.NOT_RUNNING
    assert pending.read_text() == f"20261028 {int(MIDNIGHT.timestamp())}\n"   # the first failed try
    later = MIDNIGHT + wardrobe.GIVE_UP - dt.timedelta(minutes=10)
    assert wardrobe.send_day(rcon.Recorder({DAY_ONCE: "Unknown function x"}), later, pending, log.append) == 1
    assert pending.read_text() == f"20261028 {int(MIDNIGHT.timestamp())}\n"   # still counted from the first
    log.clear()
    assert wardrobe.send_day(down, MIDNIGHT + wardrobe.GIVE_UP, pending, log.append) == rcon.GAVE_UP
    assert log[-1] == "gave up: the day for 20261028 didn't start in 6 hours of tries" and not pending.exists()
    # A success clears it, and another date's pending try doesn't count against this one.
    wardrobe.send_day(down, MIDNIGHT, pending, log.append)
    assert wardrobe.send_day(rcon.Recorder(), MIDNIGHT, pending, log.append) == 0 and not pending.exists()
    pending.write_text("20261027 0\n")
    assert wardrobe.send_day(down, MIDNIGHT + wardrobe.GIVE_UP, pending, log.append) == rcon.NOT_RUNNING
    assert pending.read_text().startswith("20261028 ")
    assert wardrobe.send_day(down, MIDNIGHT + 2 * wardrobe.GIVE_UP, None, log.append) == rcon.NOT_RUNNING  # by hand


def test_the_day_keeps_its_first_try_in_systemds_state_directory(monkeypatch):
    given = []
    monkeypatch.setattr(wardrobe, "send_day", lambda server, when, pending: given.append(pending) or 0)
    monkeypatch.setenv("STATE_DIRECTORY", "/var/lib/monkey-day")
    assert wardrobe.main(["send", "--docker", "/d"]) == 0 and given == [Path("/var/lib/monkey-day/pending")]
    monkeypatch.delenv("STATE_DIRECTORY")
    assert wardrobe.main(["send", "--docker", "/d"]) == 0 and given[-1] is None   # run by hand: no limit
