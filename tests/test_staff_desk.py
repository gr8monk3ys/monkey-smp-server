"""tools/staff_desk.py: everyone who has joined, notes on a player, saved commands and the searched record of changes;
and the file manager's new folder and rename (tools/staff_panel.py)."""
import csv
import io
import json
import os
import re

import pytest
import staff_desk
import staff_panel
from test_staff_panel import actions, box  # noqa: F401 (box is the fixture: a panel over a fake server folder)

from repo import REPO

ALPHA, BRAVO, CAROL = (f"0000000{i}-0000-4000-8000-00000000000{i}" for i in (1, 2, 3))
MOD, ADMIN = {"X-Staff-Role": "moderator"}, {"X-Staff-Role": "admin"}


@pytest.fixture
def desk(box):  # noqa: F811
    cache = [{"name": "Alpha", "uuid": ALPHA}, {"name": "Bravo", "uuid": BRAVO.upper()},
             {"name": "Carol", "uuid": CAROL}, {"name": "bad name!", "uuid": ALPHA},
             {"name": "NoUuid", "uuid": "nope"}, "junk"]
    (box.root / "usercache.json").write_text(json.dumps(cache))
    players = box.root / "world" / "players"
    for folder in ("data", "stats"):
        (players / folder).mkdir(parents=True)
    for uuid, seen in ((ALPHA, 1_800_000_000), (BRAVO, 1_800_005_000)):
        (players / "data" / f"{uuid}.dat").write_bytes(b"nbt")
        os.utime(players / "data" / f"{uuid}.dat", (seen, seen))
    (players / "data" / "notes.txt").write_text("not a player")
    played = {"stats": {"minecraft:custom": {"minecraft:play_time": 180_000}}}
    (players / "stats" / f"{ALPHA}.json").write_text(json.dumps(played))
    (players / "stats" / f"{BRAVO}.json").write_text("{broken")
    return box


# ---------------------------------------------------------------- who may ask


def test_every_route_names_who_may_use_it():
    assert set(staff_desk.NEEDS) == set(staff_desk.ROUTES)
    for key in staff_desk.ROUTES:
        assert staff_panel.ROUTES[key] is staff_desk.ROUTES[key] and staff_panel.NEEDS[key] in staff_panel.ROLES
    # Deleting a note and anything to do with commands is not a moderator's.
    assert staff_desk.NEEDS[("POST", "/api/player-note-delete")] == "admin"
    assert all(need == "admin" for (_, path), need in staff_desk.NEEDS.items() if "saved-command" in path)


@pytest.mark.parametrize("method, path, body", [
    ("POST", "/api/player-note-delete", {"name": "Alpha", "id": "x"}),
    ("GET", "/api/saved-commands", None),
    ("POST", "/api/saved-commands", {"label": "x", "command": "list"}),
    ("POST", "/api/saved-command-delete", {"id": "x"}),
    ("POST", "/api/folder", {"path": "config/new"}),
    ("POST", "/api/rename", {"path": "config/plain.yml", "to": "config/other.yml"}),
])
def test_a_moderator_is_refused_what_needs_an_admin(desk, method, path, body):
    code, answer = desk.call(method, path, body, headers=MOD)
    assert code == 403 and "role" in answer["error"] and actions(desk) == ""
    assert (desk.root / "config" / "plain.yml").exists() and not (desk.root / "config" / "new").exists()


def test_a_change_must_come_from_the_page(desk):
    for path, body in (("/api/player-notes", {"name": "Alpha", "text": "x"}), ("/api/folder", {"path": "config/n"}),
                       ("/api/rename", {"path": "config/plain.yml", "to": "config/o.yml"})):
        assert desk.call("POST", path, body, marked=False)[0] == 403
    assert actions(desk) == "" and not (desk.staff / "player-notes.json").exists()


# ---------------------------------------------------------------- everyone who has joined


def test_everyone_who_has_joined_is_listed_last_seen_first(desk):
    code, data = desk.call("GET", "/api/known-players", headers=MOD)
    assert code == 200 and data["total"] == 3 and data["world"] is True
    assert [p["name"] for p in data["players"]] == ["Bravo", "Alpha", "Carol"]     # Carol never joined: no time
    bravo, alpha, carol = data["players"]
    assert alpha == {"name": "Alpha", "last_seen": 1_800_000_000, "hours": 2.5, "notes": 0, "whitelisted": True,
                     "op": True, "banned": False}
    assert bravo["last_seen"] == 1_800_005_000 and bravo["hours"] is None          # a stats file that can't be read
    assert bravo["whitelisted"] is True and bravo["op"] is False                   # whitelist.json says "bravo"
    assert carol["last_seen"] is None and carol["hours"] is None


def test_it_reads_names_times_and_play_time_and_nothing_else_of_the_world(desk):
    (desk.root / "world" / "players" / "stats" / f"{ALPHA}.json").write_text(json.dumps(
        {"stats": {"minecraft:custom": {"minecraft:play_time": 72_000, "minecraft:deaths": 9}}, "seed": "s3cret"}))
    text = json.dumps(desk.call("GET", "/api/known-players")[1])
    assert "s3cret" not in text and "deaths" not in text and ALPHA not in text and "nbt" not in text


def test_play_time_is_read_again_only_when_the_file_changes(desk, monkeypatch):
    stats = desk.root / "world" / "players" / "stats" / f"{ALPHA}.json"
    read = []
    real = staff_desk._json
    monkeypatch.setattr(staff_desk, "_json", lambda path: (read.append(path.name), real(path))[1])
    desk.call("GET", "/api/known-players")
    desk.call("GET", "/api/known-players")
    assert read.count(stats.name) == 1
    stats.write_text(json.dumps({"stats": {"minecraft:custom": {"minecraft:play_time": 720_000}}}))
    os.utime(stats, (1_800_000_500, 1_800_000_500))
    alpha = next(p for p in desk.call("GET", "/api/known-players")[1]["players"] if p["name"] == "Alpha")
    assert alpha["hours"] == 10.0 and read.count(stats.name) == 2


@pytest.mark.parametrize("ticks", [True, -5, "many", None, 1.5])
def test_a_play_time_that_is_not_a_count_is_unknown(desk, ticks):
    (desk.root / "world" / "players" / "stats" / f"{ALPHA}.json").write_text(json.dumps(
        {"stats": {"minecraft:custom": {"minecraft:play_time": ticks}}}))
    alpha = next(p for p in desk.call("GET", "/api/known-players")[1]["players"] if p["name"] == "Alpha")
    assert alpha["hours"] is None


def test_a_server_with_no_world_or_usercache_yet_lists_nobody(box):  # noqa: F811
    code, data = box.call("GET", "/api/known-players")
    assert code == 200 and data == {"ok": True, "players": [], "total": 0, "world": False}
    (box.root / "usercache.json").write_text("{broken")
    assert box.call("GET", "/api/known-players")[1]["players"] == []


# ---------------------------------------------------------------- notes


def test_a_note_is_signed_kept_by_uuid_and_logged_without_its_text(desk):
    code, made = desk.call("POST", "/api/player-notes", {"name": "alpha", "text": "  warned  about\tspawn killing "},
                           user="mia", headers=MOD)
    assert code == 200 and made["note"]["text"] == "warned about spawn killing" and made["note"]["by"] == "mia"
    kept = json.loads((desk.staff / "player-notes.json").read_text())
    assert list(kept["notes"]) == [ALPHA]
    assert os.stat(desk.staff / "player-notes.json").st_mode & 0o077 == 0 or os.name == "nt"
    assert actions(desk).rstrip().endswith("mia player-note alpha") and "spawn" not in actions(desk)
    assert all("spawn" not in line for line in desk.posted)
    # The player changes name: the note is still theirs.
    cache = json.loads((desk.root / "usercache.json").read_text())
    cache[0]["name"] = "Alpha2"
    (desk.root / "usercache.json").write_text(json.dumps(cache))
    code, data = desk.call("GET", "/api/player-notes?name=Alpha2", headers=MOD)
    assert code == 200 and [n["text"] for n in data["notes"]] == ["warned about spawn killing"]
    assert desk.call("GET", "/api/player-notes?name=Alpha")[1]["notes"] == []
    assert next(p for p in desk.call("GET", "/api/known-players")[1]["players"] if p["name"] == "Alpha2")["notes"] == 1


def test_a_note_on_a_name_the_server_does_not_know_is_kept_by_name_and_found_later(desk):
    assert desk.call("POST", "/api/player-notes", {"name": "Zed", "text": "ban evader?"})[0] == 200
    assert list(json.loads((desk.staff / "player-notes.json").read_text())["notes"]) == ["name:zed"]
    cache = json.loads((desk.root / "usercache.json").read_text())
    (desk.root / "usercache.json").write_text(json.dumps([*cache, {"name": "Zed", "uuid": CAROL.replace("3", "9")}]))
    desk.call("POST", "/api/player-notes", {"name": "Zed", "text": "second"})
    notes = desk.call("GET", "/api/player-notes?name=Zed")[1]["notes"]
    assert sorted(n["text"] for n in notes) == ["ban evader?", "second"]
    for note in notes:                                  # either kind can be deleted
        assert desk.call("POST", "/api/player-note-delete", {"name": "Zed", "id": note["id"]})[0] == 200
    assert json.loads((desk.staff / "player-notes.json").read_text())["notes"] == {}
    assert desk.call("POST", "/api/player-note-delete", {"name": "Zed", "id": notes[0]["id"]})[0] == 404


@pytest.mark.parametrize("body", [
    {"name": "Al", "text": "x"}, {"name": "Alpha;stop", "text": "x"}, {"name": 7, "text": "x"}, {"text": "x"},
    {"name": "Alpha", "text": ""}, {"name": "Alpha", "text": "   "}, {"name": "Alpha", "text": 5},
    {"name": "Alpha", "text": "x" * (staff_desk.NOTE_MAX + 1)}, {"name": "Alpha", "text": "bell\x07"},
])
def test_a_bad_note_is_refused(desk, body):
    assert desk.call("POST", "/api/player-notes", body)[0] == 400
    assert not (desk.staff / "player-notes.json").exists() and actions(desk) == ""


def test_notes_have_a_limit_and_a_broken_file_is_never_written_over(desk):
    for i in range(staff_desk.NOTES_EACH):
        assert desk.call("POST", "/api/player-notes", {"name": "Alpha", "text": f"note {i}"})[0] == 200
    assert desk.call("POST", "/api/player-notes", {"name": "Alpha", "text": "one more"})[0] == 409
    newest = desk.call("GET", "/api/player-notes?name=Alpha")[1]["notes"]
    assert len(newest) == staff_desk.NOTES_EACH and newest[0]["at"] >= newest[-1]["at"]
    (desk.staff / "player-notes.json").write_text("{broken")
    assert desk.call("POST", "/api/player-notes", {"name": "Alpha", "text": "x"})[0] == 500
    assert desk.call("POST", "/api/player-note-delete", {"name": "Alpha", "id": "x"})[0] == 500
    assert (desk.staff / "player-notes.json").read_text() == "{broken"
    assert desk.call("GET", "/api/player-notes?name=Alpha")[1]["notes"] == []      # reading it only shows none


# ---------------------------------------------------------------- saved commands


def test_a_saved_command_is_checked_as_the_console_checks_it(desk):
    for command in ("seed", "/stop", "execute as @a run seed", "op", "say a\nsay b", ""):
        assert desk.call("POST", "/api/saved-commands", {"label": "x", "command": command})[0] in (400, 403)
    assert not (desk.staff / "commands.json").exists() and desk.docker.calls == []
    code, made = desk.call("POST", "/api/saved-commands", {"label": " Vote  reminder ", "command": "/say Vote today!"},
                           headers=ADMIN)
    assert code == 200 and made["command"]["label"] == "Vote reminder"
    assert made["command"]["command"] == "say Vote today!"
    assert desk.docker.calls == []                      # saving runs nothing
    assert "diego saved-command-add Vote reminder: say Vote today!" in actions(desk)
    assert desk.call("POST", "/api/saved-commands", {"label": "vote REMINDER", "command": "list"})[0] == 409
    _, listed = desk.call("GET", "/api/saved-commands", headers=ADMIN)
    shown = [(c["label"], c["command"], c["by"]) for c in listed["commands"]]
    assert shown == [("Vote reminder", "say Vote today!", "diego")]
    assert desk.call("POST", "/api/saved-command-delete", {"id": made["command"]["id"]})[0] == 200
    assert desk.call("POST", "/api/saved-command-delete", {"id": made["command"]["id"]})[0] == 404
    assert desk.call("GET", "/api/saved-commands")[1]["commands"] == []


def test_a_secret_in_a_saved_command_stays_out_of_the_log(desk):
    desk.call("POST", "/api/saved-commands", {"label": "x", "command": "say the password is hunter2"})
    assert "hunter2" not in actions(desk) and all("hunter2" not in line for line in desk.posted)


@pytest.mark.parametrize("label", ["", "  ", 5, None, "x" * (staff_desk.LABEL_MAX + 1), "a\x00b"])
def test_a_saved_command_needs_a_plain_label(desk, label):
    assert desk.call("POST", "/api/saved-commands", {"label": label, "command": "list"})[0] == 400


def test_saved_commands_have_a_limit_and_a_broken_file_is_never_written_over(desk):
    for i in range(staff_desk.COMMANDS_MAX):
        assert desk.call("POST", "/api/saved-commands", {"label": f"c{i}", "command": "list"})[0] == 200
    assert desk.call("POST", "/api/saved-commands", {"label": "more", "command": "list"})[0] == 409
    (desk.staff / "commands.json").write_text('{"commands": 3}')
    assert desk.call("POST", "/api/saved-commands", {"label": "y", "command": "list"})[0] == 500
    assert desk.call("POST", "/api/saved-command-delete", {"id": "x"})[0] == 500
    assert (desk.staff / "commands.json").read_text() == '{"commands": 3}'
    assert desk.call("GET", "/api/saved-commands")[1]["commands"] == []


# ---------------------------------------------------------------- the record of changes


def log(desk, lines):
    desk.staff.mkdir(parents=True, exist_ok=True)
    (desk.staff / "actions.log").write_text("".join(f"{line}\n" for line in lines))


def test_the_changes_can_be_searched_by_login_action_and_text(desk):
    log(desk, ["2026-11-01T10:00:00Z diego command say hi", "2026-11-01T10:01:00Z mia save config/plain.yml",
               "2026-11-01T10:02:00Z diego save config/Other.toml", "junk", "2026-11-01T10:03:00Z mia power"])
    code, data = desk.call("GET", "/api/activity", headers=MOD)
    assert code == 200 and [a["action"] for a in data["actions"]] == ["power", "save", "save", "command"]
    assert data["users"] == ["diego", "mia"] and data["kinds"] == ["command", "power", "save"]
    assert data["more"] is None and data["cut"] is False
    found = desk.call("GET", "/api/activity?user=diego&action=save")[1]["actions"]
    assert [a["target"] for a in found] == ["config/Other.toml"]
    assert [a["user"] for a in desk.call("GET", "/api/activity?q=OTHER")[1]["actions"]] == ["diego"]
    assert desk.call("GET", "/api/activity?q=nothing")[1]["actions"] == []
    for bad in ("user=a%20b", "action=x;y", f"q={'x' * 101}", "before=abc"):
        assert desk.call("GET", f"/api/activity?{bad}")[0] == 400


def test_older_changes_come_a_page_at_a_time_without_a_gap_or_a_repeat(desk):
    log(desk, [f"2026-11-01T10:00:00Z diego command say {i}" for i in range(250)])
    seen, before = [], ""
    for _ in range(5):
        data = desk.call("GET", f"/api/activity?before={before}")[1]
        seen += [a["target"] for a in data["actions"]]
        before = data["more"]
        if before is None:
            break
    assert seen == [f"say {i}" for i in reversed(range(250))]


def test_a_long_log_is_read_from_its_end_and_says_so(desk, monkeypatch):
    monkeypatch.setattr(staff_desk, "ACTIVITY_READ", 200)
    log(desk, [f"2026-11-01T10:00:00Z diego command say {i:03d}" for i in range(50)])
    data = desk.call("GET", "/api/activity")[1]
    assert data["cut"] is True and data["actions"][0]["target"] == "say 049"
    assert all(a["time"] == "2026-11-01T10:00:00Z" and a["target"].startswith("say ") for a in data["actions"])


def test_the_changes_as_a_csv_file_with_no_formulas(desk):
    log(desk, ["2026-11-01T10:00:00Z diego command =HYPERLINK(1)", "2026-11-01T10:01:00Z mia command say \"hi\", all",
               "2026-11-01T10:02:00Z mia save -x.yml"])
    code, raw = desk.call("GET", "/api/activity-export?action=command", headers=MOD)
    rows = list(csv.reader(io.StringIO(raw.decode())))
    assert code == 200 and rows[0] == ["time (UTC)", "login", "action", "what"]
    assert rows[1:] == [["2026-11-01T10:01:00Z", "mia", "command", 'say "hi", all'],
                        ["2026-11-01T10:00:00Z", "diego", "command", "'=HYPERLINK(1)"]]
    saved = desk.call("GET", "/api/activity-export?user=mia&action=save")[1].decode()
    assert list(csv.reader(io.StringIO(saved)))[1][3] == "'-x.yml"
    assert desk.call("GET", "/api/activity-export?user=a%20b")[0] == 400


def test_no_log_yet_is_no_changes(desk):
    assert desk.call("GET", "/api/activity")[1]["actions"] == []
    assert desk.call("GET", "/api/activity-export")[1].decode().count("\n") == 1


# ---------------------------------------------------------------- files: a new folder, a new name


def test_a_new_folder(desk):
    code, made = desk.call("POST", "/api/folder", {"path": "config/extra"}, headers=ADMIN)
    assert code == 200 and made["path"] == "config/extra" and (desk.root / "config" / "extra").is_dir()
    assert "diego new-folder config/extra" in actions(desk)
    assert desk.call("POST", "/api/folder", {"path": "config/extra"})[0] == 409
    assert desk.call("POST", "/api/folder", {"path": "config/plain.yml"})[0] == 409


@pytest.mark.parametrize("path, code", [
    ("", 400), ("config/has space", 400), ("config/a$b", 400), ("../out", 400), ("/abs", 400),
    ("world/new", 403), ("world_nether/x", 403), ("logs/new", 403), ("libraries/x", 403), ("config/x.db", 403),
    ("nowhere/deep/new", 404),
])
def test_a_new_folder_stays_inside_what_the_page_may_write(desk, path, code):
    assert desk.call("POST", "/api/folder", {"path": path})[0] == code
    assert actions(desk) == ""


def test_a_file_gets_a_new_name_or_folder_and_nothing_is_replaced(desk):
    code, done = desk.call("POST", "/api/rename", {"path": "config/plain.yml", "to": "config/plain.yml.off"},
                           headers=ADMIN)
    assert code == 200 and done == {"ok": True, "path": "config/plain.yml.off", "from": "config/plain.yml"}
    assert (desk.root / "config" / "plain.yml.off").read_text() == "a: 1\n"
    assert not (desk.root / "config" / "plain.yml").exists()
    assert "diego rename config/plain.yml to config/plain.yml.off" in actions(desk)
    # Into another folder.
    assert desk.call("POST", "/api/rename", {"path": "config/plain.yml.off", "to": "plain.yml"})[0] == 200
    # A name already taken, by a file or a folder, is refused: a rename never loses a file.
    assert desk.call("POST", "/api/rename", {"path": "plain.yml", "to": "config/discord.toml"})[0] == 409
    assert desk.call("POST", "/api/rename", {"path": "plain.yml", "to": "config"})[0] == 409
    assert (desk.root / "plain.yml").read_text() == "a: 1\n"
    assert "tok-real" in (desk.root / "config" / "discord.toml").read_text()


@pytest.mark.parametrize("path, to, code", [
    ("config/plain.yml", "config/has space.yml", 400), ("config/plain.yml", "../plain.yml", 400),
    ("config/plain.yml", "", 400), ("config/plain.yml", 7, 400), ("config", "config2", 400),
    ("config/missing.yml", "config/x.yml", 400), ("config/plain.yml", "nowhere/x.yml", 404),
    ("config/plain.yml", "world/x.yml", 403), ("world/level.dat", "level.dat", 403),
    ("config/plain.yml", "logs/x.log", 403), ("logs/latest.log", "config/latest.log", 403),
    ("config/plain.yml", "config/x.db", 403), ("claims.db", "claims.txt", 403),
])
def test_a_rename_stays_inside_what_the_page_may_write(desk, path, to, code):
    assert desk.call("POST", "/api/rename", {"path": path, "to": to})[0] == code
    assert (desk.root / "config" / "plain.yml").exists() and actions(desk) == ""


@pytest.mark.parametrize("path, to", [
    ("config/plain.yml", "mods/plain.yml"), ("config/plain.yml", "config/plain.jar"), ("mods/a.jar", "config/a.txt"),
    ("mods/a.jar", "mods/a.jar.disabled"), ("config/plain.yml", "server.properties"),
    ("server.properties", "server.properties.old"), ("config/plain.yml", ".fabric/x"),
])
def test_only_an_owner_renames_code_or_server_properties(desk, path, to):
    (desk.root / ".fabric").mkdir()
    code, answer = desk.call("POST", "/api/rename", {"path": path, "to": to}, headers=ADMIN)
    assert code == 403 and "owner" in answer["error"] and actions(desk) == ""
    assert (desk.root / "config" / "plain.yml").exists() and (desk.root / "mods" / "a.jar").exists()


def test_an_admin_cannot_make_a_folder_where_code_runs_but_an_owner_can(desk):
    assert desk.call("POST", "/api/folder", {"path": "mods/sub"}, headers=ADMIN)[0] == 403
    assert desk.call("POST", "/api/folder", {"path": "mods/sub"})[0] == 200


@pytest.mark.skipif(os.name == "nt", reason="needs symlinks")
def test_a_rename_through_a_link_cannot_leave_the_server_folder_or_reach_code(desk):
    os.symlink(desk.tmp, desk.root / "config" / "out")
    os.symlink(desk.root / "mods", desk.root / "config" / "m")
    assert desk.call("POST", "/api/rename", {"path": "config/plain.yml", "to": "config/out/x.yml"})[0] == 403
    assert desk.call("POST", "/api/rename", {"path": "config/out/outside.txt", "to": "config/got.txt"})[0] == 403
    into_mods = {"path": "config/plain.yml", "to": "config/m/x.yml"}
    assert desk.call("POST", "/api/rename", into_mods, headers=ADMIN)[0] == 403
    assert (desk.tmp / "outside.txt").read_text() == "outside secret" and (desk.root / "config" / "plain.yml").exists()


# ---------------------------------------------------------------- the page


def test_the_page_has_every_element_the_scripts_use():
    page = REPO.root / "deploy" / "staff"
    html = (page / "index.html").read_text(encoding="utf-8")
    assert '<script src="desk.js" defer></script>' in html
    ids = set(re.findall(r'id="([a-z0-9-]+)"', html))
    for name in ("desk.js", "panel.js", "staff.js"):
        script = (page / name).read_text(encoding="utf-8")
        used = set(re.findall(r'\$\("([a-z0-9-]+)"\)', script))
        assert used <= ids, (name, used - ids)
        code = "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("//"))
        assert "innerHTML" not in code and not re.search(r"\b(confirm|alert)\(", code)
        assert not re.search(r"\.style\.|setAttribute\(\s*[\"']style", code)
    script = (page / "desk.js").read_text(encoding="utf-8")
    for _, path in staff_desk.ROUTES:
        assert path in script
    # Every id is on the page once.
    every = re.findall(r'id="([a-z0-9-]+)"', html)
    assert len(every) == len(set(every)), sorted({i for i in every if every.count(i) > 1})


def test_the_consoles_chat_view_knows_the_games_chat_lines():
    """The patterns in panel.js, checked here against lines as the game writes them (Python's re reads them alike)."""
    script = (REPO.root / "deploy" / "staff" / "panel.js").read_text(encoding="utf-8")
    head = re.compile(re.search(r"const LOG_HEAD = /(.*)/;", script).group(1))
    chat = re.compile(re.search(r"const CHAT = /(.*)/;", script).group(1))
    said = {
        "[12:00:00] [Server thread/INFO]: <Alpha> hello all": True,
        "[12:00:00] [Server thread/INFO]: [Not Secure] <Alpha> hi": True,
        "[12:00:00] [Server thread/INFO]: [Server] Restart in 5 minutes": True,
        "[12:00:00] [Server thread/INFO]: Alpha joined the game": True,
        "[12:00:00] [Server thread/INFO]: Alpha left the game": True,
        "[12:00:00] [Server thread/INFO]: Done (12.3s)! For help, type \"help\"": False,
        "[12:00:00] [Server thread/INFO] [luckperms]: [Alpha] something": True,
        "[12:00:00] [Server thread/WARN]: Can't keep up!": False,
    }
    for line, is_chat in said.items():
        m = head.match(line)
        assert m, line
        assert bool(chat.search(m.group(2))) is is_chat, line
    assert head.match("[12:00:00] [Worker-Main-1/ERROR]: boom").group(1) == "ERROR"
    assert head.match("\tat net.minecraft.Foo.bar(Foo.java:1)") is None
