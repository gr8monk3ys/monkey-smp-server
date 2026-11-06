"""The last of the staff page's hosting controls: Java and memory, data packs, the server icon and a Modrinth modpack.
tools/staff_host.py registers them with staff_panel (register()), so they get the same login, role and change checks.

    GET  /api/java                            the memory and extra Java flags the next start uses, and the Java    admin
    PUT  /api/java {"memory_gb", "flags"}     writes server/monkey-launch.json (null memory: picked as before)     admin
    GET  /api/datapacks                       the world's data packs, on or off when the server runs              admin
    POST /api/datapack-upload?name=N&confirm=N  a data pack .zip, the raw body: checked, then into the world     admin
    POST /api/datapack-toggle {"name", "enabled"}  datapack enable/disable "file/NAME" (the server must run)     admin
    POST /api/datapack-remove {"name", "confirm"}  into staff-removed/TIME/, never deleted                       admin
    POST /api/datapack-reload                 /reload: data packs (and their changes) load without a restart       admin
    GET  /api/server-icon                     the icon as a data: URL, or none                                    admin
    POST /api/server-icon                     a 64x64 PNG, the raw body: the old one goes to staff-removed/ first  admin
    POST /api/server-icon-remove              the icon into staff-removed/                                        admin
    POST /api/modpack?name=N&confirm=N        a .mrpack, the raw body: its server mods, all checked, then in      admin

The safety rules:
- What is replaced or removed is moved to server/staff-removed/TIME-XXXX/ first, never deleted (mods: mods-removed/).
- A Java flag is -XX:Name[=value] or -Dname=value with plain characters, and never one that runs a command or reads
  more flags from a file (package/monkey/Monkey.psm1, Read-LaunchSettings, checks the file again at every start).
  Memory is 1 GB up to the machine's memory less 1 GB. Either change takes effect at the next restart.
- A data pack zip has pack.mcmeta at its top, no absolute path, no `..`, no link and nothing encrypted. The release's
  own packs (monkey/datapacks/, and the manifest's) come back at every start, so they can't be removed here.
- A modpack must be for this server's game version on Fabric. Every server file comes from Modrinth's allowed hosts
  and must match its sha512, and every jar passes staff_host's mod checks, before any is put in: all or nothing.
  Its config and other files are left out: only mods.

Stdlib only, Python 3.10 or newer.
"""
import base64
import contextlib
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import struct
import tempfile
import threading
import zipfile
from pathlib import Path

sp = None   # tools/staff_panel.py (register)
ax = None   # tools/staff_apex.py
hs = None   # tools/staff_host.py

MB = 1024 * 1024
GB = 1024 * MB
LAUNCH_FILE = "monkey-launch.json"
# The same checks as Monkey.psm1's $script:LaunchFlag and $script:LaunchFlagRefused: keep the two alike.
FLAG = re.compile(r"-(XX:[+-]?[A-Za-z][A-Za-z0-9]{1,79}(=[A-Za-z0-9._:/,+-]{1,120})?"
                  r"|D[A-Za-z][A-Za-z0-9._-]{0,79}=[A-Za-z0-9._:/,+-]{0,120})")
FLAG_REFUSED = {"OnError", "OnOutOfMemoryError", "Flags", "VMOptionsFile", "ErrorFile", "HeapDumpPath"}
FLAGS_MAX = 20
MEMORY_MAX = 64
REMOVED = "staff-removed"

PACK_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,123}\.zip")
PACK_FOLDER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,123}")
PACK_MAX = 64 * MB
PACK_FILES_MAX = 20_000
PACK_TOTAL_MAX = 512 * MB      # unpacked
PACKS_SHOWN = 200
_ENABLED = re.compile(r"\[file/([^\]\s]+)")

ICON_MAX = 1 * MB
ICON_SIZE = 64
PNG = b"\x89PNG\r\n\x1a\n"

MRPACK_MAX = 64 * MB
MRPACK_FILES_MAX = 300
MRPACK_HOSTS = re.compile(r"https://(cdn\.modrinth\.com|github\.com|raw\.githubusercontent\.com|gitlab\.com)/"
                          r"[A-Za-z0-9._~%+/=-]{1,400}")
MRPACK_MOD = re.compile(r"mods/([A-Za-z0-9][A-Za-z0-9._+-]{0,123}\.jar)")


def clean(value, most: int) -> str:
    return hs.clean(value, most)


def zip_problem(z: zipfile.ZipFile, files_max: int, total_max: int) -> str | None:
    """Why a zip's entries are unsafe to read or keep, or None: the same rules as a world zip's."""
    infos = z.infolist()
    if not infos:
        return "The zip is empty."
    if len(infos) > files_max:
        return f"The zip has over {files_max} entries."
    total = 0
    for i in infos:
        name = i.filename
        if "\\" in name or "\x00" in name or name.startswith("/") or re.match(r"[A-Za-z]:", name):
            return "The zip has an entry with an absolute or Windows path."
        if any(p in ("", ".", "..") for p in name.rstrip("/").split("/")):
            return "The zip has an entry with .. or an empty folder name in its path."
        if stat.S_ISLNK(i.external_attr >> 16):
            return "The zip holds a link."
        if i.flag_bits & 0x1:
            return "The zip is encrypted."
        total += i.file_size
    if total > total_max:
        return f"The zip would be over {total_max // MB} MB unpacked."
    return None


def pack_description(raw: bytes) -> str:
    """pack.mcmeta's description, as plain text (a text component becomes its text)."""
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return ""
    desc = data.get("pack", {}).get("description") if isinstance(data, dict) and isinstance(data.get("pack"), dict) \
        else None

    def text(part) -> str:
        if isinstance(part, str):
            return part
        if isinstance(part, list):
            return "".join(text(p) for p in part)
        if isinstance(part, dict):
            return text(part.get("text", "")) + text(part.get("extra", []))
        return ""
    return clean(re.sub(r"§.", "", text(desc)), 200)


def png_size(data: bytes) -> tuple[int, int] | None:
    """(width, height) of a PNG from its IHDR, or None when it isn't one."""
    if len(data) < 24 or not data.startswith(PNG) or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def default_memory(total_gb: float) -> int:
    """What Monkey.psm1's Get-MemoryGB picks with nothing set (shown, not used: the start script decides)."""
    gb = 3 if total_gb <= 8.5 else 4 if total_gb <= 12.5 else 5 if total_gb <= 16.5 else 6
    if total_gb > 24.5:
        gb = 8
    if total_gb > 0 and gb > total_gb - 1:
        gb = max(1, int(total_gb - 1))
    return gb


def total_memory_gb() -> float:
    """The machine's memory in GB (0 when it can't be read)."""
    with contextlib.suppress(OSError, ValueError):
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024 / GB
    with contextlib.suppress(AttributeError, OSError, ValueError):
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / GB
    return 0.0


class More:
    """What these controls keep for one Panel. The tests replace memory and fetch."""

    def __init__(self, panel):
        self.p = panel
        self.x = ax.extras(panel)
        self.h = hs.host(panel)
        self.memory = total_memory_gb
        self.fetch = hs.fetch
        self._lock = threading.Lock()

    # ------------------------------------------------ shared

    def _aside(self, paths: list[Path], what: str) -> str:
        """Moves each file or folder to server/staff-removed/TIME-XXXX/WHAT/ (never deletes); returns that folder."""
        name = f"{dt.datetime.now(sp.server.UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(2)}"
        folder = self.p.root / REMOVED / name / what
        folder.mkdir(parents=True)
        for path in paths:
            os.replace(path, folder / path.name)
        return f"{REMOVED}/{name}/{what}"

    def _incoming(self) -> Path:
        """A temporary file beside the server's files (the same disk, so it moves in with a rename)."""
        folder = self.p.root / REMOVED
        folder.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".incoming-", suffix=".part", dir=folder)
        os.close(fd)
        return Path(tmp)

    @staticmethod
    def _write(path: Path, body, most: int) -> None:
        if body.length > most:
            raise sp.Refused(413, f"That is too big: at most {most // MB} MB.")
        with open(path, "wb") as f:
            for chunk in body.chunks():
                f.write(chunk)

    # ------------------------------------------------ Java and memory

    def _launch_path(self) -> Path:
        return self.p.root / LAUNCH_FILE

    def _launch(self) -> dict:
        try:
            data = json.loads(self._launch_path().read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            raise sp.Refused(500, f"server/{LAUNCH_FILE} is not JSON: fix or delete it in Files.") from None
        return data if isinstance(data, dict) else {}

    def _java_version(self) -> str | None:
        for path in (self.p.live / "monkey" / "manifest.json", self.p.repo / "package" / "monkey" / "manifest.json"):
            with contextlib.suppress(OSError, ValueError, AttributeError):
                java = json.loads(path.read_text(encoding="utf-8-sig")).get("java") or {}
                return clean(f"{java.get('vendor', 'Java')} {java.get('version', '')}", 80) or None
        return None

    def java(self) -> dict:
        data = self._launch()
        gb = data.get("memory_gb")
        flags = [f for f in data.get("flags") or [] if isinstance(f, str)]
        total = self.memory()
        return {"memory_gb": gb if isinstance(gb, int) and not isinstance(gb, bool) else None,
                "flags": flags, "total_gb": round(total, 1), "default_gb": default_memory(total),
                "most_gb": self._most(total), "java": self._java_version(), "running": self.x.running()}

    @staticmethod
    def _most(total: float) -> int:
        return max(1, min(MEMORY_MAX, int(total - 1))) if total else MEMORY_MAX

    def save_java(self, user: str, body: dict) -> dict:
        gb, flags = body.get("memory_gb"), body.get("flags")
        most = self._most(self.memory())
        if gb is not None and (not isinstance(gb, int) or isinstance(gb, bool) or not 1 <= gb <= most):
            raise sp.Refused(400, f"Memory is a whole number of GB from 1 to {most} (the machine keeps 1 GB), or empty "
                                  "to have it picked.")
        if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
            raise sp.Refused(400, "flags must be a list of Java flags.")
        flags = [f.strip() for f in flags if f.strip()]
        if len(flags) > FLAGS_MAX:
            raise sp.Refused(400, f"At most {FLAGS_MAX} extra flags.")
        for f in flags:
            if not FLAG.fullmatch(f):
                raise sp.Refused(400, f"{clean(f, 80)} is not a flag this page takes: -XX:Name, -XX:+Name, "
                                      "-XX:Name=value or -Dname=value, with letters, digits and . _ : / , + - only. "
                                      "Memory goes in its own box, not -Xmx.")
            name = re.sub(r"=.*$", "", re.sub(r"^-(XX:[+-]?|D)", "", f))
            if name in FLAG_REFUSED:
                raise sp.Refused(400, f"{name} runs a command or reads other flags from a file: not from this page.")
        path = self._launch_path()
        if not self.p.root.is_dir():
            raise sp.Refused(404, "There is no server folder yet: start the server once.")
        with self._lock:
            kept = self._aside([path], "java") if path.is_file() else None
            if gb is not None or flags:
                tmp = path.with_name(f".{LAUNCH_FILE}.{secrets.token_hex(4)}")
                tmp.write_text(json.dumps({"memory_gb": gb, "flags": flags}, indent=2) + "\n", encoding="utf-8")
                os.replace(tmp, path)
        self.p.record(user, "java-settings", f"memory {gb or 'picked'} GB, {len(flags)} extra flag(s)"
                      + (f", old file in {kept}" if kept else ""))
        return {**self.java(), "saved": True, "kept_in": kept}

    # ------------------------------------------------ data packs

    def _packs_folder(self, make: bool = False) -> Path:
        try:
            level = ax.WorldZip(self.x, "").level()
        except sp.Refused:
            raise sp.Refused(500, "The world's name (level-name in server.properties) isn't a plain folder name, "
                                  "so the data packs folder can't be found.") from None
        world = self.p.root / level
        if not world.is_dir() or world.is_symlink():
            raise sp.Refused(404, "There is no world yet: start the server once.")
        folder = world / "datapacks"
        if folder.is_symlink():
            raise sp.Refused(400, "The datapacks folder is a link: fix it on the machine.")
        if make:
            folder.mkdir(exist_ok=True)
        return folder

    def release_packs(self) -> set[str]:
        """The data packs every start puts back: the release's folders and the manifest's (install state)."""
        names = set()
        with contextlib.suppress(OSError):
            names |= {e.name for e in os.scandir(self.p.live / "monkey" / "datapacks") if e.is_dir()}
        with contextlib.suppress(OSError, ValueError, AttributeError):
            data = json.loads((self.p.root / ".monkey-state.json").read_text(encoding="utf-8-sig"))
            names |= {Path(n).name for n in data.get("datapacks") or [] if isinstance(n, str)}
        return names

    def _enabled(self) -> set[str] | None:
        if not self.x.running():
            return None
        try:
            said = self.x.rcon("datapack list enabled")
        except sp.server.RconError:
            return None
        return set(_ENABLED.findall(said))

    def datapacks(self) -> dict:
        try:
            folder = self._packs_folder()
            entries = sorted(os.scandir(folder), key=lambda e: e.name.lower())
        except FileNotFoundError:
            entries = []
        release = self.release_packs()
        enabled = self._enabled()
        rows = []
        for e in entries[:PACKS_SHOWN]:
            if e.is_symlink():
                continue
            if e.is_file(follow_symlinks=False) and PACK_NAME.fullmatch(e.name):
                kind, desc = "zip", ""
                with contextlib.suppress(OSError, zipfile.BadZipFile, KeyError, ValueError), \
                        zipfile.ZipFile(e.path) as z:
                    info = z.getinfo("pack.mcmeta")
                    if info.file_size <= 64 * 1024:
                        desc = pack_description(z.read(info))
                size = e.stat(follow_symlinks=False).st_size
            elif e.is_dir(follow_symlinks=False) and PACK_FOLDER.fullmatch(e.name):
                kind, desc, size = "folder", "", None
                with contextlib.suppress(OSError):
                    meta = Path(e.path) / "pack.mcmeta"
                    if meta.is_file() and meta.stat().st_size <= 64 * 1024:
                        desc = pack_description(meta.read_bytes())
            else:
                continue
            rows.append({"name": e.name, "kind": kind, "size": size, "description": desc,
                         "release": e.name in release, "enabled": None if enabled is None else e.name in enabled})
        return {"packs": rows, "running": enabled is not None}

    def datapack_upload(self, user: str, query: dict, body) -> dict:
        name = query.get("name") or ""
        if not PACK_NAME.fullmatch(name):
            raise sp.Refused(400, "A data pack's name has letters, digits, . _ + - only, no folders, and ends in .zip.")
        if (query.get("confirm") or "") != name:
            raise sp.Refused(400, f"Type the pack's name, {name}, to confirm.")
        folder = self._packs_folder(make=True)
        tmp = self._incoming()
        try:
            self._write(tmp, body, PACK_MAX)
            try:
                with zipfile.ZipFile(tmp) as z:
                    problem = zip_problem(z, PACK_FILES_MAX, PACK_TOTAL_MAX)
                    names = set(z.namelist())
            except (OSError, zipfile.BadZipFile, ValueError):
                problem = "That is not a zip file this page can read."
            if not problem and "pack.mcmeta" not in names:
                problem = ("pack.mcmeta is not at the top of the zip: zip what is inside the pack's folder "
                           "(pack.mcmeta and data/), not the folder itself.")
            if problem:
                raise sp.Refused(400, f"Not added: {problem}")
            with self._lock:
                target = folder / name
                kept = self._aside([target], "datapacks") if target.exists() else None
                os.chmod(tmp, 0o644)
                os.replace(tmp, target)
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink()
        self.p.record(user, "datapack-add", name + (f", old one in {kept}" if kept else ""))
        return {"name": name, "kept_in": kept, "running": self.x.running()}

    def _pack(self, name) -> Path:
        if not isinstance(name, str) or not (PACK_NAME.fullmatch(name) or PACK_FOLDER.fullmatch(name)):
            raise sp.Refused(400, "That is not a data pack's name from the list.")
        path = self._packs_folder() / name
        if not path.exists() or path.is_symlink():
            raise sp.Refused(404, f"{name} is not in the datapacks folder (any more): reload the list.")
        return path

    def datapack_toggle(self, user: str, body: dict) -> dict:
        name, enabled = body.get("name"), body.get("enabled")
        if not isinstance(enabled, bool):
            raise sp.Refused(400, "enabled must be true or false.")
        self._pack(name)
        if not self.x.running():
            raise sp.Refused(409, "The server isn't running: a data pack is turned on or off while it runs.")
        said = self.x._said(f'datapack {"enable" if enabled else "disable"} "file/{name}"')
        self.p.record(user, "datapack-enable" if enabled else "datapack-disable", name)
        return {"name": name, "enabled": enabled, "said": said}

    def datapack_remove(self, user: str, body: dict) -> dict:
        name, confirm = body.get("name"), body.get("confirm")
        if confirm != name:
            raise sp.Refused(400, f"Type the pack's name, {str(name)[:130]}, to confirm.")
        path = self._pack(name)
        if name in self.release_packs():
            raise sp.Refused(409, f"{name} is one of the release's own packs: every start puts it back. Turn it off "
                                  "instead.")
        with self._lock:
            kept = self._aside([path], "datapacks")
        self.p.record(user, "datapack-remove", f"{name}, kept in {kept}")
        return {"name": name, "kept_in": kept}

    def datapack_reload(self, user: str) -> dict:
        if not self.x.running():
            raise sp.Refused(409, "The server isn't running: the packs load when it starts.")
        said = self.x._said("reload")
        self.p.record(user, "datapack-reload")
        return {"said": said}

    # ------------------------------------------------ server icon

    def _icon(self) -> Path:
        return self.p.root / "server-icon.png"

    def server_icon(self) -> dict:
        path = self._icon()
        try:
            data = path.read_bytes() if path.is_file() and not path.is_symlink() else None
        except OSError:
            data = None
        if not data or len(data) > ICON_MAX:
            return {"icon": None}
        return {"icon": "data:image/png;base64," + base64.b64encode(data).decode("ascii"), "size": len(data),
                "dimensions": png_size(data)}

    def icon_upload(self, user: str, body) -> dict:
        if not self.p.root.is_dir():
            raise sp.Refused(404, "There is no server folder yet: start the server once.")
        tmp = self._incoming()
        try:
            self._write(tmp, body, ICON_MAX)
            got = png_size(tmp.read_bytes())
            if got is None:
                raise sp.Refused(400, "That is not a PNG image: save it as .png first.")
            if got != (ICON_SIZE, ICON_SIZE):
                raise sp.Refused(400, f"The icon must be {ICON_SIZE} by {ICON_SIZE} pixels; this one is {got[0]} by "
                                      f"{got[1]}.")
            with self._lock:
                path = self._icon()
                kept = self._aside([path], "icon") if path.exists() else None
                os.chmod(tmp, 0o644)
                os.replace(tmp, path)
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink()
        self.p.record(user, "server-icon", "new icon" + (f", old one in {kept}" if kept else ""))
        return {**self.server_icon(), "kept_in": kept}

    def icon_remove(self, user: str) -> dict:
        path = self._icon()
        if not path.is_file() or path.is_symlink():
            raise sp.Refused(404, "There is no server icon.")
        with self._lock:
            kept = self._aside([path], "icon")
        self.p.record(user, "server-icon-remove", f"kept in {kept}")
        return {"icon": None, "kept_in": kept}

    # ------------------------------------------------ a Modrinth modpack (.mrpack)

    def _mrpack(self, path: Path) -> tuple[dict, list[tuple[str, bytes | None, dict | None]]]:
        """The pack's index and its server jars: (name, the jar from overrides or None, the index's file or None)."""
        try:
            z = zipfile.ZipFile(path)
        except (OSError, zipfile.BadZipFile, ValueError):
            raise sp.Refused(400, "That is not a .mrpack (a zip) this page can read.") from None
        with z:
            problem = zip_problem(z, PACK_FILES_MAX, 4 * PACK_TOTAL_MAX)
            if problem:
                raise sp.Refused(400, f"Not installed: {problem}")
            try:
                info = z.getinfo("modrinth.index.json")
                if info.file_size > 4 * MB:
                    raise ValueError
                index = json.loads(z.read(info).decode("utf-8"))
            except (KeyError, ValueError, UnicodeDecodeError):
                raise sp.Refused(400, "Not installed: the pack has no modrinth.index.json this page can "
                                      "read.") from None
            if not isinstance(index, dict) or index.get("game") != "minecraft":
                raise sp.Refused(400, "Not installed: modrinth.index.json is not a Minecraft pack.")
            jars: list[tuple[str, bytes | None, dict | None]] = []
            for f in index.get("files") or []:
                if not isinstance(f, dict) or not isinstance(f.get("path"), str):
                    continue
                env = f.get("env") if isinstance(f.get("env"), dict) else {}
                if env.get("server") == "unsupported":
                    continue
                m = MRPACK_MOD.fullmatch(f["path"])
                if m:
                    jars.append((m.group(1), None, f))
            for i in z.infolist():
                for top in ("overrides/", "server-overrides/"):
                    m = MRPACK_MOD.fullmatch(i.filename[len(top):]) if i.filename.startswith(top) else None
                    if m and not i.is_dir():
                        if i.file_size > hs.MOD_MAX:
                            raise sp.Refused(400, f"Not installed: {m.group(1)} in the pack is over "
                                                  f"{hs.MOD_MAX // MB} MB.")
                        jars = [j for j in jars if j[0] != m.group(1)] + [(m.group(1), z.read(i), None)]
        return index, jars

    def modpack(self, user: str, query: dict, body) -> dict:
        name = query.get("name") or ""
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._+()-]{0,123}\.mrpack", name):
            raise sp.Refused(400, "A modpack is a .mrpack file with a plain name.")
        if (query.get("confirm") or "") != name:
            raise sp.Refused(400, f"Type the pack's file name, {name}, to confirm.")
        self.h._folder()
        tmp = self._incoming()
        fetched: list[Path] = []
        try:
            self._write(tmp, body, MRPACK_MAX)
            index, jars = self._mrpack(tmp)
            deps = index.get("dependencies") if isinstance(index.get("dependencies"), dict) else {}
            version = self.h.game_version()
            if deps.get("minecraft") != version:
                wants = clean(deps.get("minecraft"), 20) or "?"
                raise sp.Refused(400, f"Not installed: the pack is for Minecraft {wants}, the server runs {version}.")
            if "fabric-loader" not in deps:
                raise sp.Refused(400, "Not installed: the pack is not a Fabric pack (no fabric-loader).")
            if not jars:
                raise sp.Refused(400, "Not installed: the pack has no mods that run on a server.")
            if len(jars) > MRPACK_FILES_MAX:
                raise sp.Refused(400, f"Not installed: the pack has over {MRPACK_FILES_MAX} server mods.")
            # Everything is fetched and checked before anything goes in.
            ready: list[tuple[str, Path]] = []
            for jar, data, entry in jars:
                if data is None:
                    hashes = entry.get("hashes") if isinstance(entry.get("hashes"), dict) else {}
                    sha512 = hashes.get("sha512")
                    urls = [u for u in entry.get("downloads") or [] if isinstance(u, str) and MRPACK_HOSTS.fullmatch(u)]
                    if not isinstance(sha512, str) or not hs.SHA512.fullmatch(sha512):
                        raise sp.Refused(400, f"Not installed: the pack gives no sha512 for {jar}.")
                    if not urls:
                        raise sp.Refused(400, f"Not installed: {jar} isn't on Modrinth, GitHub or GitLab.")
                    data = self.fetch(urls[0], hs.MOD_MAX)
                    if not hmac.compare_digest(hashlib.sha512(data).hexdigest(), sha512):
                        raise sp.Refused(502, f"Not installed: {jar} doesn't match the pack's sha512.")
                part = self._incoming()
                fetched.append(part)
                part.write_bytes(data)
                info = ax.mod_info(part)
                if "error" in info or not info.get("id"):
                    why = info.get("error", "no mod id")
                    raise sp.Refused(400, f"Not installed: {jar} is not a Fabric mod ({why}).")
                if info["environment"] == "client":
                    continue                        # the pack says server, the jar says client-only: the jar wins
                ready.append((jar, part))
            done = [self.h.install(user, jar, part, f"modpack {name}") for jar, part in ready]
        finally:
            for path in [tmp, *fetched]:
                with contextlib.suppress(OSError):
                    path.unlink()
        self.p.record(user, "modpack", f"{name}: {len(done)} mod(s)")
        return {"pack": clean(index.get("name"), 80) or name, "installed": [d["file"] for d in done],
                "replaced": sorted({r for d in done for r in d["replaced"]}), "skipped": len(jars) - len(done)}


# ---------------------------------------------------------------- wiring

_more_lock = threading.Lock()


def more(panel) -> More:
    with _more_lock:
        found = getattr(panel, "_more", None)
        if found is None:
            found = panel._more = More(panel)
        return found


ROUTES = {
    ("GET", "/api/java"): lambda p, u, q, b: more(p).java(),
    ("PUT", "/api/java"): lambda p, u, q, b: more(p).save_java(u, b),
    ("GET", "/api/datapacks"): lambda p, u, q, b: more(p).datapacks(),
    ("POST", "/api/datapack-upload"): lambda p, u, q, b: more(p).datapack_upload(u, q, b),
    ("POST", "/api/datapack-toggle"): lambda p, u, q, b: more(p).datapack_toggle(u, b),
    ("POST", "/api/datapack-remove"): lambda p, u, q, b: more(p).datapack_remove(u, b),
    ("POST", "/api/datapack-reload"): lambda p, u, q, b: more(p).datapack_reload(u),
    ("GET", "/api/server-icon"): lambda p, u, q, b: more(p).server_icon(),
    ("POST", "/api/server-icon"): lambda p, u, q, b: more(p).icon_upload(u, b),
    ("POST", "/api/server-icon-remove"): lambda p, u, q, b: more(p).icon_remove(u),
    ("POST", "/api/modpack"): lambda p, u, q, b: more(p).modpack(u, q, b),
}
NEEDS = {key: "admin" for key in ROUTES}
RAW = {("POST", "/api/datapack-upload"): PACK_MAX, ("POST", "/api/server-icon"): ICON_MAX,
       ("POST", "/api/modpack"): MRPACK_MAX}


def register(module, apex, host) -> None:
    """Adds these routes to staff_panel's (`module`); tools/staff_host.py calls this."""
    global sp, ax, hs
    sp, ax, hs = module, apex, host
    module.ROUTES.update(ROUTES)
    module.NEEDS.update(NEEDS)
    module.PATHS.update(path for _, path in ROUTES)
    module.RAW.update(RAW)
