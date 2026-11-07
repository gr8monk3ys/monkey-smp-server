"""The staff page's player controls: kick, ban, unban, send to spawn, Strength SMP's level, a faction's build-battle
prize and a per-player stat reset. tools/staff_panel.py registers them (register()), so they get the same login, role
and change checks as every other control. Admins only.

    GET  /api/player?name=N                  one player: their name as the server knows it, online or not, banned or
                                             not, and their Strength level (None: the mod hasn't given them one yet)
    POST /api/player {"action", "name", ...}
         kick {"reason"}                     `kick`, online players only
         ban {"reason"} / unban              `ban` / `pardon`
         spawn                               to the Overworld's spawn point (RCON runs commands from there)
         strength-set {"level": 0-5}         Strength_SMP+Strength_Level, read back after
         strength-add                        +1 (at 5 the mod turns the extra level into a Strength item)
         strength-reset                      the level to 0
         reset {"confirm": the name again}   Strength to 0 and the game's own kills and deaths statistics to 0;
                                             the player must be offline
    GET  /api/factions                       Open Parties and Claims' parties as saved: name and members
    POST /api/faction-strength {"party"}     +1 Strength to every member (the build battle's prize)

What Strength SMP does with its score (silvers_strength-smp-season-5 1.3, a data pack in a jar; tried on a local 26.2
server with a Carpet fake player, see docs/LIVE.md "The staff page"):
- It reads Strength_SMP+Strength_Level every tick for each online player and doesn't overwrite a value written to it.
  Below 0 it sets 0; at 6 or more it gives one Strength item and takes 1 off, each tick, so the most is 5.
- A player with no score at all gets 3 on their next tick (the starting level), so +1 on no score sets 4 here.
- Its damage bonus is attribute modifiers strength_smp:buff-level_1..4, added each tick for the level, but only all
  taken off at level 1 or below (a death clears them too). Lowering the level without a death would keep the old bonus,
  so a lower level also takes the modifiers off and the next tick puts back the right ones. That needs the player
  online: for an offline player the panel only lowers to 0 or 1, which the mod clears itself when they join.

The safety rules:
- Every name must be one the server knows (usercache.json, the whitelist, ops and bans), and is used as the server
  spells it. A reason may not hold @ (the ban and kick reasons resolve selectors) or a control character.
- The stat reset is per player only: there is no way to reset everyone. The admin types the player's name again. The
  statistics file (world/players/stats/<uuid>.json) is only written while the player is offline (the game keeps them in
  memory and writes them back when they leave), a copy goes to the history first, and the file is written whole.
- Each action is one line in actions.log before it runs, and the reset and the faction prize one more with the result.
- One change at a time.

Stdlib only, Python 3.10 or newer.
"""
import json
import re
import threading

import staff_events
import staff_status

import saved_world

sp = None   # tools/staff_panel.py (register)

STRENGTH = "Strength_SMP+Strength_Level"
LEVELS = (0, 5)
START = 3                 # the mod's starting level, for a player with no score
BUFFS = tuple(f"strength_smp:buff-level_{n}" for n in range(1, 6))
REASON_MAX = 120
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
LEVEL_NAME = re.compile(r"[A-Za-z0-9_. -]{1,64}")
# The game's own statistics that are a player's kills and deaths (the Statistics screen).
STATS = (("minecraft:custom", "minecraft:player_kills"), ("minecraft:custom", "minecraft:deaths"),
         ("minecraft:killed", "minecraft:player"), ("minecraft:killed_by", "minecraft:player"))
NOT_FOUND = ("No entity was found", "No player was found")
NO_MOD = "Strength SMP's scores aren't there: is the mod loaded? (/datapack list)"
ACTIONS = ("kick", "ban", "unban", "spawn", "strength-set", "strength-add", "strength-reset", "reset")
_SCORE = re.compile(r"has (-?\d+) \[")


class Players:
    """What these controls keep for one Panel. The RCON is staff_events' (the tests replace that)."""

    def __init__(self, panel):
        self.p = panel
        self._lock = threading.Lock()

    def _ask(self, command: str) -> str:
        return staff_events.events(self.p)._ask(command)

    # ------------------------------------------------ who

    def known(self) -> dict[str, tuple[str, str]]:
        """lower-case name -> (name, uuid) for every player the server has seen."""
        found: dict[str, tuple[str, str]] = {}
        for file in ("banned-players.json", "ops.json", "whitelist.json", "usercache.json"):   # the cache wins
            try:
                rows = json.loads((self.p.root / file).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for r in rows if isinstance(rows, list) else []:
                if isinstance(r, dict) and isinstance(r.get("name"), str) and sp.PLAYER.fullmatch(r["name"]):
                    found[r["name"].lower()] = (r["name"], str(r.get("uuid") or "").lower())
        return found

    def player(self, value) -> tuple[str, str]:
        """(name, uuid) of a player the server knows, or Refused."""
        if not isinstance(value, str) or not sp.PLAYER.fullmatch(value.strip()):
            raise sp.Refused(400, "A player name is 3 to 16 letters, digits or underscores.")
        found = self.known().get(value.strip().lower())
        if found is None:
            raise sp.Refused(404, f"No player called {value.strip()} has joined this server.")
        return found

    def online(self) -> list[str]:
        who = staff_status.players(self._ask("list"))
        if who is None:
            raise sp.Refused(502, "The server didn't say who is online: is it running?")
        return who["names"]

    def is_online(self, name: str) -> bool:
        return name.lower() in (n.lower() for n in self.online())

    def banned(self, name: str) -> bool:
        try:
            rows = json.loads((self.p.root / "banned-players.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return any(isinstance(r, dict) and str(r.get("name", "")).lower() == name.lower()
                   for r in (rows if isinstance(rows, list) else []))

    # ------------------------------------------------ Strength SMP

    def strength(self, name: str) -> int | None:
        said = self._ask(f"scoreboard players get {name} {STRENGTH}")
        m = _SCORE.search(said)
        if m:
            return int(m[1])
        if staff_events._UNSET in said:
            return None
        if staff_events._NO_OBJECTIVE in said:
            raise sp.Refused(409, NO_MOD)
        raise sp.Refused(502, "The server's answer about Strength wasn't one this page knows: "
                              f"{sp.masked(said)[-200:]}")

    def _set_strength(self, name: str, level: int, online: bool) -> int | None:
        """Sets the level and, when it went down for an online player, takes the old damage bonus off."""
        was = self.strength(name)
        self._ask(f"scoreboard players set {name} {STRENGTH} {level}")
        if online and level < (START if was is None else was):
            for buff in BUFFS:
                self._ask(f"attribute {name} minecraft:attack_damage modifier remove {buff}")
        now = self.strength(name)
        if now != level:
            raise sp.Refused(502, f"The server took the new level, but {name} has {now}. Check the console.")
        return was

    def _add_strength(self, name: str) -> tuple[int | None, int]:
        was = self.strength(name)
        if was is None:
            self._ask(f"scoreboard players set {name} {STRENGTH} {START + 1}")
        else:
            self._ask(f"scoreboard players add {name} {STRENGTH} 1")
        now = self.strength(name)
        # At 5 the online player's next tick may already have turned the 6 into an item.
        if now is None or now < (START if was is None else was):
            raise sp.Refused(502, f"The server took +1, but {name} has {now}. Check the console.")
        return was, now

    # ------------------------------------------------ the routes

    def look(self, query: dict) -> dict:
        name, uuid = self.player(query.get("name"))
        return {"player": {"name": name, "uuid": uuid, "online": self.is_online(name), "banned": self.banned(name),
                           "strength": self.strength(name), "start": START, "most": LEVELS[1]}}

    def act(self, user: str, body: dict) -> dict:
        action = body.get("action")
        if action not in ACTIONS:
            raise sp.Refused(400, f"action must be one of {', '.join(ACTIONS)}.")
        name, uuid = self.player(body.get("name"))
        if not self._lock.acquire(blocking=False):
            raise sp.Refused(409, "Another player change is under way: try again in a moment.")
        try:
            note = getattr(self, "_" + action.replace("-", "_"))(user, name, uuid, body)
        finally:
            self._lock.release()
        result = self.look({"name": name})
        return {**result, "note": note}

    def _kick(self, user, name, uuid, body) -> str:
        reason = checked_reason(body.get("reason"))
        if not self.is_online(name):
            raise sp.Refused(409, f"{name} isn't online.")
        self.p.record(user, "player-kick", f"{name}{f' ({reason})' if reason else ''}")
        self._expect(f"kick {name}{f' {reason}' if reason else ''}", "Kicked")
        return f"{name} was kicked."

    def _ban(self, user, name, uuid, body) -> str:
        reason = checked_reason(body.get("reason"))
        if self.banned(name):
            raise sp.Refused(409, f"{name} is already banned.")
        self.p.record(user, "player-ban", f"{name}{f' ({reason})' if reason else ''}")
        self._expect(f"ban {name}{f' {reason}' if reason else ''}", "Banned")
        return f"{name} is banned."

    def _unban(self, user, name, uuid, body) -> str:
        if not self.banned(name):
            raise sp.Refused(409, f"{name} isn't banned.")
        self.p.record(user, "player-unban", name)
        self._expect(f"pardon {name}", "Unbanned")
        return f"{name} can join again."

    def _spawn(self, user, name, uuid, body) -> str:
        if not self.is_online(name):
            raise sp.Refused(409, f"{name} isn't online.")
        self.p.record(user, "player-spawn", name)
        # RCON's commands run at the Overworld's spawn point; +0.5 is the middle of the block.
        self._expect(f"execute in minecraft:overworld run tp {name} ~0.5 ~ ~0.5", "Teleported")
        return f"{name} is at the world spawn."

    def _strength_set(self, user, name, uuid, body) -> str:
        level = checked_level(body.get("level"))
        return self._strength_to(user, name, level, "player-strength")

    def _strength_reset(self, user, name, uuid, body) -> str:
        return self._strength_to(user, name, 0, "player-strength")

    def _strength_to(self, user, name, level, action) -> str:
        online = self.is_online(name)
        was = self.strength(name)
        if not online and 2 <= level < (START if was is None else was):
            raise sp.Refused(409, f"{name} is offline: lowering Strength to {level} needs them online, or the mod "
                                  "keeps their old damage bonus. 0 or 1 works offline.")
        self.p.record(user, action, f"{name} set {level} (was {shown(was)})")
        self._set_strength(name, level, online)
        return f"{name}'s Strength is {level}."

    def _strength_add(self, user, name, uuid, body) -> str:
        self.p.record(user, "player-strength", f"{name} +1")
        was, now = self._add_strength(name)
        return plus_note(name, was, now)

    def _reset(self, user, name, uuid, body) -> str:
        confirm = body.get("confirm")
        if not isinstance(confirm, str) or confirm.strip().lower() != name.lower():
            raise sp.Refused(400, f"Type the player's name, {name}, to confirm the reset.")
        if self.is_online(name):
            raise sp.Refused(409, f"{name} is online: kick them first. The game keeps their statistics in memory and "
                                  "would write the old ones back when they leave.")
        path = self.stats_file(uuid)
        self.p.record(user, "player-reset", f"{name}: Strength, kills, deaths")
        was = self.strength(name)
        self._set_strength(name, 0, online=False)
        stats = self._reset_stats(user, name, path)
        self.p.record(user, "player-reset-result", f"{name}: Strength {shown(was)} -> 0, {stats}")
        note = f"{name} reset: Strength {shown(was)} -> 0, {stats}."
        if self.is_online(name):
            note += (f" {name} joined while it ran, so the game may write their old kills and deaths back: kick them "
                     "and reset again.")
        return note

    def _reset_stats(self, user: str, name: str, path) -> str:
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            return "no statistics saved yet"
        try:
            data = json.loads(raw.decode("utf-8"))
            stats = data["stats"]
        except (UnicodeDecodeError, ValueError, KeyError, TypeError):
            raise sp.Refused(502, f"{name}'s statistics file isn't one this page can read: Strength was reset, the "
                                  "kills and deaths were not.") from None
        if not isinstance(stats, dict):
            raise sp.Refused(502, f"{name}'s statistics file isn't one this page can read.")
        old = {}
        for group, key in STATS:
            if isinstance(stats.get(group), dict) and key in stats[group]:
                old[f"{group.split(':')[1]}/{key.split(':')[1]}"] = stats[group].pop(key)
        if not old:
            return "kills and deaths were already 0"
        rel = path.relative_to(self.p.root).parts
        entry = self.p._keep(path, rel, user)
        self.p._write(path, json.dumps(data, separators=(",", ":")).encode(), path.stat())
        listed = ", ".join(f"{k} {v}" for k, v in old.items())
        return f"kills and deaths to 0 (were {listed}; the old file is history entry {entry})"

    def stats_file(self, uuid: str):
        if not UUID.fullmatch(uuid):
            raise sp.Refused(409, "The server's player list has no proper UUID for that player.")
        return self.world() / "players" / "stats" / f"{uuid}.json"

    def world(self):
        level = level_name(self.p.root / "server.properties")
        if not LEVEL_NAME.fullmatch(level) or level.strip(".") == "":
            raise sp.Refused(409, "server.properties' level-name isn't a plain folder name.")
        return self.p.root / level

    def _expect(self, command: str, word: str) -> str:
        said = self._ask(command)
        if any(m in said for m in NOT_FOUND) or word not in said:
            raise sp.Refused(409, f"The server said: {sp.masked(said)[-200:] or 'nothing'}")
        return said

    # ------------------------------------------------ factions (Open Parties and Claims)

    def parties(self) -> list[dict]:
        try:
            found = saved_world.parties(self.world())
        except (OSError, ValueError):
            raise sp.Refused(502, "The factions' files couldn't be read.") from None
        names = {u: n for n, u in self.known().values()}
        rows = []
        for party in found or []:
            if party.owner is None:
                continue
            members = [names.get(m.uuid) or m.username for m in party.members]
            members = [m for m in members if m and sp.PLAYER.fullmatch(m)]
            # As saved_world.faction_name names it, written out here: the live checkout's saved_world may be older.
            rows.append({"id": party.id, "members": members,
                         "name": party.name or f"{members[0] if members else '?'}'s faction"})
        return sorted(rows, key=lambda r: r["name"].lower())

    def factions(self) -> dict:
        return {"factions": self.parties()}

    def faction_strength(self, user: str, body: dict) -> dict:
        party = body.get("party")
        found = next((f for f in self.parties() if f["id"] == party), None) if isinstance(party, str) else None
        if found is None:
            raise sp.Refused(404, "There is no such faction (a faction made in the last few minutes may not be saved "
                                  "yet).")
        if not found["members"]:
            raise sp.Refused(409, "That faction has no members this page can name.")
        if not self._lock.acquire(blocking=False):
            raise sp.Refused(409, "Another player change is under way: try again in a moment.")
        try:
            self.p.record(user, "faction-strength", f"+1 {found['name']}: {', '.join(found['members'])}")
            done, failed = [], []
            for name in found["members"]:
                try:
                    was, now = self._add_strength(name)
                    done.append(f"{name} {shown(was)} -> {now}")
                except sp.Refused as e:
                    failed.append(f"{name} ({e.message})")
            self.p.record(user, "faction-strength-result",
                          "; ".join(done + [f"FAILED {f}" for f in failed]) or "nothing")
        finally:
            self._lock.release()
        note = f"+1 Strength to {found['name']}: {', '.join(done) or 'nobody'}."
        if any(" -> 6" in d or d.endswith("5 -> 5") for d in done):
            note += " Anyone at 5 gets a Strength item instead (when they are next online)."
        if failed:
            raise sp.Refused(502, f"{note} Not given: {'; '.join(failed)}")
        return {"note": note}


def level_name(path) -> str:
    """server.properties' level-name (the last one wins, as Java's Properties reads it), "world" when unset."""
    found = "world"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return found
    for line in text.splitlines():
        m = re.fullmatch(r"\s*level-name\s*[=:]\s*(.*?)\s*", line)
        if m:
            found = m[1] or "world"
    return found


def shown(level: int | None) -> str:
    return "none (starts at 3)" if level is None else str(level)


def plus_note(name: str, was: int | None, now: int) -> str:
    if (START if was is None else was) >= LEVELS[1]:
        return f"{name} was at {LEVELS[1]}, the most: the mod turns the extra level into a Strength item."
    return f"{name}'s Strength is {now}."


def checked_level(value) -> int:
    low, high = LEVELS
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise sp.Refused(400, f"level must be a whole number from {low} to {high}.")
    return value


def checked_reason(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise sp.Refused(400, "reason must be text.")
    value = " ".join(value.split())
    if len(value) > REASON_MAX:
        raise sp.Refused(400, f"A reason can be at most {REASON_MAX} characters.")
    if "@" in value or any(not c.isprintable() for c in value):
        raise sp.Refused(400, "A reason can't have @ or a control character in it.")
    return value


_players_lock = threading.Lock()


def players(panel) -> Players:
    with _players_lock:
        found = getattr(panel, "_players", None)
        if found is None:
            found = panel._players = Players(panel)
        return found


ROUTES = {
    ("GET", "/api/player"): lambda p, u, q, b: players(p).look(q),
    ("POST", "/api/player"): lambda p, u, q, b: players(p).act(u, b),
    ("GET", "/api/factions"): lambda p, u, q, b: players(p).factions(),
    ("POST", "/api/faction-strength"): lambda p, u, q, b: players(p).faction_strength(u, b),
}
NEEDS = {key: "admin" for key in ROUTES}


def register(module) -> None:
    """Adds these routes to staff_panel's (`module` is staff_panel itself, as it runs)."""
    global sp
    sp = module
    module.ROUTES.update(ROUTES)
    module.NEEDS.update(NEEDS)
    module.PATHS.update(path for _, path in ROUTES)
