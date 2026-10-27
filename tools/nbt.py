"""Reads the world's NBT files (level.dat, scoreboard.dat, world_border.dat, Open Parties and Claims' *.nbt).

    import nbt
    root = nbt.read(world / "data" / "minecraft" / "scoreboard.dat")   # a path, or the file's bytes

`read` gives the root compound as plain Python values: compounds are dicts, lists and the byte, int and long
arrays are lists, strings are str (a byte that isn't UTF-8 becomes U+FFFD), and numbers are int or float. The
file may be gzipped or not. Whatever is wrong with a file (not gzip or NBT, cut short, a negative length, an
unknown tag) is a ValueError naming it. It only reads: nothing in tools/ writes NBT.
Stdlib only, and Python 3.10 or newer: tools/drops.py runs it on the VPS.
"""
import gzip
import os
import struct
import zlib

NUMBERS = {tag: struct.Struct(fmt) for tag, fmt in {1: ">b", 2: ">h", 3: ">i", 4: ">q", 5: ">f", 6: ">d"}.items()}
ARRAYS = {7: "b", 11: "i", 12: "q"}   # byte, int and long arrays
LENGTH, SHORT = struct.Struct(">i"), struct.Struct(">H")
GZIP = b"\x1f\x8b"


def read(source: os.PathLike | str | bytes) -> dict:
    """The root compound of an NBT file, given its path or its bytes, gzipped or not."""
    if isinstance(source, (bytes, bytearray)):
        where, data = "", bytes(source)
    else:
        where, data = f"{os.fspath(source)}: ", open(source, "rb").read()
    try:
        if data[:2] == GZIP:
            data = gzip.decompress(data)
        if not data or data[0] != 10:
            raise ValueError("not an NBT compound")
        _, pos = _value(data, 1, 8)   # the root's name (empty)
        root, _ = _value(data, pos, 10)
        assert isinstance(root, dict)
        return root
    except (IndexError, struct.error, EOFError, zlib.error, gzip.BadGzipFile) as e:
        raise ValueError(f"{where}cut short or damaged ({e})") from None
    except ValueError as e:
        raise ValueError(f"{where}{e}") from None


def _length(data: bytes, pos: int, size: int) -> int:
    """The count at `pos` of items `size` bytes each, checked against what is left of the file."""
    n = LENGTH.unpack_from(data, pos)[0]
    if n < 0 or pos + 4 + n * size > len(data):
        raise ValueError(f"bad length {n} at byte {pos}")
    return n


def _value(data: bytes, pos: int, tag: int) -> tuple[object, int]:
    """The value of type `tag` at `pos`, and the position after it."""
    if tag in NUMBERS:
        number = NUMBERS[tag]
        return number.unpack_from(data, pos)[0], pos + number.size
    if tag in ARRAYS:
        size = struct.calcsize(ARRAYS[tag])
        n = _length(data, pos, size)
        return list(struct.unpack_from(f">{n}{ARRAYS[tag]}", data, pos + 4)), pos + 4 + n * size
    if tag == 8:
        n = SHORT.unpack_from(data, pos)[0]
        if pos + 2 + n > len(data):
            raise ValueError(f"bad length {n} at byte {pos}")
        return data[pos + 2:pos + 2 + n].decode("utf-8", "replace"), pos + 2 + n
    if tag == 9:
        item, n = data[pos], _length(data, pos + 1, 1)   # every item is at least a byte (an empty compound)
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
