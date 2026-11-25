"""Check the manifest and package for mistakes that would break an install.

  python tools/validate.py              offline checks (structure, entries, patches, defaults, the site's links,
                                        the generated data packs)
  python tools/validate.py --online     also download every file (Java for every platform, the Paper jar
                                        or Fabric launcher, plugins, mods, datapacks, and the PowerShell
                                        builds in pwsh.lock), verify its size and hash, and apply each
                                        mod/datapack patch to its download to prove it still fits
"""
import argparse
import hashlib
import re
import sys

import build
import datapacks
import defaults
import entries
import patches
import pwsh_lock
import season_ics
import site_links
from repo import REPO
from upstream import LiveHttp, Upstream

PACKAGE_FILES = ("Start Server.bat", "Stop Server.bat", "Backup World.bat", "Schedule Backups.bat", "Add Player.bat",
                 "Prepare for Hosting.bat", "READ ME FIRST.txt",
                 # Linux and macOS: the same launchers as sh scripts, and the PowerShell bootstrap they share.
                 "start.sh", "stop.sh", "backup.sh", "add-player.sh", "prepare-for-hosting.sh", "Start Server.command",
                 "monkey/monkey.sh", "monkey/pwsh.lock")
# The Docker image files (package/docker/), checked once that folder exists.
DOCKER_FILES = ("docker/Dockerfile", "docker/compose.yaml", "docker/entrypoint.sh", "docker/.env.example")
# Read by sh (or Docker) on Linux and macOS: a CR at the end of a line breaks them.
UNIX_FILES = ("*.sh", "*.command", "pwsh.lock", "docker/*")
ASCII_NOTE = "must be plain ASCII (Windows PowerShell 5.1 reads BOM-less files as ANSI; see ADR-0003)"
# Tab, LF, CR. Anything else below 32 in a READ ME, script or doc is a backslash path eaten by an escape
# (\v in "config\voicechat").
CONTROL_OK = (9, 10, 13)
CONTROL_NOTE = "has a control character (a backslash in a path read as an escape, like \\v or \\b?)"
# "mods" is not required: 1.x (Paper-only) manifests predate it, and a missing group reads as [].
MANIFEST_KEYS = ("name", "version", "minecraft", "java", "server", "world", "plugins", "datapacks")


def validate(manifest: dict, repo=REPO) -> list[str]:
    errors = [f"manifest: missing '{key}'" for key in MANIFEST_KEYS if key not in manifest]
    errors += [f"manifest: '{group}' must be a list" for group in entries.GROUPS.values()
               if not isinstance(manifest.get(group, []), list)]
    if errors:
        return errors
    if not re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]):
        errors.append("manifest: version must look like 1.2.3")
    if not re.fullmatch(r"-?\d*", str(manifest["world"].get("seed", ""))):
        errors.append("manifest: world.seed must be a number (or empty for random)")
    for kind, e in entries.artifacts(manifest):
        errors += entries.check(kind, e)
    errors += entries.check_java(manifest)
    errors += entries.check_types(manifest)
    for kind, group in entries.GROUPS.items():
        files = [e.get("file", "").lower() for e in entries.group(manifest, kind)]
        slugs = [e.get("slug") for e in entries.group(manifest, kind)]
        for dup in sorted({f for f in files if files.count(f) > 1}):
            errors.append(f"{group}: duplicate file {dup}")
        for dup in sorted({s for s in slugs if slugs.count(s) > 1}):
            errors.append(f"{group}: duplicate project {dup}")
    return errors + patches.check(manifest, repo)


def validate_package(repo=REPO) -> list[str]:
    props = (repo.defaults / "server.properties").read_text(encoding="utf-8")
    errors = defaults.check_server_properties(props)
    errors += [f"package/{name} is missing" for name in PACKAGE_FILES if not (repo.package / name).is_file()]
    if (repo.package / "docker").is_dir():
        errors += [f"package/{name} is missing" for name in DOCKER_FILES if not (repo.package / name).is_file()]
    unix = sorted({f for _, f in build.package_files(repo)
                   if any(f.match(pattern) or f.relative_to(repo.package).match(pattern) for pattern in UNIX_FILES)})
    for script in sorted(repo.package.rglob("*.ps*1")) + sorted(repo.package.glob("*.bat")) + unix:
        if any(b > 127 for b in script.read_bytes()):
            errors.append(f"{script.relative_to(repo.package).as_posix()} {ASCII_NOTE}")
    for script in unix:
        if b"\r" in script.read_bytes():
            errors.append(f"{script.relative_to(repo.package).as_posix()} must have LF line endings (it is run by sh)")
    if repo.pwsh_lock.is_file():
        errors += pwsh_lock.check(repo.pwsh_lock.read_text(encoding="ascii", errors="replace"))
    # The READ MEs, the scripts (they write HOSTING.txt and every message) and the docs.
    texts = [path for pattern in ("*.txt", "*.bat", "*.command", "**/*.sh", "**/*.ps*1")
             for path in sorted(repo.package.glob(pattern))]
    texts += sorted(repo.root.glob("*.md")) + sorted((repo.root / "docs").rglob("*.md"))
    for text in texts:
        if any(b < 32 and b not in CONTROL_OK for b in text.read_bytes()):
            errors.append(f"{text.relative_to(repo.root).as_posix()} {CONTROL_NOTE}")
    return errors


def verify_online(manifest: dict, upstream: Upstream, repo=REPO) -> list[str]:
    errors = []
    for kind, e in entries.artifacts(manifest):
        data = upstream.download(e["url"])
        if not entries.matches(e, data):
            errors.append(f"{kind} {e['file']}: download doesn't match the pinned size/hash")
            continue
        if "patch" in e:
            try:
                patches.apply(data, patches.read(patches.folder(repo, e)))
            except patches.PatchError as err:
                errors.append(f"{kind} {e['file']}: patch {e['patch']['path']} doesn't fit the download: {err}")
                continue
        print(f"ok  {kind:8} {e['file']}{'  (patch fits)' if 'patch' in e else ''}")
    return errors


def verify_pwsh_online(upstream: Upstream, repo=REPO) -> list[str]:
    """Every PowerShell build in pwsh.lock must still download with its pinned sha256."""
    errors = []
    for pin in pwsh_lock.parse(repo.pwsh_lock.read_text(encoding="ascii")):
        if hashlib.sha256(upstream.download(pin.url)).hexdigest() != pin.sha256:
            errors.append(f"pwsh.lock {pin.platform} {pin.file}: download doesn't match the pinned sha256")
            continue
        print(f"ok  pwsh     {pin.file}")
    return errors


def main(argv=None, repo=REPO, upstream=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--online", action="store_true")
    a = ap.parse_args(argv)
    manifest = repo.load_manifest()
    errors = validate(manifest, repo) + validate_package(repo) + site_links.problems(repo)
    if repo.root == REPO.root:  # the generators are this checkout's; an older release's packs came from older ones
        errors += [f"{p} is out of date (run python tools/datapacks.py)" for p in datapacks.differences(repo)]
        errors += datapacks.problems(datapacks.all_files(repo))
        errors += season_ics.problems(repo)
    if a.online and not errors:
        upstream = upstream or Upstream(LiveHttp())
        errors += verify_online(manifest, upstream, repo) + verify_pwsh_online(upstream, repo)
    for e in errors:
        print("ERROR", e)
    counts = ", ".join(f"{len(entries.group(manifest, kind))} {group}" for kind, group in entries.GROUPS.items())
    print(f"{len(errors)} problem(s); {manifest['server'].get('type', '?')} server, {counts}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
