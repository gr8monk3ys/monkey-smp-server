"""A tiny NBT writer for made-up worlds in the tests (tools/ only reads NBT: tools/nbt.py).

dicts are compounds, Ints int arrays, other lists lists, str strings, float TAG_Double, Long TAG_Long and any
other int TAG_Int.
"""
import gzip
import struct


class Long(int):
    pass


class Ints(list):
    """An NBT int array (how Minecraft saves a UUID)."""


def nbt(value: dict, name: str = "", gzipped: bool = False) -> bytes:
    def tag(v) -> int:
        return (10 if isinstance(v, dict) else 11 if isinstance(v, Ints) else 9 if isinstance(v, list)
                else 8 if isinstance(v, str) else 6 if isinstance(v, float) else 4 if isinstance(v, Long) else 3)

    def payload(v) -> bytes:
        if isinstance(v, dict):
            return b"".join(bytes([tag(x)]) + string(k) + payload(x) for k, x in v.items()) + b"\x00"
        if isinstance(v, Ints):
            return struct.pack(f">i{len(v)}i", len(v), *v)
        if isinstance(v, list):
            return bytes([tag(v[0]) if v else 0]) + struct.pack(">i", len(v)) + b"".join(payload(x) for x in v)
        if isinstance(v, str):
            return string(v)
        return struct.pack(">d" if isinstance(v, float) else ">q" if isinstance(v, Long) else ">i", v)

    def string(s: str) -> bytes:
        raw = s.encode()
        return struct.pack(">H", len(raw)) + raw
    data = bytes([10]) + string(name) + payload(value)
    return gzip.compress(data) if gzipped else data
