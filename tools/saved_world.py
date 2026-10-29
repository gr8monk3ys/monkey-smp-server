"""The saved world: what the tools read from the files the server saves in a world folder (server/world).

    import saved_world
    board = saved_world.scoreboard(folder)              # None when the world has no scoreboard saved
    board.scores["ev.cup"]["red"]                       # objective -> holder -> score
    board.displays["ev.cup"]["red"]                     # the display name a holder was given, as plain text
    board.teams                                         # every team: name, colour, prefix, suffix, players
    saved_world.parties(folder)                         # Open Parties and Claims' parties (None: no parties folder)
    saved_world.claims(folder, saved_world.OVERWORLD)   # claim file -> one dimension's claimed chunks [(x, z)]
    saved_world.claim_counts(folder)                    # claim file -> chunks claimed in every dimension
    saved_world.border(folder, saved_world.OVERWORLD)   # a dimension's border (None: none saved)

The files, relative to the world folder:
  data/minecraft/scoreboard.dat                                 scores, display names and teams
  data/openpartiesandclaims/parties/<party>.nbt                 each party: its owner and members
  data/openpartiesandclaims/player-configs/<player>.toml        a party's name (its owner's parties.name)
  data/openpartiesandclaims/player-claims/<player>.nbt          each player's claimed chunks
  dimensions/<namespace>/<name>/data/minecraft/world_border.dat  a dimension's border (since 26.3)

This module says where things are and how they are saved (26.3 leaves a score of 0 out; the scoreboard sits
under "data"; a UUID is four ints); callers keep their own rules (ranking, where drops land, map masks).
It only reads, through tools/nbt.py. A damaged file is a ValueError naming it: nbt.read's when it isn't NBT,
this module's when it is NBT but not shaped as the server saves it (a field missing or of the wrong type, a
UUID that isn't one). Only what a caller asks for is looked at, so a bad claim in a dimension a caller doesn't
read never stops it. The server saves every 5 to 10 minutes and when it stops, so run `save-all` first for
what changed since.
Stdlib only, and Python 3.10 or newer: tools/drops.py runs it on the VPS (so tomllib, 3.11, is imported
only where a party name is read).
"""
import struct
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import nbt

SCOREBOARD = Path("data") / "minecraft" / "scoreboard.dat"
OPAC = Path("data") / "openpartiesandclaims"
PARTIES = OPAC / "parties"
PLAYER_CONFIGS = OPAC / "player-configs"
PLAYER_CLAIMS = OPAC / "player-claims"
OVERWORLD = "minecraft:overworld"


@contextmanager
def _shaped(path: Path) -> Iterator[None]:
    """Reading what nbt.read gave for `path`: a field missing or of the wrong type is a ValueError naming it."""
    try:
        yield
    except (KeyError, IndexError, TypeError, AttributeError, ValueError) as e:
        raise ValueError(f"{path}: not as the server saves it ({type(e).__name__}: {e})") from None


def uuid_text(value) -> str:
    """A UUID as Minecraft saves it (four ints, two longs or text) in its usual 8-4-4-4-12 form.
    Anything else is a ValueError."""
    try:
        if isinstance(value, list) and len(value) == 4:
            return str(uuid.UUID(bytes=struct.pack(">4i", *value)))
        if isinstance(value, list) and len(value) == 2:
            return str(uuid.UUID(bytes=struct.pack(">2q", *value)))
    except struct.error as e:
        raise ValueError(f"not a UUID: {value!r} ({e})") from None
    return str(uuid.UUID(str(value)))


def plain(component) -> str:
    """The text of a text component as saved in NBT (a string, a compound or a list)."""
    if isinstance(component, str):
        return component
    if isinstance(component, list):
        return "".join(plain(c) for c in component)
    if isinstance(component, dict):
        return plain(component.get("text", "")) + plain(component.get("extra", []))
    return ""


# ---------------------------------------------------------------- the scoreboard


@dataclass(frozen=True)
class Team:
    name: str
    color: str = ""            # "" when the team has none
    prefix: object = None      # a text component as saved (a string or a compound), or None
    suffix: object = None
    players: list[str] = field(default_factory=list)


@dataclass
class Scoreboard:
    scores: dict[str, dict[str, int]]     # objective -> holder -> score
    displays: dict[str, dict[str, str]]   # objective -> holder -> display name (plain text), for holders with one
    teams: list[Team]


def scoreboard_path(folder: Path) -> Path:
    return folder / SCOREBOARD


def scoreboard(folder: Path) -> Scoreboard | None:
    """The world's scoreboard, or None when it has none saved. A holder saved twice keeps the later entry."""
    path = scoreboard_path(folder)
    if not path.is_file():
        return None
    root = nbt.read(path)
    with _shaped(path):
        data = root.get("data", root)
        scores: dict[str, dict[str, int]] = {}
        displays: dict[str, dict[str, str]] = {}
        for s in data.get("PlayerScores", []):
            # 26.3 leaves Score out when it is 0.
            scores.setdefault(s["Objective"], {})[s["Name"]] = s.get("Score", 0)
            display = s.get("display") or s.get("Display")
            if display:
                displays.setdefault(s["Objective"], {})[s["Name"]] = plain(display)
        teams = [Team(t.get("Name", ""), t.get("TeamColor") or "", t.get("MemberNamePrefix"),
                      t.get("MemberNameSuffix"), list(t.get("Players", []))) for t in data.get("Teams", [])]
    return Scoreboard(scores, displays, teams)


# ---------------------------------------------------------------- Open Parties and Claims


@dataclass(frozen=True)
class Member:
    uuid: str        # 8-4-4-4-12
    username: str    # as the party file has it, which may be an old name; "" when it has none


@dataclass(frozen=True)
class Party:
    id: str                 # the file's name (the party's UUID)
    owner: Member | None    # None when the file has no owner
    members: list[Member]   # the owner first, then the members, each once; empty without an owner
    name: str               # the owner's parties.name setting, "" when unset or unreadable


def parties(folder: Path) -> list[Party] | None:
    """Every party saved, by file name; None when the world has no parties folder (no party made yet).
    A party file not shaped as Open Parties and Claims saves it (a member whose UUID isn't one, say) is a
    ValueError naming it: standings has always stopped there rather than rank a faction without them."""
    where = folder / PARTIES
    if not where.is_dir():
        return None
    found = []
    for path in sorted(where.glob("*.nbt")):
        data = nbt.read(path)
        if not isinstance(data.get("owner"), dict):
            found.append(Party(path.stem, None, [], ""))
            continue
        members: list[Member] = []
        with _shaped(path):
            for p in [data["owner"], *data.get("members", [])]:
                u = uuid_text(p["uuid"])
                if all(m.uuid != u for m in members):
                    members.append(Member(u, p.get("username") or ""))
        found.append(Party(path.stem, members[0], members, party_name(folder, members[0].uuid)))
    return found


def party_name(folder: Path, owner_uuid: str) -> str:
    """The party name its owner set (/openpac-player-config: parties.name), or "" when unset or unreadable."""
    import tomllib  # 3.11+: here, so tools/drops.py still runs on 3.10

    path = folder / PLAYER_CONFIGS / f"{owner_uuid}.toml"
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    name = config.get("playerConfig", {}).get("parties", {}).get("name", "")
    return name.strip() if isinstance(name, str) else ""


def _claim_files(folder: Path) -> Iterator[tuple[Path, dict]]:
    """Each player-claims file with its dimensions compound as saved; none without a player-claims folder.
    Open Parties and Claims saves a player's claims as dimensions > claims > positions: [{x, z}] (chunks)."""
    where = folder / PLAYER_CLAIMS
    for path in sorted(where.glob("*.nbt")) if where.is_dir() else []:
        dimensions = nbt.read(path).get("dimensions", {})
        if not isinstance(dimensions, dict):
            raise ValueError(f"{path}: not as the server saves it (dimensions is not a compound)")
        yield path, dimensions


def claims(folder: Path, dimension: str) -> dict[str, list[tuple[int, int]]]:
    """Every chunk claimed in one dimension, whoever claimed it (players, parties' members, the server's spawn
    claim): claim file name (a player's UUID) -> chunks [(x, z)], in the order saved. Only that dimension is
    read, so a bad claim in another never stops it. No player-claims folder: no claims."""
    found = {}
    for path, dimensions in _claim_files(folder):
        with _shaped(path):
            found[path.stem] = [(int(p["x"]), int(p["z"])) for c in dimensions.get(dimension, {}).get("claims", [])
                                for p in c.get("positions", [])]
    return found


def claim_counts(folder: Path) -> dict[str, int]:
    """How many chunks each claim file (a player's UUID) claims, in every dimension. Positions are counted,
    not read, so one saved oddly still counts. No player-claims folder: no claims."""
    found = {}
    for path, dimensions in _claim_files(folder):
        with _shaped(path):
            found[path.stem] = sum(len(c.get("positions", [])) for dim in dimensions.values()
                                   for c in dim.get("claims", []))
    return found


# ---------------------------------------------------------------- the border


@dataclass(frozen=True)
class SavedBorder:
    center_x: float
    center_z: float
    size: float     # its width now
    target: float   # the width it is moving to (lerp_target); the same as size when it isn't moving


def border_path(folder: Path, dimension: str = OVERWORLD) -> Path:
    namespace, _, name = dimension.partition(":")
    return folder / "dimensions" / namespace / name / "data" / "minecraft" / "world_border.dat"


def border(folder: Path, dimension: str = OVERWORLD) -> SavedBorder | None:
    """A dimension's border as saved, or None when the world has none saved for it."""
    path = border_path(folder, dimension)
    if not path.is_file():
        return None
    root = nbt.read(path)
    with _shaped(path):
        data = root["data"]
        return SavedBorder(data["center_x"], data["center_z"], data["size"], data.get("lerp_target", data["size"]))
