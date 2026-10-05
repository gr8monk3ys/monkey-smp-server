"""Check the manifest and package for mistakes that would break an install.

  python tools/validate.py              offline checks (structure, entries, patches, defaults, client pack)
  python tools/validate.py --online     also download every file, verify its size and hash, and apply
                                        each patch to its download to prove it still fits
"""
import argparse
import re
import sys

import defaults
import entries
import patches
from repo import REPO, load_json
from upstream import LiveHttp, Upstream

PACKAGE_FILES = ("Start Server.bat", "Stop Server.bat", "Backup World.bat", "Add Player.bat", "READ ME FIRST.txt")
MANIFEST_KEYS = ("name", "version", "minecraft", "java", "server", "world", "plugins", "datapacks")


def validate(manifest: dict, repo=REPO) -> list[str]:
    errors = [f"manifest: missing '{key}'" for key in MANIFEST_KEYS if key not in manifest]
    if errors:
        return errors
    if not re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]):
        errors.append("manifest: version must look like 1.2.3")
    if not re.fullmatch(r"-?\d*", str(manifest["world"].get("seed", ""))):
        errors.append("manifest: world.seed must be a number (or empty for random)")
    for kind, e in entries.artifacts(manifest):
        errors += entries.check(kind, e)
    for group in entries.GROUPS.values():
        files = [e.get("file", "").lower() for e in manifest[group]]
        slugs = [e.get("slug") for e in manifest[group]]
        for dup in sorted({f for f in files if files.count(f) > 1}):
            errors.append(f"{group}: duplicate file {dup}")
        for dup in sorted({s for s in slugs if slugs.count(s) > 1}):
            errors.append(f"{group}: duplicate project {dup}")
    return errors + patches.check(manifest, repo)


def validate_package(repo=REPO) -> list[str]:
    props = (repo.defaults / "server.properties").read_text(encoding="utf-8")
    errors = defaults.check_server_properties(props)
    errors += [f"package/{name} is missing" for name in PACKAGE_FILES if not (repo.package / name).is_file()]
    for script in sorted(repo.package.rglob("*.ps*1")) + sorted(repo.package.glob("*.bat")):
        if any(b > 127 for b in script.read_bytes()):
            errors.append(f"{script.relative_to(repo.package).as_posix()} must be plain ASCII "
                          "(Windows PowerShell 5.1 reads BOM-less files as ANSI; see ADR-0003)")
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


def main(argv=None, repo=REPO, upstream=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--online", action="store_true")
    a = ap.parse_args(argv)
    manifest = repo.load_manifest()
    errors = validate(manifest, repo) + validate_package(repo) + validate_client(manifest, repo)
    if a.online and not errors:
        errors += verify_online(manifest, upstream or Upstream(LiveHttp()), repo)
    for e in errors:
        print("ERROR", e)
    print(f"{len(errors)} problem(s); {len(manifest['plugins'])} plugins, {len(manifest['datapacks'])} datapacks")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
