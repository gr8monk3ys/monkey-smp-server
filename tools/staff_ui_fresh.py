"""Whether the committed staff page (deploy/staff) is the build of its source (staff-ui/).

The VPS has no Node, so the built page is committed and Caddy serves it from the checkout (docs/LIVE.md, "The staff
page"). This builds staff-ui/ again into a temporary folder (bun run build with STAFF_UI_OUT) and compares it with
deploy/staff file by file. Run it from the checkout's root after `bun install` in staff-ui/; tools/checks.py does.

    python tools/staff_ui_fresh.py        exit 1, with what differs, when deploy/staff is stale
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from repo import REPO

SOURCE = REPO.root / "staff-ui"
PAGE = REPO.root / "deploy" / "staff"
# What deploy/staff holds besides the build: tools/staff_modcfg.py reads it, and the page fetches it.
KEPT = {"mod-settings.json"}


def build(into: Path) -> None:
    bun = shutil.which("bun") or "bun"
    env = dict(os.environ, STAFF_UI_OUT=str(into))
    subprocess.run([bun, "run", "build"], cwd=SOURCE, env=env, check=True, stdout=subprocess.DEVNULL)


def _lf(path: Path) -> bytes:
    """A file's bytes with CRLF read as LF: a Windows checkout with core.autocrlf is not a stale build
    (.gitattributes keeps deploy/staff LF anyway)."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def differences(built: Path, page: Path) -> list[str]:
    """What is wrong with `page` against a fresh build in `built`, one line each (none when it is fresh)."""
    made = {p.relative_to(built).as_posix() for p in built.rglob("*") if p.is_file()}
    there = {p.relative_to(page).as_posix() for p in page.rglob("*") if p.is_file()} - KEPT
    problems = [f"missing from deploy/staff: {name}" for name in sorted(made - there)]
    problems += [f"in deploy/staff but not built from staff-ui/ (delete it): {name}" for name in sorted(there - made)]
    problems += [f"stale: {name}" for name in sorted(made & there) if _lf(built / name) != _lf(page / name)]
    return problems


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="staff-ui-") as folder:
        built = Path(folder)
        build(built)
        problems = differences(built, PAGE)
    for line in problems:
        print(line)
    if problems:
        print("deploy/staff is not the build of staff-ui/: run `bun run build` in staff-ui/ and commit deploy/staff.")
        return 1
    print("deploy/staff is the build of staff-ui/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
