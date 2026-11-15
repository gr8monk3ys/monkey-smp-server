"""Whether a world data pack is on: the one place that reads the server's `datapack list enabled`.

    on(said, names)                  the NAMES (datapacks folder entries) the answer shows on, in its order
    off(said, names)                 the NAMES it doesn't show on
    listing(ask, folder, box)        the answer, from the copy kept in the docker folder when it is fresh
    forget(folder)                   staff changed a pack: drop that copy
    at_restart(folder) / set_at_restart(folder, name, verb, write)
                                     the changes staff asked for at the next restart (deploy/monkey-deploy.sh,
                                     packs_at_restart, applies them)
    pack_entry(name)                 a name this module (and the staff page) will put in a command

Every caller uses the same rule: a pack is on when the answer shows it whole, as [file/NAME] or [file/NAME (world)],
so `monkey-drops` is never read as on because `monkey-drops-old` is, and a name with spaces ("Enchant Disabler for
DnT 5.3.0.zip") is never cut at its first space. An answer that isn't the enabled list raises Unreadable: it never
reads as "off".

The copy (PACKS_CACHE) exists because every listing makes the server re-read every pack and mod on its main
thread; the timers asked 28 times an hour (2026-11-11). It is used for PACKS_CACHE_S, only for the running container
it came from (`box`: a restart is a new container, and may have changed the packs), and only when it was asked after
the last forget(). The staff page asks fresh (fresh=True) and keeps its answer for the timers.

Stdlib only, and no import of rcon: tools/rcon.py (the server adapter, and the `packs-on` command the timers run)
imports this.
"""
import contextlib
import json
import os
import re
import time
from collections.abc import Callable, Iterable
from pathlib import Path

LIST = "datapack list enabled"
PACKS_CACHE = ".packs-enabled.json"     # in the live docker folder
PACKS_CACHE_S = 1800
PACKS_FORGOT = ".packs-forgot"          # when staff last changed a pack (forget)
# In the live docker folder: "enable NAME" / "disable NAME" lines that monkey-deploy.sh applies at a restart.
AT_RESTART = ".packs-at-restart"


class Unreadable(Exception):
    """The server's answer isn't the enabled list (an error, a refusal, nothing)."""


def pack_entry(name) -> bool:
    """A name in the datapacks folder that may be named in a command (datapack enable "file/NAME"): it may have
    spaces ("Enchant Disabler for DnT 5.3.0.zip"), but no quote, backslash or slash, no "..", no control
    character, and it starts with a letter or digit."""
    return (isinstance(name, str) and 0 < len(name) <= 128 and name.isprintable() and name[0].isalnum()
            and not any(c in name for c in '"\\/') and ".." not in name)


def _readable(said: str) -> str:
    if not isinstance(said, str) or "enabled" not in said:
        raise Unreadable(f"{LIST} answered: {str(said)[-300:] or 'nothing'}")
    return said


def on(said: str, names: Iterable[str]) -> list[str]:
    """The NAMES that `datapack list enabled`'s answer shows on, in the answer's order. Each is found whole."""
    _readable(said)
    found = []
    for name in names:
        m = re.search(r"\[file/" + re.escape(name) + r"(?: \([^()\[\]]*\))?\]", said)
        if m:
            found.append((m.start(), name))
    return [name for _, name in sorted(found)]


def off(said: str, names: Iterable[str]) -> list[str]:
    """The NAMES the answer doesn't show on, in the order given."""
    names = list(names)
    shown = set(on(said, names))
    return [n for n in names if n not in shown]


def _forgot_at(folder: Path) -> float:
    try:
        return float((Path(folder) / PACKS_FORGOT).read_text(encoding="ascii"))
    except (OSError, ValueError):
        return 0.0


def listing(ask: Callable[[str], str], folder: Path, box: str, fresh: bool = False,
            now: Callable[[], float] = time.time) -> str:
    """The server's answer to `datapack list enabled` (ask(command) sends one command): the copy in the docker
    FOLDER when it came from container BOX under PACKS_CACHE_S ago and after the last forget(), else asked now and
    kept there (unless staff changed a pack while it was being asked). fresh=True always asks, and keeps the
    answer. Unreadable when the answer isn't the list; a copy that can't be read or written is skipped."""
    cache = Path(folder) / PACKS_CACHE
    if not fresh:
        try:
            kept = json.loads(cache.read_text(encoding="utf-8"))
            at = float(kept.get("at", -1)) if isinstance(kept, dict) else -1.0
            if (kept.get("box") == box and isinstance(kept.get("answer"), str) and 0 <= now() - at < PACKS_CACHE_S
                    and at > _forgot_at(folder)):
                return kept["answer"]
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    asked = now()
    answer = _readable(ask(LIST))
    if box and _forgot_at(folder) < asked:
        tmp = cache.with_name(f"{cache.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(json.dumps({"box": box, "at": asked, "answer": answer}), encoding="utf-8")
            tmp.replace(cache)
        except OSError:
            with contextlib.suppress(OSError):
                tmp.unlink()
    return answer


def forget(folder: Path, now: Callable[[], float] = time.time) -> None:
    """Drops the kept copy: staff turned a pack on or off, or reloaded. The time is kept too, so a timed job that
    asked the server just before can't put back a list from before the change."""
    with contextlib.suppress(OSError):
        (Path(folder) / PACKS_FORGOT).write_text(repr(now()), encoding="ascii")
    with contextlib.suppress(OSError):
        (Path(folder) / PACKS_CACHE).unlink()


def at_restart(folder: Path) -> dict[str, str]:
    """{pack name: "enable" | "disable"} staff asked for at the next restart, from FOLDER/AT_RESTART."""
    try:
        lines = (Path(folder) / AT_RESTART).read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return {}
    out = {}
    for line in lines:
        verb, _, name = line.partition(" ")
        if verb in ("enable", "disable") and pack_entry(name):
            out[name] = verb
    return out


def set_at_restart(folder: Path, name: str, verb: str | None, write: Callable[[Path, bytes], None]) -> None:
    """Queues `verb` ("enable" / "disable") for NAME at the next restart, or drops NAME's queued change (verb None).
    write(path, data) writes the file (the staff page's, which keeps its history)."""
    later = at_restart(folder)
    later.pop(name, None)
    if verb:
        later[name] = verb
    path = Path(folder) / AT_RESTART
    if later:
        write(path, ("\n".join(f"{v} {n}" for n, v in later.items()) + "\n").encode("utf-8"))
    else:
        path.unlink(missing_ok=True)
