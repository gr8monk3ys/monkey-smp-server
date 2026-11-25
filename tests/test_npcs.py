import json
import re

import challenges
import datapacks
import npcs
import rules
import season_calendar
from repo import REPO

FILES = npcs.datapack_files()
DIALOGS = npcs.dialogs()
ADMIN = (REPO.root / "docs/ADMIN.md").read_text(encoding="utf-8")
GROUPS = REPO.defaults / "plugins/LuckPerms/yaml-storage/groups"


def body(path: str) -> list[str]:
    """A function's commands, comments left out."""
    return [line for line in FILES[path].splitlines() if not line.startswith("#")]


def talk_file(name: str) -> str:
    return f"{npcs.FN}/{name}/talk.mcfunction"


def actions(d: dict) -> list[dict]:
    return [b["action"] for b in d["actions"]]


def texts() -> list[str]:
    return [m["contents"] for d in DIALOGS.values() for m in d["body"]]


def test_the_pack_is_two_talk_functions_and_their_dialogs():
    assert set(FILES) == {"pack.mcmeta", *(talk_file(n) for n in npcs.NPCS),
                          *(f"{npcs.DIALOGS}/{p}.json" for p in DIALOGS)}
    for path, d in DIALOGS.items():
        assert json.loads(FILES[f"{npcs.DIALOGS}/{path}.json"]) == d
    # Calls, objectives read and JSON, checked across every pack (rq.guide and rc.seen are other packs').
    assert not [e for e in datapacks.problems(datapacks.all_files()) if e.startswith(f"{npcs.DATAPACK}/")]


def test_nothing_of_easy_npc_is_left():
    assert not any(re.search(r"easy.?npc|preset", text, re.I) for text in [*FILES, *FILES.values()])
    assert not (REPO.defaults / "config" / "easy_npc").exists()
    assert not (REPO.root / "deploy" / "npc-claims.sh").exists()


def test_the_staff_commands_make_each_npc_run_its_talk_function_from_the_console():
    for name, (title, color, _about) in npcs.NPCS.items():
        cmds = npcs.staff_commands(name)
        assert cmds[0] == f"/npc create {name}"
        assert f"/npc displayname {name} <{color}>{title}</{color}>" in cmds
        assert f"/npc turn_to_player {name} true" in cmds
        action = [c for c in cmds if c.startswith(f"/npc action {name} ")]
        # One right-click action, run as the console with the clicking player's name put in for {player}.
        assert action == [f"/npc action {name} RIGHT_CLICK add console_command "
                          f"execute as {{player}} run function monkey:npcs/{name}/talk"]
        assert f"data/monkey/function/npcs/{name}/talk.mcfunction" in FILES
        # The names FancyNpcs takes: A-Z a-z 0-9 _ - /
        assert re.fullmatch(r"[A-Za-z0-9_/-]+", name)


def test_admin_md_gives_the_same_staff_commands_and_the_permission_warning():
    section = ADMIN.split("## Spawn NPCs", 1)[1].split("\n## ", 1)[0]
    for name in npcs.NPCS:
        for cmd in npcs.staff_commands(name):
            assert cmd in section, cmd
    assert "fancynpcs.*" in section and "console" in section
    assert "Easy NPC" not in ADMIN


def test_only_admins_get_fancynpcs_permissions():
    # An NPC's console command runs as the server: whoever may add one may run anything.
    for group in GROUPS.glob("*.yml"):
        text = group.read_text(encoding="utf-8")
        if group.stem == "admin":
            assert "- '*'" in text
            continue
        assert "fancynpcs" not in text.lower() and "'*'" not in text, group.name


def test_talking_to_the_guide_counts_the_quest_step_and_opens_its_dialog():
    guide = body(talk_file("guide"))
    # Run by hand from the console (no player), it says how to run it instead of failing on @s.
    assert guide[0].startswith("execute unless entity @s[type=minecraft:player] run return run say ")
    assert guide[1:] == ["scoreboard players set @s rq.guide 1", "dialog show @s monkey:npcs/guide"]


def test_every_dialog_a_button_shows_exists():
    known = {npcs.dialog_id(p) for p in DIALOGS} | {npcs.LINKS_DIALOG}
    assert f"data/{npcs.NS}/dialog/links.json" in rules.rules_files()
    shown = {a["dialog"] for d in DIALOGS.values() for a in actions(d) if a["type"] == "minecraft:show_dialog"}
    assert npcs.LINKS_DIALOG in shown
    assert shown <= known, shown - known
    for d in DIALOGS.values():
        assert {a["type"] for a in actions(d)} <= {"minecraft:show_dialog", "minecraft:run_command"}
        labels = [b["label"] for b in d["actions"]]
        assert len(labels) == len(set(labels))


def test_the_guide_keeps_its_buttons():
    labels = {b["label"]: b["action"] for b in DIALOGS["guide"]["actions"]}
    assert list(labels) == ["The short rules", "Find a faction", "Your first week", "This week's challenges",
                            "Faction standings", "Your progress"]
    assert labels["The short rules"] == npcs.show("monkey:npcs/guide/rules")
    assert labels["Find a faction"] == npcs.show("monkey:npcs/guide/factions")
    assert labels["Your first week"] == npcs.trigger("quest")
    assert labels["This week's challenges"] == npcs.trigger("challenges")
    assert labels["Faction standings"] == npcs.trigger("standings")
    assert labels["Your progress"] == npcs.trigger("wardrobe")
    for page, link in (("guide/rules", "Discord and links"), ("guide/factions", "Open the Discord")):
        page_labels = {b["label"]: b["action"] for b in DIALOGS[page]["actions"]}
        assert page_labels == {link: npcs.show(npcs.LINKS_DIALOG), "Back": npcs.show("monkey:npcs/guide")}


def test_buttons_run_triggers_every_player_has_and_the_data_packs_answer():
    packs = "".join(datapacks.all_files().values())
    answered = set(re.findall(r"scores=\{(\w+)=1\.\.\}", packs))
    enabled = set(re.findall(r"scoreboard players enable @a (\w+)", packs))
    commands = [a["command"] for d in DIALOGS.values() for a in actions(d) if a["type"] == "minecraft:run_command"]
    assert all(re.fullmatch(r"/trigger \w+", c) for c in commands), commands
    used = {c.removeprefix("/trigger ") for c in commands}
    assert used == set(npcs.TRIGGERS)
    assert used <= answered, used - answered
    # The player runs /trigger themselves, so it has to be enabled for them (the packs enable it every second).
    assert used <= enabled, used - enabled


def test_the_crier_shows_the_dialog_for_the_players_week():
    crier = body(talk_file("crier"))
    assert crier[1:-1] == [f"execute if score @s rc.seen matches {w} run return run dialog show @s "
                           f"monkey:npcs/crier/week{w}" for w in range(npcs.LAST_WEEK + 1)]
    assert crier[-1] == "dialog show @s monkey:npcs/crier/other"
    for w in range(npcs.LAST_WEEK + 1):
        d = DIALOGS[f"crier/week{w}"]
        assert "\n\n".join(m["contents"] for m in d["body"]) == npcs.crier_text(w)
        assert actions(d) == [npcs.trigger("challenges")]
    assert "\n\n".join(m["contents"] for m in DIALOGS["crier/other"]["body"]) == npcs.CRIER_OTHER
    # rc.seen is the week number the challenges keep for every online player.
    assert ("rc.seen", "dummy") in challenges.objectives()


def test_crier_names_each_weeks_event():
    for w in range(1, npcs.LAST_WEEK + 1):
        text = npcs.crier_text(w)
        assert npcs.EVENTS[w] in text and npcs.day(season_calendar.saturday(w)) in text
        if w < npcs.LAST_WEEK:
            assert npcs.EVENTS[w + 1] in text


def test_copy_is_plain_and_says_monkey_smp():
    all_text = texts()
    assert any("Monkey SMP" in t for t in all_text)
    for t in all_text:
        # Plain strings: no tags such as <br>, and no @initiator.
        assert "<" not in t and "@initiator" not in t, t
    # Every Discord channel named is one the rulebook names.
    channels = set(re.findall(r"#[a-z-]+", " ".join(all_text)))
    assert channels and channels <= set(re.findall(r"#[a-z-]+", (REPO.root / "docs/RULES.md").read_text()))


def test_dialogs_are_headed_with_the_npcs_name():
    for path, d in DIALOGS.items():
        title, color, _about = npcs.NPCS[path.split("/")[0]]
        assert d["title"] == {"text": title, "color": color}
        assert d["type"] == "minecraft:multi_action" and "exit_action" in d
