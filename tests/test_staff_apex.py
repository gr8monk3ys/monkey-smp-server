"""The staff page's hosting controls: tools/staff_apex.py, deploy/monkey-staff-helper.sh and the Server tab
(staff-ui/src/tabs/server)."""
import datetime as dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import staff_apex
import staff_panel
from test_staff_panel import box  # noqa: F401 (the panel behind a real HTTP server, docker and the lock faked)

from repo import REPO

DEPLOY = REPO.root / "deploy"
PROPERTIES = ("#Minecraft server properties\n"
              "motd=\\u00a7aMonkey SMP\n"
              "rcon.password=hunter2-real\n"
              "rcon.port=25575\n"
              "enable-rcon=true\n"
              "level-seed=s33d-real\n"
              "level-name=world\n"
              "server-port=25565\n"
              "max-players=30\n"
              "difficulty=normal\n"
              "pvp=true\n"
              "view-distance=10\n"
              "some-mod-key=hello\n")


@pytest.fixture
def apex(box, tmp_path):  # noqa: F811 (box is the imported fixture)
    (box.root / "server.properties").write_text(PROPERTIES, newline="\n")
    x = staff_apex.extras(box.panel)
    x.results = tmp_path / "results"
    x.results.mkdir()
    x.unit = tmp_path / "monkey-staff-helper.path"
    x.sleep = lambda seconds: None
    box.x = x
    return box


def installed(b):
    b.x.unit.write_text("[Path]\n")
    b.x.requests.mkdir(parents=True, exist_ok=True)


def actions(b) -> str:
    path = b.staff / "actions.log"
    return path.read_text() if path.exists() else ""


def as_role(role):
    return {"X-Staff-Role": role}


# ---------------------------------------------------------------- who may ask


def test_every_route_names_who_may_use_it():
    for key in staff_apex.ROUTES:
        assert key in staff_apex.NEEDS and key in staff_panel.NEEDS and key in staff_panel.ROUTES
        assert staff_panel.NEEDS[key] in staff_panel.ROLES
    assert set(staff_apex.NEEDS) == set(staff_apex.ROUTES)
    # The two that hand over the whole world, or replace it, are owners' only.
    assert staff_apex.NEEDS[("POST", "/api/world-restore")] == "owner"
    assert staff_apex.NEEDS[("GET", "/api/world-download")] == "owner"
    assert staff_apex.NEEDS[("POST", "/api/world-download")] == "owner"


@pytest.mark.parametrize("method,path,role", [
    ("GET", "/api/settings", "moderator"), ("GET", "/api/gamerules", "moderator"),
    ("POST", "/api/world-restore", "admin"), ("POST", "/api/world-download", "admin"),
    ("GET", "/api/ip-bans", "moderator"), ("POST", "/api/schedules", "moderator"),
])
def test_a_role_below_the_need_is_refused(apex, method, path, role):
    code, body = apex.call(method, path, {} if method != "GET" else None, headers=as_role(role))
    assert code == 403 and "role" in body["error"]


def test_moderators_may_look_at_the_mods_and_the_helper(apex):
    assert apex.call("GET", "/api/mods", headers=as_role("moderator"))[0] == 200
    assert apex.call("GET", "/api/helper", headers=as_role("moderator"))[0] == 200


# ---------------------------------------------------------------- settings


def test_escaping_round_trips_the_way_java_writes_it():
    for text in ("\u00a7aMonkey SMP", "back\\slash", " leading space", "emoji \U0001F412", "plain"):
        assert staff_apex.unescape(staff_apex.escape(text)) == text
    assert staff_apex.escape("\u00a7a") == "\\u00a7a"
    assert staff_apex.unescape("\\u00a7aHi\\:there") == "\u00a7aHi:there"


def test_the_settings_form_shows_typed_fields_and_hides_secrets(apex):
    code, data = apex.call("GET", "/api/settings")
    assert code == 200
    fields = {f["key"]: f for f in data["fields"]}
    assert fields["max-players"]["type"] == "int" and fields["max-players"]["value"] == "30"
    assert fields["difficulty"]["type"] == "enum" and "hard" in fields["difficulty"]["choices"]
    assert fields["pvp"]["type"] == "bool" and fields["motd"]["value"] == "\u00a7aMonkey SMP"
    assert set(data["groups"]) == {"Gameplay", "World", "Players", "Network"}
    other = {r["key"]: r for r in data["other"]}
    # The locked and unknown keys are shown, never editable, and a secret never shows.
    assert {"rcon.password", "rcon.port", "enable-rcon", "level-seed", "level-name", "server-port",
            "some-mod-key"} <= set(other)
    assert other["rcon.password"]["value"] == staff_panel.MASK and other["level-seed"]["value"] == staff_panel.MASK
    assert "hunter2-real" not in json.dumps(data) and "s33d-real" not in json.dumps(data)


def test_a_settings_save_changes_only_those_keys_and_keeps_the_secrets(apex):
    _, data = apex.call("GET", "/api/settings")
    code, done = apex.call("PUT", "/api/settings", {"values": {"max-players": 40, "motd": "\u00a7bHello \u00e9",
                                                                "pvp": False, "difficulty": "hard"},
                                                     "mtime": data["mtime"]})
    assert code == 200 and set(done["changed"]) == {"max-players", "motd", "pvp", "difficulty"}
    text = (apex.root / "server.properties").read_text()
    assert "max-players=40\n" in text and "motd=\\u00a7bHello \\u00e9\n" in text and "pvp=false\n" in text
    assert "rcon.password=hunter2-real\n" in text and "level-seed=s33d-real\n" in text
    assert "some-mod-key=hello\n" in text and text.startswith("#Minecraft server properties\n")
    # Through the panel's own save: the old file is in the history, and the log says who.
    assert any("server.properties" in str(p) for p in (apex.staff / "history").rglob("*"))
    log = actions(apex)
    assert "diego save server.properties" in log and "diego settings" in log and "hunter2" not in log
    # A second save with the old time is refused: someone saved since.
    code, body = apex.call("PUT", "/api/settings", {"values": {"max-players": 41}, "mtime": data["mtime"]})
    assert code == 409


def test_values_sent_back_unchanged_keep_their_lines_byte_for_byte(apex):
    text = ("#Minecraft server properties\n# odd\x0c commentâ€¨ here\n"
            "motd=line one\\nline two\r\n"
            "pvp=TRUE\n"
            "max-players=30\n"
            "difficulty=normal")           # no newline at the end
    (apex.root / "server.properties").write_bytes(text.encode("utf-8"))
    _, data = apex.call("GET", "/api/settings")
    fields = {f["key"]: f["value"] for f in data["fields"]}
    assert fields["pvp"] == "TRUE" and "\n" in fields["motd"]
    sent = {k: fields[k] for k in ("motd", "pvp", "difficulty")}
    code, done = apex.call("PUT", "/api/settings", {"values": {**sent, "max-players": 40}, "mtime": data["mtime"]})
    assert code == 200 and done["changed"] == ["max-players"]
    assert (apex.root / "server.properties").read_bytes() == text.replace("max-players=30", "max-players=40").encode()
    # Nothing changed at all: the file is not written again.
    _, data = apex.call("GET", "/api/settings")
    code, done = apex.call("PUT", "/api/settings", {"values": sent, "mtime": data["mtime"]})
    assert code == 200 and done["changed"] == []


@pytest.mark.parametrize("values,code", [
    ({"rcon.password": "x"}, 403), ({"rcon.port": 1}, 403), ({"enable-rcon": False}, 403),
    ({"level-seed": "1"}, 403), ({"level-name": "other"}, 403), ({"server-port": 1}, 403),
    ({"some-mod-key": "x"}, 403), ({"query.port": 1}, 403), ({"online-mode": False}, 403),
    ({"max-players": 0}, 400), ({"max-players": "lots"}, 400), ({"max-players": True}, 400),
    ({"difficulty": "nightmare"}, 400), ({"pvp": "yes"}, 400), ({"motd": "a\nrcon.password=x"}, 400),
    ({"view-distance": 99}, 400), ({"hardcore": True}, 400),    # hardcore is a known key not in this file
])
def test_a_settings_save_refuses_locked_unknown_and_bad_values(apex, values, code):
    _, data = apex.call("GET", "/api/settings")
    before = (apex.root / "server.properties").read_text()
    got, body = apex.call("PUT", "/api/settings", {"values": values, "mtime": data["mtime"]})
    assert got == code and body["ok"] is False
    assert (apex.root / "server.properties").read_text() == before


# ---------------------------------------------------------------- game rules


@pytest.mark.parametrize("name,value", [
    ("keep_inventory", "true; stop"), ("keep_inventory", "yes"), ("keep_inventory", 1),
    ("keep_inventory true\nstop", True), ("stop", True), ("doFireTick", True), (None, True),
    ("random_tick_speed", 11), ("random_tick_speed", -1), ("random_tick_speed", "3 stop"),
    ("players_sleeping_percentage", True), ("players_sleeping_percentage", 3.5),
])
def test_a_game_rule_takes_only_a_known_name_and_a_value_of_its_type(apex, name, value):
    code, body = apex.call("POST", "/api/gamerules", {"name": name, "value": value})
    assert code == 400 and body["ok"] is False
    assert not [c for c in apex.docker.calls if "exec" in c]


def test_a_game_rule_is_set_with_exactly_that_command(apex):
    apex.docker.answers["gamerule keep_inventory true"] = "Gamerule keep_inventory is now set to: true"
    apex.docker.answers["gamerule random_tick_speed 5"] = "Gamerule random_tick_speed is now set to: 5"
    assert apex.call("POST", "/api/gamerules", {"name": "keep_inventory", "value": True})[1]["value"] is True
    assert apex.call("POST", "/api/gamerules", {"name": "random_tick_speed", "value": "5"})[1]["value"] == 5
    sent = [c[-1] for c in apex.docker.calls if "exec" in c]
    assert sent == ["gamerule keep_inventory true", "gamerule random_tick_speed 5"]
    assert "diego gamerule keep_inventory true" in actions(apex)


def test_the_game_rules_are_read_and_a_missing_one_is_marked(apex):
    apex.docker.answers["gamerule keep_inventory"] = "Gamerule keep_inventory is currently set to: false"
    apex.docker.answers["gamerule random_tick_speed"] = "Gamerule random_tick_speed is currently set to: 3"
    code, data = apex.call("GET", "/api/gamerules")
    assert code == 200
    rules = {r["name"]: r for r in data["rules"]}
    assert rules["keep_inventory"]["value"] is False and not rules["keep_inventory"]["missing"]
    assert rules["random_tick_speed"]["value"] == 3
    assert rules["spawn_wardens"]["missing"] and rules["spawn_wardens"]["value"] is None
    asked = {c[-1] for c in apex.docker.calls if "exec" in c}
    assert asked == {f"gamerule {n}" for n in staff_apex.GAMERULES}


def test_game_rules_need_a_running_server(apex):
    apex.docker.ps = json.dumps({"State": "exited", "Status": "Exited (0)", "Health": ""})
    assert apex.call("GET", "/api/gamerules")[0] == 502


# ---------------------------------------------------------------- the backup helper, from the panel's side


def test_without_the_helper_the_page_says_so(apex):
    code, data = apex.call("GET", "/api/helper")
    assert code == 200 and data["installed"] is False
    code, body = apex.call("POST", "/api/backup-now", {})
    assert code == 503 and "--install-helper" in body["error"]


def test_a_request_holds_only_fixed_words(apex):
    installed(apex)
    code, done = apex.call("POST", "/api/backup-now", {})
    assert code == 200 and staff_apex.REQUEST_ID.fullmatch(done["request"])
    files = list(apex.x.requests.iterdir())
    assert [f.name for f in files] == [f"{done['request']}.req"]
    assert files[0].read_text() == "action=backup-now\nuser=diego\n"
    assert "diego backup-now" in actions(apex)
    # A full queue is refused rather than piling up.
    for _ in range(staff_apex.HELPER_PENDING_MAX - 1):
        assert apex.call("POST", "/api/snapshots", {})[0] == 200
    assert apex.call("POST", "/api/snapshots", {})[0] == 409


def write_result(b, rid, **data):
    (b.x.results / f"{rid}.json").write_text(json.dumps(data))


SNAPS = [{"id": "a" * 64, "time": "2026-11-05T10:00:00Z", "tags": ["world"], "summary": {"total_bytes_processed": 9}},
         {"id": "b" * 64, "time": "2026-11-06T10:00:00Z", "tags": ["world", "bad tag;rm"]},
         {"id": "not-hex", "time": "2026-11-06T11:00:00Z"}]


def test_the_helper_results_are_read_and_bad_ones_skipped(apex):
    installed(apex)
    write_result(apex, "20261106T100000Z-0000aaaa", action="list-snapshots", state="done", time="t",
                 snapshots=staff_apex.reduce_snapshots(SNAPS))
    write_result(apex, "20261106T110000Z-0000bbbb", action="rm -rf", state="done")
    (apex.x.results / "nonsense.json").write_text(json.dumps({"action": "backup-now"}))
    (apex.x.results / "20261106T120000Z-0000cccc.json").write_text("not json")
    code, data = apex.call("GET", "/api/helper")
    assert [j["id"] for j in data["jobs"]] == ["20261106T100000Z-0000aaaa"]
    code, data = apex.call("GET", "/api/snapshots")
    assert [s["id"] for s in data["snapshots"]] == ["b" * 64, "a" * 64]
    assert data["snapshots"][0]["tags"] == ["world"] and data["snapshots"][1]["size"] == 9


def test_a_restore_is_owners_only_and_needs_the_typed_short_id(apex):
    installed(apex)
    write_result(apex, "20261106T100000Z-0000aaaa", action="list-snapshots", state="done", time="t",
                 snapshots=staff_apex.reduce_snapshots(SNAPS))
    snap = "a" * 64
    assert apex.call("POST", "/api/world-restore", {"snapshot": snap, "confirm": snap[:8]},
                     headers=as_role("admin"))[0] == 403
    assert apex.call("POST", "/api/world-restore", {"snapshot": snap, "confirm": "nope"})[0] == 400
    assert apex.call("POST", "/api/world-restore", {"snapshot": "c" * 64, "confirm": "c" * 8})[0] == 400
    assert apex.call("POST", "/api/world-restore", {"snapshot": "zz; rm", "confirm": "zz; rm"})[0] == 400
    assert not list(apex.x.requests.iterdir())
    code, done = apex.call("POST", "/api/world-restore", {"snapshot": snap, "confirm": snap[:8]})
    assert code == 200
    assert (apex.x.requests / f"{done['request']}.req").read_text() == f"action=restore\nuser=diego\nsnapshot={snap}\n"
    # A second one while the first waits is refused.
    assert apex.call("POST", "/api/world-restore", {"snapshot": snap, "confirm": snap[:8]})[0] == 409


def test_the_snapshot_reducer_cli_reads_restics_json():
    done = subprocess.run([sys.executable, "-I", str(REPO.root / "tools" / "staff_apex.py"), "snapshots"],
                          input=json.dumps(SNAPS), capture_output=True, text=True, check=True)
    assert [r["short_id"] for r in json.loads(done.stdout)] == ["b" * 8, "a" * 8]
    bad = subprocess.run([sys.executable, "-I", str(REPO.root / "tools" / "staff_apex.py"), "snapshots"],
                         input="", capture_output=True, text=True)
    assert bad.returncode == 1


# ---------------------------------------------------------------- the helper script


def test_the_helper_script_is_plain_posix_sh_with_a_fixed_allow_list():
    raw = (DEPLOY / "monkey-staff-helper.sh").read_bytes()
    assert b"\r\n" not in raw and raw.isascii()
    text = raw.decode()
    assert text.startswith("#!/bin/sh\n") and "set -eu" in text
    assert "eval" not in text and '. "$req"' not in text and "source " not in text
    actions_ = re.findall(r"^        ([a-z-]+)\) do_", text, re.M)
    assert actions_ == list(staff_apex.HELPER_ACTIONS)
    for unit in ("monkey-staff-helper.path", "monkey-staff-helper.service"):
        unit_raw = (DEPLOY / unit).read_bytes()
        assert b"\r\n" not in unit_raw and unit_raw.isascii()
    assert "PathExistsGlob=/srv/monkey/staff/requests/*.req" in (DEPLOY / "monkey-staff-helper.path").read_text()
    service = (DEPLOY / "monkey-staff-helper.service").read_text()
    assert "User=root" in service and "StateDirectory=monkey-staff-helper" in service
    assert "ExecStart=/bin/sh /opt/monkey/deploy/monkey-staff-helper.sh" in service   # root's copy
    shell = shutil.which("dash")
    if shell:
        for name in ("monkey-staff-helper.sh", "monkey-staff.sh"):
            subprocess.run([shell, "-n", str(DEPLOY / name)], check=True)


HELPER_FAKES = {
    "id": "echo 0",
    "sleep": 'echo "sleep $*" >>"$FAKE_CALLS"',
    # flock FD, or flock FILE CMD...: runs CMD.
    "flock": 'echo "flock $*" >>"$FAKE_CALLS"\n'
             'while :; do case $1 in -w) shift 2 ;; -*) shift ;; *) break ;; esac; done\n'
             'shift\n[ $# -eq 0 ] || exec "$@"',
    "runuser": 'while [ "$1" != -- ]; do shift; done\nshift\nexec "$@"',
    "chown": 'echo "chown $*" >>"$FAKE_CALLS"',
    "stat": 'case "$*" in *%U*) echo monkey ;; *) exec /usr/bin/stat "$@" ;; esac',
    "systemctl": 'echo "systemctl $*" >>"$FAKE_CALLS"',
    # docker compose: running unless FAKE_STOPPED; `rcon list` says nobody is on.
    "docker": 'echo "docker $*" >>"$FAKE_CALLS"\ncase "$*" in\n'
              '  *"ps -q"*) [ -n "${FAKE_STOPPED:-}" ] || echo 0123456789ab ;;\n'
              '  *"rcon list"*) echo "There are 0 of a max of 30 players online:" ;;\nesac',
}
# The repo's monkey-backup.sh needs root's keys; this one answers --restic like restic would.
FAKE_BACKUP = """#!/bin/sh
echo "backup.sh $*" >>"$FAKE_CALLS"
[ "$1" = --restic-read ] || exit 2   # read-only: the helper never writes to the repository
shift
case $1 in
    snapshots) cat "$FAKE_SNAPSHOTS" ;;
    restore)
        [ -z "${FAKE_RESTORE_FAILS:-}" ] || exit 1
        target=''
        while [ $# -gt 0 ]; do [ "$1" != --target ] || target=$2; shift; done
        mkdir -p "$target" && printf restored >"$target/level.dat"
        ;;
    *) exit 3 ;;
esac
"""


@pytest.fixture
def helper(tmp_path):
    """Runs the real monkey-staff-helper.sh under dash, as root, with docker, systemctl and restic faked."""
    shell = shutil.which("dash")
    if not shell:
        pytest.skip("needs dash (tools/checks.py puts Git for Windows' dash on PATH)")
    bin_dir, calls = tmp_path / "bin", tmp_path / "calls"
    bin_dir.mkdir()
    fakes = dict(HELPER_FAKES)
    fakes["python3"] = f'exec "{Path(sys.executable).as_posix()}" "$@"'
    for name, body in fakes.items():
        (bin_dir / name).write_text(f"#!/bin/sh\n{body}\n", newline="\n")
        (bin_dir / name).chmod(0o755)
    repo = tmp_path / "repo"
    (repo / "deploy").mkdir(parents=True)
    (repo / "tools").mkdir()
    shutil.copy(REPO.root / "tools" / "staff_apex.py", repo / "tools" / "staff_apex.py")
    (repo / "deploy" / "monkey-backup.sh").write_text(FAKE_BACKUP, newline="\n")
    live, staff_dir, results = tmp_path / "live", tmp_path / "staff", tmp_path / "results"
    (live / "server" / "world").mkdir(parents=True)
    (live / "docker").mkdir()
    (live / "server" / "world" / "level.dat").write_text("live")
    (live / "server" / "server.properties").write_text("level-name=world\n", newline="\n")
    (staff_dir / "requests").mkdir(parents=True)
    snaps = tmp_path / "snaps.json"
    snaps.write_text(json.dumps(SNAPS))

    def request(name, text):
        (staff_dir / "requests" / f"{name}.req").write_text(text, newline="\n")

    def run(**env):
        calls.unlink(missing_ok=True)
        environ = {**os.environ, "PATH": bin_dir.as_posix() + os.pathsep + os.environ["PATH"],
                   "FAKE_CALLS": calls.as_posix(), "FAKE_SNAPSHOTS": snaps.as_posix(),
                   "MONKEY_DEPLOY_ENV": (tmp_path / "none").as_posix(), "REPO_DIR": repo.as_posix(),
                   "LIVE_DIR": live.as_posix(), "STAFF_DIR": staff_dir.as_posix(),
                   "HELPER_RESULTS": results.as_posix(), "LOCK_FILE": (tmp_path / "deploy.lock").as_posix(),
                   # root's copies (in /opt/monkey on the VPS): here the made-up checkout's
                   "HELPER_BACKUP": (repo / "deploy" / "monkey-backup.sh").as_posix(),
                   "HELPER_TOOLS": (repo / "tools").as_posix(), **env}
        done = subprocess.run([shell, (DEPLOY / "monkey-staff-helper.sh").as_posix()], env=environ,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
        out = {p.stem: json.loads(p.read_text()) for p in results.glob("*.json")} if results.exists() else {}
        return SimpleNamespace(code=done.returncode, out=done.stdout, results=out,
                               calls=calls.read_text().splitlines() if calls.exists() else [])

    return SimpleNamespace(run=run, request=request, live=live, requests=staff_dir / "requests")


RID = "20261106T100000Z-0123abcd"


def test_the_helper_starts_a_backup_and_reads_nothing_else(helper):
    helper.request(RID, "action=backup-now\nuser=diego\nsnapshot=; rm -rf /\nmotd=$(reboot)\n")
    done = helper.run()
    assert done.code == 0, done.out
    assert done.results[RID]["action"] == "backup-now" and done.results[RID]["state"] == "done"
    assert "systemctl start --no-block monkey-backup.service" in done.calls
    assert not [c for c in done.calls if "reboot" in c or "rm -rf" in c]
    assert not list(helper.requests.iterdir())


@pytest.mark.parametrize("text", ["action=stop\n", "action=backup-now; reboot\n", "action=$(reboot)\n", "",
                                  "user=diego\n", "action=Backup-Now\n"])
def test_the_helper_refuses_anything_but_its_three_actions(helper, text):
    helper.request(RID, text)
    done = helper.run()
    assert done.code == 0, done.out
    assert done.results[RID]["action"] == "unknown" and done.results[RID]["state"] == "refused"
    assert not [c for c in done.calls if c.startswith(("systemctl", "docker", "backup.sh"))]


def test_the_helper_deletes_requests_it_does_not_trust_unread(helper, tmp_path):
    helper.request("not-a-request-name", "action=backup-now\n")
    target = tmp_path / "elsewhere.txt"
    target.write_text("action=backup-now\n")
    link = helper.requests / f"{RID}.req"
    try:
        link.symlink_to(target)
    except OSError:
        link = None
    done = helper.run()
    assert done.code == 0, done.out
    assert not done.results and not [c for c in done.calls if c.startswith("systemctl")]
    assert not list(helper.requests.iterdir()) and target.exists()


def test_the_helper_lists_the_snapshots_cut_down(helper):
    helper.request(RID, "action=list-snapshots\nuser=diego\n")
    done = helper.run()
    assert done.code == 0, done.out
    result = done.results[RID]
    assert result["state"] == "done"
    assert [s["short_id"] for s in result["snapshots"]] == ["b" * 8, "a" * 8]
    assert "backup.sh --restic-read snapshots --json --tag world" in done.calls


def test_the_helper_refuses_a_snapshot_that_is_not_hex(helper):
    helper.request(RID, "action=restore\nsnapshot=abc;reboot\n")
    done = helper.run()
    assert done.results[RID]["state"] == "refused"
    assert not [c for c in done.calls if c.startswith(("docker", "backup.sh"))]
    assert (helper.live / "server" / "world" / "level.dat").read_text() == "live"


def test_the_helper_restores_a_snapshot_and_keeps_the_old_world(helper):
    snap = "a" * 64
    helper.request(RID, f"action=restore\nuser=diego\nsnapshot={snap}\n")
    done = helper.run()
    assert done.code == 0, done.out
    assert done.results[RID]["state"] == "done", done.results[RID]
    assert (helper.live / "server" / "world" / "level.dat").read_text() == "restored"
    kept = list((helper.live / "backups").glob("before-restore-*/world/level.dat"))
    assert len(kept) == 1 and kept[0].read_text() == "live"
    assert not list(helper.live.glob(".restore.*"))
    restore = next(i for i, c in enumerate(done.calls) if c.startswith("backup.sh --restic-read restore"))
    assert f"{snap}:{helper.live.as_posix()}/server/world" in done.calls[restore]
    stop = next(i for i, c in enumerate(done.calls) if c.endswith("stop monkey"))
    start = next(i for i, c in enumerate(done.calls) if c.endswith("up -d --no-build monkey"))
    held = next(i for i, c in enumerate(done.calls) if c.startswith("flock") and "backup.lock" in c)
    lock = next(i for i, c in enumerate(done.calls) if c.startswith("flock") and "backup.lock" not in c)
    # Downloaded under the backup lock (no forget or prune meanwhile) while the server ran; the swap is under the
    # deploy lock, between the stop and the start.
    assert held < restore < lock < stop < start


def test_a_failed_restore_leaves_the_world_and_the_server_alone(helper):
    helper.request(RID, f"action=restore\nsnapshot={'a' * 64}\n")
    done = helper.run(FAKE_RESTORE_FAILS="1")
    assert done.results[RID]["state"] == "failed"
    assert (helper.live / "server" / "world" / "level.dat").read_text() == "live"
    assert not [c for c in done.calls if c.endswith("stop monkey")]
    assert not list(helper.live.glob(".restore.*"))


def test_the_staff_script_installs_the_helper_only_as_its_own_step():
    text = (DEPLOY / "monkey-staff.sh").read_text()
    install = text.split('if [ "$MODE" = install ]; then', 1)[1].split("exit 0", 1)[0]
    assert "monkey-staff-helper" not in install
    assert "--install-helper) MODE=install-helper" in text
    assert "install -d -m 770 -o monkey -g monkey" in text


@pytest.fixture
def install_helper(tmp_path):
    """Runs `monkey-staff.sh --install-helper` under dash as a fake root: root's copies in DEST, root's clone in SRC,
    the units in UNITS; id, install and systemctl faked."""
    shell = shutil.which("dash")
    if not shell:
        pytest.skip("needs dash (tools/checks.py puts Git for Windows' dash on PATH)")
    dest, src, units, staff, bin_dir = (tmp_path / n for n in ("dest", "src", "units", "staff", "bin"))
    calls = tmp_path / "calls"
    for d in (dest / "deploy", dest / "tools", src / "deploy", units, staff, bin_dir):
        d.mkdir(parents=True)
    for f in ("deploy/monkey-staff-helper.sh", "deploy/monkey-backup.sh", "deploy/lib.sh", "tools/staff_apex.py"):
        (dest / f).write_text("#\n", newline="\n")
    for u in ("monkey-staff-helper.path", "monkey-staff-helper.service"):
        (src / "deploy" / u).write_text(f"[Unit]\n# {u} v2\n", newline="\n")
    fakes = {"id": 'echo "${FAKE_UID:-0}"',
             "install": 'last=; prev=; dir=0\n'
                        'for a in "$@"; do case $a in -d) dir=1 ;; esac; prev=$last; last=$a; done\n'
                        'if [ $dir = 1 ]; then mkdir -p "$last"; else cp "$prev" "$last"; fi',
             "systemctl": "exit 0"}
    for name, body in fakes.items():
        (bin_dir / name).write_text(f'#!/bin/sh\necho "{name} $*" >>"$FAKE_CALLS"\n{body}\n', newline="\n")
        (bin_dir / name).chmod(0o755)

    def run(**env):
        calls.unlink(missing_ok=True)
        environ = {**os.environ, "PATH": bin_dir.as_posix() + os.pathsep + os.environ["PATH"],
                   "FAKE_CALLS": calls.as_posix(), "MONKEY_DEPLOY_ENV": (tmp_path / "none").as_posix(),
                   "STAFF_DIR": staff.as_posix(), "HELPER_WATCHED": staff.as_posix(), "ROOT_DEST": dest.as_posix(),
                   "ROOT_SRC": src.as_posix(), "UNIT_DIR": units.as_posix(), **env}
        done = subprocess.run([shell, (DEPLOY / "monkey-staff.sh").as_posix(), "--install-helper"], env=environ,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
        return done.returncode, done.stdout, calls.read_text().splitlines() if calls.exists() else []

    return SimpleNamespace(run=run, dest=dest, src=src, units=units, staff=staff)


def test_install_helper_installs_root_clones_units_and_only_changed_ones(install_helper):
    h = install_helper
    code, out, calls = h.run()
    assert code == 0, out
    assert sorted(p.name for p in h.units.iterdir()) == ["monkey-staff-helper.path", "monkey-staff-helper.service"]
    assert (h.units / "monkey-staff-helper.path").read_text() == "[Unit]\n# monkey-staff-helper.path v2\n"
    assert (h.staff / "requests").is_dir()
    assert "systemctl daemon-reload" in calls and "systemctl enable --now monkey-staff-helper.path" in calls
    code, out, calls = h.run()   # nothing changed: no reload, no restart
    assert code == 0 and "systemctl daemon-reload" not in calls
    assert not any("restart" in c for c in calls) and not any("installed" in line for line in out.splitlines())


def test_install_helper_refuses_without_root_or_root_copies(install_helper):
    h = install_helper
    code, out, _ = h.run(FAKE_UID="1000")
    assert code == 1 and "run as root" in out
    code, out, _ = h.run(HELPER_WATCHED="/srv/monkey/staff")
    assert code == 1 and "the helper watches /srv/monkey/staff/requests" in out
    (h.dest / "tools" / "staff_apex.py").unlink()
    code, out, calls = h.run()
    assert code == 1 and "tools/staff_apex.py is missing: install root's copies first" in out
    assert not any(h.units.iterdir()) and not any(c.startswith("systemctl") for c in calls)
    (h.dest / "tools" / "staff_apex.py").write_text("#\n")
    (h.src / "deploy" / "monkey-staff-helper.service").unlink()
    code, out, _ = h.run()
    assert code == 1 and "deploy/monkey-staff-helper.service is missing" in out and not any(h.units.iterdir())


# ---------------------------------------------------------------- schedules: when a run is due


def at(text, tz=None):
    naive = dt.datetime.fromisoformat(text)
    return staff_apex.from_local(naive, tz)


@pytest.fixture
def la():
    zoneinfo = pytest.importorskip("zoneinfo")
    try:
        return zoneinfo.ZoneInfo("America/Los_Angeles")
    except zoneinfo.ZoneInfoNotFoundError:
        pytest.skip("no time zone database here")


def test_daily_and_weekly_slots(la):
    daily = {"type": "daily", "time": "04:00"}
    assert staff_apex.latest_slot(daily, at("2026-11-06 05:00", la), la) == at("2026-11-06 04:00", la)
    assert staff_apex.latest_slot(daily, at("2026-11-06 03:59", la), la) == at("2026-11-05 04:00", la)
    assert staff_apex.next_slot(daily, at("2026-11-06 04:00", la), la) == at("2026-11-07 04:00", la)
    weekly = {"type": "weekly", "time": "20:00", "day": 4}     # Friday
    assert staff_apex.latest_slot(weekly, at("2026-11-06 21:00", la), la) == at("2026-11-06 20:00", la)
    assert staff_apex.latest_slot(weekly, at("2026-11-06 19:00", la), la) == at("2026-10-30 20:00", la)


def test_a_daily_slot_runs_once_across_a_clock_change(la):
    # 2026-11-01 01:30 happens twice in Los Angeles; 2026-03-08 02:30 never happens.
    autumn = {"type": "daily", "time": "01:30"}
    first = staff_apex.latest_slot(autumn, at("2026-11-01 03:00", la), la)
    slots = {staff_apex.latest_slot(autumn, at("2026-11-01 00:00", la) + m * 60, la) for m in range(0, 24 * 60, 5)}
    assert first in slots and len([s for s in slots if s and s >= at("2026-11-01 00:00", la)]) == 1
    spring = {"type": "daily", "time": "02:30"}
    gap = staff_apex.latest_slot(spring, at("2026-03-08 12:00", la), la)
    assert at("2026-03-08 01:00", la) < gap < at("2026-03-08 04:00", la)
    assert staff_apex.latest_slot(spring, at("2026-03-09 01:00", la), la) == gap


def test_interval_slots_count_from_their_anchor():
    when = {"type": "interval", "minutes": 30, "anchor": 1_000_000}
    assert staff_apex.latest_slot(when, 999_999) is None
    assert staff_apex.latest_slot(when, 1_000_000 + 30 * 60 * 3 + 5) == 1_000_000 + 30 * 60 * 3
    assert staff_apex.next_slot(when, 1_000_000 + 1) == 1_000_000 + 30 * 60


@pytest.mark.parametrize("when", [
    {"type": "interval", "minutes": 9}, {"type": "interval", "minutes": "60"}, {"type": "daily", "time": "24:00"},
    {"type": "daily", "time": "4:00"}, {"type": "weekly", "time": "04:00", "day": 7}, {"type": "cron"}, "daily",
])
def test_a_bad_when_is_refused(apex, when):
    code, _ = apex.call("POST", "/api/schedules", {"name": "x", "kind": "backup", "when": when})
    assert code == 400


@pytest.mark.parametrize("anchor", [float("nan"), float("inf"), -float("inf"), 1e999, 5e9, -5e9, True, "x"])
def test_an_interval_anchor_must_be_a_sane_number(anchor):
    got = staff_apex.checked_when({"type": "interval", "minutes": 30, "anchor": anchor}, 1_700_000_000.7)
    assert got["anchor"] == 1_700_000_000
    assert staff_apex.checked_when({"type": "interval", "minutes": 30, "anchor": 1_600_000_000.5}, 1)["anchor"] \
        == 1_600_000_000.5


def test_a_row_with_an_unreadable_anchor_does_not_break_the_list(apex):
    bad = {"id": "i1", "name": "i", "kind": "backup", "enabled": True, "last_slot": 0,
           "when": {"type": "interval", "minutes": 30, "anchor": float("inf")}}
    apex.staff.mkdir(parents=True, exist_ok=True)
    (apex.staff / "schedules.json").write_text(json.dumps({"schedules": [bad]}))
    code, data = apex.call("GET", "/api/schedules")
    assert code == 200 and data["schedules"][0]["describe"] == "not readable"


def test_a_failed_save_in_a_tick_does_not_stop_the_schedule_for_good(apex):
    row = {"id": "g1", "name": "g", "kind": "command", "command": "list", "enabled": True,
           "when": {"type": "interval", "minutes": 10, "anchor": 0}, "last_slot": 0}
    apex.staff.mkdir(parents=True, exist_ok=True)
    (apex.staff / "schedules.json").write_text(json.dumps({"schedules": [row]}))
    now = 10 * 60 * 1000 + 5
    apex.x.clock = lambda: now
    real = apex.x._save

    def broken(rows):
        raise OSError("disk full")
    apex.x._save = broken
    with pytest.raises(OSError):
        apex.x.tick()
    assert "g1" not in apex.x._running
    apex.x._save = real
    assert apex.x.tick() == ["g1"]


def test_a_scheduled_command_follows_the_consoles_rules(apex):
    for command in ("stop", "seed", "kick", "say hi\nstop"):
        code, _ = apex.call("POST", "/api/schedules", {"name": "x", "kind": "command", "command": command,
                                                        "when": {"type": "daily", "time": "04:00"}})
        assert code in (400, 403)
    assert not (apex.staff / "schedules.json").exists()


def test_the_scheduler_runs_a_slot_once_even_after_a_restart(apex):
    clock = [at("2026-11-06 03:50")]
    apex.x.clock = lambda: clock[0]
    apex.docker.answers["say Vote!"] = ""
    code, made = apex.call("POST", "/api/schedules", {"name": "vote", "kind": "command", "command": "say Vote!",
                                                       "when": {"type": "daily", "time": "04:00"}})
    assert code == 200
    sid = made["schedule"]["id"]
    assert apex.x.tick() == []                       # armed: not before 04:00
    clock[0] = at("2026-11-06 04:00:30")
    assert apex.x.tick() == [sid]
    assert apex.x.tick() == []
    # A new panel (a restart of monkey-panel) reads the saved slot and doesn't run it again.
    fresh = staff_apex.Extras(apex.panel)
    fresh.clock, fresh.sleep = apex.x.clock, apex.x.sleep
    assert fresh.tick() == []
    # The run's thread saves the result, then writes actions.log (_finish): wait for both.
    for _ in range(100):
        rows = json.loads((apex.staff / "schedules.json").read_text())["schedules"]
        if rows[0]["last_result"] != "running" and "schedule schedule-run vote" in actions(apex):
            break
        threading.Event().wait(0.05)
    assert rows[0]["last_result"].startswith("done")
    assert [c[-1] for c in apex.docker.calls if "exec" in c] == ["say Vote!"]
    assert "schedule schedule-run vote" in actions(apex) and "diego schedule-add vote" in actions(apex)


def test_a_slot_missed_while_the_panel_was_down_is_skipped(apex):
    clock = [at("2026-11-06 03:00")]
    apex.x.clock = lambda: clock[0]
    apex.call("POST", "/api/schedules", {"name": "b", "kind": "command", "command": "list",
                                         "when": {"type": "daily", "time": "04:00"}})
    clock[0] = at("2026-11-06 05:00")
    assert apex.x.tick() == []
    rows = json.loads((apex.staff / "schedules.json").read_text())["schedules"]
    assert rows[0]["last_result"].startswith("missed")


def test_bad_rows_and_a_corrupt_file_never_stop_the_scheduler(apex):
    good = {"id": "g1", "name": "g", "kind": "command", "command": "list", "enabled": True,
            "when": {"type": "interval", "minutes": 10, "anchor": 0}, "last_slot": 0}
    rows = [{"id": "b1", "enabled": True, "kind": "command", "when": {"type": "daily", "time": "nope"}},
            {"id": "b2", "enabled": True}, "not a row", good]
    (apex.staff).mkdir(parents=True, exist_ok=True)
    (apex.staff / "schedules.json").write_text(json.dumps({"schedules": rows}))
    now = 10 * 60 * 1000 + 5
    apex.x.clock = lambda: now
    assert apex.x.tick() == ["g1"]
    (apex.staff / "schedules.json").write_text("{broken")
    assert apex.x.tick() == []
    assert (apex.staff / "schedules.json").read_text() == "{broken"
    assert apex.call("POST", "/api/schedules", {"name": "x", "kind": "backup",
                                                "when": {"type": "daily", "time": "04:00"}})[0] == 500
    assert (apex.staff / "schedules.json").read_text() == "{broken"


def _restart_row(apex, enabled=True):
    row = {"id": "r", "name": "r", "kind": "restart", "enabled": enabled,
           "when": {"type": "daily", "time": "04:00"}, "last_slot": 0}
    apex.staff.mkdir(parents=True, exist_ok=True)
    (apex.staff / "schedules.json").write_text(json.dumps({"schedules": [row]}))
    apex.docker.answers.update({f"say Scheduled restart {w}.": "" for _, w in staff_apex.RESTART_WARNINGS})
    return row


def test_a_scheduled_restart_warns_then_uses_the_restart_path(apex):
    row = _restart_row(apex)
    slept = []
    apex.x.sleep = slept.append
    result = apex.x._do(row)
    said = [c[-1] for c in apex.docker.calls if "exec" in c]
    assert said == [f"say Scheduled restart {w}." for _, w in staff_apex.RESTART_WARNINGS]
    assert sum(slept) == 300 and result.startswith("restarted")
    assert "schedule power restart-now" in actions(apex)


def test_a_restart_is_skipped_if_the_schedule_goes_during_the_warnings(apex):
    for how, word in (("delete", "deleted"), ("off", "turned off")):
        row = _restart_row(apex)

        def change(seconds, how=how, row=row):
            rows = [] if how == "delete" else [{**row, "enabled": False}]
            (apex.staff / "schedules.json").write_text(json.dumps({"schedules": rows}))
        apex.x.sleep = change
        result = apex.x._do(row)
        assert result.startswith("skipped") and word in result
    assert "restart-now" not in actions(apex)


def test_a_restart_is_skipped_if_the_server_was_stopped_during_the_warnings(apex):
    row = _restart_row(apex)
    states = iter([True, False])
    apex.x.running = lambda: next(states)
    result = apex.x._do(row)
    assert result.startswith("skipped") and "stopped" in result
    assert "restart-now" not in actions(apex)


NOBODY = "There are 0 of a max of 30 players online: "


@pytest.mark.parametrize("only, answer, runs", [
    ("always", None, True), (None, None, True),         # None: a row from before the condition existed
    ("empty", NOBODY, True), ("empty", None, False),    # the fixture's `list` answers 2 online
    ("players", None, True), ("players", NOBODY, False),
])
def test_a_schedule_runs_only_when_its_condition_holds(apex, only, answer, runs):
    if answer is not None:
        apex.docker.answers["list"] = answer
    apex.docker.answers["say hi"] = ""
    row = {"id": "c", "name": "c", "kind": "command", "command": "say hi", **({"only": only} if only else {})}
    result = apex.x._do(row)
    sent = [c[-1] for c in apex.docker.calls if "exec" in c and c[-1] != "list"]
    assert result.startswith("done" if runs else "skipped") and sent == (["say hi"] if runs else [])


def test_a_count_the_server_will_not_give_is_never_taken_as_nobody_online(apex):
    apex.docker.answers["list"] = "something else"
    for only in ("empty", "players"):
        result = apex.x._do({"id": "c", "name": "c", "kind": "restart", "only": only})
        assert result == "skipped: the server didn't say who is online"
    assert "restart-now" not in actions(apex)
    # A stopped server has nobody on it: an only-when-empty backup still runs, an only-with-players one doesn't.
    apex.x.running = lambda: False
    assert apex.x.players_on() == 0
    assert apex.x._held_back({"only": "empty"}) is None and "nobody" in apex.x._held_back({"only": "players"})


def test_a_restart_only_when_empty_is_called_off_if_someone_joins_during_the_warnings(apex):
    row = {**_restart_row(apex), "only": "empty"}
    apex.docker.answers["say The scheduled restart is called off."] = ""
    (apex.staff / "schedules.json").write_text(json.dumps({"schedules": [row]}))
    apex.docker.answers["list"] = NOBODY
    joined = "There are 1 of a max of 30 players online: Alpha"
    apex.x.sleep = lambda seconds: apex.docker.answers.update({"list": joined})
    result = apex.x._do(row)
    assert result == "skipped: 1 online, and it runs only when nobody is" and "restart-now" not in actions(apex)
    said = [c[-1] for c in apex.docker.calls if "exec" in c]
    assert said[-1] == "say The scheduled restart is called off."      # players were told it was coming


def test_a_schedules_condition_is_checked_kept_and_shown(apex):
    when = {"type": "daily", "time": "04:00"}
    bad = {"name": "x", "kind": "restart", "when": when, "only": "sometimes"}
    assert apex.call("POST", "/api/schedules", bad)[0] == 400
    code, made = apex.call("POST", "/api/schedules", {"name": "x", "kind": "restart", "when": when, "only": "empty"})
    assert code == 200 and made["schedule"]["only"] == "empty"
    code, edited = apex.call("PUT", "/api/schedules", {"id": made["schedule"]["id"], "enabled": False})
    assert code == 200 and edited["schedule"]["only"] == "empty"      # an edit of something else keeps it
    _, made = apex.call("POST", "/api/schedules", {"name": "y", "kind": "backup", "when": when})
    assert made["schedule"]["only"] == "always"


def test_schedules_can_be_turned_off_and_deleted(apex):
    _, made = apex.call("POST", "/api/schedules", {"name": "n", "kind": "backup",
                                                   "when": {"type": "weekly", "time": "06:00", "day": 0}})
    sid = made["schedule"]["id"]
    code, edited = apex.call("PUT", "/api/schedules", {"id": sid, "enabled": False})
    assert code == 200 and edited["schedule"]["enabled"] is False and edited["schedule"]["next"] is None
    _, listed = apex.call("GET", "/api/schedules")
    assert listed["schedules"][0]["describe"] == "every Monday at 06:00" and "UTC" in listed["timezone"]
    assert apex.call("POST", "/api/schedule-delete", {"id": sid})[0] == 200
    assert apex.call("POST", "/api/schedule-delete", {"id": sid})[0] == 404


# ---------------------------------------------------------------- mods


def jar(path: Path, meta=None, raw=None):
    with zipfile.ZipFile(path, "w") as z:
        if raw is not None:
            z.writestr("fabric.mod.json", raw)
        elif meta is not None:
            z.writestr("fabric.mod.json", json.dumps(meta))
        z.writestr("a.class", b"\xca\xfe")


def test_the_mods_list_reads_each_jar(apex):
    mods = apex.root / "mods"
    (mods / "a.jar").unlink()
    jar(mods / "sodium.jar", {"id": "sodium", "name": "Sodium", "version": "0.6", "environment": "client",
                              "description": "Fast\nrendering"})
    jar(mods / "lib.jar", raw='\ufeff{"id": "lib", "version": "1",\n "description": "tab\there"}')
    jar(mods / "plain.jar")
    (mods / "broken.jar").write_bytes(b"not a zip")
    code, data = apex.call("GET", "/api/mods", headers=as_role("moderator"))
    assert code == 200
    rows = {r["file"]: r for r in data["mods"]}
    assert rows["sodium.jar"]["name"] == "Sodium" and rows["sodium.jar"]["environment"] == "client"
    assert rows["sodium.jar"]["description"] == "Fast rendering"
    assert rows["lib.jar"]["name"] == "lib" and rows["lib.jar"]["environment"] == "both"
    assert "not a Fabric mod" in rows["plain.jar"]["error"] and "error" in rows["broken.jar"]
    # Cached until the jar changes.
    calls = []
    real = staff_apex.mod_info
    staff_apex.mod_info = lambda p: calls.append(p.name) or real(p)
    try:
        apex.call("GET", "/api/mods")
        assert calls == []
        jar(mods / "sodium.jar", {"id": "sodium", "name": "Sodium", "version": "0.7"})
        os.utime(mods / "sodium.jar", (1, 1))
        assert {r["file"]: r for r in apex.call("GET", "/api/mods")[1]["mods"]}["sodium.jar"]["version"] == "0.7"
        assert calls == ["sodium.jar"]
    finally:
        staff_apex.mod_info = real


# ---------------------------------------------------------------- the world download


def saving(b):
    return [c[-1] for c in b.docker.calls if "exec" in c and c[-1].startswith("save-")]


def test_the_world_streams_as_a_zip_with_saving_off_meanwhile(apex):
    apex.docker.answers.update({"save-off": "Automatic saving is now disabled", "save-all flush": "Saved the game",
                                "save-on": "Automatic saving is now enabled"})
    (apex.root / "world" / "region").mkdir()
    (apex.root / "world" / "region" / "r.0.0.mca").write_bytes(os.urandom(4096))
    (apex.root / "world" / "session.lock").write_text("lock")
    code, link = apex.call("POST", "/api/world-download", {})
    assert code == 200 and link["url"].startswith("/api/world-download?token=")
    code, raw = apex.call("GET", link["url"])
    assert code == 200
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert sorted(z.namelist()) == ["world/level.dat", "world/region/r.0.0.mca"]
        assert z.read("world/region/r.0.0.mca") == (apex.root / "world" / "region" / "r.0.0.mca").read_bytes()
    assert saving(apex) == ["save-off", "save-all flush", "save-on"]
    assert apex.lock.held == apex.lock.released == 1
    # The link works once.
    assert apex.call("GET", link["url"])[0] == 403
    assert "diego world-download world" in actions(apex)


def test_saving_comes_back_on_when_the_stream_breaks(apex, monkeypatch):
    apex.docker.answers.update({"save-off": "ok", "save-all flush": "ok", "save-on": "ok"})

    def broken(self, world):
        yield str(world / "level.dat"), "world/level.dat"
        raise OSError("disk gone")

    monkeypatch.setattr(staff_apex.WorldZip, "files", broken)
    _, link = apex.call("POST", "/api/world-download", {})
    apex.call("GET", link["url"])
    assert saving(apex) == ["save-off", "save-all flush", "save-on"]
    assert apex.lock.released == 1 and "world-download-result stopped" in actions(apex)
    assert apex.x._download.acquire(blocking=False)


def test_the_download_is_refused_before_anything_when_saving_wont_stop(apex):
    apex.docker.answers.update({"save-on": "ok"})       # save-off isn't answered: refused
    _, link = apex.call("POST", "/api/world-download", {})
    code, body = apex.call("GET", link["url"])
    assert code == 502 and saving(apex) == ["save-off", "save-on"]
    assert apex.lock.released == 1


def test_a_download_link_is_the_owners_who_asked_for_it(apex):
    _, link = apex.call("POST", "/api/world-download", {}, user="lorenzo")
    assert apex.call("GET", link["url"], user="diego")[0] == 403
    assert apex.call("GET", "/api/world-download?token=made-up")[0] == 403
    assert apex.call("GET", link["url"], headers=as_role("admin"))[0] == 403


# ---------------------------------------------------------------- bans by address


@pytest.mark.parametrize("text", ["8.8.8.8", "1.1.1.1", "2001:4860:4860::8888", "::ffff:8.8.8.8"])
def test_a_public_address_is_taken(text):
    assert staff_apex.public_ip(text) in ("8.8.8.8", "1.1.1.1", "2001:4860:4860::8888")


@pytest.mark.parametrize("text", ["10.0.0.1", "192.168.1.5", "172.17.0.1", "127.0.0.1", "::1", "fe80::1",
                                  "0.0.0.0", "224.0.0.1", "8.8.8.8; stop", "8.8.8.8 stop", "not an ip", "",
                                  "8.8.8.8/24", "999.1.1.1"])
def test_anything_else_is_refused(text):
    with pytest.raises(staff_panel.Refused):
        staff_apex.public_ip(text)


def test_an_address_ban_sends_one_command_and_logs_no_address(apex):
    apex.docker.answers["ban-ip 8.8.8.8 alt accounts"] = "Banned IP 8.8.8.8: alt accounts"
    apex.docker.answers["ban-ip Alpha"] = "Banned IP of Alpha"
    apex.docker.answers["pardon-ip 8.8.8.8"] = "Unbanned IP 8.8.8.8"
    assert apex.call("POST", "/api/ip-ban", {"target": "8.8.8.8", "reason": "alt accounts"})[0] == 200
    assert apex.call("POST", "/api/ip-ban", {"target": "Alpha"})[0] == 200
    assert apex.call("POST", "/api/ip-pardon", {"ip": "8.8.8.8"})[0] == 200
    assert apex.call("POST", "/api/ip-ban", {"target": "8.8.8.8", "reason": "a\nstop"})[0] == 400
    assert apex.call("POST", "/api/ip-ban", {"target": "10.0.0.1"})[0] == 400
    assert [c[-1] for c in apex.docker.calls if "exec" in c] == ["ban-ip 8.8.8.8 alt accounts", "ban-ip Alpha",
                                                                 "pardon-ip 8.8.8.8"]
    assert "8.8.8.8" not in actions(apex) and "diego ban-ip an address" in actions(apex)


def test_an_address_in_the_ban_list_can_be_pardoned_even_if_private(apex):
    # `ban-ip Alpha` lets the server pick the address, which can be a proxy's or Docker's.
    (apex.root / "banned-ips.json").write_text(json.dumps([{"ip": "172.17.0.1", "reason": "x"}]))
    apex.docker.answers["pardon-ip 172.17.0.1"] = "Unbanned IP 172.17.0.1"
    assert apex.call("POST", "/api/ip-pardon", {"ip": "172.17.0.1"})[0] == 200
    # Not in the list: still only a public address.
    assert apex.call("POST", "/api/ip-pardon", {"ip": "10.0.0.1"})[0] == 400
    assert apex.call("POST", "/api/ip-pardon", {"ip": "nonsense"})[0] == 400
    assert apex.call("POST", "/api/ip-ban", {"target": "172.17.0.1"})[0] == 400
    assert [c[-1] for c in apex.docker.calls if "exec" in c] == ["pardon-ip 172.17.0.1"]


def test_the_address_bans_are_listed(apex):
    (apex.root / "banned-ips.json").write_text(json.dumps([
        {"ip": "8.8.8.8", "reason": "alts", "created": "2026-11-06"}, {"ip": "nonsense"}, "x"]))
    code, data = apex.call("GET", "/api/ip-bans")
    assert code == 200 and [b["ip"] for b in data["ips"]] == ["8.8.8.8"]


# ---------------------------------------------------------------- the page


def test_the_new_page_code_runs_under_the_strict_policy():
    # The settings, mods and server tabs (staff-ui/src/tabs): text only, no style attribute, no confirm(), and no
    # address of another site in the tabs' code (the links the server returns are not in the source).
    from staff_ui import code, only_text, source
    tabs = source("tabs")
    only_text(tabs)
    assert not re.search(r"https?://", code(tabs))
    shell = source("shell", "tabs.ts")
    for tab in ("settings", "mods", "server"):
        assert f'id: "{tab}"' in shell
        assert source("tabs", tab)
