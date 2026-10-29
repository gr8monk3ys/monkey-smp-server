"""Check the manifest and package for mistakes that would break an install.

  python tools/validate.py              offline checks (structure, entries, patches, defaults, client pack,
                                        Fabric launcher profile, player installer files, the site's links and modpack,
                                        the generated data packs)
  python tools/validate.py --online     also download every file (Java for every platform, the Paper jar
                                        or Fabric launcher, plugins, mods, datapacks, and the PowerShell
                                        builds in pwsh.lock), verify its size and hash, apply each
                                        mod/datapack patch to its download to prove it still fits, and
                                        check Fabric meta still serves the pinned launcher profile
"""
import argparse
import hashlib
import re
import sys

import build
import client_env
import datapacks
import defaults
import entries
import launcher_profile
import patches
import pwsh_lock
import site_links
from repo import REPO, load_json
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
# Checked only once player/ exists (the player zip can't be built without it).
PLAYER_FILES = ("Install for Minecraft Launcher.bat", "READ ME.txt", "installer/install-client.ps1",
                "installer/PlayerInstall.psm1")
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
    if repo.player.is_dir():
        errors += [f"player/{name} is missing" for name in PLAYER_FILES if not (repo.player / name).is_file()]
        for script in sorted(repo.player.rglob("*.ps*1")) + sorted(repo.player.rglob("*.bat")):
            if any(b > 127 for b in script.read_bytes()):
                errors.append(f"{script.relative_to(repo.root).as_posix()} {ASCII_NOTE}")
    # The READ MEs, the scripts (they write HOSTING.txt and every message) and the docs.
    texts = [path for folder in (repo.package, repo.player) if folder.is_dir()
             for pattern in ("*.txt", "*.bat", "*.command", "**/*.sh", "**/*.ps*1")
             for path in sorted(folder.glob(pattern))]
    texts += sorted(repo.root.glob("*.md")) + sorted((repo.root / "docs").rglob("*.md"))
    for text in texts:
        if any(b < 32 and b not in CONTROL_OK for b in text.read_bytes()):
            errors.append(f"{text.relative_to(repo.root).as_posix()} {CONTROL_NOTE}")
    return errors


def validate_client(manifest: dict, repo=REPO) -> list[str]:
    index = load_json(repo.client / "modrinth.index.json")
    errors = []
    if index["dependencies"].get("minecraft") != manifest["minecraft"]:
        errors.append("client: minecraft version differs from the server manifest")
    for f in index["files"]:
        if not f["downloads"] or not all(u.startswith("https://cdn.modrinth.com/") for u in f["downloads"]):
            errors.append(f"client {f['path']}: downloads must be Modrinth CDN URLs")
        if f["path"].startswith(("/", "..")) or ".." in f["path"].split("/"):
            errors.append(f"client {f['path']}: unsafe path")
    # Two versions of one mod: Fabric refuses to start (or picks one) when two jars have the same mod id.
    by_project = {}
    for f in index["files"]:
        m = re.match(r"https://cdn\.modrinth\.com/data/([^/]+)/", f["downloads"][0]) if f["downloads"] else None
        if m and f["path"].startswith("mods/"):
            by_project.setdefault(m.group(1), []).append(f["path"])
    errors += [f"client: {' and '.join(sorted(paths))} are the same Modrinth project (keep one version)"
               for paths in by_project.values() if len(paths) > 1]
    errors += client_env.check(index)  # which files a player may untick (optional) and which they need
    return errors + validate_profile(index, repo)


def validate_profile(index: dict, repo=REPO) -> list[str]:
    """client/fabric-profile.json must be the launcher profile for the client index's Minecraft + loader."""
    mc, loader = index["dependencies"].get("minecraft"), index["dependencies"].get("fabric-loader")
    if not loader:
        return ["client: modrinth.index.json has no fabric-loader dependency"]
    if not repo.fabric_profile.is_file():
        return ["client/fabric-profile.json is missing (pin it with `python tools/snapshot.py profile`)"]
    try:
        profile = load_json(repo.fabric_profile)
    except ValueError as err:
        return [f"client/fabric-profile.json is not valid JSON: {err}"]
    return launcher_profile.check(profile, mc, loader)


def verify_profile_online(upstream: Upstream, repo=REPO) -> list[str]:
    """Fabric meta must still serve the pinned profile (ignoring its generation time)."""
    deps = load_json(repo.client / "modrinth.index.json")["dependencies"]
    served = upstream.fabric_profile(deps["minecraft"], deps["fabric-loader"])
    if not launcher_profile.same(load_json(repo.fabric_profile), served):
        return ["client/fabric-profile.json differs from what Fabric meta serves now "
                "(re-pin it with `python tools/snapshot.py profile`)"]
    print(f"ok  profile  {served['id']}")
    return []


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
    errors = (validate(manifest, repo) + validate_package(repo) + validate_client(manifest, repo)
              + site_links.problems(repo))
    if repo.root == REPO.root:  # the generators are this checkout's; an older release's packs came from older ones
        errors += [f"{p} is out of date (run python tools/datapacks.py)" for p in datapacks.differences(repo)]
        errors += datapacks.problems(datapacks.all_files(repo))
    if a.online and not errors:
        upstream = upstream or Upstream(LiveHttp())
        errors += (verify_online(manifest, upstream, repo) + verify_pwsh_online(upstream, repo)
                   + verify_profile_online(upstream, repo))
    for e in errors:
        print("ERROR", e)
    counts = ", ".join(f"{len(entries.group(manifest, kind))} {group}" for kind, group in entries.GROUPS.items())
    print(f"{len(errors)} problem(s); {manifest['server'].get('type', '?')} server, {counts}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
