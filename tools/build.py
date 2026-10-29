"""Build the release files into dist/.

  dist/MonkeySMP-Server-<version>.zip     unzip anywhere; double-click Start Server.bat (Windows) or
                                          Start Server.command (macOS), or run ./start.sh (Linux)
  dist/MonkeySMP-Client-<version>.mrpack  import into Prism Launcher / Modrinth App to play
  dist/MonkeySMP-Player-<version>.zip     for the official Minecraft Launcher: unzip, double-click
                                          Install for Minecraft Launcher.bat

The player zip is everything in player/ (the installer) under MonkeySMP-Player-<version>/, plus the
.mrpack (the same bytes as the standalone file) and installer/fabric-profile.json (a copy of
client/fabric-profile.json, the Fabric launcher profile the installer adds to the launcher).

None of the files contains third-party jars or datapacks: the server downloads them on first start
and the launcher downloads the client mods, both from their official sources.

  python tools/build.py --notes notes.md  also writes the GitHub release's notes: the version's CHANGELOG.md
                                          section and what each download is for
"""
import argparse
import fnmatch
import json
import os
import sys
import zipfile
from pathlib import Path

from repo import REPO, load_json

TOP = "MonkeySMP-Server"
# Fixed timestamp so the same inputs give byte-identical zips.
EPOCH = (2026, 1, 1, 0, 0, 0)
# Files Linux and macOS run directly (including docker/entrypoint.sh); unzip and Archive Utility give
# them these permission bits.
EXECUTABLE = (".sh", ".command")
# What a local test install (or Docker) leaves in package/: never part of a release. Top-level folders,
# then files by their path relative to package/ (fnmatch patterns).
RUNTIME_DIRS = {"server", "java", "backups", "exports", "downloads", "pwsh"}
RUNTIME_FILES = (".monkey-launch", "smoke-console.log*", "docker/.env")
# The end of every GitHub release's notes, one markdown line per entry.
DOWNLOADS = "\n".join([
    "### Downloads",
    "- **MonkeySMP-Server-*.zip** - for whoever hosts. Unzip, double-click `Start Server.bat`, read "
    "`READ ME FIRST.txt`.",
    "  - Hosting on a Mac, Linux or with Docker? Same zip: double-click `Start Server.command` (Mac), run "
    "`./start.sh` (Linux), or in the `docker` folder copy `.env.example` to `.env`, set `EULA=TRUE` and run "
    "`docker compose up -d`.",
    "- **MonkeySMP-Client-*.mrpack** - for players. Import into Prism Launcher or the Modrinth App.",
    "- **MonkeySMP-Player-*.zip** - for players who use the official Minecraft Launcher. Unzip, double-click "
    "`Install for Minecraft Launcher.bat`, read `READ ME.txt`. (Using the Modrinth App or Prism Launcher "
    "instead? Import the .mrpack.)",
]) + "\n"


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
    out = Path(dist or repo.dist) / f"MonkeySMP-Server-{version}.zip"
    with zipfile.ZipFile(out, "w") as z:
        for rel, path in package_files(repo):
            _add(z, f"{TOP}/{rel}", path.read_bytes())
    return out


def build_client(version: str, repo=REPO, dist: Path | None = None) -> Path:
    index = load_json(repo.client / "modrinth.index.json")
    index["versionId"] = version
    out = Path(dist or repo.dist) / f"MonkeySMP-Client-{version}.mrpack"
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
    top = f"MonkeySMP-Player-{version}"
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


def changelog_section(changelog: str, version: str) -> str:
    """The `## [version]` section of CHANGELOG.md, up to the next `## ` heading."""
    heading = f"## [{version}]"
    lines, on = [], False
    for line in changelog.splitlines():
        if line.startswith(heading):
            on = True
        elif on and line.startswith("## "):
            break
        elif on:
            lines.append(line)
    section = "\n".join(lines).strip()
    if not section:
        raise SystemExit(f"CHANGELOG.md has no '{heading}' section")
    return section


def release_notes(version: str, repo=REPO) -> str:
    """The GitHub release's notes: the version's CHANGELOG section, then what each download is for."""
    return changelog_section((repo.root / "CHANGELOG.md").read_text(encoding="utf-8"), version) + "\n\n" + DOWNLOADS


def main(repo=REPO, dist: Path | None = None, argv=()):
    p = argparse.ArgumentParser(description="Build the release files into dist/.")
    p.add_argument("--notes", type=Path, metavar="FILE",
                   help="also write the GitHub release notes (CHANGELOG section + downloads) to FILE")
    args = p.parse_args(argv)
    version = repo.load_manifest()["version"]
    tag = os.environ.get("GITHUB_REF_NAME", "")
    if tag.startswith("v") and tag[1:] != version:
        raise SystemExit(f"tag {tag} doesn't match manifest version {version}")
    _require_player(repo)
    notes = release_notes(version, repo) if args.notes else None
    dist = Path(dist or repo.dist)
    dist.mkdir(parents=True, exist_ok=True)
    mrpack = build_client(version, repo, dist)
    for path in (build_server(version, repo, dist), mrpack, build_player(version, mrpack, repo, dist)):
        print(f"{path}  {path.stat().st_size / 1e6:.1f} MB")
    if notes:
        args.notes.write_text(notes, encoding="utf-8", newline="\n")
        print(f"{args.notes}  release notes for {version}")


if __name__ == "__main__":
    main(argv=sys.argv[1:])
