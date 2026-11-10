"""Pin one of the owner's own mods from a GitHub release (ADR-0009), on the server and in the players' pack.

  python tools/pin_github.py patina-and-chime v0.2.0 patina-and-chime-0.2.0+26.2.jar

The mod is the name of a repository in entries.GITHUB_PINS; the tag and the jar are one release of it and one
asset of that release. This downloads the asset, and writes its size and hashes as the mod's entry in the
manifest and as the same file in client/modrinth.index.json, replacing the release pinned before. The version
is read from the jar's fabric.mod.json.

Nothing else moves such a pin (check_updates.py and add.py skip it), so run this again for every new release of
the mod. Afterwards: validate.py --online and the smoke test. Players need the new pack to join, because these
mods add blocks and items, so the release is a new client pack too.
"""
import argparse
import hashlib
import io
import json
import zipfile

import client_env
import entries
from repo import REPO, load_json, save_json
from upstream import LiveHttp, Upstream

REPOS = {repo.split("/", 1)[1]: repo for repo in entries.GITHUB_PINS}


def mod_version(jar: bytes) -> str:
    """The version a Fabric mod jar gives itself."""
    try:
        with zipfile.ZipFile(io.BytesIO(jar)) as z:
            version = json.loads(z.read("fabric.mod.json").decode("utf-8-sig"))["version"]
    except (zipfile.BadZipFile, KeyError, ValueError) as err:
        raise SystemExit(f"not a Fabric mod jar (fabric.mod.json: {err})") from None
    if not isinstance(version, str) or not version:
        raise SystemExit("not a Fabric mod jar (fabric.mod.json has no version)")
    return version


def pin(manifest: dict, index: dict, slug: str, tag: str, file: str, jar: bytes) -> tuple[dict, dict]:
    """Copies of the manifest and the client index with the mod pinned to this jar (in their sort order)."""
    if slug not in REPOS:
        raise SystemExit(f"{slug} can't be pinned from GitHub: it is not one of {', '.join(sorted(REPOS))} "
                         "(entries.GITHUB_PINS, ADR-0009)")
    server_type = manifest.get("server", {}).get("type", "paper")
    if not entries.kind_allowed(server_type, "mod"):
        raise SystemExit(f"a {server_type} server can't run mods")
    mods = entries.group(manifest, "mod")
    old = next((e for e in mods if e["slug"] == slug), None)
    if old and not entries.is_github(old):
        raise SystemExit(f"{slug} is pinned from Modrinth; take that pin out first")
    new = entries.github(slug, REPOS[slug], tag, mod_version(jar), file, jar)
    out = entries.with_all_groups(dict(manifest))
    out["mods"] = sorted([e for e in mods if e is not old] + [new], key=lambda e: e["slug"])

    path = f"mods/{file}"
    client = {"path": path, "hashes": {"sha1": hashlib.sha1(jar).hexdigest(), "sha512": new["hashes"]["sha512"]},
              "env": client_env.env({"path": path, "downloads": [new["url"]]}),
              "downloads": [new["url"]], "fileSize": new["size"]}
    gone = {path, f"mods/{old['file']}"} if old else {path}
    files = [f for f in index["files"] if f["path"] not in gone] + [client]
    # mods/ first, by path ignoring case (as the index is kept), then everything else in its order.
    mod_files = sorted((f for f in files if f["path"].startswith("mods/")), key=lambda f: f["path"].lower())
    return out, {**index, "files": mod_files + [f for f in files if not f["path"].startswith("mods/")]}


def main(argv=None, repo=REPO, upstream=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mod", choices=sorted(REPOS))
    ap.add_argument("tag", help="the release's tag, e.g. v0.2.0")
    ap.add_argument("file", help="the jar's name in that release")
    a = ap.parse_args(argv)
    jar = (upstream or Upstream(LiveHttp())).download(entries.github_url(REPOS[a.mod], a.tag, a.file))
    index_path = repo.client / "modrinth.index.json"
    manifest, index = pin(repo.load_manifest(), load_json(index_path), a.mod, a.tag, a.file, jar)
    repo.save_manifest(manifest)
    save_json(index_path, index)
    e = next(x for x in manifest["mods"] if x["slug"] == a.mod)
    print(f"pinned {a.mod} {e['version']} ({e['file']}, {e['size']} bytes) from {e['github']} {e['tag']}, "
          "server and players' pack")


if __name__ == "__main__":
    main()
