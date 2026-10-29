"""Re-record tests/fixtures/patch-golden/expected.json: the patch rules' answers for one fixed input.

  python -I tests/fixtures/patch-golden/record.py          # from the committed input.zip and patches/
  python -I tests/fixtures/patch-golden/record.py --input  # first rebuild input.zip from INPUT below

The patch rules live twice, on purpose: tools/patches.py and tools/entries.py for the maintainer tools,
and Realms.psm1 (Get-ExpectedHash, Get-PatchId, Invoke-ZipPatch, Install-PatchedArtifact) for the
installer, which has to stay Windows PowerShell 5.1 (ADR-0003, ADR-0007). Both are tested against this
one fixture: tests/test_patches.py checks the Python side and tests/Realms.Tests.ps1 the PowerShell side.

Only re-record when a rule changes on purpose, then check that both test suites pass. The fixture holds
only dummy text files (never a real jar or datapack):
  input.zip          the "upstream" zip: stored and deflated files plus a directory entry
  patches/golden/    a patch in the real layout (paths as inside the zip), replacing six of its files
  patches/adds-a-file/  a patch naming a file input.zip doesn't have, which both sides must refuse

Python has no copy of the patch id: only the installer uses it (as the key in its install state that says
a patched file on disk is still current). patch_id() below writes down its recipe so the id is pinned too.
"""
import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import entries  # noqa: E402
import patches  # noqa: E402

HERE = Path(__file__).resolve().parent
INPUT_ZIP = HERE / "input.zip"
EXPECTED = HERE / "expected.json"
GOLDEN, REFUSED = "patches/golden", "patches/adds-a-file"
URL = "https://example.invalid/input.zip"  # never fetched: the PowerShell test's Fetch adapter copies input.zip

# input.zip, in entry order: (name, contents, compression). None is a directory entry.
INPUT = [
    ("README.txt", b"Golden fixture for the patch rules. Not a mod or a datapack.\n", zipfile.ZIP_STORED),
    ("notes/", None, zipfile.ZIP_STORED),
    ("notes/a.txt", b"upstream a\n", zipfile.ZIP_DEFLATED),
    ("notes/b.txt", b"upstream b, never patched\n", zipfile.ZIP_DEFLATED),
    ("notes/deep/c.txt", b"upstream c\n", zipfile.ZIP_DEFLATED),
    # Names a culture-aware sort orders differently from a code-point sort (case, and "-" against a letter).
    ("notes/Upper.txt", b"upstream Upper\n", zipfile.ZIP_DEFLATED),
    ("notes/a-z.txt", b"upstream a-z\n", zipfile.ZIP_DEFLATED),
    ("notes/ab.txt", b"upstream ab\n", zipfile.ZIP_DEFLATED),
    ("overlay_1/notes/a.txt", b"upstream overlay a\n", zipfile.ZIP_STORED),
]


def build_input() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data, compression in INPUT:
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = compression
            info.external_attr = (0o40755 << 16) | 0x10 if data is None else 0o100644 << 16
            z.writestr(info, data or b"")
    return out.getvalue()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def zip_entries(data: bytes) -> dict[str, str]:
    """{entry name: sha256 of its contents}, sorted by name (entry order is not part of the rules).

    A name that appears twice (a replaced file added again instead of replaced) raises ValueError.
    """
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate zip entries: {sorted({n for n in names if names.count(n) > 1})}")
    return {n: sha256(z.read(n)) for n in sorted(names)}


def patch_id(files: dict[str, bytes]) -> str:
    """The installer's Get-PatchId: sha256 of "<path>=<sha256 of the file>;" for every file, in ordinal
    (code-point) order of the path."""
    return sha256("".join(f"{rel}={sha256(files[rel])};" for rel in sorted(files)).encode("utf-8"))


def expected_hash_cases(data: bytes) -> list[dict]:
    """Manifest `hashes` objects and the hash the rule picks (the strongest of sha512, sha256)."""
    h = {algo: hashlib.new(algo, data).hexdigest() for algo in ("sha1", "sha256", "sha512")}
    cases = [{"sha512": h["sha512"], "sha256": h["sha256"]}, {"sha256": h["sha256"]},
             {"sha1": h["sha1"], "sha256": h["sha256"]}, {"sha1": h["sha1"]}]
    out = []
    for hashes in cases:
        try:
            algo, value = entries.hash_of({"file": "input.zip", "hashes": hashes})
            out.append({"hashes": hashes, "algorithm": algo, "value": value})
        except KeyError as err:
            out.append({"hashes": hashes, "error": err.args[0]})
    return out


def golden(folder: Path = HERE) -> dict:
    """Everything expected.json pins, computed with the Python rules from the files in `folder`."""
    data = (folder / "input.zip").read_bytes()
    patch = patches.read(folder.joinpath(*GOLDEN.split("/")))
    try:
        patches.apply(data, patches.read(folder.joinpath(*REFUSED.split("/"))))
        refused = None
    except patches.PatchError:
        names = set(zipfile.ZipFile(io.BytesIO(data)).namelist())
        refused = sorted(set(patches.read(folder.joinpath(*REFUSED.split("/")))) - names)
    sha512 = hashlib.sha512(data).hexdigest()
    entry = {"file": "input.zip", "url": URL, "size": len(data), "hashes": {"sha512": sha512},
             "patch": patches.reference(GOLDEN.split("/")[1], sha512)}
    return {
        "_about": "Pinned by tests/test_patches.py (Python) and tests/Realms.Tests.ps1 (PowerShell). "
                  "Re-record with: python -I tests/fixtures/patch-golden/record.py",
        "input": {"file": "input.zip", "sha256": sha256(data), "entries": zip_entries(data)},
        "patch": {"path": GOLDEN, "files": {rel: sha256(b) for rel, b in patch.items()}, "id": patch_id(patch)},
        "patched": {"entries": zip_entries(patches.apply(data, patch))},
        "refused": {"path": REFUSED, "missing": refused},
        "entry": entry,
        "install_id": f"{entries.hash_of(entry)[1]}:{patch_id(patch)}",
        "expected_hash": expected_hash_cases(data),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", action="store_true", help="rebuild input.zip from INPUT first")
    args = ap.parse_args(argv)
    if args.input:
        INPUT_ZIP.write_bytes(build_input())
    EXPECTED.write_text(json.dumps(golden(), indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {EXPECTED.relative_to(HERE.parents[2]).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
