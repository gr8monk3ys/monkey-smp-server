import json
import struct

import pytest

import wardrobe
from repo import REPO


def test_committed_packs_match_the_generator():
    assert wardrobe.differences(REPO) == [], "run python tools/wardrobe.py"


def test_pack_formats_follow_the_server_minecraft_version():
    # DATA_FORMAT and RESOURCE_FORMAT are 26.3's; a Minecraft update must bump them too.
    assert REPO.load_manifest()["minecraft"] == wardrobe.MINECRAFT


def test_trigger_values_are_unique_and_clear_of_the_menu_values():
    values = [v for v, _, _ in wardrobe.skins()]
    assert len(values) == len(set(values))
    assert min(values) > wardrobe.MENU_SUPPORT
    assert len({s["id"] for _, _, s in wardrobe.skins()}) == len(values)


def test_tenure_rewards_the_first_three_months():
    """A new buyer should unlock something at each of the first renewals, not wait half a year."""
    months = {s["unlock"][1] for _, _, s in wardrobe.skins() if s["unlock"][0] == "rw.months"}
    assert {1, 2, 3} <= months


def test_event_and_holiday_skins_are_never_sold():
    """Attendance and holiday skins are earned by showing up. No store command may set their scores."""
    earned = {s["unlock"][0] for _, _, s in wardrobe.skins()} - wardrobe.SOLD
    assert "rw.events" in earned and set(wardrobe.HOLIDAYS) <= earned
    events = sorted(s["unlock"][1] for _, _, s in wardrobe.skins() if s["unlock"][0] == "rw.events")
    assert events == [3, 10]
    store = [line for line in (REPO.root / "docs" / "RETENTION.md").read_text(encoding="utf-8").splitlines()
             if "{username}" in line]
    assert store
    for line in store:
        assert not any(objective in line for objective in earned), line


def test_every_unlock_score_exists_and_announces_itself():
    data = wardrobe.datapack_files()
    load = data["data/realms/function/wardrobe/load.mcfunction"]
    second = data["data/realms/function/wardrobe/second.mcfunction"]
    for _, _, s in wardrobe.skins():
        objective, n = s["unlock"]
        assert f"scoreboard objectives add {objective} " in load
        if objective in wardrobe.NOTIFY:
            notice = data[f"data/realms/function/wardrobe/notice/{objective[3:]}.mcfunction"]
            assert f"matches {n}.. unless score @s {objective}.seen matches {n}.. run tellraw" in notice
            assert f"{objective}.seen" in load and f"function realms:wardrobe/notice/{objective[3:]}" in second


def test_hours_include_play_carried_from_earlier_worlds():
    second = wardrobe.datapack_files()["data/realms/function/wardrobe/second.mcfunction"].splitlines()
    play = second.index("execute as @a run scoreboard players operation @s rw.hours = @s rw.play")
    assert second[play + 1] == "execute as @a run scoreboard players operation @s rw.hours += @s rw.playbase"
    assert second[play + 2] == "scoreboard players operation @a rw.hours /= #hour rw.const"


def test_each_menu_page_fits_open_chat():
    """Open chat shows 20 lines. Each page prints a header (two lines), the counts, one title per item kind,
    one line per skin and the footer."""
    data = wardrobe.datapack_files()
    use = data["data/realms/function/wardrobe/use.mcfunction"]
    for number, name in ((1, "menu"), (wardrobe.MENU_SUPPORT, "menu_support")):
        assert f"matches {number} run function realms:wardrobe/{name}" in use
        menu = data[f"data/realms/function/wardrobe/{name}.mcfunction"]
        on_page = [(kind, s) for _, kind, s in wardrobe.skins() if wardrobe.page(s["unlock"]) == number]
        for _, s in on_page:
            assert f'"text":"[{s["name"]}]"' in menu
        assert 2 + 1 + len({kind for kind, _ in on_page}) + len(on_page) + 1 <= 20
    assert sum(1 for _ in wardrobe.skins()) == sum(
        1 for _, _, s in wardrobe.skins() if wardrobe.page(s["unlock"]) in (1, wardrobe.MENU_SUPPORT))


def test_the_docs_list_every_skin():
    doc = (REPO.root / "docs" / "RETENTION.md").read_text(encoding="utf-8")
    for _, kind, s in wardrobe.skins():
        objective, n = s["unlock"]
        assert f"| {s['name']} | {kind} |" in doc and f"`{objective} {n}`" in doc, s["name"]


def test_every_skin_is_wired_end_to_end():
    data = wardrobe.datapack_files()
    res = wardrobe.resourcepack_files()
    use = data["data/realms/function/wardrobe/use.mcfunction"]
    for value, kind, s in wardrobe.skins():
        sid = s["id"]
        assert f"matches {value} run function realms:wardrobe/skin/{sid}" in use
        assert f"realms:wardrobe/{sid}" in data[f"data/realms/function/wardrobe/skin/{sid}.mcfunction"]
        assert f"data/realms/item_modifier/wardrobe/{sid}.json" in data
        assert f"assets/realms/items/{sid}.json" in res
        assert f"assets/realms/models/item/{sid}.json" in res
        assert png_size(res[f"assets/realms/textures/item/{sid}.png"]) == (16, 16)
        if kind == "helm":
            assert f"assets/realms/equipment/{sid}.json" in res
            assert png_size(res[f"assets/realms/textures/entity/equipment/humanoid/{sid}.png"]) == (64, 32)


def test_skins_change_the_look_and_nothing_else():
    """Mojang's usage guidelines: what supporters get must be cosmetic. A skin may only touch the model,
    and on a helmet the worn look; never damage, armor, durability or enchantments."""
    data = wardrobe.datapack_files()
    modifiers = {path for path in data if "/item_modifier/" in path}
    # Every skin, the new ones included, goes through this check: no skin may apply anything but a modifier.
    assert {f"data/realms/item_modifier/wardrobe/{s['id']}.json" for _, _, s in wardrobe.skins()} <= modifiers
    for path, text in data.items():
        if "/function/" in path:
            assert "item replace" not in text and "attribute" not in text and "enchant" not in text, path
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
    blades = json.loads(data["data/realms/tags/item/wardrobe_blades.json"])["values"]
    helms = json.loads(data["data/realms/tags/item/wardrobe_helms.json"])["values"]
    for item in blades + helms:
        name = item.split(":")[1]
        assert f"data/realms/item_modifier/wardrobe/reset/{name}.json" in data


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
