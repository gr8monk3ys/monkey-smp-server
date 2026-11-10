"""The restore drill against a fake snapshot: deploy/monkey-restore-drill.sh with fake restic (through a fake
monkey-backup.sh), docker and rsync, and tools/restore_drill.py on its own."""
import contextlib
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

import restore_drill
from repo import REPO

SCRIPT = REPO.root / "deploy" / "monkey-restore-drill.sh"
DASH = shutil.which("dash")
needs_dash = pytest.mark.skipif(not DASH, reason="needs dash")
NOW = dt.datetime(2026, 11, 9, 12, 0, tzinfo=dt.UTC)
FULL = "a1b2c3d4" + "0" * 56
UNFLUSHED = "ffff0000" + "0" * 56


def level_dat(ticks):
    """A gzipped level.dat holding only Data.Time."""
    def name(s):
        return struct.pack(">H", len(s)) + s.encode()
    body = b"\x0a" + name("") + b"\x0a" + name("Data") + b"\x04" + name("Time") + struct.pack(">q", ticks) + b"\0\0"
    return gzip.compress(body)


def snapshots():
    return [{"id": FULL, "time": "2026-11-09T09:00:02.123456789-00:00", "tags": ["world"]},
            {"id": UNFLUSHED, "time": "2026-11-09T11:00:00Z", "tags": ["world", "unflushed"]},
            {"id": "b" * 64, "time": "2026-11-08T09:00:00+00:00", "tags": ["world", "stopped"]}]


# ---------------------------------------------------------------- tools/restore_drill.py

def test_pick_takes_the_newest_snapshot_that_is_not_unflushed():
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert restore_drill.main(["pick"], io.StringIO(json.dumps(snapshots())), NOW) == 0
    assert out.getvalue() == f"{FULL} 2026-11-09T09:00Z 2\n"


@pytest.mark.parametrize("data", ["[]", json.dumps([snapshots()[1]]), "{}", "not json",
                                  json.dumps([{"id": "../x", "time": "2026-11-09T09:00:00Z"}]),
                                  json.dumps([{"id": FULL, "time": "2026-11-09T09:00:00"}])])   # no time zone
def test_pick_with_nothing_safe_to_restore_says_so(data, capsys):
    assert restore_drill.main(["pick"], io.StringIO(data), NOW) == 1
    assert "restore drill:" in capsys.readouterr().err


def test_level_time_reads_the_restored_level_dat(tmp_path, capsys):
    (tmp_path / "level.dat").write_bytes(level_dat(123456))
    assert restore_drill.main(["level-time", str(tmp_path / "level.dat")]) == 0
    assert capsys.readouterr().out == "123456\n"
    (tmp_path / "level.dat").write_bytes(b"\x1f\x8b broken")
    assert restore_drill.main(["level-time", str(tmp_path / "level.dat")]) == 1
    assert restore_drill.main(["level-time", str(tmp_path / "missing.dat")]) == 1


# ---------------------------------------------------------------- the drill script

def msys(path):
    """A path as dash on Git for Windows takes it (/c/...); unchanged elsewhere."""
    p = path.as_posix()
    return f"/{p[0].lower()}{p[2:]}" if re.match(r"[A-Za-z]:/", p) else p


def tree(folder):
    """A digest of every file name and content under folder."""
    h = hashlib.sha256()
    for f in sorted(folder.rglob("*")):
        h.update(f.relative_to(folder).as_posix().encode())
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()


@pytest.fixture
def drill(tmp_path):
    """Runs the drill as a fake root; returns (exit code, logged lines, calls, the paths)."""
    if not DASH:
        pytest.skip("needs dash")
    bin_dir, calls = tmp_path / "bin", tmp_path / "calls"
    bin_dir.mkdir()
    live = tmp_path / "live"
    for d in ("monkey", "docker", "java", "pwsh", "server/mods", "server/world/region"):
        (live / d).mkdir(parents=True)
    (live / "monkey" / "monkey.sh").write_text("x")
    (live / "docker" / ".env").write_text("RCON=secret\n")
    (live / "server" / "mods" / "a.jar").write_text("jar")
    (live / "server" / "world" / "level.dat").write_bytes(level_dat(999))
    # The fake snapshot: what restic restores.
    snap = tmp_path / "snapshot"
    (snap / "world" / "region").mkdir(parents=True)
    (snap / "world" / "level.dat").write_bytes(level_dat(5000))
    (snap / "world" / "region" / "r.0.0.mca").write_bytes(b"region")
    (snap / "server.properties").write_text("level-name=world\n")
    (tmp_path / "snapshots.json").write_text(json.dumps(snapshots()))
    scratch_root = tmp_path / "scratch"
    scratch_root.mkdir()
    fakes = {
        "docker": 'case "$1 $2" in "image inspect") exit "${FAKE_RC_image:-0}" ;; '
                  '"inspect -f") echo "${FAKE_RUNNING:-true}"; exit 0 ;; '
                  '"inspect "*) [ -e "$FAKE_STATE/container" ] || exit 1; exit 0 ;; '
                  '"run "*) : >"$FAKE_STATE/container"; exit 0 ;; '
                  '"rm "*) rm -f "$FAKE_STATE/container"; exit 0 ;; '
                  '"logs "*) echo "boot log line"; exit 0 ;; esac\n'
                  'case " $* " in *" rcon list "*) exit "${FAKE_RC_list:-0}" ;; '
                  '*" time query gametime "*) echo "The time is ${FAKE_GAMETIME-5100}"; exit 0 ;; esac\nexit 0',
        "flock": "exit 0", "sleep": "exit 0", "chown": "exit 0", "rsync": "exit 0", "curl": "exit 0",
        "timeout": 'shift\nexec "$@"',
        "df": 'echo "Filesystem 1024-blocks Used Available Capacity Mounted"\n'
              'echo "x 1 1 ${FAKE_FREE_KB:-99999999} 1% /"',
        # python_ok passes; the rest runs the real Python, its \r\n on Windows made \n as on the VPS.
        "python3": f'case "$1" in -c) exit 0 ;; esac\nout=$("{msys_python()}" "$@") && rc=0 || rc=$?\n'
                   '[ -z "$out" ] || printf "%s\\n" "$out" | tr -d "\\r"\nexit "$rc"',
    }
    for name, body in fakes.items():
        (bin_dir / name).write_text(f'#!/bin/sh\necho "{name} $*" >>"$FAKE_CALLS"\n{body}\n', newline="\n")
    (bin_dir / "id").write_text('#!/bin/sh\necho 0\n', newline="\n")
    # The fake monkey-backup.sh: snapshots from the JSON file, a restore copies the fake snapshot to TARGET/<server>.
    backup = tmp_path / "fake-backup.sh"
    backup.write_text('echo "backup $*" >>"$FAKE_CALLS"\n'
                      '[ "$1" = --restic-read ] || exit 9\n'
                      'case "$2" in snapshots) cat "$FAKE_SNAPSHOTS" ;; '
                      'restore) mkdir -p "$5$FAKE_SERVER" && cp -R "$FAKE_SNAP/." "$5$FAKE_SERVER/" ;; '
                      '*) exit 9 ;; esac\n', newline="\n")
    for fake in bin_dir.iterdir():
        fake.chmod(0o755)
    (tmp_path / "meminfo").write_text("MemTotal: 8000000 kB\nMemAvailable: 6000000 kB\n")
    (tmp_path / "deploy.env").write_text(f"LIVE_DIR={msys(live)}\nSTAFF_WEBHOOK_URL=https://hook/staff\n")
    paths = {"live": live, "scratch": scratch_root, "state": tmp_path / "state"}

    def run(**env):
        environ = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "FAKE_CALLS": calls.as_posix(),
                   "FAKE_STATE": tmp_path.as_posix(), "FAKE_SNAPSHOTS": (tmp_path / "snapshots.json").as_posix(),
                   "FAKE_SNAP": msys(snap), "FAKE_SERVER": msys(live / "server"),
                   "MONKEY_DEPLOY_ENV": (tmp_path / "deploy.env").as_posix(), "MONKEY_BACKUP_ENV": "/nonexistent",
                   "DRILL_BACKUP": msys(backup), "DRILL_TOOLS": msys(REPO.root / "tools"),
                   "DRILL_ROOT": msys(scratch_root), "DRILL_STATE": msys(tmp_path / "state"),
                   "DRILL_MEMINFO": msys(tmp_path / "meminfo"), "MONKEY_BACKUP_LOCK": msys(tmp_path / "lock"), **env}
        done = subprocess.run([DASH, SCRIPT.as_posix()], env=environ, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
        said = calls.read_text().splitlines() if calls.exists() else []
        calls.unlink(missing_ok=True)
        logged = [re.sub(r"^\S+ \S+ \[restore-drill\] ", "", line) for line in done.stdout.splitlines()]
        return done.returncode, logged, said, paths
    run.paths = paths
    return run


def msys_python():
    return msys(Path(sys.executable))


@needs_dash
def test_a_good_snapshot_passes_and_nothing_is_left_behind(drill):
    live_before = tree(drill.paths["live"])
    code, logged, calls, paths = drill()
    assert code == 0, logged
    assert "the world on disk: level.dat reads (game time 5000), 1 region files" in logged
    assert logged[-1].startswith("Monkey SMP restore drill PASSED: restored and booted in 1 min, world time 5100")
    assert "Snapshot: a1b2c3d4 from 2026-11-09T09:00Z" in logged[-1]   # not the newer, unflushed one
    restore = next(c for c in calls if c.startswith("backup --restic-read restore"))
    target = restore.split(" --target ")[1]
    assert restore.startswith(f"backup --restic-read restore {FULL} ") and target.startswith(
        msys(paths["scratch"]) + "/monkey-drill.")
    run = next(c for c in calls if c.startswith("docker run"))
    assert " --network none " in run and " -p " not in run and " --publish" not in run
    assert re.search(r" -v \S+/monkey-drill\.\w+:/monkey monkey-smp-monkey$", run)
    assert any(c.startswith("docker stop -t 120 monkey-drill-") for c in calls)
    assert any(c.startswith("docker rm -f monkey-drill-") for c in calls)
    assert list(paths["scratch"].iterdir()) == []   # the scratch folder is gone
    assert tree(paths["live"]) == live_before   # the live folder is as it was
    assert "PASSED" in (paths["state"] / "last-pass").read_text()
    assert any(c.startswith("curl ") and c.endswith(" https://hook/staff") for c in calls)


@needs_dash
@pytest.mark.parametrize(("env", "why"), [
    ({"FAKE_GAMETIME": "4000"}, "game time (4000) is behind its level.dat's (5000)"),
    ({"FAKE_GAMETIME": ""}, "answered, but not with its game time"),
    ({"FAKE_RC_list": "1", "FAKE_RUNNING": "false"}, "did not answer RCON within 900s"),
])
def test_a_server_that_does_not_come_back_right_fails_and_is_cleaned_up(drill, env, why):
    code, logged, calls, paths = drill(**env)
    assert code == 1 and why in logged[-1] and logged[-1].endswith("Check: journalctl -u monkey-restore-drill")
    assert any(c.startswith("docker rm -f monkey-drill-") for c in calls)
    assert list(paths["scratch"].iterdir()) == [] and not (paths["state"] / "last-pass").exists()


@needs_dash
@pytest.mark.parametrize(("env", "why"), [
    ({"FAKE_FREE_KB": "1000"}, "not enough disk"),
    ({"DRILL_MEMORY_GB": "9"}, "not enough free memory"),
    ({"FAKE_RC_image": "1"}, "there is no docker image monkey-smp-monkey"),
])
def test_no_room_stops_before_anything_is_restored(drill, env, why):
    code, logged, calls, paths = drill(**env)
    assert code == 1 and why in logged[-1]
    assert not any(c.startswith("backup ") or c.startswith("docker run") for c in calls)
    assert list(paths["scratch"].iterdir()) == []


@needs_dash
def test_a_scratch_root_inside_the_live_folder_is_refused_before_anything_is_made(drill):
    live = drill.paths["live"]
    before = tree(live)
    code, logged, calls, _ = drill(DRILL_ROOT=msys(live / "server"))
    assert code == 1 and "is inside the live folder" in logged[-1]
    assert tree(live) == before and not any(c.startswith("backup ") for c in calls)


@needs_dash
def test_drill_keep_keeps_the_scratch_folder_to_look_at(drill):
    code, _, _, paths = drill(DRILL_KEEP="1")
    kept = list(paths["scratch"].iterdir())
    assert code == 0 and len(kept) == 1 and (kept[0] / "server" / "world" / "level.dat").exists()
    assert not (kept[0] / "docker" / ".env").exists()   # the live secrets file is never copied
