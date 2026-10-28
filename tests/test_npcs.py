import json
import re

import challenges
import datapacks
import npcs
import rules
import season_calendar
import standings
from repo import REPO

FILES = npcs.datapack_files()
PRESETS = {name: npcs.preset(name) for name in npcs.NPCS}


def walk(value):
    """Every dict inside a preset."""
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v)


def actions(name: str) -> list[dict]:
    return [a for d in walk(PRESETS[name]) for a in d.get("Actions", [])]


def test_easy_npc_is_pinned_at_the_tested_version():
    mods = {m["slug"]: m for m in REPO.load_manifest()["mods"]}
    for slug in ("easy-npc", "easy-npc-core", "easy-npc-config-ui"):
        assert mods[slug]["version"].endswith(npcs.EASY_NPC), slug
        assert f"-{datapacks.MINECRAFT}-" in mods[slug]["file"], slug


def test_every_named_dialog_exists_and_labels_fit():
    for name, preset in PRESETS.items():
        dialogs = preset["data"]["DialogData"]["DialogDataSet"]
        labels = [d["Label"] for d in dialogs]
        assert len(labels) == len(set(labels)), name
        buttons = [b["Label"] for d in dialogs for b in d["Buttons"]]
        assert len(buttons) == len(set(buttons)), name
        # Easy NPC cuts dialog and button labels at 32 characters.
        assert all(len(label) <= 32 for label in labels + buttons), name
        for a in actions(name):
            if a["Type"] == "OPEN_NAMED_DIALOG":
                assert a["Cmd"] in labels, f"{name}: no dialog {a['Cmd']}"
        # Exactly one dialog opens on a right-click whatever the player's scores: a fallback with no conditions.
        assert any(d["Priority"] >= 0 and "Conditions" not in d for d in dialogs), name


def test_buttons_set_triggers_the_data_packs_answer():
    tick = (REPO.realms / "datapacks/realms-wardrobe/data/realms/function/wardrobe/tick.mcfunction").read_text()
    answered = set(re.findall(r"scores=\{(\w+)=1\.\.\}", tick))
    answered |= set(re.findall(r"scores=\{(\w+)=1\.\.\}", "".join(standings.datapack_files().values())))
    used = {a["Cmd"].split(":")[1] for name in PRESETS for a in actions(name) if a["Type"] == "SCOREBOARD"}
    assert used == set(npcs.TRIGGERS)
    assert used <= answered, used - answered
    triggers = {o for o, crit in challenges.objectives() if crit == "trigger"}
    assert "challenges" in triggers


def test_the_links_button_opens_the_pause_menu_dialog():
    assert f"data/{npcs.NS}/dialog/links.json" in rules.rules_files()
    commands = [a for name in PRESETS for a in actions(name) if a["Type"] == "COMMAND"]
    assert commands
    for a in commands:
        assert a["Cmd"] == f"/dialog show @initiator {npcs.LINKS_DIALOG}"
        assert a["PermLevel"] == 2 and "ExecAsUser" not in a   # run by the NPC: players can't use /dialog


def test_crier_has_a_dialog_for_every_week_of_the_season():
    dialogs = PRESETS["crier"]["data"]["DialogData"]["DialogDataSet"]
    weeks = {d["Conditions"][0]["Value"]: d for d in dialogs if "Conditions" in d}
    assert sorted(weeks) == list(range(npcs.LAST_WEEK + 1))
    for w, d in weeks.items():
        assert d["Conditions"] == [{"Name": "rc.seen", "Operation": "EQUALS", "Type": "SCOREBOARD", "Value": w}]
    # rc.seen is the week number the challenges keep for every online player.
    assert ("rc.seen", "dummy") in challenges.objectives()


def test_crier_names_each_weeks_event():
    for w in range(1, npcs.LAST_WEEK + 1):
        text = npcs.crier_text(w)
        assert npcs.EVENTS[w] in text and npcs.day(season_calendar.saturday(w)) in text
        if w < npcs.LAST_WEEK:
            assert npcs.EVENTS[w + 1] in text


def test_copy_is_plain_and_says_monkey_smp():
    texts = [d["Text"] for name in PRESETS for d in walk(PRESETS[name]) if "Text" in d]
    texts += [t for name in PRESETS for d in walk(PRESETS[name]) for t in d.get("Texts", []) if isinstance(t, str)]
    assert any("Monkey SMP" in t for t in texts)
    for t in texts:
        assert "Realms" not in t and "realms" not in t, t
        # Easy NPC reads <tags> as formatting: only line breaks are used.
        assert set(re.findall(r"<(/?\w+)>", t)) <= {"br"}, t
    # Every Discord channel named is one the rulebook names.
    channels = set(re.findall(r"#[a-z-]+", " ".join(texts)))
    assert channels and channels <= set(re.findall(r"#[a-z-]+", (REPO.root / "docs/RULES.md").read_text()))


def test_speech_bubbles_only():
    for name in PRESETS:
        for d in walk(PRESETS[name]):
            if d.get("Type") == "MESSAGE":
                assert d["Msg"]["T"] == 4 and len(d["Msg"]["Texts"]) <= 6   # no chat spam at spawn


def test_npcs_are_protected_and_kept():
    for name, preset in PRESETS.items():
        data = preset["data"]
        assert data["Invulnerable"] == 1 and data["PersistenceRequired"] == 1, name
        assert "Owner" not in json.dumps(data), name
        assert "access" not in preset["PresetMetadata"], name   # INTERNAL presets can't be imported by command


def test_uuids_are_fixed_and_distinct():
    ids = {npcs.npc_uuid(name) for name in npcs.NPCS}
    assert len(ids) == len(npcs.NPCS)
    for name in npcs.NPCS:
        for fn in ("place", "remove"):
            assert npcs.npc_uuid(name) in FILES[f"{npcs.FN}/{name}/{fn}.mcfunction"], (name, fn)


def test_placing_replaces_the_npc_and_turns_the_entity():
    for name in npcs.NPCS:
        npc = npcs.npc_uuid(name)
        place = [line for line in FILES[f"{npcs.FN}/{name}/place.mcfunction"].splitlines() if not line.startswith("#")]
        # Removed first, so a second placement leaves one NPC with nothing (an owner, an edit) left over.
        assert place[0] == f"easy_npc delete {npc}"
        assert place[1] == f"$easy_npc preset import data {npcs.preset_id(name)} $(x) $(y) $(z) {npc}"
        # The vanilla rotate turns the entity; Easy NPC's turns only the model, on top of where it looks.
        assert place[2] == f"$rotate {npc} $(yaw) 0"
        # Random Mob Sizes (in the pack since 2.8.0) skips mobs tagged global.ignore; untagged, the NPCs would
        # come out anywhere from 0.75 to 1.25 times their size.
        assert place[3] == f"tag {npc} add global.ignore"
        assert len(place) == 4


def test_here_places_through_a_marker_so_the_npc_has_no_owner():
    spot = FILES[f"{npcs.FN}/spot.mcfunction"]
    assert "$function realms:npcs/$(name)/place with storage" in spot and "kill @s[type=minecraft:marker]" in spot
    for name in npcs.NPCS:
        here = FILES[f"{npcs.FN}/{name}/here.mcfunction"]
        assert f'place.name set value "{name}"' in here
        assert "summon minecraft:marker run function realms:npcs/spot with storage" in here
        assert f"npcs/{name}/place with" not in here   # run as the admin, the import would make them its owner


def test_preset_ids_point_at_the_preset_files():
    for name in npcs.NPCS:
        ns, path = npcs.preset_id(name).split(":", 1)
        assert f"data/{ns}/{path}" in FILES


def test_every_npc_has_the_functions_its_macro_calls_name():
    # datapacks.problems() only knows $(name) is some function; the names are npcs.NPCS.
    for path, body in FILES.items():
        for called in re.findall(rf"function {npcs.NS}:([\w/]*\$\(name\)[\w/]*)", body):
            for name in npcs.NPCS:
                assert f"data/{npcs.NS}/function/{called.replace('$(name)', name)}.mcfunction" in FILES, path


def test_security_defaults_need_an_admin_for_every_feature():
    cfg = npcs.security_cfg()
    values = dict(line.split("=", 1) for line in cfg.splitlines() if "=" in line and not line.startswith("#"))
    assert {k for k in values if k.startswith("feature.")} == {f"feature.{f}" for f in npcs.FEATURES}
    assert all(values[f"feature.{f}"] == "ADMIN" for f in npcs.FEATURES)
    assert values["creativePlayerCommandLevel"] == "ALL"


def test_snbt_escapes_quotes_and_backslashes():
    assert npcs.snbt({"a b": 'say "hi" \\o/'}) == '{\n  "a b":"say \\"hi\\" \\\\o/"\n}'
    assert npcs.snbt([npcs.Byte(1), npcs.Long(2), 3]) == "[1b,2L,3]"
