"""tests/hosting-smoke.sh's verdict, with a stand-in for docker: it can only run the real thing where Docker does."""
import os
import re
import shutil
import subprocess
import zipfile

import pytest

from repo import REPO

SCRIPT = REPO.root / "tests" / "hosting-smoke.sh"
BASH = shutil.which("bash")
BOOT_TESTS = [REPO.root / "tests" / name for name in ("smoke.ps1", "docker-smoke.sh", "hosting-smoke.sh")]
DONE = 'Done (12.3s)! For help, type "help"\n'
SAVED = DONE + "All dimensions are saved\n"

# Lines as the server logs them (26.2), and whether the boot must fail on them.
ERROR = "[16:31:09] [main/ERROR]: "
DATA_LINES = [
    (ERROR + "Failed to load function monkey:camera/tick", True),
    (ERROR + "Failed to load function strength_smp:tick", True),
    (ERROR + "Couldn't load tag minecraft:tick as it is missing following references: monkey:camera/tick "
     "(from file/monkey-camera)", True),
    (ERROR + "Couldn't parse data file 'monkey:firsts/root' from 'monkey:advancement/firsts/root.json': "
     "DataResult.Error['No key criteria']", True),
    (ERROR + "Couldn't parse data file 'rcl:rcl' from 'rcl:advancement/rcl.json': DataResult.Error['x']", True),
    (ERROR + "Couldn't parse data file 'morevillagers:gilded_station' from 'morevillagers:recipe/gilded_station.json': "
     "DataResult.Error['Map entry '#' : Failed to parse either']", False),
    (ERROR + "Couldn't load advancements: [strength_smp:strength_smp, monkey:firsts/dragon, rcl:rcl]", True),
    (ERROR + "Couldn't load advancements: [monkey:firsts/dragon]", True),
    (ERROR + "Couldn't load advancements: [strength_smp:strength_smp, minecraft:adventure/totem_of_undying, "
     "codemonkey:root]", False),
    ("[16:31:15] [Server thread/INFO]: Loaded 946 functions", False),
]

FAKE_DOCKER = """#!/bin/sh
echo "$*" >> "$FAKE/calls"
case "$*" in
    'compose logs --no-color monkey') cat "$FAKE/log" ;;
    'compose ps --status running --services') echo monkey ;;
    'compose ps --all --quiet monkey') echo abc123 ;;
    'compose up -d' | 'compose stop -t 180' | 'compose down') ;;
    'inspect --format {{.State.Running}} {{.State.ExitCode}} abc123')
        [ -f "$FAKE/state" ] || exit 1; cat "$FAKE/state" ;;
    *) echo "the script called docker in a way this stand-in doesn't know: $*" >&2; exit 64 ;;
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
@pytest.mark.parametrize("state", ["false 0", "false 143", "false 137", "false 1", "true 0", None])
def test_no_saved_line_fails_however_the_container_stopped(tmp_path, state):
    """A clean exit proves no save: the world could have stopped short of it."""
    done = run(tmp_path, DONE, state)
    assert done.returncode == 1 and "no clean shutdown in the log" in done.stdout
    assert "HOSTING SMOKE TEST FAILED" in done.stdout


@needs_posix
def test_errors_in_the_log_fail_even_with_the_saved_line(tmp_path):
    done = run(tmp_path, SAVED + "Exception in server tick loop\n", "false 143")
    assert done.returncode == 1 and "errors in the server log" in done.stdout


def data_patterns(script) -> tuple[str, str]:
    """The two patterns a boot test reads the log with: what failed to load, and what is known to."""
    text = script.read_text()
    return tuple(re.search(rf'^\$?{name} ?= ?"(.*)"$', text, re.M).group(1)
                 for name in ("data_?[eE]rrors", "known_?[dD]ata"))


def test_the_three_boot_tests_look_for_the_same_data_errors():
    assert len({data_patterns(script) for script in BOOT_TESTS}) == 1


@pytest.mark.parametrize("line,fails", DATA_LINES)
def test_what_counts_as_data_that_failed_to_load(line, fails):
    """The patterns themselves, so this runs where bash doesn't."""
    errors, known = data_patterns(SCRIPT)
    assert bool(re.search(errors, line) and not re.search(known, line)) == fails


@needs_posix
@pytest.mark.parametrize("line,fails", DATA_LINES)
def test_data_that_failed_to_load_fails_even_with_the_saved_line(tmp_path, line, fails):
    done = run(tmp_path, SAVED + line + "\n", "false 143")
    assert done.returncode == (1 if fails else 0)
    assert ("data that failed to load" in done.stdout) == fails


@needs_posix
def test_the_script_makes_no_docker_call_the_stand_in_doesnt_know(tmp_path):
    done = run(tmp_path, SAVED, "false 143")
    assert done.returncode == 0 and "doesn't know" not in done.stderr


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
