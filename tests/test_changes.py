import datetime as dt
import re

from repo import REPO

PAGE = REPO.root / "site" / "changes.html"


def test_the_player_changelog_is_newest_first():
    html = PAGE.read_text(encoding="utf-8")
    entries = re.findall(r"<h3><time class=\"label\"( datetime=\"([\d-]+)\")?>", html)
    assert entries, "no entries"
    dated = [dt.date.fromisoformat(d) for has, d in entries if has]
    assert dated == sorted(dated, reverse=True)
    # An undated "Next update" entry may only sit on top, until its release dates it.
    assert all(has for has, _ in entries[1:])
    assert not re.search(r"<time[^>]*datetime=\"(?!\d{4}-\d{2}-\d{2}\")", html)


def test_the_player_changelog_is_linked_from_the_docs():
    admin = (REPO.root / "docs" / "ADMIN.md").read_text(encoding="utf-8")
    releasing = (REPO.root / "docs" / "MAINTAINING.md").read_text(encoding="utf-8")
    assert "site/changes.html" in admin and "site/changes.html" in releasing
