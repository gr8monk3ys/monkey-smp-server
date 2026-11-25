"""Build the release files into dist/.

  dist/MonkeySMP-Server-<version>.zip     unzip anywhere; double-click Start Server.bat (Windows) or
                                          Start Server.command (macOS), or run ./start.sh (Linux)
  dist/SHA256SUMS.txt                     the SHA-256 of the zip, so a download can be checked
                                          (tools/checksums.py)

The zip contains no third-party jars or datapacks: the server downloads them on first start, from their
official sources. Players need nothing from a release: they join with a plain Minecraft client.

  python tools/build.py --notes notes.md  also writes the GitHub release's notes: the version's CHANGELOG.md
                                          section and what the download is for
"""
import argparse
import fnmatch
import os
import sys
import zipfile
from pathlib import Path

import checksums
from repo import REPO

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
    "- Players need nothing from here: they join with a plain Minecraft client, Java or Bedrock, and no mods.",
    "- **SHA256SUMS.txt** - the SHA-256 of the zip above. To check a download, compare the file's own with its "
    "line: `Get-FileHash <file>` in PowerShell, `shasum -a 256 <file>` on macOS, `sha256sum <file>` on Linux.",
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
    """The GitHub release's notes: the version's CHANGELOG section, then what the download is for."""
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
    notes = release_notes(version, repo) if args.notes else None
    dist = Path(dist or repo.dist)
    dist.mkdir(parents=True, exist_ok=True)
    built = (build_server(version, repo, dist),)
    for path in built:
        print(f"{path}  {path.stat().st_size / 1e6:.1f} MB")
    # Only what was just built: dist/ may still hold another version's files.
    print(f"{checksums.write(dist, built)}  the SHA-256 of each file")
    if notes:
        args.notes.write_text(notes, encoding="utf-8", newline="\n")
        print(f"{args.notes}  release notes for {version}")


if __name__ == "__main__":
    main(argv=sys.argv[1:])
