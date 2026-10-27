"""Ending a season: the world download for players, and carrying wardrobe progress into the next world.

    python tools/season.py download BACKUP/world --season I --modpack 2.5.0 [--out "Monkey SMP Season I.zip"]
    python tools/season.py carry OLD/world --into NEW/world --season 2

download zips a season's world to open in singleplayer: the map, everyone's inventories and stats, and
the data packs, plus a READ ME. It leaves out what is private or only matters to the live server:
server.properties (the RCON password), ops, the whitelist and ban lists and usercache all sit outside
the world folder and never go in; inside it, the Ledger database (who did what, where), mod server
config, scripts, player-activity times, Distant Horizons' cache and session.lock stay out too.

carry reads the old world's scoreboard and writes a small data pack into the new world, realms-carry,
that puts back every wardrobe score (rw.*: days, months, invites, tiers, founders, events, holidays,
weekly challenges done, the launch weekend),
the supporter, title and champion teams, and hours played (as rw.playbase, because the new world's
play-time statistic starts at zero). It runs once, by itself, when the new world first loads; see
docs/SEASONS.md, "Ending a season".

Stdlib only.
"""
import argparse
import datetime as dt
import fnmatch
import gzip
import json
import shutil
import struct
import sys
import zipfile
from pathlib import Path

from datapacks import NS, function_tag, mcmeta

CARRY = "realms-carry"
# What goes in the download, relative to the world folder; then what is taken back out.
KEEP = ["level.dat", "dimensions", "data", "players", "datapacks"]
DROP = ["DistantHorizons*", "session.lock", "data/baguettelib", "data/mezz_config", f"datapacks/{CARRY}"]
# Scores that are not carried: worked out again (rw.hours), the play-time statistic (rw.play, carried as
# rw.playbase), constants (rw.const), the day counter, set on its own (rw.day), and the seconds played in
# Season I's launch weekend (rw.launchtime; rw.launch, the skin, carries). The weekly challenges' rc.* scores
# are this week's only and never carried; the challenges done (rw.challenges) are.
NOT_CARRIED = {"rw.play", "rw.hours", "rw.const", "rw.day", "rw.playbase", "rw.launchtime"}
TEAMS = ("tier_", "title_", "champion")   # the teams docs/RETENTION.md and docs/SEASONS.md set up

READ_ME = """Monkey SMP, Season {season}: the world download

This is the server's world as it was when Season {season} ended ({date}): every build, chest and map.

To open it:
1. Install the Monkey SMP modpack, version {modpack}, in your launcher (the same one you played with).
   Builds made with mod blocks need it; in plain Minecraft those blocks are lost.
2. Unzip this into the modpack instance's saves folder, so you have saves/Monkey SMP Season {season}/level.dat.
3. Start the game and pick it under Singleplayer (it may be listed as "world").

You load in as yourself, with your inventory where you left it. The world opens locked, as the server
left it: adventure mode, no PvP, peaceful. To build or fly around, press Esc, Open to LAN, turn Allow
Cheats on, start it, then type /function realms:events/season/unlock (or /gamemode creative). Make a
copy first if you want to keep the original.
"""


# ---------------------------------------------------------------- NBT (just enough to read a scoreboard)


def read_nbt(data: bytes) -> dict:
    """The root compound of an uncompressed NBT file, as plain Python values."""
    def value(pos: int, tag: int):
        if tag in SIMPLE:
            fmt = SIMPLE[tag]
            return struct.unpack_from(fmt, data, pos)[0], pos + struct.calcsize(fmt)
        if tag in ARRAYS:
            n = struct.unpack_from(">i", data, pos)[0]
            fmt = ARRAYS[tag]
            return list(struct.unpack_from(f">{n}{fmt}", data, pos + 4)), pos + 4 + n * struct.calcsize(fmt)
        if tag == 8:
            n = struct.unpack_from(">H", data, pos)[0]
            return data[pos + 2:pos + 2 + n].decode("utf-8", "replace"), pos + 2 + n
        if tag == 9:
            inner, n = struct.unpack_from(">bi", data, pos)
            pos += 5
            items = []
            for _ in range(n):
                item, pos = value(pos, inner)
                items.append(item)
            return items, pos
        if tag == 10:
            out = {}
            while data[pos] != 0:
                inner = data[pos]
                n = struct.unpack_from(">H", data, pos + 1)[0]
                name = data[pos + 3:pos + 3 + n].decode("utf-8", "replace")
                out[name], pos = value(pos + 3 + n, inner)
            return out, pos + 1
        raise ValueError(f"unknown NBT tag {tag} at byte {pos}")
    if data[0] != 10:
        raise ValueError("not an NBT compound")
    n = struct.unpack_from(">H", data, 1)[0]
    root = value(3 + n, 10)[0]
    assert isinstance(root, dict)
    return root


SIMPLE = {1: ">b", 2: ">h", 3: ">i", 4: ">q", 5: ">f", 6: ">d"}
ARRAYS = {7: "b", 11: "i", 12: "q"}


# ---------------------------------------------------------------- download


def world_files(world: Path) -> list[Path]:
    files = []
    for top in KEEP:
        path = world / top
        for f in ([path] if path.is_file() else sorted(path.rglob("*")) if path.is_dir() else []):
            rel = f.relative_to(world).as_posix()
            if f.is_file() and not any(fnmatch.fnmatch(part, pat) for part in rel.split("/") for pat in DROP) \
                    and not any(rel == d or rel.startswith(d + "/") for d in DROP):
                files.append(f)
    return files


def download(world: Path, season: str, modpack: str, out: Path) -> int:
    if not (world / "level.dat").is_file():
        raise SystemExit(f"{world} has no level.dat: give the world folder (e.g. backups/<time>/world)")
    root = f"Monkey SMP Season {season}"
    files = world_files(world)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr(f"{root}/READ ME.txt", READ_ME.format(season=season, modpack=modpack,
                                                        date=dt.date.today().isoformat()))
        for f in files:
            z.write(f, f"{root}/{f.relative_to(world).as_posix()}")
    print(f"wrote {out} ({out.stat().st_size // 2**20} MB, {len(files)} files from {world})")
    return 0


# ---------------------------------------------------------------- carry


def mc_string(text: str) -> str:
    """A name in a command: bare when Minecraft allows it, quoted otherwise."""
    return text if text and all(c.isalnum() or c in "_-.+#" for c in text) else json.dumps(text)


def carry_function(scoreboard: dict, season: int, source: str) -> str:
    data = scoreboard.get("data", scoreboard)
    # 26.3 leaves Score out when it is 0.
    scores: dict[tuple[str, str], int] = {(s["Objective"], s["Name"]): s.get("Score", 0)
                                          for s in data.get("PlayerScores", [])}
    lines = [f"# Generated by tools/season.py carry from {source}: the last season's wardrobe progress.",
             "# Runs once, at the first load of the new world (#carried stops it running again).",
             "scoreboard objectives add rw.day dummy",
             "execute if score #carried rw.day matches 1 run return 0",
             f"scoreboard players set #season rw.day {season}"]
    if ("rw.day", "#today") in scores:
        lines.append(f"scoreboard players set #today rw.day {scores['rw.day', '#today']}")
    objectives = sorted({o for o, _ in scores if o.startswith("rw.") and o not in NOT_CARRIED})
    lines += [f"scoreboard objectives add {o} dummy" for o in [*objectives, "rw.playbase"]]
    for (objective, name), score in sorted(scores.items()):
        if objective in objectives and not name.startswith("#"):
            lines.append(f"scoreboard players set {mc_string(name)} {objective} {score}")
    played: dict[str, int] = {}
    for (objective, name), score in scores.items():
        if objective in ("rw.play", "rw.playbase") and not name.startswith("#"):
            played[name] = played.get(name, 0) + score
    lines += [f"scoreboard players set {mc_string(name)} rw.playbase {ticks}" for name, ticks in sorted(played.items())]
    teams = [t for t in data.get("Teams", []) if t.get("Name", "").startswith(TEAMS)]
    for t in teams:
        name = t["Name"]
        lines.append(f"team add {name}")
        if t.get("TeamColor"):
            lines.append(f"team modify {name} color {t['TeamColor']}")
        for field, option in (("MemberNamePrefix", "prefix"), ("MemberNameSuffix", "suffix")):
            if t.get(field):
                lines.append(f"team modify {name} {option} {json.dumps(t[field], ensure_ascii=False)}")
        lines += [f"team join {name} {mc_string(p)}" for p in t.get("Players", [])]
    lines += ["scoreboard players set #carried rw.day 1",
              f"say Carried {len({n for (o, n) in scores if o in objectives and not n.startswith('#')})} players' "
              f"wardrobe scores and {len(teams)} teams into season {season}."]
    return "\n".join(lines) + "\n"


def carry(old: Path, new: Path, season: int) -> int:
    board = old / "data" / "minecraft" / "scoreboard.dat"
    if not board.is_file():
        raise SystemExit(f"no scoreboard at {board}: give the old world folder")
    scoreboard = read_nbt(gzip.decompress(board.read_bytes()))
    pack = new / "datapacks" / CARRY
    shutil.rmtree(pack, ignore_errors=True)
    files = {
        "pack.mcmeta": mcmeta("Monkey SMP: last season's wardrobe progress (one-shot, generated by tools/season.py)"),
        "data/minecraft/tags/function/load.json": function_tag(f"{NS}:carry/run"),
        f"data/{NS}/function/carry/run.mcfunction": carry_function(scoreboard, season, old.as_posix()),
    }
    for rel, text in files.items():
        (pack / rel).parent.mkdir(parents=True, exist_ok=True)
        (pack / rel).write_text(text, encoding="utf-8", newline="\n")
    run = files[f"data/{NS}/function/carry/run.mcfunction"]
    print(f"wrote {pack}: {run.count(chr(10))} lines. It runs when the new world first loads; check with\n"
          f'  realms rcon "scoreboard players get #carried rw.day"   (1 once it has run)')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Season end: the world download, and carrying progress over.")
    sub = ap.add_subparsers(dest="command", required=True)
    d = sub.add_parser("download", help="zip a season's world for singleplayer")
    d.add_argument("world", type=Path, help="the world folder of the final backup")
    d.add_argument("--season", required=True, help="the season's name, e.g. I")
    d.add_argument("--modpack", required=True, help="the client modpack version to open it with")
    d.add_argument("--out", type=Path, help='default: "Monkey SMP Season <season>.zip" here')
    c = sub.add_parser("carry", help="carry wardrobe scores and teams into the next season's world")
    c.add_argument("old", type=Path, help="the last season's world folder")
    c.add_argument("--into", type=Path, required=True, help="the new world folder (it may not exist yet)")
    c.add_argument("--season", type=int, required=True, help="the new season's number, e.g. 2")
    args = ap.parse_args(argv)
    if args.command == "download":
        return download(args.world, args.season, args.modpack, args.out or Path(f"Monkey SMP Season {args.season}.zip"))
    return carry(args.old, args.into, args.season)


if __name__ == "__main__":
    sys.exit(main())
