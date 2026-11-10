"""The staff page's controls: the server's console, its files, its players and its power, for the people who run it.

    python3 tools/staff_panel.py serve      listens on 127.0.0.1:8130 (deploy/monkey-panel.service, as monkey)

Caddy sends /api/* here from https://staff.monkeysmp.lscaturchio.xyz after its password check, with the login's name
in X-Staff-User (deploy/Caddyfile.staff). docs/LIVE.md, "The staff page", says what staff can and cannot do with it.

Every request must come from this machine and name a login. Every change must also carry `X-Monkey-Staff: 1`, and a
`Sec-Fetch-Site` other than same-origin is refused: the browser keeps sending the password once it has it, so a page
on another site must not be able to make a change in a staff member's name. Answers are JSON, {"ok": true, ...} or
{"ok": false, "error": "..."}, except a download.

    GET  /api/console?after=OFFSET    new lines of server/logs/latest.log (the last 64 KB the first time), masked
    POST /api/command {"command"}     one console command through the container's own `monkey rcon`
    GET  /api/power                   running, stopped or restarting
    POST /api/power {"action"}        restart (monkey-deploy.sh --restart: the 5-minute warning), restart-now, stop,
                                      start; one at a time
    GET  /api/files?path=DIR          a folder of LIVE_DIR/server
    GET  /api/file?path=F             a text file, secrets masked; PUT /api/file {"path", "text", "mtime"} saves it
    GET  /api/download?path=F         the file itself (a text file with its secrets masked)
    POST /api/upload?path=DIR&name=N  a file, the raw body
    POST /api/delete {"path"}         moves a file to the history
    POST /api/folder {"path"}         makes an empty folder
    POST /api/rename {"path", "to"}   a file's new name or folder; a name already taken is refused
    GET  /api/history                 the last 50 saved copies; POST /api/restore {"entry", "path"} puts one back
    GET  /api/players                 whitelist, ops, bans and who is online
    GET  /api/timers                  the monkey-*.timer schedules
    GET  /api/backups                 the last backup, as the status page has it
    GET  /api/actions                 the last 100 changes made here
    GET  /api/known-players, /api/player-notes, /api/saved-commands, /api/activity
                                      everyone who has joined, staff's notes on them, the console's saved
                                      commands and the changes with a search (tools/staff_desk.py)
    GET  /api/reports                 the weekly rule checks written; GET /api/report?week=2026-W45 one of them
                                      (tools/staff_report.py; moderators too)
    GET  /api/users                   the staff page's own logins (owners only); POST /api/users adds one, and
                                      /api/users/{role,disable,delete,sessions,link,2fa-off} change one
                                      (tools/staff_auth.py)
    /auth/*                           the login itself, asked with no X-Staff-User (tools/staff_auth.py)

The safety rules, all here rather than in the page:
- Files: every path is relative to LIVE_DIR/server and must stay inside it once links are followed. The worlds, the
  game's own libraries and versions, BlueMap's files and databases (*.db) are refused; logs/ and crash-reports/ are
  read-only. A save checks the file wasn't saved by someone else since it was read, and writes a whole new file.
  Nothing is ever deleted: a file that is replaced, deleted or restored over goes to STAFF_DIR/history first, the newest
  200 kept. A value whose key says password, secret or token is shown as ******** and saved back as it was.
  Only an owner saves, uploads, restores or renames a jar, or anything in mods/ or .fabric/ (asked or reached through
  a link; a rename is checked under its old name and its new one):
  a jar runs as the server, so with it an admin could do anything the server's user can.
- Commands: one line, no `seed` (the seed is secret) and no `stop` (the container would start again at once: the
  power controls stop it). Player commands need a real player name. Log lines and answers are masked as the status
  page's are (tools/staff_status.py): a line that mentions a secret is left out, addresses and links are masked.
- Power: the restart and the stop take the deploy lock (deploy/lib.sh's deploy_lock), so none of them lands during a
  deploy, the daily restart, a timed job or an off-site backup.
- Every change is one line in STAFF_DIR/actions.log (when, who, what, which file or command; never a file's text) and,
  with STAFF_WEBHOOK_URL set, one post to that staff channel. No other webhook is ever used.
- Every program it runs is an argument list, never a shell line, with a time limit.

Reads REPO_DIR, LIVE_DIR, STAFF_DIR, LOCK_FILE and STAFF_WEBHOOK_URL from /etc/monkey-deploy.env (or
MONKEY_DEPLOY_ENV), without running it; the environment wins. Stdlib only (plus tools/), Python 3.10 or newer.
"""
import argparse
import contextlib
import datetime as dt
import errno
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlsplit

import staff_apex
import staff_auth
import staff_desk
import staff_events
import staff_modcfg
import staff_report
import staff_spark
import staff_status

import rcon as server

# Run as `python3 tools/staff_panel.py serve` this module is __main__; staff_auth's late `from staff_panel import ...`
# must get this same module, not a second copy that registers the routes again with its own Refused class.
sys.modules.setdefault("staff_panel", sys.modules[__name__])

PORT = 8130
LOOPBACK = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
USER = re.compile(r"[A-Za-z0-9_-]{1,64}")
PLAYER = re.compile(r"[A-Za-z0-9_]{3,16}")
UPLOAD_NAME = re.compile(r"[A-Za-z0-9._+-]{1,128}")
ENTRY = re.compile(r"\d{8}T\d{6}\.\d{6}Z-[A-Za-z0-9_-]{1,64}")
MASK = "********"
JSON_MAX = 1024 * 1024
SAVE_MAX = 6 * 1024 * 1024          # a 2 MB text file, escaped as JSON
UPLOAD_MAX = 64 * 1024 * 1024
TEXT_MAX = 2 * 1024 * 1024
CONSOLE_FIRST = 256 * 1024           # most of the log is RCON noise, left out, so read back further
CONSOLE_READ = 1024 * 1024
COMMAND_MAX = 1000
HISTORY_KEPT = 200
HISTORY_BYTES = 2 * 1024 * 1024 * 1024
HISTORY_SHOWN = 50
ACTIONS_SHOWN = 100
LIST_MAX = 5000
COMMAND_TIMEOUT = 20
POWER_TIMEOUT = 300                 # compose waits up to 2 minutes (stop_grace_period) for the world to save
RESTART_TIMEOUT = 4000              # the script's 30 minutes for the lock, 5 of warning and 15 for the start
LOCK_WAIT = 10
ACTIONS = ("restart", "restart-now", "stop", "start")
TOP_REFUSED = {"libraries", "versions", "bluemap"}
READ_ONLY = {"logs", "crash-reports"}
# Files that run as the server: only the owner writes them from the file manager (save, upload, restore), like the
# Mods tab's own upload. Deleting stays admin, like removing a mod.
CODE_TOPS = {"mods", ".fabric"}
CODE_ONLY_OWNER = "Only the owner can add or change jars, or files in mods/ (they run as the server)."
# The file the Settings form keeps some keys of (staff_apex.LOCKED: online-mode, RCON, the ports) for the owner.
PROPERTIES = "server.properties"
PROPERTIES_ONLY_OWNER = ("Only the owner can write server.properties here: change the game's settings on the Settings "
                         "page.")
_DATABASE = re.compile(r"\.db(-\w+)?$", re.I)
# level-seed too: the seed is as secret here as in the console.
_SECRET_KEY = re.compile(r"password|secret|token|seed", re.I)
_KEY_LINE = re.compile(r"^(?P<pre>\s*[\"']?)(?P<key>[^\s\"'=:#;\[\]{}]+)(?P<sep>[\"']?\s*[=:]\s*)(?P<rest>.*)$")
# The first word of a command that must not run here, alone or after `execute ... run`.
_REFUSED_COMMAND = re.compile(r"(?:^|\brun\s+)(?:minecraft:)?(seed|stop)\b", re.I)
# A log line's time, thread and level, kept as they are: "[10:00:00]" is no address.
_LOG_HEAD = re.compile(r"^\[\d\d:\d\d:\d\d\] \[[^\]\n]*\](?: \[[^\]\n]*\])?: ")
# The two lines the game logs each time a scheduled job (or this page) connects over RCON from inside the container:
# left out of the console. Whole lines from the RCON threads only, so chat can't hide itself, nor can another address.
_RCON_NOISE = re.compile(r"^\[\d\d:\d\d:\d\d\] \[RCON (?:Listener #\d+|Client /127\.0\.0\.1 #\d+)/INFO\]: "
                         r"Thread RCON Client /127\.0\.0\.1 (?:started|shutting down)\s*$")
# The word must end there: banlist, ban-ip and pardon-ip take no player name.
_PLAYER_VERB = re.compile(r"^(?:minecraft:)?(whitelist\s+(?:add|remove)|op|deop|ban|pardon|kick)(?=\s|$)(?:\s+(\S+))?",
                          re.I)


class Refused(Exception):
    """An answer of `code` with `message`, a plain sentence for the page."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def stamp(when: dt.datetime | None = None) -> str:
    return staff_status.public.iso(when or dt.datetime.now(server.UTC))


def masked(line: str) -> str:
    """A console line fit for the page, masked as the status page masks the log (staff_status's own patterns), but
    whole: the console shows long lines in full."""
    head = _LOG_HEAD.match(line)
    head, said = (head[0], line[head.end():]) if head else ("", line)
    if staff_status._SECRET.search(said):
        return head + staff_status.LEFT_OUT
    said = staff_status._LINK.sub("<link>", said)
    said = staff_status._LONG_NUMBER.sub("<number>", staff_status._ADDRESS.sub("an address", said))
    return "".join(c if c.isprintable() else " " for c in head + said).rstrip()


def lines_of(text: str) -> list[str]:
    """The lines of `text`, split on \\n only: splitlines() also splits on U+2028 and the like, which a player can
    put in chat to make a line that looks like the console's own."""
    if not text:
        return []
    rows = text.split("\n")
    if rows[-1] == "":
        rows.pop()
    return [r[:-1] if r.endswith("\r") else r for r in rows]


def masked_lines(text: str) -> list[str]:
    return [masked(line) for line in lines_of(text)]


def settings_file(path: Path) -> dict[str, str]:
    """KEY=value lines as deploy/lib.sh's setting_in reads them (the last one wins, quotes taken off), never run."""
    found: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return found
    for line in text.splitlines():
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if m:
            value = m[2]
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            found[m[1]] = value
    return found


# ---------------------------------------------------------------- secrets in config files


def _split_value(rest: str) -> tuple[str, str]:
    """(value, what follows it) of a key's line: a quoted value ends at its quote (a JSON line's comma follows)."""
    if rest[:1] in ("'", '"'):
        end = rest.find(rest[0], 1)
        if end > 0:
            return rest[:end + 1], rest[end + 1:]
    value = rest.rstrip()
    return value, rest[len(value):]


def _secret_line(line: str):
    """(prefix, key, value, tail) of a line whose key says password, secret or token and that has a value, else None."""
    if line.lstrip().startswith(("#", ";", "//", "!")):
        return None
    m = _KEY_LINE.match(line)
    if not m or not _SECRET_KEY.search(m["key"]):
        return None
    value, tail = _split_value(m["rest"])
    if value in ("", '""', "''", "{", "[") or value.endswith(("{", "[")):
        return None
    return m["pre"] + m["key"] + m["sep"], m["key"], value, tail


def _is_mask(value: str) -> bool:
    return value in (MASK, f'"{MASK}"', f"'{MASK}'")


def mask_secrets(text: str) -> tuple[str, int]:
    """The text with every secret value shown as ********, and how many there were."""
    out, count = [], 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        found = _secret_line(body)
        if found:
            head, _, value, tail = found
            shown = value[0] + MASK + value[0] if value[0] in "\"'" and len(value) > 1 else MASK
            line = head + shown + tail + line[len(body):]
            count += 1
        out.append(line)
    return "".join(out), count


def unmask_secrets(new: str, old: str) -> str:
    """The new text with each ******** put back as the value the file on disk has for that key (the first ********
    of a key gets its first value). A ******** with nothing to put back is refused rather than saved."""
    kept: dict[str, list[str]] = {}
    for line in old.splitlines():
        found = _secret_line(line)
        if found:
            kept.setdefault(found[1], []).append(found[2])
    out = []
    for line in new.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        found = _secret_line(body)
        if found and _is_mask(found[2]):
            head, key, _, tail = found
            if not kept.get(key):
                raise Refused(400, f"{key} says {MASK} but the file had no value to keep: type the real value.")
            line = head + kept[key].pop(0) + tail + line[len(body):]
        out.append(line)
    return "".join(out)


# ---------------------------------------------------------------- the deploy lock


class FileLock:
    """deploy/lib.sh's deploy_lock as the monkey user takes it: flock on LOCK_FILE, opened for appending."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def take(self, wait: float):
        import fcntl  # not on Windows; the tests give the panel their own lock

        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o664)
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    return None
                time.sleep(0.5)

    def release(self, held) -> None:
        os.close(held)


def spawn_detached(argv: list[str], log: Path) -> int:
    """Starts argv in its own session, its output appended to `log`, and returns its pid. It outlives this process
    (the unit's KillMode=process), so a restart it started finishes even if the panel itself is restarted."""
    with open(log, "ab") as out:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, cwd="/",
                                 start_new_session=True)
    threading.Thread(target=child.wait, daemon=True).start()    # reaped, so it never lingers as a zombie
    return child.pid


def pid_alive(pid: int) -> bool:
    """Whether `pid` is still the restart this panel started (its command line names the deploy script)."""
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False
    return b"monkey-deploy.sh" in cmdline


post_webhook = staff_status.post_webhook     # one line to the staff channel, mentioning nobody


# ---------------------------------------------------------------- the panel


class Panel:
    """Everything the endpoints do, apart from HTTP. `run` is subprocess.run's shape, `spawn(argv, log) -> pid`,
    `alive(pid)`, `lock` has take(wait)/release(held) and `post(url, line)`: the tests replace them all."""

    def __init__(self, live: Path, staff: Path, repo: Path, lock_file: Path = Path("/tmp/monkey-deploy.lock"),
                 webhook: str = "", run=subprocess.run, spawn=spawn_detached, alive=pid_alive, lock=None,
                 post=post_webhook, backup_settings: Path = staff_status.BACKUP_SETTINGS,
                 backup_failing: Path = staff_status.BACKUP_FAILING, auth: staff_auth.Auth | None = None):
        self.live, self.staff, self.repo = Path(live), Path(staff), Path(repo)
        self.root = self.live / "server"
        self.history = self.staff / "history"
        self.webhook, self.run, self.spawn, self.alive, self.post = webhook, run, spawn, alive, post
        self.lock = lock or FileLock(lock_file)
        self.backup_settings, self.backup_failing = backup_settings, backup_failing
        self.docker = server.Docker(self.live / "docker", run=run)
        self._files = threading.Lock()
        self._power = threading.Lock()
        self._busy: dict | None = None
        self._log = threading.Lock()
        self.auth = auth or staff_auth.Auth(self.staff / "auth")

    # ------------------------------------------------ the record of changes

    def record(self, user: str, action: str, target: str = "") -> None:
        """One line in actions.log and, with a webhook, one post. `target` is a path or a masked command."""
        target = "".join(c if c.isprintable() else " " for c in target)[:200]
        line = f"{stamp()} {user} {action} {target}".rstrip()
        with self._log:
            self.staff.mkdir(parents=True, exist_ok=True)
            with open(self.staff / "actions.log", "a", encoding="utf-8") as f:
                f.write(line + "\n")
        if self.webhook:
            threading.Thread(target=self.post, args=(self.webhook, f"Staff page: {user} {action} {target}".rstrip()),
                             daemon=True).start()

    def actions(self) -> dict:
        try:
            with open(self.staff / "actions.log", "rb") as f:
                size = f.seek(0, os.SEEK_END)
                f.seek(max(0, size - 64 * 1024))
                text = f.read().decode("utf-8", "replace")
        except FileNotFoundError:
            text = ""
        rows = []
        for line in text.splitlines()[-ACTIONS_SHOWN:]:
            parts = line.split(" ", 3)
            if len(parts) >= 3:
                rows.append({"time": parts[0], "user": parts[1], "action": parts[2],
                             "target": parts[3] if len(parts) > 3 else ""})
        return {"actions": rows[::-1]}

    # ------------------------------------------------ console and commands

    def console(self, after: str | None) -> dict:
        log = self.root / "logs" / "latest.log"
        try:
            with open(log, "rb") as f:
                size = f.seek(0, os.SEEK_END)
                reset = False
                if after is None or after == "":
                    start, first = max(0, size - CONSOLE_FIRST), True
                else:
                    if not after.isdigit():
                        raise Refused(400, "after must be a whole number.")
                    start, first = int(after), False
                    if start > size:            # a new log: the server starts one each time it starts
                        start, first, reset = max(0, size - CONSOLE_FIRST), True, True
                f.seek(start)
                chunk = f.read(CONSOLE_READ)
        except FileNotFoundError:
            return {"offset": 0, "lines": [], "reset": after not in (None, "", "0")}
        if first and start > 0:                 # started mid-line: skip to the next whole one
            cut = chunk.find(b"\n") + 1
            start, chunk = start + cut, chunk[cut:]
        end = chunk.rfind(b"\n") + 1
        if not end and len(chunk) == CONSOLE_READ:
            end = CONSOLE_READ
        lines = [line for line in lines_of(chunk[:end].decode("utf-8", "replace")) if not _RCON_NOISE.search(line)]
        return {"offset": start + end, "lines": [masked(line) for line in lines], "reset": reset}

    @staticmethod
    def checked_command(command) -> str:
        """The command as it goes to the server, or Refused."""
        if not isinstance(command, str):
            raise Refused(400, "command must be text.")
        if "\n" in command or "\r" in command or "\x00" in command:
            raise Refused(400, "One command at a time: no new lines.")
        command = re.sub(r"^[\s/]+", "", command).rstrip()     # every leading /, so //stop is stop
        if not command:
            raise Refused(400, "Type a command.")
        if len(command) > COMMAND_MAX:
            raise Refused(400, f"A command can be at most {COMMAND_MAX} characters.")
        if any(not c.isprintable() for c in command):
            raise Refused(400, "The command has a control character in it.")
        refused = _REFUSED_COMMAND.search(command)
        if refused and refused[1].lower() == "seed":
            raise Refused(403, "The seed is secret: it is not shown here.")
        if refused:
            raise Refused(403, "Use the Server tab to stop or restart the server: a stop here would start it again.")
        verb = _PLAYER_VERB.match(command)
        if verb and not (verb[2] and PLAYER.fullmatch(verb[2])):
            raise Refused(400, f"{verb[1].lower()} needs a player name: 3 to 16 letters, digits or _.")
        return command

    def command(self, user: str, body: dict) -> dict:
        command = self.checked_command(body.get("command"))
        self.record(user, "command", masked(command))
        try:
            done = self.docker.compose("exec", "-T", "monkey", "monkey", "rcon", command, timeout=COMMAND_TIMEOUT)
        except server.RconError:
            raise Refused(502, "Docker did not answer in time: is the server running?") from None
        output = "\n".join(masked_lines(done.stdout.strip()))
        if done.returncode != 0:
            said = " ".join(masked_lines(done.stderr.strip())[-2:]) or "no answer"
            raise Refused(502, f"The server did not take the command ({said}).")
        return {"output": output, "refused": any(m in done.stdout for m in server.REFUSED)}

    # ------------------------------------------------ power

    def busy(self) -> dict | None:
        """The power action running now, if any, with the restart started before the panel last started included."""
        with self._power:
            return self._busy_locked()

    def _busy_locked(self) -> dict | None:
        if self._busy is None:
            pid_file = self.staff / "power.pid"
            try:
                pid, since = pid_file.read_text(encoding="ascii").split()
                if self.alive(int(pid)):
                    self._busy = {"action": "restart", "since": since, "pid": int(pid)}
            except (OSError, ValueError):
                pass
        if self._busy and "pid" in self._busy and not self.alive(self._busy["pid"]):
            self._busy = None
            with contextlib.suppress(OSError):
                (self.staff / "power.pid").unlink()
        return self._busy

    def power(self) -> dict:
        busy = self.busy()
        box = staff_status.container(self.docker)
        state = box["state"] if box else None
        if busy and busy["action"] in ("restart", "restart-now"):
            shown, since = "restarting", busy["since"]
        elif state == "running":
            shown, since = "running", self.started()
        elif state == "restarting":
            shown, since = "restarting", None
        else:
            shown, since = "stopped", None
        return {"state": shown, "since": since, "busy": busy["action"] if busy else None, "container": box}

    def started(self) -> str | None:
        """When the running container started (UTC, to the second), None when docker didn't say."""
        try:
            done = self.docker.compose("ps", "-q", "monkey", timeout=COMMAND_TIMEOUT)
            box = done.stdout.strip().splitlines()[0] if done.returncode == 0 and done.stdout.strip() else ""
            if not re.fullmatch(r"[0-9a-f]{12,64}", box):
                return None
            done = self.run(["docker", "inspect", "-f", "{{.State.StartedAt}}", box], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=COMMAND_TIMEOUT)
        except (server.RconError, OSError, subprocess.TimeoutExpired):
            return None
        m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", done.stdout.strip()) if done.returncode == 0 else None
        return f"{m[1]}Z" if m else None

    def power_action(self, user: str, body: dict) -> dict:
        action = body.get("action")
        if action not in ACTIONS:
            raise Refused(400, "action must be restart, restart-now, stop or start.")
        with self._power:
            if self._busy_locked():
                raise Refused(409, f"A {self._busy['action']} is already under way: wait for it to finish.")
            since = stamp()
            if action == "restart":
                script = self.repo / "deploy" / "monkey-deploy.sh"
                # RESTART_MIN_UPTIME=0: the daily restart skips a server that started under 6 hours ago; one asked
                # for here should not. (A value in /etc/monkey-deploy.env still wins: the script reads that file.)
                argv = ["env", "RESTART_MIN_UPTIME=0", "timeout", "-k", "60", str(RESTART_TIMEOUT), "sh", str(script),
                        "--restart"]
                self.staff.mkdir(parents=True, exist_ok=True)
                pid = self.spawn(argv, self.staff / "power.log")
                (self.staff / "power.pid").write_text(f"{pid} {since}\n", encoding="ascii")
                self._busy = {"action": action, "since": since, "pid": pid}
                self.record(user, "power", "restart (5-minute warning)")
                return {"started": action}
            self._busy = {"action": action, "since": since}    # claimed: a second one is refused from here on
        # The lock wait (up to LOCK_WAIT) happens outside _power, so GET /api/power doesn't wait on it. Until the
        # thread owns the lock and _busy, any failure gives both back.
        held = None
        try:
            held = self.lock.take(LOCK_WAIT)
            if held is None:
                raise Refused(409, "A deploy, the daily restart, a backup or a timed job has the deploy lock: "
                                   "try again in a few minutes.")
            self.record(user, "power", action)
            args = {"restart-now": ("restart", "monkey"), "stop": ("stop", "monkey"),
                    "start": ("up", "-d", "--no-build", "monkey")}[action]
            threading.Thread(target=self._power_run, args=(user, action, args, held), daemon=True).start()
        except BaseException:
            if held is not None:
                self.lock.release(held)
            with self._power:
                self._busy = None
            raise
        return {"started": action}

    def _power_run(self, user: str, action: str, args: tuple, held) -> None:
        try:
            try:
                done = self.docker.compose(*args, timeout=POWER_TIMEOUT)
                result = "done" if done.returncode == 0 else f"failed (exit {done.returncode})"
            except server.RconError:
                result = "failed (docker did not answer in time)"
            self.record(user, "power-result", f"{action} {result}")
        finally:
            self.lock.release(held)
            with self._power:
                self._busy = None

    def wait_for_power(self, seconds: float = 5) -> None:
        """For the tests: returns once no in-process power action runs."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            with self._power:
                if not self._busy or "pid" in self._busy:
                    return
            time.sleep(0.01)

    # ------------------------------------------------ paths

    @staticmethod
    def _rules(parts: tuple[str, ...]) -> str:
        """'refused', 'read-only' or 'writable' for a path inside the server folder, as its parts."""
        if not parts:
            return "writable"
        top = parts[0].lower()
        if top.startswith("world") or top in TOP_REFUSED or any(_DATABASE.search(p) for p in parts):
            return "refused"
        if top in READ_ONLY:
            return "read-only"
        return "writable"

    @staticmethod
    def holds_code(parts: tuple[str, ...]) -> bool:
        """Whether a path (its parts from the server folder) is a jar, or in a folder the game loads code from."""
        return bool(parts) and (parts[0].lower() in CODE_TOPS or parts[-1].lower().endswith(".jar"))

    def code_guard(self, rel) -> None:
        """Refused unless `rel` (as asked, and the file a link leads to) holds no code and is not server.properties,
        whose locked keys (online-mode, RCON, the ports) the Settings form keeps for the owner. For non-owners'
        writes."""
        if not isinstance(rel, str):
            return                      # resolve() refuses it with its own sentence
        _, real_parts = self.resolve(rel, "write")
        asked = tuple(p for p in PurePosixPath(rel).parts if p != ".")
        if self.holds_code(asked) or self.holds_code(real_parts):
            raise Refused(403, CODE_ONLY_OWNER)
        if any(tuple(p.lower() for p in parts) == (PROPERTIES,) for parts in (asked, real_parts)):
            raise Refused(403, PROPERTIES_ONLY_OWNER)

    def resolve(self, rel, want: str = "read") -> tuple[Path, tuple[str, ...]]:
        """(real path, its parts from the server folder) for `rel`, or Refused. `want` is read or write."""
        if not isinstance(rel, str):
            raise Refused(400, "path must be text.")
        if "\x00" in rel or any(ord(c) < 32 or ord(c) == 127 for c in rel):
            raise Refused(400, "That path has a control character in it.")
        if "\\" in rel or rel.startswith("/") or re.match(r"^[A-Za-z]:", rel) or os.path.isabs(rel):
            raise Refused(400, "Paths are relative to the server folder.")
        parts = tuple(p for p in PurePosixPath(rel).parts if p != ".")
        if ".." in parts:
            raise Refused(400, "A path can't go up a folder (..).")
        root = os.path.realpath(self.root)
        real = os.path.realpath(os.path.join(root, *parts))
        try:
            inside = os.path.commonpath([root, real]) == root
        except ValueError:
            inside = False
        if not inside:
            raise Refused(403, "That path leads outside the server folder.")
        real_parts = tuple(PurePosixPath(Path(os.path.relpath(real, root)).as_posix()).parts) if real != root else ()
        real_parts = tuple(p for p in real_parts if p != ".")
        rules = {self._rules(parts), self._rules(real_parts)}
        if "refused" in rules:
            raise Refused(403, "That file or folder is not open to the staff page (the worlds, the game's own files, "
                               "the map's files and databases).")
        if want == "write" and "read-only" in rules and parts:
            raise Refused(403, "That folder is read-only here.")
        # The real path's parts, so every later rule (read-only, masking) is about the file itself, not a link to it.
        return Path(real), real_parts

    def _entry(self, d: os.DirEntry, parts: tuple[str, ...]) -> dict | None:
        try:
            st = d.stat()
        except OSError:
            return None
        is_dir = stat.S_ISDIR(st.st_mode)
        here = (*parts, d.name)
        rule = self._rules(here)
        root = os.path.realpath(self.root)
        if d.is_symlink():
            real = os.path.realpath(d.path)
            try:
                if os.path.commonpath([root, real]) != root:
                    return None
            except ValueError:
                return None
            rule = max(rule, self._rules(Path(os.path.relpath(real, root)).parts), key=["writable", "read-only",
                                                                                         "refused"].index)
        if rule == "refused":
            if not (len(here) == 1 and here[0].lower().startswith("world")):
                return None
            return {"name": d.name, "dir": is_dir, "size": None, "mtime": st.st_mtime, "writable": False,
                    "locked": True}
        return {"name": d.name, "dir": is_dir, "size": None if is_dir else st.st_size, "mtime": st.st_mtime,
                "writable": rule == "writable"}

    def files(self, rel: str) -> dict:
        path, parts = self.resolve(rel or "")
        if not path.is_dir():
            raise Refused(400, "That is not a folder.")
        rows = []
        with os.scandir(path) as it:
            for d in it:
                if d.name.startswith(".staff-"):
                    continue
                row = self._entry(d, parts)
                if row:
                    rows.append(row)
                if len(rows) >= LIST_MAX:
                    break
        rows.sort(key=lambda r: (not r["dir"], r["name"].lower()))
        return {"path": "/".join(parts), "writable": self._rules(parts) == "writable",
                "entries": rows}

    def _text(self, path: Path) -> tuple[str, os.stat_result]:
        try:
            st = path.stat()
        except FileNotFoundError:
            raise Refused(404, "There is no such file.") from None
        if not stat.S_ISREG(st.st_mode):
            raise Refused(400, "That is not a file.")
        if st.st_size > TEXT_MAX:
            raise Refused(413, "That file is over 2 MB: download it.")
        try:
            return path.read_bytes().decode("utf-8"), st
        except UnicodeDecodeError:
            raise Refused(415, "binary file: download it") from None

    def _shown(self, text: str, parts: tuple[str, ...]) -> tuple[str, int]:
        """The text as staff see it: secret values masked and, in logs/ and crash-reports/, every line masked as the
        console's are (a crash report can hold the seed and players' addresses)."""
        shown, secrets = mask_secrets(text)
        if self._rules(parts) == "read-only":
            shown = "\n".join(masked_lines(shown)) + ("\n" if shown.endswith("\n") else "")
        return shown, secrets

    def read_file(self, rel: str) -> dict:
        path, parts = self.resolve(rel)
        text, st = self._text(path)
        shown, secrets = self._shown(text, parts)
        return {"path": "/".join(parts), "text": shown, "mtime": st.st_mtime, "size": st.st_size,
                "masked": secrets, "writable": self._rules(parts) == "writable"}

    def download(self, rel: str) -> tuple[str, bytes | Path, int]:
        """(file name, bytes or path to stream, size). Text has its secrets masked, as on screen. A file that isn't
        UTF-8 but has no NUL byte is masked too, its other bytes kept as they are; a binary file or one over 2 MB goes
        as it is only when no line in it holds a secret."""
        path, parts = self.resolve(rel)
        try:
            st = path.stat()
        except FileNotFoundError:
            raise Refused(404, "There is no such file.") from None
        if not stat.S_ISREG(st.st_mode):
            raise Refused(400, "That is not a file.")
        if st.st_size <= TEXT_MAX:
            data = path.read_bytes()
            try:
                shown = self._shown(data.decode("utf-8"), parts)[0].encode("utf-8")
            except UnicodeDecodeError:
                if self._rules(parts) == "read-only":       # an old log is .log.gz: it can't be masked as it is
                    raise Refused(415, "Only plain-text logs and crash reports can be downloaded here: they are "
                                       "masked first.") from None
                if b"\x00" not in data:                     # text in another encoding: masked, byte for byte
                    text = data.decode("utf-8", "surrogateescape")
                    shown = mask_secrets(text)[0].encode("utf-8", "surrogateescape")
                elif self._has_secret(path):
                    raise Refused(415, "That file has a secret in it and isn't plain text: it can't be masked, so "
                                       "it can't be downloaded here.") from None
                else:
                    shown = data
            return parts[-1], shown, len(shown)
        if self._rules(parts) == "read-only":
            raise Refused(413, "A log or crash report over 2 MB can't be downloaded here: it isn't masked.")
        if self._has_secret(path):
            raise Refused(413, "That file is over 2 MB and has a secret in it: it can't be masked, so it can't be "
                               "downloaded here.")
        return parts[-1], path, st.st_size

    @staticmethod
    def _has_secret(path: Path) -> bool:
        """Whether any line of the file would be masked, read 1 MB at a time (a longer line is checked in pieces)."""
        rest = b""
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                data = rest + chunk
                cut = data.rfind(b"\n") + 1 if chunk else len(data)
                if chunk and not cut and len(data) >= 1024 * 1024:
                    cut = len(data)
                for line in data[:cut].split(b"\n"):
                    if _secret_line(line.rstrip(b"\r").decode("utf-8", "surrogateescape")):
                        return True
                rest = data[cut:]
                if not chunk:
                    return False

    # ------------------------------------------------ history

    def _new_entry(self, user: str) -> Path:
        now = dt.datetime.now(server.UTC)
        while True:
            entry = self.history / f"{now:%Y%m%dT%H%M%S.%fZ}-{user}"
            try:
                entry.mkdir(parents=True)
                return entry
            except FileExistsError:
                now += dt.timedelta(microseconds=1)

    def _keep(self, path: Path, parts: tuple[str, ...], user: str, move: bool = False) -> str:
        """Copies (or moves) the file at `path` into a new history entry, as history/<entry>/<path>."""
        self.history.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            os.chmod(self.history, 0o700)   # it holds server.properties, password and all
        entry = self._new_entry(user)
        target = entry.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if move:
            shutil.move(str(path), str(target))
        else:
            shutil.copy2(path, target)
        self._prune()
        return entry.name

    def _prune(self) -> None:
        """Keeps the newest HISTORY_KEPT entries, and of those only as many as fit in HISTORY_BYTES (old mod jars add
        up), though always the newest one."""
        entries = sorted(e.name for e in os.scandir(self.history) if e.is_dir() and ENTRY.fullmatch(e.name))
        dropped, kept = entries[:-HISTORY_KEPT], entries[-HISTORY_KEPT:]
        total = 0
        for i, name in enumerate(reversed(kept)):
            for folder, _, names in os.walk(self.history / name):
                total += sum(os.path.getsize(os.path.join(folder, n)) for n in names)
            if i and total > HISTORY_BYTES:
                dropped += kept[:len(kept) - i]
                break
        for name in dropped:
            shutil.rmtree(self.history / name, ignore_errors=True)

    def _entry_file(self, name: str) -> str | None:
        """The one file an entry holds, as a path from the server folder."""
        base = self.history / name
        for folder, _, names in os.walk(base):
            for n in names:
                return Path(os.path.relpath(os.path.join(folder, n), base)).as_posix()
        return None

    def history_list(self) -> dict:
        try:
            names = sorted((e.name for e in os.scandir(self.history) if e.is_dir() and ENTRY.fullmatch(e.name)),
                           reverse=True)[:HISTORY_SHOWN]
        except FileNotFoundError:
            names = []
        rows = []
        for name in names:
            rel = self._entry_file(name)
            if rel is None:
                continue
            when = dt.datetime.strptime(name[:23], "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=server.UTC)
            rows.append({"entry": name, "path": rel, "user": name[24:], "time": stamp(when),
                         "size": (self.history / name / rel).stat().st_size})
        return {"entries": rows}

    # ------------------------------------------------ changes

    def _write(self, path: Path, data: bytes, like: os.stat_result | None) -> os.stat_result:
        """Writes the file whole: a temporary file in the same folder, flushed to disk, renamed over it, with the old
        file's mode and owner."""
        fd, tmp = tempfile.mkstemp(prefix=".staff-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, stat.S_IMODE(like.st_mode) if like else 0o644)
            if like and hasattr(os, "chown"):
                with contextlib.suppress(OSError):
                    os.chown(tmp, like.st_uid, like.st_gid)
            os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
        return path.stat()

    def save(self, user: str, body: dict) -> dict:
        text, mtime = body.get("text"), body.get("mtime")
        if not isinstance(text, str):
            raise Refused(400, "text must be text.")
        if mtime is not None and not isinstance(mtime, int | float):
            raise Refused(400, "mtime must be the number the file was read with.")
        data_len = len(text.encode("utf-8"))
        if data_len > TEXT_MAX:
            raise Refused(413, "A file saved here can be at most 2 MB.")
        path, parts = self.resolve(body.get("path"), "write")
        with self._files:
            try:
                st = path.stat()
            except FileNotFoundError:
                st = None
            if st is None:
                if mtime is not None:
                    raise Refused(409, "The file was deleted since you opened it.")
                if not path.parent.is_dir():
                    raise Refused(404, "There is no such folder.")
                new = text
            else:
                if not stat.S_ISREG(st.st_mode):
                    raise Refused(400, "That is not a file.")
                if mtime is None or st.st_mtime != mtime:
                    raise Refused(409, "Someone else saved this file since you opened it: open it again.")
                old, _ = self._text(path)
                new = unmask_secrets(text, old)
                self._keep(path, parts, user)
            done = self._write(path, new.encode("utf-8"), st)
        self.record(user, "save", "/".join(parts))
        return {"path": "/".join(parts), "mtime": done.st_mtime, "size": done.st_size}

    def upload(self, user: str, query: dict, stream, length: int) -> dict:
        name = query.get("name") or ""
        if not UPLOAD_NAME.fullmatch(name) or name in (".", ".."):
            raise Refused(400, "A file name may have letters, digits, ., _, + and - only.")
        folder, parts = self.resolve(query.get("path") or "", "write")
        if not folder.is_dir():
            raise Refused(400, "Upload into a folder.")
        path, parts = self.resolve("/".join((*parts, name)), "write")
        # The body goes to a temporary file first, outside the files lock: a slow upload holds up no one else.
        fd, tmp = tempfile.mkstemp(prefix=".staff-", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "wb") as f:
                left = length
                while left:
                    chunk = stream.read(min(left, 256 * 1024))
                    if not chunk:
                        raise Refused(400, "The upload stopped part way.")
                    f.write(chunk)
                    left -= len(chunk)
                f.flush()
                os.fsync(f.fileno())
            with self._files:
                st = None
                with contextlib.suppress(FileNotFoundError):
                    st = path.stat()
                if st is not None and not stat.S_ISREG(st.st_mode):
                    raise Refused(400, "A folder has that name.")
                os.chmod(tmp, stat.S_IMODE(st.st_mode) if st else 0o644)
                if st is not None:
                    self._keep(path, parts, user)
                os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
        self.record(user, "upload", "/".join(parts))
        return {"path": "/".join(parts), "size": length, "replaced": st is not None}

    def delete(self, user: str, body: dict) -> dict:
        path, parts = self.resolve(body.get("path"), "write")
        with self._files:
            if path.is_symlink() or not path.is_file():
                raise Refused(400, "Only a file can be deleted here, not a folder.")
            entry = self._keep(path, parts, user, move=True)
        self.record(user, "delete", "/".join(parts))
        return {"path": "/".join(parts), "entry": entry}

    def new_folder(self, user: str, body: dict) -> dict:
        path, parts = self.resolve(body.get("path"), "write")
        if not parts or not UPLOAD_NAME.fullmatch(parts[-1]):
            raise Refused(400, "A folder name may have letters, digits, ., _, + and - only.")
        with self._files:
            if not path.parent.is_dir():
                raise Refused(404, "There is no such folder to make it in.")
            try:
                path.mkdir(mode=0o755)
            except FileExistsError:
                raise Refused(409, "Something already has that name.") from None
        self.record(user, "new-folder", "/".join(parts))
        return {"path": "/".join(parts)}

    def rename(self, user: str, body: dict) -> dict:
        """Gives a file a new name, or moves it to another folder of the server's. Nothing is lost by it, so it keeps
        no copy; a name already taken is refused rather than replaced."""
        if not isinstance(body.get("to"), str) or not UPLOAD_NAME.fullmatch(PurePosixPath(body["to"]).name):
            raise Refused(400, "A file name may have letters, digits, ., _, + and - only.")
        path, parts = self.resolve(body.get("path"), "write")
        target, to_parts = self.resolve(body["to"], "write")
        if not parts or not to_parts:
            raise Refused(400, "Say which file, and its new name.")
        # resolve() follows links, so ask about the name as given: renaming a link would move the file it points to
        # and leave the link pointing at nothing.
        asked = os.path.join(os.path.realpath(self.root), *PurePosixPath(body["path"]).parts)
        with self._files:
            if os.path.islink(asked) or not path.is_file():
                raise Refused(400, "Only a file can be renamed here, not a folder or a link.")
            if not target.parent.is_dir():
                raise Refused(404, "There is no such folder to move it to.")
            # A link to the new name then the old name taken away: link() fails on a name already taken, even one
            # the game made a moment ago, where a rename would quietly replace it.
            try:
                os.link(path, target)
            except FileExistsError:
                raise Refused(409, "Something already has that name.") from None
            except OSError:                 # a file system without hard links: the check, then the rename
                if os.path.lexists(target):
                    raise Refused(409, "Something already has that name.") from None
                os.rename(path, target)
            else:
                os.unlink(path)
        self.record(user, "rename", f"{'/'.join(parts)} to {'/'.join(to_parts)}")
        return {"path": "/".join(to_parts), "from": "/".join(parts)}

    def restore(self, user: str, body: dict) -> dict:
        entry, rel = body.get("entry"), body.get("path")
        if not isinstance(entry, str) or not ENTRY.fullmatch(entry):
            raise Refused(400, "That is not a history entry.")
        path, parts = self.resolve(rel, "write")
        base = os.path.realpath(self.history / entry)
        source = os.path.realpath(os.path.join(base, *parts))
        if (not os.path.isdir(base) or os.path.commonpath([base, source]) != base or os.path.islink(source)
                or not os.path.isfile(source)):
            raise Refused(404, "That history entry has no such file.")
        with self._files:
            st = None
            with contextlib.suppress(FileNotFoundError):
                st = path.stat()
            if st is not None:
                if not stat.S_ISREG(st.st_mode):
                    raise Refused(400, "A folder has that name.")
                self._keep(path, parts, user)
            path.parent.mkdir(parents=True, exist_ok=True)
            done = self._write(path, Path(source).read_bytes(), st)
        self.record(user, "restore", f"{'/'.join(parts)} from {entry}")
        return {"path": "/".join(parts), "mtime": done.st_mtime}

    # ------------------------------------------------ what it only reads

    def players(self) -> dict:
        def names(file: str, reasons: bool = False) -> list | None:
            try:
                rows = json.loads((self.root / file).read_text(encoding="utf-8"))
            except FileNotFoundError:
                return []
            except (OSError, ValueError):
                return None
            if not isinstance(rows, list):
                return None
            rows = sorted((r for r in rows if isinstance(r, dict) and isinstance(r.get("name"), str)),
                          key=lambda r: r["name"].lower())
            if reasons:
                return [{"name": r["name"], "reason": masked(str(r.get("reason") or ""))} for r in rows]
            return [r["name"] for r in rows]

        who = self.who_is_on()
        return {"online": who["names"] if who else None, "whitelist": names("whitelist.json"), "ops": names("ops.json"),
                "banned": names("banned-players.json", reasons=True)}

    def who_is_on(self) -> dict | None:
        """`list` over RCON as {"count", "max", "names"}; None when the server isn't running or doesn't say."""
        box = staff_status.container(self.docker)
        if not (box and box["state"] == "running"):
            return None
        return staff_status.players(staff_status.ask(self.docker, "list"))

    def timers(self) -> dict:
        argv = ["systemctl", "list-timers", "--all", "--no-pager"]
        try:
            done = self.run([*argv, "--output=json"], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            timeout=COMMAND_TIMEOUT)
            if done.returncode == 0:
                return {"timers": timers_from_json(done.stdout)}
            done = self.run([*argv, "--no-legend"], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            timeout=COMMAND_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired):
            raise Refused(502, "systemctl did not answer.") from None
        except ValueError:
            done = None
        if done is None or done.returncode != 0:
            raise Refused(502, "systemctl did not list the timers.")
        return {"timers": timers_from_text(done.stdout)}

    def backups(self) -> dict:
        return {"local": staff_status.last_backup(self.live),
                "offsite": staff_status.offsite(self.backup_settings, self.backup_failing)}


def _usec(value) -> str | None:
    if not isinstance(value, int) or value <= 0:
        return None
    return stamp(dt.datetime.fromtimestamp(value / 1_000_000, server.UTC))


def timers_from_json(text: str) -> list[dict]:
    rows = json.loads(text)
    if not isinstance(rows, list):
        raise ValueError("not a list")
    out = [{"name": r["unit"], "next": _usec(r.get("next")), "last": _usec(r.get("last"))}
           for r in rows if isinstance(r, dict) and isinstance(r.get("unit"), str)
           and re.fullmatch(r"monkey-[\w-]+\.timer", r["unit"])]
    return sorted(out, key=lambda r: r["name"])


_WHEN = r"(?:\w{3} \d{4}-\d\d-\d\d \d\d:\d\d:\d\d \S+|n/a|-)"
_TIMER_TEXT = re.compile(rf"^\s*(?P<next>{_WHEN})\s+.*?\s*(?P<last>{_WHEN})\s+.*?(?P<unit>monkey-[\w-]+\.timer)\b")


def timers_from_text(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        m = _TIMER_TEXT.match(line)
        if m:
            out.append({"name": m["unit"], "next": None if m["next"] in ("n/a", "-") else m["next"],
                        "last": None if m["last"] in ("n/a", "-") else m["last"]})
    return sorted(out, key=lambda r: r["name"])


# ---------------------------------------------------------------- HTTP


ROUTES = {
    ("GET", "/api/console"): lambda p, u, q, b: p.console(q.get("after")),
    ("POST", "/api/command"): lambda p, u, q, b: p.command(u, b),
    ("GET", "/api/power"): lambda p, u, q, b: p.power(),
    ("POST", "/api/power"): lambda p, u, q, b: p.power_action(u, b),
    ("GET", "/api/files"): lambda p, u, q, b: p.files(q.get("path") or ""),
    ("GET", "/api/file"): lambda p, u, q, b: p.read_file(q.get("path") or ""),
    ("PUT", "/api/file"): lambda p, u, q, b: p.save(u, b),
    ("GET", "/api/download"): lambda p, u, q, b: p.download(q.get("path") or ""),
    ("POST", "/api/upload"): None,      # the body is the file: handled apart
    ("POST", "/api/delete"): lambda p, u, q, b: p.delete(u, b),
    ("POST", "/api/folder"): lambda p, u, q, b: p.new_folder(u, b),
    ("POST", "/api/rename"): lambda p, u, q, b: p.rename(u, b),
    ("GET", "/api/history"): lambda p, u, q, b: p.history_list(),
    ("POST", "/api/restore"): lambda p, u, q, b: p.restore(u, b),
    ("GET", "/api/players"): lambda p, u, q, b: p.players(),
    ("GET", "/api/timers"): lambda p, u, q, b: p.timers(),
    ("GET", "/api/backups"): lambda p, u, q, b: p.backups(),
    ("GET", "/api/actions"): lambda p, u, q, b: p.actions(),
}
PATHS = {path for _, path in ROUTES}

# Who may ask what. A role is X-Staff-Role from the login in front of the page, exactly one and a known one: a missing
# role is refused, never taken as owner (a `Connection: X-Staff-Role` makes Caddy drop the copied one). The basic_auth
# logins get owner from deploy/Caddyfile.staff. A request not listed needs admin.
ROLES = ("moderator", "admin", "owner")
NEEDS = {
    ("GET", "/api/me"): "moderator",
    ("GET", "/api/console"): "moderator",
    ("GET", "/api/players"): "moderator",
    ("GET", "/api/power"): "moderator",
    ("GET", "/api/timers"): "moderator",
    ("GET", "/api/backups"): "moderator",
    ("GET", "/api/actions"): "moderator",
}
ROUTES[("GET", "/api/me")] = None     # who is asking: handled apart, from the request
PATHS.add("/api/me")
# The staff page's own logins (tools/staff_auth.py), for owners only; the last owner can't be demoted or removed.
USER_ROUTES = {
    ("GET", "/api/users"): lambda p, u, q, b: p.auth.list_users(),
    ("POST", "/api/users"): lambda p, u, q, b: p.auth.add_user(u, b.get("name"), b.get("role"), b.get("email")),
    ("POST", "/api/users/role"): lambda p, u, q, b: p.auth.set_role(u, b.get("name"), b.get("role")),
    ("POST", "/api/users/disable"): lambda p, u, q, b: p.auth.set_disabled(u, b.get("name"), b.get("disabled")),
    ("POST", "/api/users/delete"): lambda p, u, q, b: p.auth.delete_user(u, b.get("name")),
    ("POST", "/api/users/sessions"): lambda p, u, q, b: p.auth.end_sessions(u, b.get("name")),
    ("POST", "/api/users/link"): lambda p, u, q, b: p.auth.handover_link(u, b.get("name")),
    ("POST", "/api/users/2fa-off"): lambda p, u, q, b: two_step_off(p, u, b.get("name")),
}


def two_step_off(panel, user: str, name) -> dict:
    """An owner turns off someone else's two-step login (a lost phone); it goes in the record of changes."""
    done = panel.auth.two_step_off_for(user, name)
    panel.record(user, "2fa-off", done["name"])
    return done
ROUTES.update(USER_ROUTES)
NEEDS.update(dict.fromkeys(USER_ROUTES, "owner"))
PATHS.update(path for _, path in USER_ROUTES)
SCHEDULER_LOOKS: list = []   # f(panel), each called on the scheduler's thread every 20 s (staff_desk: temp bans' ends)
RAW: dict = {}      # (method, path) -> the most bytes: routes whose body is a file, handed over as (stream, length)
staff_apex.register(sys.modules[__name__])   # settings, game rules, backups, schedules, mods, world, IP bans
staff_desk.register(sys.modules[__name__])    # everyone who has joined, notes, saved commands, the changes searched
staff_events.register(sys.modules[__name__])  # the event timer and the leaderboard update
staff_spark.register(sys.modules[__name__])   # the lag finder: spark's profiler and its report link
staff_modcfg.register(sys.modules[__name__])  # the Mod settings tab: mod config files as forms
staff_report.register(sys.modules[__name__])  # the Reports tab: the weekly rule check


# The file manager's writes that could put code in place: a non-owner's is checked with Panel.code_guard first.
CODE_WRITES = {("PUT", "/api/file"), ("POST", "/api/upload"), ("POST", "/api/restore"), ("POST", "/api/folder"),
               ("POST", "/api/rename")}


def allowed(role: str, need: str) -> bool:
    return ROLES.index(role) >= ROLES.index(need)


class Handler(BaseHTTPRequestHandler):
    server_version = "monkey-panel"
    timeout = 60                        # a request that stalls this long is dropped
    sys_version = ""

    def do_GET(self):
        self.answer("GET")

    def do_POST(self):
        self.answer("POST")

    def do_PUT(self):
        self.answer("PUT")

    def do_DELETE(self):
        self.answer("DELETE")

    def log_message(self, format, *args):     # the request line holds file paths at most; nothing else is logged
        pass

    def send_json(self, code: int, data: dict, headers=()) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def checked(self, method: str) -> tuple[str, str]:
        """The login's name and role, or Refused for a request that must not get in."""
        if self.client_address[0] not in LOOPBACK:
            raise Refused(403, "Only this machine may ask.")
        users = self.headers.get_all("X-Staff-User") or []
        if len(users) != 1 or not USER.fullmatch(users[0]):
            raise Refused(403, "No login name came with the request.")
        roles = self.headers.get_all("X-Staff-Role") or []
        if len(roles) != 1 or roles[0] not in ROLES:
            raise Refused(403, "The login's role is not one this page knows.")
        if method != "GET":
            self.from_the_page()
        return users[0], roles[0]

    def from_the_page(self) -> None:
        if self.headers.get("X-Monkey-Staff") != "1":
            raise Refused(403, "A change must come from the staff page.")
        site = self.headers.get("Sec-Fetch-Site")
        if site is not None and site != "same-origin":
            raise Refused(403, "A change must come from the staff page itself.")

    def length(self, most: int) -> int:
        if self.headers.get("Transfer-Encoding"):
            raise Refused(411, "Send the body with its length.")
        value = self.headers.get("Content-Length")
        if value is None or not value.isdigit():
            raise Refused(411, "Send the body with its length.")
        if int(value) > most:
            raise Refused(413, f"That is too big: at most {most // (1024 * 1024)} MB.")
        return int(value)

    def json_body(self, most: int) -> dict:
        if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
            raise Refused(415, "Send JSON (application/json).")
        size = self.length(most)
        try:
            raw = self.rfile.read(size)
            self.drained = True
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise Refused(400, "That is not JSON.") from None
        if not isinstance(body, dict):
            raise Refused(400, "Send a JSON object.")
        return body

    def drain(self) -> None:
        """Reads and drops a body a refusal left unread (Caddy lets none over 64 MB through), so the page gets the
        refusal rather than a broken connection."""
        value = self.headers.get("Content-Length") or ""
        if self.drained or not value.isdigit() or int(value) > UPLOAD_MAX:
            return
        left = int(value)
        with contextlib.suppress(OSError):
            while left:
                chunk = self.rfile.read(min(left, 256 * 1024))
                if not chunk:
                    break
                left -= len(chunk)

    def answer(self, method: str) -> None:
        panel: Panel = self.server.panel
        self.drained = False
        try:
            url = urlsplit(self.path)
            query = {k: v[0] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
            if url.path.startswith("/auth/"):
                return self.answer_auth(method, url.path)
            user, role = self.checked(method)
            if (method, url.path) not in ROUTES:
                raise Refused(405 if url.path in PATHS else 404, "There is no such request.")
            if not allowed(role, NEEDS.get((method, url.path), "admin")):
                raise Refused(403, "Your login's role can't do that.")
            code_write = role != "owner" and (method, url.path) in CODE_WRITES
            if code_write and url.path == "/api/upload":
                panel.code_guard("/".join(p for p in (query.get("path") or "", query.get("name") or "") if p))
            if url.path == "/api/me":
                result = {"user": user, "role": role}
            elif url.path == "/api/upload":
                ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if ctype != "application/octet-stream":
                    raise Refused(415, "Send the file as application/octet-stream.")
                size = self.length(UPLOAD_MAX)
                result = panel.upload(user, query, self.rfile, size)
                self.drained = True
            elif (method, url.path) in RAW:     # staff_apex's jar and world uploads
                ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if ctype != "application/octet-stream":
                    raise Refused(415, "Send the file as application/octet-stream.")
                raw = staff_apex.Body(self.rfile, self.length(RAW[(method, url.path)]), role)
                try:
                    result = ROUTES[(method, url.path)](panel, user, query, raw)
                finally:
                    self.drained = raw.started      # a body read part way is never read on: the connection closes
            else:
                body = self.json_body(SAVE_MAX if method == "PUT" else JSON_MAX) if method != "GET" else {}
                if code_write:
                    panel.code_guard(body.get("path"))
                    if url.path == "/api/rename":       # a new name can make a file code, or server.properties
                        panel.code_guard(body.get("to"))
                result = ROUTES[(method, url.path)](panel, user, query, body)
            if isinstance(result, tuple):       # a file to hand over: (name, bytes or path, size)
                self.send_download(*result)
            elif hasattr(result, "stream"):     # staff_apex's world zip: it writes its own answer
                result.stream(self)
            else:
                self.send_json(200, {"ok": True, **result})
        except (Refused, staff_auth.AuthError) as e:
            self.close_connection = True
            self.drain()
            self.send_json(e.code, {"ok": False, "error": e.message})
        except Exception as e:      # noqa: BLE001 (one line for the journal; the page gets a plain sentence)
            print(f"monkey-panel: {method} {urlsplit(self.path).path} failed: {type(e).__name__}", file=sys.stderr)
            self.close_connection = True
            with contextlib.suppress(OSError):
                self.send_json(500, {"ok": False, "error": "Something went wrong on the server: see "
                                                           "journalctl -u monkey-panel."})

    def answer_auth(self, method: str, path: str) -> None:
        """The login's own requests (tools/staff_auth.py): from this machine, with no login name to trust yet, and a
        change (a login too) only from the page itself."""
        if self.client_address[0] not in LOOPBACK:
            raise Refused(403, "Only this machine may ask.")
        if method not in ("GET", "POST"):
            raise Refused(405, "There is no such request.")
        if method == "POST":
            self.from_the_page()
        body = self.json_body(staff_auth.BODY_MAX) if method == "POST" else {}
        # Caddy puts the visitor's address last (and ignores one the visitor sent); only Caddy reaches here.
        forwarded = [a.strip() for a in ",".join(self.headers.get_all("X-Forwarded-For") or []).split(",") if a.strip()]
        ip = forwarded[-1][:64] if forwarded else self.client_address[0]
        code, data, headers = self.server.panel.auth.http(method, path, body, self.headers, ip)
        self.send_json(code, data, headers)

    def send_download(self, name: str, data, size: int) -> None:
        safe = re.sub(r"[^A-Za-z0-9._+-]", "_", name) or "file"
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{safe}"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(size))
        self.end_headers()
        if isinstance(data, bytes):
            self.wfile.write(data)
        else:
            with open(data, "rb") as f:
                shutil.copyfileobj(f, self.wfile, 256 * 1024)


class PanelServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, panel: Panel, host: str = "127.0.0.1", port: int = PORT):
        if host not in LOOPBACK:
            raise ValueError("the panel listens on this machine only")
        self.panel = panel
        super().__init__((host, port), Handler)


def from_settings(env: dict | None = None) -> Panel:
    env = os.environ if env is None else env
    file = settings_file(Path(env.get("MONKEY_DEPLOY_ENV") or "/etc/monkey-deploy.env"))

    def setting(name: str, default: str = "") -> str:
        return env.get(name) or file.get(name) or default

    return Panel(live=Path(setting("LIVE_DIR", "/srv/monkey/MonkeySMP-Server")),
                 staff=Path(setting("STAFF_DIR", "/srv/monkey/staff")),
                 repo=Path(setting("REPO_DIR", "/srv/monkey/repo")),
                 lock_file=Path(setting("LOCK_FILE", "/tmp/monkey-deploy.lock")),
                 webhook=setting("STAFF_WEBHOOK_URL"),    # never DISCORD_WEBHOOK_URL: that channel is public
                 auth=staff_auth.from_settings(Path(setting("STAFF_DIR", "/srv/monkey/staff")), env))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("serve", help="listen on 127.0.0.1 (deploy/monkey-panel.service)")
    p.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args(argv)
    panel = from_settings()
    try:
        httpd = PanelServer(panel, "127.0.0.1", args.port)
    except OSError as e:
        print(f"monkey-panel: cannot listen on 127.0.0.1:{args.port}: {errno.errorcode.get(e.errno, e)}",
              file=sys.stderr)
        return 1
    print(f"monkey-panel: listening on 127.0.0.1:{args.port}, files in {panel.root}, history in {panel.history}",
          flush=True)
    staff_apex.start_scheduler(panel)
    with contextlib.suppress(KeyboardInterrupt):
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
