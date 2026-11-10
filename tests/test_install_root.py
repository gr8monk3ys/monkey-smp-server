"""deploy/install-root.sh: root's own copies of what root runs, from root's clone, only for a release that passed the
release gate. Runs under dash with fakes for git, id, stat, realpath, install, systemctl and python3 (the gate)."""
import os
import re
import shutil
import subprocess

import pytest

from repo import REPO

DEPLOY = REPO.root / "deploy"
SCRIPT = DEPLOY / "install-root.sh"
DASH = shutil.which("dash")
COMMIT = "a" * 40
REMOTE = "https://github.com/gr8monk3ys/monkey-smp-server.git"
pytestmark = pytest.mark.skipif(not DASH, reason="needs dash")


def msys(path):
    """A path as dash on Git for Windows takes it (/c/...); unchanged elsewhere."""
    p = path.as_posix()
    return f"/{p[0].lower()}{p[2:]}" if re.match(r"[A-Za-z]:/", p) else p


def root_files():
    text = (DEPLOY / "lib.sh").read_text()
    files = re.search(r"^ROOT_FILES='([^']*)'", text, re.M).group(1).split()
    units = re.search(r"^ROOT_NEW_UNITS='([^']*)'", text, re.M).group(1).split()
    return files, units


def test_every_root_file_and_new_unit_is_in_the_repo_and_every_root_unit_runs_a_root_copy():
    files, units = root_files()
    for f in files:
        assert (REPO.root / f).is_file(), f
    for u in units:
        assert (DEPLOY / u).is_file(), u
    # A unit that runs as root (no User=) runs only /opt/monkey copies, never the checkout monkey can write.
    for unit in DEPLOY.glob("monkey-*.service"):
        text = unit.read_text()
        if re.search(r"^User=monkey$", text, re.M):
            continue
        for line in re.findall(r"^Exec\w*=(.*)$", text, re.M):
            assert "/srv/monkey/repo" not in line and "%h" not in line, (unit.name, line)
            for path in re.findall(r"(/\S+\.(?:sh|py))", line):
                assert path.startswith("/opt/monkey/"), (unit.name, line)


@pytest.fixture
def run(tmp_path):
    """Root's clone (SRC) holds the root files and some units; DEST and UNITS start empty."""
    files, _ = root_files()
    src, dest, units, bin_dir = (tmp_path / n for n in ("src", "dest", "units", "bin"))
    calls = tmp_path / "calls"
    for d in (src / ".git", dest, units, bin_dir):
        d.mkdir(parents=True)
    for f in files:
        (src / f).parent.mkdir(parents=True, exist_ok=True)
        (src / f).write_text(f"# {f} v2\n", newline="\n")
    for script in ("monkey-logs.sh", "monkey-alert.sh"):   # the deployed checkout (REPO_DIR is src here) has them
        (src / "deploy" / script).write_text("#\n", newline="\n")
    for u in ("monkey-backup.service", "monkey-backup.timer", "monkey-logs.timer", "monkey-other.service"):
        (src / "deploy" / u).write_text(f"[Unit]\n# {u} v2\n", newline="\n")
    fakes = {
        "git": 'case "$*" in\n'
               f'  *"remote get-url origin"*) echo "${{FAKE_REMOTE:-{REMOTE}}}" ;;\n'
               '  *"tag -l"*) printf "${FAKE_TAGS-v3.5.0\\nv3.4.0\\n}" ;;\n'
               f'  *rev-parse*) [ -z "${{FAKE_NO_TAG:-}}" ] || exit 1; echo {COMMIT} ;;\n'
               'esac\n',
        "id": 'echo "${FAKE_UID:-0}"\n',
        "stat": 'case "$*" in *"${FAKE_GROUP_WRITABLE:-@none@}"*) echo "0 drwxrwxr-x" ;;\n'
                '  *) echo "0 drwxr-xr-x" ;; esac\n',
        "realpath": 'echo "$2"\n',
        # install: no owners on Windows; -d makes folders, else copies the last two arguments.
        "install": 'last=; prev=; dir=0\nfor a in "$@"; do case $a in -d) dir=1 ;; esac; prev=$last; last=$a; done\n'
                   'if [ $dir = 1 ]; then mkdir -p "$last"; else cp "$prev" "$last"; fi\n',
        "systemctl": 'exit "${FAKE_RC_systemctl:-0}"\n',
        "python3": 'case "$*" in *release_gate.py*) echo "${FAKE_GATE:-release gate: ok}"; exit "${FAKE_RC_gate:-0}" ;;'
                   ' esac\n',
    }
    for name, body in fakes.items():
        (bin_dir / name).write_text(f'#!/bin/sh\necho "{name} $*" >>"$FAKE_CALLS"\n{body}', newline="\n")
        (bin_dir / name).chmod(0o755)

    def go(*args, **env):
        environ = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "FAKE_CALLS": calls.as_posix(),
                   "ROOT_SRC": msys(src), "ROOT_DEST": msys(dest), "UNIT_DIR": msys(units),
                   "REPO_DIR": msys(src), "MONKEY_DEPLOY_ENV": msys(tmp_path / "none.env"), **env}
        if calls.exists():
            calls.unlink()
        done = subprocess.run([DASH, SCRIPT.as_posix(), *args], env=environ, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
        out = [re.sub(r"^\S+ \S+ ", "", line) for line in done.stdout.splitlines()]
        made = calls.read_text().splitlines() if calls.exists() else []
        return done.returncode, out, made

    go.src, go.dest, go.units, go.files = src, dest, units, files
    return go


def test_an_install_copies_the_root_files_the_changed_and_new_units_and_records_the_tag(run):
    (run.units / "monkey-backup.service").write_text("[Unit]\n# monkey-backup.service v1\n", newline="\n")
    (run.units / "monkey-backup.timer").write_text("[Unit]\n# monkey-backup.timer v2\n", newline="\n")  # the same
    code, out, calls = run()
    assert code == 0, out
    for f in run.files:
        assert (run.dest / f).read_text() == f"# {f} v2\n"
    assert not list(run.dest.rglob("*.new"))
    # Changed (backup.service) and new from ROOT_NEW_UNITS (logs.timer); the same one and an uninstalled other: not.
    assert sorted(p.name for p in run.units.iterdir()) == ["monkey-backup.service", "monkey-backup.timer",
                                                           "monkey-logs.timer"]
    assert "v2" in (run.units / "monkey-backup.service").read_text()
    assert (run.dest / "INSTALLED").read_text() == f"v3.5.0 {COMMIT}\n"
    gate = next(c for c in calls if "release_gate.py" in c)
    assert gate.endswith(f"{COMMIT} --tag v3.5.0")
    sysd = [c for c in calls if c.startswith("systemctl")]
    assert sysd == ["systemctl daemon-reload", "systemctl try-restart monkey-logs.timer",
                    "systemctl enable --now monkey-logs.timer"]
    assert f"checkout --quiet --force --detach {COMMIT}" in " ".join(calls)
    assert out[-1].startswith(f"[install-root] done: root's copies are v3.5.0 ({len(run.files)} file(s) changed)")
    # A second run changes nothing.
    code, out, calls = run()
    assert code == 0 and "(0 file(s) changed), units changed: none" in out[-1]
    assert "systemctl daemon-reload" not in calls


def test_a_release_the_gate_holds_installs_nothing(run):
    code, out, calls = run(FAKE_RC_gate="1", FAKE_GATE="release gate: not yet: v3.5.0 has no published release")
    assert code == 1 and "v3.5.0 was not installed: not yet: v3.5.0 has no published release" in out[-1]
    assert not any(run.dest.rglob("*.*")) and not list(run.units.iterdir())
    assert not any("checkout" in c for c in calls) and not any(c.startswith("systemctl") for c in calls)


def test_the_tag_given_is_the_one_asked_about_and_a_bad_tag_stops_before_git(run):
    code, _, calls = run("--tag=v3.4.0")
    assert code == 0 and next(c for c in calls if "release_gate.py" in c).endswith("--tag v3.4.0")
    for bad in ("--tag=main", "--tag=v1.2", "--tag=v1.2.3;rm", "--tag=v1..2.3"):
        code, out, calls = run(bad)
        assert code == 1 and "takes a release tag" in out[-1] and calls == [], bad


def test_install_refuses_without_root_a_strange_origin_a_writable_folder_or_a_missing_tag(run):
    code, out, _ = run(FAKE_UID="1000")
    assert code == 1 and "run this as root" in out[-1]
    code, out, _ = run(FAKE_REMOTE="https://example.com/evil.git")
    assert code == 1 and "origin is not" in out[-1]
    code, out, _ = run(FAKE_GROUP_WRITABLE=msys(run.src))
    assert code == 1 and "writable by others than root" in out[-1]
    code, out, _ = run(FAKE_TAGS="")
    assert code == 1 and "no release tag" in out[-1]
    code, out, _ = run(FAKE_NO_TAG="1")
    assert code == 1 and "there is no tag v3.5.0" in out[-1]
    assert not any(run.dest.rglob("*.*"))


def test_an_old_release_without_the_root_files_installs_nothing(run):
    (run.src / "tools" / "restore_drill.py").unlink()
    code, out, _ = run()
    assert code == 1 and "has no tools/restore_drill.py" in out[-1]
    assert not any(run.dest.rglob("*.*"))


def test_check_lists_what_differs_and_changes_nothing_for_any_user(run):
    code, out, calls = run("--check", FAKE_UID="1000")
    assert code == 0 and "differ from" in out[0]
    listed = [line.strip().split("] ", 1)[1].strip() for line in out[1:]]
    assert set(listed) == set(run.files) | {"monkey-logs.timer"}
    assert all(c.split()[0] not in ("git", "install", "systemctl") for c in calls)
    run()
    code, out, _ = run("--check", FAKE_UID="1000")
    assert code == 0 and out == [f"[install-root] root's copies and the units match {msys(run.src)}"]


def test_the_log_timer_waits_for_a_checkout_that_has_its_scripts(run):
    (run.src / "deploy" / "monkey-logs.sh").unlink()
    code, out, calls = run()
    assert code == 0 and not any("enable" in c for c in calls)
    assert any("run this again once it is live" in line for line in out)
