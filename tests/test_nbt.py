import gzip
import struct

import pytest
from nbt_writer import Ints, Long
from nbt_writer import nbt as write

import nbt

WORLD = {"DataVersion": 5023, "data": {
    "name": "Monkey SMP", "size": 2500.0, "time": Long(-7), "uuid": Ints([1, -2, 3, 4]),
    "PlayerScores": [{"Objective": "ev.cup", "Name": "AlexFake", "Score": 3}], "empty": [], "nested": {"a": {}}}}


def test_reads_what_the_writer_writes_from_a_path_or_bytes_gzipped_or_not(tmp_path):
    for data in (write(WORLD), write(WORLD, gzipped=True)):
        assert nbt.read(data) == WORLD
        (tmp_path / "level.dat").write_bytes(data)
        assert nbt.read(tmp_path / "level.dat") == WORLD


def test_reads_every_number_and_array_tag():
    def named(tag, name, payload):
        return bytes([tag]) + struct.pack(">H", len(name)) + name.encode() + payload
    body = b"".join([
        named(1, "byte", struct.pack(">b", -1)), named(2, "short", struct.pack(">h", -300)),
        named(5, "float", struct.pack(">f", 0.5)), named(7, "bytes", struct.pack(">i3b", 3, 1, -1, 0)),
        named(12, "longs", struct.pack(">i2q", 2, 1, -(2 ** 40))),
    ])
    assert nbt.read(b"\x0a\x00\x00" + body + b"\x00") == {
        "byte": -1, "short": -300, "float": 0.5, "bytes": [1, -1, 0], "longs": [1, -(2 ** 40)]}


def test_a_string_that_is_not_utf8_still_reads():
    assert nbt.read(b"\x0a\x00\x00\x08\x00\x01s\x00\x02\xff\x41\x00") == {"s": "�A"}


@pytest.mark.parametrize(("data", "said"), [
    (b"", "not an NBT compound"),
    (b"\x09\x00\x00", "not an NBT compound"),
    (gzip.compress(b"\x08\x00\x00"), "not an NBT compound"),
    (b"\x0a\x00\x00\x0d\x00\x01x\x00", "unknown NBT tag 13 at byte 7"),
    (b"\x0a\x00\x00\x03\x00\x01x\x00", "cut short"),
])
def test_what_is_not_an_nbt_compound_is_a_value_error_naming_the_file(tmp_path, data, said):
    with pytest.raises(ValueError, match=said):
        nbt.read(data)
    path = tmp_path / "bad.dat"
    path.write_bytes(data)
    with pytest.raises(ValueError, match=f"^{repr(str(path))[1:-1]}: {said}"):
        nbt.read(path)
