"""tools/staff_lookup.py: the console for moderators (an allowed list), block history from Ledger, the mod update
check and one player's history."""
import datetime as dt
import hashlib
import json

import pytest
import staff_lookup
import staff_panel
from test_staff_desk import ALPHA, desk  # noqa: F401 (desk is the fixture: box with players who have joined)
from test_staff_panel import actions, box  # noqa: F401
from test_staff_report import ledger, place

from repo import REPO

MOD, ADMIN = {"X-Staff-Role": "moderator"}, {"X-Staff-Role": "admin"}


# ---------------------------------------------------------------- who may ask


def test_every_route_names_who_may_use_it():
    for key in staff_lookup.ROUTES:
        assert staff_panel.ROUTES[key] is staff_lookup.ROUTES[key] and staff_lookup.NEEDS[key] in staff_panel.ROLES
    assert staff_lookup.NEEDS[("PUT", "/api/mod-commands")] == "owner"
    assert staff_lookup.NEEDS[("GET", "/api/mod-updates")] == "admin"


@pytest.mark.parametrize("method, path, body", [
    ("PUT", "/api/mod-commands", {"commands": ["list"]}),
    ("GET", "/api/mod-updates", None),
])
def test_a_moderator_is_refused_what_needs_more(box, method, path, body):  # noqa: F811
    assert box.call(method, path, body, headers=MOD)[0] == 403


def test_an_admin_cannot_change_the_moderators_list(box):  # noqa: F811
    assert box.call("PUT", "/api/mod-commands", {"commands": ["give"]}, headers=ADMIN)[0] == 403
    assert not (box.staff / "mod-commands.json").exists()


# ---------------------------------------------------------------- the console for moderators


def test_a_moderator_runs_only_the_allowed_commands(box):  # noqa: F811
    code, answer = box.call("POST", "/api/command", {"command": "list"}, headers=MOD)
    assert code == 200 and "Alpha" in answer["output"]
    code, answer = box.call("POST", "/api/command", {"command": "/whitelist list"}, headers=MOD)
    assert code == 200
    for refused in ("op Alpha", "whitelist off", "give Alpha diamond", "execute run op Alpha", "minecraft:op Alpha",
                    "time set day"):
        code, answer = box.call("POST", "/api/command", {"command": refused}, headers=MOD)
        assert code == 403 and "moderator login can run only" in answer["error"], refused
    sent = [c[-1] for c in box.docker.calls if "exec" in c]
    assert sent == ["list", "whitelist list"]
    assert "command list" in actions(box) and "op Alpha" not in actions(box)


def test_the_consoles_own_checks_still_come_first_for_a_moderator(box):  # noqa: F811
    box.call("PUT", "/api/mod-commands", {"commands": ["list", "kick"]})
    assert box.call("POST", "/api/command", {"command": "kick"}, headers=MOD)[0] == 400       # no name
    code, answer = box.call("POST", "/api/command", {"command": "seed"}, headers=MOD)
    assert code == 403 and "secret" in answer["error"]


def test_admins_and_owners_use_the_console_as_before(box):  # noqa: F811
    assert box.call("POST", "/api/command", {"command": "time set day"}, headers=ADMIN)[0] == 200


def test_the_owner_sets_the_list_and_it_is_logged(box):  # noqa: F811
    code, answer = box.call("GET", "/api/mod-commands", headers=MOD)
    assert code == 200 and answer["default"] and "kick" in answer["commands"]
    assert "kick" in answer["can_allow"] and "op" not in answer["can_allow"]
    code, answer = box.call("PUT", "/api/mod-commands", {"commands": ["/Time Set", "time set", " tp ", ""]})
    assert code == 200 and answer["commands"] == ["time set", "tp"]
    assert box.call("GET", "/api/mod-commands", headers=MOD)[1]["commands"] == ["time set", "tp"]
    assert box.call("POST", "/api/command", {"command": "time set day"}, headers=MOD)[0] == 200
    assert box.call("POST", "/api/command", {"command": "list"}, headers=MOD)[0] == 403
    assert "mod-commands time set, tp" in actions(box)


# setblock, give, data and the rest can make a command block, which runs as the server; tellraw's, team's and
# bossbar's text can carry a click that runs a command as whoever clicks it. Anything not known is refused too.
@pytest.mark.parametrize("entries", [["execute"], ["minecraft:op"], ["reload"], ["banlist ips"], ["a b c d"],
                                     ["semi;colon"], "list", [1], ["x"] * 41, ["setblock"], ["give"],
                                     ["minecraft:data"], ["summon"], ["fill"], ["clone"], ["place"], ["item"],
                                     ["loot"], ["tellraw"], ["dialog"], ["team modify"], ["bossbar set"],
                                     ["scoreboard objectives"], ["title"], ["some_mod_command"]])
def test_commands_that_lift_a_moderator_can_never_be_allowed(box, entries):  # noqa: F811
    assert box.call("PUT", "/api/mod-commands", {"commands": entries})[0] == 400
    assert not (box.staff / "mod-commands.json").exists()


def test_a_broken_list_allows_nothing(box):  # noqa: F811
    box.staff.mkdir(parents=True, exist_ok=True)
    (box.staff / "mod-commands.json").write_text("{broken")
    assert box.call("POST", "/api/command", {"command": "list"}, headers=MOD)[0] == 403
    (box.staff / "mod-commands.json").write_text(json.dumps({"commands": ["list", "op", "execute as",
                                                                       "minecraft:execute run", "give"]}))
    assert box.call("GET", "/api/mod-commands", headers=MOD)[1]["commands"] == ["list"]


def test_allows_matches_whole_words_only():
    rows = ["whitelist add", "w"]
    assert staff_lookup.allows(rows, "whitelist add Alpha") and staff_lookup.allows(rows, "w Alpha hi")
    assert not staff_lookup.allows(rows, "whitelist addx Alpha") and not staff_lookup.allows(rows, "whitelist")
    assert not staff_lookup.allows(rows, "weather clear") and not staff_lookup.allows(["op"], "op Alpha")


# ---------------------------------------------------------------- block history


NOW = dt.datetime(2026, 11, 10, 12, 0, 0)


def _db(box, rows):  # noqa: F811
    path = box.root / "world" / "ledger.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger(path, rows)
    return path


def look(box, **query):  # noqa: F811
    return staff_lookup.block_history(box.panel, {k: str(v) for k, v in query.items()}, now=NOW)


def test_block_history_lists_who_changed_what_newest_first(box):  # noqa: F811
    _db(box, [
        place("2026-11-10 09:00:00", "Alpha", "chest", 10, 64, 10),
        ("2026-11-10 10:00:00", "item-remove", 10, 64, 10, "overworld", "diamond", None, "player", "Bravo", None),
        ("2026-11-10 11:00:00", "block-break", 12, 65, 9, "overworld", "air", "stone", "player", "Carol", None),
        ("2026-11-10 11:30:00", "block-place", 10, 64, 10, "overworld", "light", "air", "command", None, None),
        place("2026-11-10 11:00:00", "Dan", "dirt", 30, 64, 10),                       # outside the box
        place("2026-11-10 11:00:00", "Eve", "dirt", 10, 64, 10, world="the_nether"),   # another world
        place("2026-11-01 11:00:00", "Eve", "dirt", 10, 64, 10),                       # too long ago
    ])
    found = look(box, x=10, y=64, z=10, radius=2, hours=24)
    assert [r["who"] for r in found["rows"]] == ["Carol", "Bravo", "Alpha"]
    assert found["rows"][0] == {"time": "2026-11-10 11:00:00", "action": "block-break", "who": "Carol",
                                "object": "air", "old": "stone", "x": 12, "y": 65, "z": 9, "rolled_back": False}
    assert not found["stopped"] and not found["more"]
    assert [r["who"] for r in look(box, x=10, y=64, z=10, radius=2, hours=24, kind="containers")["rows"]] == ["Bravo"]
    assert [r["who"] for r in look(box, x=10, y=64, z=10, radius=2, hours=24, player="alpha")["rows"]] == ["Alpha"]
    assert [r["who"] for r in look(box, x=10, y=64, z=10, world="Nether")["rows"]] == ["Eve"]
    assert look(box, x=10, y=64, z=10, player="Nobody")["rows"] == []


@pytest.mark.parametrize("query", [{"x": 1, "y": 1}, {"x": 1, "y": 1, "z": 1, "radius": 9},
                                   {"x": "1.5", "y": 1, "z": 1}, {"x": 1, "y": 1, "z": 1, "hours": 0},
                                   {"x": 1, "y": 1, "z": 1, "kind": "drop table"},
                                   {"x": 1, "y": 1, "z": 1, "world": "Moon"},
                                   {"x": 1, "y": 1, "z": 1, "player": "bad name!"}])
def test_block_history_refuses_a_bad_question(box, query):  # noqa: F811
    _db(box, [])
    with pytest.raises(staff_panel.Refused) as e:
        look(box, **query)
    assert e.value.code == 400


def test_block_history_never_reads_the_whole_table(box):  # noqa: F811
    with pytest.raises(staff_panel.Refused) as e:
        look(box, x=1, y=1, z=1)
    assert e.value.code == 404
    path = _db(box, [])
    import sqlite3
    db = sqlite3.connect(path)
    db.execute("drop index actions_by_location")
    db.commit()
    db.close()
    with pytest.raises(staff_panel.Refused) as e:
        look(box, x=1, y=1, z=1)
    assert e.value.code == 503 and "location index" in e.value.message


def test_block_history_stops_at_its_limit_and_says_so(box, monkeypatch):  # noqa: F811
    monkeypatch.setattr(staff_lookup, "LOOKUP_ROWS", 3)
    _db(box, [place(f"2026-11-10 10:00:0{i}", "Alpha", "dirt", 5, 64, i) for i in range(8)])
    found = look(box, x=5, y=64, z=4, radius=4)
    assert len(found["rows"]) == 3 and found["more"]
    assert [r["z"] for r in found["rows"]] == [7, 6, 5]


def test_block_history_reads_the_asked_block_before_the_edges(box, monkeypatch):  # noqa: F811
    # A busy column at the box's edge must not use up the cap before the asked block is read.
    monkeypatch.setattr(staff_lookup, "LOOKUP_ROWS", 2)
    _db(box, [*(place(f"2026-11-10 10:00:{i:02d}", "Alpha", "dirt", 0, 64, 5) for i in range(12)),
              place("2026-11-10 09:00:00", "Bravo", "tnt", 4, 64, 5)])
    assert look(box, x=4, y=64, z=5, radius=4)["stopped"]
    import staff_report
    ledger = staff_report.Ledger(box.root / "world" / "ledger.sqlite")
    rows, stopped = staff_lookup._lookup(ledger, 4, 64, 5, 4, ledger.world_id("Overworld"), "2026-11-01 00:00:00",
                                         -1, None, None)
    ledger.db.close()
    assert stopped and ledger.players[rows[0][7]] == "Bravo"   # the asked block's column was read first


def test_block_history_over_http_is_a_moderators(box):  # noqa: F811
    _db(box, [place("2026-11-10 09:00:00", "Alpha", "chest", 10, 64, 10)])
    code, answer = box.call("GET", "/api/block-history?x=10&y=64&z=10&hours=720", headers=MOD)
    assert code == 200 and answer["box"]["world"] == "Overworld"


# ---------------------------------------------------------------- mod updates


def _jar(box, name, data):  # noqa: F811
    (box.root / "mods" / name).write_bytes(data)
    return hashlib.sha512(data).hexdigest()


def test_mod_updates_ask_modrinth_by_hash_and_list_only_newer_files(box, monkeypatch):  # noqa: F811
    import staff_host
    monkeypatch.setattr(staff_host.Host, "game_version", lambda self: "26.2")
    old, same = _jar(box, "lithium-0.1.jar", b"old lithium"), _jar(box, "ledger-1.jar", b"ledger")
    _jar(box, "off.jar.disabled", b"off")
    asked = []

    def post(url, body):
        asked.append((url, body))
        return {old: {"id": "VER1", "project_id": "gvQqBUqZ", "version_number": "0.2", "version_type": "release",
                      "name": "Lithium 0.2", "date_published": "2026-11-01T00:00:00Z",
                      "files": [{"primary": True, "filename": "lithium-0.2.jar", "hashes": {"sha512": "f" * 128}}]},
                same: {"id": "VER2", "project_id": "LEDGER12", "version_number": "1",
                       "files": [{"primary": True, "filename": "ledger-1.jar", "hashes": {"sha512": same}}]}}

    updates = staff_lookup.updates(box.panel)
    updates.post = post
    updates.get = lambda url: [{"id": "gvQqBUqZ", "slug": "lithium"}]
    code, answer = box.call("GET", "/api/mod-updates", headers=ADMIN)
    assert code == 200 and answer["checked"] == 3 and answer["game"] == "26.2" and not answer["cached"]
    assert [(u["jar"], u["version"], u["slug"]) for u in answer["updates"]] == [("lithium-0.1.jar", "0.2", "lithium")]
    assert answer["updates"][0]["url"] == "https://modrinth.com/mod/lithium/changelog"
    url, body = asked[0]
    assert url.endswith("/version_files/update") and body["algorithm"] == "sha512" and body["loaders"] == ["fabric"]
    assert set(body["hashes"]) >= {old, same} and body["game_versions"] == ["26.2"]
    assert box.call("GET", "/api/mod-updates", headers=ADMIN)[1]["cached"] and len(asked) == 1
    assert not box.call("GET", "/api/mod-updates?fresh=1", headers=ADMIN)[1]["cached"] and len(asked) == 2


def test_only_modrinths_api_is_posted_to(box):  # noqa: F811
    with pytest.raises(staff_panel.Refused):
        staff_lookup.post_json("https://example.com/v2/version_files/update", {})


# ---------------------------------------------------------------- one player's history


def test_a_players_history_brings_their_lists_ban_notes_and_changes_together(desk):  # noqa: F811
    desk.call("POST", "/api/player-notes", {"name": "Alpha", "text": "warned for spam"}, headers=MOD)
    desk.call("POST", "/api/command", {"command": "kick Alpha spam"})
    desk.call("POST", "/api/command", {"command": "kick Alphabet"})
    (desk.root / "banned-players.json").write_text(json.dumps([{"uuid": ALPHA, "name": "Alpha", "reason": "grief"}]))
    code, answer = desk.call("GET", "/api/player-history?name=alpha", headers=MOD)
    assert code == 200 and answer["name"] == "Alpha" and answer["known"] and answer["hours"] == 2.5
    assert answer["whitelisted"] and answer["op"] and answer["ban"]["reason"] == "grief"
    assert [n["text"] for n in answer["notes"]] == ["warned for spam"]
    assert [c["action"] for c in answer["changes"]] == ["command", "player-note"]
    assert desk.call("GET", "/api/player-history?name=bad!", headers=MOD)[0] == 400


# ---------------------------------------------------------------- the page


def test_the_page_has_every_element_lookup_js_uses():
    import re
    page = REPO.root / "deploy" / "staff"
    html = (page / "index.html").read_text(encoding="utf-8")
    assert '<script src="lookup.js" defer></script>' in html
    ids = set(re.findall(r'id="([a-z0-9-]+)"', html))
    script = (page / "lookup.js").read_text(encoding="utf-8")
    used = set(re.findall(r'\$\("([a-z0-9-]+)"\)', script))
    assert used <= ids, used - ids
    code = "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("//"))
    assert "innerHTML" not in code and not re.search(r"\b(confirm|alert)\(", code)
    assert not re.search(r"\.style\.|setAttribute\(\s*[\"']style", code)
    for _, path in staff_lookup.ROUTES:
        assert path in script
