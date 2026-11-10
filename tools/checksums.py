"""SHA256SUMS.txt: the SHA-256 of every file a release publishes, so a download can be checked.

    python tools/checksums.py DIR              write DIR/SHA256SUMS.txt for the files in DIR
    python tools/checksums.py --check DIR      exit 1 unless DIR/SHA256SUMS.txt lists exactly DIR's files, each
                                               with the hash it has now
    python tools/checksums.py --same DIR OTHER
                                               exit 1 if a file both lists name has another hash in OTHER

The list is one line per file, "<64 hex digits>  <name>", sorted by name, LF line ends: what `sha256sum` and
`shasum -a 256` write, so `sha256sum -c SHA256SUMS.txt` checks a folder against it.

tools/build.py writes dist/SHA256SUMS.txt beside the three release files and the release workflow attaches it to
the GitHub release, after `--check dist` (so a release can't go out without the list, or with a stale one).
Players download from the website, so site/public/pack/ has a list too, for the files there: tools/site_links.py
writes it, validate.py fails when it is missing or stale, and the front page links to it. `--same` is how the
release workflow says when the website's files are not the release's own bytes.
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

NAME = "SHA256SUMS.txt"
LINE = re.compile(r"([0-9a-f]{64})  ([^/\\\r\n]+)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def listed_files(folder: Path) -> list[Path]:
    """The files of `folder` a list covers: every file in it but the list itself."""
    return sorted((p for p in folder.iterdir() if p.is_file() and p.name != NAME), key=lambda p: p.name)


def text(files) -> str:
    """The list for `files`."""
    return "".join(f"{sha256(p)}  {p.name}\n" for p in sorted(files, key=lambda p: p.name))


def write(folder: Path, files=None) -> Path:
    """Write folder/SHA256SUMS.txt for `files` (default: every file in the folder)."""
    out = folder / NAME
    out.write_text(text(listed_files(folder) if files is None else files), encoding="ascii", newline="\n")
    return out


def parse(listing: str) -> dict[str, str]:
    """{name: hash} of a list's text; ValueError for a line that isn't "<hash>  <name>" or a name listed twice."""
    found: dict[str, str] = {}
    lines = listing.split("\n")
    if lines[-1] == "":
        lines.pop()     # the last line's end
    for n, line in enumerate(lines, 1):
        m = LINE.fullmatch(line)
        if not m:
            raise ValueError(f'line {n} is not "<sha256>  <file name>"')
        if m.group(2) in found:
            raise ValueError(f"line {n} lists {m.group(2)} a second time")
        found[m.group(2)] = m.group(1)
    return found


def load(folder: Path) -> dict[str, str]:
    """{name: hash} of folder/SHA256SUMS.txt; ValueError when it is missing or isn't a list."""
    path = folder / NAME
    if not path.is_file():
        raise ValueError("missing")
    try:
        return parse(path.read_bytes().decode("ascii"))
    except UnicodeDecodeError:
        raise ValueError("not plain text") from None


def problems(folder: Path, label: str | None = None) -> list[str]:
    """What is wrong with folder/SHA256SUMS.txt: missing, unreadable, or out of step with the folder's files."""
    label = label or folder.as_posix()
    try:
        listed = load(folder)
    except ValueError as e:
        return [f"{label}/{NAME}: {e}"]
    files = {p.name: p for p in listed_files(folder)}
    errors = [f"{label}/{NAME}: lists {name}, which isn't in {label}/" for name in sorted(set(listed) - set(files))]
    errors += [f"{label}/{NAME}: doesn't list {name}" for name in sorted(set(files) - set(listed))]
    errors += [f"{label}/{NAME}: {name} is listed as {listed[name][:12]}..., but the file is {sha256(p)[:12]}..."
               for name, p in sorted(files.items()) if name in listed and listed[name] != sha256(p)]
    return errors


def differences(folder: Path, other: Path) -> list[str]:
    """The files both folders' lists name with different hashes; a list that can't be read is a difference too."""
    try:
        ours, theirs = load(folder), load(other)
    except ValueError as e:
        return [f"can't compare {folder.as_posix()} and {other.as_posix()}: a {NAME} is {e}"]
    return [f"{name}: {folder.as_posix()} has {ours[name][:12]}..., {other.as_posix()} has {theirs[name][:12]}..."
            for name in sorted(set(ours) & set(theirs)) if ours[name] != theirs[name]]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path, metavar="DIR")
    ap.add_argument("--check", action="store_true", help=f"check DIR/{NAME} instead of writing it")
    ap.add_argument("--same", type=Path, metavar="OTHER", help="compare DIR's list with OTHER's")
    a = ap.parse_args(argv)
    if not a.folder.is_dir():
        print(f"ERROR {a.folder} is not a folder")
        return 1
    if a.same is not None:
        errors = differences(a.folder, a.same)
    elif a.check:
        errors = problems(a.folder)
    else:
        out = write(a.folder)
        print(f"{out}  {len(listed_files(a.folder))} files")
        return 0
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
