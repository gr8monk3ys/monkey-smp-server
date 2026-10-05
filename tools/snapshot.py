"""Capture a running setup into the repo, so it can be rebuilt anywhere.

  python tools/snapshot.py server C:/MCServer/factions
      Rewrites package/realms/manifest.json from the server's paper.jar, plugins/*.jar and
      <level-name>/datapacks/*.zip (level-name read from its server.properties). Every file must
      be on Modrinth (matched by hash) or the snapshot fails. A datapack edited in place is matched
      against datapack-originals/<same name>, and the files that differ are stored as a patch under
      package/realms/patches/<slug>/, pinned to that original's hash.

  python tools/snapshot.py client "C:/Games/PrismLauncher/instances/Factions Client/minecraft"
      Rewrites client/ (a Modrinth modpack source) from a Prism instance: mods, resource packs
      and shader packs are linked by hash, and config/, shader settings and options.txt are
      copied as overrides. Files that aren't on Modrinth are left out (not redistributed).

Hand-curated config defaults (package/realms/defaults/) are not touched.
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import NamedTuple

import defaults
import entries
import patches
from repo import REPO, load_json, save_json
from upstream import LiveHttp, Upstream

JAVA_MAJOR = 25
CLIENT_CONTENT = ("mods", "resourcepacks", "shaderpacks")


class Found(NamedTuple):
    version: dict
    sha1: str
    slug: str


def identify(upstream: Upstream, paths) -> dict[Path, Found | None]:
    """Match each local file to its Modrinth version by SHA-1. Unmatched files map to None."""
    sha1 = {p: hashlib.sha1(p.read_bytes()).hexdigest() for p in paths}
    versions = upstream.modrinth_versions_by_sha1(sha1.values())
    projects = upstream.modrinth_projects(v["project_id"] for v in versions.values())
    return {p: Found(versions[h], h, projects[versions[h]["project_id"]]["slug"]) if h in versions else None
            for p, h in sha1.items()}


def files_in(folder: Path, exts) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.name.lower().endswith(exts))


def minecraft_version(server_dir: Path) -> str:
    hist = load_json(server_dir / "version_history.json")["currentVersion"]
    m = re.search(r"MC: ([\w.\-]+)\)", hist)
    if not m:
        raise SystemExit(f"can't read the Minecraft version from version_history.json: {hist}")
    return m.group(1)


def level_name(server_dir: Path) -> str:
    """The world folder the server uses (server.properties level-name, Minecraft's default 'world')."""
    props = server_dir / "server.properties"
    if not props.is_file():
        return "world"
    return defaults.parse_properties(props.read_text(encoding="utf-8")).get("level-name") or "world"


def paper_entry(upstream: Upstream, server_dir: Path, mc: str) -> dict:
    sha256 = hashlib.sha256((server_dir / "paper.jar").read_bytes()).hexdigest()
    for build in upstream.paper_builds(mc):
        entry = entries.paper(build)
        if entry["hashes"]["sha256"] == sha256:
            return entry
    raise SystemExit("paper.jar doesn't match any Paper build for " + mc)


def snapshot_server(server_dir, *, repo=REPO, upstream: Upstream | None = None, keep_java=True) -> dict:
    upstream = upstream or Upstream(LiveHttp())
    server_dir = Path(server_dir)
    old = repo.load_manifest() if repo.manifest.exists() else {}
    mc = minecraft_version(server_dir)
    level = level_name(server_dir)

    plugin_paths = files_in(server_dir / "plugins", (".jar",))
    pack_paths = files_in(server_dir / level / "datapacks", (".zip",))
    originals = server_dir / "datapack-originals"
    found = identify(upstream, plugin_paths + pack_paths + files_in(originals, (".zip",)))

    missing = [p for p in plugin_paths if not found[p]]
    plugins = [entries.from_disk(*found[p], disk_name=p.name) for p in plugin_paths if found[p]]
    datapacks, new_patches = [], {}
    for p in pack_paths:
        orig = originals / p.name
        if found[p]:
            datapacks.append(entries.from_disk(*found[p], disk_name=p.name))
        elif found.get(orig):
            base = entries.from_disk(*found[orig], disk_name=p.name)
            try:
                files = patches.make(orig.read_bytes(), p.read_bytes())
            except patches.PatchError as err:
                raise SystemExit(f"{p}: {err}") from err
            if files:
                new_patches[base["slug"]] = files
                base = entries.from_disk(*found[orig], disk_name=p.name,
                                         patch=patches.reference(base["slug"], base["hashes"]["sha512"]))
            datapacks.append(base)
        else:
            missing.append(p)
    if missing:
        raise SystemExit("not on Modrinth (add them by hand or replace them):\n  "
                         + "\n  ".join(str(p) for p in missing))

    if repo.patches.is_dir():
        for stale in repo.patches.iterdir():
            if stale.name not in new_patches:
                shutil.rmtree(stale)
    for slug, files in new_patches.items():
        patches.write(repo.patches / slug, files)

    manifest = {
        "name": old.get("name", "The Realms"),
        "version": old.get("version", "1.0.0"),
        "minecraft": mc,
        "java": old["java"] if keep_java and "java" in old else entries.java(upstream.adoptium_latest_jre(JAVA_MAJOR)),
        "server": paper_entry(upstream, server_dir, mc),
        "world": old.get("world", {"level_name": level, "seed": ""}),
        "plugins": sorted(plugins, key=lambda e: e["slug"]),
        "datapacks": sorted(datapacks, key=lambda e: e["slug"]),
    }
    repo.save_manifest(manifest)
    print(f"manifest: Minecraft {mc}, Paper build {manifest['server']['build']}, "
          f"{len(plugins)} plugins, {len(datapacks)} datapacks from {level}/datapacks "
          f"({len(new_patches)} patched)")
    return manifest


def snapshot_client(instance, *, repo=REPO, upstream: Upstream | None = None) -> dict:
    upstream = upstream or Upstream(LiveHttp())
    instance = Path(instance)
    index_path = repo.client / "modrinth.index.json"
    old = load_json(index_path) if index_path.exists() else {}
    paths = [p for d in CLIENT_CONTENT for p in files_in(instance / d, (".jar", ".zip"))]
    found = identify(upstream, paths)
    files, skipped = [], []
    for p in paths:
        rel = p.relative_to(instance).as_posix()
        if not found[p]:
            skipped.append(rel)
            continue
        version, sha1, _ = found[p]
        f = next(x for x in version["files"] if x["hashes"]["sha1"] == sha1)
        files.append({"path": rel, "hashes": {"sha1": sha1, "sha512": f["hashes"]["sha512"]},
                      "env": {"client": "required", "server": "unsupported"},
                      "downloads": [f["url"]], "fileSize": f["size"]})
    manifest = repo.load_manifest()
    loader = fabric_loader(instance) or old.get("dependencies", {}).get("fabric-loader")
    if not loader:
        raise SystemExit("can't tell the Fabric loader version (no mmc-pack.json next to the instance)")
    index = {"formatVersion": 1, "game": "minecraft",
             "versionId": manifest["version"], "name": old.get("name", "The Realms - Client"),
             "summary": old.get("summary", "Client pack for The Realms factions server."),
             "files": files,
             "dependencies": {"minecraft": manifest["minecraft"], "fabric-loader": loader}}

    overrides = repo.client / "overrides"
    shutil.rmtree(overrides, ignore_errors=True)
    overrides.mkdir(parents=True)
    if (instance / "config").is_dir():
        shutil.copytree(instance / "config", overrides / "config", ignore=shutil.ignore_patterns("*.bak*", "*.old"))
    (overrides / "shaderpacks").mkdir()
    for f in files_in(instance / "shaderpacks", (".txt",)):
        shutil.copy2(f, overrides / "shaderpacks" / f.name)
    if (instance / "options.txt").is_file():
        shutil.copy2(instance / "options.txt", overrides / "options.txt")
    save_json(index_path, index)
    print(f"client: {len(files)} files linked from Modrinth")
    if skipped:
        print("left out (not on Modrinth):\n  " + "\n  ".join(skipped))
    return index


def fabric_loader(instance: Path) -> str | None:
    pack = instance.parent / "mmc-pack.json"
    if pack.exists():
        for c in json.loads(pack.read_text(encoding="utf-8"))["components"]:
            if c["uid"] == "net.fabricmc.fabric-loader":
                return c["version"]
    return None


def main(argv=None, repo=REPO, upstream=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["server", "client"])
    ap.add_argument("path")
    ap.add_argument("--update-java", action="store_true",
                    help="pin the newest Temurin JRE instead of keeping the current one")
    a = ap.parse_args(argv)
    if a.what == "server":
        snapshot_server(a.path, repo=repo, upstream=upstream, keep_java=not a.update_java)
    else:
        snapshot_client(a.path, repo=repo, upstream=upstream)


if __name__ == "__main__":
    main()
