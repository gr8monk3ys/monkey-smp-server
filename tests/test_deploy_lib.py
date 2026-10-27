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
    assert not functions(text) & functions(LIB.read_text())
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
    """Runs a dash snippet with lib.sh loaded and fake flock, docker and python3 first on PATH; each fake records
    its arguments in `calls` and exits with FAKE_RC_<name> (default 0)."""
    if not DASH:
        pytest.skip("needs dash")
    bin_dir, calls = tmp_path / "bin", tmp_path / "calls"
    bin_dir.mkdir()
    for name in ("flock", "docker", "python3"):
        (bin_dir / name).write_text(
            f'#!/bin/sh\necho "{name} $*" >>"$FAKE_CALLS"\n'
            f'[ -z "${{FAKE_OUT_{name}:-}}" ] || printf "$FAKE_OUT_{name}"\n'
            f'case " $* " in *" send "*) exit "${{FAKE_RC_send:-0}}" ;; esac\n'
            f'exit "${{FAKE_RC_{name}:-0}}"\n', newline="\n")
    (bin_dir / "id").write_text("#!/bin/sh\necho 1000\n", newline="\n")  # not root, whoever runs the tests

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


def test_a_lock_that_cannot_be_opened_is_a_failure_the_caller_logs(sh, tmp_path):
    assert sh("deploy_lock 60 || log 'no lock'", LOCK_FILE=(tmp_path / "missing" / "lock").as_posix())[1][-1] == (
        "[t] no lock")


@pytest.mark.parametrize(("seconds", "flag"), [("0", "-n 9"), ("1800", "-w 1800 9")])
def test_deploy_lock_waits_on_fd_9(sh, seconds, flag):
    code, out, calls = sh(f"deploy_lock {seconds} && log locked")
    assert code == 0 and out == ["[t] locked"] and calls == [f"flock {flag}"]
    assert sh("deploy_lock 60 || log 'not free'", FAKE_RC_flock="1")[1] == ["[t] not free"]


def test_rcon_and_running_go_through_the_release_compose(sh):
    compose = "docker compose --project-directory /srv/live/docker -f /srv/live/docker/compose.yaml"
    code, out, calls = sh("running && log up; rcon list", FAKE_OUT_docker=r"3f2a\n")
    assert code == 0 and out == ["[t] up", "3f2a"]
    assert calls == [f"{compose} ps -q --status running realms", f"{compose} exec -T realms realms rcon list"]
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
