"""More of the staff page's hosting controls: the mod manager, the version switch, the world reset, the world upload and
the SFTP card. tools/staff_apex.py registers them with staff_panel (register()), so they get the same login, role and
change checks; docs/LIVE.md, "The staff page", says what each one does.

    POST /api/mod-upload?name=N&confirm=N   a jar, the raw body: checked, then into mods/      owner
    POST /api/mod-toggle {"file", "enabled", "confirm", "hold"?}  N.jar <-> N.jar.disabled     owner
    POST /api/mod-remove {"file", "confirm", "hold"?}     into mods-removed/TIME/, never deleted  owner
    POST /api/mod-hold {"file", "held", "confirm"}        keep a pinned mod off at starts, or allow it again  owner
    POST /api/mod-side {"file", "players"}    staff's answer: do players need it (required, no, unknown)  admin
    GET  /api/modrinth?q=TEXT                 Modrinth's Fabric mods for the server's game version  admin
    POST /api/modrinth-install {"project", "confirm"}     its newest file, sha512 checked          owner
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
- A pinned mod (one the release's manifest lists, with a slug) comes back at every start. Turned off or removed with
  "hold", or held with /api/mod-hold, its slug goes in server/.monkey-held.json and the start script leaves it out
  until someone allows it again, across release deploys too (a new version of the jar is still the same slug);
  turning it on or installing a jar of the release's name allows it again. Only this page writes that file, and only
  while the live release's start script reads it (Get-HeldMods): after a rollback to one that doesn't, holds are
  refused. A note that fails to save after a jar moved never undoes the move: the answer says it in note_error.
- After each install the page notes whether players need the mod too (server/.monkey-mod-sides.json): Modrinth's
  client_side, looked up by the jar's sha512 for an upload, or staff's answer. A failed lookup is "unknown" and never
  stops the install. GET /api/mods then lists the mods players need that the players' pack (client/ in the checkout)
  lacks.
- The players' pack follows the owner's mod changes through a release, never from here: after each change the page
  writes server/.monkey-pack-changes.json, the pack changes waiting (pack_waiting in GET /api/mods: a mod players
  need that the owner added, or removed or keeps off). tools/pack_sync.py, on the owner's PC, reads it over SSH and
  writes the repo change; a release publishes it. The page holds no repo or Modrinth key.
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
# A jar's file name: no folder, no "..", no leading dot or space, no control characters; spaces and ( ) are fine, as
# four of the release's own jars have them ("Simple Harvesting 26.2-3.0.1.jar"). A name only ever goes in a path in
# mods/, a JSON file or the audit log: never a shell, RCON or a URL (an upload's name is URL-encoded).
MOD_NAME = re.compile(r"(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9 ._+()-]{0,123}\.jar")
MOD_FILE = re.compile(r"(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9 ._+()-]{0,123}\.jar(?:\.disabled)?")
SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}")     # a manifest mod's slug; Monkey.psm1's $script:HeldSlug
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
HELD_FILE = ".monkey-held.json"           # server/: the pinned mods staff keep off, by slug (Monkey.psm1, Get-HeldMods)
SIDES_FILE = ".monkey-mod-sides.json"     # server/: whether players need each mod
PACK_FILE = ".monkey-pack-changes.json"   # server/: the players' pack changes waiting for a release (pack_sync.py)
PACK_ACTIONS = ("add", "remove")
PACK_HOW = ("off", "removed", "held")
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
        goes to mods-removed first. A hold on NAME's slug is cleared; `side` ({"client", "source", "project"?}) is
        noted. The jar is in and recorded before either note is written: a note that fails is said in note_error."""
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
            self.p.record(user, "mod-install", f"{name} ({source})" + (f", old one in {kept}" if kept else ""))
            done = {"file": name, "id": info["id"], "name": info["name"], "version": info["version"],
                    "replaced": [p.name for p in replaced], "kept_in": kept, "client_side": "unknown",
                    "pinned": bool({name, *(p.name.removesuffix(".disabled") for p in replaced)}
                                   & set(self.x.pinned()))}
            try:
                self._allow(user, name)
            except OSError as e:
                done["note_error"] = (f"{name} is in, but the mark that kept it off could not be cleared, so the "
                                      f"release's jar won't come back at starts: {e}")
            gone = {p.name.removesuffix(".disabled") for p in replaced} - {name}
            try:
                done["client_side"] = self._note_side(user, name, side, drop=gone)
            except OSError as e:
                done.setdefault("note_error", f"{name} is in, but whether players need it could not be saved: {e}")
            notes = self._notes_for(name, self._context())
            done["held"] = notes["held"] is not None
            done["in_players_pack"] = notes["in_players_pack"]
        return done

    def mod_upload(self, user: str, query: dict, body) -> dict:
        name = query.get("name") or ""
        if not MOD_NAME.fullmatch(name):
            raise sp.Refused(400, "A jar's name has letters, digits, spaces and . _ + - ( ) only, no folders and no "
                                  "'..', and ends in .jar.")
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
            try:
                done["client_side"] = self._note_side(
                    user, name, {"client": client, "source": "modrinth", "project": project})
            except OSError as e:
                done.setdefault("note_error", f"{name} is in, but whether players need it could not be saved: {e}")
            done["in_players_pack"] = self._notes_for(name, self._context())["in_players_pack"]
        return {**done, "side_checked": project is not None}

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
            base = target.name if enabled else name
            slug = self._slug(base)
            if hold and not enabled and slug:
                self._holds_or_refuse()
            if enabled:
                mod_id = ax.mod_info(path).get("id")
                clash = self._same_id(folder, mod_id) if mod_id else []
                if clash:
                    raise sp.Refused(409, f"{clash[0].name} has the same mod id ({mod_id}): turn it off or remove it "
                                          "first.")
            kept = self._aside([target]) if target.exists() else None
            os.replace(path, target)
            self.p.record(user, "mod-enable" if enabled else "mod-disable", name)
            done = {"file": target.name, "enabled": enabled, "kept_in": kept, "pinned": base in self.x.pinned()}
            try:
                if enabled:
                    self._allow(user, base)
                elif hold and slug:
                    self._hold(user, slug, self._held_entry(user, body, "turned off", base))
            except OSError as e:
                done["note_error"] = (f"The mod was turned {'on' if enabled else 'off'}, but 'keep it off' could not "
                                      f"be {'cleared' if enabled else 'saved'}: {e}")
            done["held"] = bool(slug) and slug in self.held()
        return done

    def mod_remove(self, user: str, body: dict) -> dict:
        name, confirm = body.get("file"), body.get("confirm")
        hold = self._hold_flag(body)
        if confirm != name:
            raise sp.Refused(400, f"Type the jar's name, {str(name)[:130]}, to confirm.")
        with self._mods:
            path = self._entry(name)
            base = name.removesuffix(".disabled")
            slug = self._slug(base)
            if hold and slug:
                self._holds_or_refuse()
            kept = self._aside([path])
            self.p.record(user, "mod-remove", f"{name}, kept in {kept}")
            done = {"file": name, "kept_in": kept, "pinned": base in self.x.pinned()}
            try:
                if hold and slug:
                    self._hold(user, slug, self._held_entry(user, body, "removed", base))
            except OSError as e:
                done["note_error"] = f"The mod was removed, but 'keep it off' could not be saved: {e}"
            done["held"] = bool(slug) and slug in self.held()
        return done

    # ------------------------------------------------ held mods, and whether players need a mod

    def _read_note(self, name: str) -> dict:
        """One of the page's JSON files in server/: {} when it is missing or not JSON (the start script does alike)."""
        try:
            data = json.loads((self.p.root / name).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_note(self, name: str, data: dict) -> None:
        """Writes one of them whole, readable by the server's user."""
        self.p._write(self.p.root / name, (json.dumps(data, indent=1, sort_keys=True) + "\n").encode("utf-8"), None)

    def _manifests(self):
        """The release's monkey/manifest.json, as JSON objects: the live package's first, then the repo checkout's."""
        for path in (self.p.live / "monkey" / "manifest.json", self.p.repo / "package" / "monkey" / "manifest.json"):
            with contextlib.suppress(OSError, ValueError):
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    yield data

    def _release_mods(self) -> dict[str, dict]:
        """{jar: its manifest entry ("file", "slug", "project_id", ...)} from the first manifest that reads; {} when its
        mods are not a list."""
        for data in self._manifests():
            mods = data.get("mods")
            if not isinstance(mods, list):
                return {}
            return {m["file"]: m for m in mods if isinstance(m, dict) and isinstance(m.get("file"), str)}
        return {}

    def _release_projects(self) -> dict[str, str]:
        """{jar: Modrinth project id} for the release's mods."""
        return {f: m["project_id"] for f, m in self._release_mods().items() if isinstance(m.get("project_id"), str)}

    @staticmethod
    def _slug_in(entry) -> str | None:
        slug = entry.get("slug") if isinstance(entry, dict) else None
        return slug if isinstance(slug, str) and SLUG.fullmatch(slug) else None

    def _slug(self, jar: str) -> str | None:
        """The release's slug for a pinned jar name; None for a jar the release doesn't pin (it can't be held)."""
        return self._slug_in(self._release_mods().get(jar))

    def holds_supported(self) -> bool:
        """True when the live package's start script reads the held file (an older release, rolled back to, doesn't:
        a hold would then be a promise nothing keeps)."""
        try:
            text = (self.p.live / "monkey" / "Monkey.psm1").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        return "Get-HeldMods" in text

    def _holds_or_refuse(self) -> None:
        if not self.holds_supported():
            raise sp.Refused(409, "The running release can't keep mods off after restarts. Turn it off without "
                                  "keeping it off, or update the release first.")

    def held(self) -> dict[str, dict]:
        """{slug: {"by", "at", "why", "file"} or {}}: the pinned mods the start script leaves out (server/
        .monkey-held.json). Any key that is a slug counts, whatever its value, as Get-HeldMods reads it. Keys that are
        the same but for case make the file unreadable for PowerShell's JSON reader, so they hold nothing here too."""
        mods = self._read_note(HELD_FILE).get("mods")
        if not isinstance(mods, dict) or len({str(n).lower() for n in mods}) != len(mods):
            return {}
        return {n: (v if isinstance(v, dict) else {}) for n, v in mods.items() if isinstance(n, str)
                and SLUG.fullmatch(n)}

    @staticmethod
    def _held_entry(user: str, body: dict, what: str, jar: str) -> dict:
        why = clean(body.get("why"), WHY_MAX) or f"{what} on the staff page"
        return {"by": user, "at": sp.stamp(), "why": why, "file": jar}

    def _set_held(self, slug: str, entry: dict | None) -> bool:
        """Holds SLUG (entry) or allows it again (None), changing only that key in the file as it is on disk. True
        when the file changed. A file that isn't {"mods": {...}} is written over when something is held."""
        with self._notes:
            raw = self._read_note(HELD_FILE)
            mods = raw.get("mods")
            if not isinstance(mods, dict):
                if entry is None:
                    return False
                raw, mods = {}, {}
            if entry is None:
                if slug not in mods:
                    return False
                del mods[slug]
            else:
                mods[slug] = entry
            raw["mods"] = mods
            self._write_note(HELD_FILE, raw)
        return True

    def _hold(self, user: str, slug: str, entry: dict) -> None:
        if self._set_held(slug, entry):
            self.p.record(user, "mod-hold", f"{slug} ({entry['file']}), kept off after restarts")

    def _allow(self, user: str, jar: str) -> bool:
        slug = self._slug(jar)
        if slug and self._set_held(slug, None):
            self.p.record(user, "mod-allow", f"{slug} ({jar}), no longer kept off")
            return True
        return False

    def _held_slug(self, name: str, now: dict) -> str | None:
        """The held slug a name from the page means: the release's slug for that jar, the slug whose stored jar it
        is, or the slug itself (a held_gone row with no stored jar)."""
        slug = self._slug(name)
        if slug in now:
            return slug
        for key, entry in now.items():
            if entry.get("file") == name:
                return key
        return name if name in now else None

    def mod_hold(self, user: str, body: dict) -> dict:
        name, held, confirm = body.get("file"), body.get("held"), body.get("confirm")
        if not isinstance(name, str) or not (MOD_NAME.fullmatch(name) or SLUG.fullmatch(name)):
            raise sp.Refused(400, "That is not a jar's name from the list.")
        if not isinstance(held, bool):
            raise sp.Refused(400, "held must be true or false.")
        if confirm != name:
            raise sp.Refused(400, f"Type the jar's name, {name}, to confirm.")
        with self._mods:
            now = self.held()
            if held:
                slug = self._slug(name) if MOD_NAME.fullmatch(name) else None
                if slug is None:
                    raise sp.Refused(409, f"{name} is not one of the release's pinned mods: no start puts it back, "
                                          "so there is nothing to keep off.")
                self._holds_or_refuse()
                if slug in now:
                    raise sp.Refused(409, f"{name} is kept off already.")
                if (self.p.root / "mods" / name).is_file():
                    raise sp.Refused(409, f"{name} is on: turn it off or remove it, and it stays off.")
                self._set_held(slug, self._held_entry(user, body, "kept off", name))
            else:
                slug = self._held_slug(name, now)
                if slug is None or not self._set_held(slug, None):
                    raise sp.Refused(409, f"{name} is not kept off.")
            self.p.record(user, "mod-hold" if held else "mod-allow", name if slug == name else f"{slug} ({name})")
        return {"file": name, "slug": slug, "held": held}

    def sides(self) -> dict[str, dict]:
        """{jar: {"client", "source", "by", "at", "project"?}} (server/.monkey-mod-sides.json)."""
        return {n: v for n, v in self._read_note(SIDES_FILE).items()
                if MOD_NAME.fullmatch(n) and isinstance(v, dict) and v.get("client") in SIDES}

    def _note_side(self, user: str, name: str, side: dict | None, drop=()) -> str:
        """Notes whether players need NAME and forgets the jars in `drop`; returns what is noted for NAME now. Staff's
        answer always replaces the note; a lookup's "unknown" (Modrinth down, a modpack without env) never replaces
        an answer that is known."""
        with self._notes:
            sides = self.sides()
            for gone in drop:
                sides.pop(gone, None)
            old = sides.get(name)
            known = bool(old) and old.get("client") != "unknown"
            if side and (side["source"] == "staff" or side["client"] != "unknown" or not known):
                row = {"client": side["client"], "source": side["source"], "by": user, "at": sp.stamp()}
                project = side.get("project") or (old or {}).get("project")    # staff's answer keeps the project
                if project:
                    row["project"] = project
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
        if not isinstance(players, str) or players not in PLAYER_ANSWERS:
            raise sp.Refused(400, "players is required, no or unknown.")
        with self._mods:
            name = self._entry(body.get("file")).name.removesuffix(".disabled")
            noted = self._note_side(user, name, {"client": PLAYER_ANSWERS[players], "source": "staff"})
            self.p.record(user, "mod-side", f"{name}: do players need it? {players}")
            in_pack = self._notes_for(name, self._context())["in_players_pack"]
        return {"file": name, "client_side": noted, "in_players_pack": in_pack}

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

    def _context(self) -> dict:
        """What _notes_for reads, read once for a whole list."""
        return {"held": self.held(), "sides": self.sides(), "pack": self._client_pack(),
                "release": self._release_mods(), "supported": self.holds_supported()}

    @staticmethod
    def _notes_for(base: str, ctx: dict, slug: str | None = None) -> dict:
        """One jar's "held" (or None), "holdable", "client_side" and "in_players_pack" (None: no pack to read)."""
        pack = ctx["pack"]
        projects = pack["projects"] if pack else {}
        entry = ctx["release"].get(base) or {}
        slug = slug or Host._slug_in(entry)
        side = ctx["sides"].get(base)
        project = (side or {}).get("project") or (entry.get("project_id") if isinstance(entry.get("project_id"), str)
                                                   else None)
        client = side["client"] if side else projects.get(project, "unknown")
        h = ctx["held"].get(slug) if slug else None
        return {"held": {"by": clean(h.get("by"), 40), "at": clean(h.get("at"), 40),
                         "why": clean(h.get("why"), WHY_MAX)} if h is not None else None,
                "holdable": bool(slug) and ctx["supported"] and bool(entry),
                "client_side": client,
                "project": project if isinstance(project, str) and PROJECT.fullmatch(project) else None,
                "in_players_pack": None if pack is None else (project in projects or base in pack["files"])}

    # ------------------------------------------------ the players' pack, following the owner's mod changes

    def pack_changes(self) -> list[dict]:
        """The lines of server/.monkey-pack-changes.json: [{"file", "action", "how"?, "project", "sha512"?, "by",
        "at"}], as the last mod change wrote them. tools/pack_sync.py reads the file over SSH."""
        rows = self._read_note(PACK_FILE).get("changes")
        return [r for r in rows if isinstance(r, dict) and isinstance(r.get("file"), str) and MOD_NAME.fullmatch(
            r["file"]) and r.get("action") in PACK_ACTIONS] if isinstance(rows, list) else []

    def _pack_waiting(self, rows: list[dict], ctx: dict) -> list[dict]:
        """The players' pack changes the mods folder calls for now, worked out afresh each time, so a line goes away
        by itself once a release has the pack match (or the owner undoes the change):
        - add: an enabled jar players need that the owner put in (not the release's: the release decides those),
          whose file the pack lacks. A new version of a mod the pack has counts: the pack must match the server.
        - remove: a mod players need in the pack that the server no longer runs: a jar the owner put in and then
          removed or turned off, or a release mod the owner keeps off (held). A release mod that is only off or
          removed comes back at the next start, so it isn't one.
        Only mods players need ("required") count. Nothing, when the pack can't be read."""
        pack = ctx["pack"]
        if pack is None:
            return []
        out, running = [], {r["project"] for r in rows if r.get("enabled") and r.get("project")}
        for r in rows:
            if r.get("enabled") and not r.get("pinned") and r.get("client_side") == "required" \
                    and r["file"] not in pack["files"]:
                out.append({"file": r["file"], "action": "add", "project": r.get("project")})
        by_project = {m["project_id"]: m for m in ctx["release"].values() if isinstance(m.get("project_id"), str)}
        noted = {v["project"]: jar for jar, v in sorted(ctx["sides"].items())
                 if v.get("client") == "required" and isinstance(v.get("project"), str)}
        off = {r["file"].removesuffix(".disabled") for r in rows if not r.get("enabled")}
        for project, client in sorted(pack["projects"].items()):
            if client != "required" or project in running:
                continue
            entry = by_project.get(project)
            if entry is not None:
                slug = self._slug_in(entry)
                if slug and slug in ctx["held"]:
                    out.append({"file": entry["file"], "action": "remove", "how": "held", "project": project})
            elif project in noted:
                jar = noted[project]
                out.append({"file": jar, "action": "remove", "how": "off" if jar in off else "removed",
                            "project": project})
        stored = {(c["file"], c["action"]): c for c in self.pack_changes()}
        for w in out:
            old = stored.get((w["file"], w["action"]), {})
            w["by"], w["at"] = clean(old.get("by"), 40) or None, clean(old.get("at"), 40) or None
        return out

    def after_mods(self, user: str, done: dict) -> dict:
        """Run after each change to the mods folder or to "do players need it?": writes server/
        .monkey-pack-changes.json from GET /api/mods's pack_waiting, with who and when for each new line and, for an
        add, the jar's sha512 (pack_sync.py finds the Modrinth version by it). The change stands whatever happens
        here: a failure is said in pack_error."""
        try:
            with self._mods:
                waiting = self.x.mods()["pack_waiting"]
                lines = []
                for w in waiting:
                    line = {**w, "by": w["by"] or user, "at": w["at"] or sp.stamp()}
                    jar = self.p.root / "mods" / w["file"]
                    if w["action"] == "add" and jar.is_file() and not jar.is_symlink():
                        sha = hashlib.sha512()
                        with open(jar, "rb") as f:
                            for chunk in iter(lambda: f.read(MB), b""):
                                sha.update(chunk)
                        line["sha512"] = sha.hexdigest()
                    lines.append(line)
                with self._notes:
                    if lines != self.pack_changes() and (lines or (self.p.root / PACK_FILE).exists()):
                        self._write_note(PACK_FILE, {"changes": lines})
            return {**done, "pack_waiting": len(lines)}
        except OSError as e:
            return {**done, "pack_error": f"The change is made, but the players' pack list could not be saved: {e}"}

    def mod_notes(self, result: dict) -> dict:
        """GET /api/mods's rows with "held", "holdable", "client_side" and "in_players_pack"; the held mods whose
        release jar is not in mods/ (held_gone); the enabled mods players need that their pack lacks
        (players_missing); and whether the live release keeps holds at all (holds_supported)."""
        ctx = self._context()
        seen, missing = set(), []
        for row in result["mods"]:
            base = row["file"].removesuffix(".disabled")
            seen.add(base)
            row.update(self._notes_for(base, ctx))
            if row.get("enabled") and row["client_side"] == "required" and not row["in_players_pack"]:
                missing.append(row["file"])
        by_slug = {self._slug_in(m): f for f, m in ctx["release"].items() if self._slug_in(m)}
        gone = []
        for slug in sorted(ctx["held"]):
            current = by_slug.get(slug)
            if current in seen:
                continue                    # its row in the list says it is held
            stored = ctx["held"][slug].get("file")
            shown = stored if isinstance(stored, str) and MOD_NAME.fullmatch(stored) else current or slug
            gone.append({"file": shown, "slug": slug, **self._notes_for(current or shown, ctx, slug)})
        return {**result, "held_gone": gone, "players_missing": missing, "players_pack": ctx["pack"] is not None,
                "holds_supported": ctx["supported"], "pack_waiting": self._pack_waiting(result["mods"], ctx)}

    # ------------------------------------------------ Modrinth

    def game_version(self) -> str:
        for data in self._manifests():
            version = data.get("minecraft")
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


# Each change to the mods folder, and each answer to "do players need it?", then rewrites the players' pack list.
ROUTES = {
    ("POST", "/api/mod-upload"): lambda p, u, q, b: host(p).after_mods(u, host(p).mod_upload(u, q, b)),
    ("POST", "/api/mod-toggle"): lambda p, u, q, b: host(p).after_mods(u, host(p).mod_toggle(u, b)),
    ("POST", "/api/mod-remove"): lambda p, u, q, b: host(p).after_mods(u, host(p).mod_remove(u, b)),
    ("POST", "/api/mod-hold"): lambda p, u, q, b: host(p).after_mods(u, host(p).mod_hold(u, b)),
    ("POST", "/api/mod-side"): lambda p, u, q, b: host(p).after_mods(u, host(p).mod_side(u, b)),
    ("GET", "/api/modrinth"): lambda p, u, q, b: host(p).modrinth_search(q),
    ("POST", "/api/modrinth-install"): lambda p, u, q, b: host(p).after_mods(u, host(p).modrinth_install(u, b)),
    ("GET", "/api/versions"): lambda p, u, q, b: host(p).versions(),
    ("POST", "/api/version-switch"): lambda p, u, q, b: host(p).version_switch(u, b),
    ("POST", "/api/world-reset"): lambda p, u, q, b: host(p).world_reset(u, b),
    ("GET", "/api/world-upload"): lambda p, u, q, b: host(p).upload_waiting(),
    ("POST", "/api/world-upload"): lambda p, u, q, b: host(p).world_upload(u, b),
    ("POST", "/api/world-upload-apply"): lambda p, u, q, b: host(p).world_upload_apply(u, b),
    ("GET", "/api/sftp"): lambda p, u, q, b: host(p).sftp(u),
}
# Every route here names who may use it (the owner made all of these admin: 2026-11-06). A jar from the visitor's
# own computer runs as the server on the next restart, so that one is the owner's (exploit audit, 2026-11-07).
# Only the owner changes which jars run (owner, 2026-11-08): installing from Modrinth, turning a jar on or off,
# removing it, and holding a pinned mod off or allowing it again. The answer to "do players need it?" stays admin:
# it is a note in .monkey-mod-sides.json, never a jar moved, and the start script doesn't read it.
OWNER_MODS = {("POST", path) for path in ("/api/mod-upload", "/api/modrinth-install", "/api/mod-toggle",
                                          "/api/mod-remove", "/api/mod-hold")}
NEEDS = {key: "owner" if key in OWNER_MODS else "admin" for key in ROUTES}
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
