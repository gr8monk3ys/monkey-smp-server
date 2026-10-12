"""Build the release files into dist/.

  dist/TheRealms-Server-<version>.zip     unzip anywhere; double-click Start Server.bat (Windows) or
                                          Start Server.command (macOS), or run ./start.sh (Linux)
  dist/TheRealms-Client-<version>.mrpack  import into Prism Launcher / Modrinth App to play
  dist/TheRealms-Player-<version>.zip     for the official Minecraft Launcher: unzip, double-click
                                          Install for Minecraft Launcher.bat

The player zip is everything in player/ (the installer) under TheRealms-Player-<version>/, plus the
.mrpack (the same bytes as the standalone file) and installer/fabric-profile.json (a copy of
client/fabric-profile.json, the Fabric launcher profile the installer adds to the launcher).

None of the files contains third-party jars or datapacks: the server downloads them on first start
and the launcher downloads the client mods, both from their official sources.
"""
import fnmatch
import json
import os
import zipfile
from pathlib import Path

from repo import REPO, load_json

TOP = "TheRealms-Server"
# Fixed timestamp so the same inputs give byte-identical zips.
EPOCH = (2026, 1, 1, 0, 0, 0)
# Files Linux and macOS run directly (including docker/entrypoint.sh); unzip and Archive Utility give
# them these permission bits.
EXECUTABLE = (".sh", ".command")
# What a local test install (or Docker) leaves in package/: never part of a release. Top-level folders,
# then files by their path relative to package/ (fnmatch patterns).
RUNTIME_DIRS = {"server", "java", "backups", "exports", "downloads", "pwsh"}
RUNTIME_FILES = (".realms-launch", "smoke-console.log*", "docker/.env")


def _add(z: zipfile.ZipFile, arcname: str, data: bytes) -> None:
    info = zipfile.ZipInfo(arcname, EPOCH)
    info.compress_type = zipfile.ZIP_DEFLATED
    # Made on Unix whatever builds it (zipfile picks the build machine's OS), so the permission bits
    # are honoured and a build on Windows is byte-identical to one on Linux.
    info.create_system = 3
    info.external_attr = (0o100755 if arcname.endswith(EXECUTABLE) else 0o100644) << 16
    z.writestr(info, data)


def _walk(folder: Path):
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        for f in sorted(files):
            yield Path(root) / f


def package_files(repo=REPO):
    """Every file of package/ that ships, as (path relative to package/, Path)."""
    for path in _walk(repo.package):
        rel = path.relative_to(repo.package).as_posix()
        if rel.split("/", 1)[0] in RUNTIME_DIRS and "/" in rel:
            continue
        if any(fnmatch.fnmatchcase(rel, pattern) for pattern in RUNTIME_FILES):
            continue
        yield rel, path


def build_server(version: str, repo=REPO, dist: Path | None = None) -> Path:
    out = Path(dist or repo.dist) / f"TheRealms-Server-{version}.zip"
    with zipfile.ZipFile(out, "w") as z:
        for rel, path in package_files(repo):
            _add(z, f"{TOP}/{rel}", path.read_bytes())
    return out


def build_client(version: str, repo=REPO, dist: Path | None = None) -> Path:
    index = load_json(repo.client / "modrinth.index.json")
    index["versionId"] = version
    out = Path(dist or repo.dist) / f"TheRealms-Client-{version}.mrpack"
    with zipfile.ZipFile(out, "w") as z:
        _add(z, "modrinth.index.json", json.dumps(index, indent=2, ensure_ascii=False).encode())
        for path in _walk(repo.client / "overrides"):
            _add(z, path.relative_to(repo.client).as_posix(), path.read_bytes())
    return out


def _require_player(repo) -> None:
    if not repo.player.is_dir():
        raise SystemExit(f"{repo.player} is missing: the player zip is built from the installer in player/")


def build_player(version: str, mrpack: Path, repo=REPO, dist: Path | None = None) -> Path:
    """The player zip; `mrpack` is the client pack build_client made for the same version."""
    _require_player(repo)
    if not repo.fabric_profile.is_file():
        raise SystemExit(f"{repo.fabric_profile} is missing: pin it with `python tools/snapshot.py profile`")
    top = f"TheRealms-Player-{version}"
    files = {f"{top}/{path.relative_to(repo.player).as_posix()}": path.read_bytes() for path in _walk(repo.player)}
    extra = {f"{top}/{mrpack.name}": mrpack.read_bytes(),
             f"{top}/installer/fabric-profile.json": repo.fabric_profile.read_bytes()}
    if clash := sorted(set(files) & set(extra)):
        raise SystemExit(f"player/ must not contain {', '.join(n.split('/', 1)[1] for n in clash)}: the build adds it")
    out = Path(dist or repo.dist) / f"{top}.zip"
    with zipfile.ZipFile(out, "w") as z:
        for name, data in sorted({**files, **extra}.items()):
            _add(z, name, data)
    return out


def main(repo=REPO, dist: Path | None = None):
    version = repo.load_manifest()["version"]
    tag = os.environ.get("GITHUB_REF_NAME", "")
    if tag.startswith("v") and tag[1:] != version:
        raise SystemExit(f"tag {tag} doesn't match manifest version {version}")
    _require_player(repo)
    dist = Path(dist or repo.dist)
    dist.mkdir(parents=True, exist_ok=True)
    mrpack = build_client(version, repo, dist)
    for path in (build_server(version, repo, dist), mrpack, build_player(version, mrpack, repo, dist)):
        print(f"{path}  {path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
