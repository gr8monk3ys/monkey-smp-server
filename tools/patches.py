"""Patches: small sets of file replacements applied inside one downloaded mod jar or datapack zip
(see ADR-0004). Jars are zips, so both are handled the same way.

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
  - A patch never replaces a file whose place in the zip matters (ORDER_SENSITIVE): the installer's
    Invoke-ZipPatch moves replaced files to the end of the zip, and Java's JarInputStream only finds
    META-INF/MANIFEST.MF as the first or second entry. make, apply and check refuse one.
  - A mod or datapack entry's `patch` is {"path": "patches/<folder>", "base_sha512": <hex>}, where
    base_sha512 is the hash of the exact upstream file the patch was made against. In a consistent
    manifest that equals the entry's own hashes.sha512; when they differ, the pin moved without the
    patch being re-made, and the manifest is invalid.
  - Every folder under patches/ belongs to exactly one mod or datapack entry.
"""
import io
import shutil
import zipfile
from pathlib import Path

import entries

PATCHES_DIR = "patches"
ORDER_SENSITIVE = ("META-INF/MANIFEST.MF",)  # compared ignoring case, as JarInputStream does


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
    files = {n: b.read(n) for n in sorted(after) if not n.endswith("/") and a.read(n) != b.read(n)}
    _refuse_order_sensitive(files)
    return files


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
    _refuse_order_sensitive(files)
    src = zipfile.ZipFile(io.BytesIO(zip_bytes))
    missing = sorted(set(files) - set(src.namelist()))
    if missing:
        raise PatchError(f"the zip has no {', '.join(missing)} to replace")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as dst:
        for info in src.infolist():
            dst.writestr(info, files[info.filename] if info.filename in files else src.read(info))
    return out.getvalue()


def order_sensitive(names) -> list[str]:
    """The names a patch must not replace, because their place in the zip matters."""
    wanted = {n.upper() for n in ORDER_SENSITIVE}
    return sorted(n for n in names if n.upper() in wanted)


def _refuse_order_sensitive(files) -> None:
    if bad := order_sensitive(files):
        raise PatchError(f"a patch can't replace {', '.join(bad)}: the installer moves replaced files to the end "
                         "of the zip, and Java only reads the manifest near the start")


def reference(slug: str, base_sha512: str) -> dict:
    return {"path": f"{PATCHES_DIR}/{slug}", "base_sha512": base_sha512}


def folder(repo, entry: dict) -> Path:
    return repo.monkey.joinpath(*entry["patch"]["path"].split("/"))


def check(manifest: dict, repo) -> list[str]:
    errors, used = [], {}
    for kind in entries.PATCHABLE:
        for entry in entries.group(manifest, kind):
            if "patch" in entry:
                errors += _check_entry(kind, entry, repo)
                if isinstance(entry["patch"], dict):
                    path = str(entry["patch"].get("path"))
                    if path in used:
                        errors.append(f"{kind} {entry.get('file', '?')}: patch {path} is also used by {used[path]}")
                    used.setdefault(path, f"{kind} {entry.get('file', '?')}")
    if repo.patches.is_dir():
        for p in sorted(repo.patches.iterdir()):
            if f"{PATCHES_DIR}/{p.name}" not in used:
                errors.append(f"{PATCHES_DIR}/{p.name} is not used by any mod or datapack")
    return errors


def _check_entry(kind: str, entry: dict, repo) -> list[str]:
    name = f"{kind} {entry.get('file', '?')}"
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
        elif bad := order_sensitive(f.relative_to(where).as_posix() for f in where.rglob("*") if f.is_file()):
            errors.append(f"{name}: patch {path} replaces {', '.join(bad)}, whose place in the zip matters")
    if patch["base_sha512"] != entry.get("hashes", {}).get("sha512"):
        errors.append(f"{name}: patch was made against a different upstream file (base_sha512 differs from "
                      "the pinned sha512); re-make it with a snapshot")
    return errors
