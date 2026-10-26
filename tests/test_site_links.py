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


STORE_TEXT = '<p data-store="open">Buy it.</p><p class="small" data-store="soon">Ask in the Discord.</p>'


def test_while_the_store_is_closed_only_the_soon_text_shows():
    page, errors = site_links.stamp(STORE_TEXT, links())
    assert page == '<p data-store="open" hidden>Buy it.</p><p class="small" data-store="soon">Ask in the Discord.</p>'
    assert errors == []


def test_once_the_store_url_is_set_the_open_text_shows():
    filled = {**links(), "STORE_URL": "https://shop.example"}
    closed, _ = site_links.stamp(STORE_TEXT, links())
    page, _ = site_links.stamp(closed, filled)
    assert page == '<p data-store="open">Buy it.</p><p class="small" data-store="soon" hidden>Ask in the Discord.</p>'
    assert site_links.stamp(page, filled)[0] == page


def test_hidden_inside_another_attribute_is_left_alone():
    tag = '<p title="a hidden gem" data-store="soon" hidden="hidden">x</p>'
    assert site_links.stamp(tag, links())[0] == '<p title="a hidden gem" data-store="soon">x</p>'


def test_an_unknown_store_state_is_reported():
    page, errors = site_links.stamp('<p data-store="later">x</p>', links())
    assert page == '<p data-store="later">x</p>'
    assert errors == ['data-store="later" should be "open" or "soon"']


def test_an_unknown_key_is_reported():
    page, errors = site_links.stamp('<a data-link="NOPE" href="#">x</a>', links())
    assert page == '<a data-link="NOPE" href="#">x</a>'
    assert errors == ['data-link="NOPE" is not set in config.js']


LAUNCH = "2026-11-22T01:00:00Z"   # Saturday 21 November 2026, 5 PM Pacific


def launching(at=LAUNCH):
    return {**links(), "LAUNCH_AT": at}


def test_a_launch_time_gets_written_into_its_element():
    page, errors = site_links.stamp('<p class="launch"><time data-launch="{date}, {pacific} ({eastern})">'
                                    "soon</time></p>", launching())
    assert page == ('<p class="launch"><time data-launch="{date}, {pacific} ({eastern})" '
                    f'datetime="{LAUNCH}">Saturday 21 November 2026, 5 PM Pacific (8 PM Eastern)</time></p>')
    assert errors == []
    assert site_links.stamp(page, launching())[0] == page


def test_a_meta_tag_gets_the_launch_in_its_content():
    tag = ('<meta name="description" content="Old." data-launch="Claim what isn\'t nailed down & more. '
           'Season I launch: {date}, {pacific}.">')
    page, errors = site_links.stamp(tag, launching())
    assert page == ('<meta name="description" content="Claim what isn\'t nailed down &amp; more. Season I launch: '
                    'Saturday 21 November 2026, 5 PM Pacific." data-launch="Claim what isn\'t nailed down & more. '
                    'Season I launch: {date}, {pacific}.">')
    assert errors == []
    assert site_links.stamp(page, launching())[0] == page


def test_moving_the_launch_rewrites_the_text_and_datetime():
    once, _ = site_links.stamp('<time data-launch="{date} at {pacific}">x</time>', launching())
    page, _ = site_links.stamp(once, launching("2027-02-21T01:30:00+00:00"))
    assert page == ('<time data-launch="{date} at {pacific}" datetime="2027-02-21T01:30:00+00:00">'
                    "Saturday 20 February 2027 at 5:30 PM Pacific</time>")


def test_launch_words_follow_daylight_saving_and_the_eastern_date():
    summer = site_links.launch_words(site_links.launch_time("2027-06-19T19:00:00-07:00"))
    assert summer == {"date": "Saturday 19 June 2027", "pacific": "7 PM Pacific", "eastern": "10 PM Eastern"}
    late = site_links.launch_words(site_links.launch_time("2026-11-22T06:00:00Z"))
    assert late == {"date": "Saturday 21 November 2026", "pacific": "10 PM Pacific", "eastern": "Sunday 1 AM Eastern"}
    noon = site_links.launch_words(site_links.launch_time("2026-12-01T20:00:00Z"))
    assert noon["pacific"] == "12 PM Pacific"


def test_a_page_without_a_launch_element_needs_no_launch_time():
    assert site_links.stamp('<p>Nothing to launch.</p>', links()) == ('<p>Nothing to launch.</p>', [])


def test_a_missing_or_bad_launch_time_is_reported():
    for value in [None, "", "next Saturday", "2026-11-21T17:00:00"]:
        given = links() if value is None else launching(value)
        page, errors = site_links.stamp('<time data-launch="{date}">x</time>', given)
        assert page == '<time data-launch="{date}">x</time>'
        assert len(errors) == 1 and "LAUNCH_AT" in errors[0], value


def test_a_launch_element_must_hold_only_text_and_known_words():
    page, errors = site_links.stamp('<p data-launch="{date}">On <b>launch</b> day</p>', launching())
    assert page == '<p data-launch="{date}">On <b>launch</b> day</p>'
    assert errors == ['<p data-launch="{date}"> must hold only text']
    _, errors = site_links.stamp('<span data-launch="{when}">x</span>', launching())
    assert errors == ['data-launch="{when}" can only use {date}, {pacific} and {eastern}']


def test_the_real_site_says_when_the_season_opens():
    config = (REPO.root / "site" / "config.js").read_text(encoding="utf-8")
    when = site_links.launch_time(site_links.load_links(config)["LAUNCH_AT"])
    index = (REPO.root / "site" / "index.html").read_text(encoding="utf-8")
    assert site_links.launch_words(when)["date"] in index


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
