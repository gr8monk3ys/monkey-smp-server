"""Capture a running setup into the repo, so it can be rebuilt anywhere.

  python tools/snapshot.py server C:/MCServer/factions
      Rewrites package/realms/manifest.json from a Paper or Fabric server folder. Every plugin, mod
      and datapack must be on Modrinth (matched by hash) or the snapshot fails.

      Paper (paper.jar + version_history.json): the Paper build is matched by hash, plugins come
      from plugins/*.jar.
      Fabric (a Fabric server launcher jar such as fabric-server.jar, plus a mods/ folder): the
      Minecraft and loader versions are read from the launcher jar's install.properties, the
      launcher is pinned to Fabric meta's jar for the newest stable installer, and mods come from
      mods/*.jar.

      Datapacks come from <level-name>/datapacks/*.zip (level-name read from server.properties).
      A mod or datapack edited in place is matched against mod-originals/ or datapack-originals/
      <same name>, and the files that differ are stored as a patch under
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
import zipfile
from pathlib import Path
from typing import NamedTuple

import defaults
import entries
import patches
from repo import REPO, load_json, save_json
from upstream import LiveHttp, Upstream, fabric_server_jar_url

JAVA_MAJOR = 25
CLIENT_CONTENT = ("mods", "resourcepacks", "shaderpacks")


class Found(NamedTuple):
    version: dict
    sha1: str
    slug: str


class FabricLauncher(NamedTuple):
    """A Fabric server launcher jar and the versions baked into it."""
    path: Path
    minecraft: str
    loader: str
    installer: str  # the installer that generated the jar ("" if its MANIFEST.MF doesn't say)


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


def server_properties(server_dir: Path) -> dict[str, str]:
    props = server_dir / "server.properties"
    return defaults.parse_properties(props.read_text(encoding="utf-8")) if props.is_file() else {}


def level_name(server_dir: Path) -> str:
    """The world folder the server uses (server.properties level-name, Minecraft's default 'world')."""
    return server_properties(server_dir).get("level-name") or "world"


def level_seed(server_dir: Path) -> str:
    """server.properties level-seed as the number Minecraft uses ("" when empty, i.e. random).

    Minecraft takes a seed that isn't a whole number as text and uses its Java String.hashCode().
    """
    seed = server_properties(server_dir).get("level-seed", "")
    if re.fullmatch(r"-?\d+", seed) and -2**63 <= int(seed) < 2**63:
        return seed
    if not seed:
        return ""
    h = 0
    utf16 = seed.encode("utf-16-be")
    for i in range(0, len(utf16), 2):
        h = (31 * h + int.from_bytes(utf16[i:i + 2], "big")) & 0xFFFFFFFF
    return str(h - 2**32 if h >= 2**31 else h)


# --- what kind of server it is ------------------------------------------------------------------

def read_fabric_launcher(jar: Path) -> FabricLauncher | None:
    """The versions in a Fabric server launcher jar, or None if `jar` isn't one.

    Fabric meta generates the launcher with an install.properties naming the Minecraft and loader
    versions; the launcher reads exactly that file to decide what to download and run, so it is the
    authority on what the server runs (versions/ and .fabric/ are caches that can hold leftovers
    from an earlier version). The installer version is MANIFEST.MF's Implementation-Version.
    """
    try:
        with zipfile.ZipFile(jar) as z:
            names = set(z.namelist())
            if "install.properties" not in names:
                return None
            props = defaults.parse_properties(z.read("install.properties").decode("utf-8"))
            mf = z.read("META-INF/MANIFEST.MF").decode("utf-8") if "META-INF/MANIFEST.MF" in names else ""
    except (zipfile.BadZipFile, OSError):
        return None
    mc, loader = props.get("game-version"), props.get("fabric-loader-version")
    if not mc or not loader:
        return None
    installer = next((line.split(":", 1)[1].strip() for line in mf.splitlines()
                      if line.startswith("Implementation-Version:")), "")
    return FabricLauncher(jar, mc, loader, installer)


def detect_server(server_dir: Path) -> FabricLauncher | None:
    """The Fabric launcher of a Fabric server folder, or None for a Paper server folder.

    Paper: paper.jar + version_history.json. Fabric: a launcher jar in the folder (fabric-server.jar
    preferred if there are several) + a mods/ folder.
    """
    launchers = [x for p in sorted(server_dir.glob("*.jar")) if (x := read_fabric_launcher(p))]
    is_paper = (server_dir / "paper.jar").is_file() and (server_dir / "version_history.json").is_file()
    if launchers and is_paper:
        raise SystemExit(f"{server_dir} has both paper.jar and a Fabric launcher "
                         f"({launchers[0].path.name}); remove the one the server doesn't use")
    if len(launchers) > 1:
        preferred = [x for x in launchers if x.path.name.lower() == "fabric-server.jar"]
        if len(preferred) != 1:
            names = ", ".join(x.path.name for x in launchers)
            raise SystemExit(f"{server_dir} has several Fabric launchers ({names}); keep only the one start.bat runs")
        launchers = preferred
    if launchers:
        if not (server_dir / "mods").is_dir():
            raise SystemExit(f"{server_dir} has a Fabric launcher ({launchers[0].path.name}) but no mods/ folder")
        return launchers[0]
    if is_paper:
        return None
    raise SystemExit(f"{server_dir} is neither a Paper server (paper.jar + version_history.json) nor a "
                     "Fabric server (a Fabric launcher jar such as fabric-server.jar + mods/)")


def paper_entry(upstream: Upstream, server_dir: Path, mc: str) -> dict:
    sha256 = hashlib.sha256((server_dir / "paper.jar").read_bytes()).hexdigest()
    for build in upstream.paper_builds(mc):
        entry = entries.paper(build)
        if entry["hashes"]["sha256"] == sha256:
            return entry
    raise SystemExit("paper.jar doesn't match any Paper build for " + mc)


def fabric_entry(upstream: Upstream, launcher: FabricLauncher) -> dict:
    """Fabric meta's launcher for the server's Minecraft and loader versions and the newest stable installer.

    The launcher's bytes depend on the installer version, so the local jar matches the pinned one only
    if it came from the same installer; when it doesn't, meta's jar is pinned anyway (it runs the same
    loader and Minecraft version) and a note says so.
    """
    installer = upstream.newest_stable_fabric_installer()
    if not installer:
        raise SystemExit("Fabric meta lists no stable installer")
    jar = upstream.download(fabric_server_jar_url(launcher.minecraft, launcher.loader, installer))
    entry = entries.fabric(launcher.minecraft, launcher.loader, installer, jar)
    if hashlib.sha256(launcher.path.read_bytes()).hexdigest() != entry["hashes"]["sha256"]:
        print(f"note: {launcher.path.name} (installer {launcher.installer or 'unknown'}) is not byte-identical to "
              f"Fabric meta's launcher for installer {installer}; pinning meta's jar, which runs the same "
              f"Minecraft {launcher.minecraft} and loader {launcher.loader}")
    return entry


# --- snapshot -----------------------------------------------------------------------------------

def _match(paths: list[Path], originals: Path, found: dict, missing: list, new_patches: dict) -> list[dict]:
    """Entries for files found on disk; a file not on Modrinth whose original (same name in
    `originals`) is becomes that original plus a patch. Unknown files are appended to `missing`."""
    out = []
    for p in paths:
        orig = originals / p.name
        if found[p]:
            out.append(entries.from_disk(*found[p], disk_name=p.name))
        elif found.get(orig):
            base = entries.from_disk(*found[orig], disk_name=p.name)
            try:
                files = patches.make(orig.read_bytes(), p.read_bytes())
            except patches.PatchError as err:
                raise SystemExit(f"{p}: {err}") from err
            if files:
                slug = base["slug"]
                if slug in new_patches:
                    raise SystemExit(f"{p}: another patched file already uses patches/{slug}")
                new_patches[slug] = files
                base = entries.from_disk(*found[orig], disk_name=p.name,
                                         patch=patches.reference(slug, base["hashes"]["sha512"]))
            out.append(base)
        else:
            missing.append(p)
    return out


def snapshot_server(server_dir, *, repo=REPO, upstream: Upstream | None = None, keep_java=True) -> dict:
    upstream = upstream or Upstream(LiveHttp())
    server_dir = Path(server_dir)
    old = repo.load_manifest() if repo.manifest.exists() else {}
    launcher = detect_server(server_dir)
    server_type = "fabric" if launcher else "paper"
    mc = launcher.minecraft if launcher else minecraft_version(server_dir)
    level = level_name(server_dir)

    plugin_paths = [] if launcher else files_in(server_dir / "plugins", (".jar",))
    mod_paths = files_in(server_dir / "mods", (".jar",)) if launcher else []
    pack_paths = files_in(server_dir / level / "datapacks", (".zip",))
    mod_originals, pack_originals = server_dir / "mod-originals", server_dir / "datapack-originals"
    original_paths = (files_in(mod_originals, (".jar",)) if launcher else []) + files_in(pack_originals, (".zip",))
    found = identify(upstream, plugin_paths + mod_paths + pack_paths + original_paths)

    missing = [p for p in plugin_paths if not found[p]]
    plugins = [entries.from_disk(*found[p], disk_name=p.name) for p in plugin_paths if found[p]]
    new_patches = {}
    mods = _match(mod_paths, mod_originals, found, missing, new_patches)
    datapacks = _match(pack_paths, pack_originals, found, missing, new_patches)
    if missing:
        raise SystemExit("not on Modrinth (add them by hand or replace them):\n  "
                         + "\n  ".join(str(p) for p in missing))

    server = fabric_entry(upstream, launcher) if launcher else paper_entry(upstream, server_dir, mc)
    java = old["java"] if keep_java and "java" in old else entries.java(upstream.adoptium_latest_jre(JAVA_MAJOR))
    same_world = "world" in old and old.get("minecraft") == mc and old.get("server", {}).get("type") == server_type
    world = old["world"] if same_world else {"level_name": level, "seed": level_seed(server_dir)}

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
        "java": java,
        "server": server,
        "world": world,
        "plugins": sorted(plugins, key=lambda e: e["slug"]),
        "mods": sorted(mods, key=lambda e: e["slug"]),
        "datapacks": sorted(datapacks, key=lambda e: e["slug"]),
    }
    repo.save_manifest(manifest)
    what = (f"Fabric loader {server['loader']} (installer {server['installer']}), {len(mods)} mods" if launcher
            else f"Paper build {server['build']}, {len(plugins)} plugins")
    print(f"manifest: Minecraft {mc}, {what}, {len(datapacks)} datapacks from {level}/datapacks "
          f"({len(new_patches)} patched); world {'kept' if same_world else 'read from server.properties'}")
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
