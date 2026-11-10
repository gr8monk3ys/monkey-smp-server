"""deploy/monkey-alert.sh (OnFailure= posts) and deploy/monkey-logs.sh (log pruning), under dash with fakes."""
import datetime as dt
import os
import re
import shutil
import subprocess
import time

import pytest

from repo import REPO

DEPLOY = REPO.root / "deploy"
DASH = shutil.which("dash")
pytestmark = pytest.mark.skipif(not DASH, reason="needs dash")
SELF_REPORTING = {"monkey-backup.service", "monkey-restore-drill.service", "monkey-alert@.service"}


def msys(path):
    """A path as dash on Git for Windows takes it (/c/...); unchanged elsewhere."""
    p = path.as_posix()
    return f"/{p[0].lower()}{p[2:]}" if re.match(r"[A-Za-z]:/", p) else p


def test_every_service_but_the_self_reporting_ones_alerts_on_failure():
    for unit in sorted(DEPLOY.glob("monkey-*.service")):
        text = unit.read_text()
        head = text.split("[Service]")[0]
        if unit.name in SELF_REPORTING:
            assert not re.search(r"^OnFailure=", text, re.M), unit.name
        else:
            assert "\nOnFailure=monkey-alert@%n.service\n" in head, unit.name
    alert = (DEPLOY / "monkey-alert@.service").read_text()
    assert "User=monkey" in alert and "monkey-alert.sh %i" in alert


@pytest.fixture
def dash(tmp_path):
    bin_dir, calls = tmp_path / "bin", tmp_path / "calls"
    bin_dir.mkdir()
    (bin_dir / "systemctl").write_text('#!/bin/sh\necho "systemctl $*" >>"$FAKE_CALLS"\n'
                                       'echo "${FAKE_STATUS:-1}"\n', newline="\n")
    (bin_dir / "curl").write_text('#!/bin/sh\necho "curl $*" >>"$FAKE_CALLS"\n'
                                  'case " $* " in *" -d @- "*) { cat; echo; } >>"$FAKE_CALLS" ;; esac\n', newline="\n")
    for fake in bin_dir.iterdir():
        fake.chmod(0o755)
    env_file = tmp_path / "deploy.env"
    env_file.write_text("STAFF_WEBHOOK_URL=https://hook/staff\n", newline="\n")

    def run(script, *args, **env):
        environ = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "FAKE_CALLS": calls.as_posix(),
                   "MONKEY_DEPLOY_ENV": msys(env_file), "ALERT_STATE": msys(tmp_path / "state"), **env}
        if calls.exists():
            calls.unlink()
        done = subprocess.run([DASH, (DEPLOY / script).as_posix(), *args], env=environ, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
        out = [re.sub(r"^\S+ \S+ ", "", line) for line in done.stdout.splitlines()]
        return done.returncode, out, calls.read_text().splitlines() if calls.exists() else []

    run.env_file, run.state = env_file, tmp_path / "state"
    return run


def posts(calls):
    return [c for c in calls if c.startswith("{")]


def test_a_failure_posts_the_unit_once_then_counts_repeats_for_6_hours(dash):
    code, out, calls = dash("monkey-alert.sh", "monkey-day.service")
    assert code == 0 and out[-1] == "[monkey-alert] posted: monkey-day.service failed"
    assert posts(calls) == ['{"content":"Monkey SMP: monkey-day.service failed. '
                            'Check: journalctl -u monkey-day.service"}']
    assert any(c.startswith("curl") and c.endswith("https://hook/staff") for c in calls)
    for n in (1, 2):
        code, out, calls = dash("monkey-alert.sh", "monkey-day.service")
        assert code == 0 and posts(calls) == [] and f"counted ({n})" in out[-1]
    # Another unit has its own count.
    _, _, calls = dash("monkey-alert.sh", "monkey-news.service")
    assert len(posts(calls)) == 1
    # Six hours later: one post that says how many were held back.
    state = dash.state / "monkey-day.service"
    state.write_text(f"{int(time.time()) - 6 * 3600 - 1} 2\n", newline="\n")
    _, _, calls = dash("monkey-alert.sh", "monkey-day.service")
    assert posts(calls) == ['{"content":"Monkey SMP: monkey-day.service failed. Check: journalctl -u monkey-day.service'
                            ' (It also failed 2 more time(s) since the last alert about it.)"}']
    assert state.read_text().endswith(" 0\n")


def test_exit_4_means_staff_were_told_so_nothing_is_posted(dash):
    code, out, calls = dash("monkey-alert.sh", "monkey-deploy.service", FAKE_STATUS="4")
    assert code == 0 and posts(calls) == [] and "told staff itself" in out[-1]
    assert "systemctl show -p ExecMainStatus --value monkey-deploy.service" in calls


def test_the_general_webhook_stands_in_and_no_webhook_posts_nothing(dash):
    dash.env_file.write_text("DISCORD_WEBHOOK_URL=https://hook/all\n", newline="\n")
    _, out, calls = dash("monkey-alert.sh", "monkey-week.service")
    assert any(c.endswith("https://hook/all") for c in calls) and len(posts(calls)) == 1
    assert not any("https://" in line for line in out)    # the URL is never logged
    dash.env_file.write_text("", newline="\n")
    code, out, calls = dash("monkey-alert.sh", "monkey-sieges.service")
    assert code == 0 and posts(calls) == [] and "nothing is posted" in out[-1]


@pytest.mark.parametrize("unit", ["", "sshd.service", "monkey-x.timer", "monkey-$(id).service", "monkey-a b.service",
                                  "monkey-../x.service"])
def test_only_a_monkey_service_name_is_taken(dash, unit):
    code, _, calls = dash("monkey-alert.sh", unit)
    assert code in (1, 2) and posts(calls) == []
    assert not dash.state.exists() or not any(dash.state.iterdir())


def logs_folder(tmp_path, days_ago):
    """A live folder whose server/logs holds one daily log per age in days_ago, the logs being written, and others."""
    logs = tmp_path / "live" / "server" / "logs"
    logs.mkdir(parents=True)
    today = dt.datetime.now(dt.timezone.utc).date()  # noqa: UP017
    names = []
    for age in days_ago:
        name = f"{today - dt.timedelta(days=age)}-1.log.gz"
        (logs / name).write_text("x")
        names.append(name)
    for keep in ("latest.log", "debug.log", "notes.txt", "2020-01-01-1.log"):
        (logs / keep).write_text("x")
    (logs / "2020-01-01-1.log.gz.d").mkdir()  # a folder, never removed
    old_debug, new_debug = logs / "debug-1.log.gz", logs / "debug-2.log.gz"
    old_debug.write_text("x")
    new_debug.write_text("x")
    long_ago = time.time() - 200 * 86400
    os.utime(old_debug, (long_ago, long_ago))
    (tmp_path / "live" / "world").mkdir()
    (tmp_path / "live" / "world" / "2020-01-01-1.log.gz").write_text("x")  # not in logs: never removed
    return logs, names


def test_log_pruning_deletes_only_rolled_logs_older_than_the_limit(dash, tmp_path):
    logs, names = logs_folder(tmp_path, [0, 1, 89, 90, 91, 92, 400])
    env = {"LIVE_DIR": msys(tmp_path / "live")}
    code, out, _ = dash("monkey-logs.sh", "--check", **env)
    assert code == 0 and "4 log file(s)" in out[0]
    assert sorted(line.split("] ", 1)[1].strip() for line in out[1:]) == sorted(names[4:] + ["debug-1.log.gz"])
    assert len(list(logs.iterdir())) == len(names) + 7      # --check deleted nothing
    code, out, _ = dash("monkey-logs.sh", **env)
    assert code == 0 and "deleted 4 log file(s) older than 90 days" in out[-1]
    left = sorted(p.name for p in logs.iterdir())
    assert left == sorted(names[:4] + ["latest.log", "debug.log", "notes.txt", "2020-01-01-1.log",
                                       "2020-01-01-1.log.gz.d", "debug-2.log.gz"])
    assert (tmp_path / "live" / "world" / "2020-01-01-1.log.gz").exists()
    code, out, _ = dash("monkey-logs.sh", **env)
    assert code == 0 and out == [f"[monkey-logs] no log in {msys(logs)} is older than 90 days"]


def test_log_pruning_takes_the_days_from_the_settings_and_refuses_a_short_or_bad_limit(dash, tmp_path):
    logs, names = logs_folder(tmp_path, [10, 20, 40])
    dash.env_file.write_text(f"LIVE_DIR={msys(tmp_path / 'live')}\nLOG_KEEP_DAYS=30\n", newline="\n")
    code, out, _ = dash("monkey-logs.sh")
    assert code == 0 and "deleted 2 log file(s) older than 30 days" in out[-1]   # day 40 and the old debug log
    assert (logs / names[1]).exists() and not (logs / names[2]).exists()
    for bad in ("7", "0", "x", "-5", ""):
        dash.env_file.write_text(f"LIVE_DIR={msys(tmp_path / 'live')}\nLOG_KEEP_DAYS={bad}\n", newline="\n")
        code, _, _ = dash("monkey-logs.sh")
        assert code == 1 or bad == "", bad    # empty: the default, 90
        assert (logs / names[0]).exists()


def test_log_pruning_with_no_logs_folder_does_nothing(dash, tmp_path):
    code, out, _ = dash("monkey-logs.sh", LIVE_DIR=msys(tmp_path / "none"))
    assert code == 0 and "nothing to do" in out[-1]
