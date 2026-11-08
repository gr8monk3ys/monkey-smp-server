import json
from pathlib import Path

import repairs

from datapacks import DATA_FORMAT


def test_tag_adds_diamond_and_keeps_the_ingot():
    tag = json.loads(repairs.datapack_files()[repairs.TAG])
    assert tag == {"replace": False, "values": ["minecraft:diamond"]}


def test_pack_format_matches_the_other_packs():
    meta = json.loads(repairs.datapack_files()["pack.mcmeta"])["pack"]
    assert meta["min_format"] == meta["max_format"] == DATA_FORMAT


def test_generated_pack_is_checked_in():
    root = Path(__file__).resolve().parent.parent / "package/monkey/datapacks" / repairs.DATAPACK
    for rel, text in repairs.datapack_files().items():
        assert (root / rel).read_text(encoding="utf-8") == text
