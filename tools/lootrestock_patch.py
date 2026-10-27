"""Loot Restock's patch (ADR-0004): makes the edited jar that `tools/snapshot.py server` turns into
patches/lootrestock.

    python tools/lootrestock_patch.py LootRestock-<version>.jar OUT.jar

Why. Loot Restock starts tracking a structure chest (or chest minecart) the first time a player opens it,
and records whether it is empty with the container's isEmpty(). For a container that still has its loot
table, vanilla's isEmpty() rolls the loot first, with no player. Vanilla then has nothing left to roll when
the player's own open goes through, so the `player_generates_container_loot` advancement never fires and
the weekly "Open 8 loot chests" challenge never counts a chest (tested on 26.3 with Loot Restock 1.0.3;
barrels, which Loot Restock leaves alone in our config, still counted).

The patch. In ChestInteractionHandler's two container handlers, the call to isEmpty() becomes `false`
(bytecode `pop; iconst_0; nop` in place of the 3-byte invokevirtual, so no offsets or stack map frames
move). The handlers return early unless the container still has a loot table, so "not empty" is the true
answer there, and Loot Restock decides its resets from the container's contents at reset time, not from
this value. Loot Restock is GPL-3.0-or-later; its source is https://github.com/Quackster/LootRestock and
this file is the whole of the change. Stdlib only.
"""
import argparse
import struct
import sys
import zipfile
from pathlib import Path

import patches

CLASS = "org/oldskooler/lootrestock/handler/ChestInteractionHandler.class"
METHODS = ("handleChestInteraction", "handleMinecartChestInteraction")
# The containers whose isEmpty() rolls a pending loot table; ItemStack.isEmpty() (item frames) is harmless.
CONTAINERS = ("net/minecraft/world/level/block/entity/RandomizableContainerBlockEntity",
              "net/minecraft/world/entity/vehicle/minecart/MinecartChest")
INVOKEVIRTUAL, POP, ICONST_0, NOP = 0xB6, 0x57, 0x03, 0x00
# Operand bytes after the opcode, for the fixed-length instructions that have operands.
OPERANDS = {0x10: 1, 0x11: 2, 0x12: 1, 0x13: 2, 0x14: 2, **dict.fromkeys(range(0x15, 0x1A), 1),
            **dict.fromkeys(range(0x36, 0x3B), 1), 0x84: 2, **dict.fromkeys(range(0x99, 0xA9), 2), 0xA9: 1,
            **dict.fromkeys(range(0xB2, 0xB9), 2), 0xB9: 4, 0xBA: 4, 0xBB: 2, 0xBC: 1, 0xBD: 2, 0xC0: 2,
            0xC1: 2, 0xC5: 3, 0xC6: 2, 0xC7: 2, 0xC8: 4, 0xC9: 4}


class ClassFile:
    """Just enough of a class file to find method calls: the constant pool and each method's code."""

    def __init__(self, data: bytes):
        self.data = data
        if data[:4] != b"\xca\xfe\xba\xbe":
            raise ValueError("not a class file")
        count = struct.unpack_from(">H", data, 8)[0]
        self.pool: list = [None] * count
        i, k = 10, 1
        while k < count:
            tag = data[i]
            if tag == 1:
                n = struct.unpack_from(">H", data, i + 1)[0]
                self.pool[k] = ("utf8", data[i + 3:i + 3 + n].decode("utf-8", "replace"))
                i += 3 + n
            elif tag in (7, 8, 16, 19, 20):
                self.pool[k] = (tag, struct.unpack_from(">H", data, i + 1)[0])
                i += 3
            elif tag in (9, 10, 11, 12, 17, 18):
                self.pool[k] = (tag, *struct.unpack_from(">HH", data, i + 1))
                i += 5
            elif tag == 15:
                i += 4
            elif tag in (3, 4):
                i += 5
            elif tag in (5, 6):
                i += 9
                k += 1
            else:
                raise ValueError(f"unknown constant pool tag {tag}")
            k += 1
        i += 6                                                    # access, this, super
        i += 2 + 2 * struct.unpack_from(">H", data, i)[0]         # interfaces
        self.code: dict[str, tuple[int, int]] = {}                # method name -> (code offset, length)
        self._members(self._members(i, None), self.code)          # fields, then methods

    def _members(self, i: int, code: dict | None) -> int:
        """Walk a field or method table starting at its count; returns the offset after it."""
        count = struct.unpack_from(">H", self.data, i)[0]
        i += 2
        for _ in range(count):
            name = self.utf8(struct.unpack_from(">H", self.data, i + 2)[0])
            n_attrs = struct.unpack_from(">H", self.data, i + 6)[0]
            i += 8
            for _ in range(n_attrs):
                attr, length = struct.unpack_from(">HI", self.data, i)
                if code is not None and self.utf8(attr) == "Code":   # max_stack, max_locals, code_length
                    code[name] = (i + 14, struct.unpack_from(">I", self.data, i + 10)[0])
                i += 6 + length
        return i

    def utf8(self, index: int) -> str:
        return self.pool[index][1]

    def method_ref(self, index: int) -> tuple[str, str, str]:
        _, cls, nat = self.pool[index]
        _, name, desc = self.pool[nat]
        return self.utf8(self.pool[cls][1]), self.utf8(name), self.utf8(desc)

    def calls(self, method: str):
        """(offset in the file, owner, name, descriptor) of every invokevirtual in a method."""
        start, length = self.code[method]
        pc = 0
        while pc < length:
            op = self.data[start + pc]
            if op == INVOKEVIRTUAL:
                yield (start + pc, *self.method_ref(struct.unpack_from(">H", self.data, start + pc + 1)[0]))
            if op in (0xAA, 0xAB):                                # tableswitch, lookupswitch
                p = pc + 1 + (-(pc + 1) % 4)
                if op == 0xAA:
                    low, high = struct.unpack_from(">ii", self.data, start + p + 4)
                    pc = p + 12 + 4 * (high - low + 1)
                else:
                    pc = p + 8 + 8 * struct.unpack_from(">i", self.data, start + p + 4)[0]
            elif op == 0xC4:                                      # wide
                pc += 6 if self.data[start + pc + 1] == 0x84 else 4
            else:
                pc += 1 + OPERANDS.get(op, 0)


def rolling_calls(data: bytes) -> list[str]:
    """The isEmpty() calls on a loot container left in the handlers: none in a patched class."""
    cf = ClassFile(data)
    return [f"{m}: {owner}.{name}{desc}" for m in METHODS for _, owner, name, desc in cf.calls(m)
            if owner in CONTAINERS and name == "isEmpty" and desc == "()Z"]


def patch_class(data: bytes) -> bytes:
    cf = ClassFile(data)
    out = bytearray(data)
    hits = [(at, m) for m in METHODS for at, owner, name, desc in cf.calls(m)
            if owner in CONTAINERS and name == "isEmpty" and desc == "()Z"]
    found = {m for _, m in hits}
    if found != set(METHODS):
        raise SystemExit(f"expected an isEmpty() call in each of {', '.join(METHODS)}; found it in "
                         f"{', '.join(sorted(found)) or 'neither'}. Loot Restock changed: check the source again.")
    for at, _ in hits:
        out[at:at + 3] = bytes((POP, ICONST_0, NOP))
    return bytes(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("jar", type=Path, help="the Loot Restock jar as downloaded")
    ap.add_argument("out", type=Path, help="where to write the edited jar")
    a = ap.parse_args(argv)
    original = a.jar.read_bytes()
    edited = patches.apply(original, {CLASS: patch_class(zipfile.ZipFile(a.jar).read(CLASS))})
    a.out.write_bytes(edited)
    print(f"wrote {a.out}: {CLASS} no longer rolls loot when Loot Restock starts tracking a container")
    return 0


if __name__ == "__main__":
    sys.exit(main())
