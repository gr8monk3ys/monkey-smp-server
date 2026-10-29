import gzip
import struct
import zlib

import migrate_names as mn
import pytest
from nbt_writer import nbt

import nbt as nbt_reader

OLD_NS, OLD_PACK, OLD_TAG = "realms", "realms-carry", "realms.joined"


def region(chunks: dict[int, bytes], kind: int = mn.ZLIB) -> bytes:
    """A region file holding each chunk's NBT at its header index."""
    header, body, sector = bytearray(2 * mn.SECTOR), bytearray(), 2
    for i, raw in chunks.items():
        payload = bytes([kind]) + (zlib.compress(raw) if kind == mn.ZLIB else gzip.compress(raw))
        blob = struct.pack(">I", len(payload)) + payload
        blob += b"\0" * (-len(blob) % mn.SECTOR)
        struct.pack_into(">I", header, i * 4, sector << 8 | len(blob) // mn.SECTOR)
        body += blob
        sector += len(blob) // mn.SECTOR
    return bytes(header) + bytes(body)


def chunks_of(data: bytes) -> dict[int, dict]:
    out = {}
    for i in range(1024):
        loc = struct.unpack_from(">I", data, i * 4)[0]
        if loc >> 8:
            pos = (loc >> 8) * mn.SECTOR
            length = struct.unpack_from(">I", data, pos)[0]
            kind, payload = data[pos + 4], data[pos + 5:pos + 4 + length]
            out[i] = nbt_reader.read(zlib.decompress(payload) if kind == mn.ZLIB else gzip.decompress(payload))
    return out


def test_swap_keeps_case_length_and_vanilla_names():
    text = b"The Realms TheRealms the-realms the_realms REALMS_X Realms realms:rules realmsNotifications"
    new = mn.swap(text)
    assert new == b"Monkey SMP MonkeySMP monkey-smp monkey_smp MONKEY_X Monkey monkey:rules realmsNotifications"
    assert len(new) == len(text)
    assert mn.swap(new) == new


def test_nbt_strings_keep_their_length_prefix_gzipped_or_not():
    value = {"Data": {"ScheduledEvents": [{"Name": f"{OLD_NS}:rules/second"}], "Tags": [OLD_TAG]}}
    for gzipped in (True, False):
        new = mn.swap_nbt(nbt(value, gzipped=gzipped))
        assert (new[:2] == b"\x1f\x8b") is gzipped
        data = nbt_reader.read(new)["Data"]
        assert data["ScheduledEvents"][0]["Name"] == "monkey:rules/second" and data["Tags"] == ["monkey.joined"]


def test_nbt_without_old_names_comes_back_byte_for_byte():
    data = nbt({"Data": {"x": "minecraft:stone"}}, gzipped=True)
    assert mn.swap_nbt(data) is data


def test_region_swaps_only_changed_chunks_and_relays_out_the_file():
    big = {"Entities": [{"CustomName": "x" * 9000, "Tags": [OLD_TAG]}]}   # grows past one sector
    plain = {"Status": "minecraft:full"}
    data = region({0: nbt(plain), 5: nbt(big), 1023: nbt({"Tags": [OLD_TAG]})})
    new = mn.swap_region(data, "r.0.0.mca")
    assert len(new) % mn.SECTOR == 0
    chunks = chunks_of(new)
    assert chunks[0] == plain
    assert chunks[5]["Entities"][0]["Tags"] == ["monkey.joined"] and chunks[1023]["Tags"] == ["monkey.joined"]
    assert mn.swap_region(new) == new


def test_region_without_old_names_and_empty_region_are_left_alone():
    data = region({3: nbt({"Status": "minecraft:full"})}, kind=mn.GZIP)
    assert mn.swap_region(data) is data
    assert mn.swap_region(b"") == b""


def test_region_with_lz4_chunks_stops_with_a_message():
    data = bytearray(region({0: nbt({"a": "b"})}))
    data[2 * mn.SECTOR + 4] = mn.LZ4
    with pytest.raises(ValueError, match="compression 4"):
        mn.swap_region(bytes(data), "r.0.0.mca")


def server(tmp_path):
    """A server folder installed before 2.10.0, with what the migration has to find."""
    root = tmp_path / "pkg"
    world = root / "server" / "world"
    (world / "datapacks" / OLD_PACK / "data" / OLD_NS / "function").mkdir(parents=True)
    (world / "datapacks" / OLD_PACK / "data" / OLD_NS / "function" / "load.mcfunction").write_text(
        f"scoreboard objectives add {OLD_NS}.grace dummy\nschedule function {OLD_NS}:carry/tick 1t\n")
    (world / "data" / OLD_NS).mkdir(parents=True)
    (world / "data" / OLD_NS / "command_storage.dat").write_bytes(
        nbt({"data": {"contents": {"factions": {"n": 1}}}}, gzipped=True))
    (world / "level.dat").write_bytes(nbt({"Data": {"DataPacks": {"Enabled": [f"file/{OLD_PACK}"]}}}, gzipped=True))
    (world / "entities").mkdir()
    (world / "entities" / "r.0.0.mca").write_bytes(region({7: nbt({"Tags": [OLD_TAG]})}))
    (world / "players" / "advancements").mkdir(parents=True)
    (world / "players" / "advancements" / "a.json").write_text(f'{{"{OLD_NS}:joined": {{"done": true}}}}')
    (root / "server" / f".{OLD_NS}-state.json").write_text(f'{{"datapacks": ["world/datapacks/{OLD_PACK}"]}}')
    (root / "server" / "logs").mkdir()
    (root / "server" / "logs" / "latest.log").write_text(f"{OLD_NS} stays in the logs")
    (root / "server" / "mods").mkdir()
    (root / "server" / "mods" / f"{OLD_NS}-patch.jar").write_bytes(b"PK\x03\x04 realms")
    (root / "docker").mkdir()
    (root / "docker" / ".env").write_text(f"{OLD_NS.upper()}_MAP=1\n")
    return root


def test_migrates_a_server_folder_and_a_second_run_finds_nothing(tmp_path, capsys):
    root = server(tmp_path)
    assert mn.main([str(root)]) == 0
    assert "Add --apply" in capsys.readouterr().out
    assert (root / "server" / "world" / "datapacks" / OLD_PACK).is_dir()   # a dry run writes nothing

    assert mn.main([str(root), "--apply"]) == 0
    world = root / "server" / "world"
    load = world / "datapacks" / "monkey-carry" / "data" / "monkey" / "function" / "load.mcfunction"
    assert load.read_text() == "scoreboard objectives add monkey.grace dummy\nschedule function monkey:carry/tick 1t\n"
    assert not (world / "datapacks" / OLD_PACK).exists() and not (world / "data" / OLD_NS).exists()
    assert nbt_reader.read(world / "data" / "monkey" / "command_storage.dat")["data"]["contents"]["factions"]
    assert nbt_reader.read(world / "level.dat")["Data"]["DataPacks"]["Enabled"] == ["file/monkey-carry"]
    assert chunks_of((world / "entities" / "r.0.0.mca").read_bytes())[7]["Tags"] == ["monkey.joined"]
    assert "monkey:joined" in (world / "players" / "advancements" / "a.json").read_text()
    state = root / "server" / ".monkey-state.json"
    assert state.read_text() == '{"datapacks": ["world/datapacks/monkey-carry"]}'
    assert (root / "docker" / ".env").read_text() == "MONKEY_MAP=1\n"
    # Logs and jars are history and third-party files: left as they were.
    assert (root / "server" / "logs" / "latest.log").read_text() == f"{OLD_NS} stays in the logs"
    assert (root / "server" / "mods" / f"{OLD_NS}-patch.jar").exists()

    capsys.readouterr()
    assert mn.main([str(root), "--apply"]) == 0
    assert "Nothing to migrate" in capsys.readouterr().out


def test_an_old_and_a_new_pack_side_by_side_stops_before_writing(tmp_path, capsys):
    root = server(tmp_path)
    (root / "server" / "world" / "datapacks" / "monkey-carry").mkdir()
    level = (root / "server" / "world" / "level.dat").read_bytes()
    assert mn.main([str(root), "--apply"]) == 1
    assert "both" in capsys.readouterr().err
    assert (root / "server" / "world" / "level.dat").read_bytes() == level
    assert (root / "server" / "world" / "datapacks" / OLD_PACK).is_dir()


def test_a_damaged_file_stops_before_writing(tmp_path, capsys):
    root = server(tmp_path)
    (root / "server" / "world" / "broken.dat").write_bytes(b"\x1f\x8bnot gzip")
    assert mn.main([str(root), "--apply"]) == 1
    assert "broken.dat" in capsys.readouterr().err
    assert (root / "server" / "world" / "datapacks" / OLD_PACK).is_dir()
