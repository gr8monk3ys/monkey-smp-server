"""Reads the world's NBT files (level.dat, scoreboard.dat, world_border.dat, Open Parties and Claims' *.nbt).

    import nbt
    root = nbt.read(world / "data" / "minecraft" / "scoreboard.dat")   # a path, or the file's bytes

`read` gives the root compound as plain Python values: compounds are dicts, lists and the byte, int and long
arrays are lists, strings are str (a byte that isn't UTF-8 becomes U+FFFD), and numbers are int or float. The
file may be gzipped or not. A file that isn't an NBT compound, or holds an unknown tag, is a ValueError naming
the file. It only reads: nothing in tools/ writes NBT.
Stdlib only, and Python 3.10 or newer: tools/drops.py runs it on the VPS.
"""
import gzip
import struct
from pathlib import Path

NUMBERS = {1: ">b", 2: ">h", 3: ">i", 4: ">q", 5: ">f", 6: ">d"}
ARRAYS = {7: "b", 11: "i", 12: "q"}   # byte, int and long arrays
GZIP = b"\x1f\x8b"


def read(source: Path | bytes) -> dict:
    """The root compound of an NBT file, given its path or its bytes, gzipped or not."""
    where = f"{source}: " if isinstance(source, Path) else ""
    data = source.read_bytes() if isinstance(source, Path) else source
    if data[:2] == GZIP:
        data = gzip.decompress(data)
    if not data or data[0] != 10:
        raise ValueError(f"{where}not an NBT compound")
    try:
        _, pos = _value(data, 1, 8)   # the root's name (empty)
        root, _ = _value(data, pos, 10)
    except (IndexError, struct.error) as e:
        raise ValueError(f"{where}cut short ({e})") from None
    except ValueError as e:
        raise ValueError(f"{where}{e}") from None
    assert isinstance(root, dict)
    return root


def _value(data: bytes, pos: int, tag: int) -> tuple[object, int]:
    """The value of type `tag` at `pos`, and the position after it."""
    if tag in NUMBERS:
        return struct.unpack_from(NUMBERS[tag], data, pos)[0], pos + struct.calcsize(NUMBERS[tag])
    if tag in ARRAYS:
        fmt = f">{struct.unpack_from('>i', data, pos)[0]}{ARRAYS[tag]}"
        return list(struct.unpack_from(fmt, data, pos + 4)), pos + 4 + struct.calcsize(fmt)
    if tag == 8:
        n = struct.unpack_from(">H", data, pos)[0]
        return data[pos + 2:pos + 2 + n].decode("utf-8", "replace"), pos + 2 + n
    if tag == 9:
        item, n = data[pos], struct.unpack_from(">i", data, pos + 1)[0]
        pos += 5
        items = []
        for _ in range(n):
            value, pos = _value(data, pos, item)
            items.append(value)
        return items, pos
    if tag == 10:
        compound = {}
        while (child := data[pos]) != 0:
            name, pos = _value(data, pos + 1, 8)
            compound[name], pos = _value(data, pos, child)
        return compound, pos + 1
    raise ValueError(f"unknown NBT tag {tag} at byte {pos}")
