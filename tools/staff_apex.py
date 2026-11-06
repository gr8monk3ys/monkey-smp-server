"""The staff page's hosting-panel controls, the ones a host like Apex has: settings, game rules, backups, schedules,
mods, the world download and bans by address. tools/staff_panel.py serves them (it calls register() with itself),
with the same login, role and change checks as its own; docs/LIVE.md, "The staff page", says what each one does.

    GET  /api/settings                server.properties as typed fields      admin
    PUT  /api/settings {"values", "mtime"}  saves the changed ones          admin
    GET  /api/gamerules               the game rules, asked over RCON        admin
    POST /api/gamerules {"name", "value"}   `gamerule NAME VALUE`            admin
    GET  /api/helper                  whether the backup helper is in, and its last jobs          moderator
    POST /api/backup-now              asks the helper for an off-site backup                      admin
    POST /api/snapshots               asks the helper for the snapshot list; GET reads the last   admin
    POST /api/world-restore {"snapshot", "confirm"}  asks the helper to put a snapshot's world back  owner
    GET  /api/schedules               the page's own schedules; POST adds, PUT changes one          admin
    POST /api/schedule-delete {"id"}                                                              admin
    GET  /api/mods                    the mods folder's jars (on, off, pinned)                    moderator
    POST /api/world-download          a one-time link; GET /api/world-download?token=T streams a zip   owner
    GET  /api/ip-bans                 banned-ips.json                        admin
    POST /api/ip-ban {"target", "reason"}, POST /api/ip-pardon {"ip"}         admin

The safety rules, as in staff_panel.py, are all here rather than in the page:
- Settings: only keys this file knows, each with its type and range; the RCON, port, query, seed, world-name, online
  mode, management server and secret keys are locked; keys it doesn't know are shown, never changed. A save goes
  through staff_panel's own file save (the history copy, the check that nobody else saved since, the action log).
- Game rules: a name from GAMERULES and a value of its type, nothing else, so no other command can ride along.
- Backups: the panel runs as monkey and can't read the backup keys, so it never runs restic. It writes a request file
  (an action from HELPER_ACTIONS, a snapshot ID in hex, and REQUEST_FIELDS values) to STAFF_DIR/requests;
  deploy/monkey-staff-helper.sh, as root, reads only those and writes what happened to RESULTS, a root-owned folder
  the panel only reads.
- Schedules: a command runs through the console's own checks (no seed, no stop), a restart through the power path
  after warnings in chat, a backup through the helper. One thread runs them; each run's slot is saved before it
  starts, so a restarted panel never runs the same one twice, and one it missed by over GRACE is skipped.
- The world download stops saving (save-off, save-all flush) while it streams the zip, holds the deploy lock so no
  restart or backup lands meanwhile, and turns saving back on whatever happens. One at a time, owners only.
- Bans by address: a real public IPv4 or IPv6 address, or a player name for an online player's address. A private,
  loopback or Docker address is refused: it could be everyone's (a proxy, Docker's own gateway).

    python3 tools/staff_apex.py snapshots < restic.json   restic's snapshot list, cut down for the page (the helper)

The mod manager, the version switch, the world reset and upload and the SFTP card are in tools/staff_host.py, which
register() adds too.

Stdlib only, Python 3.10 or newer. Imports nothing from tools/ at load: staff_panel hands itself over in register(),
which imports staff_host only then (the helper runs this file alone, with python3 -I).
"""
import argparse
import concurrent.futures
import contextlib
import datetime as dt
import ipaddress
import json
import os
import re
import secrets
import sys
import threading
import time
import zipfile
from pathlib import Path

sp = None   # tools/staff_panel.py, the module that serves these (register)

HELPER_UNIT = Path("/etc/systemd/system/monkey-staff-helper.path")
HELPER_RESULTS = Path("/var/lib/monkey-staff-helper/results")
HELPER_ACTIONS = ("backup-now", "list-snapshots", "restore", "deploy", "reset", "world-upload")
HELPER_PENDING_MAX = 5
SNAPSHOT_ID = re.compile(r"[0-9a-f]{8,64}")
REQUEST_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{8}")
# The other words a request may carry (staff_host.py checks them first; the helper checks them again).
REQUEST_FIELDS = {"tag": re.compile(r"v\d{1,4}\.\d{1,4}\.\d{1,4}"), "seed": re.compile(r"-?[A-Za-z0-9_]{1,64}"),
                  "upload": REQUEST_ID}
RESULT_MAX = 2 * 1024 * 1024
JOBS_SHOWN = 20

GAMERULE_CACHE = 20             # seconds a reading of the game rules is reused
GAMERULE_THREADS = 4
SCHEDULES_MAX = 50
SCHEDULE_TICK = 20              # seconds between the scheduler's looks
GRACE = 15 * 60                 # a run missed by more than this (the panel was down) is skipped, not run late
INTERVAL_MIN = 10
RESTART_WARNINGS = ((300, "in 5 minutes"), (60, "in 1 minute. Find a safe spot"), (10, "in 10 seconds"))
LEAD = {"restart": RESTART_WARNINGS[0][0]}  # a restart's warnings start this long before its time
TOKEN_TTL = 60
JAR_JSON_MAX = 1024 * 1024
MODS_MAX = 1000
REASON_MAX = 120
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# ---------------------------------------------------------------- server.properties

GROUPS = ("Gameplay", "World", "Players", "Network")


def _b(group, about):
    return {"group": group, "type": "bool", "about": about}


def _i(group, lo, hi, about):
    return {"group": group, "type": "int", "min": lo, "max": hi, "about": about}


def _e(group, choices, about):
    return {"group": group, "type": "enum", "choices": choices, "about": about}


def _t(group, most, about):
    return {"group": group, "type": "text", "max": most, "about": about}


# The keys the form knows, in the order it shows them. A key in the file that isn't here is shown read-only.
PROPERTIES = {
    "difficulty": _e("Gameplay", ["peaceful", "easy", "normal", "hard"], "How hard mobs hit; whether hunger kills."),
    "gamemode": _e("Gameplay", ["survival", "creative", "adventure", "spectator"], "The mode new players start in."),
    "force-gamemode": _b("Gameplay", "Put every player back in the default mode each time they join."),
    "hardcore": _b("Gameplay", "One life: a player who dies becomes a spectator. Leave off."),
    "pvp": _b("Gameplay", "Players can hurt each other (the events and omens also switch the pvp game rule)."),
    "allow-flight": _b("Gameplay", "Don't kick players the game thinks are flying (needed by some mods' items)."),
    "spawn-protection": _i("Gameplay", 0, 1000, "Blocks around spawn that only operators can change. 0 is off."),
    "enable-command-block": _b("Gameplay", "Command blocks work."),
    "op-permission-level": _i("Gameplay", 1, 4, "What operators may do: 4 is everything, 2 is most commands."),
    "function-permission-level": _i("Gameplay", 1, 4, "The permission level data pack functions run with."),
    "enable-code-of-conduct": _b("Gameplay", "Players accept the short rules before they join."),
    "view-distance": _i("World", 3, 32, "How many chunks the server sends each player. Higher costs memory and CPU."),
    "simulation-distance": _i("World", 3, 32, "How many chunks around a player keep running (farms, mobs)."),
    "max-world-size": _i("World", 1, 29999984, "The world's radius in blocks (the season border is set apart)."),
    "allow-nether": _b("World", "The Nether can be entered."),
    "spawn-monsters": _b("World", "Hostile mobs spawn."),
    "sync-chunk-writes": _b("World", "Write chunks to disk one at a time (safer, slower). Off here for speed."),
    "region-file-compression": _e("World", ["deflate", "lz4", "none"], "How the world's region files are packed."),
    "entity-broadcast-range-percentage": _i("World", 10, 1000, "How far away players see entities, in percent."),
    "max-tick-time": _i("World", -1, 2147483647, "Milliseconds a tick may take before the watchdog stops the "
                                                 "server. -1 is off, as set here for slow world generation."),
    "pause-when-empty-seconds": _i("World", 0, 86400, "Seconds with nobody online before the server pauses. 0 never."),
    "max-players": _i("Players", 1, 1000, "The most players online at once."),
    "white-list": _b("Players", "Only players on the whitelist can join."),
    "enforce-whitelist": _b("Players", "Kick players who aren't on the whitelist when it is reloaded."),
    "motd": _t("Players", 150, "The message under the server's name in the server list."),
    "player-idle-timeout": _i("Players", 0, 1440, "Minutes before an idle player is kicked. 0 never."),
    "hide-online-players": _b("Players", "Don't show who is online in the server list."),
    "enforce-secure-profile": _b("Players", "Only players with a Mojang-signed chat key can join."),
    "log-ips": _b("Players", "Write players' addresses in the log."),
    "broadcast-console-to-ops": _b("Players", "Operators see what console commands do."),
    "broadcast-rcon-to-ops": _b("Players", "Operators see what RCON commands do (every timed job uses RCON)."),
    "require-resource-pack": _b("Players", "Players who refuse the resource pack are kicked."),
    "resource-pack": _t("Players", 500, "The address of a server resource pack. Empty for none."),
    "resource-pack-sha1": _t("Players", 40, "The pack's SHA-1, so players' games can check it."),
    "resource-pack-prompt": _t("Players", 200, "The text shown when players are asked to take the pack."),
    "accepts-transfers": _b("Players", "Other servers can send players here (/transfer)."),
    "network-compression-threshold": _i("Network", -1, 65535, "Packets larger than this many bytes are "
                                                              "compressed. -1 is off."),
    "rate-limit": _i("Network", 0, 100000, "Packets a second a player may send before being kicked. 0 is no limit."),
    "use-native-transport": _b("Network", "Use Linux's faster network code."),
    "prevent-proxy-connections": _b("Network", "Kick players whose address doesn't match Mojang's check."),
    "enable-status": _b("Network", "The server shows up as online in the server list."),
    "enable-jmx-monitoring": _b("Network", "Expose tick timings to Java monitoring tools."),
    "bug-report-link": _t("Network", 500, "The link the game's bug report screen offers."),
    "max-chained-neighbor-updates": _i("Network", -1, 10000000, "Limits block update chains (redstone). "
                                                                "-1 is no limit."),
}
# Never changed here: the console's own access (RCON), what players and the jobs connect to, what the world was made
# with, who can join at all (online mode), and anything secret.
LOCKED = {
    "level-name": "The world's folder: every job and backup names it.",
    "level-seed": "The seed is secret.",
    "level-type": "Set when the world was made.",
    "generator-settings": "Set when the world was made.",
    "generate-structures": "Set when the world was made.",
    "server-port": "Players, the proxy and the firewall use this port.",
    "server-ip": "Changing it can make the server unreachable.",
    "online-mode": "Off would let anyone join under any name.",
    "enable-rcon": "The staff page and every timed job use RCON.",
    "enable-query": "Locked with the ports.",
    "query.port": "Locked with the ports.",
}
LOCKED_PREFIXES = {"rcon.": "The staff page and every timed job use RCON.",
                   "management-server": "The game's management server is locked with the ports."}
_PROP_LINE = re.compile(r"^(?P<key>[^\s=:#!][^\s=:]*)\s*[=:]\s?(?P<value>.*)$")
_ESCAPES = {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}


def unescape(raw: str) -> str:
    """A server.properties value as Java reads it: \\uXXXX, \\t and the like, and \\x for x."""
    out, i = [], 0
    while i < len(raw):
        c = raw[i]
        if c == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt == "u" and re.fullmatch(r"[0-9A-Fa-f]{4}", raw[i + 2:i + 6]):
                out.append(chr(int(raw[i + 2:i + 6], 16)))
                i += 6
                continue
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
            continue
        out.append(c)
        i += 1
    text = "".join(out)
    with contextlib.suppress(UnicodeError):   # 😀, an emoji the way Java writes one
        text = text.encode("utf-16", "surrogatepass").decode("utf-16")
    return text


def escape(value: str) -> str:
    """The value as the game writes it: backslashes doubled and anything outside printable ASCII as \\uXXXX."""
    out = []
    for c in value:
        if c == "\\":
            out.append("\\\\")
        elif 32 <= ord(c) < 127:
            out.append(c)
        else:
            out.extend(f"\\u{unit:04x}" for unit in _utf16(c))
    text = "".join(out)
    return "\\" + text if text.startswith(" ") else text


def _utf16(c: str) -> list[int]:
    data = c.encode("utf-16-be")
    return [int.from_bytes(data[i:i + 2], "big") for i in range(0, len(data), 2)]


def parse_properties(text: str) -> dict[str, tuple[int, str]]:
    """{key: (line index, raw value)}, the last line of a key winning as in Java. Comments and blank lines skipped."""
    found = {}
    for n, line in enumerate(text.splitlines()):
        stripped = line.lstrip()
        if not stripped or stripped[0] in "#!":
            continue
        m = _PROP_LINE.match(stripped)
        if m:
            found[m["key"]] = (n, m["value"].rstrip("\r"))
    return found


def why_locked(key: str) -> str | None:
    if key in LOCKED:
        return LOCKED[key]
    for prefix, why in LOCKED_PREFIXES.items():
        if key.startswith(prefix):
            return why
    if sp is not None and sp._SECRET_KEY.search(key):
        return "A secret: shown as ********, never changed here."
    return None


def coerce(key: str, value) -> str:
    """The value as it goes in the file (before escaping), or Refused."""
    spec = PROPERTIES[key]
    kind = spec["type"]
    if kind == "bool":
        if isinstance(value, bool):
            return "true" if value else "false"
        if value in ("true", "false"):
            return value
        raise sp.Refused(400, f"{key} is on or off (true or false).")
    if kind == "int":
        if isinstance(value, str) and re.fullmatch(r"-?\d{1,10}", value.strip()):
            value = int(value.strip())
        if not isinstance(value, int) or isinstance(value, bool):
            raise sp.Refused(400, f"{key} must be a whole number.")
        if not spec["min"] <= value <= spec["max"]:
            raise sp.Refused(400, f"{key} must be from {spec['min']} to {spec['max']}.")
        return str(value)
    if kind == "enum":
        if value not in spec["choices"]:
            raise sp.Refused(400, f"{key} must be one of {', '.join(spec['choices'])}.")
        return value
    if not isinstance(value, str):
        raise sp.Refused(400, f"{key} must be text.")
    if len(value) > spec["max"]:
        raise sp.Refused(400, f"{key} can be at most {spec['max']} characters.")
    if any(not c.isprintable() for c in value):
        raise sp.Refused(400, f"{key} can't have a new line or a control character in it.")
    return value


# ---------------------------------------------------------------- game rules

def _gb(about):
    return {"type": "bool", "about": about}


def _gi(lo, hi, about):
    return {"type": "int", "min": lo, "max": hi, "about": about}


# The 26.x names (snake_case since 1.21.11; the repo's data packs use pvp and allow_entering_nether_using_portals).
# A name the server doesn't know answers "Unknown or incomplete command" and shows as not on this server.
GAMERULES = {
    "keep_inventory": _gb("Players keep their items and experience when they die."),
    "pvp": _gb("Players can hurt each other. The launch, Truce Hour and season events switch it themselves."),
    "allow_entering_nether_using_portals": _gb("Portals to the Nether work. The launch hour switches it."),
    "mob_griefing": _gb("Creepers, endermen and other mobs can change blocks."),
    "advance_time": _gb("Day turns to night (the daylight cycle)."),
    "advance_weather": _gb("The weather changes by itself."),
    "spawn_mobs": _gb("Mobs spawn naturally."),
    "spawn_phantoms": _gb("Phantoms come for players who haven't slept."),
    "spawn_patrols": _gb("Pillager patrols spawn."),
    "spawn_wandering_traders": _gb("Wandering traders visit."),
    "spawn_wardens": _gb("Wardens can be summoned by sculk shriekers."),
    "raids": _gb("Raids start when a player with Bad Omen enters a village."),
    "immediate_respawn": _gb("Players respawn at once, with no death screen."),
    "natural_health_regeneration": _gb("Players heal over time when fed."),
    "fall_damage": _gb("Falling hurts."),
    "fire_damage": _gb("Fire and lava hurt."),
    "drowning_damage": _gb("Running out of air hurts."),
    "freeze_damage": _gb("Powder snow hurts."),
    "show_death_messages": _gb("Deaths are announced in chat."),
    "show_advancement_messages": _gb("Advancements are announced in chat."),
    "forgive_dead_players": _gb("Angered neutral mobs calm down when the player they chase dies."),
    "universal_anger": _gb("Angered neutral mobs attack every nearby player."),
    "block_drops": _gb("Broken blocks drop items."),
    "mob_drops": _gb("Mobs drop loot."),
    "entity_drops": _gb("Minecarts, boats and item frames drop as items."),
    "tnt_explodes": _gb("TNT explodes."),
    "projectiles_can_break_blocks": _gb("Projectiles can break blocks such as pots and chorus flowers."),
    "spectators_generate_chunks": _gb("Players in spectator mode load new chunks."),
    "send_command_feedback": _gb("Commands say what they did in chat."),
    "command_block_output": _gb("Command blocks tell operators what they ran."),
    "log_admin_commands": _gb("Operators' commands are written to the log."),
    "players_sleeping_percentage": _gi(0, 100, "Percent of players who must sleep to skip the night."),
    "random_tick_speed": _gi(0, 10, "Crop growth and leaf decay speed. 3 is normal; more costs CPU."),
    "respawn_radius": _gi(0, 64, "How far from the world spawn new players and those with no bed appear."),
    "max_entity_cramming": _gi(0, 100, "Mobs that can share one block before they start to suffocate. 0 is off."),
}
_RULE_VALUE = re.compile(r"(?:set to|is)\s*:?\s*(true|false|-?\d+)\s*$", re.I)


def gamerule_value(name: str, value) -> str:
    """The value as `gamerule NAME VALUE` takes it, or Refused. Only a known name and a value of its type."""
    if not isinstance(name, str) or name not in GAMERULES:
        raise sp.Refused(400, "That is not a game rule this page knows.")
    spec = GAMERULES[name]
    if spec["type"] == "bool":
        if isinstance(value, bool):
            return "true" if value else "false"
        if value in ("true", "false"):
            return value
        raise sp.Refused(400, f"{name} is true or false.")
    if isinstance(value, str) and re.fullmatch(r"-?\d{1,6}", value):
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool):
        raise sp.Refused(400, f"{name} must be a whole number.")
    if not spec["min"] <= value <= spec["max"]:
        raise sp.Refused(400, f"{name} must be from {spec['min']} to {spec['max']}.")
    return str(value)


def read_rule(answer: str):
    """The value in `gamerule NAME`'s answer ("Gamerule keep_inventory is currently set to: false"), else None."""
    m = _RULE_VALUE.search(answer.strip())
    if not m:
        return None
    word = m[1].lower()
    return word == "true" if word in ("true", "false") else int(word)


# ---------------------------------------------------------------- schedules: when a run is due

def to_local(ts: float, tz=None) -> dt.datetime:
    """The machine's local time (or tz's) at ts, without a zone."""
    return dt.datetime.fromtimestamp(ts, tz).replace(tzinfo=None) if tz else dt.datetime.fromtimestamp(ts)


def from_local(naive: dt.datetime, tz=None) -> float:
    """A local time as a timestamp. A time a clock change skips (2:30 on the spring night) lands just after it, and
    one it repeats (1:30 on the autumn night) is the first of the two: either way one run a day."""
    return naive.replace(tzinfo=tz, fold=0).timestamp() if tz else naive.replace(fold=0).timestamp()


def _clock(text: str) -> tuple[int, int]:
    h, m = text.split(":")
    return int(h), int(m)


def latest_slot(when: dict, t: float, tz=None) -> float | None:
    """The newest time at or before t that `when` names, None if there is none yet."""
    kind = when["type"]
    if kind == "interval":
        step, anchor = when["minutes"] * 60, when["anchor"]
        return None if t < anchor else anchor + ((t - anchor) // step) * step
    h, m = _clock(when["time"])
    today = to_local(t, tz).date()
    for back in range(0, 16):
        day = today - dt.timedelta(days=back)
        if kind == "weekly" and day.weekday() != when["day"]:
            continue
        slot = from_local(dt.datetime.combine(day, dt.time(h, m)), tz)
        if slot <= t:
            return slot
    return None


def next_slot(when: dict, t: float, tz=None) -> float | None:
    """The first time after t that `when` names."""
    kind = when["type"]
    if kind == "interval":
        step, anchor = when["minutes"] * 60, when["anchor"]
        return anchor if t < anchor else anchor + ((t - anchor) // step + 1) * step
    h, m = _clock(when["time"])
    today = to_local(t, tz).date()
    for ahead in range(0, 16):
        day = today + dt.timedelta(days=ahead)
        if kind == "weekly" and day.weekday() != when["day"]:
            continue
        slot = from_local(dt.datetime.combine(day, dt.time(h, m)), tz)
        if slot > t:
            return slot
    return None


def checked_when(when, now: float) -> dict:
    if not isinstance(when, dict):
        raise sp.Refused(400, "Say when it runs.")
    kind = when.get("type")
    if kind in ("daily", "weekly"):
        text = when.get("time")
        if not isinstance(text, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", text):
            raise sp.Refused(400, "The time is HH:MM, from 00:00 to 23:59.")
        out = {"type": kind, "time": text}
        if kind == "weekly":
            day = when.get("day")
            if not isinstance(day, int) or isinstance(day, bool) or not 0 <= day <= 6:
                raise sp.Refused(400, "The day is 0 (Monday) to 6 (Sunday).")
            out["day"] = day
        return out
    if kind == "interval":
        minutes = when.get("minutes")
        if not isinstance(minutes, int) or isinstance(minutes, bool) or not INTERVAL_MIN <= minutes <= 7 * 24 * 60:
            raise sp.Refused(400, f"Every N minutes runs at most every {INTERVAL_MIN} minutes, and at least weekly.")
        anchor = when.get("anchor")
        anchor = anchor if isinstance(anchor, int | float) and not isinstance(anchor, bool) else int(now)
        return {"type": "interval", "minutes": minutes, "anchor": anchor}
    raise sp.Refused(400, "When is daily, weekly or interval.")


def describe_when(when: dict) -> str:
    if when["type"] == "daily":
        return f"every day at {when['time']}"
    if when["type"] == "weekly":
        return f"every {DAYS[when['day']]} at {when['time']}"
    return f"every {when['minutes']} minutes"


def timezone_name() -> str:
    """The machine's time zone, as /etc/localtime names it when it can, with its offset now."""
    name = ""
    with contextlib.suppress(OSError):
        real = os.path.realpath("/etc/localtime")
        if "zoneinfo/" in real:
            name = real.split("zoneinfo/", 1)[1]
    now = dt.datetime.now().astimezone()
    return f"{name or now.tzname()} (UTC{now.strftime('%z')[:3]}:{now.strftime('%z')[3:]})"


# ---------------------------------------------------------------- mods

def mod_info(path: Path) -> dict:
    """What a jar's fabric.mod.json says about it: id, name, version, description and environment."""
    row = {"file": path.name}
    try:
        with zipfile.ZipFile(path) as jar:
            info = jar.getinfo("fabric.mod.json")
            if info.file_size > JAR_JSON_MAX:
                return {**row, "error": "its fabric.mod.json is too big to read"}
            meta = json.loads(jar.read(info).decode("utf-8-sig", "replace"), strict=False)
    except KeyError:
        return {**row, "error": "no fabric.mod.json: not a Fabric mod"}
    except (OSError, zipfile.BadZipFile, ValueError, RuntimeError):
        return {**row, "error": "not a jar this page can read"}
    if not isinstance(meta, dict):
        return {**row, "error": "its fabric.mod.json is not an object"}

    def text(key, most=120):
        value = meta.get(key)
        if not isinstance(value, str):
            return ""
        value = "".join(c if c.isprintable() else " " for c in value).strip()
        return value if len(value) <= most else value[:most - 3] + "..."

    env = meta.get("environment")
    return {**row, "id": text("id", 64), "name": text("name") or text("id", 64), "version": text("version", 64),
            "description": text("description", 300), "environment": env if env in ("client", "server") else "both"}


# ---------------------------------------------------------------- the helper's snapshot list (run by the helper)

def reduce_snapshots(data) -> list[dict]:
    """restic's `snapshots --json`, newest first, cut to what the page shows."""
    rows = []
    for s in data if isinstance(data, list) else []:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or not SNAPSHOT_ID.fullmatch(s["id"]):
            continue
        summary = s.get("summary") if isinstance(s.get("summary"), dict) else {}
        size = summary.get("total_bytes_processed", s.get("size"))   # restic's, or a row cut down already
        tags = [t for t in s.get("tags") or [] if isinstance(t, str) and re.fullmatch(r"[\w.-]{1,40}", t)]
        when = s.get("time") if isinstance(s.get("time"), str) and re.fullmatch(r"[\dT:.+Z-]{10,40}", s["time"]) else ""
        rows.append({"id": s["id"], "short_id": s["id"][:8], "time": when, "tags": tags,
                     "size": size if isinstance(size, int) and not isinstance(size, bool) else None})
    rows.sort(key=lambda r: r["time"], reverse=True)
    return rows[:200]


# ---------------------------------------------------------------- one panel's state

class Extras:
    """What these controls keep for one Panel. The tests replace clock, tz, sleep, rcon, results and unit."""

    def __init__(self, panel):
        self.p = panel
        self.requests = panel.staff / "requests"
        self.results = Path(os.environ.get("MONKEY_HELPER_RESULTS") or HELPER_RESULTS)
        self.unit = HELPER_UNIT
        self.clock = time.time
        self.tz = None
        self.sleep = time.sleep
        self.rcon = self._rcon
        self._rules: tuple[float, dict] | None = None
        self._rules_lock = threading.Lock()
        self._mods: dict[str, tuple] = {}
        self._mods_lock = threading.Lock()
        self._download = threading.Lock()
        self._tokens: dict[str, tuple[str, float]] = {}
        self._sched = threading.Lock()
        self._running: set[str] = set()
        self._helper = threading.Lock()
        self.thread: threading.Thread | None = None
        self.stop = threading.Event()

    def _rcon(self, command: str) -> str:
        """The server's answer to one command, RconError when it didn't take it."""
        done = self.p.docker.compose("exec", "-T", "monkey", "monkey", "rcon", command, timeout=sp.COMMAND_TIMEOUT)
        return sp.server.checked(command, done.stdout.strip(), done.returncode, done.stderr)

    def running(self) -> bool:
        box = sp.staff_status.container(self.p.docker)
        return bool(box and box["state"] == "running")

    # ------------------------------------------------ settings

    def _properties(self) -> tuple[Path, str, os.stat_result]:
        path = self.p.root / "server.properties"
        try:
            st = path.stat()
            return path, path.read_bytes().decode("utf-8"), st
        except FileNotFoundError:
            raise sp.Refused(404, "There is no server.properties yet: start the server once.") from None
        except UnicodeDecodeError:
            raise sp.Refused(415, "server.properties is not plain text: open it in Files.") from None

    def settings(self) -> dict:
        _, text, st = self._properties()
        found = parse_properties(text)
        fields, unknown = [], []
        for key, spec in PROPERTIES.items():
            if key not in found:
                continue
            locked = why_locked(key)
            value = unescape(found[key][1])
            fields.append({"key": key, **spec, "value": sp.MASK if locked and "secret" in locked.lower() else value,
                           "editable": locked is None, **({"locked": locked} if locked else {})})
        for key, (_, raw) in found.items():
            if key in PROPERTIES:
                continue
            locked = why_locked(key)
            secret = sp._SECRET_KEY.search(key) and raw.strip()
            unknown.append({"key": key, "value": sp.MASK if secret else unescape(raw),
                            "locked": locked or "Not a setting this form knows: change it in Files."})
        return {"path": "server.properties", "mtime": st.st_mtime, "groups": list(GROUPS), "fields": fields,
                "other": sorted(unknown, key=lambda r: r["key"])}

    def save_settings(self, user: str, body: dict) -> dict:
        values, mtime = body.get("values"), body.get("mtime")
        if not isinstance(values, dict) or not values or len(values) > len(PROPERTIES):
            raise sp.Refused(400, "values must be the settings to change.")
        if not isinstance(mtime, int | float) or isinstance(mtime, bool):
            raise sp.Refused(400, "mtime must be the number the settings were read with.")
        _, text, st = self._properties()
        if st.st_mtime != mtime:
            raise sp.Refused(409, "Someone else saved server.properties since you opened it: reload the settings.")
        found = parse_properties(text)
        lines = text.splitlines(keepends=True)
        changed = []
        for key, value in values.items():
            if not isinstance(key, str) or key not in PROPERTIES:
                raise sp.Refused(403, f"{str(key)[:40]} is not a setting this form can change: use Files.")
            locked = why_locked(key)
            if locked:
                raise sp.Refused(403, f"{key} is locked. {locked}")
            if key not in found:
                raise sp.Refused(400, f"{key} is not in server.properties.")
            new = coerce(key, value)
            n, raw = found[key]
            if unescape(raw) == new:
                continue
            ending = lines[n][len(lines[n].rstrip("\r\n")):]
            indent = lines[n][:len(lines[n]) - len(lines[n].lstrip())]
            lines[n] = f"{indent}{key}={escape(new)}{ending}"
            changed.append(key)
        if not changed:
            return {"changed": [], "mtime": st.st_mtime}
        # Staff_panel's own save: it checks the time again under its lock, keeps the old file in the history, puts
        # each ******** back as the value on disk and logs "save server.properties".
        shown, _ = sp.mask_secrets("".join(lines))
        done = self.p.save(user, {"path": "server.properties", "text": shown, "mtime": mtime})
        self.p.record(user, "settings", ", ".join(changed))
        return {"changed": changed, "mtime": done["mtime"]}

    # ------------------------------------------------ game rules

    def gamerules(self) -> dict:
        with self._rules_lock:
            if self._rules and self.clock() - self._rules[0] < GAMERULE_CACHE:
                return self._rules[1]
        if not self.running():
            raise sp.Refused(502, "The server isn't running: game rules can only be read while it is.")

        def ask(name):
            try:
                return name, read_rule(self.rcon(f"gamerule {name}"))
            except sp.server.RconError:
                return name, None

        with concurrent.futures.ThreadPoolExecutor(GAMERULE_THREADS) as pool:
            values = dict(pool.map(ask, GAMERULES))
        if all(v is None for v in values.values()):
            raise sp.Refused(502, "The server didn't answer for any game rule: is it still starting?")
        rows = [{"name": n, **spec, "value": values[n], "missing": values[n] is None} for n, spec in GAMERULES.items()]
        result = {"rules": rows}
        with self._rules_lock:
            self._rules = (self.clock(), result)
        return result

    def set_gamerule(self, user: str, body: dict) -> dict:
        name = body.get("name")
        value = gamerule_value(name, body.get("value"))
        command = f"gamerule {name} {value}"
        self.p.record(user, "gamerule", f"{name} {value}")
        try:
            said = self.rcon(command)
        except sp.server.RconError as e:
            raise sp.Refused(502, f"The server did not take it: {sp.masked(str(e))[:200]}") from None
        with self._rules_lock:
            self._rules = None
        return {"name": name, "value": read_rule(said) if read_rule(said) is not None else value,
                "said": sp.masked(said)}

    # ------------------------------------------------ the root helper

    def installed(self) -> bool:
        return self.unit.exists() and self.requests.is_dir()

    def _pending(self) -> list[str]:
        try:
            return sorted(e.name[:-4] for e in os.scandir(self.requests) if e.name.endswith(".req"))
        except OSError:
            return []

    def request(self, user: str, action: str, snapshot: str = "", **fields: str) -> str:
        """Writes one request for the helper and returns its id. The file has only fixed words and checked values."""
        if action not in HELPER_ACTIONS:
            raise ValueError(action)
        for key, value in fields.items():
            if key not in REQUEST_FIELDS or not isinstance(value, str) or not REQUEST_FIELDS[key].fullmatch(value):
                raise ValueError(key)
        if not self.installed():
            raise sp.Refused(503, "The root helper isn't installed, so backups, restores, version switches and world "
                                  "resets or uploads can't be started from here. The owner installs it: "
                                  "sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --install-helper")
        if snapshot and not SNAPSHOT_ID.fullmatch(snapshot):
            raise sp.Refused(400, "A snapshot ID is 8 to 64 hex digits.")
        with self._helper:
            if len(self._pending()) >= HELPER_PENDING_MAX:
                raise sp.Refused(409, "The helper has requests waiting already: give it a minute.")
            rid = f"{dt.datetime.now(sp.server.UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
            lines = [f"action={action}", f"user={user if sp.USER.fullmatch(user) else 'unknown'}"]
            if snapshot:
                lines.append(f"snapshot={snapshot}")
            lines += [f"{key}={fields[key]}" for key in sorted(fields)]
            tmp = self.requests / f".tmp-{rid}"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o640)
            with os.fdopen(fd, "w", encoding="ascii", newline="\n") as f:
                f.write("\n".join(lines) + "\n")
            os.replace(tmp, self.requests / f"{rid}.req")
        return rid

    def _result(self, path: Path) -> dict | None:
        try:
            if path.is_symlink() or path.stat().st_size > RESULT_MAX:
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or data.get("action") not in (*HELPER_ACTIONS, "unknown"):
            return None
        return data

    def jobs(self) -> list[dict]:
        try:
            names = sorted((e.name for e in os.scandir(self.results)
                            if e.name.endswith(".json") and REQUEST_ID.fullmatch(e.name[:-5])), reverse=True)
        except OSError:
            names = []
        rows = []
        for name in names[:JOBS_SHOWN]:
            data = self._result(self.results / name)
            if data:
                rows.append({"id": name[:-5], "action": data["action"], "state": str(data.get("state", ""))[:20],
                             "time": str(data.get("time", ""))[:40],
                             "message": sp.masked(str(data.get("message", "")))[:300]})
        return rows

    def helper(self) -> dict:
        return {"installed": self.installed(), "jobs": self.jobs(), "pending": self._pending()}

    def backup_now(self, user: str) -> dict:
        rid = self.request(user, "backup-now")
        self.p.record(user, "backup-now")
        return {"request": rid}

    def ask_snapshots(self, user: str) -> dict:
        return {"request": self.request(user, "list-snapshots")}

    def snapshots(self) -> dict:
        """The newest snapshot list the helper wrote."""
        try:
            names = sorted((e.name for e in os.scandir(self.results)
                            if e.name.endswith(".json") and REQUEST_ID.fullmatch(e.name[:-5])), reverse=True)
        except OSError:
            names = []
        for name in names:
            data = self._result(self.results / name)
            if data and data["action"] == "list-snapshots" and data.get("state") == "done":
                rows = reduce_snapshots(data.get("snapshots"))
                return {"time": str(data.get("time", ""))[:40], "snapshots": rows, "installed": self.installed()}
        return {"time": None, "snapshots": [], "installed": self.installed()}

    def world_restore(self, user: str, body: dict) -> dict:
        snapshot, confirm = body.get("snapshot"), body.get("confirm")
        if not isinstance(snapshot, str) or not SNAPSHOT_ID.fullmatch(snapshot):
            raise sp.Refused(400, "Pick a snapshot from the list.")
        known = [s["id"] for s in self.snapshots()["snapshots"]]
        if snapshot not in known:
            raise sp.Refused(400, "That snapshot is not in the last list: list the snapshots again.")
        if not isinstance(confirm, str) or confirm.strip() != snapshot[:8]:
            raise sp.Refused(400, f"Type the snapshot's short ID, {snapshot[:8]}, to confirm.")
        for job in self.jobs():
            if job["action"] == "restore" and job["state"] == "running":
                raise sp.Refused(409, "A restore is under way already.")
        with self._helper:
            pending = list(self._pending())
        for rid in pending:
            with contextlib.suppress(OSError):
                if "action=restore" in (self.requests / f"{rid}.req").read_text(encoding="ascii", errors="replace"):
                    raise sp.Refused(409, "A restore is waiting to start already.")
        rid = self.request(user, "restore", snapshot)
        self.p.record(user, "world-restore", snapshot[:8])
        return {"request": rid}

    # ------------------------------------------------ schedules

    @property
    def schedules_file(self) -> Path:
        return self.p.staff / "schedules.json"

    def _load(self) -> list | None:
        """The schedules, [] when there are none yet, None when the file can't be read (then nothing is saved)."""
        try:
            data = json.loads(self.schedules_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, ValueError):
            return None
        rows = data.get("schedules") if isinstance(data, dict) else None
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else None

    def _save(self, rows: list) -> None:
        self.p.staff.mkdir(parents=True, exist_ok=True)
        tmp = self.schedules_file.with_name(f".schedules-{secrets.token_hex(4)}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "schedules": rows}, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.schedules_file)

    def _rows(self) -> list:
        rows = self._load()
        if rows is None:
            raise sp.Refused(500, "schedules.json can't be read: fix or move it (STAFF_DIR) and reload.")
        return rows

    def _checked_schedule(self, body: dict, now: float, old: dict | None = None) -> dict:
        old = old or {}
        name = body.get("name", old.get("name"))
        if not isinstance(name, str) or not name.strip() or len(name) > 60 or any(not c.isprintable() for c in name):
            raise sp.Refused(400, "Give the schedule a name, at most 60 characters.")
        kind = body.get("kind", old.get("kind"))
        if kind not in ("command", "restart", "backup"):
            raise sp.Refused(400, "A schedule runs a command, a restart or a backup.")
        row = {"name": name.strip(), "kind": kind}
        if kind == "command":
            command = body.get("command", old.get("command"))
            row["command"] = sp.Panel.checked_command(command)
        when = body.get("when", old.get("when"))
        if isinstance(when, dict) and isinstance(old.get("when"), dict) and when.get("type") == "interval":
            when = {**when, "anchor": when.get("anchor", old["when"].get("anchor"))}
        row["when"] = checked_when(when, now)
        enabled = body.get("enabled", old.get("enabled", True))
        if not isinstance(enabled, bool):
            raise sp.Refused(400, "enabled is true or false.")
        row["enabled"] = enabled
        return row

    def _shown(self, row: dict, now: float) -> dict:
        out = {k: row.get(k) for k in ("id", "name", "kind", "command", "when", "enabled", "last_run", "last_result",
                                       "created_by")}
        try:
            nxt = next_slot(row["when"], now + LEAD.get(row["kind"], 0), self.tz)
            out["describe"] = describe_when(row["when"])
            out["next"] = to_local(nxt, self.tz).strftime("%Y-%m-%d %H:%M") if nxt and row.get("enabled") else None
        except (KeyError, TypeError, ValueError):
            out["describe"], out["next"] = "not readable", None
        return out

    def schedules(self) -> dict:
        now = self.clock()
        with self._sched:
            rows = self._rows()
        return {"timezone": timezone_name(), "now": to_local(now, self.tz).strftime("%Y-%m-%d %H:%M"),
                "schedules": [self._shown(r, now) for r in rows], "helper": self.installed()}

    def _armed(self, row: dict, now: float) -> dict:
        """The row with its last slot set to now's, so a new or changed schedule waits for its next time."""
        slot = latest_slot(row["when"], now + LEAD.get(row["kind"], 0), self.tz)
        return {**row, "last_slot": slot or 0}

    def add_schedule(self, user: str, body: dict) -> dict:
        now = self.clock()
        row = self._checked_schedule(body, now)
        with self._sched:
            rows = self._rows()
            if len(rows) >= SCHEDULES_MAX:
                raise sp.Refused(409, f"There can be at most {SCHEDULES_MAX} schedules.")
            row = {"id": secrets.token_hex(6), **self._armed(row, now), "created_by": user, "last_run": None,
                   "last_result": None}
            rows.append(row)
            self._save(rows)
        self.p.record(user, "schedule-add", f"{row['name']} ({row['kind']}, {describe_when(row['when'])})")
        return {"schedule": self._shown(row, now)}

    def _find(self, rows: list, sid) -> int:
        if not isinstance(sid, str):
            raise sp.Refused(400, "Say which schedule.")
        for i, r in enumerate(rows):
            if r.get("id") == sid:
                return i
        raise sp.Refused(404, "There is no such schedule.")

    def edit_schedule(self, user: str, body: dict) -> dict:
        now = self.clock()
        with self._sched:
            rows = self._rows()
            i = self._find(rows, body.get("id"))
            row = self._checked_schedule(body, now, rows[i])
            rows[i] = {**rows[i], **self._armed(row, now)}
            self._save(rows)
            row = rows[i]
        self.p.record(user, "schedule-edit", f"{row['name']} ({'on' if row['enabled'] else 'off'})")
        return {"schedule": self._shown(row, now)}

    def delete_schedule(self, user: str, body: dict) -> dict:
        with self._sched:
            rows = self._rows()
            row = rows.pop(self._find(rows, body.get("id")))
            self._save(rows)
        self.p.record(user, "schedule-delete", str(row.get("name", ""))[:60])
        return {"deleted": row.get("id")}

    def tick(self, now: float | None = None) -> list[str]:
        """Starts every schedule whose time has come; returns their ids. A bad row is skipped, never fatal."""
        now = self.clock() if now is None else now
        started = []
        with self._sched:
            rows = self._load()
            if rows is None:
                return []
            changed = False
            for row in rows:
                try:
                    if row.get("enabled") is not True or row.get("id") in self._running:
                        continue
                    lead = LEAD.get(row["kind"], 0)
                    slot = latest_slot(row["when"], now + lead, self.tz)
                    last = row.get("last_slot") or 0
                    if slot is None or slot <= last:
                        continue
                    row["last_slot"], changed = slot, True
                    row["last_run"] = sp.stamp(dt.datetime.fromtimestamp(now, sp.server.UTC))
                    if now + lead - slot > GRACE:
                        row["last_result"] = "missed: the staff page's controls weren't running then"
                        continue
                    row["last_result"] = "running"
                    self._running.add(row["id"])
                    started.append(dict(row))
                except (KeyError, TypeError, ValueError, AttributeError):
                    continue
            if changed:
                self._save(rows)
        for row in started:
            threading.Thread(target=self._run, args=(row,), daemon=True).start()
        return [r["id"] for r in started]

    def _run(self, row: dict) -> None:
        try:
            try:
                result = self._do(row)
            except sp.Refused as e:
                result = f"failed: {e.message}"
            except Exception as e:  # noqa: BLE001 (one schedule must not stop the others)
                result = f"failed ({type(e).__name__})"
            self._finish(row, result)
        finally:
            with self._sched:
                self._running.discard(row["id"])

    def _do(self, row: dict) -> str:
        if row["kind"] == "command":
            done = self.p.command("schedule", {"command": row["command"]})
            said = " ".join(done["output"].split())[:120]
            return ("refused by the server: " if done["refused"] else "done: ") + (said or "no answer")
        if row["kind"] == "backup":
            self.request("schedule", "backup-now")
            return "asked the helper for a backup"
        if not self.running():
            return "skipped: the server isn't running"
        for i, (ahead, words) in enumerate(RESTART_WARNINGS):
            with contextlib.suppress(sp.server.RconError):
                self.rcon(f"say Scheduled restart {words}.")
            nxt = RESTART_WARNINGS[i + 1][0] if i + 1 < len(RESTART_WARNINGS) else 0
            self.sleep(ahead - nxt)
        self.p.power_action("schedule", {"action": "restart-now"})
        return "restarted (after warnings at 5 minutes, 1 minute and 10 seconds)"

    def _finish(self, row: dict, result: str) -> None:
        with self._sched:
            rows = self._load()
            if rows is not None:
                for r in rows:
                    if r.get("id") == row["id"]:
                        r["last_result"] = result[:300]
                self._save(rows)
        self.p.record("schedule", "schedule-run", f"{row['name']}: {result}"[:200])

    def run_scheduler(self) -> None:
        while not self.stop.is_set():
            try:
                self.tick()
            except Exception as e:  # noqa: BLE001 (the loop must outlive one bad look)
                print(f"monkey-panel: the scheduler failed once: {type(e).__name__}", file=sys.stderr, flush=True)
            self.stop.wait(SCHEDULE_TICK)

    # ------------------------------------------------ mods

    def mods(self) -> dict:
        folder = self.p.root / "mods"
        rows = []
        try:
            entries = sorted((e for e in os.scandir(folder) if e.name.lower().endswith((".jar", ".jar.disabled"))),
                             key=lambda e: e.name)
        except FileNotFoundError:
            entries = []
        pinned = self.pinned()
        with self._mods_lock:
            seen = set()
            for e in entries[:MODS_MAX]:
                if e.is_symlink() or not e.is_file(follow_symlinks=False):
                    continue
                st = e.stat(follow_symlinks=False)
                key = (st.st_mtime, st.st_size)
                cached = self._mods.get(e.name)
                if not cached or cached[0] != key:
                    cached = (key, mod_info(Path(e.path)))
                    self._mods[e.name] = cached
                enabled = e.name.lower().endswith(".jar")
                base = e.name if enabled else e.name[:-len(".disabled")]
                rows.append({**cached[1], "size": st.st_size, "enabled": enabled, "pinned": base in pinned})
                seen.add(e.name)
            for name in set(self._mods) - seen:
                del self._mods[name]
        return {"mods": rows, "count": len(rows)}

    def pinned(self) -> set[str]:
        """The jar names the release's install put in mods/ (server/.monkey-state.json); it puts them back at starts."""
        try:
            data = json.loads((self.p.root / ".monkey-state.json").read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return set()
        names = data.get("mods") if isinstance(data, dict) else None
        return {n for n in names if isinstance(n, str)} if isinstance(names, list) else set()

    # ------------------------------------------------ the world download

    def download_link(self, user: str) -> dict:
        now = self.clock()
        token = secrets.token_urlsafe(24)
        with self._helper:
            self._tokens = {t: v for t, v in self._tokens.items() if v[1] > now}
            self._tokens[token] = (user, now + TOKEN_TTL)
        return {"url": f"/api/world-download?token={token}", "expires": TOKEN_TTL}

    def world_download(self, user: str, query: dict) -> "WorldZip":
        token = query.get("token") or ""
        with self._helper:
            found = self._tokens.pop(token, None)
        if not found or found[0] != user or found[1] < self.clock():
            raise sp.Refused(403, "That download link has run out: press Download the world again.")
        return WorldZip(self, user)

    # ------------------------------------------------ bans by address

    def ip_bans(self) -> dict:
        def rows(name):
            try:
                data = json.loads((self.p.root / name).read_text(encoding="utf-8"))
            except FileNotFoundError:
                return []
            except (OSError, ValueError):
                return None
            return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else None

        ips = rows("banned-ips.json")
        out = None
        if ips is not None:
            out = []
            for r in ips:
                with contextlib.suppress(ValueError, TypeError):
                    out.append({"ip": str(ipaddress.ip_address(r.get("ip"))), "reason": sp.masked(str(r.get("reason")
                               or ""))[:REASON_MAX], "created": str(r.get("created") or "")[:40],
                                "expires": str(r.get("expires") or "")[:40]})
        return {"ips": out}

    def ip_ban(self, user: str, body: dict) -> dict:
        target, reason = body.get("target"), body.get("reason") or ""
        if not isinstance(target, str) or not target.strip():
            raise sp.Refused(400, "Type an address or the name of a player who is online.")
        target = target.strip()
        shown = target
        if sp.PLAYER.fullmatch(target):
            pass
        else:
            target = public_ip(target)
            shown = "an address"
        if not isinstance(reason, str) or len(reason) > REASON_MAX or any(not c.isprintable() for c in reason):
            raise sp.Refused(400, f"A reason is one line of at most {REASON_MAX} characters.")
        command = f"ban-ip {target}" + (f" {reason.strip()}" if reason.strip() else "")
        self.p.record(user, "ban-ip", shown)
        return {"said": self._said(command)}

    def ip_pardon(self, user: str, body: dict) -> dict:
        ip = body.get("ip")
        if not isinstance(ip, str):
            raise sp.Refused(400, "Say which address.")
        ip = public_ip(ip.strip())
        self.p.record(user, "pardon-ip", "an address")
        return {"said": self._said(f"pardon-ip {ip}")}

    def _said(self, command: str) -> str:
        try:
            return sp.masked(self.rcon(command))
        except sp.server.RconError as e:
            raise sp.Refused(502, f"The server did not take it: {sp.masked(str(e))[:200]}") from None


def public_ip(text: str) -> str:
    """The address, written the standard way, or Refused for one that isn't a single public address."""
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        raise sp.Refused(400, "That is neither an IPv4 or IPv6 address nor a player name.") from None
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        raise sp.Refused(400, "That is a private, local or reserved address: it could be a proxy's or Docker's, "
                              "and banning it could keep everyone out.")
    return str(ip)


class WorldZip:
    """The world folder as a zip, streamed straight to the browser: nothing the size of the world is written to disk.
    Saving is off while it streams and on again afterwards, whatever happens."""

    def __init__(self, extras: Extras, user: str):
        self.x, self.user = extras, user

    def level(self) -> str:
        try:
            text = (self.x.p.root / "server.properties").read_text(encoding="utf-8", errors="replace")
            raw = parse_properties(text).get("level-name", (0, "world"))[1]
        except OSError:
            raw = "world"
        name = unescape(raw).strip() or "world"
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", name) or ".." in name:
            raise sp.Refused(500, "The world's name in server.properties is not one this page can download.")
        return name

    def files(self, world: Path):
        """(path, name in the zip) for every plain file in the world, in order. No links, no session.lock."""
        base = world.name
        for folder, dirs, names in os.walk(world, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(folder, d)))
            for n in sorted(names):
                path = os.path.join(folder, n)
                if n == "session.lock" or os.path.islink(path) or not os.path.isfile(path):
                    continue
                yield path, base + "/" + Path(os.path.relpath(path, world)).as_posix()

    def stream(self, handler) -> None:
        x, p = self.x, self.x.p
        if not x._download.acquire(blocking=False):
            raise sp.Refused(409, "Someone is downloading the world already: one at a time.")
        held = saving_off = None
        try:
            world = p.root / self.level()
            if not (world / "level.dat").is_file():
                raise sp.Refused(404, "There is no world with a level.dat to download.")
            held = p.lock.take(sp.LOCK_WAIT)
            if held is None:
                raise sp.Refused(409, "A deploy, the daily restart, a backup or a timed job has the deploy lock: "
                                      "try again in a few minutes.")
            if x.running():
                try:
                    saving_off = True
                    x.rcon("save-off")
                    x.rcon("save-all flush")
                except sp.server.RconError:
                    raise sp.Refused(502, "The server did not stop saving, so the world can't be copied whole "
                                          "right now.") from None
                x.sleep(2)
            p.record(self.user, "world-download", world.name)
            name = f"monkey-smp-{world.name}-{dt.datetime.now(sp.server.UTC):%Y%m%d-%H%M}.zip"
            handler.send_response(200)
            handler.send_header("Content-Type", "application/zip")
            handler.send_header("Content-Disposition", f'attachment; filename="{name}"')
            handler.send_header("Cache-Control", "no-store")
            handler.send_header("Connection", "close")
            handler.end_headers()
            handler.close_connection = True
            out = _Counted(handler.wfile)
            try:
                with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
                    for path, arc in self.files(world):
                        z.write(path, arc)
                result = f"done, {out.n // (1024 * 1024)} MB"
            except Exception as e:  # noqa: BLE001 (the headers are gone: the browser sees a broken download)
                result = f"stopped ({type(e).__name__})"
            p.record(self.user, "world-download-result", result)
        finally:
            try:
                if saving_off:
                    with contextlib.suppress(sp.server.RconError):
                        x.rcon("save-on")
            finally:
                if held is not None:
                    p.lock.release(held)
                x._download.release()


class _Counted:
    """A write-only stream that knows how much went through, which is all zipfile needs to write to a socket."""

    def __init__(self, raw):
        self.raw, self.n = raw, 0

    def write(self, data) -> int:
        self.raw.write(data)
        self.n += len(data)
        return len(data)

    def tell(self) -> int:
        return self.n

    def flush(self) -> None:
        self.raw.flush()


class Body:
    """A request body that is a file (staff_panel.RAW): read in chunks, never past `length`. `started` says whether
    any of it was read, so a refusal before that can still read and drop it."""

    def __init__(self, raw, length: int):
        self.raw, self.length, self.left, self.started = raw, length, length, False

    def chunks(self, size: int = 256 * 1024):
        while self.left:
            self.started = True
            chunk = self.raw.read(min(self.left, size))
            if not chunk:
                raise sp.Refused(400, "The upload stopped part way.")
            self.left -= len(chunk)
            yield chunk


# ---------------------------------------------------------------- wiring

_extras_lock = threading.Lock()


def extras(panel) -> Extras:
    with _extras_lock:
        found = getattr(panel, "_apex", None)
        if found is None:
            found = panel._apex = Extras(panel)
        return found


def start_scheduler(panel) -> threading.Thread:
    """The one scheduler thread for this panel (a second call returns the first)."""
    x = extras(panel)
    with _extras_lock:
        if x.thread is None or not x.thread.is_alive():
            x.thread = threading.Thread(target=x.run_scheduler, name="monkey-schedules", daemon=True)
            x.thread.start()
        return x.thread


ROUTES = {
    ("GET", "/api/settings"): lambda p, u, q, b: extras(p).settings(),
    ("PUT", "/api/settings"): lambda p, u, q, b: extras(p).save_settings(u, b),
    ("GET", "/api/gamerules"): lambda p, u, q, b: extras(p).gamerules(),
    ("POST", "/api/gamerules"): lambda p, u, q, b: extras(p).set_gamerule(u, b),
    ("GET", "/api/helper"): lambda p, u, q, b: extras(p).helper(),
    ("POST", "/api/backup-now"): lambda p, u, q, b: extras(p).backup_now(u),
    ("GET", "/api/snapshots"): lambda p, u, q, b: extras(p).snapshots(),
    ("POST", "/api/snapshots"): lambda p, u, q, b: extras(p).ask_snapshots(u),
    ("POST", "/api/world-restore"): lambda p, u, q, b: extras(p).world_restore(u, b),
    ("GET", "/api/schedules"): lambda p, u, q, b: extras(p).schedules(),
    ("POST", "/api/schedules"): lambda p, u, q, b: extras(p).add_schedule(u, b),
    ("PUT", "/api/schedules"): lambda p, u, q, b: extras(p).edit_schedule(u, b),
    ("POST", "/api/schedule-delete"): lambda p, u, q, b: extras(p).delete_schedule(u, b),
    ("GET", "/api/mods"): lambda p, u, q, b: extras(p).mods(),
    ("POST", "/api/world-download"): lambda p, u, q, b: extras(p).download_link(u),
    ("GET", "/api/world-download"): lambda p, u, q, b: extras(p).world_download(u, q),
    ("GET", "/api/ip-bans"): lambda p, u, q, b: extras(p).ip_bans(),
    ("POST", "/api/ip-ban"): lambda p, u, q, b: extras(p).ip_ban(u, b),
    ("POST", "/api/ip-pardon"): lambda p, u, q, b: extras(p).ip_pardon(u, b),
}
# Every route here names who may use it (none falls back to staff_panel's default).
NEEDS = {
    ("GET", "/api/settings"): "admin",
    ("PUT", "/api/settings"): "admin",
    ("GET", "/api/gamerules"): "admin",
    ("POST", "/api/gamerules"): "admin",
    ("GET", "/api/helper"): "moderator",
    ("POST", "/api/backup-now"): "admin",
    ("GET", "/api/snapshots"): "admin",
    ("POST", "/api/snapshots"): "admin",
    ("POST", "/api/world-restore"): "owner",
    ("GET", "/api/schedules"): "admin",
    ("POST", "/api/schedules"): "admin",
    ("PUT", "/api/schedules"): "admin",
    ("POST", "/api/schedule-delete"): "admin",
    ("GET", "/api/mods"): "moderator",
    ("POST", "/api/world-download"): "owner",
    ("GET", "/api/world-download"): "owner",
    ("GET", "/api/ip-bans"): "admin",
    ("POST", "/api/ip-ban"): "admin",
    ("POST", "/api/ip-pardon"): "admin",
}


def register(module) -> None:
    """Adds these routes to staff_panel's (`module` is staff_panel itself, as it runs, __main__ or imported)."""
    global sp
    sp = module
    module.ROUTES.update(ROUTES)
    module.NEEDS.update(NEEDS)
    module.PATHS.update(path for _, path in ROUTES)
    # Imported here, not at the top: the helper runs this file alone (python3 -I) for its snapshot list.
    import staff_host
    staff_host.register(module, sys.modules[__name__])   # mods, versions, world reset and upload, SFTP


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="the staff page's backup helper's snapshot list")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("snapshots", help="restic snapshots --json on stdin, the page's list on stdout")
    ap.parse_args(argv)
    try:
        data = json.loads(sys.stdin.read())
    except ValueError:
        print("staff_apex: restic's snapshot list is not JSON", file=sys.stderr)
        return 1
    json.dump(reduce_snapshots(data), sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
