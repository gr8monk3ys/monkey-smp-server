"""Manifest entries: the one place that knows their shape, where they come from and what is valid.

Kinds of artifact: "java" (the Temurin JRE), "server" (the Paper jar or the Fabric server launcher),
"plugin", "mod" and "datapack". Every entry has `file`, `url`, `size` and `hashes`; Modrinth entries
(plugins, mods, datapacks) add `slug`, `project_id`, `version` and `version_id`; a mod or datapack
may add a `patch` (owned by patches.py).

Server types (manifest["server"]["type"]) and the groups they may use (GROUPS_BY_TYPE):
  - paper:  {"type", "build", file, url, size, hashes}; plugins + datapacks, `mods` must be empty.
  - fabric: {"type", "loader", "installer", file, url, size, hashes}; mods + datapacks, `plugins`
            must be empty. The url is Fabric meta's launcher jar for (minecraft, loader, installer).
A 1.x manifest has no `mods` group; readers treat it as [] (with_all_groups adds it on load).

The rule for `file`: it is the artifact's name on the host's disk, and upstream names it unless
that name is already established and something depends on it.
  - java:     the upstream archive name (the installer unpacks it, so the name only labels it).
  - server:   Paper's file name for the build, or Fabric meta's name for the launcher jar (the
              installer saves it under a fixed name regardless).
  - plugin, mod:
              a snapshot records the name it found in plugins/ or mods/; an update takes the
              upstream file name (the install removes the old jar as a managed file).
  - datapack: a snapshot records the name it found in <level>/datapacks/; an update KEEPS it,
              because the world's level.dat refers to datapacks by file name.
In short: snapshots record what is on disk, updates take upstream's name except where the name is
sticky (STICKY_NAMES).

Built from upstream responses with: from_disk (snapshot), updated (update check), added (add.py),
paper, fabric, java. Checked with: check (one entry), check_types (server type vs groups).
Hash choice: hash_of, matches.
"""
import hashlib
import os
import re

from upstream import fabric_server_jar_url

KINDS = ("java", "server", "plugin", "mod", "datapack")
GROUPS = {"plugin": "plugins", "mod": "mods", "datapack": "datapacks"}
STICKY_NAMES = {"datapack"}
PATCHABLE = ("mod", "datapack")
SERVER_TYPES = ("paper", "fabric")
GROUPS_BY_TYPE = {"paper": ("plugins", "datapacks"), "fabric": ("mods", "datapacks")}

HEX = {"sha1": 40, "sha256": 64, "sha512": 128}
ALLOWED_HOSTS = ("https://cdn.modrinth.com/", "https://fill-data.papermc.io/", "https://meta.fabricmc.net/",
                 "https://github.com/adoptium/")


def group(manifest: dict, kind: str) -> list[dict]:
    """The entries of one Modrinth kind ("plugin", "mod", "datapack"); a missing group is empty."""
    return manifest.get(GROUPS[kind]) or []


def with_all_groups(manifest: dict) -> dict:
    """The manifest with every group present (a 1.x manifest gets "mods": [] after "plugins")."""
    if all(g in manifest for g in GROUPS.values()):
        return manifest
    out = {}
    for key, value in manifest.items():
        out[key] = value
        if key == "plugins":
            out.setdefault("mods", [])
    for g in GROUPS.values():
        out.setdefault(g, [])
    return out


def kind_allowed(server_type: str, kind: str) -> bool:
    """Whether a server of this type runs this kind of Modrinth artifact."""
    return GROUPS[kind] in GROUPS_BY_TYPE.get(server_type, ())


def artifacts(manifest: dict):
    """Every downloadable file in the manifest as (kind, entry)."""
    yield "java", manifest["java"]
    yield "server", manifest["server"]
    for kind in GROUPS:
        for entry in group(manifest, kind):
            yield kind, entry


# --- building entries from upstream responses ---------------------------------------------------

def from_disk(version: dict, sha1: str, slug: str, *, disk_name: str, patch: dict | None = None) -> dict:
    """Entry for a plugin/mod/datapack a snapshot found on disk, matched to a Modrinth version by SHA-1."""
    f = next(x for x in version["files"] if x["hashes"]["sha1"] == sha1)
    return _modrinth(version, f, slug=slug, project_id=version["project_id"], file=disk_name, patch=patch)


def updated(kind: str, entry: dict, version: dict) -> dict:
    """`entry` moved to a newer Modrinth version, naming the file by the rule above.

    A patched mod or datapack can't be updated this way: its patch was made against the old file
    (ADR-0004), so that raises ValueError. Re-make the patch with a snapshot instead.
    """
    if "patch" in entry:
        raise ValueError(f"{entry['slug']} is patched; re-snapshot it to update (ADR-0004)")
    f = pick_file(version, entry["file"])
    name = entry["file"] if kind in STICKY_NAMES else f["filename"]
    return _modrinth(version, f, slug=entry["slug"], project_id=entry["project_id"], file=name)


def added(kind: str, slug: str, version: dict) -> dict:
    """Entry for a plugin/mod/datapack being added to the manifest: upstream names the file."""
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


def fabric_server_file(mc: str, loader: str, installer: str) -> str:
    """Fabric meta's own name for the launcher jar (what its Content-Disposition says)."""
    return f"fabric-server-mc.{mc}-loader.{loader}-launcher.{installer}.jar"


def fabric(mc: str, loader: str, installer: str, jar: bytes) -> dict:
    """Server entry for Fabric meta's launcher jar, pinned to the bytes downloaded from it."""
    return {"type": "fabric", "loader": loader, "installer": installer,
            "file": fabric_server_file(mc, loader, installer), "url": fabric_server_jar_url(mc, loader, installer),
            "size": len(jar), "hashes": {"sha256": hashlib.sha256(jar).hexdigest()}}


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
    if kind == "server":
        errors += _check_server_keys(e)
    if errors:
        return errors
    if not e["url"].startswith(ALLOWED_HOSTS):
        errors.append(f"{kind} {e['file']}: url is not from an allowed host: {e['url']}")
    if re.search(r'[\\/:*?"<>|]', e["file"]):
        errors.append(f"{kind} {e['file']}: file name has characters Windows can't use")
    if not isinstance(e["size"], int) or e["size"] <= 0:
        errors.append(f"{kind} {e['file']}: bad size")
    if "patch" in e and kind not in PATCHABLE:
        errors.append(f"{kind} {e['file']}: only mods and datapacks can be patched")
    try:
        algo, value = hash_of(e)
        if not isinstance(value, str) or not re.fullmatch(rf"[0-9a-f]{{{HEX[algo]}}}", value):
            errors.append(f"{kind} {e['file']}: {algo} is not {HEX[algo]} lowercase hex chars")
    except KeyError as err:
        errors.append(str(err.args[0]))
    return errors


def _check_server_keys(e: dict) -> list[str]:
    name = f"server {e.get('file', '?')}"
    if e.get("type") not in SERVER_TYPES:
        return [f"{name}: type must be one of {', '.join(SERVER_TYPES)}, not {e.get('type')!r}"]
    if e["type"] == "paper":
        return [] if isinstance(e.get("build"), int) else [f"{name}: a paper server needs an integer 'build'"]
    return [f"{name}: a fabric server needs '{key}' (a version string)"
            for key in ("loader", "installer") if not isinstance(e.get(key), str) or not e.get(key)]


def check_types(manifest: dict) -> list[str]:
    """Problems with the server type against the rest of the manifest (as error strings).

    A Paper server runs no mods and a Fabric server no plugins, and a Fabric launcher must be the
    one Fabric meta serves for the manifest's Minecraft version and the entry's loader/installer.
    """
    server = manifest["server"]
    server_type = server.get("type")
    if server_type not in SERVER_TYPES:
        return []  # reported by check("server", ...)
    errors = [f"{GROUPS[kind]}: a {server_type} server can't use {GROUPS[kind]} "
              f"({len(group(manifest, kind))} listed)"
              for kind in GROUPS if group(manifest, kind) and not kind_allowed(server_type, kind)]
    if server_type == "fabric" and not _check_server_keys(server):
        mc, loader, installer = manifest["minecraft"], server["loader"], server["installer"]
        url = fabric_server_jar_url(mc, loader, installer)
        if server.get("url") != url:
            errors.append(f"server: url must be {url} "
                          f"(Fabric meta's launcher for Minecraft {mc}, loader {loader}, installer {installer})")
        if server.get("file") != fabric_server_file(mc, loader, installer):
            errors.append(f"server: file must be {fabric_server_file(mc, loader, installer)}")
    return errors
