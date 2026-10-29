"""A made-up saved world for the tests: the files tools/saved_world.py reads, laid out and shaped as 26.3 and
Open Parties and Claims save them (the paths are written out here, not taken from saved_world.py, so a wrong
path there fails the tests).

    folder = FakeWorld(tmp_path / "world").scores(("ev.cup", "red", 30)).claims(UUID, {OVERWORLD: [(0, 0)]}).path
"""
import json
import struct
import uuid
from pathlib import Path

from nbt_writer import Ints, Long, nbt

OVERWORLD = "minecraft:overworld"


def uuid_ints(text: str) -> Ints:
    """A UUID as Minecraft saves it: four ints."""
    return Ints(struct.unpack(">4i", uuid.UUID(text).bytes))


def member(player_uuid: str, username: str | None = None) -> dict:
    """A party file's owner or member entry. username None: the entry has none."""
    return {"uuid": uuid_ints(player_uuid), "rank": "MEMBER"} | ({"username": username} if username is not None else {})


def toml_string(text: str) -> str:
    """text as a TOML basic string: in double quotes, with backslash, the quote and control characters escaped."""
    def escape(c: str) -> str:
        if c in '\\"':
            return "\\" + c
        return f"\\u{ord(c):04x}" if ord(c) < 0x20 or c == "\x7f" else c
    return '"' + "".join(escape(c) for c in text) + '"'


def score_rows(*rows) -> list[dict]:
    """PlayerScores entries from (objective, holder, score[, more fields]). 26.3 leaves Score out when it is 0."""
    return [{"Objective": objective, "Name": name} | ({"Score": score} if score else {}) | (extra[0] if extra else {})
            for objective, name, score, *extra in rows]


def claim_file(chunks: dict[str, list[tuple[int, int]]]) -> dict:
    """A player-claims file as Open Parties and Claims 0.32 saves it: one claim per dimension."""
    return {"username": "x", "confirmedActivity": Long(0), "dimensions": {
        dim: {"claims": [{"state": {"subConfigIndex": -1, "forceloadable": 0},
                          "positions": [{"x": x, "z": z} for x, z in positions]}]}
        for dim, positions in chunks.items()}}


class FakeWorld:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

    def _write(self, rel: str, data: bytes) -> "FakeWorld":
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return self

    def scoreboard(self, board: dict) -> "FakeWorld":
        """A whole scoreboard.dat, as given (26.3 puts it under "data", with a DataVersion)."""
        return self._write("data/minecraft/scoreboard.dat", nbt(board, gzipped=True))

    def scores(self, *rows, teams: list[dict] | None = None) -> "FakeWorld":
        """A scoreboard.dat holding these score rows (score_rows) and teams."""
        data: dict = {"PlayerScores": score_rows(*rows)}
        if teams is not None:
            data["Teams"] = teams
        return self.scoreboard({"DataVersion": 5023, "data": data})

    def party(self, party_id: str, owner: dict | None, members=()) -> "FakeWorld":
        """A party file; owner and members are member(...) entries. owner None: no owner."""
        data = {"confirmedActivity": Long(1), "invites": [], "allies": [], "members": list(members)}
        if owner is not None:
            data = {"owner": owner} | data
        return self._write(f"data/openpartiesandclaims/parties/{party_id}.nbt", nbt(data))

    def party_name(self, owner_uuid: str, name: str) -> "FakeWorld":
        """The owner's player config with parties.name set, laid out as Open Parties and Claims writes it."""
        toml = (f"[playerConfig]\n\t[playerConfig.parties]\n\t\tname = {toml_string(name)}\n"
                "\t\tshareLocationWithParty = true\n")
        return self._write(f"data/openpartiesandclaims/player-configs/{owner_uuid}.toml", toml.encode())

    def claims(self, player: str, chunks: dict[str, list[tuple[int, int]]]) -> "FakeWorld":
        """A player's claims file (named by their UUID): dimension -> chunks."""
        return self._write(f"data/openpartiesandclaims/player-claims/{player}.nbt", nbt(claim_file(chunks)))

    def border(self, dimension: str, center_x: float, center_z: float, size: float,
               lerp_target: float | None = None) -> "FakeWorld":
        """A dimension's world_border.dat as 26.3 writes it (the fields read, plus a few that aren't)."""
        namespace, name = dimension.split(":")
        data = {"center_x": center_x, "center_z": center_z, "size": size,
                "lerp_target": size if lerp_target is None else lerp_target}
        data = {k: float(v) for k, v in data.items()} | {"lerp_time": Long(0), "warning_blocks": 5}
        return self._write(f"dimensions/{namespace}/{name}/data/minecraft/world_border.dat",
                           nbt({"DataVersion": 5023, "data": data}, gzipped=True))

    def advancements(self, player_uuid: str, done: dict[str, str], undone: dict[str, str] | None = None,
                     ) -> "FakeWorld":
        """A player's players/advancements/<uuid>.json as 26.3 writes it (pretty JSON, DataVersion last; seen on
        a 26.3 test server on 2026-10-25): advancement -> {"criteria": {name: "2026-10-25 21:12:32 -0700"},
        "done": bool}. `done` and `undone` map an advancement to its one criterion's time."""
        data = {adv: {"criteria": {"requirement": when}, "done": True} for adv, when in done.items()}
        data |= {adv: {"criteria": {"requirement": when}, "done": False} for adv, when in (undone or {}).items()}
        return self._write(f"players/advancements/{player_uuid}.json",
                           json.dumps(data | {"DataVersion": 5023}, indent=2).encode())

    def storage(self, namespace: str, contents: dict) -> "FakeWorld":
        """A namespace's command storage as 26.3 saves it: data/<namespace>/command_storage.dat, key -> compound."""
        return self._write(f"data/{namespace}/command_storage.dat",
                           nbt({"DataVersion": 5023, "data": {"contents": contents}}, gzipped=True))
