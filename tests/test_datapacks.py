import json

import pytest

import datapacks
from repo import REPO

FILES = datapacks.all_files()


def test_committed_packs_match_the_generators():
    assert datapacks.differences(REPO) == [], "run python tools/datapacks.py"


def test_formats_follow_the_server_minecraft_version():
    # DATA_FORMAT, wardrobe's RESOURCE_FORMAT and rules' VANILLA_NON_TREASURE are 26.3's: a Minecraft update must
    # bump or re-check them all.
    assert REPO.load_manifest()["minecraft"] == datapacks.MINECRAFT


def test_every_generator_has_a_pack():
    for name, gen in datapacks.generators().items():
        assert gen.packs(REPO), name


def test_the_shipped_packs_have_no_problems():
    assert datapacks.problems(FILES) == []


PACK = {
    "p/pack.mcmeta": datapacks.mcmeta("test"),
    "p/data/minecraft/tags/function/load.json": datapacks.function_tag("realms:load"),
    "p/data/realms/function/load.mcfunction": datapacks.lines("scoreboard objectives add t.a dummy",
                                                             "function realms:go/north"),
    "p/data/realms/function/go/north.mcfunction": datapacks.lines("$say $(where)", "scoreboard players add @s t.a 1"),
}


def test_a_clean_pack_has_no_problems():
    assert datapacks.problems(PACK) == []


@pytest.mark.parametrize(("path", "body", "problem"), [
    ("p/data/realms/function/x.mcfunction", "function realms:nowhere\n", "calls realms:nowhere"),
    ("p/data/realms/function/x.mcfunction", "$function realms:go/$(dir)\n", None),
    ("p/data/realms/function/x.mcfunction", "$function realms:stay/$(dir)\n", "calls realms:stay/$(dir)"),
    ("p/data/realms/function/x.mcfunction", "say $(who)\n", "macro marker"),
    ("p/data/realms/function/x.mcfunction", "$say hello\n", "macro marker"),
    ("p/data/realms/function/x.mcfunction", "scoreboard players add @s t.missing 1\n", "objective t.missing"),
    ("p/data/realms/function/x.mcfunction", "execute if score #a t.missing matches 1 run say hi\n",
     "objective t.missing"),
    ("p/data/realms/function/x.mcfunction", "say hi\r\n", "line endings"),
    ("p/data/realms/function/x.mcfunction", "say hi", "line endings"),
    ("p/data/realms/x.json", "{\n", "p/data/realms/x.json"),
    ("p/pack.mcmeta", datapacks.mcmeta("old", fmt=1), "format isn't"),
    ("p/data/minecraft/tags/function/tick.json", datapacks.function_tag("realms:gone"), "lists realms:gone"),
])
def test_problems_catches(path, body, problem):
    found = datapacks.problems({**PACK, path: body})
    if problem is None:
        assert found == []
    else:
        assert found and all(problem in p for p in found), found


def test_objectives_made_by_other_mods_count_as_created():
    body = "".join(f"scoreboard players get @s {o}\n" for o in datapacks.EXTERNAL_OBJECTIVES)
    assert datapacks.problems({**PACK, "p/data/realms/function/x.mcfunction": body}) == []


def test_text_and_mcmeta_shapes():
    assert datapacks.text("hi") == '"hi"'
    assert json.loads(datapacks.text({"text": "a"}, "b")) == [{"text": "a"}, "b"]
    pack = json.loads(datapacks.mcmeta("d"))["pack"]
    assert pack["min_format"] == pack["max_format"] == datapacks.DATA_FORMAT


def test_check_reports_up_to_date(capsys):
    assert datapacks.main(["--check"]) == 0
    assert "up to date" in capsys.readouterr().out
