"""Add Modrinth projects to the manifest, pinned to their newest stable build for our Minecraft version.

  python tools/add.py datapack player-corpses dragonkind-evolved
  python tools/add.py plugin chunky          (Paper servers)
  python tools/add.py mod lithium            (Fabric servers)

Projects already in the manifest are skipped (use check_updates.py to move them). A project with no
stable release for the pinned Minecraft version and loader fails the whole command, so nothing is
half-added, and so does a kind the server type doesn't run (plugins on Fabric, mods on Paper).
Run validate.py --online and the smoke test afterwards.
"""
import argparse

import entries
from check_updates import LOADERS
from repo import REPO
from upstream import LiveHttp, Upstream


def add(manifest: dict, kind: str, slugs: list[str], upstream: Upstream) -> tuple[dict, list[str]]:
    """A copy of the manifest with the projects added (sorted by slug), and the slugs actually added."""
    group = entries.GROUPS[kind]
    server_type = manifest.get("server", {}).get("type", "paper")
    if not entries.kind_allowed(server_type, kind):
        raise SystemExit(f"a {server_type} server can't run {group}")
    current = entries.group(manifest, kind)
    have = {e["slug"] for e in current} | {e["project_id"] for e in current}
    projects = {p["slug"]: p for p in upstream.modrinth_projects(slugs).values()}
    missing = [s for s in slugs if s not in projects]
    if missing:
        raise SystemExit(f"not on Modrinth: {', '.join(missing)}")
    new, added_slugs, problems = [], [], []
    for slug in slugs:
        p = projects[slug]
        if slug in have or p["id"] in have:
            continue
        v = upstream.newest_release(p["id"], manifest["minecraft"], LOADERS[kind])
        if not v:
            problems.append(f"{slug}: no stable {kind} release for Minecraft {manifest['minecraft']}")
            continue
        new.append(entries.added(kind, slug, v))
        added_slugs.append(slug)
    if problems:
        raise SystemExit("\n".join(problems))
    out = entries.with_all_groups(dict(manifest))
    out[group] = sorted(current + new, key=lambda e: e["slug"])
    return out, added_slugs


def main(argv=None, repo=REPO, upstream=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=sorted(entries.GROUPS))
    ap.add_argument("slugs", nargs="+")
    a = ap.parse_args(argv)
    manifest, added_slugs = add(repo.load_manifest(), a.kind, a.slugs, upstream or Upstream(LiveHttp()))
    if added_slugs:
        repo.save_manifest(manifest)
    group = manifest[entries.GROUPS[a.kind]]
    for slug in added_slugs:
        e = next(x for x in group if x["slug"] == slug)
        print(f"added {a.kind} {slug} {e['version']} ({e['file']})")
    print(f"{len(added_slugs)} added, {len(a.slugs) - len(added_slugs)} already present")


if __name__ == "__main__":
    main()
