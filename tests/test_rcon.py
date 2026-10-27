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


def test_send_carries_on_past_a_failure_and_says_so():
    server, log = rcon.Recorder(fail=1), []
    assert rcon.send(server, ["a", "b"], log.append) is False
    assert server.sent == ["b"]
    assert log == ["refused or failed: the server is down", "b: ok"]
    assert rcon.send(rcon.Recorder(), ["c"], log.append, describe=lambda c, a: f"<{c}>") is True
    assert log[-1] == "<c>"
