"""Manifest entries: the one place that knows their shape, where they come from and what is valid.

Kinds of artifact: "java" (the Temurin JRE), "server" (the Paper jar), "plugin" and "datapack".
Every entry has `file`, `url`, `size` and `hashes`; Modrinth entries add `slug`, `project_id`,
`version` and `version_id`; a datapack may add a `patch` (owned by patches.py).

The rule for `file`: it is the artifact's name on the host's disk, and upstream names it unless
that name is already established and something depends on it.
  - java:     the upstream archive name (the installer unpacks it, so the name only labels it).
  - server:   Paper's file name for the build (the installer saves it as paper.jar regardless).
  - plugin:   a snapshot records the name it found in plugins/; an update takes the upstream
              file name (the install removes the old jar as a managed file).
  - datapack: a snapshot records the name it found in <level>/datapacks/; an update KEEPS it,
              because the world's level.dat refers to datapacks by file name.
In short: snapshots record what is on disk, updates take upstream's name except where the name is
sticky (STICKY_NAMES).

Built from upstream responses with: from_disk (snapshot), updated (update check), paper, java.
Checked with: check. Hash choice: hash_of, matches.
"""
import hashlib
import os
import re

KINDS = ("java", "server", "plugin", "datapack")
GROUPS = {"plugin": "plugins", "datapack": "datapacks"}
STICKY_NAMES = {"datapack"}

HEX = {"sha1": 40, "sha256": 64, "sha512": 128}
ALLOWED_HOSTS = ("https://cdn.modrinth.com/", "https://fill-data.papermc.io/", "https://github.com/adoptium/")


def artifacts(manifest: dict):
    """Every downloadable file in the manifest as (kind, entry)."""
    yield "java", manifest["java"]
    yield "server", manifest["server"]
    for kind, group in GROUPS.items():
        for entry in manifest[group]:
            yield kind, entry


# --- building entries from upstream responses ---------------------------------------------------

def from_disk(version: dict, sha1: str, slug: str, *, disk_name: str, patch: dict | None = None) -> dict:
    """Entry for a plugin/datapack a snapshot found on disk, matched to a Modrinth version by SHA-1."""
    f = next(x for x in version["files"] if x["hashes"]["sha1"] == sha1)
    return _modrinth(version, f, slug=slug, project_id=version["project_id"], file=disk_name, patch=patch)


def updated(kind: str, entry: dict, version: dict) -> dict:
    """`entry` moved to a newer Modrinth version, naming the file by the rule above.

    A patched datapack can't be updated this way: its patch was made against the old file
    (ADR-0004), so that raises ValueError. Re-make the patch with a snapshot instead.
    """
    if "patch" in entry:
        raise ValueError(f"{entry['slug']} is patched; re-snapshot it to update (ADR-0004)")
    f = pick_file(version, entry["file"])
    name = entry["file"] if kind in STICKY_NAMES else f["filename"]
    return _modrinth(version, f, slug=entry["slug"], project_id=entry["project_id"], file=name)


def added(kind: str, slug: str, version: dict) -> dict:
    """Entry for a plugin/datapack being added to the manifest: upstream names the file."""
    f = pick_file(version, ".zip" if kind == "datapack" else ".jar")
    return _modrinth(version, f, slug=slug, project_id=version["project_id"], file=f["filename"])


def pick_file(version: dict, like: str) -> dict:
    """The file of a Modrinth version that replaces `like`: same extension, primary first."""
    files = version["files"]
    jar_or_zip = [f for f in files if f["filename"].endswith((".jar", ".zip"))] or files
    ext = os.path.splitext(like)[1]
    same_ext = [f for f in jar_or_zip if os.path.splitext(f["filename"])[1] == ext]
    return next((f for f in same_ext if f.get("primary")), (same_ext or jar_or_zip)[0])


def paper(build: dict) -> dict:
    d = build["downloads"]["server:default"]
    return {"type": "paper", "build": build["id"], "file": d["name"], "url": d["url"], "size": d["size"],
            "hashes": {"sha256": d["checksums"]["sha256"]}}


def java(asset: dict) -> dict:
    p = asset["binary"]["package"]
    return {"vendor": "Eclipse Temurin JRE", "version": asset["release_name"], "file": p["name"],
            "url": p["link"], "size": p["size"], "hashes": {"sha256": p["checksum"]}}


def _modrinth(version, f, *, slug, project_id, file, patch=None):
    entry = {"slug": slug, "project_id": project_id, "version": version["version_number"],
             "version_id": version["id"], "file": file, "url": f["url"], "size": f["size"],
             "hashes": {"sha512": f["hashes"]["sha512"]}}
    if patch is not None:
        entry["patch"] = patch
    return entry


# --- hashes -------------------------------------------------------------------------------------

def hash_of(entry: dict) -> tuple[str, str]:
    """(algorithm, hex) of the strongest hash an entry carries."""
    for algo in ("sha512", "sha256"):
        if algo in entry.get("hashes", {}):
            return algo, entry["hashes"][algo]
    raise KeyError(f"{entry.get('file', '?')} has no sha512/sha256")


def matches(entry: dict, data: bytes) -> bool:
    """Whether downloaded bytes are exactly the pinned artifact (size and strongest hash)."""
    algo, value = hash_of(entry)
    return len(data) == entry["size"] and hashlib.new(algo, data).hexdigest() == value


# --- validation ---------------------------------------------------------------------------------

def check(kind: str, e: dict) -> list[str]:
    """Problems with one entry on its own (as error strings; empty means fine)."""
    errors = [f"{kind} {e.get('file', '?')}: missing '{key}'" for key in ("file", "url", "size", "hashes")
              if key not in e]
    if kind in GROUPS:
        errors += [f"{kind} {e.get('file', '?')}: missing '{key}'"
                   for key in ("slug", "project_id", "version", "version_id") if key not in e]
    if errors:
        return errors
    if not e["url"].startswith(ALLOWED_HOSTS):
        errors.append(f"{kind} {e['file']}: url is not from an allowed host: {e['url']}")
    if re.search(r'[\\/:*?"<>|]', e["file"]):
        errors.append(f"{kind} {e['file']}: file name has characters Windows can't use")
    if not isinstance(e["size"], int) or e["size"] <= 0:
        errors.append(f"{kind} {e['file']}: bad size")
    if "patch" in e and kind != "datapack":
        errors.append(f"{kind} {e['file']}: only datapacks can be patched")
    try:
        algo, value = hash_of(e)
        if not isinstance(value, str) or not re.fullmatch(rf"[0-9a-f]{{{HEX[algo]}}}", value):
            errors.append(f"{kind} {e['file']}: {algo} is not {HEX[algo]} lowercase hex chars")
    except KeyError as err:
        errors.append(str(err.args[0]))
    return errors
