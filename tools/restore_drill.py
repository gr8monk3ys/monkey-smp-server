"""What the restore drill (deploy/monkey-restore-drill.sh) asks Python: which snapshot to restore, and how far the
restored world had got. It only reads.

    restic snapshots --json | python3 tools/restore_drill.py pick    "ID TIME HOURS": the newest snapshot that is not
                                                                     tagged unflushed, when it was taken (UTC) and how
                                                                     many whole hours ago; exit 1 when there is none
    python3 tools/restore_drill.py level-time LEVEL_DAT              the world's game time in ticks (Data.Time), the
                                                                     number `time query gametime` starts from; exit 1
                                                                     when the file can't be read

A snapshot tagged unflushed (deploy/monkey-backup.sh) was taken while the server didn't answer, so it is the one kind a
restore avoids when there is a choice. Stdlib only, Python 3.10 or newer (the VPS's python3).
"""
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # run with -I: the script's folder isn't on the path
import nbt  # noqa: E402

ID = re.compile(r"[0-9a-f]{8,64}")
UTC = dt.timezone.utc   # noqa: UP017 (datetime.UTC is 3.11+, and the VPS may have 3.10)


def when(text: str) -> dt.datetime:
    """restic's time ("2026-11-09T04:00:01.123456789-08:00" or "...Z") as an aware datetime; nanoseconds dropped."""
    text = re.sub(r"(\.\d{6})\d+", r"\1", text.strip()).replace("Z", "+00:00")
    moment = dt.datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError("no time zone")
    return moment


def pick(snapshots: list, now: dt.datetime) -> tuple[str, dt.datetime] | None:
    """The newest snapshot without the unflushed tag: (its full id, its time), or None."""
    best = None
    for s in snapshots:
        if "unflushed" in (s.get("tags") or []):
            continue
        sid = s.get("id")
        if not isinstance(sid, str) or not ID.fullmatch(sid):
            raise ValueError("a snapshot without a readable id")
        moment = when(s["time"])
        if moment <= now and (best is None or moment > best[1]):
            best = (sid, moment)
    return best


def main(argv=None, stdin=sys.stdin, now=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["pick"]:
        try:
            data = json.load(stdin)
            if not isinstance(data, list):
                raise ValueError("not a list")
            chosen = pick(data, now or dt.datetime.now(UTC))
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            print(f"restore drill: could not read restic's snapshot list ({e})", file=sys.stderr)
            return 1
        if chosen is None:
            print("restore drill: no snapshot to restore (none that is not tagged unflushed)", file=sys.stderr)
            return 1
        sid, moment = chosen
        hours = int(((now or dt.datetime.now(UTC)) - moment).total_seconds() // 3600)
        print(sid, moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), hours)
        return 0
    if len(argv) == 2 and argv[0] == "level-time":
        try:
            ticks = nbt.read(argv[1])["Data"]["Time"]
            if not isinstance(ticks, int) or ticks < 0:
                raise ValueError("Data.Time is not a tick count")
        except (OSError, ValueError, KeyError, TypeError) as e:
            print(f"restore drill: could not read the world's time from level.dat ({e})", file=sys.stderr)
            return 1
        print(ticks)
        return 0
    print("usage: restore_drill.py pick < restic.json | restore_drill.py level-time LEVEL_DAT", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
