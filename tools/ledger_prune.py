"""Takes Sulfur Cube Expansion's button churn out of Ledger's history: a long copy while the server runs, then a short
finish with it stopped.

    python3 tools/ledger_prune.py WORLD_DIR    server running: copies the history without the churn into
                                               WORLD_DIR/ledger.sqlite.pruning (run again, it adds only what's new)
                                               server stopped: catches the copy up, swaps it in and keeps the old
                                               file as ledger.sqlite.before-prune

Run it as the user the server runs as (it opens world/session.lock to see whether the server is up). Linux and macOS.

Before the charged-cube patch (docs/MAINTAINING.md, "Patches this pack carries"), every charged sulfur cube broke and
placed a powered mangrove button every tick, and Ledger logged each change: about 29 million rows a day, 99.9% of the
live server's history (57 GB by 14 November 2026). Those rows say nothing about players. A row is left out when it is
from the `command` source, with no player, and is one of the churn's three shapes:

    block-place  mangrove_button over air        (the cube placing its button)
    block-break  air over mangrove_button        (the marker taking it away)
    block-place  air over air                    (the marker's fill finding nothing; never a change)

and the button in it is the one upstream's fill makes, {face:"floor",facing:"north",powered:"true"}, so a staff
/fill of other buttons keeps its rows.

Every other row is copied as it is, with its id. Deleting from the old file instead would take hours with the server
stopped and leave it 57 GB on disk.

The copy reads the old file read-only in batches of ids, each a short read, so Ledger keeps writing and checkpointing
meanwhile. The finish holds world/session.lock for its whole run, so the server can't start under it. It folds the
old file's write-ahead log in, copies the rows added since, the small tables again (new players and blocks), and what
Ledger changed in rows already copied (a rollback or restore flips `rolled_back`, a purge deletes rows), then builds
the indexes (and any views or triggers), checks the file and swaps the two, the old one with its -wal and -shm;
ledger.sqlite exists at every step of the swap. Nothing in the old file's rows
changes; it is kept for staff to delete once the server runs well on the new one (docs/LIVE.md, "Ledger's history").
"""
import argparse
import contextlib
import fcntl
import os
import sqlite3
import sys
from pathlib import Path

DB = "ledger.sqlite"
NEW = DB + ".pruning"
KEPT = DB + ".before-prune"
SIDECARS = ("-wal", "-shm")
PROGRESS = "ledger_prune_progress"  # in the new file only: the old file's newest id copied so far
BATCH = 5_000_000  # ids per read of the old file
BUTTON, AIR = "minecraft:mangrove_button", "minecraft:air"
BUTTON_STATE = '{face:"floor",facing:"north",powered:"true"}'  # as Ledger writes it


class PruneError(Exception):
    pass


class WorldOpen(PruneError):
    pass


@contextlib.contextmanager
def world_lock(world: Path):
    """Holds the world's session.lock (an fcntl lock, as the JVM's FileChannel lock is) until the block ends.

    Raises WorldOpen while the server holds it. A world without one has never been opened: nothing to hold.
    """
    lock = world / "session.lock"
    if not lock.exists():
        yield
        return
    try:
        f = open(lock, "rb+")
    except PermissionError:
        raise PruneError(f"can't open {lock} to see whether the server is up: run this as the user that owns it "
                         f"(uid {lock.stat().st_uid})") from None
    with f:
        try:
            fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise WorldOpen("the world is open (session.lock is held)") from None
        try:
            yield
        finally:
            fcntl.lockf(f, fcntl.LOCK_UN)


def churn(con) -> tuple[str, list]:
    """The WHERE clause that matches the churn's rows in the attached `old`, and its parameters."""
    def one(sql, *args):
        row = con.execute(sql, args).fetchone()
        return row[0] if row else None

    source = one("SELECT id FROM old.sources WHERE name = 'command'")
    button = one("SELECT id FROM old.ObjectIdentifiers WHERE identifier = ?", BUTTON)
    air = one("SELECT id FROM old.ObjectIdentifiers WHERE identifier = ?", AIR)
    place = one("SELECT id FROM old.ActionIdentifiers WHERE action_identifier = 'block-place'")
    brk = one("SELECT id FROM old.ActionIdentifiers WHERE action_identifier = 'block-break'")
    if None in (source, button, air, place, brk):
        return "0", []  # this history never had the churn
    where = ('"source" = ? AND player_id IS NULL AND ('
             "(action_id = ? AND object_id = ? AND old_object_id = ? AND block_state IS ?) OR "
             "(action_id = ? AND object_id = ? AND old_object_id = ? AND old_block_state IS ?) OR "
             "(action_id = ? AND object_id = ? AND old_object_id = ?))")
    return where, [source, place, button, air, BUTTON_STATE, brk, air, button, BUTTON_STATE, place, air, air]


def _open(world: Path) -> sqlite3.Connection:
    new = world / NEW
    con = sqlite3.connect(new.as_uri(), uri=True, isolation_level=None)  # uri: so ATTACH can open the old read-only
    con.execute("PRAGMA journal_mode = MEMORY")  # rolls back a failed run; a crash leaves a file to delete
    con.execute("PRAGMA synchronous = OFF")
    con.execute("ATTACH DATABASE ? AS old", (f"{(world / DB).as_uri()}?mode=ro",))
    return con


def _small_tables(con) -> list[tuple[str, str]]:
    return [(n, s) for n, s in con.execute(
        "SELECT name, sql FROM old.sqlite_master WHERE type = 'table' AND sql IS NOT NULL "
        "AND name NOT LIKE 'sqlite_%' AND name != 'actions'")]


def _has(con, schema: str, name: str) -> bool:
    return con.execute(f"SELECT 1 FROM {schema}.sqlite_master WHERE name = ?", (name,)).fetchone() is not None


def copy(world: Path) -> int:
    """Copies (or adds to the copy) the kept rows up to the old file's newest; returns the newest id copied."""
    world = Path(world).resolve()
    if not (world / DB).is_file():
        raise PruneError(f"no {world / DB}")
    if (world / KEPT).exists():
        raise PruneError(f"{KEPT} is already there: delete it (or put it back) first")
    fresh = not (world / NEW).exists()  # only until its tables are committed: then batches are worth keeping
    con = None
    try:
        con = _open(world)
        con.execute("BEGIN")
        if fresh:
            actions = con.execute("SELECT sql FROM old.sqlite_master WHERE name = 'actions'").fetchone()
            if not actions:
                raise PruneError(f"{DB} has no actions table: is it Ledger's?")
            con.execute(actions[0])
            con.execute(f"CREATE TABLE {PROGRESS} (upto INTEGER NOT NULL)")
            con.execute(f"INSERT INTO {PROGRESS} VALUES (0)")
        elif not _has(con, "main", PROGRESS):
            raise PruneError(f"{NEW} is not one of this tool's copies: delete it first")
        con.execute("COMMIT")
        fresh = False
        where, args = churn(con)
        newest = con.execute("SELECT coalesce(max(id), 0) FROM old.actions").fetchone()[0]
        done = con.execute(f"SELECT upto FROM {PROGRESS}").fetchone()[0]
        while done < newest:  # one short read of the old file per batch, committed with its progress
            upto = min(done + BATCH, newest)
            con.execute("BEGIN")
            con.execute("INSERT INTO main.actions SELECT * FROM old.actions "
                        f"WHERE id > ? AND id <= ? AND NOT ({where})", [done, upto, *args])
            con.execute(f"UPDATE {PROGRESS} SET upto = ?", (upto,))
            con.execute("COMMIT")
            done = upto
    except BaseException:
        if con is not None:
            if con.in_transaction:
                con.execute("ROLLBACK")
            con.close()
        if fresh:
            (world / NEW).unlink(missing_ok=True)
        raise
    con.close()
    return done


def _checkpoint(db: Path) -> None:
    """Folds a write-ahead log the server left into the old file, as SQLite itself would on the next open."""
    wal = Path(str(db) + "-wal")
    if not (wal.exists() and wal.stat().st_size):
        return
    con = sqlite3.connect(db)
    try:
        busy, _, _ = con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    finally:
        con.close()
    if busy:
        raise PruneError(f"{wal.name} could not be folded in: is something else using {db.name}?")


def finish(world: Path) -> dict:
    """With the world closed (and kept closed): catches the copy up, builds its indexes and swaps it in."""
    world = Path(world).resolve()
    db, new, kept = world / DB, world / NEW, world / KEPT
    with world_lock(world):
        _checkpoint(db)
        upto = copy(world)  # the rows added since the last copy (all of them, if there was none)
        con = _open(world)
        try:
            con.execute("BEGIN")
            for name, sql in _small_tables(con):
                if not _has(con, "main", name):
                    con.execute(sql)  # first finish, or a table Ledger added since the copy began
                con.execute(f'DELETE FROM main."{name}"')
                con.execute(f'INSERT INTO main."{name}" SELECT * FROM old."{name}"')
            # Rows Ledger changed or purged after they were copied: one lookup each, and only those rows written.
            changed = con.execute("SELECT m.id, o.id IS NULL, o.rolled_back FROM main.actions m "
                                  "LEFT JOIN old.actions o ON o.id = m.id "
                                  "WHERE o.id IS NULL OR o.rolled_back IS NOT m.rolled_back").fetchall()
            for rid, gone, rolled_back in changed:
                if gone:
                    con.execute("DELETE FROM main.actions WHERE id = ?", (rid,))
                else:
                    con.execute("UPDATE main.actions SET rolled_back = ? WHERE id = ?", (rolled_back, rid))
            # New rows carry on after the old file's last id, not after the last kept one.
            con.execute("DELETE FROM main.sqlite_sequence")
            con.execute("INSERT INTO main.sqlite_sequence SELECT * FROM old.sqlite_sequence")
            # Indexes, then any views and triggers, so the new file has the old one's whole schema.
            rest = con.execute("SELECT type, name, sql FROM old.sqlite_master WHERE sql IS NOT NULL "
                               "AND type IN ('index', 'view', 'trigger') "
                               "ORDER BY type = 'index' DESC").fetchall()
            for _kind, name, sql in rest:
                if not _has(con, "main", name):  # a finish run again after a failed swap built them already
                    con.execute(sql)
            kept_rows = con.execute("SELECT count(*) FROM main.actions").fetchone()[0]
            if con.execute("PRAGMA main.quick_check").fetchone()[0] != "ok":
                raise PruneError(f"{NEW} failed SQLite's check; nothing was swapped")
            con.execute("COMMIT")
            con.execute("DETACH DATABASE old")
            con.execute("PRAGMA journal_mode = WAL")  # as Ledger keeps it
        except BaseException:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

        # ledger.sqlite exists at every step: the old file gets its second name first, then the new one replaces
        # the first name in one rename. The progress table stays until then, so a finish that fails here can run
        # again.
        st = db.stat()
        if os.geteuid() == 0:
            os.chown(new, st.st_uid, st.st_gid)
        os.chmod(new, st.st_mode & 0o777)
        os.link(db, kept)
        for side in SIDECARS:  # the old file's (empty after the checkpoint): they go with it
            if Path(str(db) + side).exists():
                os.replace(str(db) + side, str(kept) + side)
        os.replace(new, db)
        con = sqlite3.connect(db)
        try:
            con.execute(f"DROP TABLE IF EXISTS {PROGRESS}")
            con.commit()
        finally:
            con.close()
    return {"rows_before": upto, "rows_kept": kept_rows, "bytes_before": st.st_size, "bytes_after": db.stat().st_size}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Take Sulfur Cube Expansion's button churn out of Ledger's history: run "
                                             "it with the server running (the long copy), then stopped (the finish).")
    ap.add_argument("world", type=Path, help="the world folder holding ledger.sqlite")
    args = ap.parse_args(argv)
    try:
        try:
            r = finish(args.world)
        except WorldOpen:
            upto = copy(args.world)
            print(f"copied up to row {upto:,} into {args.world / NEW}. Stop the server and run this again to finish "
                  "(it adds only what's new).")
            return 0
    except (PruneError, sqlite3.Error, OSError) as e:
        print(f"ledger_prune: {e}", file=sys.stderr)
        return 1
    print(f"kept {r['rows_kept']:,} of about {r['rows_before']:,} rows; "
          f"{r['bytes_before'] / 1e9:.1f} GB -> {r['bytes_after'] / 1e9:.2f} GB. "
          f"The old file is {args.world / KEPT}: delete it once the server runs well.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
