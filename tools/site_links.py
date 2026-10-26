"""Writes the site's links from site/config.js into its pages, so they work without JavaScript.

    python tools/site_links.py           set the href of every data-link anchor in site/*.html
    python tools/site_links.py --check   exit 1 if a page doesn't match config.js (validate.py runs this too)

config.js is the one place the links live, and app.js fills them in for visitors. Crawlers and link
previews read the HTML as it is served, though, so the same URLs are written into the pages as well. A
link whose URL is empty points at the Discord with a "coming soon" title, as app.js does. When the modpack
is served from the site itself (site/pack/), the check also makes sure that file is there and is the pack
of the version the manifest pins, since a player with another version's pack can't join.
"""
import argparse
import html
import json
import re
import sys
import zipfile
from pathlib import Path

from repo import REPO

SOON = "Coming soon: ask in the Discord"
_SETTING = re.compile(r'^\s*([A-Z_]+):\s*"([^"]*)"', re.M)
_ANCHOR = re.compile(r'<a\b[^>]*\bdata-link="([A-Z_]+)"[^>]*>')


def site(repo=REPO) -> Path:
    return repo.root / "site"


def load_links(config_js: str) -> dict[str, str]:
    return dict(_SETTING.findall(config_js))


def target(links: dict[str, str], key: str) -> tuple[str, str | None]:
    """The href a data-link anchor gets, and its title (None: no title)."""
    if links[key]:
        return links[key], None
    if key != "DISCORD_INVITE" and links.get("DISCORD_INVITE"):
        return links["DISCORD_INVITE"], SOON
    return "#", None


def _set_attr(tag: str, name: str, value: str | None) -> str:
    attr = re.compile(rf'\s{name}="([^"]*)"')
    if value is None:
        # Only drop a title this tool wrote; one written by hand stays.
        return attr.sub(lambda m: "" if html.unescape(m.group(1)) == SOON else m.group(0), tag)
    new = f' {name}="{html.escape(value)}"'
    if attr.search(tag):
        return attr.sub(lambda _: new, tag, count=1)
    return tag[:-1] + new + ">"


def stamp(page: str, links: dict[str, str]) -> tuple[str, list[str]]:
    """The page with every data-link anchor pointing where config.js says, plus any unknown keys."""
    errors = []

    def fix(m: re.Match) -> str:
        tag, key = m.group(0), m.group(1)
        if key not in links:
            errors.append(f'data-link="{key}" is not set in config.js')
            return tag
        href, title = target(links, key)
        return _set_attr(_set_attr(tag, "href", href), "title", title)

    return _ANCHOR.sub(fix, page), errors


def pack_problems(links: dict[str, str], repo=REPO) -> list[str]:
    url = links.get("MODPACK_URL", "")
    if not url.endswith(".mrpack") or re.match(r"[a-z]+:", url):
        return []
    path = site(repo) / url
    if not path.is_file():
        return [f"site: MODPACK_URL is {url}, but site/{url} doesn't exist"]
    served = json.loads(zipfile.ZipFile(path).read("modrinth.index.json"))["versionId"]
    pinned = repo.load_manifest()["version"]
    if served != pinned:
        return [f"site: site/{url} is the {served} client pack, but the manifest is {pinned}: copy "
                f"TheRealms-Client-{pinned}.mrpack and TheRealms-Player-{pinned}.zip into site/pack/ "
                "(docs/MAINTAINING.md, Releasing)"]
    return []


def problems(repo=REPO, write=False) -> list[str]:
    """What is out of step between config.js and the pages; with write, fix the pages instead."""
    config = site(repo) / "config.js"
    if not config.is_file():
        return []
    links = load_links(config.read_text(encoding="utf-8"))
    errors = []
    for page in sorted(site(repo).glob("*.html")):
        text = page.read_text(encoding="utf-8")
        stamped, unknown = stamp(text, links)
        errors += [f"site/{page.name}: {e}" for e in unknown]
        if stamped != text:
            if write:
                page.write_text(stamped, encoding="utf-8", newline="\n")
                print(f"updated site/{page.name}")
            else:
                errors.append(f"site/{page.name}: links differ from config.js (run python tools/site_links.py)")
    return errors + pack_problems(links, repo)


def main(argv=None, repo=REPO) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    errors = problems(repo, write=not a.check)
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
