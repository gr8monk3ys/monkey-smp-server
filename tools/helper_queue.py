"""The backup helper's queue: what the staff page may ask root for, and what root runs to answer. The page
(tools/staff_apex.py and tools/staff_host.py, as monkey) writes a request file into STAFF_DIR/requests;
deploy/monkey-staff-helper.sh, as root, reads it, checks every value again itself, does the job and writes a result
into its own folder, which the page only reads. docs/LIVE.md, "The staff page", "Backups from the page".

A request is a few `key=value` lines: `action=` one of HELPER_ACTIONS, `user=` a login name, `snapshot=` 8 to 64 hex
digits and the REQUEST_FIELDS values, nothing else. Its name is a REQUEST_ID, and so is its result's (ID.json).

    python3 tools/helper_queue.py snapshots < restic.json   restic's snapshot list, cut down for the page
    python3 tools/helper_queue.py unzip-world ZIP DEST       a checked world zip, unpacked into DEST/world

Root runs this file, and only this one of tools/, from its own copy in /opt/monkey/tools (docs/LIVE.md, "Root's own
copies"): the snapshot list as root, the world zip as the server's user. So it imports nothing from tools/ and keeps
to Python 3.10 (python3 -I runs it alone).
"""
import argparse
import datetime as dt
import json
import os
import re
import secrets
import shutil
import stat
import sys
import zipfile
from pathlib import Path

HELPER_ACTIONS = ("backup-now", "list-snapshots", "restore", "deploy", "reset", "world-upload")
SNAPSHOT_ID = re.compile(r"[0-9a-f]{8,64}")
REQUEST_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{8}")
USER = re.compile(r"[A-Za-z0-9_-]{1,64}")
# The other words a request may carry (the page checks them first; the helper checks them again).
REQUEST_FIELDS = {"tag": re.compile(r"v\d{1,4}\.\d{1,4}\.\d{1,4}"), "seed": re.compile(r"-?[A-Za-z0-9_]{1,64}"),
                  "upload": REQUEST_ID}
RESULT_MAX = 2 * 1024 * 1024
REQUEST_MAX = 2048              # the most of a request the helper reads

MB = 1024 * 1024
GB = 1024 * MB
WORLD_TOTAL_MAX = 64 * GB       # unpacked
WORLD_FILES_MAX = 500_000
SPARE = 2 * GB                  # left free on the disk after an upload, and after unpacking it
UTC = dt.timezone.utc   # noqa: UP017 (datetime.UTC is 3.11+, and root's python may be 3.10)


class Problem(Exception):
    """A world zip this file won't unpack, in words for the page."""


# ---------------------------------------------------------------- requests (the page writes them)

def check_request(action: str, snapshot: str = "", **fields: str) -> None:
    """ValueError, naming it, for an action or a value outside the rules."""
    if action not in HELPER_ACTIONS:
        raise ValueError(action)
    if snapshot and not SNAPSHOT_ID.fullmatch(snapshot):
        raise ValueError("snapshot")
    for key, value in fields.items():
        if key not in REQUEST_FIELDS or not isinstance(value, str) or not REQUEST_FIELDS[key].fullmatch(value):
            raise ValueError(key)


def write_request(folder, action: str, user: str, snapshot: str = "", **fields: str) -> str:
    """Writes one request into `folder` and returns its id (check_request first). The file holds only fixed words and
    checked values, and appears whole (a temp file, then a rename)."""
    check_request(action, snapshot, **fields)
    rid = f"{dt.datetime.now(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
    lines = [f"action={action}", f"user={user if isinstance(user, str) and USER.fullmatch(user) else 'unknown'}"]
    if snapshot:
        lines.append(f"snapshot={snapshot}")
    lines += [f"{key}={fields[key]}" for key in sorted(fields)]
    folder = Path(folder)
    tmp = folder / f".tmp-{rid}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o640)
    with os.fdopen(fd, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, folder / f"{rid}.req")
    return rid


def pending(folder) -> list[str]:
    """The ids of the requests waiting in `folder`, oldest first."""
    try:
        return sorted(e.name[:-4] for e in os.scandir(folder) if e.name.endswith(".req"))
    except OSError:
        return []


def pending_actions(folder) -> list[str]:
    """The actions of the requests waiting in `folder` (one that can't be read, or names none, is left out)."""
    found = []
    for rid in pending(folder):
        try:
            text = (Path(folder) / f"{rid}.req").read_text(encoding="ascii", errors="replace")[:REQUEST_MAX]
        except OSError:
            continue
        m = re.search(r"^action=([a-z-]+)$", text, re.M)
        if m and m.group(1) in HELPER_ACTIONS:
            found.append(m.group(1))
    return found


# ---------------------------------------------------------------- results (the helper writes them)

def read_result(path) -> dict | None:
    """One result file, or None when it is a link, too big, not JSON or not about one of the helper's actions."""
    path = Path(path)
    try:
        if path.is_symlink() or path.stat().st_size > RESULT_MAX:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("action") not in (*HELPER_ACTIONS, "unknown"):
        return None
    return data


def results(folder):
    """(id, result) for each good result in `folder`, newest first."""
    try:
        names = sorted((e.name for e in os.scandir(folder)
                        if e.name.endswith(".json") and REQUEST_ID.fullmatch(e.name[:-5])), reverse=True)
    except OSError:
        return
    for name in names:
        data = read_result(Path(folder) / name)
        if data is not None:
            yield name[:-5], data


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


# ---------------------------------------------------------------- world zips (the page checks, the helper unpacks)

def check_world_zip(path) -> dict:
    """What a world zip holds, or Problem: one level.dat at the top or one folder down, nothing outside where it
    unpacks to, no links, nothing encrypted, and not too big unpacked."""
    try:
        z = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile, ValueError) as e:
        raise Problem("That is not a zip file this page can read.") from e
    with z:
        infos = z.infolist()
        if not infos:
            raise Problem("The zip is empty.")
        if len(infos) > WORLD_FILES_MAX:
            raise Problem(f"The zip has over {WORLD_FILES_MAX} entries: that is not one world.")
        levels, total = [], 0
        for i in infos:
            name = i.filename
            if "\\" in name or "\x00" in name or name.startswith("/") or re.match(r"[A-Za-z]:", name):
                raise Problem("The zip has an entry with an absolute or Windows path: nothing was changed.")
            parts = name.rstrip("/").split("/")
            if any(p in ("", ".", "..") for p in parts):
                raise Problem("The zip has an entry with .. or an empty folder name in its path: nothing was changed.")
            if stat.S_ISLNK(i.external_attr >> 16):
                raise Problem("The zip holds a link: worlds have none, so it is refused.")
            if i.flag_bits & 0x1:
                raise Problem("The zip is encrypted: zip the world folder again without a password.")
            total += i.file_size
            if not i.is_dir() and parts[-1] == "level.dat" and len(parts) <= 2:
                levels.append(parts)
        if total > WORLD_TOTAL_MAX:
            raise Problem(f"The world would be over {WORLD_TOTAL_MAX // GB} GB unpacked.")
        if len(levels) != 1:
            raise Problem("The zip needs exactly one level.dat, at the top or inside one folder (world/level.dat)."
                          if not levels else "The zip has more than one world (more than one level.dat).")
        prefix = levels[0][0] + "/" if len(levels[0]) == 2 else ""
        files = sum(1 for i in infos if not i.is_dir() and i.filename.startswith(prefix))
        return {"prefix": prefix, "files": files, "size": total}


def unzip_world(src, dest) -> Path:
    """Unpacks a world zip into DEST/world (DEST an empty folder), checking it all again first. Returns that folder."""
    dest = Path(dest)
    if not dest.is_dir() or dest.is_symlink() or any(dest.iterdir()):
        raise Problem("The folder to unpack into must be an empty folder.")
    info = check_world_zip(src)
    if shutil.disk_usage(dest).free < info["size"] + SPARE:
        raise Problem(f"Not enough disk space to unpack the world ({info['size'] // MB} MB, and "
                      f"{SPARE // GB} GB kept free).")
    world = dest / "world"
    world.mkdir()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    with zipfile.ZipFile(src) as z:
        for i in z.infolist():
            if not i.filename.startswith(info["prefix"]):
                continue                    # beside the world folder (a __MACOSX/ folder, a readme): left out
            rel = i.filename[len(info["prefix"]):].rstrip("/")
            if not rel or rel.split("/")[-1] == "session.lock":
                continue
            target = world.joinpath(*rel.split("/"))
            if i.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(target, flags, 0o644)
            with os.fdopen(fd, "wb") as out, z.open(i) as data:
                shutil.copyfileobj(data, out, 1024 * 1024)   # zipfile stops at file_size and checks the CRC
    if not (world / "level.dat").is_file():
        raise Problem("The world has no level.dat after unpacking.")
    return world


# ---------------------------------------------------------------- what the helper runs

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="the backup helper's snapshot list and world unpacking")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("snapshots", help="restic snapshots --json on stdin, the page's list on stdout")
    unzip = sub.add_parser("unzip-world", help="check a world zip and unpack it into DEST/world")
    unzip.add_argument("zip")
    unzip.add_argument("dest")
    args = ap.parse_args(argv)
    if args.command == "snapshots":
        try:
            data = json.loads(sys.stdin.read())
        except ValueError:
            print("helper_queue: restic's snapshot list is not JSON", file=sys.stderr)
            return 1
        json.dump(reduce_snapshots(data), sys.stdout)
        return 0
    try:
        unzip_world(args.zip, args.dest)
    except (Problem, OSError, zipfile.BadZipFile, ValueError) as e:
        print(f"helper_queue: {e if isinstance(e, Problem) else type(e).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
