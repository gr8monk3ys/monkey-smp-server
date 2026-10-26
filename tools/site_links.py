"""Writes the site's links from site/config.js into its pages, so they work without JavaScript.

    python tools/site_links.py           set the href of every data-link anchor in site/*.html
    python tools/site_links.py --check   exit 1 if a page doesn't match config.js (validate.py runs this too)

config.js is the one place the links live, and app.js fills them in for visitors. Crawlers and link
previews read the HTML as it is served, though, so the same URLs are written into the pages as well. A
link whose URL is empty points at the Discord with a "coming soon" title, as app.js does. Text that is only
true once the store is open is marked data-store="open", and its stand-in for now data-store="soon": the
one that doesn't apply while STORE_URL is empty (or once it is set) gets the hidden attribute. When the
modpack is served from the site itself (site/pack/), the check also makes sure that file is there and is
the pack of the version the manifest pins, since a player with another version's pack can't join.

The season's launch time is LAUNCH_AT, an ISO 8601 time with its offset ("2026-11-22T01:00:00Z"). An element
with data-launch="..." gets that attribute as a template for its text (for a <meta>, its content), with
{date} the day in Pacific time ("Saturday 21 November 2026"), {pacific} the time there ("5 PM Pacific") and
{eastern} the time in Eastern ("8 PM Eastern", with the weekday when it falls on the next day); a <time>
also gets datetime="LAUNCH_AT". The element must hold only text. app.js adds the visitor's own time and the
countdown on top.
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo

from repo import REPO

SOON = "Coming soon: ask in the Discord"
_SETTING = re.compile(r'^\s*([A-Z_]+):\s*"([^"]*)"', re.M)
_ANCHOR = re.compile(r'<a\b[^>]*\bdata-link="([A-Z_]+)"[^>]*>')
_STORE_TEXT = re.compile(r'<[a-z]+\b[^>]*\bdata-store="([^"]*)"[^>]*>')
# A hidden attribute, or a quoted value (kept as it is, so "hidden" inside a title isn't touched).
_HIDDEN = re.compile(r'("[^"]*")|\shidden(?:="[^"]*")?(?=[\s>])')
# An element with a launch template, and its text when it holds nothing else (a <meta> holds nothing).
_LAUNCH = re.compile(r'<([a-z]+)\b[^>]*\bdata-launch="([^"]*)"[^>]*>(?:([^<]*)</\1>)?')
PACIFIC = ZoneInfo("America/Los_Angeles")
EASTERN = ZoneInfo("America/New_York")
# Written out here rather than with strftime, which follows the machine's locale.
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


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


def _escape(text: str, quote=True) -> str:
    """html.escape, except apostrophes, which are fine in text and in double-quoted attributes."""
    text = html.escape(text, quote=False)
    return text.replace('"', "&quot;") if quote else text


def _set_attr(tag: str, name: str, value: str | None) -> str:
    attr = re.compile(rf'\s{name}="([^"]*)"')
    if value is None:
        # Only drop a title this tool wrote; one written by hand stays.
        return attr.sub(lambda m: "" if html.unescape(m.group(1)) == SOON else m.group(0), tag)
    new = f' {name}="{_escape(value)}"'
    if attr.search(tag):
        return attr.sub(lambda _: new, tag, count=1)
    return tag[:-1] + new + ">"


def _set_hidden(tag: str, hidden: bool) -> str:
    tag = _HIDDEN.sub(lambda m: m.group(1) or "", tag)
    return tag[:-1] + " hidden>" if hidden else tag


def launch_time(value: str) -> dt.datetime:
    """LAUNCH_AT as a time; ValueError unless it is an ISO 8601 time with an offset."""
    when = dt.datetime.fromisoformat(value)
    if when.tzinfo is None:
        raise ValueError("no time zone")
    return when


def _clock(when: dt.datetime) -> str:
    hour = when.hour % 12 or 12
    minutes = f":{when.minute:02}" if when.minute else ""
    return f"{hour}{minutes} {'AM' if when.hour < 12 else 'PM'}"


def launch_words(when: dt.datetime) -> dict[str, str]:
    """What a data-launch template can say: {date}, {pacific} and {eastern}."""
    west, east = when.astimezone(PACIFIC), when.astimezone(EASTERN)
    eastern = f"{_clock(east)} Eastern"
    if east.date() != west.date():
        eastern = f"{DAYS[east.weekday()]} {eastern}"
    return {"date": f"{DAYS[west.weekday()]} {west.day} {MONTHS[west.month - 1]} {west.year}",
            "pacific": f"{_clock(west)} Pacific", "eastern": eastern}


def _stamp_launch(page: str, value: str | None, errors: list[str]) -> str:
    if not _LAUNCH.search(page):
        return page
    try:
        when = launch_time(value or "")
    except ValueError:
        errors.append("data-launch needs LAUNCH_AT in config.js: an ISO 8601 time with its offset, "
                      f'like "2026-11-22T01:00:00Z", not "{value or ""}"')
        return page
    words = launch_words(when)

    def fill(m: re.Match) -> str:
        whole, name, template, text = m.group(0), m.group(1), html.unescape(m.group(2)), m.group(3)
        try:
            said = template.format_map(words)
        except (KeyError, ValueError, IndexError):
            errors.append(f'data-launch="{m.group(2)}" can only use {{date}}, {{pacific}} and {{eastern}}')
            return whole
        tag = whole[:whole.index(">") + 1]
        if name == "meta":
            return _set_attr(tag, "content", said) + whole[len(tag):]
        if text is None:
            errors.append(f'<{name} data-launch="{m.group(2)}"> must hold only text')
            return whole
        if name == "time":
            tag = _set_attr(tag, "datetime", value)
        return f"{tag}{_escape(said, quote=False)}</{name}>"

    return _LAUNCH.sub(fill, page)


def stamp(page: str, links: dict[str, str]) -> tuple[str, list[str]]:
    """The page with every data-link anchor pointing where config.js says, only the store text that
    applies showing and the launch time written in, plus any unknown keys."""
    errors = []

    def fix(m: re.Match) -> str:
        tag, key = m.group(0), m.group(1)
        if key not in links:
            errors.append(f'data-link="{key}" is not set in config.js')
            return tag
        href, title = target(links, key)
        return _set_attr(_set_attr(tag, "href", href), "title", title)

    store_open = bool(links.get("STORE_URL"))

    def show(m: re.Match) -> str:
        tag, when = m.group(0), m.group(1)
        if when not in ("open", "soon"):
            errors.append(f'data-store="{when}" should be "open" or "soon"')
            return tag
        return _set_hidden(tag, (when == "open") != store_open)

    page = _STORE_TEXT.sub(show, _ANCHOR.sub(fix, page))
    return _stamp_launch(page, links.get("LAUNCH_AT"), errors), errors


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
