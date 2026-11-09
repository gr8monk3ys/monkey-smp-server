"""Bring the players' pack (and the server's pins) in line with the owner's mod changes on the staff panel.

  python tools/pack_sync.py --ssh monkey-vps              read the list over SSH, change the two files
  python tools/pack_sync.py --ssh monkey-vps --dry-run    only say what would change
  python tools/pack_sync.py --file changes.json --pr      read a copy; open a draft pull request after

The staff panel writes server/.monkey-pack-changes.json on the VPS after each owner mod change that players
need in their pack too (tools/staff_host.py, "pack_waiting"; the Mods tab lists it as "Players' pack: waiting
for a release"). This tool reads that file (read only: `ssh HOST cat FILE`) and, for each line:

- add: finds the jar's Modrinth version by its sha512 and pins that exact file in client/modrinth.index.json
  and package/monkey/manifest.json, in place of any other version of the same project. A jar that isn't on
  Modrinth, a version for another game version or loader, a version with more than one jar (a split client
  and server jar), or a patched manifest entry (ADR-0004) is refused: change those by hand.
- remove: drops the project from both files. A mod that is only turned off on the server is left alone
  unless you pass --include-off: a short "off" to find a bug shouldn't take a mod out of players' packs.

Then it runs tools/validate.py and, when the pack gained or lost a mod, re-records
tests/fixtures/client_mods.json (tests/test_client_env.py). With --pr it commits the changes on a new branch,
pushes it and opens a draft pull request; it never pushes to main.

Nothing reaches players until the owner merges that pull request and tags a release (release.yml builds the
.mrpack and publishes it on GitHub and Modrinth): that stays the owner's step. No repo or Modrinth key goes on
the VPS. The panel's line goes by itself once the deployed release's pack matches the server.
"""
import argparse
import datetime
import json
import re
import subprocess
import sys

import client_env
import entries
from repo import REPO, load_json, save_json
from upstream import LiveHttp, Upstream

REMOTE = "/srv/monkey/MonkeySMP-Server/server/.monkey-pack-changes.json"
SAFE_PATH = re.compile(r"/[A-Za-z0-9/._-]+")      # passed to the remote shell as one word
SAFE_HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9@._-]*")
SHA512 = re.compile(r"[0-9a-f]{128}")
PROJECT = re.compile(r"[A-Za-z0-9]{8}")
LOADER = "fabric"
FIXTURE = "tests/fixtures/client_mods.json"


def read_changes(text: str) -> list[dict]:
    """The lines of the panel's file, only those this tool can act on."""
    try:
        rows = json.loads(text).get("changes")
    except (ValueError, AttributeError):
        raise SystemExit("the panel's list is not the JSON the staff panel writes") from None
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict) and isinstance(r.get("file"), str)
            and r.get("action") in ("add", "remove")]


def fetch(a, run) -> str:
    if a.file:
        with open(a.file, encoding="utf-8") as f:
            return f.read()
    if not SAFE_HOST.fullmatch(a.ssh) or not SAFE_PATH.fullmatch(a.path):
        raise SystemExit("--ssh takes a host or user@host, --path an absolute path of plain characters")
    done = run(["ssh", a.ssh, "cat", "--", a.path], capture_output=True, text=True)
    if done.returncode != 0:
        if "No such file" in (done.stderr or ""):
            return '{"changes": []}'                 # the panel writes it only once there is something to say
        raise SystemExit(f"ssh {a.ssh} failed: {(done.stderr or '').strip() or done.returncode}")
    return done.stdout


def _client_entry(f: dict) -> dict:
    path = f"mods/{f['filename']}"
    return {"path": path, "hashes": {"sha1": f["hashes"]["sha1"], "sha512": f["hashes"]["sha512"]},
            "env": client_env.env({"path": path, "downloads": [f["url"]]}),
            "downloads": [f["url"]], "fileSize": f["size"]}


def _in_project(f: dict, project: str) -> bool:
    return f["path"].startswith("mods/") and client_env.project_id(f) == project


def _sorted_files(files: list[dict]) -> list[dict]:
    """mods/ first, by path ignoring case (as the index is kept), then everything else in its order."""
    mods = sorted((f for f in files if f["path"].startswith("mods/")), key=lambda f: f["path"].lower())
    return mods + [f for f in files if not f["path"].startswith("mods/")]


def plan(changes: list[dict], include_off: bool) -> tuple[list[dict], list[str]]:
    """(lines to act on, what is left alone and why)."""
    todo, skipped = [], []
    for c in changes:
        if c["action"] == "add" and not SHA512.fullmatch(str(c.get("sha512", ""))):
            skipped.append(f"{c['file']}: no sha512 in the panel's line (is the jar still on the server?)")
        elif c["action"] == "remove" and not PROJECT.fullmatch(str(c.get("project", ""))):
            skipped.append(f"{c['file']}: no Modrinth project in the panel's line: take it out by hand")
        elif c["action"] == "remove" and c.get("how") == "off" and not include_off:
            skipped.append(f"{c['file']}: only turned off on the server; pass --include-off to take it out "
                           "of the players' pack")
        else:
            todo.append(c)
    return todo, skipped


def apply(index: dict, manifest: dict, todo: list[dict], upstream: Upstream) -> tuple[dict, dict, list[str], list[str]]:
    """Copies of the client index and the manifest with the changes made, what was done, and what was refused.
    A refused line changes nothing; the others still go ahead."""
    files = list(index["files"])
    mods = list(entries.group(manifest, "mod"))
    done, refused = [], []
    adds = [c for c in todo if c["action"] == "add"]
    found = upstream.modrinth_versions_by_sha512([c["sha512"] for c in adds])
    projects = upstream.modrinth_projects({v["project_id"] for v in found.values()})
    for c in todo:
        name = c["file"]
        if c["action"] == "remove":
            project = c["project"]
            if any(e.get("project_id") == project and "patch" in e for e in mods):
                refused.append(f"{name}: its manifest entry is patched (ADR-0004): take it out by hand")
                continue
            before = len(files) + len(mods)
            files = [f for f in files if not _in_project(f, project)]
            mods = [e for e in mods if e.get("project_id") != project]
            if before == len(files) + len(mods):    # the panel keeps its line until the release is deployed
                done.append(f"already out: {name} (project {project}) is in neither the pack nor the manifest")
            else:
                done.append(f"removed {name} (project {project})")
            continue
        version = found.get(c["sha512"])
        if version is None:
            refused.append(f"{name}: Modrinth doesn't know this jar, so the pack can't link to it: add it by hand")
            continue
        if manifest["minecraft"] not in version.get("game_versions", []) or LOADER not in version.get("loaders", []):
            refused.append(f"{name}: Modrinth's version {version['version_number']} is not for Fabric "
                           f"{manifest['minecraft']}")
            continue
        jars = [f for f in version["files"] if f["filename"].endswith(".jar")]
        f = next((x for x in jars if x["hashes"].get("sha512") == c["sha512"]), None)
        if f is None or len(jars) > 1:
            refused.append(f"{name}: Modrinth's version {version['version_number']} has {len(jars)} jars "
                           "(a split client and server jar?): pick the players' file by hand")
            continue
        project = version["project_id"]
        old = [e for e in mods if e.get("project_id") == project]
        if any("patch" in e for e in old):
            refused.append(f"{name}: its manifest entry is patched (ADR-0004): re-snapshot it by hand")
            continue
        slug = old[0]["slug"] if old else projects.get(project, {}).get("slug")
        if not slug:
            refused.append(f"{name}: Modrinth didn't say which project {project} is")
            continue
        entry = entries.from_disk(version, f["hashes"]["sha1"], slug, disk_name=f["filename"])
        mods = [e for e in mods if e.get("project_id") != project] + [entry]
        files = [x for x in files if not _in_project(x, project)] + [_client_entry(f)]
        done.append(f"added {name} as {slug} {version['version_number']} ({f['filename']})")
    new_manifest = entries.with_all_groups(dict(manifest))
    new_manifest["mods"] = sorted(mods, key=lambda e: e["slug"])
    return {**index, "files": _sorted_files(files)}, new_manifest, done, refused


def projects_in(index: dict) -> set:
    return {client_env.project_id(f) for f in index["files"] if f["path"].startswith("mods/")}


def open_pr(repo, run, done: list[str], skipped: list[str]) -> None:
    branch = f"pack-sync/{datetime.datetime.now(datetime.UTC):%Y%m%d-%H%M%S}"
    paths = ["client/modrinth.index.json", "package/monkey/manifest.json", FIXTURE]
    body = ("The owner's mod changes on the staff panel, for the players' pack and the server's pins "
            "(`python tools/pack_sync.py`).\n\n" + "\n".join(f"- {d}" for d in done)
            + ("\n\nLeft alone:\n" + "\n".join(f"- {s}" for s in skipped) if skipped else "")
            + "\n\nPlayers get it only once this is merged and a release is tagged (that publishes on Modrinth).")
    for cmd in (["git", "switch", "-c", branch], ["git", "add", "--", *paths],
                ["git", "commit", "-m", "Players' pack: follow the panel's mod changes", "-m", "\n".join(done)],
                ["git", "push", "-u", "origin", branch],
                ["gh", "pr", "create", "--draft", "--title", "Players' pack: follow the panel's mod changes",
                 "--body", body]):
        if run(cmd, cwd=repo.root).returncode != 0:
            raise SystemExit(f"stopped at: {' '.join(cmd[:3])} (the files are changed; finish by hand)")


def main(argv=None, repo=REPO, upstream=None, run=subprocess.run) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--ssh", metavar="HOST", help="read the panel's list on this SSH host (your existing login)")
    src.add_argument("--file", help="read a copy of the panel's list instead")
    ap.add_argument("--path", default=REMOTE, help=f"the list on the host (default {REMOTE})")
    ap.add_argument("--include-off", action="store_true", help="also take out mods that are only turned off")
    ap.add_argument("--dry-run", action="store_true", help="say what would change; write nothing")
    ap.add_argument("--pr", action="store_true", help="commit on a new branch and open a draft pull request")
    a = ap.parse_args(argv)

    todo, skipped = plan(read_changes(fetch(a, run)), a.include_off)
    for s in skipped:
        print("left alone:", s)
    if not todo:
        print("nothing for the players' pack to change")
        return 0
    index_path = repo.client / "modrinth.index.json"
    index, manifest = load_json(index_path), repo.load_manifest()
    new_index, new_manifest, done, refused = apply(index, manifest, todo, upstream or Upstream(LiveHttp()))
    for r in refused:
        print("refused:", r)
    for d in done:
        print(("would have " if a.dry_run and not d.startswith("already") else "") + d)
    if not done or a.dry_run:
        return 1 if refused else 0
    if new_index == index and new_manifest == manifest:
        print("the pack and the manifest have these changes already: merge and release them")
        return 1 if refused else 0
    save_json(index_path, new_index)
    repo.save_manifest(new_manifest)
    python = sys.executable
    if run([python, "tools/validate.py"], cwd=repo.root).returncode != 0:
        print("validate.py found problems: fix them before a pull request (git diff shows the change)")
        return 1
    if projects_in(new_index) != projects_in(index) and \
            run([python, "-I", "tests/fixtures/record_client_mods.py"], cwd=repo.root).returncode != 0:
        print(f"couldn't re-record {FIXTURE}: run `python -I tests/fixtures/record_client_mods.py` before a PR")
        return 1
    if a.pr:
        open_pr(repo, run, done, skipped + refused)
    else:
        print("changed client/modrinth.index.json and package/monkey/manifest.json: look over `git diff`, "
              "then open a pull request (or run again with --pr)")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
