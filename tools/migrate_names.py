"""Moves a server folder installed before 2.10.0 from the old names (The Realms, `realms`) to Monkey SMP's.

    python tools/migrate_names.py <folder>            list what would change (nothing is written)
    python tools/migrate_names.py <folder> --apply    change it

<folder> is the server package folder (the one holding `server/`) or any folder inside it, such as a world.
Stop the server and take a backup first: the world's files are rewritten in place.

Before 2.10.0 the data pack namespace was `realms:`, the packs `realms-*`, the command storage
`data/realms`, the state files `.realms-*` and the scoreboard objectives and tags `realms.*`. A world keeps
those names in its saved data (scheduled functions in level.dat, scores, player tags, NPC dialogs), so
installing 2.10.0 over an old world would leave them pointing at functions that no longer exist. This renames
every file and folder whose name has the old name in it and swaps the old name for the new inside the files
the server and the installer read back: text (JSON, TOML, properties, YAML, functions) and NBT, gzipped,
zlib or plain, including the chunks of the region files.

Every old name is exactly as long as its new one (realms/monkey, TheRealms/MonkeySMP, The Realms/Monkey SMP),
so a swap inside NBT never changes a string's length prefix. Logs, backups, the Java runtime, jars and
databases are left alone. A target that already exists (an old and a new pack side by side) stops the run
before anything is written. Running it again on a migrated folder finds nothing to do.

A player's game folder (%APPDATA%\\.the-realms) is moved by the player installer, not here.
Stdlib only, and Python 3.10 or newer: it runs on the VPS (deploy/monkey-switch.sh).
"""
import argparse
import gzip
import os
import struct
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path

# Order matters: the longer, specific forms first. Every pair is the same length.
PAIRS = [(b"TheRealms", b"MonkeySMP"), (b"The Realms", b"Monkey SMP"), (b"the-realms", b"monkey-smp"),
         (b"the_realms", b"monkey_smp"), (b"REALMS", b"MONKEY"), (b"Realms", b"Monkey"), (b"realms", b"monkey")]
KEEP = [b"realmsNotifications"]   # vanilla Minecraft's own option, not ours
OLD = b"realms"

SKIP_DIRS = {"logs", "crash-reports", "backups", "java", "libraries", "versions", ".fabric", "cache", ".cache",
             ".git", "debug"}
TEXT = {".json", ".json5", ".toml", ".properties", ".txt", ".yml", ".yaml", ".mcfunction", ".mcmeta", ".snbt",
        ".cfg", ".conf", ".ini", ".env", ".example"}
NBT = {".dat", ".dat_old", ".nbt"}
REGION = {".mca"}
EXTERNAL_CHUNK = {".mcc"}
TEXT_NAMES = {".env", ".realms-launch", ".monkey-launch"}

SECTOR = 4096
GZIP, ZLIB, NONE, LZ4, EXTERNAL = 1, 2, 3, 4, 128

assert all(len(a) == len(b) for a, b in PAIRS)


def swap(data: bytes) -> bytes:
    """`data` with every old name replaced by its new one, case kept."""
    if OLD not in data.lower():
        return data
    for i, k in enumerate(KEEP):
        data = data.replace(k, b"\0KEEP%d\0" % i)
    for a, b in PAIRS:
        data = data.replace(a, b)
    for i, k in enumerate(KEEP):
        data = data.replace(b"\0KEEP%d\0" % i, k)
    return data


def swap_name(name: str) -> str:
    return swap(name.encode()).decode()


def _compressed(data: bytes) -> tuple[str, bytes]:
    """How an NBT file is stored ("gzip", "zlib" or "plain") and its NBT."""
    if data[:2] == b"\x1f\x8b":
        return "gzip", gzip.decompress(data)
    if data[:1] == b"\x78":
        return "zlib", zlib.decompress(data)
    return "plain", data


def _compress(kind: str, data: bytes) -> bytes:
    return gzip.compress(data, mtime=0) if kind == "gzip" else zlib.compress(data) if kind == "zlib" else data


def swap_nbt(data: bytes) -> bytes:
    """An NBT file's bytes with the old names swapped, stored as it was (the same bytes back if none)."""
    kind, raw = _compressed(data)
    new = swap(raw)
    return data if new == raw else _compress(kind, new)


def _chunk_payload(kind: int, payload: bytes, where: str) -> bytes:
    if kind == GZIP:
        return gzip.decompress(payload)
    if kind == ZLIB:
        return zlib.decompress(payload)
    if kind == NONE:
        return payload
    raise ValueError(f"{where}: chunk compression {kind} isn't one this tool reads (gzip, zlib or none)")


def _chunk_pack(kind: int, raw: bytes) -> bytes:
    return gzip.compress(raw, mtime=0) if kind == GZIP else zlib.compress(raw) if kind == ZLIB else raw


def swap_region(data: bytes, where: str = "region") -> bytes:
    """A region file (.mca) with the old names swapped inside its chunks (the same bytes back if none).

    The header is 1024 locations (3 bytes: the first sector, 1 byte: the sector count) then 1024 timestamps.
    Each chunk is a 4-byte length, a compression byte, then the payload. A changed chunk can come out a
    different size, so a changed file is laid out again from sector 2 with every chunk in its old order.
    A chunk too big for the region (compression | 128) lives in its own .mcc file, handled on its own.
    """
    if len(data) < 2 * SECTOR:
        return data   # an empty region: the server writes these for chunks it never saved
    chunks: list[tuple[int, int, bytes]] = []   # (header index, first sector, the chunk's bytes)
    changed = False
    for i in range(1024):
        loc = struct.unpack_from(">I", data, i * 4)[0]
        start, count = loc >> 8, loc & 0xFF
        if not start:
            continue
        pos = start * SECTOR
        if pos + 5 > len(data):
            raise ValueError(f"{where}: chunk {i} points past the end of the file")
        length = struct.unpack_from(">I", data, pos)[0]
        if length < 1 or pos + 4 + length > len(data):
            raise ValueError(f"{where}: chunk {i} is cut short")
        kind = data[pos + 4]
        body = data[pos + 4:pos + 4 + length]   # the compression byte and the payload
        if not kind & EXTERNAL:
            raw = _chunk_payload(kind, body[1:], f"{where} chunk {i}")
            new = swap(raw)
            if new != raw:
                body = bytes([kind]) + _chunk_pack(kind, new)
                changed = True
        chunks.append((i, start, body))
    if not changed:
        return data
    header = bytearray(data[:2 * SECTOR])
    out = bytearray()
    sector = 2
    for i, _, body in sorted(chunks, key=lambda c: c[1]):
        blob = struct.pack(">I", len(body)) + body
        blob += b"\0" * (-len(blob) % SECTOR)
        count = len(blob) // SECTOR
        if count > 255:
            raise ValueError(f"{where}: chunk {i} no longer fits in the region file")
        struct.pack_into(">I", header, i * 4, sector << 8 | count)
        out += blob
        sector += count
    return bytes(header) + bytes(out)


def swap_external_chunk(data: bytes, where: str, kind: int) -> bytes:
    """A .mcc file (one oversized chunk, compressed as its region entry says)."""
    raw = _chunk_payload(kind, data, where)
    new = swap(raw)
    return data if new == raw else _chunk_pack(kind, new)


def _external_kind(mcc: Path) -> int:
    """The compression of a .mcc chunk, from its region file's entry (c.<x>.<z>.mcc -> r.<x>.<z>.mca)."""
    _, x, z, _ = mcc.name.split(".")
    cx, cz = int(x), int(z)
    region = mcc.with_name(f"r.{cx >> 5}.{cz >> 5}.mca")
    data = region.read_bytes()
    index = (cx & 31) + (cz & 31) * 32
    start = struct.unpack_from(">I", data, index * 4)[0] >> 8
    return data[start * SECTOR + 4] & ~EXTERNAL


def _rewritable(path: Path) -> bool:
    suffix = path.suffix.lower()
    return suffix in REGION | EXTERNAL_CHUNK | NBT | TEXT or path.name.lower() in TEXT_NAMES


def swap_file(path: Path) -> bytes | None:
    """The file's new bytes, or None when it has nothing to change or isn't a kind this tool rewrites."""
    if not _rewritable(path):
        return None
    suffix = path.suffix.lower()
    data = path.read_bytes()
    try:
        if suffix in REGION:
            new = swap_region(data, str(path))
        elif suffix in EXTERNAL_CHUNK:
            new = swap_external_chunk(data, str(path), _external_kind(path))
        elif suffix in NBT:
            new = swap_nbt(data)
        else:
            new = swap(data)
    except (zlib.error, gzip.BadGzipFile, EOFError, struct.error) as e:
        raise ValueError(f"{path}: damaged ({e})") from None
    return None if new == data else new


@dataclass
class Plan:
    rewrites: dict[Path, bytes] = field(default_factory=dict)   # file (old path) -> new bytes
    renames: list[tuple[Path, Path]] = field(default_factory=list)   # deepest first, so children move first
    problems: list[str] = field(default_factory=list)


def plan(folder: Path) -> Plan:
    """What migrating `folder` would change, read but not written."""
    p = Plan()
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        here = Path(root)
        for f in files:
            path = here / f
            new = swap_file(path)
            if new is not None:
                p.rewrites[path] = new
        # Folders, and the files this tool reads; a jar or a database keeps its name.
        for name in dirs + [f for f in files if _rewritable(Path(f))]:
            new_name = swap_name(name)
            if new_name != name:
                target = here / new_name
                if target.exists():
                    p.problems.append(f"both {here / name} and {target} exist: move one away, then run this again")
                p.renames.append((here / name, target))
    p.renames.sort(key=lambda r: len(r[0].parts), reverse=True)
    return p


def apply(p: Plan) -> None:
    """Writes the plan: every rewrite (through a temporary file), then every rename, deepest first."""
    for path, data in p.rewrites.items():
        tmp = path.with_name(path.name + ".migrating")
        tmp.write_bytes(data)
        os.replace(tmp, path)
    for old, new in p.renames:
        old.rename(new)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Moves a server folder from the old names to Monkey SMP's.")
    parser.add_argument("folder", type=Path, help="the server package folder (or a world inside it)")
    parser.add_argument("--apply", action="store_true", help="change the files (default: only list them)")
    args = parser.parse_args(argv)
    folder = args.folder.resolve()
    if not folder.is_dir():
        print(f"{folder} is not a folder", file=sys.stderr)
        return 2
    try:
        p = plan(folder)
    except ValueError as e:
        print(f"Stopped, nothing changed: {e}", file=sys.stderr)
        return 1
    for path in sorted(p.rewrites):
        print(f"rewrite  {path.relative_to(folder)}")
    for old, new in sorted(p.renames):
        print(f"rename   {old.relative_to(folder)} -> {new.name}")
    if p.problems:
        print("\n".join(["", "Stopped, nothing changed:", *p.problems]), file=sys.stderr)
        return 1
    if not p.rewrites and not p.renames:
        print("Nothing to migrate: no old names left.")
        return 0
    if not args.apply:
        print(f"\n{len(p.rewrites)} files to rewrite, {len(p.renames)} to rename. Add --apply to do it.")
        return 0
    apply(p)
    print(f"\nRewrote {len(p.rewrites)} files and renamed {len(p.renames)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
