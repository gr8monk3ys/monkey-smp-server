"""More of the staff page's hosting controls: the mod manager, the version switch, the world reset, the world upload and
the SFTP card. tools/staff_apex.py registers them with staff_panel (register()), so they get the same login, role and
change checks; docs/LIVE.md, "The staff page", says what each one does.

    POST /api/mod-upload?name=N&confirm=N   a jar, the raw body: checked, then into mods/      admin
    POST /api/mod-toggle {"file", "enabled", "confirm", "hold"?}  N.jar <-> N.jar.disabled     admin
    POST /api/mod-remove {"file", "confirm", "hold"?}     into mods-removed/TIME/, never deleted  admin
    POST /api/mod-hold {"file", "held", "confirm"}        keep a pinned mod off at starts, or allow it again  admin
    POST /api/mod-side {"file", "players"}    staff's answer: do players need it (required, no, unknown)  admin
    GET  /api/modrinth?q=TEXT                 Modrinth's Fabric mods for the server's game version  admin
    POST /api/modrinth-install {"project", "confirm"}     its newest file, sha512 checked          admin
    GET  /api/versions                        the release tags in the repo checkout, and the live one  admin
    POST /api/version-switch {"tag", "confirm"}           the helper deploys that tag            admin
    POST /api/world-reset {"confirm": "RESET", "seed"?}   the helper moves the world aside       admin
    GET  /api/world-upload                    the upload waiting to be swapped in, if any          admin
    POST /api/world-upload                    a world .zip, the raw body: streamed to disk, checked  admin
    POST /api/world-upload-apply {"upload", "confirm": "REPLACE"}  the helper swaps it in         admin
    GET  /api/sftp                            host, port and user names from STAFF_DIR/sftp.json    admin

The safety rules:
- Every change is typed to confirm (the jar's name, the mod's short name, the tag, RESET or REPLACE), and what it
  replaces is kept first: a jar it replaces, disables over or removes goes to server/mods-removed/TIME/ (a move, never
  a delete); a deploy backs the world up itself; a reset or an upload moves the live world to backups/.
- A jar must be a zip with a fabric.mod.json naming an id and not marked client-only, under MOD_MAX, with a plain
  name (no folders). A Modrinth file must come from cdn.modrinth.com and match the sha512 Modrinth's API gave.
- A world zip must have one level.dat, at the top or one folder down, and no absolute path, no `..`, no link and no
  encrypted entry; its unpacked size is capped and the disk must have room. The helper unpacks it again, as the
  server's user, with unzip_world(), which checks it all again.
- A pinned mod (one the release's install put in) comes back at every start. Turned off or removed with "hold", or
  held with /api/mod-hold, its name goes in server/.monkey-held.json and the start script leaves it out until someone
  allows it again; turning it on or installing a jar of that name allows it again. Only this page writes that file.
- After each install the page notes whether players need the mod too (server/.monkey-mod-sides.json): Modrinth's
  client_side, looked up by the jar's sha512 for an upload, or staff's answer. A failed lookup is "unknown" and never
  stops the install. GET /api/mods then lists the mods players need that the players' pack (client/ in the checkout)
  lacks.
- The version, the reset and the upload run as root through deploy/monkey-staff-helper.sh, like a restore: the page
  only writes a request with checked words. A new seed goes in the request and nowhere else: never in a log.

    python3 tools/staff_host.py unzip-world ZIP DEST   unpack a checked world zip into DEST/world (the helper)

Stdlib only, Python 3.10 or newer.
"""
import argparse
import contextlib
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import stat
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import zlib
from pathlib import Path

sp = None   # tools/staff_panel.py (register)
ax = None   # tools/staff_apex.py (register)

MB = 1024 * 1024
GB = 1024 * MB
MOD_MAX = 64 * MB
MOD_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,123}\.jar")
MOD_FILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,123}\.jar(?:\.disabled)?")
REMOVED = "mods-removed"
MODRINTH = "https://api.modrinth.com/v2"
MODRINTH_CDN = re.compile(r"https://cdn\.modrinth\.com/data/[A-Za-z0-9]{8}/versions/[A-Za-z0-9]{8}/[A-Za-z0-9._+%-]{1,200}")
PROJECT = re.compile(r"[A-Za-z0-9_-]{1,64}")
SHA512 = re.compile(r"[0-9a-f]{128}")
API_MAX = 4 * MB
SEARCH_MAX = 20
USER_AGENT = "gr8monk3ys/monkey-smp-server (staff page)"
GAME_VERSION = re.compile(r"\d{1,3}(?:\.\d{1,3}){1,3}")
SIDES = ("required", "optional", "unsupported", "unknown")
HELD_FILE = ".monkey-held.json"           # server/: the pinned mods staff keep off (Monkey.psm1, Get-HeldMods)
SIDES_FILE = ".monkey-mod-sides.json"     # server/: whether players need each mod
SIDE_SOURCES = ("modrinth", "modpack", "staff")
PLAYER_ANSWERS = {"required": "required", "no": "unsupported", "unknown": "unknown"}
CDN_PROJECT = re.compile(r"https://cdn\.modrinth\.com/data/([A-Za-z0-9]{8})/")
WHY_MAX = 200

TAG = re.compile(r"v(\d{1,4})\.(\d{1,4})\.(\d{1,4})")
SHA = re.compile(r"[0-9a-f]{40}")
TAGS_SHOWN = 60
WORLD_JOBS = ("restore", "deploy", "reset", "world-upload")
# monkey-staff-helper.service has TimeoutStartSec=4h: a "running" result older than that (plus a margin) is from a
# helper that died, and must not block world jobs forever.
STALE_JOB = dt.timedelta(hours=5)

WORLD_UPLOAD_MAX = 8_000_000_000     # 8GB in deploy/Caddyfile.staff
WORLD_TOTAL_MAX = 64 * GB       # unpacked
WORLD_FILES_MAX = 500_000
SPARE = 2 * GB                  # left free on the disk after an upload, and after unpacking it
RESET_WORD = "RESET"
UPLOAD_WORD = "REPLACE"
SFTP_USER = re.compile(r"[a-z][a-z0-9_-]{0,30}")
SFTP_HOST = re.compile(r"[A-Za-z0-9.:-]{1,253}")


class Problem(Exception):
    """A world zip this file won't unpack, in words for the page."""


def clean(value, most: int) -> str:
    if not isinstance(value, str):
        return ""
    value = "".join(c if c.isprintable() else " " for c in value).strip()
    return value if len(value) <= most else value[:most - 3] + "..."


# ---------------------------------------------------------------- world zips (also run alone, by the helper)

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


# ---------------------------------------------------------------- release tags in a git checkout, read as files

def _peel(git: Path, sha: str) -> str | None:
    """The commit a tag object (or a commit) names, from a loose object; None when the object is packed."""
    path = git / "objects" / sha[:2] / sha[2:]
    try:
        raw = zlib.decompressobj().decompress(path.read_bytes(), 4096)
    except (OSError, zlib.error):
        return None
    head, _, body = raw.partition(b"\x00")
    if head.startswith(b"commit "):
        return sha
    if head.startswith(b"tag "):
        m = re.match(rb"object ([0-9a-f]{40})\n", body)
        return m.group(1).decode() if m else None
    return None


def release_tags(repo: Path) -> dict[str, str | None]:
    """{vX.Y.Z: commit or None} from REPO/.git: packed-refs, then the loose refs, which win."""
    git = Path(repo) / ".git"
    if not git.is_dir():
        raise FileNotFoundError(git)
    found: dict[str, str | None] = {}
    with contextlib.suppress(FileNotFoundError):
        lines = (git / "packed-refs").read_text(encoding="ascii", errors="replace").splitlines()
        fully = bool(lines) and lines[0].startswith("#") and "fully-peeled" in lines[0]
        last = None
        for line in lines:
            if line.startswith("^") and last and SHA.fullmatch(line[1:]):
                found[last] = line[1:]
                continue
            sha, _, ref = line.partition(" ")
            last = None
            if ref.startswith("refs/tags/") and TAG.fullmatch(ref[10:]) and SHA.fullmatch(sha):
                last = ref[10:]
                found[last] = sha if fully else _peel(git, sha)
    with contextlib.suppress(OSError):
        for e in os.scandir(git / "refs" / "tags"):
            if TAG.fullmatch(e.name) and e.is_file(follow_symlinks=False):
                sha = Path(e.path).read_text(encoding="ascii", errors="replace").strip()
                if SHA.fullmatch(sha):
                    found[e.name] = _peel(git, sha)
    return found


def tag_key(tag: str) -> tuple[int, int, int]:
    return tuple(int(n) for n in TAG.fullmatch(tag).groups())


# ---------------------------------------------------------------- one panel's state

class Host:
    """What these controls keep for one Panel. The tests replace fetch."""

    def __init__(self, panel):
        self.p = panel
        self.x = ax.extras(panel)
        self.fetch = fetch
        self._mods = threading.Lock()
        self._notes = threading.Lock()      # the held and sides files; taken inside _mods, never around it
        self._upload = threading.Lock()

    # ------------------------------------------------ mods

    def _folder(self) -> Path:
        folder = self.p.root / "mods"
        if not folder.is_dir() or folder.is_symlink():
            raise sp.Refused(404, "There is no mods folder yet: start the server once.")
        return folder

    def _entry(self, name) -> Path:
        if not isinstance(name, str) or not MOD_FILE.fullmatch(name):
            raise sp.Refused(400, "That is not a jar's name from the list.")
        path = self._folder() / name
        try:
            st = path.lstat()
        except FileNotFoundError:
            raise sp.Refused(404, f"{name} is not in the mods folder (any more): reload the list.") from None
        if not stat.S_ISREG(st.st_mode):
            raise sp.Refused(400, f"{name} is not a plain file.")
        return path

    def _aside(self, paths: list[Path]) -> str:
        """Moves each file to server/mods-removed/TIME-XXXX/ (never deletes) and returns that folder's name."""
        name = f"{dt.datetime.now(sp.server.UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(2)}"
        folder = self.p.root / REMOVED / name
        folder.mkdir(parents=True)
        for path in paths:
            os.replace(path, folder / path.name)
        return f"{REMOVED}/{name}"

    def _incoming(self) -> Path:
        """A temporary file beside mods/ (the same disk, so it moves in with a rename). Fabric loads only .jar."""
        folder = self.p.root / REMOVED
        folder.mkdir(exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".incoming-", suffix=".part", dir=folder)
        os.close(fd)
        return Path(tmp)

    def _same_id(self, folder: Path, mod_id: str, skip: tuple = ()) -> list[Path]:
        out = []
        for e in os.scandir(folder):
            if e.name in skip or not e.name.lower().endswith(".jar") or e.is_symlink():
                continue
            if e.is_file(follow_symlinks=False) and ax.mod_info(Path(e.path)).get("id") == mod_id:
                out.append(Path(e.path))
        return out

    def install(self, user: str, name: str, tmp: Path, source: str, side: dict | None = None) -> dict:
        """Puts a checked jar in as mods/NAME. A jar of that name (on or off) or an enabled one with the same mod id
        goes to mods-removed first. A hold on NAME is cleared; `side` ({"client", "source", "project"?}) is noted."""
        info = ax.mod_info(tmp)
        if "error" in info:
            raise sp.Refused(400, f"Not installed: {info['error']}.")
        if not info.get("id"):
            raise sp.Refused(400, "Not installed: its fabric.mod.json names no mod id.")
        if info["environment"] == "client":
            raise sp.Refused(400, f"Not installed: {info['name']} is a client-only mod. It belongs in the players' "
                                  "pack, not on the server.")
        with self._mods:
            folder = self._folder()
            replaced = [folder / n for n in (name, name + ".disabled") if (folder / n).is_file()]
            replaced += self._same_id(folder, info["id"], skip=(name,))
            kept = self._aside(replaced) if replaced else None
            os.chmod(tmp, 0o644)
            os.replace(tmp, folder / name)
            allowed = self._set_held(name, None)
            gone = {p.name.removesuffix(".disabled") for p in replaced} - {name}
            client = self._note_side(user, name, side, drop=gone)
        self.p.record(user, "mod-install", f"{name} ({source})" + (f", old one in {kept}" if kept else "")
                      + (", no longer kept off" if allowed else ""))
        return {"file": name, "id": info["id"], "name": info["name"], "version": info["version"],
                "replaced": [p.name for p in replaced], "kept_in": kept, "client_side": client,
                "pinned": bool({name, *(p.name.removesuffix(".disabled") for p in replaced)} & set(self.x.pinned()))}

    def mod_upload(self, user: str, query: dict, body) -> dict:
        name = query.get("name") or ""
        if not MOD_NAME.fullmatch(name):
            raise sp.Refused(400, "A jar's name has letters, digits, . _ + - only, no folders, and ends in .jar.")
        if (query.get("confirm") or "") != name:
            raise sp.Refused(400, f"Type the jar's name, {name}, to confirm.")
        if body.length > MOD_MAX:
            raise sp.Refused(413, f"A mod is at most {MOD_MAX // MB} MB.")
        self._folder()
        tmp = self._incoming()
        sha = hashlib.sha512()
        try:
            with open(tmp, "wb") as f:
                for chunk in body.chunks():
                    sha.update(chunk)
                    f.write(chunk)
            done = self.install(user, name, tmp, "uploaded")
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink()
        # The jar is in already: the lookup only adds a note, and its failure is "unknown".
        client, project = self._modrinth_side(sha.hexdigest())
        with self._mods:
            noted = self._note_side(user, name, {"client": client, "source": "modrinth", "project": project})
        return {**done, "client_side": noted, "side_checked": project is not None}

    def _hold_flag(self, body: dict) -> bool:
        hold = body.get("hold", False)
        if not isinstance(hold, bool):
            raise sp.Refused(400, "hold must be true or false.")
        return hold

    def mod_toggle(self, user: str, body: dict) -> dict:
        name, enabled, confirm = body.get("file"), body.get("enabled"), body.get("confirm")
        if not isinstance(enabled, bool):
            raise sp.Refused(400, "enabled must be true or false.")
        hold = self._hold_flag(body)
        if confirm != name:
            raise sp.Refused(400, f"Type the jar's name, {str(name)[:130]}, to confirm.")
        with self._mods:
            path = self._entry(name)
            folder = path.parent
            if enabled == name.endswith(".jar"):
                raise sp.Refused(409, f"{name} is {'on' if enabled else 'off'} already.")
            target = folder / (name[:-len(".disabled")] if enabled else name + ".disabled")
            if enabled:
                mod_id = ax.mod_info(path).get("id")
                clash = self._same_id(folder, mod_id) if mod_id else []
                if clash:
                    raise sp.Refused(409, f"{clash[0].name} has the same mod id ({mod_id}): turn it off or remove it "
                                          "first.")
            kept = self._aside([target]) if target.exists() else None
            os.replace(path, target)
            base = target.name if enabled else name
            pinned = base in self.x.pinned()
            if enabled:
                changed = self._set_held(base, None)
            else:
                changed = hold and pinned and self._set_held(base, self._held_entry(user, body, "turned off"))
        note = (", no longer kept off" if enabled else ", kept off after restarts") if changed else ""
        self.p.record(user, "mod-enable" if enabled else "mod-disable", name + note)
        return {"file": target.name, "enabled": enabled, "kept_in": kept, "pinned": pinned,
                "held": base in self.held()}

    def mod_remove(self, user: str, body: dict) -> dict:
        name, confirm = body.get("file"), body.get("confirm")
        hold = self._hold_flag(body)
        if confirm != name:
            raise sp.Refused(400, f"Type the jar's name, {str(name)[:130]}, to confirm.")
        with self._mods:
            kept = self._aside([self._entry(name)])
            base = name.removesuffix(".disabled")
            pinned = base in self.x.pinned()
            changed = hold and pinned and self._set_held(base, self._held_entry(user, body, "removed"))
        self.p.record(user, "mod-remove", f"{name}, kept in {kept}" + (", kept off after restarts" if changed else ""))
        return {"file": name, "kept_in": kept, "pinned": pinned, "held": base in self.held()}

    # ------------------------------------------------ held mods, and whether players need a mod

    def _read_note(self, name: str) -> dict:
        """One of the page's JSON files in server/: {} when it is missing or not JSON (the start script does alike)."""
        try:
            data = json.loads((self.p.root / name).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_note(self, name: str, data: dict) -> None:
        """Writes one of them whole (a temporary file, then a rename), readable by the server's user."""
        fd, tmp = tempfile.mkstemp(prefix=f"{name}.", suffix=".tmp", dir=self.p.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1, sort_keys=True)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, 0o644)
            os.replace(tmp, self.p.root / name)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    def held(self) -> dict[str, dict]:
        """{jar: {"by", "at", "why"}}: the pinned mods the start script leaves out (server/.monkey-held.json)."""
        mods = self._read_note(HELD_FILE).get("mods")
        if not isinstance(mods, dict):
            return {}
        return {n: v for n, v in mods.items() if isinstance(n, str) and MOD_NAME.fullmatch(n) and isinstance(v, dict)}

    @staticmethod
    def _held_entry(user: str, body: dict, what: str) -> dict:
        why = clean(body.get("why"), WHY_MAX) or f"{what} on the staff page"
        return {"by": user, "at": sp.stamp(), "why": why}

    def _set_held(self, name: str, entry: dict | None) -> bool:
        """Holds NAME (entry) or allows it again (None). True when the file changed."""
        with self._notes:
            held = self.held()
            if entry is None and name not in held:
                return False
            if entry is None:
                del held[name]
            else:
                held[name] = entry
            self._write_note(HELD_FILE, {"mods": held})
        return True

    def mod_hold(self, user: str, body: dict) -> dict:
        name, held, confirm = body.get("file"), body.get("held"), body.get("confirm")
        if not isinstance(name, str) or not MOD_NAME.fullmatch(name):
            raise sp.Refused(400, "That is not a jar's name from the list.")
        if not isinstance(held, bool):
            raise sp.Refused(400, "held must be true or false.")
        if confirm != name:
            raise sp.Refused(400, f"Type the jar's name, {name}, to confirm.")
        with self._mods:
            now = self.held()
            if held:
                if name in now:
                    raise sp.Refused(409, f"{name} is kept off already.")
                if name not in self.x.pinned():
                    raise sp.Refused(409, f"{name} is not one of the release's pinned mods: no start puts it back, "
                                          "so there is nothing to keep off.")
                if (self.p.root / "mods" / name).is_file():
                    raise sp.Refused(409, f"{name} is on: turn it off or remove it, and it stays off.")
                self._set_held(name, self._held_entry(user, body, "kept off"))
            elif not self._set_held(name, None):
                raise sp.Refused(409, f"{name} is not kept off.")
        self.p.record(user, "mod-hold" if held else "mod-allow", name)
        return {"file": name, "held": held}

    def sides(self) -> dict[str, dict]:
        """{jar: {"client", "source", "by", "at", "project"?}} (server/.monkey-mod-sides.json)."""
        return {n: v for n, v in self._read_note(SIDES_FILE).items()
                if MOD_NAME.fullmatch(n) and isinstance(v, dict) and v.get("client") in SIDES}

    def _note_side(self, user: str, name: str, side: dict | None, drop=()) -> str:
        """Notes whether players need NAME and forgets the jars in `drop`; returns what is noted for NAME now. Modrinth
        not knowing a mod never overwrites staff's answer for it."""
        with self._notes:
            sides = self.sides()
            for gone in drop:
                sides.pop(gone, None)
            old = sides.get(name)
            if side and not (side["client"] == "unknown" and old and old.get("source") == "staff"):
                row = {"client": side["client"], "source": side["source"], "by": user, "at": sp.stamp()}
                if side.get("project"):
                    row["project"] = side["project"]
                sides[name] = row
            if drop or side:
                self._write_note(SIDES_FILE, sides)
            return sides[name]["client"] if name in sides else "unknown"

    def _modrinth_side(self, sha512: str) -> tuple[str, str | None]:
        """Modrinth's client_side for a jar, found by its sha512, and its project id; ("unknown", None) when Modrinth
        doesn't know the file or can't be asked."""
        try:
            version = self._json(f"{MODRINTH}/version_file/{sha512}?algorithm=sha512")
            project = version.get("project_id") if isinstance(version, dict) else None
            if not isinstance(project, str) or not PROJECT.fullmatch(project):
                return "unknown", None
            meta = self._json(f"{MODRINTH}/project/{project}")
        except Exception:  # noqa: BLE001 (a failed lookup must never fail the install)
            return "unknown", None
        side = meta.get("client_side") if isinstance(meta, dict) else None
        return (side if side in SIDES else "unknown"), project

    def mod_side(self, user: str, body: dict) -> dict:
        players = body.get("players")
        if players not in PLAYER_ANSWERS:
            raise sp.Refused(400, "players is required, no or unknown.")
        with self._mods:
            name = self._entry(body.get("file")).name.removesuffix(".disabled")
            noted = self._note_side(user, name, {"client": PLAYER_ANSWERS[players], "source": "staff"})
        self.p.record(user, "mod-side", f"{name}: do players need it? {players}")
        return {"file": name, "client_side": noted}

    def _client_pack(self) -> dict | None:
        """The players' pack, client/modrinth.index.json in the repo checkout: its jar names and {Modrinth project:
        client env}, or None when it can't be read."""
        try:
            data = json.loads((self.p.repo / "client" / "modrinth.index.json").read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or not isinstance(data.get("files"), list):
            return None
        files, projects = set(), {}
        for f in data["files"]:
            if not isinstance(f, dict) or not isinstance(f.get("path"), str):
                continue
            files.add(f["path"].rsplit("/", 1)[-1])
            env = f.get("env") if isinstance(f.get("env"), dict) else {}
            client = env.get("client") if env.get("client") in SIDES else "required"   # no env: every client has it
            for url in f.get("downloads") or []:
                m = CDN_PROJECT.match(url) if isinstance(url, str) else None
                if m:
                    projects[m.group(1)] = client
        return {"files": files, "projects": projects}

    def _release_projects(self) -> dict[str, str]:
        """{jar: Modrinth project id} for the release's mods (monkey/manifest.json)."""
        for path in (self.p.live / "monkey" / "manifest.json", self.p.repo / "package" / "monkey" / "manifest.json"):
            with contextlib.suppress(OSError, ValueError, AttributeError):
                mods = json.loads(path.read_text(encoding="utf-8-sig")).get("mods")
                return {m["file"]: m["project_id"] for m in mods if isinstance(m, dict)
                        and isinstance(m.get("file"), str) and isinstance(m.get("project_id"), str)}
        return {}

    def mod_notes(self, result: dict) -> dict:
        """GET /api/mods's rows with "held", "client_side" and "in_players_pack"; and the held jars no longer in mods/
        (held_gone), and the enabled mods players need that their pack lacks (players_missing)."""
        held, sides, pack, release = self.held(), self.sides(), self._client_pack(), self._release_projects()
        projects = pack["projects"] if pack else {}

        def notes(base: str) -> dict:
            side = sides.get(base)
            project = (side or {}).get("project") or release.get(base)
            client = side["client"] if side else projects.get(project, "unknown")
            in_pack = None if pack is None else (project in projects or base in pack["files"])
            h = held.get(base)
            return {"held": {"by": clean(h.get("by"), 40), "at": clean(h.get("at"), 40),
                             "why": clean(h.get("why"), WHY_MAX)} if h else None,
                    "client_side": client, "in_players_pack": in_pack}

        seen, missing = set(), []
        for row in result["mods"]:
            base = row["file"].removesuffix(".disabled")
            seen.add(base)
            row.update(notes(base))
            if row.get("enabled") and row["client_side"] == "required" and not row["in_players_pack"]:
                missing.append(row["file"])
        gone = [{"file": n, **notes(n)} for n in sorted(set(held) - seen)]
        return {**result, "held_gone": gone, "players_missing": missing, "players_pack": pack is not None}

    # ------------------------------------------------ Modrinth

    def game_version(self) -> str:
        for path in (self.p.live / "monkey" / "manifest.json", self.p.repo / "package" / "monkey" / "manifest.json"):
            with contextlib.suppress(OSError, ValueError, AttributeError):
                version = json.loads(path.read_text(encoding="utf-8-sig")).get("minecraft")
                if isinstance(version, str) and GAME_VERSION.fullmatch(version):
                    return version
        raise sp.Refused(503, "This page can't tell the server's game version (monkey/manifest.json): upload the jar "
                              "instead.")

    def _json(self, url: str):
        try:
            return json.loads(self.fetch(url, API_MAX).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise sp.Refused(502, "Modrinth's answer was not JSON: try again in a minute.") from None

    def modrinth_search(self, query: dict) -> dict:
        text = (query.get("q") or "").strip()
        if not 1 <= len(text) <= 80 or not text.isprintable():
            raise sp.Refused(400, "Search for one to 80 characters.")
        version = self.game_version()
        facets = [["project_type:mod"], ["categories:fabric"], [f"versions:{version}"],
                  ["server_side:required", "server_side:optional"]]
        data = self._json(f"{MODRINTH}/search?" + urllib.parse.urlencode(
            {"query": text, "facets": json.dumps(facets), "limit": SEARCH_MAX}))
        rows = []
        for h in (data.get("hits") if isinstance(data, dict) else None) or []:
            if not isinstance(h, dict) or not isinstance(h.get("slug"), str) or not PROJECT.fullmatch(h["slug"]):
                continue
            downloads = h.get("downloads")
            rows.append({"slug": h["slug"], "title": clean(h.get("title"), 80) or h["slug"],
                         "description": clean(h.get("description"), 240),
                         "downloads": downloads if isinstance(downloads, int) and not isinstance(downloads, bool)
                         else None,
                         "server_side": h.get("server_side") if h.get("server_side") in SIDES else "unknown",
                         "client_side": h.get("client_side") if h.get("client_side") in SIDES else "unknown"})
        return {"game_version": version, "hits": rows[:SEARCH_MAX]}

    def modrinth_install(self, user: str, body: dict) -> dict:
        project, confirm = body.get("project"), body.get("confirm")
        if not isinstance(project, str) or not PROJECT.fullmatch(project):
            raise sp.Refused(400, "Pick a mod from the search.")
        if confirm != project:
            raise sp.Refused(400, f"Type the mod's short name, {project}, to confirm.")
        version = self.game_version()
        meta = self._json(f"{MODRINTH}/project/{project}")
        if not isinstance(meta, dict) or meta.get("slug") != project or not isinstance(meta.get("id"), str) \
                or not PROJECT.fullmatch(meta["id"]):
            raise sp.Refused(502, "Modrinth doesn't know that mod by that name.")
        versions = self._json(f"{MODRINTH}/project/{meta['id']}/version?" + urllib.parse.urlencode(
            {"loaders": '["fabric"]', "game_versions": json.dumps([version])}))
        versions = [v for v in versions if isinstance(v, dict)] if isinstance(versions, list) else []
        pick = next((v for v in versions if v.get("version_type") == "release"), versions[0] if versions else None)
        if pick is None:
            raise sp.Refused(404, f"{project} has no Fabric file for {version}.")
        files = [f for f in pick.get("files") or [] if isinstance(f, dict)]
        file = next((f for f in files if f.get("primary")), files[0] if files else None)
        if file is None:
            raise sp.Refused(502, "Modrinth listed that version with no file.")
        name, url = file.get("filename"), file.get("url")
        sha512 = (file.get("hashes") or {}).get("sha512") if isinstance(file.get("hashes"), dict) else None
        if not isinstance(name, str) or not MOD_NAME.fullmatch(name):
            raise sp.Refused(502, "Modrinth's file for it doesn't have a plain .jar name: nothing was installed.")
        if not isinstance(url, str) or not MODRINTH_CDN.fullmatch(url):
            raise sp.Refused(502, "Modrinth's file for it is not on cdn.modrinth.com: nothing was installed.")
        if not isinstance(sha512, str) or not SHA512.fullmatch(sha512):
            raise sp.Refused(502, "Modrinth gave no sha512 for the file: nothing was installed.")
        self._folder()
        data = self.fetch(url, MOD_MAX)
        if not hmac.compare_digest(hashlib.sha512(data).hexdigest(), sha512):
            raise sp.Refused(502, "The download doesn't match Modrinth's sha512: nothing was installed.")
        tmp = self._incoming()
        try:
            tmp.write_bytes(data)
            client = meta.get("client_side") if meta.get("client_side") in SIDES else "unknown"
            done = self.install(user, name, tmp, f"Modrinth {project} {clean(pick.get('version_number'), 40)}",
                                side={"client": client, "source": "modrinth", "project": meta["id"]})
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink()
        needs = [d.get("project_id") for d in pick.get("dependencies") or []
                 if isinstance(d, dict) and d.get("dependency_type") == "required"]
        return {**done, "requires": [n for n in needs if isinstance(n, str) and PROJECT.fullmatch(n)]}

    # ------------------------------------------------ the root helper's world and version jobs

    @staticmethod
    def _stale(stamp: str) -> bool:
        """True when a result's time (UTC, 2026-11-06T12:00:00Z) is older than the helper's longest run."""
        try:
            when = dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
        except ValueError:
            return False
        return dt.datetime.now(dt.UTC) - when > STALE_JOB

    def _busy(self) -> None:
        for job in self.x.jobs():
            if job["action"] in WORLD_JOBS and job["state"] == "running" and not self._stale(job.get("time", "")):
                raise sp.Refused(409, f"The helper is busy with a {job['action']} already: wait for it to finish.")
        for rid in self.x._pending():
            with contextlib.suppress(OSError):
                text = (self.x.requests / f"{rid}.req").read_text(encoding="ascii", errors="replace")
                if any(f"action={a}\n" in text for a in WORLD_JOBS):
                    raise sp.Refused(409, "A restore, version switch, reset or upload is waiting to start already.")

    # ------------------------------------------------ versions

    def _tags(self) -> dict[str, str | None]:
        try:
            return release_tags(self.p.repo)
        except FileNotFoundError:
            raise sp.Refused(503, "The repo checkout isn't here, so the release tags can't be read.") from None

    def versions(self) -> dict:
        tags = self._tags()
        deployed = ""
        with contextlib.suppress(OSError):
            deployed = (self.p.live / ".deployed").read_text(encoding="ascii", errors="replace").strip()
        pin = ""
        with contextlib.suppress(OSError):
            pin = (self.p.live / ".deploy-pin").read_text(encoding="ascii", errors="replace").strip()
        names = sorted(tags, key=tag_key, reverse=True)
        rows = [{"tag": t, "live": bool(deployed) and tags[t] == deployed} for t in names[:TAGS_SHOWN]]
        return {"tags": rows, "newest": names[0] if names else None,
                "deployed": deployed[:12] if SHA.fullmatch(deployed) else None,
                "pinned": pin if TAG.fullmatch(pin) else None, "installed": self.x.installed()}

    def version_switch(self, user: str, body: dict) -> dict:
        tag, confirm = body.get("tag"), body.get("confirm")
        if not isinstance(tag, str) or not TAG.fullmatch(tag) or tag not in self._tags():
            raise sp.Refused(400, "Pick a release tag from the list.")
        if confirm != tag:
            raise sp.Refused(400, f"Type the tag, {tag}, to confirm.")
        self._busy()
        rid = self.x.request(user, "deploy", tag=tag)
        self.p.record(user, "version-switch", tag)
        return {"request": rid}

    # ------------------------------------------------ world reset

    def world_reset(self, user: str, body: dict) -> dict:
        if body.get("confirm") != RESET_WORD:
            raise sp.Refused(400, f"Type {RESET_WORD} to confirm.")
        seed = body.get("seed")
        seed = seed.strip() if isinstance(seed, str) else seed
        if seed in (None, ""):
            fields = {}
        elif isinstance(seed, str) and ax.REQUEST_FIELDS["seed"].fullmatch(seed):
            fields = {"seed": seed}
        else:
            raise sp.Refused(400, "A seed here is a number or a word: up to 64 letters, digits or _, and a - in "
                                  "front if you like. Leave it empty to keep the seed.")
        self._busy()
        rid = self.x.request(user, "reset", **fields)
        self.p.record(user, "world-reset", "seed changed" if fields else "same seed")
        return {"request": rid}

    # ------------------------------------------------ world upload

    @property
    def uploads(self) -> Path:
        return self.p.staff / "uploads"

    def _waiting(self) -> list[Path]:
        try:
            return sorted(Path(e.path) for e in os.scandir(self.uploads)
                          if e.name.endswith(".zip") and ax.REQUEST_ID.fullmatch(e.name[:-4])
                          and e.is_file(follow_symlinks=False))
        except OSError:
            return []

    def upload_waiting(self) -> dict:
        found = self._waiting()
        if not found:
            return {"upload": None}
        path = found[-1]
        st = path.stat()
        info = {}
        with contextlib.suppress(Problem):
            info = check_world_zip(path)
        return {"upload": path.stem, "size": st.st_size, "time": st.st_mtime, "files": info.get("files"),
                "unpacked": info.get("size"), "installed": self.x.installed()}

    def world_upload(self, user: str, body) -> dict:
        if not self.x.installed():
            raise sp.Refused(503, "The root helper isn't installed, so an uploaded world can't be swapped in. The "
                                  "owner installs it: sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --install-helper")
        if body.length > WORLD_UPLOAD_MAX:
            raise sp.Refused(413, "A world upload is at most 8 GB.")
        self.uploads.mkdir(parents=True, exist_ok=True)
        need = 2 * body.length + SPARE
        if shutil.disk_usage(self.uploads).free < need:
            raise sp.Refused(507, f"Not enough disk space: the zip and the world unpacked need about {need // GB + 1} "
                                  "GB free.")
        if not self._upload.acquire(blocking=False):
            raise sp.Refused(409, "Someone is uploading a world already: one at a time.")
        try:
            uid = f"{dt.datetime.now(sp.server.UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
            part = self.uploads / f".part-{uid}"
            try:
                with open(part, "xb") as f:
                    for chunk in body.chunks(1024 * 1024):
                        f.write(chunk)
                    f.flush()
                    os.fsync(f.fileno())
                info = check_world_zip(part)
            except Problem as e:
                part.unlink(missing_ok=True)
                raise sp.Refused(400, str(e)) from None
            except BaseException:
                part.unlink(missing_ok=True)
                raise
            for old in self._waiting():          # one upload waits at a time; an upload is not a world yet
                old.unlink(missing_ok=True)
            os.replace(part, self.uploads / f"{uid}.zip")
        finally:
            self._upload.release()
        self.p.record(user, "world-upload", f"{body.length // MB} MB, {info['files']} files")
        return {"upload": uid, "files": info["files"], "unpacked": info["size"],
                "folder": info["prefix"].rstrip("/") or None}

    def world_upload_apply(self, user: str, body: dict) -> dict:
        uid = body.get("upload")
        if not isinstance(uid, str) or not ax.REQUEST_ID.fullmatch(uid) or \
                uid not in [p.stem for p in self._waiting()]:
            raise sp.Refused(400, "That upload isn't here (any more): upload the world again.")
        if body.get("confirm") != UPLOAD_WORD:
            raise sp.Refused(400, f"Type {UPLOAD_WORD} to confirm.")
        self._busy()
        rid = self.x.request(user, "world-upload", upload=uid)
        self.p.record(user, "world-replace", uid)
        return {"request": rid}

    # ------------------------------------------------ SFTP (the owner sets it up: monkey-staff.sh --add-sftp-user)

    def sftp(self, user: str) -> dict:
        try:
            data = json.loads((self.p.staff / "sftp.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict):
            return {"set_up": False}
        users = [u for u in data.get("users") or [] if isinstance(u, str) and SFTP_USER.fullmatch(u)]
        host, port = data.get("host"), data.get("port")
        if not users or not isinstance(host, str) or not SFTP_HOST.fullmatch(host) or not isinstance(port, int) \
                or isinstance(port, bool) or not 0 < port < 65536:
            return {"set_up": False}
        return {"set_up": True, "host": host, "port": port, "users": sorted(users),
                "you": user if user in users else None}


def fetch(url: str, most: int) -> bytes:
    """GET url (https only), at most `most` bytes, or Refused(502)."""
    if not url.startswith("https://"):
        raise sp.Refused(502, "Only https is fetched.")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as answer:   # noqa: S310 (https, checked above)
            data = answer.read(most + 1)
    except (urllib.error.URLError, OSError, ValueError):
        raise sp.Refused(502, "Modrinth didn't answer: try again in a minute.") from None
    if len(data) > most:
        raise sp.Refused(502, f"Modrinth's answer was over {most // MB} MB.")
    return data


# ---------------------------------------------------------------- wiring

_host_lock = threading.Lock()


def host(panel) -> Host:
    with _host_lock:
        found = getattr(panel, "_host", None)
        if found is None:
            found = panel._host = Host(panel)
        return found


ROUTES = {
    ("POST", "/api/mod-upload"): lambda p, u, q, b: host(p).mod_upload(u, q, b),
    ("POST", "/api/mod-toggle"): lambda p, u, q, b: host(p).mod_toggle(u, b),
    ("POST", "/api/mod-remove"): lambda p, u, q, b: host(p).mod_remove(u, b),
    ("POST", "/api/mod-hold"): lambda p, u, q, b: host(p).mod_hold(u, b),
    ("POST", "/api/mod-side"): lambda p, u, q, b: host(p).mod_side(u, b),
    ("GET", "/api/modrinth"): lambda p, u, q, b: host(p).modrinth_search(q),
    ("POST", "/api/modrinth-install"): lambda p, u, q, b: host(p).modrinth_install(u, b),
    ("GET", "/api/versions"): lambda p, u, q, b: host(p).versions(),
    ("POST", "/api/version-switch"): lambda p, u, q, b: host(p).version_switch(u, b),
    ("POST", "/api/world-reset"): lambda p, u, q, b: host(p).world_reset(u, b),
    ("GET", "/api/world-upload"): lambda p, u, q, b: host(p).upload_waiting(),
    ("POST", "/api/world-upload"): lambda p, u, q, b: host(p).world_upload(u, b),
    ("POST", "/api/world-upload-apply"): lambda p, u, q, b: host(p).world_upload_apply(u, b),
    ("GET", "/api/sftp"): lambda p, u, q, b: host(p).sftp(u),
}
# Every route here names who may use it (the owner made all of these admin: 2026-11-06).
NEEDS = {key: "admin" for key in ROUTES}
# The routes whose body is a file, and the most bytes each takes (staff_panel.RAW).
RAW = {("POST", "/api/mod-upload"): MOD_MAX, ("POST", "/api/world-upload"): WORLD_UPLOAD_MAX}


def register(module, apex) -> None:
    """Adds these routes to staff_panel's (`module`); `apex` is tools/staff_apex.py, which calls this."""
    global sp, ax
    sp, ax = module, apex
    module.ROUTES.update(ROUTES)
    module.NEEDS.update(NEEDS)
    module.PATHS.update(path for _, path in ROUTES)
    module.RAW.update(RAW)
    import staff_more
    staff_more.register(module, apex, sys.modules[__name__])   # Java, data packs, the icon and modpacks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="the staff page's world upload, unpacked for the root helper")
    sub = ap.add_subparsers(dest="command", required=True)
    unzip = sub.add_parser("unzip-world", help="check a world zip and unpack it into DEST/world")
    unzip.add_argument("zip")
    unzip.add_argument("dest")
    args = ap.parse_args(argv)
    try:
        unzip_world(args.zip, args.dest)
    except (Problem, OSError, zipfile.BadZipFile, ValueError) as e:
        print(f"staff_host: {e if isinstance(e, Problem) else type(e).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
