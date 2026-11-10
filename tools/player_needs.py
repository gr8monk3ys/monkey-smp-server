"""What a player needs, said in one place: site/player-needs.json (the client pack's download size, the RAM).

    python tools/player_needs.py           exit 1 if the file or a text that states the numbers is out of step
    python tools/player_needs.py --write   work out the pack's size again and write it to the file

The pack's size is worked out from client/modrinth.index.json: the files a launcher downloads (their fileSize),
in megabytes (10^6 bytes), rounded to 10. The .mrpack itself is only the index and overrides/; the launcher
fetches the rest. The RAM is kept by hand in the same file: nothing in the repo measures what a player's computer
needs, so the file says so ("ram_measured": false) and the number stays where it is until something does.

The site reads the file when it is built (src/app/page.tsx, src/content/front.tsx). The player-facing texts in
TEXTS can't read it, so the check holds them to it: a line there that says "about N MB" (or "~N MB") of the mods
or pack must say the file's size, and "N GB of RAM" must say its RAM. validate.py runs the check.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from repo import REPO

# Player-facing texts that state the pack's size or the RAM. CHANGELOG.md and site/src/content/changes.mdx are
# dated history: what the pack was then.
TEXTS = ("PRODUCT.md", "docs/PLAYERS.md", "docs/SHARING.md", "docs/MODRINTH.md", "docs/PROMOTION.md",
         "player/READ ME.txt")
SITE_TEXTS = ("site/src", (".ts", ".tsx", ".mdx"), {"changes.mdx"})
SIZE = re.compile(r"(?:about |~)(\d+) ?MB")
RAM = re.compile(r"(\d+) GB of RAM")


def needs_file(repo=REPO) -> Path:
    return repo.root / "site" / "player-needs.json"


def pack_mb(repo=REPO) -> int:
    """The client pack's download, in MB rounded to 10."""
    index = json.loads((repo.client / "modrinth.index.json").read_text(encoding="utf-8"))
    return round(sum(f["fileSize"] for f in index["files"]) / 1e7) * 10


def write(repo=REPO) -> None:
    path = needs_file(repo)
    needs = json.loads(path.read_text(encoding="utf-8"))
    needs["pack_mb"] = pack_mb(repo)
    path.write_text(json.dumps(needs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def texts(repo=REPO) -> list[Path]:
    found = [repo.root / name for name in TEXTS if (repo.root / name).is_file()]
    folder, suffixes, skip = SITE_TEXTS
    found += sorted(p for p in (repo.root / folder).rglob("*")
                    if p.suffix in suffixes and p.name not in skip and p.is_file())
    return found


def text_problems(text: str, name: str, mb: int, ram: int) -> list[str]:
    errors = []
    for n, line in enumerate(text.splitlines(), 1):
        if re.search(r"\bmods?\b|pack", line, re.IGNORECASE) and "server" not in line.lower():
            errors += [f"{name}:{n}: says the pack is {m.group(1)} MB; it is about {mb} MB (site/player-needs.json)"
                       for m in SIZE.finditer(line) if int(m.group(1)) != mb]
        errors += [f"{name}:{n}: says {m.group(1)} GB of RAM; site/player-needs.json says {ram}"
                   for m in RAM.finditer(line) if int(m.group(1)) != ram]
    return errors


def problems(repo=REPO) -> list[str]:
    path = needs_file(repo)
    if not path.is_file():
        return []
    try:
        needs = json.loads(path.read_text(encoding="utf-8"))
        mb, ram = int(needs["pack_mb"]), int(needs["ram_gb"])
    except (ValueError, KeyError, TypeError) as e:
        return [f"site/player-needs.json: {e}"]
    errors = []
    if (repo.client / "modrinth.index.json").is_file() and mb != pack_mb(repo):
        errors.append(f"site/player-needs.json: pack_mb is {mb}, but the client pack is about {pack_mb(repo)} MB "
                      "now (run python tools/player_needs.py --write)")
    for p in texts(repo):
        name = p.relative_to(repo.root).as_posix()
        errors += text_problems(p.read_text(encoding="utf-8"), name, mb, ram)
    return errors


def main(argv=None, repo=REPO) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write the pack's size to site/player-needs.json")
    a = ap.parse_args(argv)
    if a.write:
        write(repo)
    errors = problems(repo)
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
