import datetime as dt
import re

from repo import REPO

PAGE = REPO.root / "site" / "src" / "content" / "changes.mdx"


def entries(mdx: str) -> list[dict[str, str]]:
    """Each <Entry>'s attributes, top to bottom, leaving out the MDX comments ({/* ... */})."""
    mdx = re.sub(r"\{/\*.*?\*/\}", "", mdx, flags=re.S)
    return [dict(re.findall(r'(\w+)="([^"]*)"', attrs)) for attrs in re.findall(r"<Entry\b([^>]*)>", mdx)]


def test_the_player_changelog_is_newest_first():
    found = entries(PAGE.read_text(encoding="utf-8"))
    assert found, "no entries"
    assert all(e.get("title") for e in found)
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["date"]) for e in found if "date" in e)
    dated = [dt.date.fromisoformat(e["date"]) for e in found if "date" in e]
    assert dated == sorted(dated, reverse=True)
    # An undated "Next update" entry may only sit on top, until its release dates it.
    assert all("date" in e for e in found[1:])


def test_entries_are_read_the_way_the_page_has_them():
    mdx = ('{/* <Entry label="Next update" title="x"> */}\n<Entry label="Next update" title="Soon">\n\n- a\n\n'
           '</Entry>\n\n<Entry date="2026-10-29" title="Old">\n</Entry>\n')
    assert entries(mdx) == [{"label": "Next update", "title": "Soon"}, {"date": "2026-10-29", "title": "Old"}]


def test_the_player_changelog_is_linked_from_the_docs():
    admin = (REPO.root / "docs" / "ADMIN.md").read_text(encoding="utf-8")
    releasing = (REPO.root / "docs" / "MAINTAINING.md").read_text(encoding="utf-8")
    assert "site/src/content/changes.mdx" in admin and "site/src/content/changes.mdx" in releasing
