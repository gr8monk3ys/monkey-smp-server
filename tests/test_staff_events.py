"""tools/staff_events.py: the event timer and the leaderboard update on the staff page, and deploy/staff/events.js."""
import re
import subprocess
from types import SimpleNamespace

import pytest
import staff_events
import staff_panel
from test_staff_panel import actions, box  # noqa: F401 (box is a fixture)

import events
from rcon import RconError
from repo import REPO


class FakeServer:
    """The data pack's event timer as RCON sees it: the scores, the stored name, and what was sent."""

    def __init__(self):
        self.sent: list[str] = []
        self.running, self.seconds, self.name = 0, 0, None
        self.pack = True
        self.up = True
        self.ignore = False      # the function runs but changes nothing (the pack refused, quietly)

    def __call__(self, command, timeout=None):
        self.sent.append(command)
        if not self.up:
            raise RconError(f"{command} answered: nothing (exit 1)")
        if command == "scoreboard players get #timer ev.state":
            return f"#timer has {self.running} [ev.state]"
        if command == "scoreboard players get #timer ev.timer":
            return f"#timer has {self.seconds} [ev.timer]"
        if command == "data get storage monkey:events timer.name":
            return f'Storage monkey:events has the following contents: "{self.name}"'
        if command.startswith("function "):
            if not self.pack:
                raise RconError(f"{command} answered: Unknown function monkey:events/timer/start (exit 0)")
            if self.ignore:
                return ""
            m = re.fullmatch(r'function monkey:events/timer/start \{name:"(.*)",minutes:(\d+)\}', command)
            if m:
                self.running, self.name, self.seconds = 1, m[1], int(m[2]) * 60
            elif command in ("function monkey:events/timer/stop", "function monkey:events/timer/finish"):
                self.running, self.seconds = 0, 0
            return ""
        if command == "save-all flush":
            if getattr(self, "refuse_save", False):
                raise RconError("save-all flush answered: Incorrect argument for command (exit 0)")
            return "Saved the game"
        raise AssertionError(command)


@pytest.fixture
def ev(box):  # noqa: F811
    fake = FakeServer()
    staff_events.events(box.panel).rcon = fake
    box.server = fake
    box.ran = []
    box.board = SimpleNamespace(returncode=0, stdout="2026-11-07 12:00:00 [standings] board updated\n", stderr="")

    def run(argv, **how):
        box.ran.append((argv, how))
        if isinstance(box.board, BaseException):
            raise box.board
        return box.board

    box.panel.run = run
    return box


# ---------------------------------------------------------------- who may ask


def test_every_route_is_admin_and_registered():
    for key in staff_events.ROUTES:
        assert staff_panel.ROUTES[key] is staff_events.ROUTES[key]
        assert staff_panel.NEEDS[key] == "admin"
        assert key[1] in staff_panel.PATHS


@pytest.mark.parametrize("method,path", sorted(staff_events.ROUTES))
def test_a_moderator_is_refused(ev, method, path):
    code, data = ev.call(method, path, None if method == "GET" else {}, role="moderator")
    assert code == 403 and "role" in data["error"]
    assert ev.server.sent == []


def test_the_page_and_the_data_pack_agree_on_the_minutes():
    assert staff_events.MINUTES == events.TIMER_MINUTES


# ---------------------------------------------------------------- the event timer


def test_start_shows_and_finish_ends_the_timer(ev):
    assert ev.call("GET", "/api/event-timer") == (200, {"ok": True, "timer": {"running": False}})
    code, data = ev.call("POST", "/api/event-timer", {"action": "start", "name": "  Boat   Race ", "minutes": "30"})
    assert code == 200 and data["timer"] == {"running": True, "name": "Boat Race", "seconds": 1800, "minutes": 30}
    assert 'function monkey:events/timer/start {name:"Boat Race",minutes:30}' in ev.server.sent
    assert "event-timer start Boat Race (30 min)" in actions(ev)
    ev.server.seconds = 61
    assert ev.call("GET", "/api/event-timer")[1]["timer"]["minutes"] == 2
    code, data = ev.call("POST", "/api/event-timer", {"action": "finish"})
    assert code == 200 and data["timer"] == {"running": False} and "Cup points" in data["note"]
    assert "function monkey:events/timer/finish" in ev.server.sent and "event-timer finish" in actions(ev)


def test_a_second_start_and_a_stop_with_nothing_running_are_refused(ev):
    code, data = ev.call("POST", "/api/event-timer", {"action": "stop"})
    assert code == 409 and "No event timer" in data["error"]
    assert ev.call("POST", "/api/event-timer", {"action": "start", "name": "Hunt", "minutes": 5})[0] == 200
    code, data = ev.call("POST", "/api/event-timer", {"action": "start", "name": "Other", "minutes": 5})
    assert code == 409 and "already running" in data["error"]
    assert [c for c in ev.server.sent if c.startswith("function")] == [
        'function monkey:events/timer/start {name:"Hunt",minutes:5}']
    code, data = ev.call("POST", "/api/event-timer", {"action": "stop"})
    assert code == 200 and data["timer"] == {"running": False} and "note" not in data
    assert "event-timer stop" in actions(ev)


@pytest.mark.parametrize("body", [
    {"action": "start", "name": 'Boat"} run op x', "minutes": 30},
    {"action": "start", "name": "Back\\slash", "minutes": 30},
    {"action": "start", "name": "", "minutes": 30},
    {"action": "start", "name": "x" * 41, "minutes": 30},
    {"action": "start", "name": "-dash first", "minutes": 30},
    {"action": "start", "name": "Race", "minutes": 0},
    {"action": "start", "name": "Race", "minutes": 601},
    {"action": "start", "name": "Race", "minutes": 2.5},
    {"action": "start", "name": "Race", "minutes": True},
    {"action": "start", "name": "Race"},
    {"action": "start", "name": ["Race"], "minutes": 5},
    {"action": "pause"},
    {},
])
def test_bad_input_sends_nothing(ev, body):
    code, data = ev.call("POST", "/api/event-timer", body)
    assert code == 400 and data["ok"] is False
    assert ev.server.sent == [] and actions(ev) == ""


def test_the_pack_turned_off_or_a_quiet_refusal_is_said_plainly(ev):
    ev.server.pack = False
    code, data = ev.call("POST", "/api/event-timer", {"action": "start", "name": "Race", "minutes": 5})
    assert code == 409 and "monkey-events" in data["error"]
    ev.server.pack, ev.server.ignore = True, True
    code, data = ev.call("POST", "/api/event-timer", {"action": "start", "name": "Race", "minutes": 5})
    assert code == 502 and "didn't start" in data["error"]
    ev.server.up = False
    code, data = ev.call("GET", "/api/event-timer")
    assert code == 502 and "running" in data["error"]


# ---------------------------------------------------------------- the leaderboard


def test_the_leaderboard_saves_first_then_runs_the_board(ev):
    code, data = ev.call("POST", "/api/leaderboard", {})
    assert code == 200 and "up to date" in data["note"]
    assert ev.server.sent == ["save-all flush"]
    (argv, how), = ev.ran
    assert argv[-3:] == ["sh", str(ev.panel.repo / "deploy" / "monkey-standings.sh"), "board"]
    assert argv[0] == "timeout" and how["timeout"] and how["stdin"] == subprocess.DEVNULL and "shell" not in how
    assert ev.lock.held == ev.lock.released == 1      # only checked: the script takes it itself
    log = actions(ev)
    assert "leaderboard save-all" in log and "leaderboard-result done" in log


def test_a_busy_lock_skips_the_leaderboard(ev):
    ev.lock.taken_elsewhere = True
    code, data = ev.call("POST", "/api/leaderboard", {})
    assert code == 409 and data["error"].startswith("Skipped: a deploy or restart is running")
    assert ev.server.sent == [] and ev.ran == [] and "leaderboard skipped" in actions(ev)
    # The lock taken after the check: the script waits, then says so and exits 0.
    ev.lock.taken_elsewhere = False
    ev.board = SimpleNamespace(returncode=0, stderr="",
                               stdout="x [standings] a deploy, restart or backup is running; skipping this update\n")
    code, data = ev.call("POST", "/api/leaderboard", {})
    assert code == 409 and "Skipped" in data["error"] and "leaderboard-result skipped" in actions(ev)


def test_a_failed_leaderboard_says_why(ev):
    ev.board = SimpleNamespace(returncode=1, stdout="", stderr="x [standings] ERROR: no world at /srv/x\n")
    code, data = ev.call("POST", "/api/leaderboard", {})
    assert code == 502 and "no world" in data["error"] and "leaderboard-result failed (exit 1)" in actions(ev)
    ev.board = subprocess.TimeoutExpired(["sh"], 150)
    code, data = ev.call("POST", "/api/leaderboard", {})
    assert code == 502 and "in time" in data["error"]
    ev.server.up = False
    code, data = ev.call("POST", "/api/leaderboard", {})
    assert code == 502 and len(ev.ran) == 2      # no save, no board


# ---------------------------------------------------------------- the page


def test_the_page_has_every_element_events_js_uses():
    page = REPO.root / "deploy" / "staff"
    script = (page / "events.js").read_text(encoding="utf-8")
    html = (page / "index.html").read_text(encoding="utf-8")
    assert '<script src="events.js" defer></script>' in html
    ids = set(re.findall(r'\$\("([a-z0-9-]+)"\)', script))
    assert ids and all(f'id="{i}"' in html for i in ids), ids - set(re.findall(r'id="([a-z0-9-]+)"', html))
    for path in ("/api/event-timer", "/api/leaderboard", "/api/me"):
        assert path in script
    code = "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("//"))
    assert "innerHTML" not in code and not re.search(r"\b(confirm|alert)\(", code)


def test_the_lock_is_held_through_the_save_and_given_back_when_it_fails(ev):
    seen = []
    plain = ev.server

    def watching(command, timeout=None):
        if command == "save-all flush":
            seen.append(ev.lock.held - ev.lock.released)
        return plain(command, timeout)

    staff_events.events(ev.panel).rcon = watching
    assert ev.call("POST", "/api/leaderboard", {})[0] == 200 and seen == [1]
    plain.refuse_save = True
    code, data = ev.call("POST", "/api/leaderboard", {})
    assert code == 502 and data["error"].startswith("The server refused it")
    assert ev.lock.held == ev.lock.released == 2 and len(ev.ran) == 1
    assert "leaderboard-result failed (save-all did not go through)" in actions(ev)


def test_the_name_is_read_once_per_run(ev):
    ev.call("POST", "/api/event-timer", {"action": "start", "name": "Hunt", "minutes": 5})
    for _ in range(3):
        assert ev.call("GET", "/api/event-timer")[1]["timer"]["name"] == "Hunt"
    assert ev.server.sent.count("data get storage monkey:events timer.name") == 1
    ev.call("POST", "/api/event-timer", {"action": "stop"})
    ev.call("POST", "/api/event-timer", {"action": "start", "name": "Race", "minutes": 5})
    assert ev.call("GET", "/api/event-timer")[1]["timer"]["name"] == "Race"


# ---------------------------------------------------------------- event nights (the monkey-nights pack)


class FakeNights:
    """The monkey-nights pack as RCON sees it: #phase nt.state, #left nt.timer, and its functions' effect."""

    def __init__(self):
        self.sent: list[str] = []
        self.phase, self.left = 0, 0
        self.set_up = True       # nt.state exists (the pack's load step has run)
        self.pack = True
        self.ignore = False

    def __call__(self, command, timeout=None):
        self.sent.append(command)
        m = re.fullmatch(r"scoreboard players get (#phase|#left) (nt\.state|nt\.timer)", command)
        if m:
            if not self.set_up:
                return f"Unknown scoreboard objective '{m[2]}'"
            value = self.phase if m[1] == "#phase" else self.left
            return f"{m[1]} has {value} [{m[2]}]" if value or m[1] == "#phase" else \
                f"Can't get value of {m[2]} for {m[1]}; none is set"
        if not command.startswith("function monkey:nights/"):
            raise AssertionError(command)
        if not self.pack:
            raise RconError(f"{command} answered: Unknown function monkey:nights/x (exit 0)")
        self.set_up = True
        if self.ignore:
            return ""
        step = command.split("/", 1)[1]
        if step == "grace/start" and not self.phase:
            self.phase, self.left = 1, 5400
        elif step in ("grace/end", "build/start") and self.phase == (1 if step == "grace/end" else 0):
            self.phase, self.left = 2, 10800
        elif step in ("build/end", "stop") and self.phase:
            self.phase = 0
        elif step.startswith("minutes ") and self.phase:
            self.left = int(re.fullmatch(r"minutes \{minutes:(\d+)\}", step)[1]) * 60
        return ""


@pytest.fixture
def nt(box):  # noqa: F811
    fake = FakeNights()
    staff_events.events(box.panel).rcon = fake
    box.server = fake
    return box


def night(nt, body, role="admin"):
    return nt.call("POST", "/api/nights", body, role=role)


def test_the_nights_state(nt):
    assert nt.call("GET", "/api/nights", role="admin")[1]["nights"] == {
        "phase": "idle", "seconds": 0, "minutes": 0, "set_up": True}
    nt.server.phase, nt.server.left = 2, 61
    assert nt.call("GET", "/api/nights", role="admin")[1]["nights"] == {
        "phase": "build", "seconds": 61, "minutes": 2, "set_up": True}
    nt.server.set_up = False
    assert nt.call("GET", "/api/nights", role="admin")[1]["nights"]["set_up"] is False
    assert nt.call("GET", "/api/nights", role="moderator")[0] == 403


def test_a_whole_night(nt):
    code, data = night(nt, {"action": "grace/start"})
    assert code == 200 and data["nights"]["phase"] == "grace" and data["nights"]["minutes"] == 90
    assert data["before"]["phase"] == "idle" and "grace period started" in data["note"]
    assert night(nt, {"action": "minutes", "minutes": "5"})[1]["nights"]["seconds"] == 300
    assert night(nt, {"action": "grace/end"})[1]["nights"]["phase"] == "build"
    assert night(nt, {"action": "call", "block": "  Oak   Stairs "})[0] == 200
    assert night(nt, {"action": "build/end"})[1]["nights"]["phase"] == "idle"
    assert [c for c in nt.server.sent if c.startswith("function")] == [
        "function monkey:nights/grace/start", "function monkey:nights/minutes {minutes:5}",
        "function monkey:nights/grace/end", 'function monkey:nights/call {block:"Oak Stairs"}',
        "function monkey:nights/build/end"]
    log = actions(nt)
    assert "event-night grace/start (was idle)" in log
    assert "event-night-result grace/start: now grace, 90 min left" in log
    assert "event-night minutes 5 (was grace, 90 min left)" in log and "event-night call Oak Stairs" in log


def test_the_pack_sets_itself_up_on_the_first_step(nt):
    nt.server.set_up = False
    code, data = night(nt, {"action": "build/start"})
    assert code == 200 and data["before"]["set_up"] is False and data["nights"]["phase"] == "build"
    assert "event-night build/start (was idle, not set up yet)" in actions(nt)


@pytest.mark.parametrize("phase, action", [
    (0, "grace/end"), (0, "build/end"), (0, "stop"), (0, "minutes"), (1, "grace/start"), (1, "build/start"),
    (1, "build/end"), (2, "grace/end"), (2, "grace/start")])
def test_a_step_in_the_wrong_phase_is_refused_before_it_runs(nt, phase, action):
    nt.server.phase, nt.server.left = phase, 600
    code, data = night(nt, {"action": action, "minutes": 5})
    assert code == 409 and "only works when" in data["error"]
    assert not any(c.startswith("function") for c in nt.server.sent) and actions(nt) == ""


@pytest.mark.parametrize("body", [
    {"action": "load"}, {"action": "help"}, {}, {"action": "minutes", "minutes": 0},
    {"action": "minutes", "minutes": 601}, {"action": "minutes", "minutes": True}, {"action": "call"},
    {"action": "call", "block": 'a"b'}, {"action": "call", "block": "x}"}, {"action": "call", "block": "a" * 41},
    {"action": "call", "block": " "}])
def test_a_bad_step_is_refused(nt, body):
    nt.server.phase, nt.server.left = 1, 600
    assert night(nt, body)[0] == 400 and nt.server.sent == [] and actions(nt) == ""


def test_without_the_pack(nt):
    nt.server.pack = False
    code, data = night(nt, {"action": "call", "block": "Glass"})
    assert code == 409 and "monkey-nights" in data["error"]


def test_a_step_that_changes_nothing_is_an_error(nt):
    nt.server.ignore = True
    code, data = night(nt, {"action": "grace/start"})
    assert code == 502 and "Check the console" in data["error"]
    assert "event-night-result grace/start: now idle" in actions(nt)
    nt.server.phase, nt.server.left = 1, 600
    code, data = night(nt, {"action": "minutes", "minutes": 3})
    assert code == 502 and "10 min are left" in data["error"]
    nt.server.ignore = False
    real = nt.server

    def late(command, timeout=None):      # the read back comes 20 seconds late: still fine
        return real(command, timeout).replace("has 180 [", "has 160 [")

    staff_events.events(nt.panel).rcon = late
    assert night(nt, {"action": "minutes", "minutes": 3})[0] == 200


def test_one_night_change_at_a_time(nt):
    lock = staff_events.events(nt.panel)._nights
    assert lock.acquire(blocking=False)
    try:
        assert night(nt, {"action": "grace/start"})[0] == 409
    finally:
        lock.release()
    assert nt.server.sent == []


def test_the_page_has_the_nights_box():
    page = REPO.root / "deploy" / "staff"
    script = (page / "events.js").read_text(encoding="utf-8")
    html = (page / "index.html").read_text(encoding="utf-8")
    assert "/api/nights" in script
    for step, needs in staff_events.STEPS.items():
        assert f'"{step}"' in script or f"{step}:" in script
        assert all(staff_events.PHASES[p] in script for p in needs[0])
    for i in re.findall(r'"(nights-[a-z-]+)"', script):
        assert f'id="{i}"' in html, i
