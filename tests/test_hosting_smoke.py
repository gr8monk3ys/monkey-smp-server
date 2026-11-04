"""tests/hosting-smoke.sh's verdict, with a stand-in for docker: it can only run the real thing where Docker does."""
import os
import shutil
import subprocess
import zipfile

import pytest

from repo import REPO

SCRIPT = REPO.root / "tests" / "hosting-smoke.sh"
BASH = shutil.which("bash")
DONE = 'Done (12.3s)! For help, type "help"\n'
SAVED = DONE + "All dimensions are saved\n"

FAKE_DOCKER = """#!/bin/sh
echo "$*" >> "$FAKE/calls"
case "$*" in
    'compose logs --no-color monkey') cat "$FAKE/log" ;;
    'compose ps --status running --services') echo monkey ;;
    'compose ps --all --quiet monkey') echo abc123 ;;
    inspect*) [ -f "$FAKE/state" ] || exit 1; cat "$FAKE/state" ;;
esac
"""


def run(tmp_path, log: str, state: str | None) -> subprocess.CompletedProcess:
    fake = tmp_path / "fake"
    fake.mkdir()
    (fake / "docker").write_text(FAKE_DOCKER, newline="\n")
    (fake / "docker").chmod(0o755)
    (fake / "log").write_text(log)
    if state is not None:
        (fake / "state").write_text(state + "\n")
    bundle = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle, "w") as z:
        info = zipfile.ZipInfo("MonkeySMP-9.9.9-hosting/start.sh")
        info.external_attr = 0o755 << 16
        z.writestr(info, "#!/bin/sh\n")
    env = {**os.environ, "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}", "FAKE": str(fake),
           "AFTER_DONE_SECONDS": "0"}
    return subprocess.run([BASH, str(SCRIPT), str(bundle), str(tmp_path / "work")], env=env, text=True,
                          capture_output=True, timeout=120)


needs_posix = pytest.mark.skipif(os.name == "nt" or not BASH or not shutil.which("unzip"),
                                 reason="needs bash and unzip on a POSIX system")


@needs_posix
def test_the_saved_line_passes(tmp_path):
    done = run(tmp_path, SAVED, "false 143")
    assert done.returncode == 0 and "HOSTING SMOKE TEST PASSED" in done.stdout


@needs_posix
@pytest.mark.parametrize("state", ["false 0", "false 143"])
def test_a_clean_exit_passes_without_the_saved_line(tmp_path, state):
    """CI run 41883500387: stopped during the post-start save, the saved line never printed, a clean exit."""
    done = run(tmp_path, DONE, state)
    assert done.returncode == 0 and "HOSTING SMOKE TEST PASSED" in done.stdout and state in done.stdout


@needs_posix
@pytest.mark.parametrize("state", ["false 137", "false 1", "true 0", None])   # killed; crashed; still running; unknown
def test_no_saved_line_and_no_clean_exit_fails(tmp_path, state):
    done = run(tmp_path, DONE, state)
    assert done.returncode == 1 and "no clean shutdown in the log" in done.stdout
    assert "HOSTING SMOKE TEST FAILED" in done.stdout


@needs_posix
def test_a_clean_exit_doesnt_excuse_errors_in_the_log(tmp_path):
    done = run(tmp_path, DONE + "Exception in server tick loop\n", "false 143")
    assert done.returncode == 1 and "errors in the server log" in done.stdout


@needs_posix
def test_the_state_is_read_before_the_container_is_removed(tmp_path):
    run(tmp_path, SAVED, "false 143")
    calls = (tmp_path / "fake" / "calls").read_text().splitlines()
    stop, state, down = (next(i for i, c in enumerate(calls) if c.startswith(p))
                         for p in ("compose stop", "inspect", "compose down"))
    assert stop < state < down


def test_it_waits_after_done_before_the_stop_and_parses_under_dash():
    text = SCRIPT.read_text()
    assert text.index('sleep "${AFTER_DONE_SECONDS:-20}"') < text.index("docker compose stop -t 180")
    dash = shutil.which("dash")
    if dash:
        subprocess.run([dash, "-n", str(SCRIPT)], check=True)
