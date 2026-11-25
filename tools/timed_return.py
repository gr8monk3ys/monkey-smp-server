"""The 24-hour return: an eliminated player comes back on their own a day later (docs/relaunch/lifesteal.md).

LifeStealZ locks a player out at 0 hearts until someone revives them, and keeps no time of elimination, so this
timed job (deploy/monkey-return.sh, every 10 minutes) does the waiting: it reads LifeStealZ's player data
(plugins/LifeStealZ/userData.db, read-only), notes when it first saw each player at 0 hearts, and once WAIT has
passed sends `lifestealz:revive <name>`, which brings them back with the config's reviveHearts (3). A Revive Beacon
or a Revival Night that gets there first takes them off the list; a later elimination starts a new day.

It only runs inside the relaunch's season (tools/season_calendar.py's RELAUNCH), and stops at the finale's start
(Saturday 10 April 2027, 6 PM Pacific), after which nobody comes back until the next season.

    python3 tools/timed_return.py waiting WORLD [--at TIME]   who is out and when each comes back (changes nothing)
    python3 tools/timed_return.py commands WORLD [--at TIME]  the revives due now (changes nothing)
    python3 tools/timed_return.py send WORLD --docker DIR     notes new eliminations, sends the revives due
    python3 tools/timed_return.py packs-on --docker DIR       needs no data pack: always "on"

WORLD is the live server's world folder (server/world): the plugins folder is beside it. The first-seen times are
kept in the release's docker folder (.monkey-return.json, beside server/), which the job's user can write; --state
names another file. A missing database (no LifeStealZ yet, the modded season) means nobody to bring back.

Stdlib only plus tools/rcon.py and tools/season_calendar.py, Python 3.10 or newer: it runs on the VPS from the checkout.
"""
import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

import rcon
import season_calendar

UTC = dt.timezone.utc   # noqa: UP017 (datetime.UTC is 3.11+, and the VPS may have 3.10)

WAIT = dt.timedelta(hours=24)
MIN_HEARTS = 0                       # LifeStealZ's minHearts: at or below it a player is eliminated
FINALE_AT = dt.datetime.combine(season_calendar.RELAUNCH_FINALE, dt.time(18, 0), season_calendar.PACIFIC)
STATE_NAME = ".monkey-return.json"


def database(world: Path) -> Path:
    return world.parent / "plugins" / "LifeStealZ" / "userData.db"


def state_file(world: Path, given: Path | None = None) -> Path:
    """Where the first-seen times are kept: --state, else the release's docker folder (LIVE_DIR/docker)."""
    return given or world.parent.parent / "docker" / STATE_NAME


def in_season(when: dt.datetime) -> bool:
    """Whether returns run at `when`: from the relaunch's launch until the finale starts."""
    return season_calendar.RELAUNCH.launch <= when < FINALE_AT


def eliminated(db: Path) -> dict[str, str]:
    """The players at or below MIN_HEARTS, as {uuid: name}. Nothing when there is no database yet."""
    if not db.exists():
        return {}
    with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True, timeout=10) as conn:
        rows = conn.execute("SELECT uuid, name FROM hearts WHERE maxhp <= ?", (MIN_HEARTS * 2.0,)).fetchall()
    return {str(uuid): str(name) for uuid, name in rows}


def load(path: Path) -> dict[str, dict]:
    """The kept list: {uuid: {"name", "since"}}. A missing or unreadable file starts empty (the day restarts)."""
    try:
        kept = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in kept.items() if isinstance(v, dict) and "since" in v} if isinstance(kept, dict) else {}


def save(path: Path, kept: dict[str, dict]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(kept, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def track(kept: dict[str, dict], out: dict[str, str], when: dt.datetime) -> dict[str, dict]:
    """The list after this run's look: players still out keep their time, new ones start now, players no
    longer out (revived some other way) drop off."""
    return {uuid: kept.get(uuid, {"name": name, "since": when.astimezone(UTC).isoformat()}) | {"name": name}
            for uuid, name in out.items()}


def back_at(entry: dict) -> dt.datetime:
    return dt.datetime.fromisoformat(entry["since"]) + WAIT


def due(kept: dict[str, dict], when: dt.datetime) -> list[str]:
    """The uuids whose day is up at `when`, oldest first; none outside the season."""
    if not in_season(when):
        return []
    ready = [(back_at(e), uuid) for uuid, e in kept.items() if back_at(e) <= when]
    return [uuid for _, uuid in sorted(ready)]


def revive(name: str) -> str:
    return f"lifestealz:revive {name}"


def commands(world: Path, when: dt.datetime, state: Path | None = None) -> list[str]:
    kept = track(load(state_file(world, state)), eliminated(database(world)), when)
    return [revive(kept[uuid]["name"]) for uuid in due(kept, when)]


def waiting(world: Path, when: dt.datetime, state: Path | None = None) -> list[str]:
    kept = track(load(state_file(world, state)), eliminated(database(world)), when)
    if not in_season(when):
        return [f"outside the season (it runs until {season_calendar.words(FINALE_AT)['date']}, 6 PM Pacific): "
                f"nobody comes back on a timer; {len(kept)} out"]
    if not kept:
        return ["nobody is out"]
    return [f"{e['name']}: back {season_calendar.short_day(back_at(e))} "
            f"{season_calendar.clock(back_at(e).astimezone(season_calendar.PACIFIC))} Pacific"
            for e in sorted(kept.values(), key=back_at)]


def send(server, world: Path, when: dt.datetime, state: Path | None = None) -> int:
    """Notes who is out, sends the revives due, and keeps the list. A revive that didn't go through stays on it
    for the next run."""
    path = state_file(world, state)
    try:
        kept = track(load(path), eliminated(database(world)), when)
    except sqlite3.Error as e:
        print(f"can't read {database(world)}: {e}")
        return 1
    ready = due(kept, when)
    code = 0
    if ready:
        try:
            up = server.running()
        except rcon.RconError as e:
            print(f"can't tell whether the server is running: {e}")
            up, code = False, 1
        if not up and not code:
            print("server not running: the revives wait for the next run")
        for uuid in ready if up else []:
            command = revive(kept[uuid]["name"])
            try:
                print(f"{command}: {server(command) or 'ok'}")
                kept.pop(uuid)
            except rcon.RconError as e:
                print(f"{command}: refused or failed: {e}")
                code = 1
    save(path, kept)
    return code


def main(argv=None, server=rcon.Docker) -> int:
    ap = argparse.ArgumentParser(description="Brings eliminated players back after 24 hours (the relaunch).")
    sub = ap.add_subparsers(dest="command", required=True)
    rcon.job_subcommands(sub, "note who is out and send the revives due", world=True,
                         others=[("waiting", "who is out and when each comes back (changes nothing)")])
    for p in sub.choices.values():
        if p.prog.split()[-1] != "packs-on":
            p.add_argument("--state", type=Path, help=f"the kept list (default: ../docker/{STATE_NAME})")
    args = ap.parse_args(argv)
    if args.command == "packs-on":
        print("data packs on: none needed")
        return 0
    when = rcon.job_time(args)
    if args.command == "send":
        return send(server(args.docker), args.world, when, args.state)
    out = (waiting if args.command == "waiting" else commands)(args.world, when, args.state)
    if out:
        print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
