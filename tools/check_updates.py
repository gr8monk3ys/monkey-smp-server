"""Find newer builds of Paper and of every plugin/datapack for the pinned Minecraft version.

  python tools/check_updates.py                 print a Markdown report
  python tools/check_updates.py --apply         also pin the newer builds in manifest.json
  python tools/check_updates.py --out report.md write the report to a file (used by CI)

Only stable releases for the same Minecraft version are considered. A patched datapack with a
newer release is reported but never pinned by --apply: its patch was made against the old file
(ADR-0004), so take it by re-making the patch with tools/snapshot.py. After --apply, run the smoke
test (tests/smoke.ps1) before releasing: plugin updates can change configs.
"""
import argparse
import copy
import os
from dataclasses import dataclass

import entries
from repo import REPO
from upstream import LiveHttp, Upstream

LOADERS = {"plugin": ["paper", "spigot", "bukkit", "purpur", "folia"], "datapack": ["datapack"]}
NEEDS_PATCH = "patched - re-snapshot needed"


@dataclass(frozen=True)
class Update:
    kind: str           # "server", "plugin" or "datapack"
    slug: str
    pinned: str
    newest: str
    entry: dict | None  # the new manifest entry, or None when it can't be pinned automatically
    note: str = ""


def find_updates(manifest: dict, upstream: Upstream) -> list[Update]:
    mc = manifest["minecraft"]
    updates = []
    build = upstream.newest_stable_paper_build(mc)
    if build and build["id"] > manifest["server"]["build"]:
        updates.append(Update("server", "paper", str(manifest["server"]["build"]), str(build["id"]),
                              entries.paper(build)))
    for kind, group in entries.GROUPS.items():
        for e in manifest[group]:
            v = upstream.newest_release(e["project_id"], mc, LOADERS[kind])
            if not v or v["id"] == e["version_id"]:
                continue
            if "patch" in e:
                updates.append(Update(kind, e["slug"], e["version"], v["version_number"], None, NEEDS_PATCH))
            else:
                updates.append(Update(kind, e["slug"], e["version"], v["version_number"],
                                      entries.updated(kind, e, v)))
    return updates


def report(manifest: dict, updates: list[Update]) -> str:
    lines = [f"Pinned: Minecraft {manifest['minecraft']}, manifest {manifest['version']}", ""]
    if not updates:
        return "\n".join(lines + ["Everything is on the newest stable build."])
    lines += ["| Kind | Project | Pinned | Newest | Note |", "|---|---|---|---|---|"]
    lines += [f"| {u.kind} | {u.slug} | {u.pinned} | {u.newest} | {u.note} |" for u in updates]
    lines += ["", "To take them: `python tools/check_updates.py --apply`, run the smoke test, bump the version, tag."]
    if any(u.entry is None for u in updates):
        lines += ["Patched datapacks are not pinned by `--apply`: update the pack on a server, re-apply the "
                  "edit, and run `python tools/snapshot.py server <folder>` to re-make the patch (ADR-0004)."]
    return "\n".join(lines)


def apply(manifest: dict, updates: list[Update]) -> dict:
    """A copy of the manifest with every pinnable update applied (patched datapacks are left alone)."""
    out = copy.deepcopy(manifest)
    for u in updates:
        if u.entry is None:
            continue
        if u.kind == "server":
            out["server"] = u.entry
        else:
            group = entries.GROUPS[u.kind]
            out[group] = [u.entry if e["slug"] == u.slug else e for e in out[group]]
    return out


def main(argv=None, repo=REPO, upstream=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    upstream = upstream or Upstream(LiveHttp())
    manifest = repo.load_manifest()
    updates = find_updates(manifest, upstream)
    text = report(manifest, updates)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    pinnable = [u for u in updates if u.entry is not None]
    if a.apply and pinnable:
        repo.save_manifest(apply(manifest, updates))
        print(f"\npinned {len(pinnable)} update(s) in manifest.json")
    if a.apply and len(pinnable) < len(updates):
        print(f"{len(updates) - len(pinnable)} patched datapack(s) left pinned; they need a fresh patch")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"count={len(updates)}\n")


if __name__ == "__main__":
    main()
