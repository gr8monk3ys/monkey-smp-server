"""Sends console commands to the running server over RCON: the one way the VPS jobs talk to it.

An adapter is called with one command and returns the server's answer. It raises RconError when the command
didn't get through or the server turned it down: RCON exits 0 whenever the server answers, "Unknown function"
too (say, a pack is off), so the answer itself is read (REFUSED). `running()` says whether there is a server
to send to.

    Docker(folder)   the container's own `realms rcon`, through `docker compose` in the release's docker
                     folder. It finds the RCON password itself, so no secret is read here.
    Recorder(...)    keeps what was sent and answers from a table: what the tests use.

send() is the timer jobs' loop (tools/challenges.py and drops.py `send`): every command in order, one log line
each, carrying on past a failure, since each command does nothing when nothing changed and the next run retries.
"""
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path

# The server reads an RCON packet into a 1460-byte buffer, so a longer command arrives cut off.
LIMIT = 1400
REFUSED = ("<--[HERE]", "Unknown or incomplete command", "Unknown function", "Incorrect argument",
           "RCON is turned off")


class RconError(Exception):
    pass


def checked(command: str, answer: str, code: int = 0) -> str:
    """The answer, or RconError when the command failed or was refused."""
    if code != 0 or any(m in answer for m in REFUSED):
        raise RconError(f"{command[:60]} answered: {answer[-300:] or 'nothing'} (exit {code})")
    return answer


class Docker:
    def __init__(self, folder: Path, run=subprocess.run):
        self.folder, self.run = Path(folder), run

    def compose(self, *args: str) -> list[str]:
        return ["docker", "compose", "--project-directory", str(self.folder), "-f", str(self.folder / "compose.yaml"),
                *args]

    def running(self) -> bool:
        try:
            done = self.run(self.compose("ps", "-q", "--status", "running", "realms"), stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return done.returncode == 0 and bool(done.stdout.strip())

    def __call__(self, command: str) -> str:
        try:
            done = self.run(self.compose("exec", "-T", "realms", "realms", "rcon", command), stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise RconError(f"could not run docker compose ({type(e).__name__})") from None
        return checked(command, (done.stdout + done.stderr).strip(), done.returncode)


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
         describe: Callable[[str, str], str] = lambda command, answer: f"{command}: {answer or 'ok'}") -> bool:
    """Sends every command, logging what each did; True when all of them went through."""
    ok = True
    for command in commands:
        try:
            log(describe(command, rcon(command)))
        except RconError as e:
            log(f"refused or failed: {e}")
            ok = False
    return ok
