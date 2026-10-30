"""Border acts: grows the world border on the season's dates, then fits the live map to it.

    python3 tools/border.py plan [--season N]                  each act of a season: its week, date and sizes
    python3 tools/border.py status WORLD [--at TIME]           the border, the acts and the map (the timer's --check)
    python3 tools/border.py commands WORLD [--at TIME]         the RCON commands for now (changes nothing)
    python3 tools/border.py send WORLD --docker DIR [--at TIME]   sends them (deploy/monkey-border.sh, hourly)

docs/SEASONS.md, "The acts of a season": the border breaks twice a season, in the Saturday event slot (6 PM
Pacific), from 2500 to 4000 and then to 6000, and the Nether's with it at 1:8 (since 26.3 each dimension has its
own border; the monkey-rules pack sets the starting ones once per world). ACTS has each season's acts by week;
the weeks' dates come from tools/season_calendar.py's SEASONS, so moving a season moves its acts.

What the timer does, from the saved world (the server saves every 5 minutes, so an hourly job sees its own work):
- **The act.** Once an act's time has come and the world hasn't recorded it (#border_act ev.state, the last
  act done; the world's own, so a new season's starts from none), it sends `worldborder set SIZE 12000` in each
  dimension whose saved border is heading for less than the act's size (10 minutes to grow: since 26.3 the
  time is in ticks, 20 a second), tells everyone
  online, and records the act. Only the latest act that is due counts, and a border is never shrunk: one
  already that size or bigger (grown by hand) is left alone, and a recorded act never runs again, so the
  finale's shrink is safe. Nothing before the season's launch (#launched rw.day), in a locked world (the
  off-season), or in a season ACTS has no acts for.
- **The map.** While both borders are at the latest act's size, a map whose render-mask doesn't match its
  border (tools/map_border.py) gets its config written and `bluemap reload`; the maps it changed are kept in
  config/bluemap/monkey-map-purge.txt, and the next run sends `bluemap purge MAP` for each (BlueMap answers a
  reload before it has loaded, so the purge waits an hour). A purge BlueMap answers "still loading" stays
  listed for the next run. So the map follows an act about two hours later, and is never fitted to the finale's
  shrinking border (the land outside was open all season).

The timer is installed for Season II (docs/SEASONS.md, "Season II"). Season I has no acts here: staff grow its
border by hand (docs/LIVE.md), and a timer installed early must not repeat a hand act it reads from a save made
before it (that would start the growth again and announce it twice). Stdlib only (plus tools/), Python 3.10 or
newer.
"""
import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import boss
import finale

import map_border
import rcon as server
import saved_world
import season_calendar
from challenges import LAUNCHED
from events import STATE

# Each season's acts: (week, the Overworld border's new width). The Nether's is 1:8 of it.
# Season I (weeks 2 and 7, by hand) is left out on purpose: the timer does nothing in a Season I world.
ACTS = {
    2: ((2, 4000), (8, 6000)),   # Season II, proposed: 20 February and 3 April 2027
}
NETHER_SCALE = 8
GROW_SECONDS = 600
TICKS = 20                    # `worldborder set SIZE TIME` takes ticks since 26.3 (600 would grow it in 30 seconds)
EVENT_TIME = dt.time(18, 0)   # the Saturday event slot, Pacific
OVERWORLD, NETHER = saved_world.OVERWORLD, "minecraft:the_nether"
PURGE = Path("config") / "bluemap" / "monkey-map-purge.txt"
LOCKED = "#season_locked"   # in ev.state: the season lock (monkey:events/season/lock)
DONE = "#border_act"        # in ev.state: the last border act done in this world
SEASON = "#season"          # in rw.day: which season the world is


@dataclass(frozen=True)
class Act:
    season: int
    number: int    # 1, 2: the season's first and second border act
    week: int
    size: int      # the Overworld's new width; the Nether's is size / NETHER_SCALE
    at: dt.datetime

    @property
    def nether(self) -> float:
        return self.size / NETHER_SCALE

    def sizes(self) -> dict[str, float]:
        return {OVERWORLD: self.size, NETHER: self.nether}


def acts(season: int) -> list[Act]:
    """A season's border acts, first first; none for a season with no calendar or no acts."""
    calendar = season_calendar.SEASONS.get(season)
    if calendar is None:
        return []
    return [Act(season, i, week, size,
                dt.datetime.combine(calendar.saturday(week), EVENT_TIME, season_calendar.PACIFIC))
            for i, (week, size) in enumerate(ACTS.get(season, ()), 1)]


def width(size: float) -> str:
    return f"{size:g}"


def act_commands(act: Act, borders: dict[str, saved_world.SavedBorder]) -> list[str]:
    """An act not yet recorded: the `worldborder set`s it still needs (a border heading for less than its size),
    the news when the Overworld's grows, and the record, so a failed set is tried again. After the record, the
    act's border boss (tools/boss.py): the pack takes each act once and does nothing while its switch is off,
    and a pack that refuses or isn't there can't hold the act back."""
    out = [f"execute in {dim} run worldborder set {width(size)} {GROW_SECONDS * TICKS}"
           for dim, size in act.sizes().items() if borders[dim].target < size]
    if any(OVERWORLD in c for c in out):
        news = (f"The border breaks: over the next {GROW_SECONDS // 60} minutes it grows to {act.size} blocks "
                f"across, and the Nether's to {width(act.nether)}. New land to the edge.")
        out.append("tellraw @a " + json.dumps({"text": news, "color": "gold"}, separators=(",", ":")))
    centre = borders[OVERWORLD]
    return out + [f"scoreboard players set {DONE} {STATE} {act.number}",
                  boss.act_command(act.season, act.number, centre.center_x, centre.center_z, act.size)]


def finale_due(season: int, scores: dict[str, dict[str, int]], when: dt.datetime) -> bool:
    """The finale (tools/finale.py) is due: a season with border acts, its time has come, the saved world has the
    finale's switch on and it hasn't started there (the pack runs it once a world, so a retry is harmless)."""
    at = finale.finale_at(season) if ACTS.get(season) else None
    held = scores.get(finale.OBJ, {})
    return at is not None and at <= when and held.get("#on", 0) == 1 and held.get("#started", 0) == 0


@dataclass
class Run:
    """What one run would do: the act's commands, the maps to write, the purges, and why it does nothing."""
    season: int = 0
    act: Act | None = None
    borders: dict[str, saved_world.SavedBorder] = field(default_factory=dict)
    commands: list[str] = field(default_factory=list)
    maps: list[map_border.MapFit] = field(default_factory=list)
    purges: list[str] = field(default_factory=list)
    why: str = ""
    warnings: list[str] = field(default_factory=list)


def pending_purges(server_dir: Path) -> list[str]:
    path = server_dir / PURGE
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_run(world: Path, when: dt.datetime) -> Run:
    run = Run()
    server_dir = world.parent
    run.purges = pending_purges(server_dir)
    board = saved_world.scoreboard(world)
    scores = board.scores if board else {}
    holder, objective = LAUNCHED.split()
    run.season = scores.get("rw.day", {}).get(SEASON, 0)
    if not scores.get(objective, {}).get(holder):
        run.why = "the season hasn't launched"
        return run
    if scores.get(STATE, {}).get(LOCKED) == 1:
        run.why = "the season is locked"
        return run
    season_acts = acts(run.season)
    if not season_acts:
        run.why = f"no border acts for season {run.season}"
        return run
    due = [a for a in season_acts if a.at <= when]
    if not due:
        run.why = "no border act yet"
        return run
    run.act = due[-1]
    for dim in (OVERWORLD, NETHER):
        found = saved_world.border(world, dim)
        if found is None:
            run.why = f"no saved border for {dim} (a 26.3 world that has been saved?)"
            return run
        run.borders[dim] = found
    if scores.get(STATE, {}).get(DONE, 0) < run.act.number:
        run.commands = act_commands(run.act, run.borders)
    elif finale_due(run.season, scores, when):
        centre = run.borders[OVERWORLD]
        run.commands = [finale.start_command(centre.center_x, centre.center_z)]
        return run
    at_act = all(run.borders[dim].target == size for dim, size in run.act.sizes().items())
    if not run.commands and at_act and not run.purges:
        try:
            run.maps = [fit for fit in map_border.fit_maps(server_dir) if fit.changed]
        except ValueError as e:
            run.warnings.append(f"map: {e}; the map isn't fitted")
    if not run.commands and not run.maps and not run.purges:
        run.why = f"act {run.act.number} is done" + ("" if at_act else " (the border has moved on since)")
    return run


def commands(world: Path, when: dt.datetime) -> list[str]:
    """What the timer sends now: the act's commands, `bluemap reload` for maps it would fit, or the purges."""
    run = read_run(world, when)
    return run.commands + (["bluemap reload"] if run.maps else []) + [f"bluemap purge {m}" for m in run.purges]


def describe(command: str, answer: str) -> str:
    """The log's line for a command: the boss's and the finale's answers as words (their CODES)."""
    for call, codes in ((f"function {boss.NS}:boss/act", boss.CODES), (f"function {finale.NS}:finale/start",
                                                                          finale.CODES)):
        if command.startswith(call):
            return server.coded(call, codes)(command, answer)
    return f"{command}: {answer or 'ok'}"


def send(rcon, world: Path, when: dt.datetime, log=print) -> int:
    """Sends the act, or writes the fitted maps and reloads BlueMap, or purges the maps reloaded last time. A
    server that isn't running is skipped (the next hour tries again); none of it is ever sent twice over."""
    run = read_run(world, when)
    for warning in run.warnings:
        log(warning)
    server_dir = world.parent
    try:
        up = rcon.running()
    except server.RconError as e:
        log(f"can't tell whether the server is running: {e}")
        return 1
    if not up:
        if run.commands or run.maps or run.purges:
            log("server not running: nothing sent (the next hour tries again)")
        return 0
    # stop: a failed `worldborder set` must not let the record after it through, or the act never runs again.
    ok = server.send(rcon, run.commands, log, describe, stop=True) if run.commands else True
    if run.maps:
        for fit in run.maps:
            fit.conf.write_text(fit.fitted, encoding="utf-8", newline="")   # in place: keeps the owner
            log(f"map: {map_border.report(fit)}")
        (server_dir / PURGE).write_text("".join(f"{fit.id}\n" for fit in run.maps), encoding="utf-8")
        ok = server.send(rcon, ["bluemap reload"], log) and ok
    if run.purges:
        left = []
        for map_id in run.purges:
            try:
                answer = rcon(f"bluemap purge {map_id}")
            except server.RconError as e:
                log(f"refused or failed: {e}")
                left.append(map_id)
                ok = False
                continue
            log(f"bluemap purge {map_id}: {answer or 'ok'}")
            if "loading" in answer.lower():
                left.append(map_id)
        if left:
            (server_dir / PURGE).write_text("".join(f"{m}\n" for m in left), encoding="utf-8")
        else:
            (server_dir / PURGE).unlink()
    return 0 if ok else 1


def status(world: Path, when: dt.datetime) -> int:
    run = read_run(world, when)
    print(f"season {run.season or '?'}; now {season_calendar.words(when)['date']}")
    for act in acts(run.season):
        state = "due" if act.at <= when else "to come"
        print(f"  act {act.number}, week {act.week}: {season_calendar.day_words(act.at.date())} 6 PM Pacific, "
              f"{act.size} (Nether {width(act.nether)}): {state}")
    at = finale.finale_at(run.season) if ACTS.get(run.season) else None
    if at is not None:
        print(f"  the finale: {season_calendar.day_words(at.date())} 6 PM Pacific, closing on the Overworld border's "
              f"centre: {'due' if at <= when else 'to come'} (its switch and start are the saved world's #on and "
              f"#started {finale.OBJ})")
    for dim, found in run.borders.items():
        moving = f", growing to {width(found.target)}" if found.target != found.size else ""
        print(f"  {dim}: {width(found.size)} wide{moving}, centred on {found.center_x:g}, {found.center_z:g}")
    for fit in run.maps:
        print(f"  map to fit: {map_border.report(fit)}")
    for map_id in run.purges:
        print(f"  map to purge: {map_id}")
    for warning in run.warnings:
        print(f"  {warning}")
    print(run.why or "something to send (see the commands)")
    return 0


def plan(season: int) -> str:
    out = []
    for act in acts(season):
        said = season_calendar.words(act.at)
        out.append(f"Season {season}, act {act.number} (week {act.week}): {said['date']}, {said['pacific']}: "
                   f"{act.size} wide, the Nether {width(act.nether)}")
    return "\n".join(out) or f"no border acts for season {season}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Border acts: the scheduled worldborder set, and the live map.")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan", help="each act of a season: its week, date and sizes")
    p.add_argument("--season", type=int, default=2)
    server.job_subcommands(sub, "sends them to the running server (deploy/monkey-border.sh, hourly)",
                           world=True, others=[("status", "the border, the acts and the map")])
    args = ap.parse_args(argv)
    if args.command == "plan":
        print(plan(args.season))
        return 0
    if args.command == "status":
        return status(args.world, server.job_time(args))
    return server.run_job(args, lambda when: commands(args.world, when),
                          lambda rcon, when: send(rcon, args.world, when))


if __name__ == "__main__":
    sys.exit(main())
