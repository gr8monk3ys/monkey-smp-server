"""Patches: small sets of file replacements applied inside one downloaded datapack (see ADR-0004).

This module is the one owner of what a patch is. Its interface:

  make(original, edited)        zip bytes x zip bytes -> {path inside the zip: new bytes}
  write(folder, files)          store a patch as a folder (replacing what was there)
  read(folder)                  load a patch folder back as {path: bytes}
  apply(zip_bytes, files)       zip bytes -> patched zip bytes
  reference(slug, base_sha512)  the manifest entry's `patch` value for a new patch
  folder(repo, entry)           where an entry's patch lives in the repo
  check(manifest, repo)         every patch problem in a manifest (as error strings)

The rules, shared with the installer:
  - A patch only REPLACES files that already exist in the upstream zip. Making a patch that adds or
    removes files, or applying one that names a file the zip doesn't have, raises PatchError.
  - A datapack entry's `patch` is {"path": "patches/<folder>", "base_sha512": <hex>}, where
    base_sha512 is the hash of the exact upstream file the patch was made against. In a consistent
    manifest that equals the entry's own hashes.sha512; when they differ, the pin moved without the
    patch being re-made, and the manifest is invalid.
  - Every folder under patches/ belongs to exactly one datapack entry.
"""
import io
import shutil
import zipfile
from pathlib import Path

PATCHES_DIR = "patches"


class PatchError(Exception):
    """A patch can't be made or applied."""


def make(original: bytes, edited: bytes) -> dict[str, bytes]:
    """The files that differ between two versions of a zip, as the edited version has them."""
    a, b = zipfile.ZipFile(io.BytesIO(original)), zipfile.ZipFile(io.BytesIO(edited))
    before, after = set(a.namelist()), set(b.namelist())
    if before != after:
        added, removed = sorted(after - before), sorted(before - after)
        raise PatchError("a patch can only edit files in place; "
                         f"added: {added or 'none'}, removed: {removed or 'none'}")
    return {n: b.read(n) for n in sorted(after) if not n.endswith("/") and a.read(n) != b.read(n)}


def write(folder: Path, files: dict[str, bytes]) -> None:
    folder = Path(folder)
    shutil.rmtree(folder, ignore_errors=True)
    for name, data in files.items():
        out = folder.joinpath(*name.split("/"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)


def read(folder: Path) -> dict[str, bytes]:
    folder = Path(folder)
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def apply(zip_bytes: bytes, files: dict[str, bytes]) -> bytes:
    """Replace files inside a zip. Every patched path must already exist in the zip."""
    src = zipfile.ZipFile(io.BytesIO(zip_bytes))
    missing = sorted(set(files) - set(src.namelist()))
    if missing:
        raise PatchError(f"the zip has no {', '.join(missing)} to replace")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as dst:
        for info in src.infolist():
            dst.writestr(info, files[info.filename] if info.filename in files else src.read(info))
    return out.getvalue()


def reference(slug: str, base_sha512: str) -> dict:
    return {"path": f"{PATCHES_DIR}/{slug}", "base_sha512": base_sha512}


def folder(repo, entry: dict) -> Path:
    return repo.realms.joinpath(*entry["patch"]["path"].split("/"))


def check(manifest: dict, repo) -> list[str]:
    errors, used = [], set()
    for entry in manifest.get("datapacks", []):
        if "patch" in entry:
            errors += _check_entry(entry, repo)
            if isinstance(entry["patch"], dict):
                used.add(str(entry["patch"].get("path")))
    if repo.patches.is_dir():
        for p in sorted(repo.patches.iterdir()):
            if f"{PATCHES_DIR}/{p.name}" not in used:
                errors.append(f"{PATCHES_DIR}/{p.name} is not used by any datapack")
    return errors


def _check_entry(entry: dict, repo) -> list[str]:
    name = f"datapack {entry.get('file', '?')}"
    patch = entry["patch"]
    if not isinstance(patch, dict) or set(patch) != {"path", "base_sha512"}:
        return [f'{name}: patch must be {{"path": "{PATCHES_DIR}/<folder>", "base_sha512": "<hex>"}}']
    errors = []
    path = str(patch["path"])
    parts = path.split("/")
    if len(parts) != 2 or parts[0] != PATCHES_DIR or parts[1] in ("", ".", ".."):
        errors.append(f"{name}: patch path {path} must be {PATCHES_DIR}/<folder>")
    else:
        where = folder(repo, entry)
        if not where.is_dir() or not any(p.is_file() for p in where.rglob("*")):
            errors.append(f"{name}: patch folder {path} is missing or empty")
    if patch["base_sha512"] != entry.get("hashes", {}).get("sha512"):
        errors.append(f"{name}: patch was made against a different upstream file (base_sha512 differs from "
                      "the pinned sha512); re-make it with a snapshot")
    return errors
