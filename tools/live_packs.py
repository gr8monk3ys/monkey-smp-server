"""The live-pack list (site/live-packs.json), and the check that the site only sells what the live server runs.

    python tools/live_packs.py                 check the list against package/monkey/datapacks/
    python tools/live_packs.py --built DIR     also check a build's pages (site/out)

live-packs.json says, for each of the server's own data packs, whether it runs on the live server this season:
"on", "off" or "unknown" (not read yet). Flipping a pack is one line there. The site reads the same file when it
is built (site/src/lib/live.ts) and shows a pack's features only while it is "on"; where a section stays, it says
plainly that the feature is not running now (an element with data-off="<pack> ...", the OffNote component).

The checks (validate.py and checks.py's site step run them, through tools/site_links.py):
  - the list names every pack in package/monkey/datapacks/, and nothing else, each with a known state;
  - every pack has an entry in PHRASES below, so a new pack needs a decision about what names it;
  - a built page names no feature of a pack that isn't "on": not in its text, its <title>, its description or
    its structured data. Text is allowed where an element with data-off naming that pack sits beside it (the
    note's parent element is its reach; a note straight in the page's <main> or <article> covers its title and
    descriptions too), and on the pages in EXEMPT.
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from repo import REPO

STATES = ("on", "off", "unknown")

# What names each pack's features on the site. Some match their case only: "the Guide" is the spawn NPC and "the
# guide" the site's; "Server Firsts" and "Anarchy" are the features, "server first" and "non-anarchy" are not.
PHRASES: dict[str, tuple[str, ...]] = {
    "monkey-armor-repair": (),
    "monkey-boss": (r"border boss",),
    "monkey-camera": (r"creator camera",),
    "monkey-clips": (r"clip markers?",),
    "monkey-drops": (r"supply drops?", r"drop nights?"),
    "monkey-events": (r"arena glory", r"faction raids?", r"event arena", r"\bthe cup\b", r"cup points",
                      r"(?-i:\bAnarchy\b)", r"/trigger arena"),
    "monkey-finale": (r"\bfinale\b",),
    "monkey-firsts": (r"(?-i:\bServer Firsts?\b)", r"/trigger firsts", r"\bmilestones?\b"),
    "monkey-lore": (r"season story", r"monument contests?", r"/trigger lore"),
    "monkey-nights": (r"build battle",),
    "monkey-no-netherite-armor": (r"smithing table won.t make it", r"comes off at your feet"),
    "monkey-npcs": (r"town crier", r"(?-i:\bthe Guide\b)"),
    "monkey-omens": (r"\bomens?\b", r"blood moon", r"truce hour", r"\bmeteor\b"),
    "monkey-outposts": (r"\boutposts?\b",),
    "monkey-rules": (r"\bgrace\b", r"end_grace", r"safe for 48 hours", r"48 hours of safety", r"welcome screen"),
    "monkey-sieges": (r"\bsieges?\b",),
    "monkey-standings": (r"\bstandings\b", r"\bbount(?:y|ies)\b", r"wanted board", r"/trigger diplomacy",
                         r"\bpacts?\b", r"declares? war"),
    "monkey-wardrobe": (r"\bwardrobe\b", r"\b(?:sword|helmet|helm) skins?\b", r"\bskins for swords",
                        r"\bchallenges?\b", r"\bquest\b", r"\bcirclet\b", r"\bpathfinder\b"),
}

# Built pages that may name any feature, and why.
EXEMPT = {
    "changes.html": "the changelog: dated news of what changed then, not what runs now",
    "privacy.html": "the privacy notice: what data a feature would use, not an offer of it",
    "terms.html": "the terms: rights over what players make, not an offer of a feature",
}
SKIP = {"script", "style", "template", "noscript"}
DESCRIPTIONS = {"description", "og:description", "twitter:description", "og:title", "twitter:title"}


def list_file(repo=REPO) -> Path:
    return repo.root / "site" / "live-packs.json"


def load(repo=REPO) -> dict[str, str]:
    """Each pack's state, {pack: "on" | "off" | "unknown"}."""
    return json.loads(list_file(repo).read_text(encoding="utf-8"))["packs"]


def not_running(packs: dict[str, str]) -> dict[str, str]:
    """The packs the site can't say run: off, or not read yet."""
    return {pack: state for pack, state in packs.items() if state != "on"}


def shipped(repo=REPO) -> set[str]:
    folder = repo.monkey / "datapacks"
    return {p.name for p in folder.iterdir() if p.is_dir()} if folder.is_dir() else set()


def list_problems(repo=REPO) -> list[str]:
    path = list_file(repo)
    if not path.is_file():
        return ["site/live-packs.json is missing (it lists which data packs run live)"] if shipped(repo) else []
    try:
        packs = load(repo)
    except (ValueError, KeyError, TypeError) as e:
        return [f"site/live-packs.json: not a list of packs ({e})"]
    if not isinstance(packs, dict):
        return ["site/live-packs.json: packs must be an object"]
    errors = [f"site/live-packs.json: {pack} is {state!r}, not one of {', '.join(STATES)}"
              for pack, state in packs.items() if state not in STATES]
    ships = shipped(repo)
    errors += [f"site/live-packs.json: no line for {pack} (package/monkey/datapacks/{pack}): say whether it runs"
               for pack in sorted(ships - packs.keys())]
    errors += [f"site/live-packs.json: {pack} is not a pack in package/monkey/datapacks/"
               for pack in sorted(packs.keys() - ships)]
    errors += [f"tools/live_packs.py: no PHRASES entry for {pack} (what names its features on the site)"
               for pack in sorted(packs.keys() - PHRASES.keys())]
    return errors


# ---------------------------------------------------------------- the built pages


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str | None]
    parent: "_Node | None"
    allows: set[str] = field(default_factory=set)   # packs a data-off note among its children lets it name


class _Page(HTMLParser):
    """A page's visible text, each piece with the element it sits in, plus its title, descriptions and JSON-LD."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root", {}, None)
        self.at = self.root
        self.texts: list[tuple[str, _Node]] = []
        self.head: list[str] = []
        self.page_allows: set[str] = set()   # packs a note straight in <main> or <article> lets the head name
        self._skipping = 0
        self._capture: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        found = dict(attrs)
        if tag == "meta":
            name = found.get("name") or found.get("property") or ""
            if name in DESCRIPTIONS and found.get("content"):
                self.head.append(found["content"] or "")
            return
        if tag in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "source", "track", "wbr"}:
            return
        node = _Node(tag, found, self.at)
        if "data-off" in found and self.at is not None:
            packs = (found["data-off"] or "").split()
            self.at.allows.update(packs)
            if self.at.tag in {"main", "article"}:
                self.page_allows.update(packs)
        self.at = node
        if tag == "script" and found.get("type") == "application/ld+json" or tag == "title":
            self._capture = []
        elif tag in SKIP:
            self._skipping += 1

    def handle_endtag(self, tag):
        # Walk up to the matching element (HTML lets some end tags be left out).
        node = self.at
        while node is not None and node.tag != tag:
            node = node.parent
        if node is None:
            return
        while self.at is not node:
            self._leave(self.at)
        self._leave(node)

    def _leave(self, node: _Node):
        if self._capture is not None and (node.tag == "title" or node.tag == "script"):
            self.head.append("".join(self._capture))
            self._capture = None
        elif node.tag in SKIP and self._skipping:
            self._skipping -= 1
        self.at = node.parent or self.root

    def handle_data(self, data):
        if self._capture is not None:
            self._capture.append(data)
        elif not self._skipping and data.strip():
            self.texts.append((data, self.at))


def _allowed(node: _Node | None) -> set[str]:
    allows: set[str] = set()
    while node is not None:
        allows |= node.allows
        node = node.parent
    return allows


def _patterns(packs: dict[str, str]) -> dict[str, re.Pattern]:
    return {pack: re.compile("|".join(f"(?:{p})" for p in PHRASES[pack]), re.IGNORECASE)
            for pack in not_running(packs) if PHRASES.get(pack)}


def _snippet(text: str, m: re.Match) -> str:
    start, end = max(0, m.start() - 40), min(len(text), m.end() + 40)
    return " ".join(text[start:end].split())


def page_problems(page: str, packs: dict[str, str]) -> list[str]:
    """Where one built page names a feature of a pack that isn't running."""
    parsed = _Page()
    parsed.feed(page)
    parsed.close()
    patterns = _patterns(packs)
    errors = []
    for text in parsed.head:
        for pack, pattern in patterns.items():
            if pack not in parsed.page_allows and (m := pattern.search(text)):
                errors.append(f"names {pack} ({packs[pack]}) in its title, description or structured data: "
                              f"\"{_snippet(text, m)}\"")
    for text, node in parsed.texts:
        allowed = None
        for pack, pattern in patterns.items():
            if m := pattern.search(text):
                allowed = _allowed(node) if allowed is None else allowed
                if pack not in allowed:
                    errors.append(f"names {pack} ({packs[pack]}): \"{_snippet(text, m)}\"")
    return errors


def built_problems(out: Path, repo=REPO) -> list[str]:
    """Every built page (site/out) that sells a feature the live server doesn't run."""
    try:
        packs = load(repo)
    except (OSError, ValueError, KeyError):
        return []   # list_problems says what is wrong with the list
    errors = []
    for page in sorted(out.rglob("*.html")):
        name = page.relative_to(out).as_posix()
        if name in EXEMPT:
            continue
        errors += [f"{out.name}/{name}: {e}" for e in page_problems(page.read_text(encoding="utf-8"), packs)]
    return errors


def main(argv=None, repo=REPO) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--built", type=Path, metavar="DIR", help="also check a build's pages (site/out)")
    a = ap.parse_args(argv)
    errors = list_problems(repo) + (built_problems(a.built, repo) if a.built else [])
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
