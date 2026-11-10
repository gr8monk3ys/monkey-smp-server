"""Manifest entries: the one place that knows their shape, where they come from and what is valid.

Kinds of artifact: "java" (a Temurin JRE build), "server" (the Paper jar or the Fabric server launcher),
"plugin", "mod" and "datapack". Every entry has `file`, `url`, `size` and `hashes`; Modrinth entries
(plugins, mods, datapacks) add `slug`, `project_id`, `version` and `version_id`; a mod or datapack
may add a `patch` (owned by patches.py).

A GitHub pin (ADR-0009) is a mod that is not on Modrinth, pinned to one asset of one release of a
repository in GITHUB_PINS. It has `slug`, `github` ("owner/repo"), `tag` and `version` instead of the
Modrinth ids, and its `url` must be exactly that release's download URL for `file` (github_url). It
is pinned and moved by hand with pin_github.py (github builds the entry); is_github tells the update
check, add.py and the snapshots to leave it alone.

Server types (manifest["server"]["type"]) and the groups they may use (GROUPS_BY_TYPE):
  - paper:  {"type", "build", file, url, size, hashes}; plugins + datapacks, `mods` must be empty.
  - fabric: {"type", "loader", "installer", file, url, size, hashes}; mods + datapacks, `plugins`
            must be empty. The url is Fabric meta's launcher jar for (minecraft, loader, installer).
A 1.x manifest has no `mods` group; readers treat it as [] (with_all_groups adds it on load).

Java (manifest["java"]): {"vendor", "version" (Adoptium's release name, e.g. jdk-25.0.4.1+1), "builds"},
where builds maps every platform of JAVA_PLATFORMS to an entry (file, url, size, hashes) of that one
release: a .zip for Windows, a .tar.gz elsewhere. Manifests before JAVA_BUILDS_SINCE (2.3.0) pinned
only the Windows build, as file/url/size/hashes directly on "java"; java_builds reads both shapes.

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
github (pin_github.py), paper, fabric, java. Checked with: check (one entry), check_types (server type vs groups),
check_java (the Java builds).
Hash choice: hash_of, matches.
"""
import hashlib
import os
import re
import urllib.parse

from upstream import JAVA_PLATFORMS, fabric_server_jar_url

KINDS = ("java", "server", "plugin", "mod", "datapack")
GROUPS = {"plugin": "plugins", "mod": "mods", "datapack": "datapacks"}
STICKY_NAMES = {"datapack"}
PATCHABLE = ("mod", "datapack")
SERVER_TYPES = ("paper", "fabric")
GROUPS_BY_TYPE = {"paper": ("plugins", "datapacks"), "fabric": ("mods", "datapacks")}
JAVA_BUILDS_SINCE = (2, 3, 0)

HEX = {"sha1": 40, "sha256": 64, "sha512": 128}
ALLOWED_HOSTS = ("https://cdn.modrinth.com/", "https://fill-data.papermc.io/", "https://meta.fabricmc.net/",
                 "https://github.com/adoptium/")
# The repositories ("owner/repo") a mod may be pinned from as a GitHub release asset (ADR-0009): the owner's own
# mods only. Adding one is a decision, not a routine edit.
GITHUB_PINS = ("gr8monk3ys/patina-and-chime",)
MODRINTH_KEYS = ("project_id", "version_id")


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


def java_builds(manifest: dict) -> list[tuple[str, dict]]:
    """(platform, entry) for every pinned Java build; an older manifest's single build is Windows x64."""
    java = manifest["java"]
    if "builds" not in java:
        return [("windows-x64", java)]
    builds = java["builds"] if isinstance(java["builds"], dict) else {}
    order = [p for p in JAVA_PLATFORMS if p in builds] + sorted(p for p in builds if p not in JAVA_PLATFORMS)
    return [(p, builds[p]) for p in order]


def artifacts(manifest: dict):
    """Every downloadable file in the manifest as (kind, entry)."""
    for _, build in java_builds(manifest):
        yield "java", build
    yield "server", manifest["server"]
    for kind in GROUPS:
        for entry in group(manifest, kind):
            yield kind, entry


def is_github(entry: dict) -> bool:
    """Whether a plugin/mod/datapack entry is a GitHub pin (ADR-0009) and so has no Modrinth ids."""
    return "github" in entry


def github_pin_of(client_file: dict, manifest: dict) -> dict | None:
    """The server's GitHub pin that a file of the client index is, byte for byte: the same jar name in mods/, the
    same one URL, size and sha512. None for anything else, so no other download from outside Modrinth passes."""
    for e in group(manifest, "mod"):
        if (is_github(e) and client_file["path"] == f"mods/{e.get('file')}"
                and client_file["downloads"] == [e.get("url")] and client_file.get("fileSize") == e.get("size")
                and isinstance(e.get("hashes"), dict) and e["hashes"].get("sha512")
                and client_file["hashes"].get("sha512") == e["hashes"]["sha512"]):
            return e
    return None


def github_url(repo: str, tag: str, file: str) -> str:
    """GitHub's download URL for one asset of one release (a '+' in the name is %2B, as GitHub writes it)."""
    quote = urllib.parse.quote
    return f"https://github.com/{repo}/releases/download/{quote(tag, safe='')}/{quote(file, safe='')}"


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
    if is_github(entry):
        raise ValueError(f"{entry['slug']} is pinned from GitHub; pin its new release by hand (ADR-0009)")
    f = pick_file(version, entry["file"])
    name = entry["file"] if kind in STICKY_NAMES else f["filename"]
    return _modrinth(version, f, slug=entry["slug"], project_id=entry["project_id"], file=name)


def added(kind: str, slug: str, version: dict) -> dict:
    """Entry for a plugin/mod/datapack being added to the manifest: upstream names the file."""
    f = pick_file(version, ".zip" if kind == "datapack" else ".jar")
    return _modrinth(version, f, slug=slug, project_id=version["project_id"], file=f["filename"])


def github(slug: str, repo: str, tag: str, version: str, file: str, jar: bytes) -> dict:
    """Entry for a mod pinned to one asset of a GitHub release (ADR-0009), from the bytes downloaded from it."""
    return {"slug": slug, "github": repo, "tag": tag, "version": version, "file": file,
            "url": github_url(repo, tag, file), "size": len(jar),
            "hashes": {"sha512": hashlib.sha512(jar).hexdigest()}}


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


def java_build(asset: dict) -> dict:
    """One build's entry, from an Adoptium asset (Upstream.adoptium_latest_jre / adoptium_release_jre)."""
    p = asset["binary"]["package"]
    return {"file": p["name"], "url": p["link"], "size": p["size"], "hashes": {"sha256": p["checksum"]}}


def java(assets: dict[str, dict]) -> dict:
    """manifest["java"] from one Adoptium asset per platform, which must all be the same release."""
    releases = {a["release_name"] for a in assets.values()}
    if len(releases) != 1:
        raise ValueError(f"the Java builds are from different releases: {', '.join(sorted(releases))}")
    return {"vendor": "Eclipse Temurin JRE", "version": releases.pop(),
            "builds": {p: java_build(assets[p]) for p in JAVA_PLATFORMS if p in assets}}


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
    github = kind in GROUPS and is_github(e)
    if kind in GROUPS:
        keys = ("slug", "github", "tag", "version") if github else ("slug", "project_id", "version", "version_id")
        errors += [f"{kind} {e.get('file', '?')}: missing '{key}'" for key in keys if key not in e]
    if kind == "server":
        errors += _check_server_keys(e)
    if errors:
        return errors
    if github:
        errors += _check_github(kind, e)
    elif not e["url"].startswith(ALLOWED_HOSTS):
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


def _check_github(kind: str, e: dict) -> list[str]:
    """Problems with a GitHub pin: only a mod, only from GITHUB_PINS, and only that release's own URL."""
    name = f"{kind} {e['file']}"
    if kind != "mod":
        return [f"{name}: only a mod can be pinned from a GitHub release (ADR-0009)"]
    if e["github"] not in GITHUB_PINS:
        return [f"{name}: {e['github']!r} is not a repository mods may be pinned from (ADR-0009)"]
    errors = [f"{name}: a GitHub pin can't also have '{key}'" for key in MODRINTH_KEYS if key in e]
    if not isinstance(e["tag"], str) or not e["tag"]:
        return errors + [f"{name}: 'tag' must be the release's tag"]
    url = github_url(e["github"], e["tag"], e["file"])
    if e["url"] != url:
        errors.append(f"{name}: url must be {url} (release {e['tag']} of {e['github']})")
    if "sha512" not in e["hashes"]:
        errors.append(f"{name}: a GitHub pin needs a sha512 (the players' pack is matched to it)")
    return errors


def check_java(manifest: dict) -> list[str]:
    """Problems with manifest["java"] as a whole (each build is also checked as a "java" artifact)."""
    java = manifest["java"]
    if not isinstance(java, dict):
        return ["java: must be an object"]
    if "builds" not in java:
        version = manifest.get("version", "")
        if re.fullmatch(r"\d+\.\d+\.\d+", version) and tuple(map(int, version.split("."))) >= JAVA_BUILDS_SINCE:
            return [f"java: needs 'builds' with a JRE for each of {', '.join(JAVA_PLATFORMS)} "
                    f"(from {'.'.join(map(str, JAVA_BUILDS_SINCE))})"]
        return []  # an older manifest: the one Windows build is checked as an artifact
    errors = [f"java: missing '{key}'" for key in ("vendor", "version") if not java.get(key)]
    builds = java["builds"]
    if not isinstance(builds, dict):
        return errors + ["java: 'builds' must be an object of platform -> build"]
    errors += [f"java: no build for {p}" for p in JAVA_PLATFORMS if p not in builds]
    errors += [f"java: unknown platform {p}" for p in builds if p not in JAVA_PLATFORMS]
    release = urllib.parse.quote(str(java.get("version", "")), safe="")
    for p, build in builds.items():
        if p not in JAVA_PLATFORMS or not isinstance(build, dict) or not {"file", "url"} <= set(build):
            continue
        os_, arch = JAVA_PLATFORMS[p]
        ext = ".zip" if os_ == "windows" else ".tar.gz"
        if not build["file"].endswith(ext) or f"_{arch}_{os_}_" not in build["file"]:
            errors.append(f"java {p}: {build['file']} is not the {arch} {os_} {ext} build")
        if build["url"].rsplit("/", 1)[-1] != build["file"]:
            errors.append(f"java {p}: url doesn't end in the file name {build['file']}")
        if f"/{release}/" not in build["url"]:
            errors.append(f"java {p}: url is not from release {java.get('version')}")
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
