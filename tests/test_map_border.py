import gzip
import shutil
import struct

import pytest

import map_border
import rules
from repo import REPO

DEFAULT_MAPS = REPO.defaults / map_border.MAPS
# Where the pinned seed (manifest world.seed) puts spawn, and so the border's centre: read from a fresh 2.4
# world. The Nether's is spawn / 8, shifted half a block by `worldborder center`.
SPAWN = (-80.0, 416.0)
NETHER_CENTRE = (-9.5, 52.5)


def nbt_string(s: str) -> bytes:
    raw = s.encode("utf-8")
    return struct.pack(">H", len(raw)) + raw


def border_dat(center_x: float, center_z: float, size: float, lerp_target: float | None = None) -> bytes:
    """A world_border.dat as 26.3 writes it (only the fields the tool reads, plus a few it skips)."""
    data = b"".join(
        b"\x06" + nbt_string(name) + struct.pack(">d", value)
        for name, value in (("center_x", center_x), ("center_z", center_z), ("size", size),
                            ("lerp_target", size if lerp_target is None else lerp_target))
    )
    data += b"\x04" + nbt_string("lerp_time") + struct.pack(">q", 0)
    data += b"\x03" + nbt_string("warning_blocks") + struct.pack(">i", 5)
    root = b"\x03" + nbt_string("DataVersion") + struct.pack(">i", 5023) + b"\x0a" + nbt_string("data") + data + b"\x00"
    return gzip.compress(b"\x0a" + nbt_string("") + root + b"\x00")


def server(tmp_path, borders: dict, maps=DEFAULT_MAPS):
    """A server folder with the given map configs and a saved border per dimension."""
    shutil.copytree(maps, tmp_path / map_border.MAPS)
    for dimension, values in borders.items():
        path = map_border.border_file(tmp_path, "world", dimension)
        path.parent.mkdir(parents=True)
        path.write_bytes(border_dat(*values))
    return tmp_path


SEASON_ONE = {
    "minecraft:overworld": (*SPAWN, rules.BORDER),
    "minecraft:the_nether": (*NETHER_CENTRE, rules.BORDER / 8),
    "minecraft:the_end": (0.0, 0.0, map_border.NO_BORDER),
}


def masks(server_dir):
    return {fit.id: fit.border.mask() if fit.border else None for fit in map_border.fit_maps(server_dir)}


def test_the_shipped_masks_are_season_ones_starting_border(tmp_path):
    # The defaults are fitted to Rule 25's 2500 border (and the Nether's 312.5) around the pinned spawn.
    assert map_border.main([str(server(tmp_path, SEASON_ONE)), "--check"]) == 0
    assert masks(tmp_path) == {
        "world": {"min-x": -1330, "max-x": 1169, "min-z": -834, "max-z": 1665},
        "world_the_nether": {"min-x": -166, "max-x": 146, "min-z": -104, "max-z": 208},
        "world_the_end": None,
    }


def test_the_shipped_maps_are_the_worlds_bluemap_would_make():
    # Shipping maps/ stops BlueMap writing its own, so all three dimensions have to be there.
    found = {conf.stem: map_border.settings(conf.read_text(encoding="utf-8")) for conf in DEFAULT_MAPS.glob("*.conf")}
    level = REPO.load_manifest()["world"]["level_name"]
    assert {k: (v["world"], v["dimension"]) for k, v in found.items()} == {
        level: (level, "minecraft:overworld"),
        f"{level}_the_nether": (level, "minecraft:the_nether"),
        f"{level}_the_end": (level, "minecraft:the_end"),
    }


def test_the_nether_map_cuts_everything_from_y_90_up():
    # Incendium makes the Nether 192 tall: a ceiling cut that stops at 127 (BlueMap's own) leaves the bedrock
    # roof covering the map, so the cut has no top.
    nether = (DEFAULT_MAPS / "world_the_nether.conf").read_text(encoding="utf-8")
    ceiling = nether.split("subtract: true", 1)[1].split("}", 1)[0]
    assert "min-y: 90" in ceiling
    assert "max-y" not in ceiling


def test_a_border_act_widens_the_masks_and_keeps_the_nether_ceiling(tmp_path, capsys):
    grown = {**SEASON_ONE, "minecraft:overworld": (*SPAWN, 4000.0), "minecraft:the_nether": (*NETHER_CENTRE, 500.0)}
    server(tmp_path, grown)
    end_before = (tmp_path / map_border.MAPS / "world_the_end.conf").read_bytes()

    assert map_border.main([str(tmp_path), "--check"]) == 1
    assert map_border.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "bluemap reload" in out and "bluemap purge world\n" in out and "bluemap purge world_the_nether" in out
    assert "purge world_the_end" not in out
    assert masks(tmp_path)["world"] == {"min-x": -2080, "max-x": 1919, "min-z": -1584, "max-z": 2415}
    nether = (tmp_path / map_border.MAPS / "world_the_nether.conf").read_text(encoding="utf-8")
    assert "subtract: true\n    min-y: 90\n  }" in nether
    assert nether.count(map_border.MARK) == 1
    assert (tmp_path / map_border.MAPS / "world_the_end.conf").read_bytes() == end_before
    assert map_border.main([str(tmp_path), "--check"]) == 0  # running it again changes nothing


def test_a_growing_border_counts_at_its_final_size(tmp_path):
    server(tmp_path, {**SEASON_ONE, "minecraft:overworld": (*SPAWN, 2600.0, 6000.0)})
    assert masks(tmp_path)["world"] == {"min-x": -3080, "max-x": 2919, "min-z": -2584, "max-z": 3415}


GENERATED_NETHER = """world: "world"
dimension: "minecraft:the_nether"
render-mask: [
  {
    #min-x: -4000
    #max-x: 4000
  }
  {
    # This removes everything at and between y 90 and 127 (the Nether's ceiling).
    subtract: true
    min-y: 90
    max-y: 127
  }
]
render-edges: true
"""


def test_a_config_bluemap_wrote_itself_gets_the_mask(tmp_path):
    # A server that predates the shipped defaults has BlueMap's own files, with an empty first layer.
    maps = tmp_path / "bluemap-maps"
    maps.mkdir()
    (maps / "world_the_nether.conf").write_text(GENERATED_NETHER, encoding="utf-8", newline="")
    srv = server(tmp_path / "server", {"minecraft:the_nether": (*NETHER_CENTRE, 312.5)}, maps)

    assert map_border.main([str(srv)]) == 0
    assert (srv / map_border.MAPS / "world_the_nether.conf").read_text(encoding="utf-8") == GENERATED_NETHER.replace(
        "    #min-x: -4000\n    #max-x: 4000\n",
        f"    {map_border.MARK}\n    min-x: -166\n    max-x: 146\n    min-z: -104\n    max-z: 208\n",
    )


def test_a_hand_made_first_layer_is_left_for_a_person(tmp_path, capsys):
    maps = tmp_path / "bluemap-maps"
    maps.mkdir()
    hand_made = GENERATED_NETHER.replace("#min-x: -4000", "subtract: true")
    (maps / "world_the_nether.conf").write_text(hand_made, encoding="utf-8")
    srv = server(tmp_path / "server", {"minecraft:the_nether": (*NETHER_CENTRE, 312.5)}, maps)
    assert map_border.main([str(srv)]) == 2
    assert "subtract: true" in capsys.readouterr().err


@pytest.mark.parametrize("dimension", ["minecraft:overworld", "minecraft:the_nether"])
def test_a_world_never_saved_is_an_error_not_an_empty_mask(tmp_path, capsys, dimension):
    borders = {k: v for k, v in SEASON_ONE.items() if k != dimension}
    assert map_border.main([str(server(tmp_path, borders))]) == 2
    assert "no border saved" in capsys.readouterr().err
