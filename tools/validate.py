"""Check the manifest and package for mistakes that would break an install.

  python tools/validate.py              offline checks (structure, patches, defaults, client pack)
  python tools/validate.py --online     also download every file and verify its size and hash
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CLIENT, PACKAGE, REALMS, artifacts, digest, hash_of, http_bytes, load_manifest  # noqa: E402

HEX = {"sha1": 40, "sha256": 64, "sha512": 128}
ALLOWED_HOSTS = ("https://cdn.modrinth.com/", "https://fill-data.papermc.io/",
                 "https://github.com/adoptium/")
TOKENS = ("{{RCON_PASSWORD}}", "{{SEED}}", "{{LEVEL_NAME}}")


def check_entry(kind, e):
    errors = []
    for key in ("file", "url", "size", "hashes"):
        if key not in e:
            errors.append(f"{kind} {e.get('file', '?')}: missing '{key}'")
    if errors:
        return errors
    if not e["url"].startswith(ALLOWED_HOSTS):
        errors.append(f"{kind} {e['file']}: url is not from an allowed host: {e['url']}")
    if re.search(r'[\\/:*?"<>|]', e["file"]):
        errors.append(f"{kind} {e['file']}: file name has characters Windows can't use")
    if not isinstance(e["size"], int) or e["size"] <= 0:
        errors.append(f"{kind} {e['file']}: bad size")
    try:
        algo, value = hash_of(e)
        if not re.fullmatch(rf"[0-9a-f]{{{HEX[algo]}}}", value):
            errors.append(f"{kind} {e['file']}: {algo} is not {HEX[algo]} lowercase hex chars")
    except KeyError as err:
        errors.append(str(err))
    return errors


def validate(manifest):
    errors = []
    for key in ("name", "version", "minecraft", "java", "server", "world", "plugins", "datapacks"):
        if key not in manifest:
            errors.append(f"manifest: missing '{key}'")
    if errors:
        return errors
    if not re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]):
        errors.append("manifest: version must look like 1.2.3")
    if not re.fullmatch(r"-?\d*", str(manifest["world"].get("seed", ""))):
        errors.append("manifest: world.seed must be a number (or empty for random)")
    for kind, e in artifacts(manifest):
        errors += check_entry(kind, e)
    for group in ("plugins", "datapacks"):
        files = [e["file"].lower() for e in manifest[group]]
        slugs = [e.get("slug") for e in manifest[group]]
        for dup in {f for f in files if files.count(f) > 1}:
            errors.append(f"{group}: duplicate file {dup}")
        for dup in {s for s in slugs if slugs.count(s) > 1}:
            errors.append(f"{group}: duplicate project {dup}")
    for d in manifest["datapacks"]:
        if "patch" in d:
            path = os.path.join(REALMS, *d["patch"].split("/"))
            if not d["patch"].startswith("patches/") or not os.path.isdir(path) or not os.listdir(path):
                errors.append(f"datapack {d['file']}: patch folder {d['patch']} is missing or empty")
    patch_dirs = {f"patches/{p}" for p in os.listdir(os.path.join(REALMS, "patches"))} if os.path.isdir(
        os.path.join(REALMS, "patches")) else set()
    for orphan in patch_dirs - {d.get("patch") for d in manifest["datapacks"]}:
        errors.append(f"{orphan} is not used by any datapack")
    return errors


def validate_package():
    errors = []
    props = open(os.path.join(REALMS, "defaults", "server.properties"), encoding="utf-8").read()
    for token in TOKENS:
        if token not in props:
            errors.append(f"defaults/server.properties: missing {token}")
    if re.search(r"(?m)^rcon\.password=(?!\{\{)", props):
        errors.append("defaults/server.properties: a real RCON password is committed")
    for name in ("Start Server.bat", "Stop Server.bat", "Backup World.bat", "Add Player.bat", "READ ME FIRST.txt"):
        if not os.path.isfile(os.path.join(PACKAGE, name)):
            errors.append(f"package/{name} is missing")
    script = open(os.path.join(REALMS, "realms.ps1"), "rb").read()
    if any(b > 127 for b in script):
        errors.append("realms.ps1 must be plain ASCII (Windows PowerShell 5.1 reads BOM-less files as ANSI)")
    return errors


def validate_client(manifest):
    path = os.path.join(CLIENT, "modrinth.index.json")
    index = json.load(open(path, encoding="utf-8"))
    errors = []
    if index["dependencies"].get("minecraft") != manifest["minecraft"]:
        errors.append("client: minecraft version differs from the server manifest")
    for f in index["files"]:
        if not f["downloads"] or not all(u.startswith("https://cdn.modrinth.com/") for u in f["downloads"]):
            errors.append(f"client {f['path']}: downloads must be Modrinth CDN URLs")
        if f["path"].startswith(("/", "..")) or ".." in f["path"].split("/"):
            errors.append(f"client {f['path']}: unsafe path")
    return errors


def verify_online(manifest):
    errors = []
    for kind, e in artifacts(manifest):
        data = http_bytes(e["url"])
        algo, value = hash_of(e)
        if len(data) != e["size"] or digest(data, algo) != value:
            errors.append(f"{kind} {e['file']}: download doesn't match the pinned size/hash")
        else:
            print(f"ok  {kind:8} {e['file']}")
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--online", action="store_true")
    a = ap.parse_args()
    manifest = load_manifest()
    errors = validate(manifest) + validate_package() + validate_client(manifest)
    if a.online and not errors:
        errors += verify_online(manifest)
    for e in errors:
        print("ERROR", e)
    print(f"{len(errors)} problem(s); {len(manifest['plugins'])} plugins, {len(manifest['datapacks'])} datapacks")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
