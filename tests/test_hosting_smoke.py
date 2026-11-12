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
WARN = "[16:31:09] [Worker-Main-3/WARN]: "
# The line the server logs after a function's, with the reason.
REASON = ("java.util.concurrent.CompletionException: java.lang.IllegalArgumentException: "
          "Whilst parsing command on line 3: x")
DATA_LINES = [
    (ERROR + "Failed to load function monkey:camera/tick", True),
    (ERROR + "Failed to load function strength_smp:tick", True),
    (ERROR + "Couldn't load tag minecraft:tick as it is missing following references: monkey:camera/tick "
     "(from file/monkey-camera)", True),
    (ERROR + "Couldn't parse data file 'monkey:firsts/root' from 'monkey:advancement/firsts/root.json': "
     "DataResult.Error['No key criteria']", True),
    (ERROR + "Couldn't parse data file 'rcl:rcl' from 'rcl:advancement/rcl.json': DataResult.Error['x']", True),
    (ERROR + "Couldn't read tag list minecraft:tick from minecraft:tags/function/tick.json in data pack "
     "file/monkey-camera", True),
    (WARN + "Found validation problems in advancement monkey:firsts/dragon: ", True),
    (WARN + "Found loot table element validation problem in {minecraft:loot_table/monkey:drops/boss}: x", True),
    # More Villagers' files that 26.2 can't read are patched now, so none of its errors is known any more.
    (ERROR + "Couldn't parse data file 'morevillagers:gilded_station' from 'morevillagers:recipe/gilded_station.json': "
     "DataResult.Error['Map entry '#' : Failed to parse either']", True),
    (ERROR + "Couldn't parse data file 'morevillagers:kill_villager' from "
     "'morevillagers:advancement/kill_villager.json': DataResult.Error['x']", True),
    (ERROR + "Couldn't parse data file 'morevillagers:oceanography_table' from "
     "'morevillagers:recipe/oceanography_table.json': DataResult.Error['x']", True),
    (ERROR + "Couldn't parse data file 'morevillagers:gilded_station' from "
     "'morevillagers:loot_table/blocks/gilded_station.json': DataResult.Error['x']", True),
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
def test_a_stray_byte_in_the_log_hides_no_line(tmp_path):
    """grep calls a log with a NUL in it binary, and without -a prints "binary file matches", not the lines."""
    done = run(tmp_path, SAVED + "x\0y\n" + DATA_LINES[0][0] + "\n", "false 143")
    assert done.returncode == 1 and "Failed to load function monkey:camera/tick" in done.stdout
    (tmp_path / "errors").mkdir()
    done = run(tmp_path / "errors", SAVED + "x\0y\nException in server tick loop\n", "false 143")
    assert done.returncode == 1 and "Exception in server tick loop" in done.stdout


def block(script, first: str, last: str) -> str:
    """A boot test's lines from the one that starts with `first` to the next one that is `last`."""
    lines = script.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(first))
    return "\n".join(lines[start:lines.index(last, start) + 1])


@needs_posix
@pytest.mark.parametrize("line,fails", DATA_LINES)
@pytest.mark.parametrize("server_log", [True, False])
def test_docker_smoke_reads_the_same_lines(tmp_path, line, fails, server_log):
    """docker-smoke.sh needs Docker whole, so only its lines for this. Without server/logs/latest.log grep exits
    with 2, lines found or not."""
    (tmp_path / "compose.log").write_text(f"monkey-1  | {line}\n")
    if server_log:
        (tmp_path / "latest.log").write_text(SAVED + line + "\n")
    script = "set -euo pipefail\nfail=0\n" + block(BOOT_TESTS[1], "data_errors=", "fi") + '\nexit "$fail"\n'
    done = subprocess.run([BASH, "-c", script], env={**os.environ, "root": str(tmp_path),
                          "log": str(tmp_path / "latest.log")}, text=True, capture_output=True, timeout=60)
    assert done.returncode == (1 if fails else 0), done.stdout + done.stderr
    assert ("data that failed to load" in done.stdout) == fails


POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@pytest.mark.skipif(not POWERSHELL, reason="needs PowerShell")
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_smoke_ps1_reads_the_same_lines_and_takes_the_reason_along(tmp_path, newline):
    """smoke.ps1 boots the real server, so only its lines for this, on a log with every sample line in it."""
    log = [DATA_LINES[0][0], REASON, *(line for line, _ in DATA_LINES[1:])]
    (tmp_path / "latest.log").write_text(newline.join(log) + newline, newline="")
    (tmp_path / "data.ps1").write_text(
        "$logText = Get-Content -LiteralPath $args[0] -Raw\n"
        "$failures = New-Object System.Collections.Generic.List[string]\n"
        + block(BOOT_TESTS[0], "$dataErrors =", "}") + "\n$failures\n")
    done = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                           str(tmp_path / "data.ps1"), str(tmp_path / "latest.log")], text=True,
                          capture_output=True, timeout=120)
    assert done.returncode == 0, done.stderr
    wanted = [f"data failed to load: {line.strip()}" for line, fails in DATA_LINES if fails]
    wanted[0] += " <- " + REASON
    assert [line.strip() for line in done.stdout.splitlines() if line.strip()] == wanted


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
