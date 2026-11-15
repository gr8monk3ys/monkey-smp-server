"""Sends console commands to the running server over RCON: the one way the VPS jobs talk to it.

An adapter is called with one command and returns the server's answer. It raises RconError when the command
didn't get through or the server turned it down: RCON exits 0 whenever the server answers, "Unknown function"
too (say, a pack is off), so the answer itself is read (REFUSED). `running()` says whether there is a server
to send to, and raises RconError when it can't tell (docker itself failed), so a broken setup isn't taken for
a stopped server.

    Docker(folder)   the container's own `monkey rcon`, through `docker compose` in the release's docker
                     folder. It finds the RCON password itself, so no secret is read here.
    Recorder(...)    keeps what was sent and answers from a table: what the tests use.

send() is the timer jobs' loop (tools/challenges.py and drops.py `send`): every command in order, one log line
each. The week's commands don't depend on each other, so it carries on past a failure; drops passes stop=True,
since its try must not run on the spots of a night whose spots didn't arrive. The standings board (one table
over several commands) stops at its first failure too, in tools/standings.py's update_board.

    python3 tools/rcon.py running --docker DIR   exit 0 when the server is running, 1 when not, 2 when docker
                                                 failed (the timers' --check)
    python3 tools/rcon.py packs-on PACK... --docker DIR
                                                 exit 0 when every data pack named is enabled, PACK_OFF when one
                                                 is off, 2 when it can't tell (server down, docker failed, an
                                                 answer it can't read). deploy/lib.sh's timed_job skips a job
                                                 whose pack staff turned off (JOB_PACKS), instead of failing it.
                                                 It keeps the server's list in DIR/.packs-enabled.json for
                                                 PACKS_CACHE_S, for the running container it came from: every
                                                 listing makes the server re-read every pack and mod on its main
                                                 thread. Staff's pack changes drop it. The rule, the copy and
                                                 the restart queue are tools/packs.py's

A timed job's tool (tools/challenges.py, drops.py, wardrobe.py; deploy/lib.sh's timed_job runs them) has the
same three subcommands, from job_subcommands() and run_job(): `commands [--at TIME]`, what it would send now
(changes nothing), `send --docker DIR`, which sends them, and `packs-on --docker DIR`, which checks the data packs
the tool declares it needs (its NEEDS, given to run_job) as `rcon.py packs-on` does; timed_job runs it before it
takes the deploy lock, and skips the job when one is off. send's exit code: 0 sent (or, for most jobs,
the server isn't running), 1 a command wasn't accepted, NOT_RUNNING the server isn't running and the job must
run (the day), GAVE_UP the job stopped trying (the day, after 6 hours of tries).
"""
import argparse
import datetime as dt
import re
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

import packs

UTC = dt.timezone.utc   # noqa: UP017 (datetime.UTC is 3.11+, and the VPS may have 3.10)
# A timed job's `send` exit codes besides 0 and 1 (deploy/lib.sh's timed_job tells them apart). deploy/lib.sh names
# these three (JOB_NOT_RUNNING, ...): a test checks it has the same numbers.
NOT_RUNNING = 3
GAVE_UP = 4
# `packs-on`: a data pack the job needs is off (staff turned it off; deploy/lib.sh's timed_job skips the job).
PACK_OFF = 5
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

    def container(self) -> str:
        """The running server container's id, "" when it isn't running."""
        done = self.compose("ps", "-q", "--status", "running", "monkey", timeout=60)
        if done.returncode != 0:
            raise RconError(f"docker compose ps failed (exit {done.returncode}): {done.stderr.strip()[-300:]}")
        return done.stdout.strip()

    def running(self) -> bool:
        return bool(self.container())

    def __call__(self, command: str) -> str:
        done = self.compose("exec", "-T", "monkey", "monkey", "rcon", command, timeout=180)
        return checked(command, done.stdout.strip(), done.returncode, done.stderr)


class Recorder:
    """A server that answers `answers[command]` (else the first key the command starts with, else ""), and is
    down for the next `fail` commands. `sent` is every command that got through."""

    def __init__(self, answers: dict[str, str] | None = None, running: bool = True, fail: int = 0):
        self.answers, self.up, self.fail, self.sent = answers or {}, running, fail, []

    def running(self) -> bool:
        return self.up

    def container(self) -> str:
        return "box1" if self.up else ""

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


def coded(call: str, codes: dict[int, str]) -> Callable[[str, str], str]:
    """A describe for send(), for a job whose last command is a function returning why it did nothing (drops'
    and omens' try): that call's answer reads as its code in words (`codes`), storage sent before it as "<key>
    sent", and anything else as the start of the command."""
    def describe(command: str, answer: str) -> str:
        if not command.startswith(call):
            m = re.match(r"data modify storage \S+ (\w+) set value", command)
            return f"{m[1] + ' sent' if m else command[:60]}: {answer or 'ok'}"
        m = re.search(r" returned (\d+)$", answer)
        return f"{command}: {codes.get(int(m[1]), answer) if m else answer or 'ok'}"
    return describe


def send_if_running(rcon, commands: list[str], log: Callable[[str], None] = print, skipped: str = "",
                    required: bool = False, **how) -> int:
    """The timers' exit code: 0 when every command went through or the server isn't running (logging
    `skipped`), 1 when one failed or docker did. With required, a server that isn't running is NOT_RUNNING, for
    a job that systemd tries again until the server answers (the day)."""
    try:
        up = rcon.running()
    except RconError as e:
        log(f"can't tell whether the server is running: {e}")
        return 1
    if not up:
        log(skipped or "server not running: nothing sent")
        return NOT_RUNNING if required else 0
    return 0 if send(rcon, commands, log, **how) else 1


def packs_off(rcon, names: Iterable[str], folder: Path | None = None, fresh: bool = False) -> list[str]:
    """Which of the world data packs NAMES (folder names, e.g. monkey-wardrobe) are off on the running server:
    tools/packs.py's rule. With FOLDER (the docker folder) the kept copy is used (and refreshed), unless `fresh`:
    then the server is asked and the copy refreshed. Without FOLDER the server is asked and nothing is kept: for a
    decision that can't wait out a copy staff's `monkey rcon` didn't drop. RconError when the server isn't running
    or its answer can't be read, so an answer it can't read never reads as "off"."""
    names = list(names)
    if not names:
        return []
    box = rcon.container() if folder is not None else ""
    if folder is not None and not box:
        raise RconError("server not running")
    try:
        said = packs.listing(rcon, folder, box, fresh=fresh) if folder is not None else rcon(packs.LIST)
        return packs.off(said, names)
    except packs.Unreadable as e:
        raise RconError(str(e)) from None


# ---------------------------------------------------------------- a timed job's command line


def parse_time(value: str) -> dt.datetime:
    """--at's time: ISO 8601, UTC when it has no offset."""
    when = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def job_subcommands(sub, send_about: str, world: bool = False, at: bool = True,
                    others: Iterable[tuple[str, str]] = ()) -> None:
    """Adds a timed job's `commands` and `send` to the subparsers `sub`, after `others` (name, help), which take
    the same arguments: the world folder first when `world`, and --at TIME when `at`. send also takes --docker."""
    for name, about in (*others, ("commands", "the RCON commands for now (changes nothing)"), ("send", send_about)):
        p = sub.add_parser(name, help=about)
        if world:
            p.add_argument("world", type=Path, help="the world folder (server/world)")
        if at:
            p.add_argument("--at", type=parse_time, help="pretend it is this time (ISO 8601; UTC if no offset)")
        if name == "send":
            p.add_argument("--docker", type=Path, required=True, help="the release's docker folder (for RCON)")
    p = sub.add_parser("packs-on", help="are the data packs this job needs on? (exit PACK_OFF when one is off)")
    p.add_argument("--docker", type=Path, required=True, help="the release's docker folder (for RCON)")


def job_time(args) -> dt.datetime:
    """The time a job_subcommands command runs for: --at, else now."""
    return getattr(args, "at", None) or dt.datetime.now(UTC)


def run_job(args, commands: Callable[[dt.datetime], list[str]], send: Callable[[Docker, dt.datetime], int],
            needs: Iterable[str] = ()) -> int:
    """Runs job_subcommands' `commands` (prints them one per line, nothing when there are none), `send`
    (send(the server, when)), for job_time(args), or `packs-on`: whether the data packs NEEDS are on."""
    if args.command == "packs-on":
        return packs_on(Docker(args.docker), list(needs), args.docker)
    when = job_time(args)
    if args.command == "send":
        return send(Docker(args.docker), when)
    out = commands(when)
    if out:
        print("\n".join(out))
    return 0


def main(argv=None, server=Docker) -> int:
    ap = argparse.ArgumentParser(description="Is the server running, with these data packs on? (the timers)")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("running").add_argument("--docker", type=Path, required=True, help="the release's docker folder")
    on = sub.add_parser("packs-on")
    on.add_argument("packs", nargs="+", help="world data pack folder names (monkey-wardrobe)")
    on.add_argument("--docker", type=Path, required=True, help="the release's docker folder")
    on.add_argument("--fresh", action="store_true", help="ask the server, not the kept list (it keeps the answer)")
    args = ap.parse_args(argv)
    rcon = server(args.docker)
    if args.command == "running":
        try:
            return 0 if rcon.running() else 1
        except RconError as e:
            print(e, file=sys.stderr)
            return 2
    return packs_on(rcon, args.packs, args.docker, fresh=args.fresh)


def packs_on(rcon, names: list[str], folder: Path, fresh: bool = False) -> int:
    """`packs-on`'s answer: prints which pack is off (or that all are on) and returns PACK_OFF, 0, or 2 when it
    can't tell (the server isn't running, docker failed, an answer it can't read)."""
    try:
        off = packs_off(rcon, names, folder, fresh)
    except RconError as e:
        print(e, file=sys.stderr)
        return 2
    if off:
        print(f"data pack off: {' '.join(off)}")
        return PACK_OFF
    print(f"data packs on: {' '.join(names)}" if names else "data packs on: none needed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
