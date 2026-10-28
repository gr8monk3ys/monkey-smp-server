import argparse
import datetime as dt
import subprocess
from pathlib import Path

import pytest

import rcon

DOCKER = Path("/srv/realms/TheRealms-Server/docker")


class FakeRun:
    """subprocess.run as docker compose would answer it."""

    def __init__(self, stdout="", stderr="", code=0, error=None):
        self.stdout, self.stderr, self.code, self.error, self.argv = stdout, stderr, code, error, []

    def __call__(self, argv, **kw):
        self.argv.append(argv)
        assert kw["stdin"] is subprocess.DEVNULL and kw["timeout"]
        if self.error:
            raise self.error
        return subprocess.CompletedProcess(argv, self.code, self.stdout, self.stderr)


def test_docker_sends_through_the_containers_own_rcon():
    run = FakeRun(stdout="There are 0 of a max of 30 players online\n")
    assert rcon.Docker(DOCKER, run)("list") == "There are 0 of a max of 30 players online"
    assert run.argv == [["docker", "compose", "--project-directory", str(DOCKER), "-f", str(DOCKER / "compose.yaml"),
                         "exec", "-T", "realms", "realms", "rcon", "list"]]


@pytest.mark.parametrize("run", [
    FakeRun(stdout="Unknown function realms:drops/try"),
    FakeRun(stdout="Unknown or incomplete command, see below for error\n...<--[HERE]"),
    FakeRun(stdout="Incorrect argument for command"),
    FakeRun(stderr="RCON is turned off", code=1),
    FakeRun(code=1),
    FakeRun(error=OSError("no docker")),
    FakeRun(error=subprocess.TimeoutExpired("docker", 180)),
])
def test_docker_raises_when_a_command_is_refused_or_fails(run):
    with pytest.raises(rcon.RconError):
        rcon.Docker(DOCKER, run)("function realms:drops/try {night:1}")


@pytest.mark.parametrize(("run", "up"), [(FakeRun(stdout="3f2a9c\n"), True), (FakeRun(stdout=""), False)])
def test_docker_running_asks_compose(run, up):
    assert rcon.Docker(DOCKER, run).running() is up
    assert run.argv[0][-5:] == ["ps", "-q", "--status", "running", "realms"]


@pytest.mark.parametrize("run", [FakeRun(stderr="permission denied", code=1), FakeRun(error=OSError("no docker"))])
def test_a_broken_docker_is_not_a_stopped_server(run):
    with pytest.raises(rcon.RconError):
        rcon.Docker(DOCKER, run).running()


def test_docker_warnings_stay_out_of_the_answer():
    run = FakeRun(stdout="Function realms:drops/try returned 13\n", stderr="WARN[0000] `version` is obsolete\n")
    assert rcon.Docker(DOCKER, run)("function realms:drops/try") == "Function realms:drops/try returned 13"


def test_rcon_turned_off_on_stderr_is_still_refused():
    with pytest.raises(rcon.RconError, match="RCON is turned off"):
        rcon.Docker(DOCKER, FakeRun(stderr="RCON is turned off"))("list")


def test_recorder_answers_by_command_or_prefix_and_refuses_like_the_server():
    server = rcon.Recorder({"list": "0 players", "function realms:drops/": "Function returned 1"})
    assert server("list") == "0 players"
    assert server("function realms:drops/try") == "Function returned 1"
    assert server("say hi") == ""
    with pytest.raises(rcon.RconError):
        rcon.Recorder({"function": "Unknown function realms:x"})("function realms:x")
    assert server.sent == ["list", "function realms:drops/try", "say hi"]


def test_send_with_stop_sends_nothing_after_a_failure():
    server, log = rcon.Recorder(fail=1), []
    assert rcon.send(server, ["spots", "try", "more"], log.append, stop=True) is False
    assert server.sent == [] and log == ["refused or failed: the server is down", "not sent after it: 2 command(s)"]
    log.clear()
    assert rcon.send(rcon.Recorder(fail=1), ["last"], log.append, stop=True) is False
    assert log == ["refused or failed: the server is down"]


@pytest.mark.parametrize(("server", "code", "line"), [
    (rcon.Recorder(), 0, "a: ok"),
    (rcon.Recorder(running=False), 0, "server not running: nothing sent"),
    (rcon.Recorder(fail=1), 1, "refused or failed: the server is down"),
    (rcon.Docker(DOCKER, FakeRun(code=1)), 1, "can't tell whether the server is running: docker compose ps failed"),
])
def test_send_if_running_gives_the_timers_exit_code(server, code, line):
    log = []
    assert rcon.send_if_running(server, ["a"], log.append) == code
    assert log[0].startswith(line)


def test_a_required_job_fails_when_the_server_is_not_running():
    log = []
    assert rcon.send_if_running(rcon.Recorder(running=False), ["a"], log.append, required=True) == rcon.NOT_RUNNING
    assert log == ["server not running: nothing sent"] and rcon.NOT_RUNNING not in (0, 1, rcon.GAVE_UP)
    assert rcon.send_if_running(rcon.Recorder(), ["a"], log.append, required=True) == 0


def test_coded_reads_the_call_through_its_codes_and_storage_by_key():
    describe = rcon.coded("function realms:x/try", {1: "started", 5: "off"})
    assert describe("function realms:x/try {n:1}", "Function realms:x/try returned 5") == (
        "function realms:x/try {n:1}: off")
    assert describe("function realms:x/try {n:1}", "Function realms:x/try returned 9") == (
        "function realms:x/try {n:1}: Function realms:x/try returned 9")
    assert describe("function realms:x/try {n:1}", "") == "function realms:x/try {n:1}: ok"
    assert describe("data modify storage realms:x spots set value [{x:1,z:2}]", "") == "spots sent: ok"
    assert describe("function realms:x/stop", "Function realms:x/stop returned 1") == (
        "function realms:x/stop: Function realms:x/stop returned 1")


def test_send_carries_on_past_a_failure_and_says_so():
    server, log = rcon.Recorder(fail=1), []
    assert rcon.send(server, ["a", "b"], log.append) is False
    assert server.sent == ["b"]
    assert log == ["refused or failed: the server is down", "b: ok"]
    assert rcon.send(rcon.Recorder(), ["c"], log.append, describe=lambda c, a: f"<{c}>") is True
    assert log[-1] == "<c>"


# ---------------------------------------------------------------- a timed job's command line


def test_parse_time_reads_utc_and_offsets():
    utc = dt.datetime(2026, 11, 23, 8, tzinfo=rcon.UTC)
    assert rcon.parse_time("2026-11-23T08:00:00Z") == rcon.parse_time("2026-11-23T00:00:00-08:00") == utc
    assert rcon.parse_time("2026-11-23T08:00:00") == utc   # no offset: UTC


def job(argv, world=False, at=True, commands=lambda when: ["a", "b"]):
    """Parses argv with job_subcommands and runs it; returns (exit code, what send was given)."""
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    rcon.job_subcommands(sub, "sends them", world=world, at=at, others=[("spots", "where")])
    args = ap.parse_args(argv)
    given = []
    code = rcon.run_job(args, commands, lambda server, when: given.append((server.folder, when, args)) or 7)
    return code, given


def test_job_commands_prints_one_per_line_and_nothing_when_there_are_none(capsys):
    assert job(["commands", "--at", "2026-11-23T08:00:00Z"]) == (0, [])
    assert capsys.readouterr().out == "a\nb\n"
    assert job(["commands"], commands=lambda when: []) == (0, [])
    assert capsys.readouterr().out == ""


def test_job_send_gets_the_docker_folder_and_the_time():
    code, [(folder, when, _)] = job(["send", "--docker", "/srv/d", "--at", "2026-11-23T08:00:00"])
    assert code == 7 and folder == Path("/srv/d") and when == dt.datetime(2026, 11, 23, 8, tzinfo=rcon.UTC)
    code, [(_, when, args)] = job(["send", "--docker", "/srv/d"])
    assert abs(dt.datetime.now(rcon.UTC) - when) < dt.timedelta(minutes=1)   # no --at: now
    assert abs(rcon.job_time(args) - when) < dt.timedelta(minutes=1)   # the time a tool's other commands get too
    assert rcon.job_time(argparse.Namespace()) - when < dt.timedelta(minutes=1)   # a job without --at


def test_job_subcommands_take_the_world_first_and_at_only_when_asked(capsys):
    code, [(_, _, args)] = job(["send", "/w", "--docker", "/d"], world=True)
    assert args.world == Path("/w")
    with pytest.raises(SystemExit):
        job(["commands", "--at", "2026-11-23T08:00:00Z"], at=False)
    assert "unrecognized arguments: --at" in capsys.readouterr().err
