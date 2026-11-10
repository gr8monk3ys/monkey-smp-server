"""Prove the players' two ways in from clean: nothing installed, an empty folder, the real downloads.

    python tools/clean_install.py pack PACK            is the built .mrpack a valid Modrinth pack? (offline)
    python tools/clean_install.py launcher PACK DIR    what the Modrinth App or Prism Launcher does with it: every
                                                       file downloaded into the empty folder DIR and checked (size,
                                                       SHA-1, SHA-512), then the overrides unpacked over them
    python tools/clean_install.py installer ZIP DIR    Windows only: the player zip unzipped into the empty folder
                                                       DIR and "Install for Minecraft Launcher.bat" run as a
                                                       double-click runs it, against a launcher folder that holds
                                                       nothing but a launcher_profiles.json; then what it left is
                                                       checked file by file

PACK is dist/MonkeySMP-Client-X.Y.Z.mrpack and ZIP dist/MonkeySMP-Player-X.Y.Z.zip (python tools/build.py).
`launcher` and `installer` each download the whole pack (about 380 MB), so they run in the Clean install workflow
(.github/workflows/install.yml: before every release, and on a pull request that touches the pack, the installer,
the build or this file), not in tools/checks.py. `pack` is offline and runs with the unit tests on the pack the
build makes.

`installer` never touches the real launcher: the .bat runs with APPDATA pointed into DIR, which is where it looks
for %APPDATA%\\.minecraft and where it makes %APPDATA%\\.monkey-smp. It answers the installer's one question (is
the launcher still open?) with SKIP, so a launcher open on this computer doesn't stall it.

None of this starts the game. That a pack loads and plays is docs/QA.md's job.

What a valid pack is: the format's own page (support.modrinth.com, "Modrinth Modpack Format (.mrpack)") and what
the Modrinth App reads (PackFormat and PackFile in packages/app-lib/src/api/pack/install_from.rs, app 0.23.1).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

from upstream import LiveHttp

INDEX = "modrinth.index.json"
# Where a launcher looks in a pack: the index, and files it copies into the instance as they are.
OVERRIDES = ("overrides/", "client-overrides/", "server-overrides/")
# The folders a player's game gets, later ones over earlier ones (the format's order).
CLIENT_OVERRIDES = ("overrides/", "client-overrides/")
LOADERS = ("minecraft", "forge", "neoforge", "fabric-loader", "quilt-loader")
SIDES = ("required", "optional", "unsupported")
# The only hosts a pack on Modrinth may download from.
HOSTS = ("cdn.modrinth.com", "github.com", "raw.githubusercontent.com", "gitlab.com")
HASHES = {"sha1": 40, "sha512": 128}

BAT = "Install for Minecraft Launcher.bat"
PROFILE_KEY = "monkey-smp"
STATE_FILE = ".monkey-client-state.json"
BACKUP_SUFFIX = ".monkey-smp-backup"
PROFILES = "launcher_profiles.json"
# The memory the installer may pick from the computer's RAM (Get-ClientMemoryGB in PlayerInstall.psm1).
MEMORY_GB = (3, 4, 6, 8)
# A launcher_profiles.json as the Minecraft Launcher leaves it before anyone adds a profile (fake values): its two
# own profiles, its settings, a name that isn't ASCII. The installer must leave all of it exactly as it was.
SEED_PROFILES = json.dumps({
    "profiles": {
        "0000000000000000000000000000aaaa": {
            "created": "1970-01-02T00:00:00.000Z", "icon": "Grass", "lastUsed": "2026-10-05T07:20:50.000Z",
            "lastVersionId": "latest-release", "name": "", "type": "latest-release"},
        "0000000000000000000000000000bbbb": {
            "created": "1970-01-01T00:00:00.000Z", "icon": "Crafting_Table", "lastUsed": "1970-01-01T00:00:00.000Z",
            "lastVersionId": "latest-snapshot", "name": "Café world", "type": "latest-snapshot",
            "resolution": {"height": 480, "width": 854}},
    },
    "settings": {"crashAssistance": True, "enableAdvanced": False, "enableAnalytics": True, "enableHistorical": False,
                 "enableReleases": True, "enableSnapshots": False, "keepLauncherOpen": False,
                 "profileSorting": "ByLastPlayed", "showGameLog": False, "showMenu": False, "soundOn": False},
    "version": 3,
}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
INSTALLER_TIMEOUT = 45 * 60


# ---------------------------------------------------------------------------------------------- the pack

def unsafe_path(path) -> bool:
    """True for a pack path that could land outside the game folder, or that Windows would store under another
    name: absolute, a drive letter, a backslash, '.' or '..', an empty part, a part ending in a dot or a space."""
    if not isinstance(path, str) or not path or path.startswith("/") or ":" in path or "\\" in path:
        return True
    return any(not part or set(part) == {"."} or part[-1] in ". " for part in path.split("/"))


def _file_problems(f, n: int) -> list[str]:
    if not isinstance(f, dict):
        return [f"files[{n}] is not an object"]
    path = f.get("path")
    if unsafe_path(path):
        return [f"files[{n}]: {path!r} is not a safe path inside the game folder"]
    errors = []
    hashes = f.get("hashes")
    for name, length in HASHES.items():
        value = hashes.get(name) if isinstance(hashes, dict) else None
        if not isinstance(value, str) or not re.fullmatch(f"[0-9a-f]{{{length}}}", value):
            errors.append(f"{path}: hashes.{name} must be {length} small hex digits")
    downloads = f.get("downloads")
    if not isinstance(downloads, list) or not downloads:
        errors.append(f"{path}: no download")
    else:
        for url in downloads:
            parts = urllib.parse.urlsplit(url) if isinstance(url, str) else None
            if not parts or parts.scheme != "https" or parts.hostname not in HOSTS:
                errors.append(f"{path}: {url!r} is not an https download from {', '.join(HOSTS)}")
    size = f.get("fileSize")
    if isinstance(size, bool) or not isinstance(size, int) or not 0 < size < 2 ** 32:
        errors.append(f"{path}: fileSize must be the file's size in bytes")
    env = f.get("env")
    if env is not None and (not isinstance(env, dict) or not env or set(env) - {"client", "server"}
                            or any(side not in SIDES for side in env.values())):
        errors.append(f"{path}: env must say {', '.join(SIDES[:-1])} or {SIDES[-1]} for client and server")
    return errors


def index_problems(index) -> list[str]:
    """What stops a launcher from reading a modrinth.index.json."""
    if not isinstance(index, dict):
        return [f"{INDEX} is not an object"]
    errors = []
    if type(index.get("formatVersion")) is not int or index["formatVersion"] != 1:
        errors.append("formatVersion must be 1")
    if index.get("game") != "minecraft":
        errors.append('game must be "minecraft"')
    errors += [f"{key} must be text" for key in ("versionId", "name")
               if not isinstance(index.get(key), str) or not index[key]]
    if not isinstance(index.get("summary", ""), str):
        errors.append("summary must be text")
    deps = index.get("dependencies")
    if not isinstance(deps, dict):
        errors.append("dependencies must be an object")
    else:
        errors += [f"dependencies: {key!r} is not one of {', '.join(LOADERS)}" for key in deps if key not in LOADERS]
        errors += [f"dependencies.{key} must be a version" for key, value in deps.items()
                   if key in LOADERS and (not isinstance(value, str) or not value)]
        if "minecraft" not in deps:
            errors.append("dependencies has no minecraft version")
    files = index.get("files")
    if not isinstance(files, list):
        return errors + ["files must be a list"]
    for n, f in enumerate(files):
        errors += _file_problems(f, n)
    paths = [path.lower() for path in _listed_paths(index)]
    return errors + [f"{path} is listed twice" for path in sorted({p for p in paths if paths.count(p) > 1})]


def _listed_paths(index) -> list[str]:
    """The path of every file an index lists, whatever else is wrong with it."""
    files = index.get("files") if isinstance(index, dict) else None
    return [f["path"] for f in files if isinstance(f, dict) and isinstance(f.get("path"), str)
            ] if isinstance(files, list) else []


def read_pack(path: Path) -> tuple[dict, dict[str, bytes]]:
    """(the index, {path in the game folder: bytes} of the overrides a player's game gets) of a valid pack."""
    with zipfile.ZipFile(path) as z:
        index = json.loads(z.read(INDEX).decode("utf-8"))
        overrides = {}
        for prefix in CLIENT_OVERRIDES:
            for name in z.namelist():
                if name.startswith(prefix) and not name.endswith("/"):
                    overrides[name[len(prefix):]] = z.read(name)
    return index, overrides


def pack_problems(path: Path) -> list[str]:
    """What is wrong with a .mrpack as a Modrinth pack; [] for one a launcher can install."""
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if damaged := z.testzip():
                return [f"{damaged} is damaged (the zip's checksum doesn't match)"]
            if INDEX not in names:
                return [f"no {INDEX} at the top of the zip"]
            try:
                index = json.loads(z.read(INDEX).decode("utf-8"))
            except ValueError as e:
                return [f"{INDEX} is not valid JSON: {e}"]
    except (OSError, zipfile.BadZipFile) as e:
        return [f"not a zip file: {e}"]
    errors = index_problems(index)
    errors += [f"{name} is in the zip twice" for name in sorted({n for n in names if names.count(n) > 1})]
    listed = {path.lower() for path in _listed_paths(index)}
    for name in sorted(set(names)):
        if name == INDEX:
            continue
        prefix = next((p for p in OVERRIDES if name.startswith(p)), None)
        if prefix is None:
            errors.append(f"{name}: a launcher only reads {INDEX} and {', '.join(OVERRIDES)}")
        elif name.endswith("/"):
            continue    # a folder entry
        elif unsafe_path(name[len(prefix):]):
            errors.append(f"{name} is not a safe path inside the game folder")
        elif name[len(prefix):].lower() in listed:
            errors.append(f"{name} would replace the download {name[len(prefix):]}")
    return errors


def client_files(index: dict) -> list[dict]:
    """The files a player's game gets: all but the ones the pack marks as not for the client."""
    return [f for f in index["files"] if (f.get("env") or {}).get("client") != "unsupported"]


def content_problem(f: dict, data: bytes) -> str:
    """Why `data` is not the file the pack pins ('' when it is): the size, then each hash."""
    if len(data) != f["fileSize"]:
        return f"is {len(data)} bytes, the pack says {f['fileSize']}"
    for name in HASHES:
        if hashlib.new(name, data).hexdigest() != f["hashes"][name]:
            return f"has another {name} than the pack says"
    return ""


# ---------------------------------------------------------------------------------------------- the launcher's way

def _empty_folder(folder: Path) -> str:
    """Make `folder` (an error text when it holds anything: a clean install starts from nothing)."""
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        return f"{folder} is not an empty folder: a clean install starts from nothing"
    folder.mkdir(parents=True, exist_ok=True)
    return ""


def fetch(f: dict, http, tries: int = 3, pause=time.sleep) -> tuple[bytes | None, str]:
    """(the file's bytes, '') from the first of its downloads that gives the pinned file, or (None, why not)."""
    why = ""
    for attempt in range(tries):
        if attempt:
            pause(5 * attempt)
        for url in f["downloads"]:
            try:
                data = http.get_bytes(url)
            except Exception as e:  # noqa: BLE001  whatever the network raises is the reason
                why = f"{url}: {type(e).__name__}: {e}"
                continue
            why = content_problem(f, data)
            if not why:
                return data, ""
            why = f"{url} {why}"
    return None, why


def launcher_install(pack: Path, folder: Path, http, workers: int = 8, pause=time.sleep, log=print) -> list[str]:
    """Install `pack` into the empty `folder` as a launcher does. Returns what went wrong."""
    if errors := pack_problems(pack):
        return [f"{pack.name}: {e}" for e in errors]
    if error := _empty_folder(folder):
        return [error]
    index, overrides = read_pack(pack)
    files = client_files(index)

    def place(f):
        data, why = fetch(f, http, pause=pause)
        if data is None:
            return f"{f['path']}: {why}"
        dest = folder / PurePosixPath(f["path"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return ""

    errors = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for f, error in zip(files, pool.map(place, files), strict=True):
            if error:
                errors.append(error)
            else:
                log(f"ok  {f['fileSize']:>10}  {f['path']}")
    for rel, data in overrides.items():
        dest = folder / PurePosixPath(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    if not errors:
        total = sum(f["fileSize"] for f in files)
        log(f"{len(files)} files ({total / 1e6:.0f} MB) downloaded and checked, {len(overrides)} override files "
            f"unpacked: {index['name']} {index['versionId']}, Minecraft {index['dependencies']['minecraft']}")
    return errors


# ---------------------------------------------------------------------------------------------- the installer's way

def _files_in(folder: Path) -> dict[str, Path]:
    return {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()} if folder.is_dir() else {}


def _set_problems(label: str, found: set, expected: set) -> list[str]:
    errors = [f"{label}: {name} is missing" for name in sorted(expected - found)]
    return errors + [f"{label}: {name} was left behind (not a file of the pack)" for name in sorted(found - expected)]


def game_folder_problems(game: Path, index: dict, overrides: dict[str, bytes]) -> list[str]:
    """The game folder must hold exactly the pack's files, its overrides and the installer's own list of them."""
    files = {f["path"]: f for f in client_files(index)}
    found = _files_in(game)
    errors = _set_problems("game folder", set(found), set(files) | set(overrides) | {STATE_FILE})
    for rel, f in sorted(files.items()):
        if rel in found and (why := content_problem(f, found[rel].read_bytes())):
            errors.append(f"game folder: {rel} {why}")
    errors += [f"game folder: {rel} is not the pack's copy" for rel, data in sorted(overrides.items())
               if rel in found and rel not in files and found[rel].read_bytes() != data]
    if STATE_FILE in found:
        try:
            state = json.loads(found[STATE_FILE].read_bytes().decode("utf-8"))
        except ValueError as e:
            return errors + [f"game folder: {STATE_FILE} is not valid JSON: {e}"]
        want = {"pack": index["name"], "version": index["versionId"], "files": sorted(files)}
        if not isinstance(state, dict) or {**state, "files": sorted(state.get("files") or [])} != want:
            errors.append(f"game folder: {STATE_FILE} doesn't list this pack's files (name, version, every path)")
    return errors


def launcher_folder_problems(minecraft: Path, game: Path, index: dict, fabric_profile: bytes, seed: bytes) -> list[str]:
    """The launcher's folder must hold the Fabric version, our profile and a backup, and nothing else changed."""
    deps = index["dependencies"]
    version = f"fabric-loader-{deps.get('fabric-loader')}-{deps['minecraft']}"
    version_file = f"versions/{version}/{version}.json"
    found = _files_in(minecraft)
    errors = _set_problems("launcher folder", set(found), {PROFILES, PROFILES + BACKUP_SUFFIX, version_file})
    if version_file in found and found[version_file].read_bytes() != fabric_profile:
        errors.append(f"launcher folder: {version_file} is not the zip's installer/fabric-profile.json")
    if PROFILES + BACKUP_SUFFIX in found and found[PROFILES + BACKUP_SUFFIX].read_bytes() != seed:
        errors.append(f"launcher folder: {PROFILES}{BACKUP_SUFFIX} is not the file as it was before the install")
    if PROFILES not in found:
        return errors
    try:
        after = json.loads(found[PROFILES].read_bytes().decode("utf-8"))
        ours = after["profiles"].pop(PROFILE_KEY)
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        return errors + [f"launcher folder: {PROFILES} has no readable '{PROFILE_KEY}' profile "
                         f"({type(e).__name__}: {e})"]
    if after != json.loads(seed.decode("utf-8")):
        errors.append(f"launcher folder: {PROFILES} changed outside the '{PROFILE_KEY}' profile")
    if not isinstance(ours, dict):
        return errors + [f"launcher folder: the '{PROFILE_KEY}' profile is not an object"]
    want = {"name": f"Monkey SMP {index['versionId']}", "type": "custom", "lastVersionId": version}
    errors += [f"launcher folder: the profile's {key} is {ours.get(key)!r}, not {value!r}"
               for key, value in want.items() if ours.get(key) != value]
    game_dir = ours.get("gameDir")
    if not isinstance(game_dir, str) or os.path.normcase(os.path.normpath(game_dir)) != os.path.normcase(
            os.path.normpath(str(game))):
        errors.append(f"launcher folder: the profile plays from {game_dir!r}, not {str(game)!r}")
    memory = re.match(r"-Xmx(\d+)G -Xms(\d+)G ", str(ours.get("javaArgs")))
    if not memory or memory.group(1) != memory.group(2) or int(memory.group(1)) not in MEMORY_GB:
        errors.append(f"launcher folder: the profile's javaArgs don't start with one of the installer's memory "
                      f"sizes ({', '.join(f'{n} GB' for n in MEMORY_GB)}): {ours.get('javaArgs')!r}")
    errors += [f"launcher folder: the profile has no {key}" for key in ("created", "lastUsed") if not ours.get(key)]
    return errors


def run_bat(bat: Path, appdata: Path, timeout: float = INSTALLER_TIMEOUT) -> str:
    """Run the .bat as a double-click does (cmd, in its own folder), with APPDATA in the scratch folder. Its
    output goes to ours. Returns '' or why it didn't finish; the .bat's own exit code says nothing (it ends on
    `pause`), so what it left is the test."""
    env = {**os.environ, "APPDATA": str(appdata)}
    try:
        proc = subprocess.Popen(["cmd.exe", "/d", "/c", str(bat)], cwd=bat.parent, env=env, stdin=subprocess.PIPE)
    except OSError as e:
        return f"{bat.name} didn't start: {e}"
    try:
        # SKIP answers "is the launcher still open?"; the end of input answers `pause`.
        proc.communicate(b"SKIP\r\nSKIP\r\n", timeout=timeout)
    except subprocess.TimeoutExpired:
        # Ending cmd.exe alone would leave the installer's PowerShell downloading: end its whole tree (by PID,
        # so only the processes this run started).
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, check=False)
        proc.wait()
        return f"{bat.name} didn't finish in {timeout / 60:.0f} minutes"
    return ""


def installer_install(player_zip: Path, folder: Path, run=run_bat, log=print) -> list[str]:
    """Unzip the player zip into the empty `folder`, run its installer against an empty launcher folder there,
    and check what it left. Returns what went wrong."""
    if error := _empty_folder(folder):
        return [error]
    unzipped, appdata = folder / "unzipped", folder / "appdata"
    try:
        with zipfile.ZipFile(player_zip) as z:
            z.extractall(unzipped)
    except (OSError, zipfile.BadZipFile) as e:
        return [f"{player_zip.name} is not a zip file: {e}"]
    bats = sorted(unzipped.glob(f"*/{BAT}"))
    if len(bats) != 1:
        return [f"{player_zip.name} must hold one folder with {BAT} in it (found {len(bats)})"]
    top = bats[0].parent
    packs = sorted(top.glob("*.mrpack"))
    fabric_profile = top / "installer" / "fabric-profile.json"
    if len(packs) != 1 or not fabric_profile.is_file():
        return [f"{player_zip.name} must hold one .mrpack beside {BAT}, and installer/fabric-profile.json"]
    if errors := pack_problems(packs[0]):
        return [f"{packs[0].name}: {e}" for e in errors]
    index, overrides = read_pack(packs[0])

    minecraft, game = appdata / ".minecraft", appdata / ".monkey-smp"
    minecraft.mkdir(parents=True)
    (minecraft / PROFILES).write_bytes(SEED_PROFILES)
    log(f"Running {bats[0]} with APPDATA={appdata}")
    if error := run(bats[0], appdata):
        return [error]
    errors = (game_folder_problems(game, index, overrides)
              + launcher_folder_problems(minecraft, game, index, fabric_profile.read_bytes(), SEED_PROFILES))
    errors += [f"appdata: {p.name} was made beside the launcher's and the game's folders"
               for p in sorted(appdata.iterdir()) if p not in (minecraft, game)]
    if not errors:
        log(f"{len(client_files(index))} pack files and {len(overrides)} override files in {game}, the Fabric "
            f"version and the '{PROFILE_KEY}' profile in {minecraft}, everything else there as it was")
    return errors


def main(argv=None, http=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("pack", help="check a built .mrpack is a valid pack (offline)").add_argument("pack", type=Path)
    p = sub.add_parser("launcher", help="install a .mrpack into an empty folder as a launcher does")
    p.add_argument("pack", type=Path)
    p.add_argument("folder", type=Path)
    p = sub.add_parser("installer", help="Windows: run the player zip's installer against an empty launcher folder")
    p.add_argument("zip", type=Path)
    p.add_argument("folder", type=Path)
    a = ap.parse_args(argv)
    # Line by line, so our lines and the installer's own stay in order in a log; a file name the console's
    # encoding lacks is escaped instead of stopping the run.
    sys.stdout.reconfigure(line_buffering=True, errors="backslashreplace")
    if a.command == "pack":
        errors = pack_problems(a.pack)
        if not errors:
            index, overrides = read_pack(a.pack)
            print(f"{a.pack.name}: a valid pack, {len(index['files'])} files to download, {len(overrides)} overrides")
    elif a.command == "launcher":
        errors = launcher_install(a.pack, a.folder, http or LiveHttp())
    elif os.name != "nt":
        errors = ["the installer is for Windows: run this there (the Clean install workflow does)"]
    else:
        errors = installer_install(a.zip, a.folder)
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
