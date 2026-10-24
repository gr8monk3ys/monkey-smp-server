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
    assert min(values) > 3
    assert len({s["id"] for _, _, s in wardrobe.skins()}) == len(values)


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
    for path, text in wardrobe.datapack_files().items():
        if "/item_modifier/" not in path:
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
