"""deploy/monkey-backup.sh against fake docker, restic and curl: what it backs up when the server answers, is stopped
or doesn't answer, the dead-man's ping, and the read-only restic mode the restore drill uses."""
import os
import re
import shutil
import subprocess

import pytest

from repo import REPO

SCRIPT = REPO.root / "deploy" / "monkey-backup.sh"
DASH = shutil.which("dash")
pytestmark = pytest.mark.skipif(not DASH, reason="needs dash")
SECRET = "pingsecret-1234"


@pytest.fixture
def backup(tmp_path):
    """Runs monkey-backup.sh as a fake root; returns (exit code, output lines, calls). FAKE_RC_rcon is RCON's exit code,
    FAKE_PS what `docker compose ps -q --status running` prints (empty: stopped)."""
    bin_dir, calls = tmp_path / "bin", tmp_path / "calls"
    bin_dir.mkdir()
    fakes = {
        "docker": 'case " $* " in *" rcon "*) exit "${FAKE_RC_rcon:-0}" ;; *" ps -a "*) printf "${FAKE_ENDED-}" ;;\n'
                  '  *" ps "*) printf "${FAKE_PS-}"; '
                  'exit "${FAKE_RC_ps:-0}" ;; esac',
        "restic": 'case " $* " in *" --no-lock "*) echo "key=${AWS_ACCESS_KEY_ID-}" ;; esac\n'
                  'exit "${FAKE_RC_restic:-0}"',
        "curl": 'exit "${FAKE_RC_curl:-0}"',
        "flock": "exit 0", "sleep": "exit 0",
        "timeout": 'shift\nexec "$@"',
    }
    for name, body in fakes.items():
        (bin_dir / name).write_text(f'#!/bin/sh\necho "{name} $*" >>"$FAKE_CALLS"\n{body}\n', newline="\n")
    (bin_dir / "id").write_text('#!/bin/sh\necho 0\n', newline="\n")
    for fake in bin_dir.iterdir():
        fake.chmod(0o755)
    live = tmp_path / "live"
    (live / "server" / "world").mkdir(parents=True)
    (live / "server" / "world" / "level.dat").write_bytes(b"x")
    (tmp_path / "deploy.env").write_text(f"LIVE_DIR={live.as_posix()}\nLOCK_FILE={(tmp_path / 'nolock').as_posix()}\n"
                                         "DISCORD_WEBHOOK_URL=https://hook/public\nSTAFF_WEBHOOK_URL=https://hook/staff\n")
    settings = tmp_path / "backup.env"
    settings.write_text("RESTIC_REPOSITORY=s3:r2/b\nRESTIC_PASSWORD=pw\nAWS_ACCESS_KEY_ID=writer\n"
                        "AWS_SECRET_ACCESS_KEY=ws\n")

    def run(*args, extra="", **env):
        if extra:
            settings.write_text(settings.read_text() + extra)
        environ = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "FAKE_CALLS": calls.as_posix(),
                   "MONKEY_BACKUP_ENV": settings.as_posix(), "MONKEY_DEPLOY_ENV": (tmp_path / "deploy.env").as_posix(),
                   "MONKEY_BACKUP_STATE": (tmp_path / "state").as_posix(),
                   "MONKEY_BACKUP_LOCK": (tmp_path / "backup.lock").as_posix(), "RESTIC_CACHE_DIR": "/c", **env}
        done = subprocess.run([DASH, SCRIPT.as_posix(), *args], env=environ, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
        said = calls.read_text().splitlines() if calls.exists() else []
        calls.unlink(missing_ok=True)
        return done.returncode, [re.sub(r"^\S+ \S+ \[backup\] ", "", line) for line in done.stdout.splitlines()], said
    return run


def sent(calls):
    return next(c for c in calls if c.startswith("restic backup"))


def test_a_server_that_answers_is_flushed_and_backed_up_whole(backup):
    code, out, calls = backup()
    assert code == 0 and out[-1] == "done: the world is in R2"
    rcon = [c.split(" rcon ")[1] for c in calls if " rcon " in c]
    assert rcon[:3] == ["list", "save-off", "save-all flush"] and rcon[-1] == "save-on"
    assert " --tag world --exclude " in sent(calls)   # one tag: a whole copy
    forget = next(c for c in calls if c.startswith("restic forget"))
    assert "--tag world --group-by host,paths,tags --keep-hourly 48" in forget
    assert not any(c.startswith("curl") for c in calls)   # no PING_URL: no ping, no error


def test_a_stopped_server_is_backed_up_as_it_is_after_the_retries(backup):
    code, out, calls = backup(FAKE_RC_rcon="1", FAKE_PS="")
    assert code == 0 and out[-1] == "done: the world is in R2 (tag: stopped)"
    assert [c for c in calls if " rcon " in c] == [c for c in calls if c.endswith(" rcon list")]   # no save-off
    assert len([c for c in calls if c.endswith(" rcon list")]) == 4 and calls.count("sleep 30") == 3
    assert " --tag world --tag stopped --exclude " in sent(calls)


def test_a_running_server_that_does_not_answer_is_backed_up_unflushed_and_staff_hear_once(backup):
    for run in range(1, 5):
        code, out, calls = backup(FAKE_RC_rcon="1", FAKE_PS="abc123\n", RCON_TRIES="2", RCON_WAIT="5")
        assert code == 0 and out[-1] == "done: the world is in R2 (tag: unflushed)"
        assert any(line.startswith("WARNING: the server has not answered RCON for 5 seconds") for line in out)
        assert " --tag world --tag unflushed --exclude " in sent(calls)
        posts = [c for c in calls if c.startswith("curl") and "hook/staff" in c]
        assert len(posts) == (1 if run == 3 else 0)
    # It answers again: whole copies, and the count starts over.
    code, out, calls = backup()
    assert code == 0 and " --tag world --exclude " in sent(calls)


@pytest.mark.parametrize("ended", ["exited 0", "exited 143", ""])
def test_a_container_that_stopped_cleanly_is_stopped(backup, ended):
    _, _, calls = backup(FAKE_RC_rcon="1", FAKE_PS="", FAKE_ENDED=ended, RCON_TRIES="1")
    assert " --tag stopped " in sent(calls)


@pytest.mark.parametrize("ended", ["exited 137", "exited 1", "restarting 137", "dead 0"])
def test_a_container_that_crashed_or_restarts_is_unflushed_not_stopped(backup, ended):
    _, _, calls = backup(FAKE_RC_rcon="1", FAKE_PS="", FAKE_ENDED=ended, RCON_TRIES="1")
    assert " --tag unflushed " in sent(calls)


def test_docker_that_cannot_say_is_unflushed_not_stopped(backup):
    _, out, calls = backup(FAKE_RC_rcon="1", FAKE_RC_ps="1", RCON_TRIES="1")
    assert " --tag unflushed " in sent(calls) and not any(c.startswith("sleep 30") for c in calls)


def test_the_ping_follows_a_good_backup_only_and_never_shows_the_url(backup):
    code, out, calls = backup(extra=f"PING_URL=https://hc-ping.com/{SECRET}\n")
    ping = f"curl -fsS -m 10 --retry 3 -o /dev/null https://hc-ping.com/{SECRET}"
    assert code == 0 and calls.index(ping) > calls.index("restic check --read-data-subset=5%")   # after the check
    assert "pinged the dead-man switch (PING_URL)" in out and not any(SECRET in line for line in out)
    code, out, calls = backup(FAKE_RC_curl="7")
    assert code == 0 and out[-1].startswith("WARNING: could not reach PING_URL") and not any(SECRET in o for o in out)
    code, out, calls = backup(FAKE_RC_restic="1")   # restic failed: no ping
    assert code == 1 and not any(c.startswith("curl -fsS -m 10 --retry") for c in calls)


def test_a_ping_url_that_is_not_https_is_not_requested(backup):
    code, out, calls = backup(extra="PING_URL=http://plain/x\n")
    assert code == 0 and "WARNING: PING_URL is not an https:// URL; not pinging" in out
    assert not any(c.startswith("curl -fsS -m 10 --retry") for c in calls)


def test_restic_read_never_locks_and_uses_the_read_only_key_when_there_is_one(backup):
    code, out, calls = backup("--restic-read", "restore", "latest:/srv/x", "--target", "/var/tmp/d")
    assert code == 0 and calls == ["restic --no-lock restore latest:/srv/x --target /var/tmp/d"]
    assert out[-1] == "key=writer"   # (a WARNING may come first: the test's settings file is not root-only)
    code, out, _ = backup("--restic-read", "snapshots",
                          extra="READ_AWS_ACCESS_KEY_ID=reader\nREAD_AWS_SECRET_ACCESS_KEY=rs\n")
    assert code == 0 and out[-1] == "key=reader"


@pytest.mark.parametrize("command", ["forget", "backup", "prune", "init", ""])
def test_restic_read_refuses_anything_that_writes(backup, command):
    code, out, calls = backup("--restic-read", *([command] if command else []))
    assert code == 1 and "--restic-read runs only snapshots, ls or restore" in out[-1] and calls == []
