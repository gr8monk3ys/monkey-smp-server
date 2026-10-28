import json
import os
import re
import shutil
import subprocess

import pytest

from repo import REPO

DEPLOY = REPO.root / "deploy"
LIB = DEPLOY / "lib.sh"
SOURCE = '. "$(dirname -- "$0")/lib.sh"'
SCRIPTS = sorted(p for p in DEPLOY.glob("*.sh") if p != LIB)
DASH = shutil.which("dash")
needs_dash = pytest.mark.skipif(not DASH, reason="needs dash")
COMPOSE = "docker compose --project-directory /srv/live/docker -f /srv/live/docker/compose.yaml"
RCON = f"{COMPOSE} exec -T realms realms rcon"
# The 2.5.0 upgrade is a one-shot kept as it ran: its own wait_for_live and warn_players predate lib.sh's.
OWN_COPIES = {"upgrade-2.5.0.sh": {"wait_for_live", "warn_players"}}


def functions(text):
    return set(re.findall(r"^(\w+)\(\) *\{", text, re.M))


def test_lib_is_posix_and_only_defines():
    text = LIB.read_text()
    assert text.isascii() and "\r" not in text and not text.startswith("#!")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    # A sourced file leaves the shell's options and exiting to the script (die is the one exit).
    assert not re.search(r"^\s*set -", code, re.M) and re.findall(r"\bexit \d", code) == ["exit 1"]
    if DASH:
        subprocess.run([DASH, "-n", str(LIB)], check=True)


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_every_deploy_script_loads_lib_once_and_keeps_no_copy_of_it(script):
    text = script.read_text()
    assert text.count(SOURCE) == 1
    head = text[:text.index(SOURCE)]
    assert "set -eu\n" in head and re.search(r"^LOG_NAME=[\w.-]+\n\Z", head, re.M)
    assert functions(text) & functions(LIB.read_text()) == OWN_COPIES.get(script.name, set())
    # The deploy lock is fd 9, opened only by deploy_lock (realms-backup.sh's own lock is fd 8).
    assert "$COMPOSE" not in text and not re.search(r'flock -[nw]( \d+)? 9|exec 9[<>]+ *"', text)
    if DASH:
        subprocess.run([DASH, "-n", str(script)], check=True)


def test_the_deploy_loads_lib_before_it_touches_the_checkout():
    """The deploy checks out the new release at the end; whatever it sources after that would be the new copy."""
    lines = (DEPLOY / "realms-deploy.sh").read_text().splitlines()
    code = [(i, line) for i, line in enumerate(lines) if not line.lstrip().startswith("#")]
    first_git = next(i for i, line in code if re.search(r"\bgit\b", line))
    assert lines.index(SOURCE) < first_git


@pytest.fixture
def sh(tmp_path):
    """Runs a dash snippet with lib.sh loaded and fake flock, docker, python3, curl and sleep first on PATH; each
    fake records its arguments in `calls` (curl its JSON from stdin too) and exits with FAKE_RC_<name> (default 0)."""
    if not DASH:
        pytest.skip("needs dash")
    bin_dir, calls = tmp_path / "bin", tmp_path / "calls"
    bin_dir.mkdir()
    for name in ("flock", "docker", "python3", "sleep"):
        (bin_dir / name).write_text(
            f'#!/bin/sh\necho "{name} $*" >>"$FAKE_CALLS"\n'
            f'[ -z "${{FAKE_OUT_{name}:-}}" ] || printf "$FAKE_OUT_{name}"\n'
            f'case " $* " in *" send "*) exit "${{FAKE_RC_send:-0}}" ;; esac\n'
            f'exit "${{FAKE_RC_{name}:-0}}"\n', newline="\n")
    (bin_dir / "curl").write_text('#!/bin/sh\necho "curl $*" >>"$FAKE_CALLS"\n'
                                  'case " $* " in *" -d @- "*) { cat; echo; } >>"$FAKE_CALLS" ;; esac\n'
                                  'exit "${FAKE_RC_curl:-0}"\n', newline="\n")
    (bin_dir / "id").write_text('#!/bin/sh\necho "${FAKE_ID:-1000}"\n', newline="\n")  # root only when asked
    (bin_dir / "runuser").write_text('#!/bin/sh\necho "runuser $*" >>"$FAKE_CALLS"\n'
                                     'while [ "$1" != -- ]; do shift; done\nshift\nexec "$@"\n', newline="\n")

    def run(snippet, *args, **env):
        environ = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "FAKE_CALLS": calls.as_posix(),
                   "LOCK_FILE": (tmp_path / "lock").as_posix(), "LIVE_DIR": "/srv/live", **env}
        done = subprocess.run([DASH, "-c", f'set -eu; LOG_NAME=t; . "$0"; {snippet}', LIB.as_posix(), *args],
                              env=environ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        said = calls.read_text().splitlines() if calls.exists() else []
        calls.unlink(missing_ok=True)
        return done.returncode, [re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", line) for line in
                                 done.stdout.splitlines()], said
    return run


def test_setting_reads_the_last_value_as_written(sh, tmp_path):
    env = tmp_path / "env"
    env.write_bytes(b'LIVE_DIR=/old\n  LIVE_DIR = "/srv/a b"  \nPASS=\'$x "y"\'\nEMPTY=\n# KEY=no\n')
    assert sh('setting_in "$1" LIVE_DIR; echo; setting_in "$1" PASS; echo; setting_in "$1" EMPTY d; echo;'
              ' setting_in "$1" KEY d; echo; ENV_FILE=$1 setting LIVE_DIR', env.as_posix())[1] == [
        "/srv/a b", '$x "y"', "d", "d", "/srv/a b"]


def test_log_tags_each_line_and_copies_it_to_log_to(sh, tmp_path):
    copy = tmp_path / "copy.log"
    code, out, _ = sh('log one; logged echo quiet; die "it broke" 2>&1', LOG_TO=copy.as_posix())
    assert code == 1 and out == ["[t] one", "[t] ERROR: it broke"]
    lines = copy.read_text().splitlines()
    assert [re.sub(r"^\S+ \S+ ", "", line) for line in lines] == ["[t] one", "quiet", "[t] ERROR: it broke"]


def test_log_each_logs_every_line_and_keeps_the_exit_code(sh):
    assert sh("log_each python3 send || log rc=$?", FAKE_OUT_python3=r"a\n\nb\n", FAKE_RC_send="3")[1] == [
        "[t] a", "[t] b", "[t] rc=3"]
    assert sh("log_each python3 send && log ok")[1] == ["[t] ok"]
    assert sh("log_each python3 send && log ok", FAKE_OUT_python3="no newline")[1] == ["[t] no newline", "[t] ok"]


def test_a_lock_that_cannot_be_opened_is_an_error_not_busy(sh, tmp_path):
    lock = (tmp_path / "missing" / "lock").as_posix()
    for root in ("0", "1000"):
        code, out, calls = sh("deploy_lock 60 || log busy", LOCK_FILE=lock, FAKE_ID=root)
        assert code == 1 and out[-1].startswith("[t] ERROR: could not ") and out[-1].endswith(lock)
        assert "busy" not in "".join(out) and not any(c.startswith("flock") for c in calls)


def test_root_makes_a_missing_lock_as_the_service_user_or_itself_before_there_is_one(sh, tmp_path):
    lock = tmp_path / "lock"
    code, _, calls = sh("deploy_lock 0", FAKE_ID="0", SERVICE_USER="realms")
    assert code == 0 and lock.exists() and calls == [f"runuser -u realms -- touch {lock.as_posix()}", "flock -n 9"]
    lock.unlink()
    code, _, calls = sh("deploy_lock 0", FAKE_ID="0", LIVE_DIR=(tmp_path / "not-yet").as_posix())
    assert code == 0 and lock.exists() and calls == ["flock -n 9"]
    lock.unlink()
    lock.mkdir()   # something that isn't a plain file at the lock's name: root never opens it
    code, out, calls = sh("deploy_lock 0", FAKE_ID="0")
    assert code == 1 and out[-1].endswith(f"ERROR: the deploy lock {lock.as_posix()} is not a plain file")
    assert calls == []


@pytest.mark.parametrize(("seconds", "flag"), [("0", "-n 9"), ("1800", "-w 1800 9")])
def test_deploy_lock_waits_on_fd_9(sh, seconds, flag):
    code, out, calls = sh(f"deploy_lock {seconds} && log locked")
    assert code == 0 and out == ["[t] locked"] and calls == [f"flock {flag}"]
    assert sh("deploy_lock 60 || log 'not free'", FAKE_RC_flock="1")[1] == ["[t] not free"]


def test_rcon_and_running_go_through_the_release_compose(sh):
    code, out, calls = sh("running && log up; rcon list", FAKE_OUT_docker=r"3f2a\n")
    assert code == 0 and out == ["[t] up", "3f2a"]
    assert calls == [f"{COMPOSE} ps -q --status running realms", f"{RCON} list"]
    assert sh("running || log down")[1] == ["[t] down"]


@needs_dash
@pytest.mark.parametrize(("script", "sent", "retry"), [
    ("realms-week.sh", "send --docker", "the next hour tries again"),
    ("realms-drops.sh", "send /srv/live/server/world --docker", "the timer tries again in 10 minutes"),
])
def test_the_timers_send_under_the_deploy_lock_and_log_each_line(sh, tmp_path, script, sent, retry):
    tool = tmp_path / "repo" / "tools"
    tool.mkdir(parents=True)
    for name in ("challenges.py", "drops.py"):
        (tool / name).write_text("")
    run = f'sh "{(DEPLOY / script).as_posix()}"'
    env = {"REPO_DIR": (tmp_path / "repo").as_posix(), "REALMS_DEPLOY_ENV": "/nonexistent"}
    code, out, calls = sh(run, FAKE_OUT_python3=r"function realms:x: ok\n", **env)
    assert code == 0 and [line.split("] ", 1)[1] for line in out] == ["function realms:x: ok"]
    send = calls.index("flock -w 1800 9") + 1
    assert calls[send].startswith("python3 -B -u ") and calls[send].endswith(f"{sent} /srv/live/docker")
    code, out, calls = sh(run, FAKE_OUT_python3="x", FAKE_RC_flock="1", **env)
    assert code == 1 and out[-1].endswith(f"ERROR: the deploy lock was taken for 30 minutes ({retry})")
    assert calls[-1] == "flock -w 1800 9"
    code, out, _ = sh(run, FAKE_OUT_python3="x", FAKE_RC_send="1", **env)
    assert code == 1 and out[-1].endswith(f"ERROR: not every command went through ({retry})")


def test_drops_outside_drop_hours_takes_no_lock(sh, tmp_path):
    (tmp_path / "repo" / "tools").mkdir(parents=True)
    (tmp_path / "repo" / "tools" / "drops.py").write_text("")
    code, out, calls = sh(f'sh "{(DEPLOY / "realms-drops.sh").as_posix()}"', REPO_DIR=(tmp_path / "repo").as_posix(),
                          REALMS_DEPLOY_ENV="/nonexistent")
    assert code == 0 and out == [] and len(calls) == 1 and " commands " in calls[0]


LIST = r"There are 2 of a max of 20 players online: a, b\n"


def test_discord_escapes_quotes_and_backslashes_into_valid_json(sh):
    message = 'it said "no" at C:\\x\\'
    code, out, calls = sh('discord "$1"', message, DISCORD_WEBHOOK_URL="https://hook/a")
    assert code == 0 and out == []
    assert calls == ["curl -fsS -m 15 -H Content-Type: application/json -d @- https://hook/a",
                     r'{"content":"it said \"no\" at C:\\x\\"}']
    assert json.loads(calls[1]) == {"content": message}


def test_discord_posts_to_the_url_given_or_none_and_logs_a_failure(sh):
    assert sh("discord hi https://hook/b")[2][0].endswith(" https://hook/b")
    assert sh("discord hi ''", DISCORD_WEBHOOK_URL="https://hook/a")[2] == []   # empty: no post, no fallback
    assert sh("discord hi")[2] == []
    code, out, _ = sh("discord hi https://hook/b", FAKE_RC_curl="22")
    assert code == 0 and out == ["[t] could not post to Discord"]


def test_discord_attaches_a_file_to_the_same_json(sh):
    calls = sh("""discord 'a "b"' https://hook/c /tmp/r.md""")[2]
    assert calls == [r'curl -fsS -m 30 --form-string payload_json={"content":"a \"b\""} '
                     "-F files[0]=@/tmp/r.md;type=text/markdown https://hook/c"]


def test_players_online_reads_list(sh):
    assert sh("players_online", FAKE_OUT_docker=LIST)[1] == ["2"]
    assert sh("players_online; echo .", FAKE_RC_docker="1")[1] == ["."]


def test_warn_players_says_it_twice_then_waits_a_minute(sh):
    code, out, calls = sh("warn_players 'Server update to v2' 'Server update'", FAKE_OUT_docker=LIST)
    assert code == 0 and out == ["[t] 2 player(s) online; warning them 5 minutes ahead"]
    assert calls == [f"{RCON} list", f"{RCON} say Server update to v2 in 5 minutes (about 3 minutes offline).",
                     "sleep 240", f"{RCON} say Server update in 1 minute. Find a safe spot.", "sleep 60"]
    calls = sh("warn_players 'Performance test' '' '(about 25 minutes offline)'", FAKE_OUT_docker=LIST,
               WARN_MINUTES="1")[2]
    assert calls == [f"{RCON} list", f"{RCON} say Performance test in 1 minutes (about 25 minutes offline).",
                     f"{RCON} say Performance test in 1 minute. Find a safe spot.", "sleep 60"]


def test_warn_players_warns_nobody_when_no_one_is_on_or_warn_minutes_is_0(sh):
    nobody = r"There are 0 of a max of 20 players online:\n"
    assert sh("warn_players x", FAKE_OUT_docker=nobody)[1:] == ([], [f"{RCON} list"])
    assert sh("warn_players x", FAKE_RC_docker="1")[1] == []
    assert sh("warn_players x", FAKE_OUT_docker=LIST, WARN_MINUTES="0")[1:] == ([], [])


def test_wait_for_live_asks_every_15_seconds_until_boot_timeout(sh):
    code, _, calls = sh("wait_for_live", FAKE_OUT_docker=r"up\n", FAKE_RC_docker="1", BOOT_TIMEOUT="30")
    assert code == 1 and calls == ["sleep 15", f"{RCON} list"] * 2
    code, _, calls = sh("wait_for_live && log up", BOOT_TIMEOUT="30")
    assert code == 0 and calls == ["sleep 15", f"{RCON} list"]


def test_wait_for_live_while_running_gives_up_when_the_container_stops(sh):
    code, out, calls = sh("wait_for_live --while-running || log 'gave up'")
    assert out == ["[t] gave up"] and calls == ["sleep 15", f"{COMPOSE} ps -q --status running realms"]
    code, out, calls = sh("wait_for_live --while-running && log up", FAKE_OUT_docker=r"3f2a\n")
    assert out == ["[t] up"] and calls == ["sleep 15", f"{COMPOSE} ps -q --status running realms", f"{RCON} list"]
