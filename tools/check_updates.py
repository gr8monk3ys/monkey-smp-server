"""Find newer builds of Paper and of every plugin/datapack for the pinned Minecraft version.

  python tools/check_updates.py                 print a Markdown report
  python tools/check_updates.py --apply         also pin the newer builds in manifest.json
  python tools/check_updates.py --out report.md write the report to a file (used by CI)

Only stable releases for the same Minecraft version are considered. After --apply, run the
smoke test (tests/smoke.ps1) before releasing: plugin updates can change configs.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MODRINTH, http_json, load_manifest, q, save_manifest  # noqa: E402

PLUGIN_LOADERS = ["paper", "spigot", "bukkit", "purpur", "folia"]
DATAPACK_LOADERS = ["datapack"]


def newest_release(project_id, mc, loaders):
    versions = http_json(f"{MODRINTH}/project/{project_id}/version?game_versions={q([mc])}&loaders={q(loaders)}")
    releases = [v for v in versions if v["version_type"] == "release"]
    return max(releases, key=lambda v: v["date_published"]) if releases else None


def pick_file(version, old_file):
    files = version["files"]
    jar_or_zip = [f for f in files if f["filename"].endswith((".jar", ".zip"))] or files
    same_ext = [f for f in jar_or_zip if os.path.splitext(f["filename"])[1] == os.path.splitext(old_file)[1]]
    return next((f for f in same_ext if f["primary"]), (same_ext or jar_or_zip)[0])


def find_updates(manifest):
    mc = manifest["minecraft"]
    updates = []
    builds = http_json(f"https://fill.papermc.io/v3/projects/paper/versions/{mc}/builds")
    stable = [b for b in builds if b.get("channel") == "STABLE"]
    if stable and stable[0]["id"] > manifest["server"]["build"]:
        d = stable[0]["downloads"]["server:default"]
        updates.append(("server", "paper", str(manifest["server"]["build"]), str(stable[0]["id"]),
                        {"type": "paper", "build": stable[0]["id"], "file": d["name"], "url": d["url"],
                         "size": d["size"], "hashes": {"sha256": d["checksums"]["sha256"]}}))
    for group, loaders in (("plugins", PLUGIN_LOADERS), ("datapacks", DATAPACK_LOADERS)):
        for e in manifest[group]:
            v = newest_release(e["project_id"], mc, loaders)
            if not v or v["id"] == e["version_id"]:
                continue
            f = pick_file(v, e["file"])
            new = {**e, "version": v["version_number"], "version_id": v["id"], "url": f["url"],
                   "size": f["size"], "hashes": {"sha512": f["hashes"]["sha512"]}}
            # Keep the on-disk name for datapacks (it's how the world refers to them); jars take the new name.
            if group == "plugins":
                new["file"] = f["filename"]
            updates.append((group, e["slug"], e["version"], v["version_number"], new))
    return updates


def report(manifest, updates):
    lines = [f"Pinned: Minecraft {manifest['minecraft']}, manifest {manifest['version']}", ""]
    if not updates:
        return "\n".join(lines + ["Everything is on the newest stable build."])
    lines += ["| Kind | Project | Pinned | Newest |", "|---|---|---|---|"]
    lines += [f"| {k} | {slug} | {old} | {new} |" for k, slug, old, new, _ in updates]
    lines += ["", "To take them: `python tools/check_updates.py --apply`, run the smoke test, bump the version, tag."]
    return "\n".join(lines)


def apply(manifest, updates):
    for group, slug, _, _, new in updates:
        if group == "server":
            manifest["server"] = new
        else:
            manifest[group] = [new if e["slug"] == slug else e for e in manifest[group]]
    save_manifest(manifest)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    manifest = load_manifest()
    updates = find_updates(manifest)
    text = report(manifest, updates)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    if a.apply and updates:
        apply(manifest, updates)
        print(f"\npinned {len(updates)} update(s) in manifest.json")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"count={len(updates)}\n")


if __name__ == "__main__":
    main()
