"""Ledger's history (world/ledger.sqlite), read-only: the one module that knows its tables.

    Ledger(path)                        opens it read-only (FileNotFoundError when it isn't there, sqlite3.Error when
                                        it can't be opened) and reads the names its numbers stand for
    .player_rows(start, end)            the rows players made in a span (the Rule check)
    .portal_breaks(start, end)          the portal blocks that went in a span
    .placer(x, y, z, world, before, cache)
                                        who last placed a block before a time
    .around(x, y, z, radius, world, since, kinds, who, most, seconds)
                                        the rows in a box (the staff page's "Who changed this block"), bounded
    .close()

Times are Ledger's own: naive Pacific text ("2026-11-14 03:00:00.000"), compared as text. The rule for a row a
player made: a player id of 1 or more, and not the `command` source (data packs' blocks: Dynamic Lights' lights and,
before its patch, Sulfur Cube Expansion's buttons, millions a day). Every query names the index it needs: a scan of
the actions table takes minutes and slows the game.
"""
import contextlib
import sqlite3
import time
from pathlib import Path

WORLD_NAMES = {"minecraft:overworld": "Overworld", "minecraft:the_nether": "Nether", "minecraft:the_end": "End"}


class Busy(Exception):
    """The database was locked or busy (the game writing): try again later."""


class NoIndex(Exception):
    """The database lacks the index a query needs: reading the whole table instead would slow the game."""


class Ledger:
    """Ledger's database, read-only, and the names its numbers stand for."""

    def __init__(self, path: Path):
        if not path.is_file():
            raise FileNotFoundError(path)
        self.db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        self.objects = {i: name.removeprefix("minecraft:")
                        for i, name in self.db.execute("select id, identifier from ObjectIdentifiers")}
        self.object_ids = {name: i for i, name in self.objects.items()}
        self.actions = {name: i for i, name in self.db.execute("select id, action_identifier from ActionIdentifiers")}
        self.sources = {name: i for i, name in self.db.execute('select id, "name" from sources')}
        self.worlds = {i: WORLD_NAMES.get(name, name)
                       for i, name in self.db.execute("select id, identifier from worlds")}
        self.players = {}
        self.first_join = {}
        for i, name, first in self.db.execute("select id, player_name, first_join from players"):
            self.players[i] = name
            self.first_join[name] = first
        self.indexes = {r[0] for r in self.db.execute("select name from sqlite_master where type='index'")}

    def act(self, name: str) -> int:
        return self.actions.get(name, -1)

    def world_id(self, label: str) -> int:
        return next((i for i, n in self.worlds.items() if n == label), -1)

    def player_rows(self, start: str, end: str) -> list[tuple]:
        """The week's rows done by a player: not the ones commands made (source command; data packs' blocks)."""
        hint = "indexed by actions_player_id" if "actions_player_id" in self.indexes else ""
        query = (f"select time, action_id, x, y, z, world_id, object_id, old_object_id, player_id, extra_data "
                 f"from actions {hint} where player_id >= 1 and time >= ? and time < ? and source != ?")
        return self.db.execute(query, (start, end, self.sources.get("command", -1))).fetchall()

    def portal_breaks(self, start: str, end: str) -> list[tuple]:
        """Every portal block that went in the week, by a player or by itself (source gravity)."""
        portal = self.object_ids.get("nether_portal")
        if portal is None:
            return []
        hint = "indexed by actions_old_object_id" if "actions_old_object_id" in self.indexes else ""
        return self.db.execute(
            f"select time, x, y, z, world_id, player_id, source from actions {hint} "
            "where old_object_id = ? and action_id = ? and time >= ? and time < ?",
            (portal, self.act("block-break"), start, end)).fetchall()

    def placer(self, x: int, y: int, z: int, world: int, before: str, cache: dict) -> tuple[str, str] | None:
        """Who last placed the block at a spot before a time, and what it was (the container's owner)."""
        key = (x, y, z, world)
        if key not in cache:
            cache[key] = self.db.execute(
                "select time, player_id, object_id from actions where x = ? and y = ? and z = ? and world_id = ? "
                "and action_id = ? and player_id >= 1 order by time", (*key, self.act("block-place"))).fetchall()
        best = None
        for t, p, o in cache[key]:
            if t <= before:
                best = (self.players.get(p, str(p)), self.objects.get(o, str(o)))
        return best

    def around(self, x: int, y: int, z: int, radius: int, world: int, since: str, kinds: set[int] | None,
               who: int | None, most: int, seconds: float) -> tuple[list[tuple], bool]:
        """The rows in the box around (x, y, z) since a time, not made by commands, only of action ids KINDS (None:
        all) and player WHO (None: anyone): (rows, stopped), stopped when MOST rows or SECONDS of the database's
        time ran out first. One indexed (x, y) column at a time, from the asked block outward, so a cap keeps the
        rows nearest to it. Each row: time, action, x, y, z, object, old object, player, source, rolled_back, id.
        Busy when the database is locked, NoIndex when it has no location index."""
        if "actions_by_location" not in self.indexes:
            raise NoIndex("actions_by_location")
        deadline = time.monotonic() + seconds
        skip = self.sources.get("command", -1)
        self.db.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10000)
        query = ("select time, action_id, x, y, z, object_id, old_object_id, player_id, source, rolled_back, id "
                 "from actions indexed by actions_by_location "
                 "where x = ? and y = ? and z between ? and ? and world_id = ? and time >= ?")
        rows, stopped = [], False
        try:
            columns = sorted(((cx, cy) for cx in range(x - radius, x + radius + 1)
                              for cy in range(y - radius, y + radius + 1)),
                             key=lambda c: max(abs(c[0] - x), abs(c[1] - y)))
            for cx, cy in columns:
                for row in self.db.execute(query, (cx, cy, z - radius, z + radius, world, since)):
                    if row[8] == skip or (kinds is not None and row[1] not in kinds) \
                            or (who is not None and row[7] != who):
                        continue
                    rows.append(row)
                if len(rows) > most or time.monotonic() > deadline:
                    return rows, True
        except sqlite3.OperationalError as e:
            if "interrupt" not in str(e).lower():
                raise Busy(str(e)) from None
            stopped = True
        finally:
            self.db.set_progress_handler(None, 0)
        return rows, stopped

    def close(self) -> None:
        with contextlib.suppress(sqlite3.Error):
            self.db.close()
