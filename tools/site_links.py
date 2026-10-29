"""Checks the site's settings (site/config.json) and what the site serves from them.

    python tools/site_links.py --check             exit 1 if something is wrong (validate.py runs this too)
    python tools/site_links.py                     the same, after copying the site's stylesheet for Season Wrapped
    python tools/site_links.py --built site/out    also check a build's pages (checks.py's site step, after the build)

config.json is the one place the site's links, the server address and the launch time live. The site (Next.js,
site/README.md) reads it when it is built and writes every link and the launch time into its pages, so they
work without JavaScript; this checks the same file from the Python side:
  - every key is there and is a string, and nothing else is (a misspelt key would otherwise go unnoticed);
  - LAUNCH_AT is an ISO 8601 time with its offset ("2026-11-08T01:00:00Z");
  - when the modpack is served from the site itself (site/public/pack/), that file is there and is the pack of
    the version the manifest pins, since a player with another version's pack can't join;
  - site/public/wrapped/site.css is a copy of the site's stylesheet (src/app/style.css): Season Wrapped's pages
    (tools/wrapped.py) are plain HTML that load it, since the built site's own CSS has a new name every build.
    Without --check, a stale copy is replaced instead of reported.
With --built DIR, the built pages are checked too: every data-link anchor goes where config.json says (a link
whose URL is empty points at the Discord with a "coming soon" title) and every data-launch element says the
launch as tools/season_calendar.py does ({date} the day in Pacific time, "Saturday 7 November 2026"; {pacific}
"5 PM Pacific"; {eastern} "8 PM Eastern", with the weekday when it falls on the next day), with a <time>'s
datetime set to LAUNCH_AT. The site works those out in TypeScript; this is what keeps the two in step.
"""
import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path

import season_calendar
from repo import REPO

SOON = "Coming soon: ask in the Discord"
KEYS = ("ADDRESS", "DISCORD_INVITE", "STORE_URL", "MODPACK_URL", "INSTALLER_URL", "MAP_URL", "LAUNCH_AT")
PAGES = ("index.html", "changes.html", "creators.html", "guide.html", "guide/commands/players.html")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def site(repo=REPO) -> Path:
    return repo.root / "site"


def config_file(repo=REPO) -> Path:
    return site(repo) / "config.json"


def load_links(config_json: str) -> dict[str, str]:
    """config.json's settings (its text); ValueError when it isn't a JSON object."""
    links = json.loads(config_json)
    if not isinstance(links, dict):
        raise ValueError("config.json must hold one JSON object")
    return links


def links(repo=REPO) -> dict[str, str]:
    """The site's settings, {} when the checkout has no site."""
    path = config_file(repo)
    return load_links(path.read_text(encoding="utf-8")) if path.is_file() else {}


def target(links: dict[str, str], key: str) -> tuple[str, str | None]:
    """The href a link to config.json's `key` gets, and its title (None: no title). The site does the same
    (src/lib/config.ts)."""
    if links[key]:
        return links[key], None
    if key != "DISCORD_INVITE" and links.get("DISCORD_INVITE"):
        return links["DISCORD_INVITE"], SOON
    return "#", None


def launch_time(value: str) -> dt.datetime:
    """LAUNCH_AT as a time; ValueError unless it is an ISO 8601 time with an offset."""
    when = dt.datetime.fromisoformat(value)
    if when.tzinfo is None:
        raise ValueError("no time zone")
    return when


def launch_words(when: dt.datetime) -> dict[str, str]:
    """What a data-launch template can say: {date}, {pacific} and {eastern} (season_calendar.words)."""
    return season_calendar.words(when)


def config_problems(links: dict) -> list[str]:
    errors = [f"config.json: {key} is missing" for key in KEYS if key not in links]
    errors += [f"config.json: {key} is not a setting the site has (the settings: {', '.join(KEYS)})"
               for key in links if key not in KEYS]
    errors += [f"config.json: {key} should be a string" for key in KEYS
               if key in links and not isinstance(links[key], str)]
    if isinstance(links.get("LAUNCH_AT"), str):
        try:
            launch_time(links["LAUNCH_AT"])
        except ValueError:
            errors.append("config.json: LAUNCH_AT should be an ISO 8601 time with its offset, like "
                          f'"2026-11-22T01:00:00Z", not "{links["LAUNCH_AT"]}"')
    return errors


def pack_problems(links: dict[str, str], repo=REPO) -> list[str]:
    url = links.get("MODPACK_URL", "")
    if not isinstance(url, str) or not url.endswith(".mrpack") or re.match(r"[a-z]+:", url):
        return []
    path = site(repo) / "public" / url.lstrip("/")
    if not path.is_file():
        return [f"site: MODPACK_URL is {url}, but site/public/{url.lstrip('/')} doesn't exist"]
    served = json.loads(zipfile.ZipFile(path).read("modrinth.index.json"))["versionId"]
    pinned = repo.load_manifest()["version"]
    if served != pinned:
        return [f"site: site/public/{url.lstrip('/')} is the {served} client pack, but the manifest is {pinned}: "
                f"copy TheRealms-Client-{pinned}.mrpack and TheRealms-Player-{pinned}.zip into site/public/pack/ "
                "and point MODPACK_URL and INSTALLER_URL in site/config.json at them (docs/MAINTAINING.md, Releasing)"]
    return []


def stylesheet(repo=REPO) -> Path:
    return site(repo) / "src" / "app" / "style.css"


def wrapped_stylesheet(repo=REPO) -> Path:
    return site(repo) / "public" / "wrapped" / "site.css"


def stylesheet_problems(repo=REPO, write=False) -> list[str]:
    source, copy = stylesheet(repo), wrapped_stylesheet(repo)
    if not source.is_file():
        return []
    if copy.is_file() and copy.read_bytes() == source.read_bytes():
        return []
    if write:
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(source.read_bytes())
        print("updated site/public/wrapped/site.css")
        return []
    return ["site/public/wrapped/site.css is not a copy of site/src/app/style.css (run python tools/site_links.py)"]


class _Page(HTMLParser):
    """The data-link anchors and data-launch elements of a page, with their text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str | None]] = []
        self.launches: list[tuple[str, dict[str, str | None], list[str]]] = []
        self._open: list[tuple[str, list[str]]] = []

    def handle_starttag(self, tag, attrs):
        found = dict(attrs)
        if tag == "a" and "data-link" in found:
            self.anchors.append(found)
        if "data-launch" in found:
            text: list[str] = []
            self.launches.append((tag, found, text))
            if tag not in VOID:
                self._open.append((tag, text))
        elif self._open and tag not in VOID:
            self._open.append((tag, self._open[-1][1]))

    def handle_endtag(self, tag):
        if self._open:
            self._open.pop()

    def handle_data(self, data):
        if self._open:
            self._open[-1][1].append(data)


def page_problems(page: str, links: dict[str, str]) -> list[str]:
    """What in one built page doesn't say what config.json does."""
    parsed = _Page()
    parsed.feed(page)
    errors = []
    for a in parsed.anchors:
        key = a["data-link"] or ""
        if key not in links or key not in KEYS:
            errors.append(f'data-link="{key}" is not set in config.json')
            continue
        href, title = target(links, key)
        if (a.get("href"), a.get("title")) != (href, title):
            errors.append(f'data-link="{key}" goes to {a.get("href")} (title {a.get("title")!r}), but config.json '
                          f"says {href} (title {title!r})")
    if parsed.launches:
        try:
            when = launch_time(links.get("LAUNCH_AT") or "")
        except ValueError:
            return errors + ["data-launch needs LAUNCH_AT in config.json"]
        words = launch_words(when)
        for tag, attrs, text in parsed.launches:
            template = attrs["data-launch"] or ""
            try:
                said = template.format_map(words)
            except (KeyError, ValueError, IndexError):
                errors.append(f'data-launch="{template}" can only use {{date}}, {{pacific}} and {{eastern}}')
                continue
            shown = attrs.get("content") if tag == "meta" else "".join(text)
            if shown != said:
                errors.append(f'<{tag} data-launch="{template}"> says "{shown}", not "{said}"')
            if tag == "time" and attrs.get("datetime") != links["LAUNCH_AT"]:
                errors.append(f'<time data-launch="{template}"> has datetime="{attrs.get("datetime")}", '
                              f'not "{links["LAUNCH_AT"]}"')
    return errors


def built_problems(out: Path, links: dict[str, str]) -> list[str]:
    """What in a build (site/out) is missing or out of step with config.json."""
    errors = [f"{out}: no {name} (is next.config.mjs's output still 'export'?)" for name in PAGES
              if not (out / name).is_file()]
    for page in sorted(out.rglob("*.html")):  # the guide's pages sit in out/guide/
        errors += [f"{out.name}/{page.relative_to(out).as_posix()}: {e}"
                   for e in page_problems(page.read_text(encoding="utf-8"), links)]
    return errors


def problems(repo=REPO, write=False, built: Path | None = None) -> list[str]:
    """What is wrong with config.json and what is served from it; with write, refresh the Wrapped stylesheet."""
    path = config_file(repo)
    if not path.is_file():
        return []
    try:
        settings = load_links(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"site/config.json: {e}"]
    errors = config_problems(settings)
    if errors:
        return errors
    errors += pack_problems(settings, repo) + stylesheet_problems(repo, write)
    if built is not None:
        errors += built_problems(built, settings)
    return errors


def main(argv=None, repo=REPO) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report a stale Wrapped stylesheet instead of copying it")
    ap.add_argument("--built", type=Path, metavar="DIR", help="also check a build's pages (site/out)")
    a = ap.parse_args(argv)
    errors = problems(repo, write=not a.check, built=a.built)
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
