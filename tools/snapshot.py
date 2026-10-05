"""Capture a running setup into the repo, so it can be rebuilt anywhere.

  python tools/snapshot.py server C:/MCServer/factions
      Rewrites package/realms/manifest.json from the server's paper.jar, plugins/*.jar and
      world/datapacks/*.zip. Every file must be on Modrinth (matched by hash) or the snapshot
      fails. A datapack edited in place is matched against datapack-originals/<same name>,
      and the files that differ are stored under package/realms/patches/<slug>/.

  python tools/snapshot.py client "C:/Games/PrismLauncher/instances/Factions Client/minecraft"
      Rewrites client/ (a Modrinth modpack source) from a Prism instance: mods, resource packs
      and shader packs are linked by hash, and config/, shader settings and options.txt are
      copied as overrides. Files that aren't on Modrinth are left out (not redistributed).

Hand-curated config defaults (package/realms/defaults/) are not touched.
"""
import argparse
import json
import os
import re
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CLIENT, MODRINTH, REALMS, digest, http_json, load_manifest, q, save_manifest  # noqa: E402

JAVA_MAJOR = 25


def modrinth_lookup(paths):
    """Map each local file to its Modrinth version/file by sha1. Unmatched files map to None."""
    blobs = {p: open(p, "rb").read() for p in paths}
    sha1 = {p: digest(b, "sha1") for p, b in blobs.items()}
    found = http_json(f"{MODRINTH}/version_files", {"hashes": list(sha1.values()), "algorithm": "sha1"}) if sha1 else {}
    ids = sorted({v["project_id"] for v in found.values()})
    slugs = {p["id"]: p["slug"] for p in http_json(f"{MODRINTH}/projects?ids={q(ids)}")} if ids else {}
    out = {}
    for p, h in sha1.items():
        v = found.get(h)
        if not v:
            out[p] = None
            continue
        f = next(x for x in v["files"] if x["hashes"]["sha1"] == h)
        out[p] = {
            "slug": slugs[v["project_id"]],
            "project_id": v["project_id"],
            "version": v["version_number"],
            "version_id": v["id"],
            "file": os.path.basename(p),
            "url": f["url"],
            "size": f["size"],
            "hashes": {"sha512": f["hashes"]["sha512"]},
        }
    return out


def files_in(folder, exts):
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith(exts) and os.path.isfile(os.path.join(folder, f)))


def zip_diff(original, patched):
    a, b = zipfile.ZipFile(original), zipfile.ZipFile(patched)
    if set(a.namelist()) != set(b.namelist()):
        raise SystemExit(f"{patched}: patch adds/removes files; only in-place edits are supported")
    return {n: b.read(n) for n in b.namelist() if a.read(n) != b.read(n)}


def paper_build(server_dir, mc):
    sha256 = digest(open(os.path.join(server_dir, "paper.jar"), "rb").read(), "sha256")
    for b in http_json(f"https://fill.papermc.io/v3/projects/paper/versions/{mc}/builds"):
        d = b["downloads"]["server:default"]
        if d["checksums"]["sha256"] == sha256:
            return {"type": "paper", "build": b["id"], "file": d["name"], "url": d["url"],
                    "size": d["size"], "hashes": {"sha256": sha256}}
    raise SystemExit("paper.jar doesn't match any Paper build for " + mc)


def java_runtime():
    a = http_json(f"https://api.adoptium.net/v3/assets/latest/{JAVA_MAJOR}/hotspot"
                  "?os=windows&architecture=x64&image_type=jre")[0]
    p = a["binary"]["package"]
    return {"vendor": "Eclipse Temurin JRE", "version": a["release_name"], "file": p["name"],
            "url": p["link"], "size": p["size"], "hashes": {"sha256": p["checksum"]}}


def snapshot_server(server_dir, keep_java):
    old = load_manifest() if os.path.exists(os.path.join(REALMS, "manifest.json")) else {}
    hist = json.load(open(os.path.join(server_dir, "version_history.json")))["currentVersion"]
    m = re.search(r"MC: ([\w.\-]+)\)", hist)
    if not m:
        raise SystemExit(f"can't read the Minecraft version from version_history.json: {hist}")
    mc = m.group(1)

    plugin_paths = files_in(os.path.join(server_dir, "plugins"), (".jar",))
    pack_paths = files_in(os.path.join(server_dir, "world", "datapacks"), (".zip",))
    originals = os.path.join(server_dir, "datapack-originals")
    lookup_paths = plugin_paths + pack_paths + files_in(originals, (".zip",))
    found = modrinth_lookup(lookup_paths)

    missing = [p for p in plugin_paths if not found[p]]
    plugins = [found[p] for p in plugin_paths if found[p]]
    datapacks = []
    for p in pack_paths:
        entry = found[p]
        orig = os.path.join(originals, os.path.basename(p))
        if not entry and os.path.exists(orig) and found.get(orig):
            entry = dict(found[orig])
            patch_dir = os.path.join(REALMS, "patches", entry["slug"])
            shutil.rmtree(patch_dir, ignore_errors=True)
            for name, data in zip_diff(orig, p).items():
                out = os.path.join(patch_dir, *name.split("/"))
                os.makedirs(os.path.dirname(out), exist_ok=True)
                open(out, "wb").write(data)
            entry["patch"] = "patches/" + entry["slug"]
        if entry:
            datapacks.append(entry)
        else:
            missing.append(p)
    if missing:
        raise SystemExit("not on Modrinth (add them by hand or replace them):\n  " + "\n  ".join(missing))

    manifest = {
        "name": old.get("name", "The Realms"),
        "version": old.get("version", "1.0.0"),
        "minecraft": mc,
        "java": old["java"] if keep_java and "java" in old else java_runtime(),
        "server": paper_build(server_dir, mc),
        "world": old.get("world", {"level_name": "world", "seed": ""}),
        "plugins": sorted(plugins, key=lambda e: e["slug"]),
        "datapacks": sorted(datapacks, key=lambda e: e["slug"]),
    }
    save_manifest(manifest)
    print(f"manifest: Minecraft {mc}, Paper build {manifest['server']['build']}, "
          f"{len(plugins)} plugins, {len(datapacks)} datapacks "
          f"({sum('patch' in d for d in datapacks)} patched)")


CLIENT_CONTENT = ("mods", "resourcepacks", "shaderpacks")


def snapshot_client(instance):
    old = json.load(open(os.path.join(CLIENT, "modrinth.index.json"))) if os.path.exists(
        os.path.join(CLIENT, "modrinth.index.json")) else {}
    paths = [p for d in CLIENT_CONTENT for p in files_in(os.path.join(instance, d), (".jar", ".zip"))]
    found = modrinth_lookup(paths)
    files, skipped = [], []
    for p in paths:
        e = found[p]
        if not e:
            skipped.append(os.path.relpath(p, instance))
            continue
        rel = os.path.relpath(p, instance).replace("\\", "/")
        files.append({"path": rel, "hashes": {"sha1": digest(open(p, "rb").read(), "sha1"),
                                              "sha512": e["hashes"]["sha512"]},
                      "env": {"client": "required", "server": "unsupported"},
                      "downloads": [e["url"]], "fileSize": e["size"]})
    manifest = load_manifest()
    index = {"formatVersion": 1, "game": "minecraft",
             "versionId": manifest["version"], "name": old.get("name", "The Realms - Client"),
             "summary": old.get("summary", "Client pack for The Realms factions server."),
             "files": files,
             "dependencies": {"minecraft": manifest["minecraft"],
                              "fabric-loader": fabric_loader(instance) or old["dependencies"]["fabric-loader"]}}

    overrides = os.path.join(CLIENT, "overrides")
    shutil.rmtree(overrides, ignore_errors=True)
    shutil.copytree(os.path.join(instance, "config"), os.path.join(overrides, "config"),
                    ignore=shutil.ignore_patterns("*.bak*", "*.old"))
    os.makedirs(os.path.join(overrides, "shaderpacks"), exist_ok=True)
    for f in os.listdir(os.path.join(instance, "shaderpacks")):
        if f.endswith(".txt"):
            shutil.copy2(os.path.join(instance, "shaderpacks", f), os.path.join(overrides, "shaderpacks", f))
    shutil.copy2(os.path.join(instance, "options.txt"), os.path.join(overrides, "options.txt"))
    with open(os.path.join(CLIENT, "modrinth.index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"client: {len(files)} files linked from Modrinth")
    if skipped:
        print("left out (not on Modrinth):\n  " + "\n  ".join(skipped))


def fabric_loader(instance):
    pack = os.path.join(os.path.dirname(instance), "mmc-pack.json")
    if os.path.exists(pack):
        for c in json.load(open(pack))["components"]:
            if c["uid"] == "net.fabricmc.fabric-loader":
                return c["version"]
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["server", "client"])
    ap.add_argument("path")
    ap.add_argument("--update-java", action="store_true",
                    help="pin the newest Temurin JRE instead of keeping the current one")
    a = ap.parse_args()
    if a.what == "server":
        snapshot_server(a.path, keep_java=not a.update_java)
    else:
        snapshot_client(a.path)


if __name__ == "__main__":
    main()
