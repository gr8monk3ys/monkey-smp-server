"""Switch the manifest from Fabric to Paper for the relaunch, pinned to the platform plugin stack.

  python tools/relaunch.py --mc 26.3                          rewrite manifest.json; stop if anything can't be pinned
  python tools/relaunch.py --mc 26.3 --skip-missing --report pins.md
                                                              pin what can be pinned, list the rest in pins.md

The stack is STACK below, the same list as docs/relaunch/plugin-stack.md (keep the two in step). A plugin
added later can go in STACK (and the run repeated) or be added on its own with tools/add.py.

What it writes: the Minecraft version, the newest STABLE Paper build for it, and each plugin's newest build for
that version on the channels entries.channels() allows (Modrinth "release", plus "beta" for Geyser), and
Floodgate's newest build from GeyserMC's own download API, the one place its Paper jar is published.
It empties `mods` (Paper runs none) and `datapacks` (the one pinned data pack only fitted the Fabric
world generation; our own packs ship in package/monkey/datapacks and aren't in the manifest). Java, the world
settings and the package version stay as they are.

The report lists, per plugin, the version and channel pinned and any required dependency that is not in the
manifest, so a missing library shows up before a boot test does.

Needs internet (Modrinth, PaperMC and GeyserMC). Afterwards: validate.py --online, then the boot test.
"""
import argparse
import sys

import entries
from check_updates import LOADERS
from repo import REPO
from upstream import LiveHttp, Upstream

# Every plugin of the relaunch (docs/relaunch/plugin-stack.md), by Modrinth slug: the platform's own first, then
# the ones other workstreams chose, so one run pins every jar.
STACK = (
    "geyser",                         # Bedrock players (Floodgate comes from GeyserMC, see GEYSERMC_STACK)
    "luckperms",                      # permissions and groups
    "essentialsx", "essentialsx-spawn",  # commands, homes, warps, kits and the Vault economy provider
    "lpc-chat",                       # chat format from LuckPerms prefixes and PlaceholderAPI (tags)
    "vaultunlocked",                  # the Vault API that economy, shop and store plugins talk to
    "grimac",                         # anti-cheat
    "chunky",                         # world pre-generation
    "worldedit", "worldguard",        # spawn and safe-zone regions
    "griefprevention",                # player land claims
    "placeholderapi",                 # placeholders for chat, tab, scoreboards and the store
    "viaversion", "viabackwards",     # Java clients a version ahead or behind the server
    "bluemap",                        # the web map (spawn only, no player or claim markers)
    "lifestealz", "pvpmanager",       # rules and seasons: hearts, combat tag, newbie protection
    "economyshopgui",                 # economy: the shop (the auction house is still open: none on Modrinth fits)
    "tebex", "ultracosmetics", "deluxetags",  # store: checkout, cosmetics and the /tags picker
)
# Plugins pinned from GeyserMC's download API rather than Modrinth (entries.GEYSERMC_PINS, ADR-0010).
GEYSERMC_STACK = ("floodgate",)


def pin_paper(manifest: dict, mc: str, upstream: Upstream) -> dict:
    build = upstream.newest_stable_paper_build(mc)
    if not build:
        raise SystemExit(f"PaperMC has no STABLE build for Minecraft {mc}")
    out = entries.with_all_groups(dict(manifest))
    out.update(minecraft=mc, server=entries.paper(build), plugins=[], mods=[], datapacks=[])
    return out


def pin_stack(manifest: dict, slugs, upstream: Upstream) -> tuple[dict, list[dict]]:
    """The manifest with each plugin added, and one report row per slug (in `slugs` order)."""
    mc = manifest["minecraft"]
    projects = {p["slug"]: p for p in upstream.modrinth_projects(slugs).values()}
    rows, plugins, deps = [], [], {}
    for slug in slugs:
        p = projects.get(slug)
        if not p:
            rows.append({"slug": slug, "problem": "not on Modrinth under this slug"})
            continue
        allowed = entries.channels(slug)
        v = upstream.newest(p["id"], mc, LOADERS["plugin"], allowed)
        if not v:
            rows.append({"slug": slug, "problem": f"no {'/'.join(allowed)} build for Paper {mc}"})
            continue
        plugins.append(entries.added("plugin", slug, v))
        deps[slug] = [d["project_id"] for d in v.get("dependencies") or []
                      if d.get("dependency_type") == "required" and d.get("project_id")]
        rows.append({"slug": slug, "version": v["version_number"], "channel": v["version_type"]})
    pinned_ids = {e["project_id"] for e in plugins}
    unknown = sorted({pid for ids in deps.values() for pid in ids if pid not in pinned_ids})
    names = {pid: p["slug"] for pid, p in upstream.modrinth_projects(unknown).items()} if unknown else {}
    for row in rows:
        missing = [names.get(pid, pid) for pid in deps.get(row["slug"], []) if pid not in pinned_ids]
        if missing:
            row["needs"] = missing
    out = dict(manifest)
    out["plugins"] = sorted(plugins, key=lambda e: e["slug"])
    return out, rows


def pin_geysermc(manifest: dict, projects, upstream: Upstream) -> tuple[dict, list[dict]]:
    """The manifest with each GeyserMC project's newest build added, and one report row per project."""
    plugins, rows = list(manifest["plugins"]), []
    for project in projects:
        build = upstream.geysermc_latest_build(project)
        url = entries.geysermc_url(project, build["version"], build["build"])
        plugins.append(entries.geysermc(project, build, upstream.download(url)))
        rows.append({"slug": project, "version": f"{build['version']} b{build['build']}", "channel": "GeyserMC"})
    return {**manifest, "plugins": sorted(plugins, key=lambda e: e["slug"])}, rows


def report(manifest: dict, rows: list[dict]) -> str:
    s = manifest["server"]
    lines = [f"# Relaunch pins: Paper {manifest['minecraft']} build {s['build']}", "",
             "| Plugin | Pinned | Channel | Needs (not pinned) |", "|---|---|---|---|"]
    for r in rows:
        if "problem" in r:
            lines.append(f"| {r['slug']} | **not pinned:** {r['problem']} | | |")
        else:
            lines.append(f"| {r['slug']} | {r['version']} | {r['channel']} | {', '.join(r.get('needs', []))} |")
    return "\n".join(lines) + "\n"


def main(argv=None, repo=REPO, upstream=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mc", required=True, help="the Minecraft version to run, e.g. 26.3")
    ap.add_argument("--skip-missing", action="store_true", help="write the manifest even if a plugin can't be pinned")
    ap.add_argument("--report", help="also write the report to this file")
    a = ap.parse_args(argv)
    upstream = upstream or Upstream(LiveHttp())
    manifest, rows = pin_stack(pin_paper(repo.load_manifest(), a.mc, upstream), STACK, upstream)
    manifest, geyser_rows = pin_geysermc(manifest, GEYSERMC_STACK, upstream)
    rows += geyser_rows
    text = report(manifest, rows)
    print(text)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write(text)
    missing = [r["slug"] for r in rows if "problem" in r]
    if missing and not a.skip_missing:
        print(f"not written: {', '.join(missing)} can't be pinned (--skip-missing writes the rest)", file=sys.stderr)
        return 1
    repo.save_manifest(manifest)
    print(f"manifest.json: Paper build {manifest['server']['build']}, {len(manifest['plugins'])} plugins")
    return 0


if __name__ == "__main__":
    sys.exit(main())
