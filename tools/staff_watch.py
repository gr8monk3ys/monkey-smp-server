"""What the staff page's Status tab says a problem probably is, and when it tells the staff channel.
tools/staff_status.py calls it on every reading (every 2 minutes); docs/LIVE.md, "The staff page", says what staff see.

advice(data, old) reads one reading (staff.json's own shape) and the one before, and gives a list of
{"id", "title", "fix", "level", "from"}:
- from the log and the crash reports: each recent error and crash description is matched against KNOWN, the
  causes this kind of server has (a mod missing a dependency, the game running out of memory, a broken data pack...),
  so staff read what it probably is and what to do, not only the line. A line that matches nothing is left as it is.
- from the numbers: lag that lasts (the last LAG_READINGS readings past the tick limit), memory or disk running out,
  swap filling, the off-site backup failing.

level is "alert" (worth a message to the staff channel), "warn" (worth a look) or "info" (usually harmless, said so
nobody worries). "from" is the line or the number it came from, already masked by staff_status.plain(). "source" is
"log", "crash" or "machine".

alerts(state, advice, crashes, now) decides what to post: an "alert" when it first shows and then at most once every
QUIET while it lasts, a line when one that was posted has cleared, and each new crash (at most one message in
CRASH_QUIET). Only to STAFF_WEBHOOK_URL (the staff channel), never the public one; staff_status.py posts nothing
without it. The state it keeps (when each was last posted) goes in staff.json, so a restart of the job changes nothing.

Stdlib only, Python 3.10 or newer: it runs on the VPS from the checkout.
"""
import datetime as dt
import re

LAG_MS = 50.0                       # a tick's whole budget at 20 ticks a second
LAG_READINGS = 3                    # readings in a row past it (6 minutes) before it counts as lasting
MEMORY_LOW = 0.10                   # memory available, as a share of all of it
SWAP_HIGH = 0.50                    # swap in use, as a share of all of it
DISK_LOW = 0.10
QUIET = dt.timedelta(hours=6)
CRASH_QUIET = dt.timedelta(minutes=30)
UTC = dt.timezone.utc   # noqa: UP017 (datetime.UTC is 3.11+, and the VPS may have 3.10)
CLEARED = {"lag": "the server keeps up again", "memory": "the machine has memory to spare again",
           "swap": "swap use is back down", "disk": "the disk has room again",
           "backup": "the off-site backup works again"}


class Known:
    def __init__(self, id: str, pattern: str, title: str, fix: str, level: str = "warn"):
        self.id, self.pattern, self.title, self.fix, self.level = id, re.compile(pattern, re.I), title, fix, level


# The first that matches a line is the one shown. Each fix says what to press on the staff page where it can.
KNOWN = (
    Known("out-of-memory", r"OutOfMemoryError|Java heap space|GC overhead limit",
          "The game ran out of memory",
          "Give it more on Server, Java and memory (it takes effect at the next restart), or run spark's health check "
          "to see what fills it. A restart frees the memory for now.", "alert"),
    Known("disk-full", r"No space left on device|Disk quota exceeded",
          "The disk is full, so the world can't save",
          "Free space now: old worlds kept in backups/ after a reset or upload are the usual weight (ask the owner). "
          "Until then the game loses what players do.", "alert"),
    Known("watchdog", r"Watching Server|single server tick took|watchdog",
          "The game froze for over a minute and stopped itself",
          "Its crash report (Files, crash-reports) names what the tick was doing. After the restart, run the spark "
          "profiler on the Server tab while it is slow.", "alert"),
    Known("ticking", r"Ticking (?:block )?entity|Exception ticking|Ticking player",
          "One entity or block keeps crashing the game",
          "The crash report (Files, crash-reports) has its position under 'Entity being ticked' or 'Block entity "
          "being ticked'. Remove it there (or turn off the mod it comes from), or the game crashes again when that "
          "chunk loads.", "alert"),
    Known("missing-dependency", r"requires .{0,80}which is missing|Incompatible mods? found|depends on .{0,80}"
                                r"which is missing|missing dependenc|Mod resolution failed",
          "A mod needs another mod, or another version of one",
          "The line names both. Install the one it needs from Modrinth on the Mods tab, or turn the mod off (owner).",
          "alert"),
    Known("mixin", r"Mixin (?:apply|transformation)|MixinApplyError|InvalidMixin|mixin.{0,40}failed",
          "A mod failed to patch the game",
          "Usually two mods that clash, or a mod built for another game version. The line names the mod's mixin: turn "
          "it off on the Mods tab (owner) and restart."),
    Known("entrypoint", r"Could not execute entrypoint|EntrypointException",
          "A mod failed while the game was starting",
          "The line names the mod. Check it is for this game version and loader (Mods tab), or turn it off."),
    Known("port", r"FAILED TO BIND TO PORT|Address already in use",
          "Another program holds the server's port",
          "Usually an old copy of the server still running: Stop, wait a minute, then Start. If it stays, ask the "
          "owner.", "alert"),
    Known("chunk", r"Couldn't load chunk|Failed to load chunk|Couldn't read chunk|Region ?file|corrupt",
          "A chunk failed to load: it may be damaged",
          "Note the position if the line has one. Putting that region back from a backup fixes it; until then the "
          "chunk may reset when someone walks into it."),
    Known("save", r"Failed to save|Couldn't save|Exception saving",
          "Part of the world didn't save",
          "Check the disk on Status first. If it has room, the line names what failed; a mod's own data is the usual "
          "cause."),
    Known("datapack", r"Failed to load function|Couldn't parse data file|Couldn't load .{0,60}data ?pack|"
                      r"Failed to load datapack|Unknown function",
          "A data pack has a broken file",
          "Mods tab, Data packs: Turn all off, then turn them back on one at a time to find it."),
    Known("network", r"Error sending packet|Connection reset|Broken pipe|io\.netty|timed out",
          "A player's connection dropped",
          "Usually harmless: someone's internet blinked. Worth a look only if it never stops.", "info"),
    Known("crash", r"Exception in server tick loop|Exception in .{0,40}tick",
          "The game crashed",
          "Open the newest report in Files, crash-reports: the first 'Caused by' line names the mod.", "alert"),
)


def known(text) -> Known | None:
    if not isinstance(text, str):
        return None
    return next((k for k in KNOWN if k.pattern.search(text)), None)


def _row(k: Known, said: str, source: str) -> dict:
    return {"id": k.id, "title": k.title, "fix": k.fix, "level": k.level, "from": said, "source": source}


def _share(part, whole) -> float | None:
    return part / whole if isinstance(part, int | float) and isinstance(whole, int | float) and whole > 0 else None


def advice(data: dict) -> list[dict]:
    """What the reading's problems probably are, the worst first; one row for each cause."""
    found: dict[str, dict] = {}
    problems = data.get("problems") if isinstance(data.get("problems"), dict) else {}
    for crash in problems.get("crashes") or []:
        text = crash.get("text") if isinstance(crash, dict) else None
        k = known(text) or (KNOWN[-1] if text is not None or isinstance(crash, dict) else None)
        if k:
            found.setdefault(k.id, _row(k, text or "a crash report with no description", "crash"))
    for error in problems.get("errors") or []:
        k = known(error.get("text")) if isinstance(error, dict) else None
        if k:
            found.setdefault(k.id, _row(k, error["text"], "log"))

    history = data.get("history") if isinstance(data.get("history"), list) else []
    last = [row[2] for row in history[-LAG_READINGS:] if isinstance(row, list) and len(row) > 2]
    if len(last) == LAG_READINGS and all(isinstance(p95, int | float) and p95 > LAG_MS for p95 in last):
        found["lag"] = {"id": "lag", "source": "machine", "level": "alert",
                        "title": "The server has been falling behind for 6 minutes",
                        "fix": "Players feel it as lag. Run the spark profiler (Server tab) while it is slow: it names "
                               "what takes the time. Many players in one place, big farms and new chunks being "
                               "made are the usual causes.",
                        "from": f"P95 tick time {max(last):.0f} ms, past the {LAG_MS:.0f} ms limit"}
    host = data.get("host") if isinstance(data.get("host"), dict) else {}
    mem, swap, disk = (host.get(k) if isinstance(host.get(k), dict) else {} for k in ("memory", "swap", "disk"))
    free = _share(mem.get("available"), mem.get("total"))
    if free is not None and free < MEMORY_LOW:
        found["memory"] = {"id": "memory", "source": "machine", "level": "alert",
                           "title": "The machine is nearly out of memory",
                           "fix": "The game may be stopped by the system to free it. Lower its memory on Server, Java "
                                  "and memory if something else needs room, or restart it to free what it holds.",
                           "from": f"{free:.0%} of the memory free"}
    used = _share((swap.get("total") or 0) - (swap.get("free") or 0), swap.get("total"))
    if used is not None and used > SWAP_HIGH:
        found["swap"] = {"id": "swap", "source": "machine", "level": "warn",
                         "title": "The machine is using a lot of swap",
                         "fix": "Swap is the disk standing in for memory, and it makes ticks slow. Usually the game "
                                "has more memory than the machine can spare: lower it on Server, Java and memory.",
                         "from": f"{used:.0%} of swap in use"}
    room = _share(disk.get("free"), disk.get("total"))
    if room is not None and room < DISK_LOW:
        found["disk"] = {"id": "disk", "source": "machine", "level": "alert",
                         "title": "The disk is nearly full",
                         "fix": "When it fills, the world stops saving. Old worlds kept in backups/ after a reset or "
                                "an upload are the usual weight: ask the owner to clear some.",
                         "from": f"{room:.0%} of the disk free"}
    backups = data.get("backups") if isinstance(data.get("backups"), dict) else {}
    if backups.get("offsite") == "failing":
        found["backup"] = {"id": "backup", "source": "machine", "level": "alert",
                           "title": "The off-site backup is failing",
                           "fix": "The last hourly copy failed, so a lost machine would lose the world back to the "
                                  "last good one. The owner checks journalctl -u monkey-backup.",
                           "from": "monkey-backup.sh marked it failing"}
    order = {"alert": 0, "warn": 1, "info": 2}
    return sorted(found.values(), key=lambda row: order.get(row["level"], 3))


def _when(text) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None


def alerts(state, rows: list[dict], crashes, now: dt.datetime) -> tuple[list[str], dict]:
    """(the messages to post now, the state to keep). `state` is the last reading's; anything unreadable starts afresh
    and posts what is wrong now."""
    state = state if isinstance(state, dict) else {}
    posted = {k: v for k, v in (state.get("posted") or {}).items() if isinstance(k, str) and _when(v)} \
        if isinstance(state.get("posted"), dict) else {}
    stamp = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    messages = []
    now_ids = set()
    machine = {row["id"] for row in rows if row.get("source") == "machine"} | set(state.get("machine") or [])
    for row in rows:
        # A crash has its own message below, whatever its cause.
        if row.get("level") != "alert" or row.get("source") == "crash":
            continue
        now_ids.add(row["id"])
        last = _when(posted.get(row["id"]))
        if last is None or now - last >= QUIET:
            again = " (still)" if last is not None else ""
            messages.append(f"Monkey SMP: {row['title']}{again}. {row['from']}. {row['fix']}")
            posted[row["id"]] = stamp
    # A number back to normal is worth a line; a log line ages out of the page after a day, which is no news.
    for gone in sorted(set(posted) - now_ids - {"crash"}):
        if gone in machine:
            messages.append(f"Monkey SMP: cleared: {CLEARED.get(gone, gone)}.")
        del posted[gone]

    # A crash is news each time: the newest report since the last one posted, at most one message in CRASH_QUIET.
    seen = _when(state.get("crash_seen"))
    rows_by_time = sorted((c for c in crashes or [] if isinstance(c, dict) and _when(c.get("when"))),
                          key=lambda c: _when(c["when"]))
    fresh = [c for c in rows_by_time if seen is None or _when(c["when"]) > seen]
    crash_seen = rows_by_time[-1]["when"] if rows_by_time else state.get("crash_seen")
    last_crash = _when(posted.get("crash"))
    if fresh and seen is not None and (last_crash is None or now - last_crash >= CRASH_QUIET):
        newest = fresh[-1]
        k = known(newest.get("text")) or KNOWN[-1]
        more = f" ({len(fresh)} crash reports since the last message)" if len(fresh) > 1 else ""
        messages.append(f"Monkey SMP: the game crashed{more}: {newest.get('text') or 'no description'}. "
                        f"{k.title}: {k.fix}")
        posted["crash"] = stamp
    elif last_crash is not None and now - last_crash >= CRASH_QUIET:
        del posted["crash"]
    # The very first reading only notes the newest crash: what was there before the job watched is not news.
    if seen is None and crash_seen is None:
        crash_seen = stamp
    return messages, {"posted": posted, "crash_seen": crash_seen,
                      "machine": sorted(k for k in posted if k in machine)}
