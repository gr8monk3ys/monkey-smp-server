"""tools/staff_players.py: the player actions, Strength, the faction prize and the stat reset on the staff page, and
deploy/staff/players.js."""
import json
import re

import pytest
import staff_events
import staff_panel
import staff_players
from fake_world import FakeWorld, member
from test_staff_panel import actions, box, history_files  # noqa: F401 (box is a fixture)

from rcon import RconError
from repo import REPO

ALPHA = "11111111-1111-1111-1111-111111111111"
BRAVO = "22222222-2222-2222-2222-222222222222"
CHARLIE = "33333333-3333-3333-3333-333333333333"
ZED = "44444444-4444-4444-4444-444444444444"
STRENGTH = staff_players.STRENGTH


class FakeServer:
    """What these controls send over RCON, answered as a 26.2 server with Strength SMP answers it (the answers' words
    were read off a local 26.2 server)."""

    def __init__(self, root):
        self.root = root
        self.sent: list[str] = []
        self.online = ["Alpha", "Bravo"]
        self.scores: dict[str, int] = {"Alpha": 3, "Bravo": 5}
        self.mod = True
        self.up = True

    def __call__(self, command, timeout=None):
        self.sent.append(command)
        if not self.up:
            raise RconError(f"{command} answered: nothing (exit 1)")
        if command == "list":
            return f"There are {len(self.online)} of a max of 30 players online: {', '.join(self.online)}"
        m = re.fullmatch(r"scoreboard players (get|set|add) (\w+) (\S+)(?: (-?\d+))?", command)
        if m:
            how, name, objective, value = m.groups()
            assert objective == STRENGTH
            if not self.mod:
                return f"Unknown scoreboard objective '{objective}'"
            if how == "get":
                if name not in self.scores:
                    return f"Can't get value of {objective} for {name}; none is set"
                return f"{name} has {self.scores[name]} [Strength Level]"
            self.scores[name] = int(value) + (self.scores.get(name, 0) if how == "add" else 0)
            return f"Set [Strength Level] for {name} to {self.scores[name]}"
        if command.startswith("attribute "):
            return "Removed modifier"
        m = re.fullmatch(r"kick (\w+)(?: (.*))?", command)
        if m:
            if m[1] not in self.online:
                return "No player was found"
            self.online.remove(m[1])
            return f"Kicked {m[1]}: {m[2] or 'Kicked by an operator'}"
        m = re.fullmatch(r"(ban|pardon) (\w+)(?: (.*))?", command)
        if m:
            path = self.root / "banned-players.json"
            rows = json.loads(path.read_text())
            if m[1] == "ban":
                rows.append({"uuid": "x", "name": m[2], "reason": m[3] or "Banned by an operator."})
                said = f"Banned {m[2]}: {m[3] or 'Banned by an operator.'}"
            else:
                rows = [r for r in rows if r["name"] != m[2]]
                said = f"Unbanned {m[2]}"
            path.write_text(json.dumps(rows))
            return said
        m = re.fullmatch(r"execute in minecraft:overworld run tp (\w+) ~0\.5 ~ ~0\.5", command)
        if m:
            return f"Teleported {m[1]} to 0.5, 64.0, 0.5" if m[1] in self.online else "No entity was found"
        raise AssertionError(command)


def stats(kills=4, deaths=7) -> dict:
    return {"stats": {"minecraft:custom": {"minecraft:player_kills": kills, "minecraft:deaths": deaths,
                                           "minecraft:jump": 99},
                      "minecraft:killed": {"minecraft:player": kills, "minecraft:zombie": 3},
                      "minecraft:killed_by": {"minecraft:player": deaths}},
            "DataVersion": 4903}


@pytest.fixture
def pl(box):  # noqa: F811
    root = box.root
    (root / "usercache.json").write_text(json.dumps([
        {"name": "Alpha", "uuid": ALPHA, "expiresOn": "x"}, {"name": "Bravo", "uuid": BRAVO, "expiresOn": "x"},
        {"name": "Charlie", "uuid": CHARLIE, "expiresOn": "x"}, {"name": "Zed", "uuid": ZED, "expiresOn": "x"}]))
    folder = root / "world" / "players" / "stats"
    folder.mkdir(parents=True)
    (folder / f"{CHARLIE}.json").write_text(json.dumps(stats()))
    fake = FakeServer(root)
    staff_events.events(box.panel).rcon = fake
    box.server = fake
    return box


def post(pl, body, role="admin"):
    return pl.call("POST", "/api/player", body, role=role)


# ---------------------------------------------------------------- who may ask


def test_every_route_is_admin_and_registered():
    for key in staff_players.ROUTES:
        assert staff_panel.ROUTES[key] is staff_players.ROUTES[key]
        assert staff_panel.NEEDS[key] == "admin"
        assert key[1] in staff_panel.PATHS


@pytest.mark.parametrize("method, path, body", [
    ("GET", "/api/player?name=Alpha", None),
    ("POST", "/api/player", {"action": "kick", "name": "Alpha"}),
    ("GET", "/api/factions", None),
    ("POST", "/api/faction-strength", {"party": "p"}),
])
def test_a_moderator_is_refused(pl, method, path, body):
    code, _ = pl.call(method, path, body, role="moderator")
    assert code == 403 and pl.server.sent == [] and actions(pl) == ""


# ---------------------------------------------------------------- one player


def test_a_player_is_looked_up_by_the_name_the_server_knows(pl):
    code, data = pl.call("GET", "/api/player?name=alpha", role="admin")
    assert code == 200
    assert data["player"] == {"name": "Alpha", "uuid": ALPHA, "online": True, "banned": False, "strength": 3,
                              "start": 3, "most": 5}
    assert pl.call("GET", "/api/player?name=Zed", role="admin")[1]["player"]["banned"] is True
    assert pl.call("GET", "/api/player?name=Charlie", role="admin")[1]["player"]["strength"] is None


@pytest.mark.parametrize("name, code", [("Nobody", 404), ("a", 400), ("@a", 400), ("Alpha extra", 400), (5, 400)])
def test_a_name_the_server_doesnt_know_is_refused(pl, name, code):
    got, data = post(pl, {"action": "kick", "name": name})
    assert got == code and data["ok"] is False
    assert pl.server.sent == [] and actions(pl) == ""


def test_an_unknown_action_is_refused(pl):
    assert post(pl, {"action": "op", "name": "Alpha"})[0] == 400 and pl.server.sent == []


def test_kick_with_a_reason(pl):
    code, data = post(pl, {"action": "kick", "name": "ALPHA", "reason": "  go   to bed "})
    assert code == 200 and data["player"]["online"] is False
    assert "kick Alpha go to bed" in pl.server.sent
    assert "player-kick Alpha (go to bed)" in actions(pl)


@pytest.mark.parametrize("reason", ["@a", "x\u0007", "x" * 121, 5])
def test_a_bad_reason_is_refused(pl, reason):
    assert post(pl, {"action": "ban", "name": "Alpha", "reason": reason})[0] == 400
    assert not any(c.startswith("ban") for c in pl.server.sent) and actions(pl) == ""


def test_kick_and_spawn_need_the_player_online(pl):
    for action in ("kick", "spawn"):
        code, data = post(pl, {"action": action, "name": "Charlie"})
        assert code == 409 and "isn't online" in data["error"]
    assert actions(pl) == ""


def test_ban_and_unban(pl):
    code, data = post(pl, {"action": "ban", "name": "Charlie", "reason": "griefing"})
    assert code == 200 and data["player"]["banned"] is True and "ban Charlie griefing" in pl.server.sent
    assert post(pl, {"action": "ban", "name": "Charlie"})[0] == 409
    code, data = post(pl, {"action": "unban", "name": "Charlie"})
    assert code == 200 and data["player"]["banned"] is False and "pardon Charlie" in pl.server.sent
    assert post(pl, {"action": "unban", "name": "Charlie"})[0] == 409
    log = actions(pl)
    assert "player-ban Charlie (griefing)" in log and "player-unban Charlie" in log


def test_spawn_sends_them_to_the_overworld_spawn(pl):
    code, data = post(pl, {"action": "spawn", "name": "Bravo"})
    assert code == 200 and "world spawn" in data["note"]
    assert pl.server.sent[-1].startswith("scoreboard")       # the look-up after
    assert "execute in minecraft:overworld run tp Bravo ~0.5 ~ ~0.5" in pl.server.sent
    assert "player-spawn Bravo" in actions(pl)


def test_a_server_that_says_no_is_an_error(pl):
    staff_events.events(pl.panel).rcon = lambda command, timeout=None: (
        "No entity was found" if command.startswith("execute") else pl.server(command))
    code, data = post(pl, {"action": "spawn", "name": "Bravo"})
    assert code == 409 and "No entity was found" in data["error"]


# ---------------------------------------------------------------- Strength


def test_raising_strength_leaves_the_modifiers_alone(pl):
    code, data = post(pl, {"action": "strength-set", "name": "Alpha", "level": 5})
    assert code == 200 and data["player"]["strength"] == 5
    assert not any(c.startswith("attribute") for c in pl.server.sent)
    assert "player-strength Alpha set 5 (was 3)" in actions(pl)


def test_lowering_strength_online_takes_the_old_bonus_off(pl):
    code, data = post(pl, {"action": "strength-set", "name": "Bravo", "level": "2"})
    assert code == 200 and pl.server.scores["Bravo"] == 2
    removed = [c for c in pl.server.sent if c.startswith("attribute")]
    assert removed == [f"attribute Bravo minecraft:attack_damage modifier remove strength_smp:buff-level_{n}"
                       for n in range(1, 6)]


def test_lowering_strength_offline_only_to_0_or_1(pl):
    pl.server.scores["Charlie"] = 4
    code, data = post(pl, {"action": "strength-set", "name": "Charlie", "level": 3})
    assert code == 409 and "offline" in data["error"] and pl.server.scores["Charlie"] == 4 and actions(pl) == ""
    assert post(pl, {"action": "strength-set", "name": "Charlie", "level": 1})[0] == 200
    assert pl.server.scores["Charlie"] == 1 and not any(c.startswith("attribute") for c in pl.server.sent)


@pytest.mark.parametrize("level", [-1, 6, 2.5, True, "x", None])
def test_a_bad_level_is_refused(pl, level):
    assert post(pl, {"action": "strength-set", "name": "Alpha", "level": level})[0] == 400
    assert actions(pl) == ""


def test_plus_one(pl):
    code, data = post(pl, {"action": "strength-add", "name": "Alpha"})
    assert code == 200 and pl.server.scores["Alpha"] == 4 and "is 4" in data["note"]
    code, data = post(pl, {"action": "strength-add", "name": "Charlie"})      # no score yet: the mod would start at 3
    assert code == 200 and pl.server.scores["Charlie"] == 4
    assert f"scoreboard players set Charlie {STRENGTH} 4" in pl.server.sent
    code, data = post(pl, {"action": "strength-add", "name": "Bravo"})        # at 5: the mod gives an item
    assert code == 200 and "Strength item" in data["note"]


def test_reset_to_zero(pl):
    code, data = post(pl, {"action": "strength-reset", "name": "Bravo"})
    assert code == 200 and pl.server.scores["Bravo"] == 0
    assert "player-strength Bravo set 0 (was 5)" in actions(pl)


def test_strength_without_the_mod(pl):
    pl.server.mod = False
    code, data = pl.call("GET", "/api/player?name=Alpha", role="admin")
    assert code == 409 and "Strength SMP" in data["error"]


def test_a_level_that_doesnt_stick_is_an_error(pl):
    plain = pl.server

    def stuck(command, timeout=None):
        if command.startswith("scoreboard players set"):
            return "Set"
        return plain(command, timeout)

    staff_events.events(pl.panel).rcon = stuck
    code, data = post(pl, {"action": "strength-set", "name": "Alpha", "level": 5})
    assert code == 502 and "Check the console" in data["error"]


def test_a_server_that_isnt_running(pl):
    pl.server.up = False
    code, data = post(pl, {"action": "strength-add", "name": "Alpha"})
    assert code == 502 and "running" in data["error"]


# ---------------------------------------------------------------- the stat reset


def stats_path(pl, uuid=CHARLIE):
    return pl.root / "world" / "players" / "stats" / f"{uuid}.json"


def test_the_reset_needs_the_name_typed(pl):
    for confirm in (None, "", "Alpha", "Charli"):
        code, data = post(pl, {"action": "reset", "name": "Charlie", "confirm": confirm})
        assert code == 400 and "Type the player's name" in data["error"]
    assert json.loads(stats_path(pl).read_text()) == stats() and actions(pl) == ""


def test_the_reset_needs_the_player_offline(pl):
    pl.server.scores["Alpha"] = 4
    code, data = post(pl, {"action": "reset", "name": "Alpha", "confirm": "alpha"})
    assert code == 409 and "kick them first" in data["error"] and pl.server.scores["Alpha"] == 4


def test_the_reset(pl):
    pl.server.scores["Charlie"] = 5
    code, data = post(pl, {"action": "reset", "name": "Charlie", "confirm": "charlie"})
    assert code == 200, data
    assert pl.server.scores["Charlie"] == 0
    saved = json.loads(stats_path(pl).read_text())
    assert saved["stats"] == {"minecraft:custom": {"minecraft:jump": 99}, "minecraft:killed": {"minecraft:zombie": 3},
                              "minecraft:killed_by": {}}
    assert saved["DataVersion"] == 4903
    kept = history_files(pl)
    assert len(kept) == 1 and kept[0].endswith(f"world/players/stats/{CHARLIE}.json")
    log = actions(pl)
    assert "player-reset Charlie: Strength, kills, deaths" in log
    assert "player-reset-result Charlie: Strength 5 -> 0, kills and deaths to 0 (were custom/player_kills 4" in log
    # again: nothing left to clear, no second history entry
    code, data = post(pl, {"action": "reset", "name": "Charlie", "confirm": "Charlie"})
    assert code == 200 and "already 0" in data["note"] and len(history_files(pl)) == 1


def test_the_reset_of_a_player_with_no_statistics_file(pl):
    pl.server.scores["Zed"] = 2
    code, data = post(pl, {"action": "reset", "name": "Zed", "confirm": "Zed"})
    assert code == 200 and "no statistics saved yet" in data["note"] and pl.server.scores["Zed"] == 0


def test_a_statistics_file_this_page_cant_read_is_left_alone(pl):
    stats_path(pl).write_text("{not json")
    code, data = post(pl, {"action": "reset", "name": "Charlie", "confirm": "Charlie"})
    assert code == 502 and "were not" in data["error"]
    assert stats_path(pl).read_text() == "{not json" and history_files(pl) == []


def test_the_world_folder_comes_from_server_properties(pl):
    props = pl.root / "server.properties"
    props.write_text(props.read_text() + "level-name=../outside\n")
    code, data = post(pl, {"action": "reset", "name": "Charlie", "confirm": "Charlie"})
    assert code == 409 and "level-name" in data["error"] and "player-reset" not in actions(pl)


def test_there_is_no_reset_for_everyone(pl):
    for name in ("@a", "*", "everyone"):
        assert post(pl, {"action": "reset", "name": name, "confirm": name})[0] in (400, 404)
    assert actions(pl) == ""


# ---------------------------------------------------------------- the faction prize


@pytest.fixture
def party(pl):
    FakeWorld(pl.root / "world").party("party-1", member(ALPHA, "OldName"), [member(CHARLIE, "Charlie")]) \
        .party("party-2", None).party_name(ALPHA, "Red Team").party("party-3", member(BRAVO, "Bravo"))
    return pl


def test_the_factions_list(party):
    code, data = party.call("GET", "/api/factions", role="admin")
    assert code == 200
    assert data["factions"] == [{"id": "party-3", "members": ["Bravo"], "name": "Bravo's faction"},
                                {"id": "party-1", "members": ["Alpha", "Charlie"], "name": "Red Team"}]


def test_no_factions_yet(pl):
    code, data = pl.call("GET", "/api/factions", role="admin")
    assert code == 200 and data["factions"] == []


def test_the_faction_prize(party):
    code, data = party.call("POST", "/api/faction-strength", {"party": "party-1"}, role="admin")
    assert code == 200, data
    assert party.server.scores == {"Alpha": 4, "Bravo": 5, "Charlie": 4}
    log = actions(party)
    assert "faction-strength +1 Red Team: Alpha, Charlie" in log
    assert "faction-strength-result Alpha 3 -> 4; Charlie none (starts at 3) -> 4" in log


def test_an_unknown_faction_is_refused(party):
    for body in ({"party": "nope"}, {"party": "party-2"}, {}, {"party": 5}):
        assert party.call("POST", "/api/faction-strength", body, role="admin")[0] == 404
    assert actions(party) == ""


def test_one_change_at_a_time(party):
    players = staff_players.players(party.panel)
    assert players._lock.acquire(blocking=False)
    try:
        assert post(party, {"action": "strength-add", "name": "Alpha"})[0] == 409
        assert party.call("POST", "/api/faction-strength", {"party": "party-1"}, role="admin")[0] == 409
    finally:
        players._lock.release()
    assert actions(party) == ""


# ---------------------------------------------------------------- the page


def test_the_page_has_every_element_players_js_uses():
    page = REPO.root / "deploy" / "staff"
    script = (page / "players.js").read_text(encoding="utf-8")
    html = (page / "index.html").read_text(encoding="utf-8")
    assert '<script src="players.js" defer></script>' in html
    ids = set(re.findall(r'\$\("([a-z0-9-]+)"\)', script))
    assert ids and all(f'id="{i}"' in html for i in ids), ids - set(re.findall(r'id="([a-z0-9-]+)"', html))
    for path in ("/api/player", "/api/factions", "/api/faction-strength", "/api/me"):
        assert path in script
    code = "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("//"))
    assert "innerHTML" not in code and not re.search(r"\b(confirm|alert)\(", code)
    for action in staff_players.ACTIONS:
        assert f'"{action}"' in script
