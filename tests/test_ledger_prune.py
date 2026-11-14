"""tools/ledger_prune.py: Sulfur Cube Expansion's button churn leaves Ledger's history, and nothing else does."""
import os
import sqlite3

import pytest

fcntl = pytest.importorskip("fcntl")  # the tool is for the Linux server (and macOS): no fcntl on Windows
import ledger_prune  # noqa: E402

# The live server's tables (Ledger 1.3.23), as `sqlite_master` has them, foreign keys and checks left out.
SCHEMA = """
CREATE TABLE ActionIdentifiers (id INTEGER PRIMARY KEY AUTOINCREMENT, action_identifier VARCHAR(16) NOT NULL);
CREATE TABLE ObjectIdentifiers (id INTEGER PRIMARY KEY AUTOINCREMENT, identifier TEXT NOT NULL);
CREATE TABLE sources (id INTEGER PRIMARY KEY AUTOINCREMENT, "name" VARCHAR(30) NOT NULL);
CREATE TABLE worlds (id INTEGER PRIMARY KEY AUTOINCREMENT, identifier TEXT NOT NULL);
CREATE TABLE players (id INTEGER PRIMARY KEY AUTOINCREMENT, player_id BLOB NOT NULL, player_name VARCHAR(16));
CREATE TABLE actions (id INTEGER PRIMARY KEY AUTOINCREMENT, action_id INT NOT NULL, "time" TEXT NOT NULL,
    x INT NOT NULL, y INT NOT NULL, z INT NOT NULL, world_id INT NOT NULL, object_id INT NOT NULL,
    old_object_id INT NOT NULL, block_state TEXT NULL, old_block_state TEXT NULL, "source" INT NOT NULL,
    player_id INT NULL, extra_data TEXT NULL, rolled_back BOOLEAN NOT NULL,
    CONSTRAINT chk_actions_signed_integer_id CHECK (id BETWEEN -2147483648 AND 2147483647));
CREATE INDEX actions_time ON actions ("time");
CREATE INDEX actions_source ON actions ("source");
CREATE INDEX actions_by_location ON actions (x, y, z, world_id);
"""
ACTIONS = {"block-place": 1, "block-break": 2, "item-insert": 3}
OBJECTS = {"minecraft:air": 1, "minecraft:mangrove_button": 2, "minecraft:stone": 3, "minecraft:light": 4}
SOURCES = {"player": 1, "command": 2, "gravity": 3}


def row(action, obj, old, source, player=None, t="2026-11-14 03:00:00", state=None, old_state=None):
    return (ACTIONS[action], t, 590, -20, -1340, 1, OBJECTS[f"minecraft:{obj}"], OBJECTS[f"minecraft:{old}"],
            state, old_state, SOURCES[source], player, None, 0)


CUBE = '{face:"floor",facing:"north",powered:"true"}'  # as the live Ledger wrote the churn's button
CHURN = [row("block-place", "mangrove_button", "air", "command", state=CUBE),
         row("block-break", "air", "mangrove_button", "command", old_state=CUBE),
         row("block-place", "air", "air", "command")]
KEEP = [row("block-place", "stone", "air", "player", player=1),               # a player building
        row("block-break", "air", "mangrove_button", "player", player=1),     # a player breaking a button
        row("block-place", "mangrove_button", "air", "command", player=1),    # a player's own /setblock
        row("block-place", "light", "air", "command"),                        # luminous cubes: not this tool's
        row("block-break", "air", "stone", "command"),                        # a staff /fill with no player
        row("block-break", "air", "stone", "gravity")]


def world(tmp_path, rows):
    w = tmp_path / "world"
    w.mkdir()
    db = sqlite3.connect(w / "ledger.sqlite")
    db.executescript(SCHEMA)
    db.executemany("INSERT INTO ActionIdentifiers VALUES (?, ?)", [(v, k) for k, v in ACTIONS.items()])
    db.executemany("INSERT INTO ObjectIdentifiers VALUES (?, ?)", [(v, k) for k, v in OBJECTS.items()])
    db.executemany('INSERT INTO sources VALUES (?, ?)', [(v, k) for k, v in SOURCES.items()])
    db.execute("INSERT INTO worlds VALUES (1, 'minecraft:overworld')")
    db.execute("INSERT INTO players VALUES (1, x'01', 'Alpha')")
    db.executemany("INSERT INTO actions (action_id, time, x, y, z, world_id, object_id, old_object_id, block_state,"
                   " old_block_state, source, player_id, extra_data, rolled_back) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   rows)
    db.commit()
    db.close()
    (w / "session.lock").write_bytes(b"")
    return w


def actions(path):
    db = sqlite3.connect(path)
    try:
        return db.execute("SELECT * FROM actions ORDER BY id").fetchall()
    finally:
        db.close()


def test_only_the_churn_leaves_and_every_other_row_keeps_its_id(tmp_path):
    w = world(tmp_path, CHURN * 3 + KEEP + CHURN)
    before = actions(w / "ledger.sqlite")
    r = ledger_prune.finish(w)
    after = actions(w / "ledger.sqlite")
    kept_ids = list(range(10, 16))  # KEEP's rows, after nine churn rows
    assert [a[0] for a in after] == kept_ids
    assert after == [b for b in before if b[0] in kept_ids]
    assert r["rows_kept"] == len(KEEP) and r["rows_before"] == len(before)
    # The old file is kept, whole, beside the new one.
    assert actions(w / "ledger.sqlite.before-prune") == before


def test_a_staff_fill_of_other_buttons_keeps_its_rows(tmp_path):
    east = '{face:"floor",facing:"east",powered:"false"}'
    staff = [row("block-place", "mangrove_button", "air", "command", state=east),
             row("block-break", "air", "mangrove_button", "command", old_state=east)]
    w = world(tmp_path, CHURN + staff)
    assert ledger_prune.finish(w)["rows_kept"] == 2


def test_an_interrupted_first_copy_keeps_its_batches(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_prune, "BATCH", 3)
    w = world(tmp_path, KEEP + CHURN)
    real, calls = sqlite3.Connection.execute, []

    def stop_in_the_second_batch(con, sql, *a):
        if sql.startswith("INSERT INTO main.actions"):
            calls.append(sql)
            if len(calls) == 2:
                raise KeyboardInterrupt
        return real(con, sql, *a)
    with holding(w):
        monkeypatch.setattr(ledger_prune, "_open", lambda world, _o=ledger_prune._open: Wrap(_o(world),
                                                                                             stop_in_the_second_batch))
        with pytest.raises(KeyboardInterrupt):
            ledger_prune.copy(w)
        monkeypatch.undo()
        db = sqlite3.connect(w / "ledger.sqlite.pruning")
        assert db.execute("SELECT upto FROM ledger_prune_progress").fetchone() == (3,)  # the first batch stayed
        db.close()
        assert ledger_prune.copy(w) == len(KEEP + CHURN)
    assert ledger_prune.finish(w)["rows_kept"] == len(KEEP)


class Wrap:
    """A connection whose execute goes through `hook` (sqlite3.Connection.execute can't be patched)."""

    def __init__(self, con, hook):
        self.con, self.hook = con, hook

    def execute(self, sql, *a):
        return self.hook(self.con, sql, *a)

    def __getattr__(self, name):
        return getattr(self.con, name)


def test_a_failed_swap_leaves_the_old_file_in_place(tmp_path, monkeypatch):
    w = world(tmp_path, KEEP + CHURN)
    before = actions(w / "ledger.sqlite")
    real = os.replace

    def refuse_the_new_file(src, dst):
        if str(src).endswith(".pruning"):
            raise OSError("disk went away")
        return real(src, dst)
    monkeypatch.setattr(ledger_prune.os, "replace", refuse_the_new_file)
    with pytest.raises(OSError):
        ledger_prune.finish(w)
    assert actions(w / "ledger.sqlite") == before  # never missing, and still the old history
    monkeypatch.undo()
    (w / "ledger.sqlite.before-prune").unlink()  # "put it back": it is the same file under a second name
    assert ledger_prune.finish(w)["rows_kept"] == len(KEEP)  # the finished copy runs again


def test_the_new_file_has_the_old_tables_indexes_and_sequence(tmp_path):
    w = world(tmp_path, KEEP + CHURN)
    ledger_prune.finish(w)
    db = sqlite3.connect(w / "ledger.sqlite")
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
    assert {"actions_time", "actions_source", "actions_by_location", "players", "worlds"} <= names
    assert db.execute("SELECT player_name FROM players").fetchall() == [("Alpha",)]
    # New rows carry on after the old file's last id, not after the last kept one.
    db.execute("INSERT INTO actions (action_id, time, x, y, z, world_id, object_id, old_object_id, source, rolled_back)"
               " VALUES (1, 't', 0, 0, 0, 1, 3, 1, 1, 0)")
    assert db.execute("SELECT max(id) FROM actions").fetchone()[0] == len(KEEP + CHURN) + 1
    assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    db.close()


def test_a_history_without_the_churn_is_copied_whole(tmp_path):
    w = world(tmp_path, KEEP)
    before = actions(w / "ledger.sqlite")
    ledger_prune.finish(w)
    assert actions(w / "ledger.sqlite") == before


def test_the_finish_refuses_while_the_server_holds_the_world(tmp_path):
    w = world(tmp_path, KEEP + CHURN)
    before = actions(w / "ledger.sqlite")
    # Python's lock and the JVM's FileChannel lock are both fcntl locks, which don't conflict within one process:
    # the lock is held from a child.
    with holding(w), pytest.raises(ledger_prune.WorldOpen, match="world is open"):
        ledger_prune.finish(w)
    assert actions(w / "ledger.sqlite") == before
    assert not (w / "ledger.sqlite.pruning").exists() and not (w / "ledger.sqlite.before-prune").exists()


def test_an_open_world_gets_the_copy_and_the_finish_catches_up(tmp_path, capsys):
    w = world(tmp_path, CHURN + KEEP[:3] + CHURN)
    with holding(w):
        assert ledger_prune.main([str(w)]) == 0
        assert "Stop the server and run this again" in capsys.readouterr().out
        assert (w / "ledger.sqlite.pruning").exists() and not (w / "ledger.sqlite.before-prune").exists()
    # Meanwhile Ledger wrote more, rolled one copied row back and purged another.
    db = sqlite3.connect(w / "ledger.sqlite")
    db.executemany("INSERT INTO actions (action_id, time, x, y, z, world_id, object_id, old_object_id, block_state,"
                   " old_block_state, source, player_id, extra_data, rolled_back) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   KEEP[3:] + CHURN)
    db.execute("UPDATE actions SET rolled_back = 1 WHERE id = 4")
    db.execute("DELETE FROM actions WHERE id = 5")
    db.execute("INSERT INTO players VALUES (2, x'02', 'Bravo')")
    db.commit()
    db.close()
    before = actions(w / "ledger.sqlite")
    r = ledger_prune.finish(w)
    after = actions(w / "ledger.sqlite")
    assert after == [b for b in before if b[0] in (4, 6, 10, 11, 12)]
    assert after[0][-1] == 1  # the rollback came across
    assert r["rows_kept"] == 5
    db = sqlite3.connect(w / "ledger.sqlite")
    assert db.execute("SELECT count(*) FROM players").fetchone()[0] == 2
    assert not db.execute("SELECT name FROM sqlite_master WHERE name = 'ledger_prune_progress'").fetchone()
    db.close()


def test_a_second_copy_adds_only_the_new_rows(tmp_path):
    w = world(tmp_path, KEEP)
    with holding(w):
        assert ledger_prune.copy(w) == len(KEEP)
        assert ledger_prune.copy(w) == len(KEEP)  # nothing new: nothing copied twice
    ledger_prune.finish(w)
    assert len(actions(w / "ledger.sqlite")) == len(KEEP)


def test_a_file_in_the_way_is_not_taken_for_a_copy(tmp_path):
    w = world(tmp_path, KEEP)
    sqlite3.connect(w / "ledger.sqlite.pruning").execute("CREATE TABLE t (x)").connection.close()
    with pytest.raises(ledger_prune.PruneError, match="not one of this tool's copies"):
        ledger_prune.copy(w)


class holding:
    """Holds the world's session.lock from a child process, as the server would."""

    def __init__(self, w):
        import multiprocessing
        ctx = multiprocessing.get_context("fork")
        self.ready, self.done = ctx.Event(), ctx.Event()
        self.proc = ctx.Process(target=_hold, args=(w / "session.lock", self.ready, self.done))

    def __enter__(self):
        self.proc.start()
        assert self.ready.wait(10)

    def __exit__(self, *exc):
        self.done.set()
        self.proc.join(10)


def _hold(lock, ready, done):
    with open(lock, "rb+") as f:
        fcntl.lockf(f, fcntl.LOCK_EX)
        ready.set()
        done.wait(10)


def test_rows_the_server_left_in_the_write_ahead_log_are_kept(tmp_path):
    w = world(tmp_path, KEEP)
    left = sqlite3.connect(w / "ledger.sqlite")  # a server that stopped without folding its log in
    left.execute("PRAGMA journal_mode = WAL")
    left.execute("PRAGMA wal_autocheckpoint = 0")
    left.executemany("INSERT INTO actions (action_id, time, x, y, z, world_id, object_id, old_object_id, block_state,"
                     " old_block_state, source, player_id, extra_data, rolled_back) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", KEEP[:1] + CHURN)
    left.commit()
    assert (w / "ledger.sqlite-wal").stat().st_size
    try:
        r = ledger_prune.finish(w)
    finally:
        left.close()
    assert r["rows_kept"] == len(KEEP) + 1
    # The old file's sidecars went with it, none is left beside the new one.
    assert not (w / "ledger.sqlite-wal").exists() and not (w / "ledger.sqlite-shm").exists()


def test_the_finish_keeps_the_world_locked_until_the_swap(tmp_path, monkeypatch):
    w = world(tmp_path, KEEP + CHURN)
    seen = []
    real = ledger_prune.copy

    def copy_and_try_the_lock(world):
        seen.append(locked_by_someone_else(w / "session.lock"))
        return real(world)
    monkeypatch.setattr(ledger_prune, "copy", copy_and_try_the_lock)
    ledger_prune.finish(w)
    assert seen == [True]  # a server starting now would find the world locked
    assert not locked_by_someone_else(w / "session.lock")  # and free again after


def locked_by_someone_else(lock):
    import multiprocessing
    ctx = multiprocessing.get_context("fork")
    out = ctx.Queue()

    def probe():
        with open(lock, "rb+") as f:
            try:
                fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                out.put(False)
            except OSError:
                out.put(True)
    p = ctx.Process(target=probe)
    p.start()
    p.join(10)
    return out.get(timeout=5)


def test_the_copy_reads_in_batches_and_a_table_added_later_comes_across(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_prune, "BATCH", 2)
    w = world(tmp_path, CHURN + KEEP + CHURN)
    with holding(w):
        assert ledger_prune.copy(w) == 12
    db = sqlite3.connect(w / "ledger.sqlite")
    db.execute("CREATE TABLE extra (id INTEGER PRIMARY KEY, v TEXT)")
    db.execute("INSERT INTO extra VALUES (1, 'new')")
    db.commit()
    db.close()
    r = ledger_prune.finish(w)
    assert r["rows_kept"] == len(KEEP)
    db = sqlite3.connect(w / "ledger.sqlite")
    assert db.execute("SELECT v FROM extra").fetchall() == [("new",)]
    db.close()


@pytest.mark.skipif(os.geteuid() == 0, reason="root opens any file")
def test_a_lock_it_cant_open_says_whose_it_is(tmp_path):
    w = world(tmp_path, KEEP)
    (w / "session.lock").chmod(0o400)
    with pytest.raises(ledger_prune.PruneError, match="run this as the user that owns it"):
        ledger_prune.finish(w)


def test_a_second_run_is_refused(tmp_path):
    w = world(tmp_path, KEEP + CHURN)
    ledger_prune.finish(w)
    with pytest.raises(ledger_prune.PruneError, match="already there"):
        ledger_prune.finish(w)


def test_main_finishes_a_closed_world_and_fails_without_a_database(tmp_path, capsys):
    w = world(tmp_path, KEEP + CHURN)
    assert ledger_prune.main([str(w)]) == 0
    assert "kept 6 of about 9 rows" in capsys.readouterr().out
    assert ledger_prune.main([str(tmp_path)]) == 1
    assert "no " in capsys.readouterr().err
