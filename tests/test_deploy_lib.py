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
    for fake in bin_dir.iterdir():  # Linux's PATH lookup skips files without the execute bit (Git Bash doesn't)
        fake.chmod(0o755)

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


def test_compose_runs_from_the_root_whatever_the_callers_folder(sh, tmp_path):
    """docker compose stats its working directory: run as realms from /root it failed every call (2.9.0's deploy)."""
    assert sh(f'cd "{tmp_path.as_posix()}"; docker() {{ pwd; }}; compose ps')[1] == ["/"]


@needs_dash
@pytest.mark.parametrize(("script", "sent", "retry"), [
    ("realms-week.sh", "send --docker", "the next hour tries again"),
    ("realms-drops.sh", "send /srv/live/server/world --docker", "the timer tries again in 10 minutes"),
    ("realms-omens.sh", "send /srv/live/server/world --docker", "the timer tries again in 10 minutes"),
    ("realms-day.sh", "send --docker", "realms-day.service tries again in 10 minutes"),
])
def test_the_timers_send_under_the_deploy_lock_and_log_each_line(sh, tmp_path, script, sent, retry):
    code, logged, calls = job(sh, tmp_path, script, FAKE_OUT_python3=r"function realms:x: ok\n")
    assert code == 0 and logged == ["function realms:x: ok"]
    send = calls.index("flock -w 1800 9") + 1
    assert calls[send].startswith("python3 -B -u ") and calls[send].endswith(f"{sent} /srv/live/docker")
    # Only drops and omens (JOB_NONE: often nothing to send) ask for the commands first; the others start one
    # python3.
    assert len([c for c in calls if c.startswith("python3")]) == (2 if script in OFTEN_NONE else 1)
    code, logged, calls = job(sh, tmp_path, script, FAKE_OUT_python3="x", FAKE_RC_flock="1")
    assert code == 1 and logged[-1] == f"ERROR: the deploy lock was taken for 30 minutes ({retry})"
    assert calls[-1] == "flock -w 1800 9"
    code, logged, _ = job(sh, tmp_path, script, FAKE_OUT_python3="x", FAKE_RC_send="1")
    assert code == 1 and logged[-1] == f"ERROR: not every command went through ({retry})"
    code, logged, _ = job(sh, tmp_path, script, FAKE_OUT_python3="x", FAKE_RC_send="3")   # rcon.NOT_RUNNING
    assert code == 1 and logged[-1] == f"ERROR: the server isn't running ({retry})"


@needs_dash
def test_a_job_that_gives_up_alerts_staff_and_exits_4_so_systemd_stops_retrying(sh, tmp_path):
    env = tmp_path / "env"
    env.write_text("DISCORD_WEBHOOK_URL=https://hook/public\nSTAFF_WEBHOOK_URL=https://hook/staff\n")
    code, logged, calls = job(sh, tmp_path, "realms-day.sh", FAKE_OUT_python3=r"gave up: the day for 20261028\n",
                              FAKE_RC_send="4", REALMS_DEPLOY_ENV=env.as_posix())
    assert code == 4 and logged == ["gave up: the day for 20261028", "gave up; the timer's next run starts afresh"]
    assert calls[-2:] == ["curl -fsS -m 15 -H Content-Type: application/json -d @- https://hook/staff",
                          '{"content":"Monkey SMP: realms-day gave up on the wardrobe\'s day job after retrying. '
                          'Check: journalctl -u realms-day"}']
    env.write_text("DISCORD_WEBHOOK_URL=https://hook/public\n")   # no staff channel: the public webhook
    assert job(sh, tmp_path, "realms-day.sh", FAKE_RC_send="4", REALMS_DEPLOY_ENV=env.as_posix())[2][-2].endswith(
        " https://hook/public")
    code, logged, calls = job(sh, tmp_path, "realms-day.sh", FAKE_RC_send="4")
    assert code == 4 and "no webhook in the settings; not posting" in logged
    assert not any(c.startswith("curl") for c in calls)


OFTEN_NONE = ("realms-drops.sh", "realms-omens.sh")


@pytest.mark.parametrize("script", OFTEN_NONE)
def test_drops_and_omens_with_nothing_to_send_take_no_lock(sh, tmp_path, script):
    code, logged, calls = job(sh, tmp_path, script)
    assert code == 0 and logged == [] and len(calls) == 1 and " commands " in calls[0]


def job(sh, tmp_path, script, *args, **env):
    """Runs a timed job's script against a made-up checkout; returns (exit code, its logged lines, calls)."""
    (tmp_path / "repo" / "tools").mkdir(parents=True, exist_ok=True)
    for name in ("challenges.py", "drops.py", "omens.py", "wardrobe.py"):
        (tmp_path / "repo" / "tools" / name).write_text("")
    code, out, calls = sh(f'sh "{(DEPLOY / script).as_posix()}" "$@"', *args, REPO_DIR=(tmp_path / "repo").as_posix(),
                          **{"REALMS_DEPLOY_ENV": "/nonexistent", **env})
    tag = f"[{script[:-3]}] "
    return code, [line[len(tag):] for line in out if line.startswith(tag)], calls


@needs_dash
@pytest.mark.parametrize(("script", "first"), [("realms-week.sh", []), ("realms-day.sh", []),
                                               ("realms-drops.sh", ["function realms:x"]),   # drops' spots
                                               ("realms-omens.sh", [])])   # never the week's plan
def test_check_shows_the_commands_the_timer_and_the_server_and_takes_no_lock(sh, tmp_path, script, first):
    code, logged, calls = job(sh, tmp_path, script, "--check", FAKE_OUT_python3=r"function realms:x\n")
    assert code == 0 and logged[:len(first) + 2] == [*first, "commands for now:", "  function realms:x"]
    assert logged[-3].startswith(f"timer: {script[:-3]}.timer ") and logged[-2:] == [
        "server: running", "check finished: nothing was changed"]
    assert not any(c.startswith("flock") for c in calls)
    assert calls[-1].endswith(" running --docker /srv/live/docker")


@needs_dash
def test_check_says_why_there_may_be_no_commands_and_what_a_stopped_server_means(sh, tmp_path):
    code, logged, _ = job(sh, tmp_path, "realms-drops.sh", "--check", FAKE_RC_python3="1")
    assert code == 1 and logged == ["ERROR: tools/drops.py commands failed"]
    _, logged, _ = job(sh, tmp_path, "realms-drops.sh", "--check")
    assert logged[:2] == ["commands for now:", "  none (outside drop hours, or no spot)"]
    _, logged, _ = job(sh, tmp_path, "realms-day.sh", "--check", FAKE_OUT_python3=r"function realms:x\n")
    assert logged[-2] == "server: running"


@needs_dash
@pytest.mark.parametrize("script", ["realms-week.sh", "realms-drops.sh", "realms-omens.sh", "realms-day.sh"])
def test_a_timed_job_refuses_an_unknown_option_and_installs_only_as_root(sh, tmp_path, script):
    code, out, calls = sh(f'sh "{(DEPLOY / script).as_posix()}" --now')
    assert code == 2 and out == [f"usage: sh {(DEPLOY / script).as_posix()} [--check | --install]"] and calls == []
    code, logged, _ = job(sh, tmp_path, script, "--install")
    assert code == 1 and logged == ["ERROR: run as root: it installs systemd units"]
    code, logged, _ = job(sh, tmp_path, script, "--install", FAKE_ID="0")
    assert code == 1 and logged[-1].endswith(f"/repo/deploy/{script[:-3]}.service is missing: is the release with "
                                             f"{JOB_FOR[script]} deployed?")


JOB_FOR = {"realms-week.sh": "the weekly challenges", "realms-drops.sh": "supply drops",
           "realms-omens.sh": "omens", "realms-day.sh": "the wardrobe's day job"}


def test_the_day_runs_its_job_and_systemd_retries_it_until_it_gives_up():
    unit = (DEPLOY / "realms-day.service").read_text()
    assert "ExecStart=/bin/sh /srv/realms/repo/deploy/realms-day.sh\n" in unit
    assert "Restart=on-failure\nRestartSec=10min\nRestartPreventExitStatus=4\n" in unit
    assert "StateDirectory=realms-day\n" in unit and "docker compose" not in unit   # wardrobe.py's --pending


LIST = r"There are 2 of a max of 20 players online: a, b\n"


def test_discord_escapes_quotes_and_backslashes_into_valid_json(sh):
    message = 'it said "no" at C:\\x\\'
    code, out, calls = sh('discord "$1"', message, DISCORD_WEBHOOK_URL="https://hook/a")
    assert code == 0 and out == []
    assert calls == ["curl -fsS -m 15 -H Content-Type: application/json -d @- https://hook/a",
                     r'{"content":"it said \"no\" at C:\\x\\"}']
    assert json.loads(calls[1]) == {"content": message}


def test_discord_turns_newlines_tabs_and_control_characters_into_valid_json(sh):
    # (The CR is mid-line: Git for Windows' sed, which these tests may run on, drops one right before a newline.)
    message = 'line one\n\tline "two"\rthree\nbell\x07 and\x1b escape\\'
    calls = sh('discord "$1" https://hook/a', message)[2]
    assert calls[1] == r'{"content":"line one\n\tline \"two\"\rthree\nbell and escape\\"}'
    assert json.loads(calls[1]) == {"content": 'line one\n\tline "two"\rthree\nbell and escape\\'}


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
    assert sh("warn_players x", FAKE_OUT_docker=LIST, WARN_MINUTES="0")[1:] == ([], [f"{RCON} list"])


def test_warn_players_keeps_the_count_so_the_caller_needs_no_second_list(sh):
    assert sh('warn_players x; log "$PLAYERS_ONLINE online"', FAKE_OUT_docker=LIST, WARN_MINUTES="0")[1] == [
        "[t] 2 online"]
    assert sh('warn_players x; log "[$PLAYERS_ONLINE] online"', FAKE_RC_docker="1")[1] == ["[t] [] online"]


@pytest.mark.parametrize("value", ["5m", "-1", "05", " 5", "five"])
def test_a_setting_that_is_not_a_whole_number_stops_before_anything_happens(sh, value):
    code, out, calls = sh("warn_players x; log warned", FAKE_OUT_docker=LIST, WARN_MINUTES=value)
    assert code == 1 and out == [f"[t] ERROR: WARN_MINUTES must be a whole number of minutes, not '{value}'"]
    assert calls == []
    code, out, calls = sh("wait_for_live; log up", BOOT_TIMEOUT=value)
    assert code == 1 and out == [f"[t] ERROR: BOOT_TIMEOUT must be a whole number of seconds, not '{value}'"]
    assert calls == []


@needs_dash
@pytest.mark.parametrize("script", ["realms-deploy.sh", "realms-loadtest.sh", "shops-claims.sh"])
def test_the_restarting_scripts_check_their_minutes_before_they_do_anything(sh, tmp_path, script):
    code, out, calls = sh(f'sh "{(DEPLOY / script).as_posix()}"', WARN_MINUTES="5m", FAKE_ID="0",
                          REALMS_DEPLOY_ENV="/nonexistent", SHOPS_LOG=(tmp_path / "shops.log").as_posix())
    assert code == 1 and out[-1].endswith("ERROR: WARN_MINUTES must be a whole number of minutes, not '5m'")
    assert not [c for c in calls if c.split()[0] in ("docker", "flock", "curl", "sleep")]


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
