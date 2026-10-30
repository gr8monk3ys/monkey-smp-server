"""Highlight clip markers: a machine-readable line in the server log at each big moment, for the clips tool.

    python tools/datapacks.py                      regenerate the monkey-clips data pack (with the others)
    python tools/clips.py markers LOGS --world W [--since D]   every marker in a logs/ folder, one JSON line each
    python tools/clips.py key WORLD                           the world's marker key (for a copy of the logs)

What it is for: whoever records the server (the streaming repo's smp-cam scenario) downloads the server's logs
after a night, and the clips tool turns each marker into a clip window in the recording. Nothing is sent
anywhere and nothing new runs on the VPS: the marker is a line in the log the server already writes.

Off by default: `function monkey:clips/on` (docs/ADMIN.md, "Clip markers"). While off, a moment writes nothing.

How a moment writes its line: data packs can't write to the log, but the server logs every villager's death
with its name. So `monkey:clips/mark` summons a silent villager at y -100 under the moment (below every
dimension's floor, where nobody sees it), names it with the marker and kills it the same tick. It drops
nothing. The line is:

    [17:42:05] [Server thread/INFO]: Villager Villager['MONKEY-CLIP v=2|key=...|kind=first|title=Server First: Enter
    the Nether|players=;Steve|factions=;Red Monkeys|dim=the_nether|pos=12,64,-30'/123, l=...] died, ...

Fields are `key=value`, split by `|`; `players` and `factions` are lists split by `;` (empty entries are
dropped; a player in no faction adds none). A player's name is never `|` or `;`, and a faction's name (the
board's plain ASCII, diplomacy.py) is neither. The time is the log line's, in the server's time zone (the
VPS logs in Pacific: docs/LIVE.md). FORMAT_VERSION goes up when a field changes meaning.

Forgery: a player can put text in the log (chat) and name a villager, so the reader only takes the server
thread's own death line (LINE), at y -100, carrying the world's key: two random numbers the pack draws once
(`#key1`/`#key2` in cl, like the omens' secret) and nothing shows players. The VPS reads it from the world
(--world); for a copy of the logs, staff hand over `key`'s output with them, not to players.

Who calls it (as and at the player the moment is about, or at a place): Server Firsts' claims, a supply drop
or Meteor landing, the Hunted player's killer, and an outpost taken. A new feature adds one line:

    function monkey:clips/mark {kind:"boss",title:"The boss is down",other:""}

`other` names a second player ("" for none), whose faction is added too. Kinds and titles are plain text
without `"`, `|` or `;`. Stdlib only, Python 3.10 too (staff run `markers` on the VPS).
"""
import argparse
import datetime as dt
import gzip
import json
import re
import sys
from pathlib import Path

from datapacks import NS, function_tag, lines, mcmeta, say
from diplomacy import FACTION, FACTIONS
from repo import Repo

DATAPACK = "monkey-clips"
FN = f"data/{NS}/function/clips"
STORE = f"{NS}:clips"
OBJ = "cl"                # #on: 1 while markers are written
LOG_TAG = "cl.log"        # the villager that carries a marker into the log, for one tick
HERE_TAG = "cl.here"      # the marker entity that reads a moment's position, for one tick
NAME_TAG = "cl.name"      # the item display that reads a player's name, for one tick
PREFIX = "MONKEY-CLIP"
FORMAT_VERSION = 2       # 2: the world's key, first
DEPTH = 100               # blocks below the moment where the villager is summoned (under every dimension's floor)
FIELDS = ("kind", "title", "players", "factions", "dim", "pos")
FORBIDDEN = set('"|;\\')  # never in a kind or a title

# A player head of whoever the loot command runs as (as firsts.head_loot_table; firsts imports this module).
HEAD = {"type": "minecraft:chest", "pools": [{"rolls": 1, "entries": [{
    "type": "minecraft:item", "name": "minecraft:player_head",
    "modifier": {"type": "minecraft:fill_player_head", "entity": "this"}}]}]}

# Exactly the server thread's line for a villager's death, nothing a player can type or name: a chat line has
# `<name>` after the thread, and a named villager would have to die 100 blocks under the Overworld's floor and
# carry the world's key (KEYS, never shown to players).
LINE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\] \[Server thread/INFO\]: Villager Villager\['" + PREFIX
                  + r" (.*?)'/\d+, l='ServerLevel\[[^\]]*\]', x=-?\d+\.\d+, y=(-?\d+\.\d+), z=-?\d+\.\d+\] died, ")
KEYS = ("#key1", "#key2")  # in OBJ: two random numbers the pack draws once a world; markers carry them
DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d+)\.log\.gz$")


def mark(kind: str, title: str, other: str = "") -> str:
    """The command a feature's function runs to mark a moment (as and at its player, or at a place)."""
    bad = FORBIDDEN & set(kind + title + other)
    if bad or not re.fullmatch(r"[a-z_]+", kind):
        raise ValueError(f"marker kind {kind!r} / title {title!r} can't hold {sorted(bad)}")
    return f'function {NS}:clips/mark {{kind:"{kind}",title:"{title}",other:"{other}"}}'


def datapack_files() -> dict[str, str]:
    f: dict[str, str] = {}
    f["pack.mcmeta"] = mcmeta("Monkey SMP clip markers: big moments in the server log (generated by tools/clips.py)")
    f["data/minecraft/tags/function/load.json"] = function_tag(f"{NS}:clips/load")
    f[f"data/{NS}/loot_table/clips/head.json"] = json.dumps(HEAD, indent=2) + "\n"
    f[f"{FN}/load.mcfunction"] = lines(
        "# Generated by tools/clips.py. Off until staff turn it on (docs/ADMIN.md, \"Clip markers\").",
        f"scoreboard objectives add {OBJ} dummy",
        f"scoreboard players add #on {OBJ} 0",
        "# The world's key, once: a marker without it is a forgery (tools/clips.py drops it). Never show it.",
        *(f"execute unless score {k} {OBJ} matches 1.. store result score {k} {OBJ} run random value 1..1000000000"
          for k in KEYS),
    )
    f[f"{FN}/on.mcfunction"] = lines(
        f"scoreboard players set #on {OBJ} 1",
        say({"text": "Clip markers on: big moments write a MONKEY-CLIP line in the server log.", "color": "green"}),
    )
    f[f"{FN}/off.mcfunction"] = lines(
        f"scoreboard players set #on {OBJ} 0",
        say({"text": "Clip markers off.", "color": "yellow"}),
    )
    f[f"{FN}/mark.mcfunction"] = lines(
        "# Macro {kind, title, other}: a big moment, as and at its player (or at a place, as the server).",
        "# other: a second player's name, or \"\". Writes one MONKEY-CLIP line in the log (tools/clips.py).",
        f"execute unless score #on {OBJ} matches 1 run return 0",
        f'$data modify storage {STORE} m set value {{kind:"$(kind)",title:"$(title)",players:"",factions:"",'
        'dim:"overworld",name:""}',
        *(f"execute store result storage {STORE} m.k{i} int 1 run scoreboard players get {k} {OBJ}"
          for i, k in enumerate(KEYS, 1)),
        f'execute if dimension minecraft:the_nether run data modify storage {STORE} m.dim set value "the_nether"',
        f'execute if dimension minecraft:the_end run data modify storage {STORE} m.dim set value "the_end"',
        f"summon minecraft:marker ~ ~ ~ {{Tags:[\"{HERE_TAG}\"]}}",
        *(f"execute store result storage {STORE} m.{axis} int 1 run data get entity "
          f"@n[type=minecraft:marker,tag={HERE_TAG}] Pos[{i}]" for i, axis in enumerate("xyz")),
        f"kill @e[type=minecraft:marker,tag={HERE_TAG}]",
        f"execute if entity @s[type=minecraft:player] run function {NS}:clips/self",
        f'$data modify storage {STORE} m.name set value "$(other)"',
        f"execute unless data storage {STORE} m{{name:\"\"}} run function {NS}:clips/add with storage {STORE} m",
        f"function {NS}:clips/log with storage {STORE} m",
    )
    f[f"{FN}/self.mcfunction"] = lines(
        "# As the moment's player: their name (through a player head on an item display, as Server Firsts read",
        "# it), then added with their faction. Where no chunk is loaded the name can't be read and is left out.",
        f"summon minecraft:item_display ~ ~ ~ {{Tags:[\"{NAME_TAG}\"]}}",
        f"loot replace entity @n[type=minecraft:item_display,tag={NAME_TAG}] contents loot {NS}:clips/head",
        f"data modify storage {STORE} m.name set from entity @n[type=minecraft:item_display,tag={NAME_TAG}] "
        'item.components."minecraft:profile".name',
        f"kill @e[type=minecraft:item_display,tag={NAME_TAG}]",
        f"execute unless data storage {STORE} m{{name:\"\"}} run function {NS}:clips/add with storage {STORE} m",
    )
    f[f"{FN}/add.mcfunction"] = lines(
        "# Macro {name, players}: the player, and their faction's name if they have a faction number.",
        f'$data modify storage {STORE} m.players set value "$(players);$(name)"',
        f"$execute store result storage {STORE} m.n int 1 run scoreboard players get $(name) {FACTION}",
        f"$execute if score $(name) {FACTION} matches 1.. run function {NS}:clips/faction with storage {STORE} m",
    )
    f[f"{FN}/faction.mcfunction"] = lines(
        "# Macro {n}: faction n's name as the board shows it (none if its party is gone).",
        f"$execute unless data storage {FACTIONS} names.f$(n).text run return 0",
        f"$data modify storage {STORE} m.fname set from storage {FACTIONS} names.f$(n).text",
        f"function {NS}:clips/join with storage {STORE} m",
    )
    f[f"{FN}/join.mcfunction"] = lines(
        "# Macro {factions, fname}.",
        f'$data modify storage {STORE} m.factions set value "$(factions);$(fname)"',
    )
    f[f"{FN}/log.mcfunction"] = lines(
        "# Macro m: the villager's death is the log line (the server logs every villager's death with its name).",
        f"$summon minecraft:villager ~ -{DEPTH} ~ {{Tags:[\"{LOG_TAG}\"],Silent:1b,NoAI:1b,CustomName:\""
        f"{PREFIX} v={FORMAT_VERSION}|key=$(k1).$(k2)|kind=$(kind)|title=$(title)|players=$(players)|"
        "factions=$(factions)|dim=$(dim)|pos=$(x),$(y),$(z)\"}",
        f"kill @e[type=minecraft:villager,tag={LOG_TAG}]",
    )
    return f


def packs(repo: Repo) -> dict[Path, dict[str, str]]:
    return {repo.monkey / "datapacks" / DATAPACK: datapack_files()}


# ---------------------------------------------------------------- reading the markers back


BODY_KEYS = ("v", "key", *FIELDS)
# Each field's shape. A free-text field holding `|`, `;` or `=` can't be told from a forged one, so a body with
# anything else (another key, one twice, a field out of order or shape) is left out whole. Titles come from
# mark(), faction names from standings.board_name() and player names are [A-Za-z0-9_]: none hold `|;=`.
SHAPES = {"v": r"\d+", "key": r"\d+\.\d+", "kind": r"[a-z_]+", "title": r"[^|;=\"]*",
          "players": r"(?:;[A-Za-z0-9_]{1,16})*", "factions": r"(?:;[^|;=\"]+)*",
          "dim": r"overworld|the_nether|the_end", "pos": r"-?\d+,-?\d+,-?\d+"}


def fields(body: str) -> dict[str, str] | None:
    """A marker's `key=value|...` body as {key: value}, or None unless it is exactly BODY_KEYS, in order."""
    parts = [part.split("=", 1) for part in body.split("|")]
    if [p[0] for p in parts] != list(BODY_KEYS) or any(len(p) != 2 for p in parts):
        return None
    raw = dict((k, v) for k, v in parts)
    return raw if all(re.fullmatch(SHAPES[k], v) for k, v in raw.items()) else None


def parse(body: str) -> dict | None:
    """A marker's body -> its fields (lists split, pos as three ints), or None if it isn't one (fields()).
    The world's key is checked by markers() and left out."""
    raw = fields(body)
    if raw is None:
        return None
    out: dict = {"version": int(raw["v"]), "kind": raw["kind"], "title": raw["title"], "dim": raw["dim"]}
    for key in ("players", "factions"):
        out[key] = list(dict.fromkeys(p for p in raw[key].split(";") if p))
    out["pos"] = [int(v) for v in raw["pos"].split(",")]
    return out


def body_key(body: str) -> str:
    """The key a marker carries ("" when the body isn't one)."""
    raw = fields(body)
    return raw["key"] if raw else ""


def world_key(world: Path) -> str | None:
    """The world's key (`#key1.#key2` in cl) from its saved scoreboard, or None before the pack has drawn it."""
    import saved_world  # (here: the pack generator doesn't need the NBT reader)

    board = saved_world.scoreboard(world)
    held = board.scores.get(OBJ, {}) if board else {}
    return f"{held[KEYS[0]]}.{held[KEYS[1]]}" if all(held.get(k) for k in KEYS) else None


def logs_by_day(logs: Path):
    """Each log's first day and its lines, oldest first; latest.log, dated by its modification time, last."""
    dated = sorted(((dt.date.fromisoformat(m.group(1)), int(m.group(2))), path)
                   for path in logs.iterdir() if (m := DATED.match(path.name)))
    for (day, _), path in dated:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            yield day, fh.read().splitlines()
    latest = logs / "latest.log"
    if latest.is_file():
        yield dt.date.fromtimestamp(latest.stat().st_mtime), latest.read_text(
            encoding="utf-8", errors="replace").splitlines()


def markers(day: dt.date, text_lines, key: str, forged: list | None = None) -> list[dict]:
    """Every genuine marker in one log's lines: the server thread's line, 100 blocks under the moment, with the
    world's key (others go to `forged`). A time earlier than the line before it is the next day."""
    found, last = [], None
    for line in text_lines:
        m = LINE.match(line)
        if not m:
            continue
        parsed = parse(m.group(4))
        if abs(float(m.group(5)) + DEPTH) > 0.5 or parsed is None or body_key(m.group(4)) != key:
            if forged is not None:
                forged.append(line)
            continue
        t = dt.time(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if last is not None and t < last:
            day += dt.timedelta(days=1)
        last = t
        found.append({"time": dt.datetime.combine(day, t).isoformat(), **parsed})
    return found


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Clip markers from the server's logs, one JSON line each.")
    sub = ap.add_subparsers(dest="command", required=True)
    m = sub.add_parser("markers", help="every MONKEY-CLIP marker in a logs/ folder, as JSON lines")
    m.add_argument("logs", type=Path, help="the server's logs/ folder")
    whose = m.add_mutually_exclusive_group(required=True)
    whose.add_argument("--world", type=Path, help="the server's world folder (its key is read from it)")
    whose.add_argument("--key", help="the world's key (`key` prints it)")
    m.add_argument("--since", type=dt.date.fromisoformat, help="only from this day (YYYY-MM-DD)")
    k = sub.add_parser("key", help="the world's marker key, for whoever reads a copy of the logs (staff only)")
    k.add_argument("world", type=Path)
    args = ap.parse_args(argv)
    if args.command == "key":
        key = world_key(args.world)
        if key is None:
            print(f"no key saved in {args.world} yet (the monkey-clips pack draws it when it first loads)",
                  file=sys.stderr)
            return 1
        print(key)
        return 0
    key = args.key or world_key(args.world)
    if not key:
        print(f"no key saved in {args.world} yet", file=sys.stderr)
        return 1
    if not args.logs.is_dir():
        print(f"no logs folder at {args.logs}", file=sys.stderr)
        return 2
    forged: list[str] = []
    for day, text_lines in logs_by_day(args.logs):
        for marker in markers(day, text_lines, key, forged):
            if args.since is None or marker["time"] >= args.since.isoformat():
                print(json.dumps(marker, ensure_ascii=False))
    if forged:
        print(f"{len(forged)} MONKEY-CLIP line(s) without the world's key or out of place, left out (forged?)",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
