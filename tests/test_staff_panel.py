import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import staff_panel
from test_staff_status import staff  # noqa: F401 (the fixture that runs the real monkey-staff.sh under dash)

from repo import REPO

DEPLOY = REPO.root / "deploy"
PROPERTIES = "motd=Monkey SMP\nrcon.password=hunter2-real\nenable-rcon=true\nlevel-seed=\nmax-players=30\n"
TOML = '[discord]\napi_token = "tok-real"\nchannel = "general"\n'
JSON5 = '{\n  "botSecret": "sec-real",\n  "name": "x"\n}\n'
LIST = "There are 2 of a max of 30 players online: Alpha, Bravo"
PS = json.dumps({"State": "running", "Status": "Up 3 hours (healthy)", "Health": "healthy"})
SECRETS = ("hunter2-real", "tok-real", "sec-real")


class FakeDocker:
    """`docker compose` as the panel runs it: what it was asked, answers from a table, and a gate a test can hold
    shut to keep a power action running."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self.answers = {"list": LIST, "whitelist list": "There are 1 whitelisted player(s): Alpha"}
        self.ps = PS
        self.gate = threading.Event()
        self.gate.set()
        self.kwargs: list[dict] = []

    def __call__(self, argv, **how):
        assert isinstance(argv, list) and "shell" not in how and how.get("timeout")
        self.calls.append(argv)
        self.kwargs.append(how)
        if argv[0] == "systemctl":
            return SimpleNamespace(returncode=1, stdout="", stderr="no systemd here")
        if argv[:2] == ["docker", "inspect"]:
            return SimpleNamespace(returncode=0, stdout="2026-11-06T09:30:00.123456789Z\n", stderr="")
        if "ps" in argv and "-q" in argv:
            return SimpleNamespace(returncode=0, stdout="0123456789abcdef\n", stderr="")
        if "ps" in argv:
            return SimpleNamespace(returncode=0, stdout=self.ps, stderr="")
        if "exec" in argv:
            command = argv[-1]
            if command in self.answers:
                return SimpleNamespace(returncode=0, stdout=self.answers[command], stderr="")
            return SimpleNamespace(returncode=0, stdout="Unknown or incomplete command, see below for error", stderr="")
        self.gate.wait(5)
        return SimpleNamespace(returncode=0, stdout="", stderr="")


class FakeLock:
    def __init__(self):
        self.taken_elsewhere = False
        self.held = 0
        self.released = 0

    def take(self, wait):
        if self.taken_elsewhere:
            return None
        self.held += 1
        return "held"

    def release(self, held):
        assert held == "held"
        self.released += 1


@pytest.fixture
def box(tmp_path):
    live, staff_dir = tmp_path / "live", tmp_path / "staff"
    root = live / "server"
    files = {
        "server.properties": PROPERTIES,
        "config/discord.toml": TOML,
        "config/bot.json5": JSON5,
        "config/plain.yml": "a: 1\n",
        "logs/latest.log": "".join(f"[10:00:{i:02d}] [Server thread/INFO]: line {i}\n" for i in range(5)),
        "crash-reports/crash-1.txt": "Description: boom\n",
        "world/level.dat": "nbt",
        "world_nether/level.dat": "nbt",
        "libraries/lib.jar": "jar",
        "versions/v.jar": "jar",
        "bluemap/web.json": "{}",
        "claims.db": "sqlite",
        "config/mod/store.db": "sqlite",
        "mods/a.jar": "jar",
        "whitelist.json": json.dumps([{"uuid": "u1", "name": "Alpha"}, {"uuid": "u2", "name": "bravo"}]),
        "ops.json": json.dumps([{"uuid": "u1", "name": "Alpha", "level": 4}]),
        "banned-players.json": json.dumps([{"uuid": "u3", "name": "Zed", "reason": "griefing"}]),
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(text.encode())
    (root / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")
    (live / "docker").mkdir()
    (tmp_path / "outside.txt").write_text("outside secret")
    docker, lock, spawned, posted = FakeDocker(), FakeLock(), [], []
    alive: set[int] = set()

    def spawn(argv, log):
        spawned.append(argv)
        alive.add(4242)
        return 4242

    panel = staff_panel.Panel(live, staff_dir, tmp_path / "repo", run=docker, spawn=spawn, alive=alive.__contains__,
                              lock=lock, webhook="https://discord.example/staff",
                              post=lambda u, line: posted.append(line),
                              backup_settings=tmp_path / "nothing", backup_failing=tmp_path / "nothing")
    httpd = staff_panel.PanelServer(panel, "127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, args=(0.05,), daemon=True)
    thread.start()

    def call(method, path, body=None, user="diego", marked=True, ctype=None, headers=None, role="owner"):
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        sent = {} if user is None else {"X-Staff-User": user}
        if role is not None:        # Caddy always sends one; `headers` can replace it
            sent["X-Staff-Role"] = role
        if marked and method != "GET":
            sent["X-Monkey-Staff"] = "1"
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            sent["Content-Type"] = ctype or ("application/octet-stream" if isinstance(body, bytes)
                                             else "application/json")
        sent.update(headers or {})
        conn.request(method, path, body=data, headers=sent)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        if r.getheader("Content-Type", "").startswith("application/json"):
            return r.status, json.loads(raw)
        return r.status, raw

    yield SimpleNamespace(call=call, port=httpd.server_address[1], panel=panel, root=root, staff=staff_dir, live=live,
                          docker=docker, lock=lock, spawned=spawned, posted=posted, alive=alive, tmp=tmp_path)
    httpd.shutdown()
    httpd.server_close()


def history_files(box) -> list[str]:
    base = box.staff / "history"
    if not base.exists():
        return []
    return sorted(Path(os.path.relpath(Path(d) / n, base)).as_posix() for d, _, names in os.walk(base) for n in names)


def actions(box) -> str:
    path = box.staff / "actions.log"
    return path.read_text() if path.exists() else ""


# ---------------------------------------------------------------- who may ask


@pytest.mark.parametrize("user", [None, "", "die go", "diego\u00e9", "a/b", "x" * 65])
def test_a_request_without_a_proper_login_name_is_refused(box, user):
    code, body = box.call("GET", "/api/power", user=user)
    assert code == 403 and body["ok"] is False and "login" in body["error"]


@pytest.mark.parametrize("method, path, body", [
    ("POST", "/api/command", {"command": "list"}),
    ("PUT", "/api/file", {"path": "server.properties", "text": "x", "mtime": 1}),
    ("POST", "/api/delete", {"path": "config/plain.yml"}),
    ("POST", "/api/power", {"action": "stop"}),
    ("POST", "/api/upload?path=config&name=x.txt", b"hi"),
])
def test_a_change_without_the_staff_header_is_refused(box, method, path, body):
    code, answer = box.call(method, path, body, marked=False)
    assert code == 403 and answer["ok"] is False
    assert (box.root / "config" / "plain.yml").exists() and not (box.root / "config" / "x.txt").exists()
    assert box.docker.calls == [] and actions(box) == ""


@pytest.mark.parametrize("site", ["cross-site", "same-site", "none"])
def test_a_change_from_another_site_is_refused(box, site):
    code, answer = box.call("POST", "/api/command", {"command": "list"}, headers={"Sec-Fetch-Site": site})
    assert code == 403 and box.docker.calls == []
    code, _ = box.call("POST", "/api/command", {"command": "list"}, headers={"Sec-Fetch-Site": "same-origin"})
    assert code == 200


def test_json_must_be_json(box):
    code, _ = box.call("POST", "/api/command", b'{"command": "list"}', ctype="text/plain")
    assert code == 415
    code, _ = box.call("POST", "/api/command", b"not json", ctype="application/json")
    assert code == 400
    code, _ = box.call("POST", "/api/command", b"x" * (staff_panel.JSON_MAX + 1), ctype="application/json")
    assert code == 413


def test_unknown_requests_and_methods(box):
    assert box.call("GET", "/api/nothing")[0] == 404
    assert box.call("DELETE", "/api/file")[0] == 405
    assert box.call("GET", "/api/command")[0] == 405


def test_it_listens_on_this_machine_only(box):
    with pytest.raises(ValueError):
        staff_panel.PanelServer(box.panel, "0.0.0.0", 0)


# ---------------------------------------------------------------- console and commands


def test_the_console_gives_new_lines_and_says_when_the_log_was_replaced(box):
    code, first = box.call("GET", "/api/console")
    assert code == 200 and first["lines"][0].endswith("line 0") and len(first["lines"]) == 5 and not first["reset"]
    log = box.root / "logs" / "latest.log"
    with open(log, "a", newline="\n") as f:
        f.write("[10:01:00] [Server thread/INFO]: Alpha joined from 203.0.113.9:5555\n"
                "[10:01:01] [Server thread/INFO]: <Bravo> my password is cheese\n[10:01:02] partial")
    _, more = box.call("GET", f"/api/console?after={first['offset']}")
    assert more["lines"] == ["[10:01:00] [Server thread/INFO]: Alpha joined from an address",
                             "[10:01:01] [Server thread/INFO]: " + staff_panel.staff_status.LEFT_OUT]
    log.write_text("[11:00:00] [main/INFO]: new\n")
    _, fresh = box.call("GET", f"/api/console?after={more['offset']}")
    assert fresh["reset"] is True and fresh["lines"] == ["[11:00:00] [main/INFO]: new"]
    assert box.call("GET", "/api/console?after=-1")[0] == 400


def test_the_console_leaves_out_the_rcon_connection_lines(box):
    log = box.root / "logs" / "latest.log"
    log.write_bytes(b"[08:42:23] [RCON Listener #1/INFO]: Thread RCON Client /127.0.0.1 started\n"
                    b"[08:42:23] [Server thread/INFO]: Alpha joined the game\n"
                    b"[08:42:23] [RCON Client /127.0.0.1 #855/INFO]: Thread RCON Client /127.0.0.1 shutting down\n"
                    b"[08:42:24] [Server thread/INFO]: <Alpha> Thread RCON Client /x started\n"
                    b"[08:42:25] [Server thread/INFO]: <Alpha> rude [RCON Client /127.0.0.1 #1/INFO]: "
                    b"Thread RCON Client /127.0.0.1 started\n"
                    b"[08:42:26] [RCON Listener #1/INFO]: Thread RCON Client /198.51.100.7 started\n")
    _, read = box.call("GET", "/api/console")
    assert read["lines"] == ["[08:42:23] [Server thread/INFO]: Alpha joined the game",
                             "[08:42:24] [Server thread/INFO]: <Alpha> Thread RCON Client /x started",
                             "[08:42:25] [Server thread/INFO]: <Alpha> rude [RCON Client /an address #1/INFO]: "
                             "Thread RCON Client /an address started",
                             "[08:42:26] [RCON Listener #1/INFO]: Thread RCON Client /an address started"]
    assert read["offset"] == log.stat().st_size
    _, whole = box.call("GET", "/api/file?path=logs/latest.log")
    assert "shutting down" in whole["text"]


def test_roles_decide_what_a_login_may_ask(box):
    assert box.call("GET", "/api/me")[1] == {"ok": True, "user": "diego", "role": "owner"}
    mod = {"X-Staff-Role": "moderator"}
    assert box.call("GET", "/api/me", headers=mod)[1]["role"] == "moderator"
    assert box.call("GET", "/api/players", headers=mod)[0] == 200
    assert box.call("GET", "/api/files", headers=mod)[0] == 403
    assert box.call("POST", "/api/command", {"command": "list"}, headers=mod)[0] == 403
    assert box.call("POST", "/api/command", {"command": "list"}, headers={"X-Staff-Role": "admin"})[0] == 200
    assert box.call("GET", "/api/me", headers={"X-Staff-Role": "root"})[0] == 403


def test_a_request_with_no_role_or_two_roles_is_refused(box):
    # A moderator's `Connection: X-Staff-Role` makes Caddy drop the copied role: no role must never mean owner.
    for method, path, body in (("GET", "/api/me", None), ("GET", "/api/files", None),
                               ("POST", "/api/command", {"command": "list"})):
        code, answer = box.call(method, path, body, role=None)
        assert code == 403 and "role" in answer["error"]
    assert box.docker.calls == []
    conn = http.client.HTTPConnection("127.0.0.1", box.port, timeout=10)
    conn.putrequest("GET", "/api/me")
    conn.putheader("X-Staff-User", "diego")
    conn.putheader("X-Staff-Role", "moderator")
    conn.putheader("X-Staff-Role", "owner")
    conn.endheaders()
    assert conn.getresponse().status == 403
    conn.close()


def test_the_panel_run_as_main_is_the_module_staff_auth_imports():
    # As the unit runs it the panel is __main__; staff_auth's late `from staff_panel import` must not load a second
    # copy, which would register the routes again and make every refusal a 500.
    script = (
        "import runpy, sys\n"
        f"sys.path.insert(0, {str(REPO.root / 'tools')!r})\n"
        "sys.argv = ['staff_panel.py', 'no-such-command']\n"
        "try:\n"
        f"    runpy.run_path({str(REPO.root / 'tools' / 'staff_panel.py')!r}, run_name='__main__')\n"
        "except SystemExit:\n"
        "    pass\n"
        "import staff_apex\n"
        "first = staff_apex.sp\n"
        "from staff_panel import settings_file\n"
        "import staff_panel\n"
        "assert staff_apex.sp is first is staff_panel, (staff_apex.sp, first, staff_panel)\n"
        "assert staff_panel.__name__ == '__main__'\n"
        "print('same')\n"
    )
    done = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0 and done.stdout.strip() == "same", done.stderr


def test_the_first_console_read_is_the_end_of_the_log_from_a_line_start(box):
    log = box.root / "logs" / "latest.log"
    log.write_text("".join(f"[10:00:00] [Server thread/INFO]: {i:06d}\n" for i in range(5000)), newline="\n")
    _, first = box.call("GET", "/api/console")
    assert first["offset"] == log.stat().st_size and all(re.search(r"\d{6}$", line) for line in first["lines"])
    assert sum(len(line) + 1 for line in first["lines"]) <= staff_panel.CONSOLE_FIRST


def test_a_command_runs_through_the_containers_rcon_with_a_time_limit(box):
    code, answer = box.call("POST", "/api/command", {"command": "/whitelist list"})
    assert code == 200 and answer["output"] == "There are 1 whitelisted player(s): Alpha"
    argv = box.docker.calls[-1]
    assert argv[0:2] == ["docker", "compose"] and argv[-6:] == ["exec", "-T", "monkey", "monkey", "rcon",
                                                               "whitelist list"]
    assert box.docker.kwargs[-1]["timeout"] == 20 and box.docker.kwargs[-1]["stdin"] == subprocess.DEVNULL
    assert " diego command whitelist list" in actions(box)
    deadline = time.monotonic() + 5
    while not box.posted and time.monotonic() < deadline:
        time.sleep(0.01)
    assert box.posted == ["Staff page: diego command whitelist list"]


def test_an_unknown_command_says_so_without_failing(box):
    code, answer = box.call("POST", "/api/command", {"command": "nonsense"})
    assert code == 200 and answer["refused"] is True


@pytest.mark.parametrize("command", ["seed", "/seed", "minecraft:seed", "execute as @p run seed", "stop", "/stop",
                                     "STOP", "minecraft:stop", "execute run stop", "//stop", "/ /stop", "//seed",
                                     " // stop"])
def test_the_seed_and_stop_are_refused(box, command):
    code, answer = box.call("POST", "/api/command", {"command": command})
    assert code == 403 and answer["ok"] is False and box.docker.calls == []


@pytest.mark.parametrize("command", ["list\nstop", "list\rseed", "say hi\n", "say \x00", "say \x1b[0m", "",
                                     "x" * 1001, 5, None])
def test_one_plain_line_only(box, command):
    code, _ = box.call("POST", "/api/command", {"command": command})
    assert code == 400 and box.docker.calls == []


@pytest.mark.parametrize("command", ["whitelist add @a", "op @p", "ban", "kick ab", "pardon a-b", "deop " + "x" * 17,
                                     "whitelist remove ../x", "//ban @a", "/ /op @p", "minecraft:ban @a"])
def test_player_commands_need_a_player_name(box, command):
    code, answer = box.call("POST", "/api/command", {"command": command})
    assert code == 400 and "player name" in answer["error"] and box.docker.calls == []


def test_good_player_commands_go_through(box):
    for command in ("whitelist add Charlie_1", "op Alpha", "ban Bravo griefing the spawn", "kick Bravo bye"):
        assert box.call("POST", "/api/command", {"command": command})[0] == 200
    assert [argv[-1] for argv in box.docker.calls] == ["whitelist add Charlie_1", "op Alpha",
                                                       "ban Bravo griefing the spawn", "kick Bravo bye"]


def test_commands_that_only_start_like_a_player_command_need_no_name(box):
    for command in ("banlist", "banlist players", "ban-ip 203.0.113.9", "pardon-ip 203.0.113.9", "opx"):
        assert box.call("POST", "/api/command", {"command": command})[0] == 200, command
    assert [argv[-1] for argv in box.docker.calls] == ["banlist", "banlist players", "ban-ip 203.0.113.9",
                                                       "pardon-ip 203.0.113.9", "opx"]


def test_a_player_cannot_forge_a_console_line_with_a_unicode_line_break(box):
    log = box.root / "logs" / "latest.log"
    log.write_bytes("[10:00:00] [Server thread/INFO]: <Bravo> hi\u2028[10:00:01] [Server thread/INFO]: Alpha was "
                    "opped\u0085x\r\n[10:00:02] [Server thread/INFO]: next\n".encode())
    _, read = box.call("GET", "/api/console")
    assert len(read["lines"]) == 2 and read["lines"][1] == "[10:00:02] [Server thread/INFO]: next"
    assert read["lines"][0].startswith("[10:00:00] [Server thread/INFO]: <Bravo> hi ") and "opped x" in read["lines"][0]
    box.docker.answers["list"] = "one\u2028fake\ntwo"
    _, answer = box.call("POST", "/api/command", {"command": "list"})
    assert answer["output"].split("\n") == ["one fake", "two"]
    report = box.root / "crash-reports" / "crash-1.txt"
    report.write_bytes("a\u2028b\r\nc\n".encode())
    _, read = box.call("GET", "/api/file?path=crash-reports/crash-1.txt")
    assert read["text"] == "a b\nc\n"
    assert staff_panel.lines_of("") == [] and staff_panel.lines_of("a\r\nb") == ["a", "b"]


def test_command_output_and_the_record_are_masked(box):
    box.docker.answers["say token abc"] = "token abc"
    code, answer = box.call("POST", "/api/command", {"command": "say token abc"})
    assert code == 200 and answer["output"] == staff_panel.staff_status.LEFT_OUT
    assert "abc" not in actions(box)


# ---------------------------------------------------------------- power


def test_power_says_how_the_server_is(box):
    code, answer = box.call("GET", "/api/power")
    assert code == 200 and answer["state"] == "running" and answer["busy"] is None
    assert answer["since"] == "2026-11-06T09:30:00Z"
    box.docker.ps = json.dumps({"State": "exited", "Status": "Exited (0)"})
    assert box.call("GET", "/api/power")[1]["state"] == "stopped"


def test_restart_runs_the_daily_restart_detached_and_one_at_a_time(box):
    code, answer = box.call("POST", "/api/power", {"action": "restart"})
    assert code == 200 and answer["started"] == "restart"
    argv = box.spawned[0]
    assert argv[-2:] == [str(box.tmp / "repo" / "deploy" / "monkey-deploy.sh"), "--restart"]
    assert "timeout" in argv and "RESTART_MIN_UPTIME=0" in argv
    assert box.call("GET", "/api/power")[1]["state"] == "restarting"
    for action in ACTIONS_ALL:
        code, answer = box.call("POST", "/api/power", {"action": action})
        assert code == 409 and "already under way" in answer["error"]
    assert len(box.spawned) == 1
    box.alive.clear()
    assert box.call("GET", "/api/power")[1]["state"] == "running"
    assert not (box.staff / "power.pid").exists()


ACTIONS_ALL = ("restart", "restart-now", "stop", "start")


def test_a_restart_started_before_the_panel_restarted_still_counts(box):
    box.staff.mkdir(parents=True, exist_ok=True)
    (box.staff / "power.pid").write_text("777 2026-11-06T00:00:00Z\n")
    box.alive.add(777)
    code, answer = box.call("POST", "/api/power", {"action": "stop"})
    assert code == 409


@pytest.mark.parametrize("action, args", [("restart-now", ["restart", "monkey"]), ("stop", ["stop", "monkey"]),
                                          ("start", ["up", "-d", "--no-build", "monkey"])])
def test_the_other_actions_take_the_deploy_lock_and_refuse_a_second(box, action, args):
    box.docker.gate.clear()
    code, _ = box.call("POST", "/api/power", {"action": action})
    assert code == 200 and box.lock.held == 1
    for other in ACTIONS_ALL:
        assert box.call("POST", "/api/power", {"action": other})[0] == 409
    box.docker.gate.set()
    box.panel.wait_for_power()
    assert box.lock.released == 1 and box.docker.calls[-1][-len(args):] == args
    assert f"diego power-result {action} done" in actions(box)
    assert box.spawned == []


def test_a_failure_before_the_power_thread_starts_gives_back_the_lock(box, monkeypatch):
    def broken(*args, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(box.panel, "record", broken)
    with pytest.raises(OSError):
        box.panel.power_action("diego", {"action": "stop"})
    assert box.lock.held == 1 and box.lock.released == 1 and box.panel.busy() is None
    monkeypatch.undo()

    class NoThread:
        def __init__(self, *a, **kw):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")

    monkeypatch.setattr(staff_panel.threading, "Thread", NoThread)
    with pytest.raises(RuntimeError):
        box.panel.power_action("diego", {"action": "start"})
    assert box.lock.held == 2 and box.lock.released == 2 and box.panel.busy() is None


def test_power_answers_while_an_action_waits_for_the_deploy_lock(box):
    waiting, go = threading.Event(), threading.Event()
    take = box.lock.take

    def slow_take(wait):
        waiting.set()
        go.wait(5)
        return take(wait)

    box.lock.take = slow_take
    box.docker.gate.clear()
    started = threading.Thread(target=box.call, args=("POST", "/api/power", {"action": "stop"}))
    started.start()
    assert waiting.wait(5)
    t0 = time.monotonic()
    code, answer = box.call("GET", "/api/power")
    assert code == 200 and answer["busy"] == "stop" and time.monotonic() - t0 < 2
    assert box.call("POST", "/api/power", {"action": "start"})[0] == 409     # claimed while it waits
    go.set()
    started.join(5)
    box.docker.gate.set()
    box.panel.wait_for_power()
    assert box.lock.released == 1 and box.panel.busy() is None


def test_a_held_deploy_lock_is_a_409_and_runs_nothing(box):
    box.lock.taken_elsewhere = True
    code, answer = box.call("POST", "/api/power", {"action": "stop"})
    assert code == 409 and "deploy lock" in answer["error"]
    box.panel.wait_for_power()
    assert not [argv for argv in box.docker.calls if "stop" in argv]
    assert box.panel.busy() is None
    box.lock.taken_elsewhere = False
    assert box.call("POST", "/api/power", {"action": "stop"})[0] == 200
    box.panel.wait_for_power()


def test_an_unknown_power_action_is_refused(box):
    assert box.call("POST", "/api/power", {"action": "kill"})[0] == 400


# ---------------------------------------------------------------- files: what can be reached


@pytest.mark.parametrize("path", ["..", "../outside.txt", "config/../../outside.txt", "/etc/passwd", "\\x",
                                  "C:/x", "config\x00.toml", "a\nb"])
def test_paths_that_leave_the_server_folder_are_refused(box, path):
    from urllib.parse import quote
    for endpoint in ("file", "files", "download"):
        code, answer = box.call("GET", f"/api/{endpoint}?path={quote(path)}")
        assert code in (400, 403), (endpoint, path)
    code, _ = box.call("PUT", "/api/file", {"path": path, "text": "x", "mtime": None})
    assert code in (400, 403)
    assert (box.tmp / "outside.txt").read_text() == "outside secret"


def link(target: Path, at: Path) -> None:
    try:
        os.symlink(target, at, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        pytest.skip("this machine can't make symlinks")


def test_a_link_that_leaves_the_server_folder_is_refused_and_hidden(box):
    link(box.tmp / "outside.txt", box.root / "config" / "out.txt")
    link(box.tmp, box.root / "config" / "up")
    for path in ("config/out.txt", "config/up/outside.txt", "config/up"):
        assert box.call("GET", f"/api/file?path={path}")[0] == 403
        assert box.call("GET", f"/api/download?path={path}")[0] == 403
    assert box.call("PUT", "/api/file", {"path": "config/out.txt", "text": "x", "mtime": None})[0] == 403
    assert box.call("POST", "/api/delete", {"path": "config/out.txt"})[0] == 403
    names = [e["name"] for e in box.call("GET", "/api/files?path=config")[1]["entries"]]
    assert "out.txt" not in names and "up" not in names
    assert (box.tmp / "outside.txt").read_text() == "outside secret"


def test_a_link_inside_to_a_refused_file_is_refused(box):
    link(box.root / "world" / "level.dat", box.root / "config" / "level.dat")
    assert box.call("GET", "/api/file?path=config/level.dat")[0] == 403


@pytest.mark.parametrize("path", ["world/level.dat", "world", "world_nether/level.dat", "libraries/lib.jar",
                                  "versions/v.jar", "bluemap/web.json", "claims.db", "config/mod/store.db"])
def test_the_worlds_the_games_files_and_databases_are_refused(box, path):
    assert box.call("GET", f"/api/file?path={path}")[0] == 403
    assert box.call("GET", f"/api/download?path={path}")[0] == 403
    assert box.call("POST", "/api/delete", {"path": path})[0] == 403
    assert (box.root / path).exists()


def test_the_listing_hides_what_is_refused_and_names_the_worlds(box):
    code, answer = box.call("GET", "/api/files?path=")
    assert code == 200 and answer["path"] == ""
    rows = {e["name"]: e for e in answer["entries"]}
    assert "libraries" not in rows and "versions" not in rows and "bluemap" not in rows and "claims.db" not in rows
    assert rows["world"]["locked"] is True and rows["world"]["writable"] is False
    assert rows["logs"]["writable"] is False and rows["config"]["writable"] is True
    assert rows["server.properties"]["writable"] is True and rows["server.properties"]["size"] == len(PROPERTIES)
    names = [e["name"] for e in answer["entries"]]
    dirs = [e["name"] for e in answer["entries"] if e["dir"]]
    assert names[:len(dirs)] == dirs
    assert "store.db" not in [e["name"] for e in box.call("GET", "/api/files?path=config/mod")[1]["entries"]]
    assert box.call("GET", "/api/files?path=world")[0] == 403


@pytest.mark.parametrize("path", ["logs/latest.log", "crash-reports/crash-1.txt"])
def test_logs_and_crash_reports_are_read_only(box, path):
    code, answer = box.call("GET", f"/api/file?path={path}")
    assert code == 200 and answer["writable"] is False
    before = (box.root / path).read_bytes()
    assert box.call("PUT", "/api/file", {"path": path, "text": "x", "mtime": answer["mtime"]})[0] == 403
    assert box.call("POST", "/api/delete", {"path": path})[0] == 403
    assert box.call("POST", f"/api/upload?path={path.split('/')[0]}&name=x.txt", b"x")[0] == 403
    assert (box.root / path).read_bytes() == before and history_files(box) == []


def test_a_download_is_masked_even_when_it_is_not_utf8_or_is_big(box):
    # Latin-1 text: masked, every other byte kept.
    (box.root / "server.properties").write_bytes(b"motd=Caf\xe9\nrcon.password=hunter2-real\n")
    code, raw = box.call("GET", "/api/download?path=server.properties")
    assert code == 200 and raw == b"motd=Caf\xe9\nrcon.password=********\n"
    # Binary with a secret line: can't be masked safely, refused.
    (box.root / "config" / "blob.bin").write_bytes(b"\x00\xff\npassword=hunter2-real\n")
    code, answer = box.call("GET", "/api/download?path=config/blob.bin")
    assert code == 415 and b"hunter2" not in json.dumps(answer).encode()
    (box.root / "config" / "clean.bin").write_bytes(b"\x00\xff\x01")
    assert box.call("GET", "/api/download?path=config/clean.bin")[1] == b"\x00\xff\x01"
    # Over 2 MB: goes as it is only with no secret in it.
    big = box.root / "config" / "big.txt"
    big.write_bytes(b"x" * (staff_panel.TEXT_MAX + 10) + b"\napi_token = hunter2-real\n")
    code, answer = box.call("GET", "/api/download?path=config/big.txt")
    assert code == 413 and answer["ok"] is False
    big.write_bytes(b"y\n" * (staff_panel.TEXT_MAX // 2 + 10))
    code, raw = box.call("GET", "/api/download?path=config/big.txt")
    assert code == 200 and raw == big.read_bytes()


def test_a_binary_file_is_for_download(box):
    code, answer = box.call("GET", "/api/file?path=icon.png")
    assert code == 415 and answer["error"] == "binary file: download it"
    code, raw = box.call("GET", "/api/download?path=icon.png")
    assert code == 200 and raw == (box.root / "icon.png").read_bytes()


# ---------------------------------------------------------------- files: changes


def test_secrets_are_masked_on_read_and_download_and_kept_on_save(box):
    for path in ("server.properties", "config/discord.toml", "config/bot.json5"):
        code, answer = box.call("GET", f"/api/file?path={path}")
        assert code == 200 and answer["masked"] == 1 and not any(s in answer["text"] for s in SECRETS)
        _, raw = box.call("GET", f"/api/download?path={path}")
        assert not any(s.encode() in raw for s in SECRETS) and staff_panel.MASK.encode() in raw
    _, read = box.call("GET", "/api/file?path=server.properties")
    assert "rcon.password=********\n" in read["text"] and "level-seed=\n" in read["text"]
    edited = read["text"].replace("max-players=30", "max-players=40")
    code, saved = box.call("PUT", "/api/file", {"path": "server.properties", "text": edited, "mtime": read["mtime"]})
    assert code == 200
    assert (box.root / "server.properties").read_text() == PROPERTIES.replace("max-players=30", "max-players=40")
    _, toml = box.call("GET", "/api/file?path=config/discord.toml")
    assert 'api_token = "********"' in toml["text"]
    box.call("PUT", "/api/file", {"path": "config/discord.toml", "text": toml["text"], "mtime": toml["mtime"]})
    assert (box.root / "config" / "discord.toml").read_text() == TOML
    _, js = box.call("GET", "/api/file?path=config/bot.json5")
    box.call("PUT", "/api/file", {"path": "config/bot.json5", "text": js["text"], "mtime": js["mtime"]})
    assert (box.root / "config" / "bot.json5").read_text() == JSON5
    assert not any(s in actions(box) for s in SECRETS)


def test_the_seed_is_masked_in_files_and_kept_on_save(box):
    path = box.root / "server.properties"
    path.write_bytes(PROPERTIES.replace("level-seed=", "level-seed=-4172144997902289642").encode())
    _, read = box.call("GET", "/api/file?path=server.properties")
    assert "level-seed=********\n" in read["text"] and "4172144997902289642" not in read["text"]
    _, raw = box.call("GET", "/api/download?path=server.properties")
    assert b"4172144997902289642" not in raw
    box.call("PUT", "/api/file", {"path": "server.properties", "text": read["text"], "mtime": read["mtime"]})
    assert "level-seed=-4172144997902289642\n" in path.read_text()


def test_crash_reports_and_logs_are_masked_like_the_console(box):
    report = box.root / "crash-reports" / "crash-1.txt"
    report.write_text("Description: boom\n\tSeed: -4172144997902289642\n\tPlayer at 203.0.113.9:51234\nok line\n")
    _, read = box.call("GET", "/api/file?path=crash-reports/crash-1.txt")
    assert "4172144997902289642" not in read["text"] and "203.0.113.9" not in read["text"]
    assert "ok line" in read["text"] and "Description: boom" in read["text"]
    _, raw = box.call("GET", "/api/download?path=crash-reports/crash-1.txt")
    assert b"4172144997902289642" not in raw and b"203.0.113.9" not in raw
    (box.root / "logs" / "2026-11-05-1.log.gz").write_bytes(b"\x1f\x8b\x08\x00\xff\xfe-4172144997902289642")
    code, raw = box.call("GET", "/api/download?path=logs/2026-11-05-1.log.gz")
    assert code == 415 and b"4172144997902289642" not in json.dumps(raw).encode()


def test_a_link_to_a_log_is_masked_and_read_only_like_the_log(box):
    (box.root / "crash-reports" / "crash-1.txt").write_bytes(b"Seed: -4172144997902289642\n")
    (box.root / "config" / "alias.txt").symlink_to(box.root / "crash-reports" / "crash-1.txt")
    _, read = box.call("GET", "/api/file?path=config/alias.txt")
    assert "4172144997902289642" not in read["text"] and read["writable"] is False
    _, raw = box.call("GET", "/api/download?path=config/alias.txt")
    assert b"4172144997902289642" not in raw
    code, _ = box.call("PUT", "/api/file", {"path": "config/alias.txt", "text": "x", "mtime": read["mtime"]})
    assert code == 403


def test_the_history_stays_within_its_size(box, monkeypatch):
    monkeypatch.setattr(staff_panel, "HISTORY_BYTES", 10)
    box.call("PUT", "/api/file", {"path": "config/big.txt", "text": "x" * 8, "mtime": None})
    for i in range(3):
        _, read = box.call("GET", "/api/file?path=config/big.txt")
        box.call("PUT", "/api/file", {"path": "config/big.txt", "text": str(i) * 8, "mtime": read["mtime"]})
    files = history_files(box)
    assert len(files) == 1 and (box.staff / "history" / files[0]).read_text() == "1" * 8


def test_a_new_secret_can_be_typed_and_a_mask_with_nothing_behind_it_is_refused(box):
    _, read = box.call("GET", "/api/file?path=server.properties")
    text = read["text"].replace("rcon.password=********", "rcon.password=new-one")
    box.call("PUT", "/api/file", {"path": "server.properties", "text": text, "mtime": read["mtime"]})
    assert "rcon.password=new-one\n" in (box.root / "server.properties").read_text()
    _, read = box.call("GET", "/api/file?path=config/plain.yml")
    code, answer = box.call("PUT", "/api/file", {"path": "config/plain.yml", "text": "password: ********\n",
                                                 "mtime": read["mtime"]})
    assert code == 400 and "real value" in answer["error"]
    assert (box.root / "config" / "plain.yml").read_text() == "a: 1\n"


def test_a_save_over_someone_elses_is_a_409(box):
    _, read = box.call("GET", "/api/file?path=config/plain.yml")
    path = box.root / "config" / "plain.yml"
    path.write_text("a: 2\n")
    os.utime(path, (read["mtime"] + 5, read["mtime"] + 5))
    code, answer = box.call("PUT", "/api/file", {"path": "config/plain.yml", "text": "a: 3\n", "mtime": read["mtime"]})
    assert code == 409 and "Someone else saved" in answer["error"]
    assert path.read_text() == "a: 2\n" and history_files(box) == []
    assert box.call("PUT", "/api/file", {"path": "config/plain.yml", "text": "a: 3\n", "mtime": None})[0] == 409


def test_a_save_keeps_the_old_file_in_the_history_and_its_mode(box):
    path = box.root / "config" / "plain.yml"
    os.chmod(path, 0o640)
    mode = os.stat(path).st_mode & 0o777
    _, read = box.call("GET", "/api/file?path=config/plain.yml")
    code, saved = box.call("PUT", "/api/file", {"path": "config/plain.yml", "text": "a: 2\n", "mtime": read["mtime"]})
    assert code == 200 and path.read_text() == "a: 2\n" and saved["mtime"] == path.stat().st_mtime
    assert os.stat(path).st_mode & 0o777 == mode
    files = history_files(box)
    assert len(files) == 1 and re.fullmatch(r"\d{8}T\d{6}\.\d{6}Z-diego/config/plain\.yml", files[0])
    assert (box.staff / "history" / files[0]).read_text() == "a: 1\n"
    assert re.search(r"^\S+Z diego save config/plain\.yml$", actions(box), re.M)
    assert not [p for p in (box.root / "config").iterdir() if p.name.startswith(".staff-")]


def test_a_new_file_can_be_saved_and_the_history_keeps_200(box, monkeypatch):
    monkeypatch.setattr(staff_panel, "HISTORY_KEPT", 3)
    assert box.call("PUT", "/api/file", {"path": "config/new.txt", "text": "0", "mtime": None})[0] == 200
    for i in range(5):
        _, read = box.call("GET", "/api/file?path=config/new.txt")
        box.call("PUT", "/api/file", {"path": "config/new.txt", "text": str(i + 1), "mtime": read["mtime"]})
    files = history_files(box)
    assert len(files) == 3 and [(box.staff / "history" / f).read_text() for f in files] == ["2", "3", "4"]


def test_delete_moves_the_file_to_the_history_and_only_files(box):
    code, answer = box.call("POST", "/api/delete", {"path": "mods/a.jar"})
    assert code == 200 and not (box.root / "mods" / "a.jar").exists()
    files = history_files(box)
    assert files == [f"{answer['entry']}/mods/a.jar"] and (box.staff / "history" / files[0]).read_text() == "jar"
    assert box.call("POST", "/api/delete", {"path": "config"})[0] == 400
    assert box.call("POST", "/api/delete", {"path": "mods/none.jar"})[0] == 400


def test_an_upload_reads_its_body_before_taking_the_files_lock(box):
    class Body:
        def __init__(self):
            self.locked = []

        def read(self, n):
            self.locked.append(box.panel._files.locked())
            return b"" if len(self.locked) > 1 else b"abc"

    body = Body()
    done = box.panel.upload("diego", {"path": "config", "name": "u.txt"}, body, 3)
    assert done["size"] == 3 and body.locked == [False] and (box.root / "config" / "u.txt").read_bytes() == b"abc"
    with pytest.raises(staff_panel.Refused):
        box.panel.upload("diego", {"path": "config", "name": "v.txt"}, Body(), 10)     # stops part way
    assert not (box.root / "config" / "v.txt").exists()
    assert not [p for p in (box.root / "config").iterdir() if p.name.startswith(".staff-")]


def test_upload_adds_or_replaces_a_file_keeping_the_old_one(box):
    code, answer = box.call("POST", "/api/upload?path=mods&name=b.jar", b"new jar")
    assert code == 200 and answer["replaced"] is False and (box.root / "mods" / "b.jar").read_bytes() == b"new jar"
    code, answer = box.call("POST", "/api/upload?path=mods&name=a.jar", b"jar 2")
    assert code == 200 and answer["replaced"] is True and (box.root / "mods" / "a.jar").read_bytes() == b"jar 2"
    assert [f.split("/", 1)[1] for f in history_files(box)] == ["mods/a.jar"]
    assert box.call("POST", "/api/upload?path=&name=server-icon.png", b"png")[0] == 200


def test_only_the_owner_adds_or_changes_jars_or_files_in_mods(box):
    admin = {"X-Staff-Role": "admin"}
    # A jar runs as the server, so the file manager keeps jars, mods/ and .fabric/ for the owner.
    for query in ("path=mods&name=b.jar", "path=config&name=x.jar", "path=&name=evil.JAR", "path=mods&name=x.txt"):
        code, answer = box.call("POST", f"/api/upload?{query}", b"jar", headers=admin)
        assert code == 403 and "owner" in answer["error"], query
    for path in ("mods/a.jar", "mods/notes.txt", ".fabric/x.txt", "config/x.jar", "./mods/a.jar"):
        code, answer = box.call("PUT", "/api/file", {"path": path, "text": "x", "mtime": None}, headers=admin)
        assert code == 403 and "owner" in answer["error"], path
    assert (box.root / "mods" / "a.jar").read_bytes() != b"x"
    # The owner still can, and an admin still saves and restores everything else.
    assert box.call("POST", "/api/upload?path=mods&name=a.jar", b"jar 2")[0] == 200
    entry = box.call("GET", "/api/history")[1]["entries"][0]
    assert entry["path"] == "mods/a.jar"
    code, answer = box.call("POST", "/api/restore", {"entry": entry["entry"], "path": "mods/a.jar"}, headers=admin)
    assert code == 403 and (box.root / "mods" / "a.jar").read_bytes() == b"jar 2"
    assert box.call("POST", "/api/restore", {"entry": entry["entry"], "path": "mods/a.jar"})[0] == 200
    _, read = box.call("GET", "/api/file?path=config/plain.yml")
    assert box.call("PUT", "/api/file", {"path": "config/plain.yml", "text": "a: 2\n", "mtime": read["mtime"]},
                    headers=admin)[0] == 200
    assert box.call("POST", "/api/upload?path=config&name=x.txt", b"x", headers=admin)[0] == 200


def test_an_admin_cannot_reach_mods_through_a_link(box):
    link(box.root / "mods", box.root / "config" / "m")
    code, answer = box.call("POST", "/api/upload?path=config/m&name=x.txt", b"x", headers={"X-Staff-Role": "admin"})
    assert code == 403 and not (box.root / "mods" / "x.txt").exists()
    code, _ = box.call("PUT", "/api/file", {"path": "config/m/new.txt", "text": "x", "mtime": None},
                       headers={"X-Staff-Role": "admin"})
    assert code == 403 and not (box.root / "mods" / "new.txt").exists()


@pytest.mark.parametrize("query", ["path=mods&name=../x.jar", "path=mods&name=a b.jar", "path=mods&name=",
                                   "path=..&name=x.jar", "path=mods&name=..", "path=mods/a.jar&name=x.jar",
                                   "path=world&name=x.jar", "path=mods&name=x.db"])
def test_bad_uploads_are_refused(box, query):
    code, _ = box.call("POST", f"/api/upload?{query.replace(' ', '%20')}", b"data")
    assert code in (400, 403)
    assert sorted(p.name for p in (box.root / "mods").iterdir()) == ["a.jar"]


def test_an_upload_must_be_raw_bytes_of_a_known_length(box):
    assert box.call("POST", "/api/upload?path=mods&name=b.jar", b"x", ctype="application/json")[0] == 415


def test_restore_puts_a_copy_back_and_keeps_the_current_one(box):
    _, read = box.call("GET", "/api/file?path=config/plain.yml")
    box.call("PUT", "/api/file", {"path": "config/plain.yml", "text": "a: 2\n", "mtime": read["mtime"]})
    _, history = box.call("GET", "/api/history")
    entry = history["entries"][0]
    assert entry["path"] == "config/plain.yml" and entry["user"] == "diego"
    code, _ = box.call("POST", "/api/restore", {"entry": entry["entry"], "path": "config/plain.yml"})
    assert code == 200 and (box.root / "config" / "plain.yml").read_text() == "a: 1\n"
    contents = sorted((box.staff / "history" / f).read_text() for f in history_files(box))
    assert contents == ["a: 1\n", "a: 2\n"]
    for bad in ({"entry": "../x", "path": "config/plain.yml"}, {"entry": entry["entry"], "path": "../outside.txt"},
                {"entry": entry["entry"], "path": "server.properties"}):
        assert box.call("POST", "/api/restore", bad)[0] in (400, 403, 404)


def test_a_deleted_file_can_be_restored(box):
    _, answer = box.call("POST", "/api/delete", {"path": "config/plain.yml"})
    assert box.call("POST", "/api/restore", {"entry": answer["entry"], "path": "config/plain.yml"})[0] == 200
    assert (box.root / "config" / "plain.yml").read_text() == "a: 1\n"


# ---------------------------------------------------------------- what it only reads


def test_players_lists_and_who_is_online(box):
    code, answer = box.call("GET", "/api/players")
    assert code == 200 and answer == {"ok": True, "online": ["Alpha", "Bravo"], "whitelist": ["Alpha", "bravo"],
                                      "ops": ["Alpha"], "banned": [{"name": "Zed", "reason": "griefing"}]}
    box.docker.ps = json.dumps({"State": "exited", "Status": "Exited (0)"})
    assert box.call("GET", "/api/players")[1]["online"] is None


def test_timers_from_systemctls_json_and_text():
    rows = staff_panel.timers_from_json(json.dumps([
        {"next": int(staff_panel.server.parse_time("2026-11-15T02:00:00Z").timestamp()) * 1_000_000, "left": 1,
         "last": 0, "passed": None, "unit": "monkey-day.timer", "activates": "monkey-day.service"},
        {"next": 1, "last": 1, "unit": "apt-daily.timer"}]))
    assert rows == [{"name": "monkey-day.timer", "next": "2026-11-15T02:00:00Z", "last": None}]
    text = ("Sat 2026-11-07 04:00:00 PST 15h left Fri 2026-11-06 04:00:00 PST 8h ago monkey-restart.timer "
            "monkey-restart.service\n"
            "n/a n/a n/a n/a monkey-border.timer monkey-border.service\n"
            "Sat 2026-11-07 06:00:00 PST 17h left - - apt-daily.timer apt-daily.service\n")
    assert staff_panel.timers_from_text(text) == [
        {"name": "monkey-border.timer", "next": None, "last": None},
        {"name": "monkey-restart.timer", "next": "Sat 2026-11-07 04:00:00 PST", "last": "Fri 2026-11-06 04:00:00 PST"}]


def test_timers_without_systemd_is_a_plain_error(box):
    code, answer = box.call("GET", "/api/timers")
    assert code == 502 and answer["ok"] is False


def test_backups_and_the_record_of_changes(box):
    code, answer = box.call("GET", "/api/backups")
    assert code == 200 and answer["local"] is None and answer["offsite"] == "not set up"
    box.call("POST", "/api/delete", {"path": "config/plain.yml"})
    box.call("POST", "/api/command", {"command": "list"}, user="lorenzo")
    rows = box.call("GET", "/api/actions")[1]["actions"]
    assert [(r["user"], r["action"], r["target"]) for r in rows] == [("lorenzo", "command", "list"),
                                                                     ("diego", "delete", "config/plain.yml")]


def test_settings_are_read_never_run_and_the_public_webhook_is_never_used(tmp_path):
    env = tmp_path / "deploy.env"
    env.write_text('LIVE_DIR="/srv/x"\nDISCORD_WEBHOOK_URL=https://public\nSTAFF_DIR=/srv/s\nLIVE_DIR=/srv/y\n'
                   "REPO_DIR=$(touch /tmp/pwned)\n")
    panel = staff_panel.from_settings({"MONKEY_DEPLOY_ENV": str(env)})
    assert panel.live == Path("/srv/y") and panel.staff == Path("/srv/s") and panel.webhook == ""
    assert str(panel.repo) == str(Path("$(touch /tmp/pwned)"))


def test_no_shell_anywhere_and_every_program_has_a_time_limit():
    source = (REPO.root / "tools" / "staff_panel.py").read_text(encoding="utf-8")
    assert "shell=True" not in source and "os.system" not in source and "os.popen" not in source
    for call in re.findall(r"self\.run\(\[[^\n]*\n?[^\n]*", source):
        assert "timeout=" in call


# ---------------------------------------------------------------- the unit and the install


def test_the_unit_runs_the_panel_as_monkey_and_lets_a_restart_finish():
    unit = (DEPLOY / "monkey-panel.service").read_bytes()
    assert unit.isascii() and b"\r" not in unit
    text = unit.decode()
    assert "User=monkey" in text and "Restart=on-failure" in text and "KillMode=process" in text
    assert "MemoryMax=512M" in text and "Nice=10" in text
    assert "ExecStart=/usr/bin/python3 -B /srv/monkey/repo/tools/staff_panel.py serve\n" in text
    # The deploy lock lives in /tmp: a private /tmp would be another lock.
    assert "PrivateTmp=" not in text


def test_caddy_sends_only_api_to_the_panel_after_the_password_with_the_login_name():
    caddy = (DEPLOY / "Caddyfile.staff").read_text()
    assert caddy.index("basic_auth") < caddy.index("handle /api/*")
    assert "reverse_proxy 127.0.0.1:8130" in caddy and "header_up X-Staff-User {http.auth.user.id}" in caddy
    assert "max_size 64MiB" in caddy and "max_size 64MB" not in caddy        # the panel's 64 * 1024 * 1024
    # Every /api/ request is an owner's (the password box has no roles), set after the hop-by-hop headers go.
    for block in re.findall(r"handle /api/[^{]*\{.*?\n\t\}", caddy, re.S):
        assert "header_up X-Staff-Role owner" in block and "header_up -X-Staff-Role" not in block
    login = (DEPLOY / "Caddyfile.staff-login").read_text()
    assert "max_size 64MiB" in login and "max_size 64MB" not in login


def test_install_starts_the_panel_and_check_reports_it():
    text = (DEPLOY / "monkey-staff.sh").read_text()
    assert "monkey-panel.service" in text and "systemctl enable --now monkey-panel.service" in text
    if shutil.which("dash"):
        subprocess.run([shutil.which("dash"), "-n", str(DEPLOY / "monkey-staff.sh")], check=True)


def test_install_copies_and_starts_the_controls_and_check_says_how_they_are(staff):  # noqa: F811
    staff.run("--login", "diego")
    done = staff.run("--install")
    assert done.code == 0
    assert any(line.startswith("install -m 644 -o root -g root ") and line.endswith("/etc/systemd/system/"
                                                                                    "monkey-panel.service")
               for line in done.calls)
    assert "systemctl enable --now monkey-panel.service" in done.calls
    # Only once the site refuses a visit with no password.
    assert done.calls.index("systemctl enable --now monkey-panel.service") > done.calls.index("systemctl reload caddy")
    done = staff.run("--check")
    assert done.code == 0 and "controls: monkey-panel.service" in done.out
    assert "the controls answer a request with no login" in done.out
    assert "systemctl enable --now monkey-panel.service" not in done.calls


def test_the_controls_never_start_when_the_site_lets_a_visit_in(staff):  # noqa: F811
    staff.run("--login", "diego")
    done = staff.run("--install", FAKE_CODE="200")
    assert done.code == 1 and "systemctl enable --now monkey-panel.service" not in done.calls
