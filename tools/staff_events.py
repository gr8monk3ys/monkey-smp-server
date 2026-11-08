"""The staff page's event controls: event nights, the event timer and a leaderboard update. tools/staff_panel.py
registers them (register()), so they get the same login, role and change checks as every other control. Admins only.

    GET  /api/nights                              the monkey-nights phase (idle, grace, build battle) and time left
    POST /api/nights {"action", ...}              /function monkey:nights/<action> (tools/nights.py): grace/start,
                                                  grace/end, build/start, build/end, stop, minutes {"minutes"} and
                                                  call {"block"}; the state is read before and after
    GET  /api/event-timer                         the running event timer: its name and the minutes left, or none
    POST /api/event-timer {"action": "start", "name", "minutes"}
                                                  /function monkey:events/timer/start (tools/events.py)
    POST /api/event-timer {"action": "finish"}    ends it now with the "Event over" title (timer/finish)
    POST /api/event-timer {"action": "stop"}      cancels it, no "Event over" (timer/stop)
    POST /api/leaderboard                         save-all flush, then `sh deploy/monkey-standings.sh board`: the
                                                  in-game board and the site's standings.json, with Cup points
                                                  given a minute ago

The safety rules:
- The event name and a called-out block are checked here (letters, digits, spaces and a few marks; no quote or
  backslash) and the data packs keep them in storage and show them through an nbt text component, so a name never
  becomes a command.
- Event nights: each step is refused unless the phase allows it (grace/start and build/start only when idle,
  grace/end only in the grace period, build/end only in the build battle), and the phase read back afterwards must be
  the one the step leads to. grace/end runs build/start itself, so it ends in the build battle.
- The functions run over the container's own `monkey rcon`, as the console does. The data pack's own refusals go to
  the command's sender, which RCON doesn't show, so the state is read back before and after every change.
- The leaderboard update takes nothing new: the panel runs as monkey with no PrivateTmp, like the standings timers,
  and the script takes the deploy lock itself. The panel holds the lock through the save (a world download or an
  off-site backup runs save-off under it), so a busy lock answers "skipped" at once; then it gives the lock back for
  the script, whose own "skipping this update" is read too (it waits 60 seconds, then skips). One update at a time.
- Every action is one line in actions.log (staff_panel's record).

Stdlib only, Python 3.10 or newer.
"""
import re
import subprocess
import threading

sp = None   # tools/staff_panel.py (register)

NS = "monkey"
MINUTES = (1, 600)        # tools/events.py's TIMER_MINUTES (tests/test_staff_events.py compares them)
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 '&!?.,:()+#-]{0,39}")
BOARD_TIMEOUT = 150       # the script's 60 seconds for the lock and the board itself
SAVE_TIMEOUT = 60
_SCORE = re.compile(r"has (-?\d+) \[")
_STORED = re.compile(r"contents: \"((?:[^\"\\]|\\.)*)\"\s*$")
SKIPPED = "skipping this update"     # deploy/monkey-standings.sh's line when the lock stays busy
NO_PACK = ("The events data pack doesn't have the event timer: is monkey-events on, and from release 3.2.0 or "
           "later? (/datapack list)")
NO_NIGHTS = "The event nights data pack isn't on: is monkey-nights enabled? (/datapack list)"
_UNSET = "none is set"            # `scoreboard players get` for a holder with no score
_NO_OBJECTIVE = "Unknown scoreboard objective"

# tools/nights.py's phases (#phase nt.state) and steps: the phase a step needs, and the phase it leads to.
PHASES = {0: "idle", 1: "grace", 2: "build"}
STEPS = {
    "grace/start": ({0}, 1),
    "grace/end": ({1}, 2),        # grace/end runs build/start
    "build/start": ({0}, 2),
    "build/end": ({2}, 0),
    "stop": ({1, 2}, 0),
    "minutes": ({1, 2}, None),    # the phase stays; the time left changes
    "call": ({0, 1, 2}, None),    # an announcement only
}
NEEDS_WHAT = {0: "nothing is running", 1: "the grace period is running", 2: "the build battle is running"}


class Events:
    """What these controls keep for one Panel. The tests replace rcon."""

    def __init__(self, panel):
        self.p = panel
        self.rcon = self._rcon
        self._timer = threading.Lock()
        self._nights = threading.Lock()
        self._board = threading.Lock()
        self._name: str | None = None     # the running timer's name, once read

    def _rcon(self, command: str, timeout: int | None = None) -> str:
        """The server's answer to one command; RconError when it didn't take it."""
        done = self.p.docker.compose("exec", "-T", "monkey", "monkey", "rcon", command,
                                     timeout=timeout or sp.COMMAND_TIMEOUT)
        return sp.server.checked(command, done.stdout.strip(), done.returncode, done.stderr)

    def _ask(self, command: str, timeout: int | None = None, missing: str = NO_PACK) -> str:
        try:
            return self.rcon(command, timeout)
        except sp.server.RconError as e:
            said = str(e)
            if "Unknown function" in said:
                raise sp.Refused(409, missing) from None
            if any(m in said for m in sp.server.REFUSED):     # the server answered, and said no
                raise sp.Refused(502, f"The server refused it: {sp.masked(said)[-200:]}") from None
            raise sp.Refused(502, "The server didn't answer: is it running?") from None

    def _score(self, holder: str, objective: str) -> int:
        m = _SCORE.search(self._ask(f"scoreboard players get {holder} {objective}"))
        return int(m[1]) if m else 0

    # ------------------------------------------------ the event timer

    def state(self) -> dict:
        if not self._score("#timer", "ev.state"):
            self._name = None
            return {"running": False}
        seconds = max(0, self._score("#timer", "ev.timer"))
        name = self._name     # read once per run: the page polls every 15 seconds, each read is a docker exec
        if name is None:
            m = _STORED.search(self._ask(f"data get storage {NS}:events timer.name"))
            name = self._name = re.sub(r"\\(.)", r"\1", m[1]) if m else None
        return {"running": True, "name": name, "seconds": seconds, "minutes": (seconds + 59) // 60}

    def timer(self) -> dict:
        return {"timer": self.state()}

    def timer_action(self, user: str, body: dict) -> dict:
        action = body.get("action")
        if action not in ("start", "finish", "stop"):
            raise sp.Refused(400, "action must be start, finish or stop.")
        name, minutes = "", 0
        if action == "start":
            name, minutes = checked_name(body.get("name")), checked_minutes(body.get("minutes"))
        if not self._timer.acquire(blocking=False):
            raise sp.Refused(409, "Another change to the timer is under way: try again in a moment.")
        try:
            running = self.state()["running"]
            if action == "start":
                if running:
                    raise sp.Refused(409, "An event timer is already running: stop or finish it first.")
                command = f'function {NS}:events/timer/start {{name:"{name}",minutes:{minutes}}}'
                self.p.record(user, "event-timer", f"start {name} ({minutes} min)")
            else:
                if not running:
                    raise sp.Refused(409, "No event timer is running.")
                command = f"function {NS}:events/timer/{action}"
                self.p.record(user, "event-timer", action)
            self._ask(command)
            after = self.state()
            if after["running"] != (action == "start"):
                raise sp.Refused(502, f"The server took the command, but the timer didn't {action}. "
                                      "Check the console.")
        finally:
            self._timer.release()
        done = {"timer": after}
        if action != "stop":
            done["note"] = ("Started." if action == "start" else
                            "Event over. Give the Cup points (cup/add), then update the leaderboard.")
        return done

    # ------------------------------------------------ event nights (monkey-nights, tools/nights.py)

    def _night_score(self, holder: str, objective: str) -> int | None:
        """The score, 0 when the holder has none, None when the objective doesn't exist yet (the pack's load step
        hasn't run: an empty server is paused)."""
        said = self._ask(f"scoreboard players get {holder} {objective}", missing=NO_NIGHTS)
        m = _SCORE.search(said)
        if m:
            return int(m[1])
        if _NO_OBJECTIVE in said:
            return None
        if _UNSET in said:
            return 0
        raise sp.Refused(502, f"The server's answer about {objective} wasn't one this page knows: "
                              f"{sp.masked(said)[-200:]}")

    def night_state(self) -> dict:
        phase = self._night_score("#phase", "nt.state")
        if phase is None:
            return {"phase": "idle", "seconds": 0, "minutes": 0, "set_up": False}
        seconds = max(0, self._night_score("#left", "nt.timer") or 0) if phase else 0
        return {"phase": PHASES.get(phase, f"unknown ({phase})"), "seconds": seconds,
                "minutes": (seconds + 59) // 60, "set_up": True}

    def nights(self) -> dict:
        return {"nights": self.night_state()}

    def night_action(self, user: str, body: dict) -> dict:
        action = body.get("action")
        if action not in STEPS:
            raise sp.Refused(400, f"action must be one of {', '.join(STEPS)}.")
        command, detail, minutes = f"function {NS}:nights/{action}", action, 0
        if action == "minutes":
            minutes = checked_minutes(body.get("minutes"))
            command, detail = f"{command} {{minutes:{minutes}}}", f"minutes {minutes}"
        elif action == "call":
            block = checked_name(body.get("block"), "block")
            command, detail = f'{command} {{block:"{block}"}}', f"call {block}"
        allowed, leads_to = STEPS[action]
        if not self._nights.acquire(blocking=False):
            raise sp.Refused(409, "Another event night change is under way: try again in a moment.")
        try:
            before = self.night_state()
            phase = next((k for k, v in PHASES.items() if v == before["phase"]), None)
            if phase not in allowed:
                needs = " or ".join(NEEDS_WHAT[p] for p in sorted(allowed))
                raise sp.Refused(409, f"{action} only works when {needs}; now: {before['phase']}.")
            self.p.record(user, "event-night", f"{detail} (was {describe(before)})")
            self._ask(command, missing=NO_NIGHTS)
            after = self.night_state()
            self.p.record(user, "event-night-result", f"{detail}: now {describe(after)}")
            if leads_to is not None and after["phase"] != PHASES[leads_to]:
                raise sp.Refused(502, f"The server took {action}, but the phase is {after['phase']}, not "
                                      f"{PHASES[leads_to]}. Check the console.")
            # A docker exec per read and a lagging server can let a fair few seconds pass before the read back.
            if action == "minutes" and not minutes * 60 - 30 <= after["seconds"] <= minutes * 60:
                raise sp.Refused(502, f"The server took the new time, but {after['minutes']} min are left. "
                                      "Check the console.")
        finally:
            self._nights.release()
        return {"nights": after, "before": before, "note": NIGHT_NOTES.get(action, "Done.")}

    # ------------------------------------------------ the leaderboard

    def leaderboard(self, user: str) -> dict:
        if not self._board.acquire(blocking=False):
            raise sp.Refused(409, "A leaderboard update is already running.")
        try:
            held = self.p.lock.take(0)
            if held is None:
                self.p.record(user, "leaderboard", "skipped (the deploy lock is busy)")
                raise sp.Refused(409, "Skipped: a deploy or restart is running. Try again in a few minutes.")
            # Held through the save, so it never lands inside a world download or an off-site backup (both run
            # save-off under this lock); given back before the script, which takes it itself.
            try:
                self.p.record(user, "leaderboard", "save-all, then monkey-standings.sh board")
                # flush: the answer comes once the world is on disk, so the board reads the points given just now.
                self._ask("save-all flush", SAVE_TIMEOUT)
            except sp.Refused:
                self.p.record(user, "leaderboard-result", "failed (save-all did not go through)")
                raise
            finally:
                self.p.lock.release(held)
            script = self.p.repo / "deploy" / "monkey-standings.sh"
            argv = ["timeout", "-k", "10", str(BOARD_TIMEOUT - 20), "sh", str(script), "board"]
            try:
                done = self.p.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  timeout=BOARD_TIMEOUT, cwd="/")
            except (OSError, subprocess.TimeoutExpired):
                self.p.record(user, "leaderboard-result", "failed (did not finish)")
                raise sp.Refused(502, "The update didn't finish in time. See journalctl -u monkey-panel.") from None
            said = sp.masked_lines(f"{done.stdout}\n{done.stderr}".strip())
            if done.returncode == 0 and any(SKIPPED in line for line in said):
                self.p.record(user, "leaderboard-result", "skipped (the deploy lock is busy)")
                raise sp.Refused(409, "Skipped: a deploy or restart is running. Try again in a few minutes.")
            if done.returncode != 0:
                self.p.record(user, "leaderboard-result", f"failed (exit {done.returncode})")
                last = said[-1] if said else "no output"
                raise sp.Refused(502, f"The update failed: {last[-300:]}")
            self.p.record(user, "leaderboard-result", "done")
            return {"note": "The leaderboard is up to date."}
        finally:
            self._board.release()


NIGHT_NOTES = {
    "grace/start": "The grace period started: PvP off, Nether closed.",
    "grace/end": "The grace period is over: PvP and the Nether are open, and the build battle started.",
    "build/start": "The build battle started.",
    "build/end": "Building is over. Judge the bases, then give the prizes.",
    "stop": "Stopped. Game rules stay as they are: check pvp and allow_entering_nether_using_portals.",
    "minutes": "Time left changed.",
    "call": "Called out.",
}


def describe(state: dict) -> str:
    if state["phase"] == "idle":
        return "idle" if state.get("set_up", True) else "idle, not set up yet"
    return f"{state['phase']}, {state['minutes']} min left"


def checked_name(value, what: str = "name") -> str:
    if not isinstance(value, str):
        raise sp.Refused(400, f"{what} must be text.")
    value = " ".join(value.split())
    if not NAME.fullmatch(value):
        label = "The event's name" if what == "name" else "The block's name"
        raise sp.Refused(400, f"{label}: 1 to 40 letters, digits, spaces and ' & ! ? . , : ( ) + # -, "
                              "starting with a letter or digit.")
    return value


def checked_minutes(value) -> int:
    low, high = MINUTES
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise sp.Refused(400, f"minutes must be a whole number from {low} to {high}.")
    return value


_events_lock = threading.Lock()


def events(panel) -> Events:
    with _events_lock:
        found = getattr(panel, "_events", None)
        if found is None:
            found = panel._events = Events(panel)
        return found


ROUTES = {
    ("GET", "/api/nights"): lambda p, u, q, b: events(p).nights(),
    ("POST", "/api/nights"): lambda p, u, q, b: events(p).night_action(u, b),
    ("GET", "/api/event-timer"): lambda p, u, q, b: events(p).timer(),
    ("POST", "/api/event-timer"): lambda p, u, q, b: events(p).timer_action(u, b),
    ("POST", "/api/leaderboard"): lambda p, u, q, b: events(p).leaderboard(u),
}
NEEDS = {key: "admin" for key in ROUTES}


def register(module) -> None:
    """Adds these routes to staff_panel's (`module` is staff_panel itself, as it runs)."""
    global sp
    sp = module
    module.ROUTES.update(ROUTES)
    module.NEEDS.update(NEEDS)
    module.PATHS.update(path for _, path in ROUTES)
