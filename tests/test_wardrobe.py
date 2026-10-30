import datetime as dt
import json
import struct
from pathlib import Path

import pytest

import challenges as challenges_module
import rcon
import wardrobe
from repo import REPO


def test_trigger_values_are_unique_and_clear_of_the_menu_values():
    values = [v for v, _, _ in wardrobe.skins()]
    assert len(values) == len(set(values))
    assert min(values) > max(wardrobe.MENUS)
    assert len({s["id"] for _, _, s in wardrobe.skins()}) == len(values)


def test_tenure_rewards_the_first_three_months():
    """A new buyer should unlock something at each of the first renewals, not wait half a year."""
    months = {s["unlock"][1] for _, _, s in wardrobe.skins() if s["unlock"][0] == "rw.months"}
    assert {1, 2, 3} <= months


def test_event_and_holiday_skins_are_never_sold():
    """Attendance, holiday, challenge and launch-weekend skins are earned by showing up. No store command may set
    their scores."""
    earned = {s["unlock"][0] for _, _, s in wardrobe.skins()} - wardrobe.SOLD
    assert "rw.events" in earned and set(wardrobe.HOLIDAYS) <= earned
    assert {"rw.challenges", "rw.launch"} <= earned
    events = sorted(s["unlock"][1] for _, _, s in wardrobe.skins() if s["unlock"][0] == "rw.events")
    assert events == [3, 10]
    store = [line for line in (REPO.root / "docs" / "RETENTION.md").read_text(encoding="utf-8").splitlines()
             if "{username}" in line]
    assert store
    for line in store:
        assert not any(objective in line for objective in earned), line


def test_every_unlock_score_exists_and_announces_itself():
    data = wardrobe.datapack_files()
    load = data["data/monkey/function/wardrobe/load.mcfunction"]
    second = data["data/monkey/function/wardrobe/second.mcfunction"]
    for _, _, s in wardrobe.skins():
        objective, n = s["unlock"]
        assert f"scoreboard objectives add {objective} " in load
        if objective in wardrobe.NOTIFY:
            notice = data[f"data/monkey/function/wardrobe/notice/{objective[3:]}.mcfunction"]
            assert f"matches {n}.. unless score @s {objective}.seen matches {n}.. run tellraw" in notice
            assert f"{objective}.seen" in load and f"function monkey:wardrobe/notice/{objective[3:]}" in second


def test_hours_include_play_carried_from_earlier_worlds():
    second = wardrobe.datapack_files()["data/monkey/function/wardrobe/second.mcfunction"].splitlines()
    play = second.index("execute as @a run scoreboard players operation @s rw.hours = @s rw.play")
    assert second[play + 1] == "execute as @a run scoreboard players operation @s rw.hours += @s rw.playbase"
    assert second[play + 2] == "scoreboard players operation @a rw.hours /= #hour rw.const"


def chat_lines(data: dict, function: str) -> int:
    """How many chat lines a function prints for one player: a tellraw is a line (plus one per newline in it), a
    skin's owned/locked pair is one, and a function it calls counts what that prints."""
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


def test_each_menu_page_fits_open_chat():
    """Open chat shows 20 lines. Each page prints a header (two lines), the counts, one title per item kind, one
    line per skin and two footer lines; the challenges page also prints one line per challenge that is on."""
    data = wardrobe.datapack_files()
    use = data["data/monkey/function/wardrobe/use.mcfunction"]
    pages = {1: "menu", wardrobe.MENU_SUPPORT: "menu_support", wardrobe.MENU_CHALLENGES: "menu_challenges"}
    assert set(pages) == set(wardrobe.MENUS)
    for number, name in pages.items():
        assert f"matches {number} run function monkey:wardrobe/{name}" in use
        menu = data[f"data/monkey/function/wardrobe/{name}.mcfunction"]
        on_page = [(kind, s) for _, kind, s in wardrobe.skins() if wardrobe.page(s["unlock"]) == number]
        for _, s in on_page:
            assert f'"text":"[{s["name"]}]"' in menu
        challenges = len(challenges_module.KINDS) if number == wardrobe.MENU_CHALLENGES else 0
        assert chat_lines(data, f"wardrobe/{name}") + challenges == (
            2 + 1 + challenges + len({kind for kind, _ in on_page}) + len(on_page) + 2)
        assert chat_lines(data, f"wardrobe/{name}") + challenges <= 20, name
        for other in set(pages) - {number}:   # every page links to the other two
            assert f'"command":"/trigger wardrobe set {other}"' in menu.splitlines()[-1]
    assert sum(1 for _ in wardrobe.skins()) == sum(
        1 for _, _, s in wardrobe.skins() if wardrobe.page(s["unlock"]) in pages)


def test_the_challenge_and_launch_skins_are_on_the_challenges_page():
    data = wardrobe.datapack_files()
    for _, _, s in wardrobe.skins():
        if s["unlock"][0] in ("rw.challenges", "rw.launch"):
            assert wardrobe.page(s["unlock"]) == wardrobe.MENU_CHALLENGES
    assert "function monkey:challenges/lines" in data["data/monkey/function/wardrobe/menu_challenges.mcfunction"]
    assert "function monkey:wardrobe/menu_challenges" in data["data/monkey/function/challenges/use.mcfunction"]
    assert "execute as @a[scores={challenges=1..}] run function monkey:challenges/use" in data[
        "data/monkey/function/wardrobe/tick.mcfunction"]


def test_the_challenge_ladder():
    """Skins at 3, 9 and 18 challenges: one week of all three, then three weeks, then six (of a 12-week
    season). rw.challenges carries over, so a later season adds to it."""
    ladder = sorted((s["unlock"][1], kind) for _, kind, s in wardrobe.skins() if s["unlock"][0] == "rw.challenges")
    assert ladder == [(3, "blade"), (9, "helm"), (18, "blade")]
    assert "rw.challenges" in wardrobe.NOTIFY and "rw.challenges" in wardrobe.SCORES


def test_the_launch_weekend_skin():
    launch = [(kind, s) for _, kind, s in wardrobe.skins() if s["unlock"][0] == "rw.launch"]
    assert [(kind, s["id"], s["unlock"][1]) for kind, s in launch] == [("helm", "founders_circlet", 1)]
    assert "rw.launch" in wardrobe.NOTIFY
    assert wardrobe.how_to_unlock(("rw.launch", 1)) == "Played on Season I's launch weekend"


def test_the_docs_list_every_skin():
    doc = (REPO.root / "docs" / "RETENTION.md").read_text(encoding="utf-8")
    for _, kind, s in wardrobe.skins():
        objective, n = s["unlock"]
        assert f"| {s['name']} | {kind} |" in doc and f"`{objective} {n}`" in doc, s["name"]


def test_every_skin_is_wired_end_to_end():
    data = wardrobe.datapack_files()
    res = wardrobe.resourcepack_files()
    use = data["data/monkey/function/wardrobe/use.mcfunction"]
    for value, kind, s in wardrobe.skins():
        sid = s["id"]
        assert f"matches {value} run function monkey:wardrobe/skin/{sid}" in use
        assert f"monkey:wardrobe/{sid}" in data[f"data/monkey/function/wardrobe/skin/{sid}.mcfunction"]
        assert f"data/monkey/item_modifier/wardrobe/{sid}.json" in data
        assert f"assets/monkey/items/{sid}.json" in res
        assert f"assets/monkey/models/item/{sid}.json" in res
        assert png_size(res[f"assets/monkey/textures/item/{sid}.png"]) == (16, 16)
        if kind == "helm":
            assert f"assets/monkey/equipment/{sid}.json" in res
            assert png_size(res[f"assets/monkey/textures/entity/equipment/humanoid/{sid}.png"]) == (64, 32)


def test_skins_change_the_look_and_nothing_else():
    """Mojang's usage guidelines: what supporters get must be cosmetic. A skin may only touch the model,
    and on a helmet the worn look; never damage, armor, durability or enchantments."""
    data = wardrobe.datapack_files()
    modifiers = {path for path in data if "/item_modifier/" in path}
    # Every skin, the new ones included, goes through this check: no skin may apply anything but a modifier.
    assert {f"data/monkey/item_modifier/wardrobe/{s['id']}.json" for _, _, s in wardrobe.skins()} <= modifiers
    for path, text in data.items():
        if "/function/" in path:
            used = commands(text)
            assert not used & {"enchant", "attribute"} and "item replace" not in text, path
        if path not in modifiers:
            continue
        modifier = json.loads(text)
        assert modifier["type"] == "minecraft:set_components"
        components = modifier["components"]
        assert set(components) <= {"minecraft:item_model", "minecraft:equippable"}, path
        if "minecraft:equippable" in components:
            assert set(components["minecraft:equippable"]) == {"slot", "asset_id", "equip_sound"}
            assert components["minecraft:equippable"]["slot"] == "head"


def test_reset_covers_every_item_a_skin_can_go_on():
    data = wardrobe.datapack_files()
    blades = json.loads(data["data/monkey/tags/item/wardrobe_blades.json"])["values"]
    helms = json.loads(data["data/monkey/tags/item/wardrobe_helms.json"])["values"]
    for item in blades + helms:
        name = item.split(":")[1]
        assert f"data/monkey/item_modifier/wardrobe/reset/{name}.json" in data


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


def test_challenge_and_launch_rewards_are_scores_and_skins_only():
    """What the weekly challenges and the launch weekend give is a score (and through it a skin): never an item,
    an effect, experience or a stat. Their functions run only these commands, and their advancements reward only
    a function."""
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


@pytest.mark.parametrize("eol", [b"\n", b"\r\n"])
def test_enable_in_options_adds_the_pack_once_and_keeps_line_endings(tmp_path, eol):
    options = tmp_path / "options.txt"
    options.write_bytes(eol.join([b"fov:0.5", b'resourcePacks:["vanilla","file/x.zip"]', b"lang:en_us"]) + eol)
    wardrobe.enable_in_options(options)
    wardrobe.enable_in_options(options)
    assert options.read_bytes() == eol.join(
        [b"fov:0.5", b'resourcePacks:["vanilla","file/x.zip","file/Monkey SMP Wardrobe"]', b"lang:en_us"]) + eol


def test_enable_in_options_without_a_resource_pack_line(tmp_path):
    options = tmp_path / "options.txt"
    options.write_text("fov:0.5\n", encoding="utf-8")
    wardrobe.enable_in_options(options)
    assert options.read_text(encoding="utf-8") == 'fov:0.5\nresourcePacks:["vanilla","file/Monkey SMP Wardrobe"]\n'


def png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


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


def test_season_skins_come_from_the_season_number_and_keep_every_trigger_value():
    """Season II's blade is everyone's who plays while #season is 2, as Founder's Edge is Season I's. It and the
    champion's helm were added at the end of their lists, so no Season I skin's trigger value moved."""
    data = wardrobe.datapack_files()
    second = data["data/monkey/function/wardrobe/second.mcfunction"]
    assert "execute if score #season rw.day matches 2 run scoreboard players set @a rw.s2 1" in second
    values = {s["id"]: value for value, _, s in wardrobe.skins()}
    assert (values["pinnacle"], values["twinmoon"]) == (118, 119)
    assert (values["founders_circlet"], values["champions_helm"]) == (208, 209)
    for objective in (*wardrobe.SEASON_SKINS, wardrobe.CHAMPION):
        assert objective not in wardrobe.SOLD and objective in wardrobe.NOTIFY
        assert wardrobe.page((objective, 1)) == wardrobe.MENU_CHALLENGES
    assert wardrobe.how_to_unlock(("rw.s2", 1)) == "Played during Season II"
    assert wardrobe.earned_for((wardrobe.CHAMPION, 1)) == "winning the season"


def test_later_season_skins_stay_out_of_season_ones_menu_until_owned():
    """Season I's menu doesn't change: a skin with shown_from shows locked only from that season, and owned
    whenever its score says so (the champion's helm is set in Season I's world, after the finale)."""
    menu = wardrobe.datapack_files()["data/monkey/function/wardrobe/menu_challenges.mcfunction"].splitlines()
    gated = [s for _, _, s in wardrobe.skins() if "shown_from" in s]
    assert {s["id"] for s in gated} == {"twinmoon", "champions_helm"}
    for s in gated:
        objective, n = s["unlock"]
        locked = [line for line in menu if line.startswith(f"execute unless score @s {objective} matches {n}.. ")]
        owned = [line for line in menu if line.startswith(f"execute if score @s {objective} matches {n}.. run ")]
        assert len(locked) == 1 and f" if score #season rw.day matches {s['shown_from']}.. run tellraw" in locked[0]
        assert len(owned) == 1
