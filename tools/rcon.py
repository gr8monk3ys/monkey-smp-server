"""Sends console commands to the running server over RCON: the one way the VPS jobs talk to it.

An adapter is called with one command and returns the server's answer. It raises RconError when the command
didn't get through or the server turned it down: RCON exits 0 whenever the server answers, "Unknown function"
too (say, a pack is off), so the answer itself is read (REFUSED). `running()` says whether there is a server
to send to, and raises RconError when it can't tell (docker itself failed), so a broken setup isn't taken for
a stopped server.

    Docker(folder)   the container's own `realms rcon`, through `docker compose` in the release's docker
                     folder. It finds the RCON password itself, so no secret is read here.
    Recorder(...)    keeps what was sent and answers from a table: what the tests use.

send() is the timer jobs' loop (tools/challenges.py and drops.py `send`): every command in order, one log line
each. The week's commands don't depend on each other, so it carries on past a failure; drops passes stop=True,
since its try must not run on the spots of a night whose spots didn't arrive. The standings board (one table
over several commands) stops at its first failure too, in tools/standings.py's update_board.

    python3 tools/rcon.py running --docker DIR   exit 0 when the server is running, 1 when not, 2 when docker
                                                 failed (the timers' --check)
"""
import argparse
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

# The server reads an RCON packet into a 1460-byte buffer, so a longer command arrives cut off.
LIMIT = 1400
REFUSED = ("<--[HERE]", "Unknown or incomplete command", "Unknown function", "Incorrect argument",
           "RCON is turned off")


class RconError(Exception):
    pass


def checked(command: str, answer: str, code: int = 0, errors: str = "") -> str:
    """The answer, or RconError when the command failed or was refused. `errors` (docker's stderr) is read for
    a refusal but isn't part of the answer."""
    if code != 0 or any(m in answer or m in errors for m in REFUSED):
        said = (answer + "\n" + errors).strip()
        raise RconError(f"{command[:60]} answered: {said[-300:] or 'nothing'} (exit {code})")
    return answer


class Docker:
    def __init__(self, folder: Path, run=subprocess.run):
        self.folder, self.run = Path(folder), run

    def compose(self, *args: str, timeout: int) -> subprocess.CompletedProcess:
        argv = ["docker", "compose", "--project-directory", str(self.folder), "-f", str(self.folder / "compose.yaml"),
                *args]
        try:
            return self.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise RconError(f"could not run docker compose ({type(e).__name__})") from None

    def running(self) -> bool:
        done = self.compose("ps", "-q", "--status", "running", "realms", timeout=60)
        if done.returncode != 0:
            raise RconError(f"docker compose ps failed (exit {done.returncode}): {done.stderr.strip()[-300:]}")
        return bool(done.stdout.strip())

    def __call__(self, command: str) -> str:
        done = self.compose("exec", "-T", "realms", "realms", "rcon", command, timeout=180)
        return checked(command, done.stdout.strip(), done.returncode, done.stderr)


class Recorder:
    """A server that answers `answers[command]` (else the first key the command starts with, else ""), and is
    down for the next `fail` commands. `sent` is every command that got through."""

    def __init__(self, answers: dict[str, str] | None = None, running: bool = True, fail: int = 0):
        self.answers, self.up, self.fail, self.sent = answers or {}, running, fail, []

    def running(self) -> bool:
        return self.up

    def __call__(self, command: str) -> str:
        if self.fail:
            self.fail -= 1
            raise RconError("the server is down")
        answer = self.answers.get(command)
        if answer is None:
            answer = next((a for k, a in self.answers.items() if command.startswith(k)), "")
        checked(command, answer)
        self.sent.append(command)
        return answer


def send(rcon, commands: Iterable[str], log: Callable[[str], None] = print,
         describe: Callable[[str, str], str] = lambda command, answer: f"{command}: {answer or 'ok'}",
         stop: bool = False) -> bool:
    """Sends the commands, logging what each did; True when all of them went through. With stop, the first
    failure ends it and the rest aren't sent."""
    ok, commands = True, list(commands)
    for i, command in enumerate(commands):
        try:
            log(describe(command, rcon(command)))
        except RconError as e:
            log(f"refused or failed: {e}")
            ok = False
            if stop:
                if commands[i + 1:]:
                    log(f"not sent after it: {len(commands) - i - 1} command(s)")
                break
    return ok


def send_if_running(rcon, commands: list[str], log: Callable[[str], None] = print, skipped: str = "",
                    **how) -> int:
    """The timers' exit code: 0 when every command went through or the server isn't running (logging
    `skipped`), 1 when one failed or docker did."""
    try:
        up = rcon.running()
    except RconError as e:
        log(f"can't tell whether the server is running: {e}")
        return 1
    if not up:
        log(skipped or "server not running: nothing sent")
        return 0
    return 0 if send(rcon, commands, log, **how) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Is the server running? (the timers' --check)")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("running").add_argument("--docker", type=Path, required=True, help="the release's docker folder")
    args = ap.parse_args(argv)
    try:
        return 0 if Docker(args.docker).running() else 1
    except RconError as e:
        print(e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
