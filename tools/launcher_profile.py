"""The Fabric launcher profile the player installer adds to the official Minecraft Launcher.

client/fabric-profile.json is Fabric meta's launcher profile for the client pack's Minecraft and
Fabric loader versions (the "minecraft" and "fabric-loader" dependencies of client/modrinth.index.json),
as served at https://meta.fabricmc.net/v2/versions/loader/<mc>/<loader>/profile/json. It is stored
with the repo's JSON formatting (save_json), so compare profiles with `same`, never byte for byte.

Meta generates the profile on request: "time" and "releaseTime" are the generation time (cached for
up to a day), everything else is the same for the same two versions. `same` ignores those two keys.

  profile_id(mc, loader)          the id the launcher shows: fabric-loader-<loader>-<mc>
  check(profile, mc, loader)      what's wrong with a profile for these versions ([] if nothing)
  same(a, b)                      equal apart from the generation time
  save(path, profile)             write it, unless the file already holds the same profile
"""
import re
from pathlib import Path

from repo import load_json, save_json

VOLATILE = ("time", "releaseTime")
# Maven repositories a library may come from (a library's "url" is the repository's base URL).
LIBRARY_HOSTS = ("https://maven.fabricmc.net/", "https://libraries.minecraft.net/",
                 "https://repo1.maven.org/maven2/", "https://repo.maven.apache.org/maven2/")
HASH_LENGTHS = {"sha1": 40, "sha256": 64, "sha512": 128}


def profile_id(mc: str, loader: str) -> str:
    return f"fabric-loader-{loader}-{mc}"


def loader_library(loader: str) -> str:
    """The loader's own library. Meta lists it without hashes; the launcher fetches it from Fabric's maven."""
    return f"net.fabricmc:fabric-loader:{loader}"


def check(profile, mc: str, loader: str) -> list[str]:
    where = "client/fabric-profile.json"
    if not isinstance(profile, dict):
        return [f"{where}: must be a JSON object"]
    errors = []
    if profile.get("id") != profile_id(mc, loader):
        errors.append(f"{where}: id must be {profile_id(mc, loader)} (the client pack's loader and Minecraft "
                      f"version), not {profile.get('id')}")
    if profile.get("inheritsFrom") != mc:
        errors.append(f"{where}: inheritsFrom must be {mc}, not {profile.get('inheritsFrom')}")
    if not isinstance(profile.get("mainClass"), str) or not profile["mainClass"]:
        errors.append(f"{where}: missing mainClass")
    libraries = profile.get("libraries")
    if not isinstance(libraries, list) or not libraries:
        return errors + [f"{where}: libraries must be a non-empty list"]
    names = [lib.get("name") for lib in libraries if isinstance(lib, dict)]
    if loader_library(loader) not in names:
        errors.append(f"{where}: libraries must include {loader_library(loader)}")
    for i, lib in enumerate(libraries):
        if not isinstance(lib, dict):
            errors.append(f"{where}: library #{i} must be an object")
            continue
        name = lib.get("name") or f"#{i}"
        if not str(lib.get("url", "")).startswith(LIBRARY_HOSTS):
            errors.append(f"{where}: library {name}: url {lib.get('url')} is not an allowed maven repository "
                          f"({', '.join(LIBRARY_HOSTS)})")
        for algo, length in HASH_LENGTHS.items():
            if algo in lib and not re.fullmatch(f"[0-9a-f]{{{length}}}", str(lib[algo])):
                errors.append(f"{where}: library {name}: {algo} must be {length} lowercase hex characters")
        if name != loader_library(loader) and not ("sha1" in lib or "sha256" in lib):
            errors.append(f"{where}: library {name}: needs a sha1 or sha256")
    return errors


def _stable(profile: dict) -> dict:
    return {k: v for k, v in profile.items() if k not in VOLATILE}


def same(a: dict, b: dict) -> bool:
    return _stable(a) == _stable(b)


def save(path: Path, profile: dict) -> bool:
    """Write `profile` to `path`; returns False (and leaves the file alone) if it already holds the same
    profile, so a refresh doesn't churn the generation time."""
    path = Path(path)
    if path.is_file():
        try:
            old = load_json(path)
        except ValueError:
            old = None  # unreadable: overwrite it
        if isinstance(old, dict) and same(old, profile):
            return False
    save_json(path, profile)
    return True
