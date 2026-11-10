"""The staff page's lag finder: spark's profiler, started and stopped from the Server tab, and the link to its report.
tools/staff_panel.py registers it (register()), so it gets the same login, role and change checks as every other
control; docs/LIVE.md, "The staff page", says what staff see. spark is one of the release's mods (manifest: spark).

    GET  /api/spark                           the last run: who, when, what kind, until when, and its report link
    POST /api/spark {"mode", "seconds"}       spark profiler start --timeout SECONDS (and the mode's flags)    admin
    POST /api/spark-stop                      spark profiler stop: ends it now, and spark uploads what it has  admin

Modes: "cpu" (what the game spends its time on), "lag" (only ticks over 100 ms: lag spikes) and "memory" (what fills
the memory, --alloc). A run lasts SECONDS (30 to 600) unless stopped.

Where the link comes from: spark answers on its own thread, so the RCON reply is usually empty, but it announces the
result to the console too, which is the server's log. So the page reads the log from where it was when the run
started, for a link of the shape LINK, and keeps the first it finds. A new log (the server restarted) ends the search.
This was written from spark's documentation and not tried on the live server: if no link shows after a run, the
console tab has spark's own words.

The safety rules:
- Only the commands above go to the server, built here from checked values: no text from the page reaches them.
- One run at a time; a second start is refused while one runs. Each start and stop is one line in actions.log.
- Only a link of LINK's shape is taken from the log, so nothing else of a log line (addresses, secrets) reaches the
  page by this road, and never one from a chat line: a player could post a page of their own. A report shows the
  mods, the machine's CPU and memory and the players online, never the seed.

Stdlib only, Python 3.10 or newer.
"""
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path

sp = None   # tools/staff_panel.py (register)

MODES = {"cpu": (), "lag": ("--only-ticks-over", "100"), "memory": ("--alloc",)}
SECONDS = (30, 600)
GRACE = 180                 # seconds after a run's end that the log is still searched: spark uploads, then says
LINK = re.compile(r"https://spark\.lucko\.me/[A-Za-z0-9]{6,32}(?![A-Za-z0-9])")
LOG_READ = 4 * 1024 * 1024  # the most of the log one look reads
# What players say: <Name> text, [Not Secure] <Name> text, and /say's [Name] text. A link there is a player's, not
# spark's, so a player can't hand staff a page of their own as "the report".
_CHAT = re.compile(r"\]: (?:\[Not Secure\] )?(?:<[^>]*>|\[[A-Za-z0-9_]{3,16}\] )")


def log_mark(log: Path) -> tuple[str, int] | None:
    """(a hash of the log's first line, its size): where a run's search starts, and how a new log is told apart."""
    try:
        with open(log, "rb") as f:
            head = hashlib.sha256(f.readline(4096)).hexdigest()[:16]
            return head, f.seek(0, os.SEEK_END)
    except OSError:
        return None


def link_after(log: Path, head: str, offset: int) -> tuple[str | None, bool]:
    """(the first report link written after `offset`, whether the log is still the one the run started in)."""
    mark = log_mark(log)
    if mark is None or mark[0] != head or mark[1] < offset:
        return None, False
    with open(log, "rb") as f:
        f.seek(offset)
        text = f.read(LOG_READ).decode("utf-8", "replace")
    for line in text.splitlines():
        found = LINK.search(line)
        if found and not _CHAT.search(line[:found.start()]):
            return found[0], True
    return None, True


class Spark:
    def __init__(self, panel):
        self.p = panel
        self._lock = threading.Lock()
        self.clock = time.time

    @property
    def state_file(self) -> Path:
        return self.p.staff / "spark.json"

    @property
    def log(self) -> Path:
        return self.p.root / "logs" / "latest.log"

    def _load(self) -> dict | None:
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def _save(self, data: dict) -> None:
        self.p.staff.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_name(".spark.json.tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, self.state_file)

    def installed(self) -> bool:
        """Whether an enabled spark jar is in mods/ (its name starts with spark)."""
        try:
            return any(e.name.lower().startswith("spark") and e.name.lower().endswith(".jar")
                       for e in os.scandir(self.p.root / "mods"))
        except OSError:
            return False

    def _running(self, run: dict | None, now: float) -> bool:
        return bool(run) and not run.get("link") and not run.get("stopped") and now < run.get("ends", 0)

    def status(self) -> dict:
        now = self.clock()
        with self._lock:
            run = self._load()
            if run and not run.get("link") and not run.get("lost") and now < run.get("ends", 0) + GRACE:
                try:
                    link, same = link_after(self.log, str(run.get("head")), int(run.get("offset", 0)))
                except (OSError, ValueError, TypeError):
                    link, same = None, True
                if link or not same:
                    run = {**run, "link": link} if link else {**run, "lost": True}
                    self._save(run)
        shown = {k: run.get(k) for k in ("by", "at", "mode", "seconds", "ends", "link", "stopped", "lost")} \
            if run else None
        waiting = bool(run) and not run.get("link") and not run.get("lost") and now < run.get("ends", 0) + GRACE
        return {"installed": self.installed(), "run": shown, "running": self._running(run, now),
                "waiting": waiting, "now": now}

    def start(self, user: str, body: dict) -> dict:
        mode, seconds = body.get("mode", "cpu"), body.get("seconds")
        if mode not in MODES:
            raise sp.Refused(400, "The kind of run is cpu, lag or memory.")
        low, high = SECONDS
        if not isinstance(seconds, int) or isinstance(seconds, bool) or not low <= seconds <= high:
            raise sp.Refused(400, f"A run lasts {low} to {high} seconds.")
        if not self.installed():
            raise sp.Refused(409, "spark isn't in the server's mods: ask the owner (it is one of the release's mods).")
        now = self.clock()
        with self._lock:
            if self._running(self._load(), now):
                raise sp.Refused(409, "A run is going already: stop it first, or wait for it to end.")
            mark = log_mark(self.log)
            if mark is None:
                raise sp.Refused(409, "The server's log can't be read: is the server running?")
            command = " ".join(("spark", "profiler", "start", "--timeout", str(seconds), *MODES[mode]))
            done = self.p.command(user, {"command": command})
            if done.get("refused"):
                raise sp.Refused(502, "The server didn't take it: is spark loaded? The console tab has its answer.")
            run = {"by": user, "at": sp.stamp(), "mode": mode, "seconds": seconds, "ends": now + seconds,
                   "head": mark[0], "offset": mark[1]}
            self._save(run)
        self.p.record(user, "spark-start", f"{mode}, {seconds} seconds")
        return {"started": True, "ends": run["ends"]}

    def stop(self, user: str) -> dict:
        now = self.clock()
        with self._lock:
            run = self._load()
            if not self._running(run, now):
                raise sp.Refused(409, "No run is going.")
            done = self.p.command(user, {"command": "spark profiler stop"})
            if done.get("refused"):
                raise sp.Refused(502, "The server didn't take it. The console tab has its answer.")
            self._save({**run, "stopped": True, "ends": now})
        self.p.record(user, "spark-stop")
        return {"stopped": True}


_spark_lock = threading.Lock()


def spark(panel) -> Spark:
    with _spark_lock:
        found = getattr(panel, "_spark", None)
        if found is None:
            found = panel._spark = Spark(panel)
        return found


ROUTES = {
    ("GET", "/api/spark"): lambda p, u, q, b: spark(p).status(),
    ("POST", "/api/spark"): lambda p, u, q, b: spark(p).start(u, b),
    ("POST", "/api/spark-stop"): lambda p, u, q, b: spark(p).stop(u),
}
NEEDS = {("GET", "/api/spark"): "moderator", ("POST", "/api/spark"): "admin", ("POST", "/api/spark-stop"): "admin"}


def register(module) -> None:
    """Adds these routes to staff_panel's (`module` is staff_panel itself, as it runs)."""
    global sp
    sp = module
    module.ROUTES.update(ROUTES)
    module.NEEDS.update(NEEDS)
    module.PATHS.update(path for _, path in ROUTES)
