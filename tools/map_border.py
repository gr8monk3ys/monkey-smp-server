"""Fits the live map (BlueMap) to the world border, so it shows no land players can't reach yet.

    python3 tools/map_border.py PATH/TO/server           set each map's render-mask to its dimension's border
    python3 tools/map_border.py PATH/TO/server --check   exit 1 if a mask doesn't match its border

Chunky pre-generates out to the season's largest border, so without a mask the map would show the land the
border acts will open (docs/SEASONS.md). The border is read from the world's own files (since 26.3 each
dimension keeps its own, in world/dimensions/minecraft/<dimension>/data/minecraft/world_border.dat), so run
`save-all` first when it changed in the last few minutes. A border that is still growing counts at its
final size. A dimension without a border (the End) keeps its map as it is.

The mask is the first layer of `render-mask` in each config/bluemap/maps/<map>.conf; later layers (the
Nether's ceiling) are kept. BlueMap only sees the change after `bluemap reload`, and `bluemap purge <map>`
then deletes the map's tiles and renders it again inside the new mask; the tool prints both.
Stdlib only, so it runs on the VPS as it is (docs/LIVE.md).
"""
import argparse
import gzip
import math
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

MAPS = Path("config") / "bluemap" / "maps"
NO_BORDER = 59_999_968  # the vanilla maximum: the dimension has no border to speak of
MARK = "# Monkey SMP: the world border. tools/map_border.py keeps this layer in step with it."
_SETTING = re.compile(r'^([a-z-]+):\s*"?([^"\n]*)"?\s*$', re.M)
_BOX_KEYS = {"min-x", "max-x", "min-z", "max-z", "min-y", "max-y"}


@dataclass(frozen=True)
class Border:
    center_x: float
    center_z: float
    size: float

    def mask(self) -> dict[str, int]:
        """The smallest block box holding every block the border lets players into, even partly."""
        half = self.size / 2
        return {
            "min-x": math.floor(self.center_x - half), "max-x": math.ceil(self.center_x + half) - 1,
            "min-z": math.floor(self.center_z - half), "max-z": math.ceil(self.center_z + half) - 1,
        }

    def describe(self) -> str:
        return f"border {self.size:g} wide at {self.center_x:g}, {self.center_z:g}"


# --- NBT: just enough to read a world_border.dat (a gzipped compound) ----------------------------------------

_NUMBERS = {1: ">b", 2: ">h", 3: ">i", 4: ">q", 5: ">f", 6: ">d"}
_ARRAYS = {7: "b", 11: "i", 12: "q"}  # byte, int and long arrays


def _read(data: bytes, pos: int, tag: int) -> tuple[object, int]:
    """The value of type `tag` at `pos`, and the position after it."""
    if tag in _NUMBERS:
        return struct.unpack_from(_NUMBERS[tag], data, pos)[0], pos + struct.calcsize(_NUMBERS[tag])
    if tag in _ARRAYS:
        fmt = f">{struct.unpack_from('>i', data, pos)[0]}{_ARRAYS[tag]}"
        return list(struct.unpack_from(fmt, data, pos + 4)), pos + 4 + struct.calcsize(fmt)
    if tag == 8:
        n = struct.unpack_from(">H", data, pos)[0]
        return data[pos + 2:pos + 2 + n].decode("utf-8"), pos + 2 + n
    if tag == 9:
        item, n = data[pos], struct.unpack_from(">i", data, pos + 1)[0]
        pos += 5
        items = []
        for _ in range(n):
            value, pos = _read(data, pos, item)
            items.append(value)
        return items, pos
    if tag == 10:
        compound = {}
        while (child := data[pos]) != 0:
            name, pos = _read(data, pos + 1, 8)
            compound[name], pos = _read(data, pos, child)
        return compound, pos + 1
    raise ValueError(f"unknown NBT tag {tag}")


def read_nbt(path: Path) -> dict:
    data = gzip.decompress(path.read_bytes())
    if not data or data[0] != 10:
        raise ValueError(f"{path}: not an NBT compound")
    _, pos = _read(data, 1, 8)  # the root's name (empty)
    root, _ = _read(data, pos, 10)
    assert isinstance(root, dict)
    return root


def border_file(server: Path, world: str, dimension: str) -> Path:
    namespace, _, name = dimension.partition(":")
    return server / world / "dimensions" / namespace / name / "data" / "minecraft" / "world_border.dat"


def read_border(path: Path) -> Border | None:
    """The border saved in a world_border.dat, or None when the dimension has none."""
    data = read_nbt(path)["data"]
    size = data.get("lerp_target", data["size"])  # where a growing border is heading
    if size >= NO_BORDER:
        return None
    return Border(data["center_x"], data["center_z"], size)


# --- the map configs -------------------------------------------------------------------------------------------

def settings(text: str) -> dict[str, str]:
    """Top-level `key: value` lines of a map config (enough for `world` and `dimension`)."""
    return {k: v for k, v in _SETTING.findall(text)}


def first_layer(lines: list[str]) -> tuple[int, int]:
    """Line numbers of the first layer's `{` and `}` in `render-mask: [`."""
    try:
        start = next(i for i, line in enumerate(lines)
                     if line.startswith("render-mask:") and line.rstrip().endswith("["))
        open_ = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "{")
        close = next(i for i in range(open_ + 1, len(lines)) if lines[i].strip().startswith(("{", "}", "]")))
    except StopIteration:
        raise ValueError("no `render-mask: [ { ... } ]` as BlueMap writes it") from None
    if lines[close].strip() != "}":
        raise ValueError("the first render-mask layer isn't a simple { ... } block")
    return open_, close


def with_mask(text: str, mask: dict[str, int]) -> str:
    """`text` with the first render-mask layer replaced by a box of `mask`; refuses a layer it didn't write."""
    lines = text.split("\n")
    open_, close = first_layer(lines)
    for line in lines[open_ + 1:close]:
        line = line.strip()
        if line and not line.startswith("#") and line.split(":")[0].strip() not in _BOX_KEYS:
            raise ValueError(f"the first render-mask layer has `{line}`: edit that by hand")
    layer = ["  {", f"    {MARK}"] + [f"    {k}: {v}" for k, v in mask.items()] + ["  }"]
    return "\n".join(lines[:open_] + layer + lines[close + 1:])


@dataclass(frozen=True)
class MapFit:
    conf: Path
    dimension: str
    border: Border | None
    text: str      # the config as it is
    fitted: str    # the config with its mask on the border

    @property
    def id(self) -> str:
        return self.conf.stem

    @property
    def changed(self) -> bool:
        return self.text != self.fitted


def fit_maps(server: Path) -> list[MapFit]:
    """Every map config under `server`, with its mask fitted to its dimension's border."""
    confs = sorted((server / MAPS).glob("*.conf"))
    if not confs:
        raise ValueError(f"no map configs in {server / MAPS}")
    fits = []
    for conf in confs:
        text = conf.read_text(encoding="utf-8")
        found = settings(text)
        world, dimension = found.get("world"), found.get("dimension")
        if not world or not dimension:
            raise ValueError(f"{conf}: no world or dimension setting")
        path = border_file(server, world, dimension)
        if not path.is_file():
            raise ValueError(f"{conf}: no border saved at {path} (a 26.3 world that has been saved?)")
        border = read_border(path)
        try:
            fitted = with_mask(text, border.mask()) if border else text
        except ValueError as e:
            raise ValueError(f"{conf}: {e}") from None
        fits.append(MapFit(conf, dimension, border, text, fitted))
    return fits


def report(fit: MapFit) -> str:
    if fit.border is None:
        return f"{fit.id} ({fit.dimension}): no border, map left as it is"
    m = fit.border.mask()
    return (f"{fit.id} ({fit.dimension}): {fit.border.describe()}: mask x {m['min-x']}..{m['max-x']}, "
            f"z {m['min-z']}..{m['max-z']} ({'changed' if fit.changed else 'already set'})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fit the BlueMap map masks to the world border.")
    ap.add_argument("server", type=Path, help="the server folder (holding world/ and config/)")
    ap.add_argument("--check", action="store_true", help="change nothing; exit 1 if a mask is off")
    args = ap.parse_args(argv)
    try:
        fits = fit_maps(args.server)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for fit in fits:
        print(report(fit))
    changed = [fit for fit in fits if fit.changed]
    if args.check:
        return 1 if changed else 0
    for fit in changed:
        fit.conf.write_text(fit.fitted, encoding="utf-8", newline="")  # in place: keeps the owner
    if changed:
        print("Then, in the server console: bluemap reload")
        for fit in changed:
            print(f"                            bluemap purge {fit.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
