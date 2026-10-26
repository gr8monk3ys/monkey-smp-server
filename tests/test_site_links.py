import json
import zipfile

import site_links
from repo import REPO, Repo

CONFIG = '''window.REALMS = {
  DISCORD_INVITE: "https://discord.gg/abc",
  // a comment
  STORE_URL: "",
  MODPACK_URL: "pack/TheRealms-Client-1.2.3.mrpack",
  MAP_URL: "https://map.example.com/?a=1&b=2",
};
'''


def links():
    return site_links.load_links(CONFIG)


def test_reads_config_js():
    assert links() == {"DISCORD_INVITE": "https://discord.gg/abc", "STORE_URL": "",
                       "MODPACK_URL": "pack/TheRealms-Client-1.2.3.mrpack", "MAP_URL": "https://map.example.com/?a=1&b=2"}


def test_a_set_link_gets_its_url_escaped():
    page, errors = site_links.stamp('<a class="x" data-link="MAP_URL" href="#">map</a>', links())
    assert page == '<a class="x" data-link="MAP_URL" href="https://map.example.com/?a=1&amp;b=2">map</a>'
    assert errors == []


def test_an_empty_link_points_at_the_discord_and_says_soon():
    page, _ = site_links.stamp('<a class="button" data-link="STORE_URL" href="#pricing">Get a pass</a>', links())
    assert page == ('<a class="button" data-link="STORE_URL" href="https://discord.gg/abc" '
                    f'title="{site_links.SOON}">Get a pass</a>')


def test_filling_a_link_in_drops_the_soon_title_but_keeps_a_hand_written_one():
    filled = {**links(), "STORE_URL": "https://shop.example"}
    page, _ = site_links.stamp(f'<a data-link="STORE_URL" href="https://discord.gg/abc" title="{site_links.SOON}">'
                               '<a data-link="STORE_URL" href="#" title="The store">', filled)
    assert page == ('<a data-link="STORE_URL" href="https://shop.example">'
                    '<a data-link="STORE_URL" href="https://shop.example" title="The store">')


def test_stamping_twice_changes_nothing():
    once, _ = site_links.stamp('<p><a data-link="STORE_URL" href="#">a</a> <a href="#rules">b</a></p>', links())
    assert site_links.stamp(once, links())[0] == once


def test_an_unknown_key_is_reported():
    page, errors = site_links.stamp('<a data-link="NOPE" href="#">x</a>', links())
    assert page == '<a data-link="NOPE" href="#">x</a>'
    assert errors == ['data-link="NOPE" is not set in config.js']


def fake_site(tmp_path, pack_version="1.2.3", manifest_version="1.2.3"):
    repo = Repo(tmp_path)
    (tmp_path / "site" / "pack").mkdir(parents=True)
    (tmp_path / "site" / "config.js").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "site" / "index.html").write_text('<a data-link="MAP_URL" href="#">map</a>\n', encoding="utf-8")
    with zipfile.ZipFile(tmp_path / "site" / "pack" / "TheRealms-Client-1.2.3.mrpack", "w") as z:
        z.writestr("modrinth.index.json", json.dumps({"versionId": pack_version}))
    repo.manifest.parent.mkdir(parents=True)
    repo.manifest.write_text(json.dumps({"version": manifest_version}), encoding="utf-8")
    return repo


def test_check_reports_a_stale_page_and_writing_fixes_it(tmp_path):
    repo = fake_site(tmp_path)
    assert site_links.main(["--check"], repo=repo) == 1
    assert site_links.main([], repo=repo) == 0
    assert site_links.main(["--check"], repo=repo) == 0
    assert "https://map.example.com/?a=1&amp;b=2" in (tmp_path / "site" / "index.html").read_text(encoding="utf-8")


def test_the_served_pack_must_be_the_pinned_version(tmp_path):
    repo = fake_site(tmp_path, manifest_version="1.3.0")
    site_links.main([], repo=repo)
    [error] = site_links.problems(repo)
    assert "1.2.3 client pack, but the manifest is 1.3.0" in error


def test_a_missing_pack_is_reported(tmp_path):
    repo = fake_site(tmp_path)
    site_links.main([], repo=repo)
    (tmp_path / "site" / "pack" / "TheRealms-Client-1.2.3.mrpack").unlink()
    assert site_links.problems(repo) == ["site: MODPACK_URL is pack/TheRealms-Client-1.2.3.mrpack, but "
                                         "site/pack/TheRealms-Client-1.2.3.mrpack doesn't exist"]


def test_a_repo_without_the_site_has_nothing_to_check(tmp_path):
    assert site_links.problems(Repo(tmp_path)) == []


def test_the_real_site_matches_its_config():
    assert site_links.problems(REPO) == []
