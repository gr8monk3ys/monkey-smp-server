"""Mace Limiter's patch (ADR-0004): makes the edited jar whose one changed class is patches/mace-limiterrr.

    python tools/macelimiter_patch.py macelimiter-<version>.jar OUT.jar

Why. Mace Limiter frees a mace's slot whenever a stack holding it is set to a count of 0, except inside
ItemStack.split and copyAndClear. Vanilla's Inventory.add moves an undamaged item with
stack.setCount(addResource(stack)), so a player picking a fresh mace up off the ground read as the mace being
destroyed: the log said "was destroyed, slot freed" with the mace in the player's hands, and the next craft
went through. Craft, drop, pick up, repeat beat the cap (tested on 26.2 with Mace Limiter 1.0.1, on a server
with only fabric-api and Carpet beside it).

The patch. In ItemStackMixin.releaseClearedMace the first instruction, `iload_1` (the new count), becomes
`iconst_1`. The `ifgt` after it then always jumps to the method's return, so a count of 0 no longer releases
anything; no offsets or stack map frames move. The mod's other two routes stay: a mace that breaks
(ItemStackBreakMixin) and a dropped mace that is destroyed (EntityRemovalMixin). What this gives up is a mace
removed with /clear, which stays counted until /macelimit reset. Counting one too many is the safe side of a
cap. Mace Limiter is CC0-1.0 and this file is the whole of the change. Stdlib only.
"""
import argparse
import sys
import zipfile
from pathlib import Path

import patches
from lootrestock_patch import ClassFile

CLASS = "com/maka/macelimiter/mixin/ItemStackMixin.class"
METHOD = "releaseClearedMace"
ILOAD_1, ICONST_1, IFGT = 0x1B, 0x04, 0x9D


def releases_on_zero(data: bytes) -> bool:
    """Whether the method still reads the new count: true upstream, false in a patched class."""
    start, _ = ClassFile(data).code[METHOD]
    return data[start] == ILOAD_1


def patch_class(data: bytes) -> bytes:
    start, _ = ClassFile(data).code[METHOD]
    if data[start] != ILOAD_1 or data[start + 1] != IFGT:
        raise SystemExit(f"expected {METHOD} to start with iload_1, ifgt. Mace Limiter changed: check it again.")
    out = bytearray(data)
    out[start] = ICONST_1
    return bytes(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("jar", type=Path, help="the Mace Limiter jar as downloaded")
    ap.add_argument("out", type=Path, help="where to write the edited jar")
    a = ap.parse_args(argv)
    original = a.jar.read_bytes()
    edited = patches.apply(original, {CLASS: patch_class(zipfile.ZipFile(a.jar).read(CLASS))})
    a.out.write_bytes(edited)
    print(f"wrote {a.out}: {CLASS} no longer frees a mace's slot when a stack's count is set to 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
