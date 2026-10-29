import json
import zipfile

import pytest

import site_links
from repo import REPO, Repo

LAUNCH = "2026-11-22T01:00:00Z"   # Saturday 21 November 2026, 5 PM Pacific
SETTINGS = {
    "ADDRESS": "play.example.com",
    "DISCORD_INVITE": "https://discord.gg/abc",
    "STORE_URL": "",
    "MODPACK_URL": "pack/TheRealms-Client-1.2.3.mrpack",
    "INSTALLER_URL": "pack/TheRealms-Player-1.2.3.zip",
    "MAP_URL": "https://map.example.com/?a=1&b=2",
    "LAUNCH_AT": LAUNCH,
}


def links(**changed):
    return {**SETTINGS, **changed}


def test_reads_config_json():
    assert site_links.load_links(json.dumps(SETTINGS)) == SETTINGS


def test_config_json_must_be_an_object():
    with pytest.raises(ValueError):
        site_links.load_links("[1, 2]")


def test_the_real_config_has_every_setting_and_nothing_else():
    assert site_links.config_problems(site_links.links()) == []
    assert set(site_links.links()) == set(site_links.KEYS)


def test_a_missing_misspelt_or_non_string_setting_is_reported():
    given = {k: v for k, v in links(MAP_URL=3, STORE_URLS="x").items() if k != "ADDRESS"}
    assert site_links.config_problems(given) == [
        "config.json: ADDRESS is missing",
        f"config.json: STORE_URLS is not a setting the site has (the settings: {', '.join(site_links.KEYS)})",
        "config.json: MAP_URL should be a string",
    ]


def test_a_bad_launch_time_is_reported():
    for value in ["", "next Saturday", "2026-11-21T17:00:00"]:
        [error] = site_links.config_problems(links(LAUNCH_AT=value))
        assert "LAUNCH_AT should be an ISO 8601 time with its offset" in error, value


def test_a_set_link_goes_to_its_url():
    assert site_links.target(links(), "MAP_URL") == ("https://map.example.com/?a=1&b=2", None)


def test_an_empty_link_points_at_the_discord_and_says_soon():
    assert site_links.target(links(), "STORE_URL") == ("https://discord.gg/abc", site_links.SOON)
    assert site_links.target(links(STORE_URL="https://shop.example"), "STORE_URL") == ("https://shop.example", None)
    assert site_links.target(links(DISCORD_INVITE="", STORE_URL=""), "STORE_URL") == ("#", None)


def test_launch_words_follow_daylight_saving_and_the_eastern_date():
    summer = site_links.launch_words(site_links.launch_time("2027-06-19T19:00:00-07:00"))
    assert summer == {"date": "Saturday 19 June 2027", "pacific": "7 PM Pacific", "eastern": "10 PM Eastern"}
    late = site_links.launch_words(site_links.launch_time("2026-11-22T06:00:00Z"))
    assert late == {"date": "Saturday 21 November 2026", "pacific": "10 PM Pacific", "eastern": "Sunday 1 AM Eastern"}
    noon = site_links.launch_words(site_links.launch_time("2026-12-01T20:00:00Z"))
    assert noon["pacific"] == "12 PM Pacific"
    half = site_links.launch_words(site_links.launch_time("2027-02-21T01:30:00+00:00"))
    assert half["pacific"] == "5:30 PM Pacific"


# What the built site writes for a link and a launch time (src/components/links.tsx), escaped as React does.
GOOD_LINKS = ('<a class="button" data-link="STORE_URL" href="https://discord.gg/abc" '
              f'title="{site_links.SOON}">Get a pass</a> '
              '<a data-link="MAP_URL" href="https://map.example.com/?a=1&amp;b=2">map</a>')
GOOD_LAUNCH = (f'<p class="when"><span>Season I launch</span> <time data-launch="{{date}}, {{pacific}} ({{eastern}})" '
               f'dateTime="{LAUNCH}">Saturday 21 November 2026<!-- -->, 5 PM Pacific (8 PM Eastern)</time></p>')


def test_a_page_that_says_what_config_json_does_passes():
    assert site_links.page_problems(GOOD_LINKS + GOOD_LAUNCH, links()) == []


def test_a_page_without_links_or_a_launch_needs_nothing():
    assert site_links.page_problems("<p>Nothing to launch.</p>", {}) == []


def test_a_link_built_from_an_old_config_is_reported():
    filled = links(STORE_URL="https://shop.example")
    assert site_links.page_problems(GOOD_LINKS, filled) == [
        'data-link="STORE_URL" goes to https://discord.gg/abc (title '
        f"'{site_links.SOON}'), but config.json says https://shop.example (title None)"]


def test_an_unknown_key_is_reported():
    assert site_links.page_problems('<a data-link="NOPE" href="#">x</a>', links()) == [
        'data-link="NOPE" is not set in config.json']


def test_a_launch_built_from_an_old_time_is_reported():
    moved = links(LAUNCH_AT="2027-02-21T01:30:00+00:00")
    assert site_links.page_problems(GOOD_LAUNCH, moved) == [
        '<time data-launch="{date}, {pacific} ({eastern})"> says "Saturday 21 November 2026, 5 PM Pacific '
        '(8 PM Eastern)", not "Saturday 20 February 2027, 5:30 PM Pacific (8:30 PM Eastern)"',
        f'<time data-launch="{{date}}, {{pacific}} ({{eastern}})"> has datetime="{LAUNCH}", '
        'not "2027-02-21T01:30:00+00:00"']


def test_text_around_a_launch_element_is_not_part_of_it():
    page = f'<p><time data-launch="{{date}}" dateTime="{LAUNCH}">Saturday 21 November 2026</time> at the spawn</p>'
    assert site_links.page_problems(page, links()) == []


def test_a_launch_template_can_only_use_known_words():
    assert site_links.page_problems('<span data-launch="{when}">x</span>', links()) == [
        'data-launch="{when}" can only use {date}, {pacific} and {eastern}']


def test_a_meta_tag_is_checked_by_its_content():
    meta = '<meta name="description" content="Season I launch: {}." data-launch="Season I launch: {{date}}.">'
    assert site_links.page_problems(meta.format("Saturday 21 November 2026"), links()) == []
    assert len(site_links.page_problems(meta.format("soon"), links())) == 1


def fake_site(tmp_path, pack_version="1.2.3", manifest_version="1.2.3", settings=None):
    repo = Repo(tmp_path)
    site = tmp_path / "site"
    (site / "public" / "pack").mkdir(parents=True)
    (site / "src" / "app").mkdir(parents=True)
    (site / "config.json").write_text(json.dumps(settings or SETTINGS), encoding="utf-8")
    (site / "src" / "app" / "style.css").write_text("body { color: green; }\n", encoding="utf-8")
    with zipfile.ZipFile(site / "public" / "pack" / "TheRealms-Client-1.2.3.mrpack", "w") as z:
        z.writestr("modrinth.index.json", json.dumps({"versionId": pack_version}))
    repo.manifest.parent.mkdir(parents=True)
    repo.manifest.write_text(json.dumps({"version": manifest_version}), encoding="utf-8")
    return repo


def test_check_reports_a_stale_wrapped_stylesheet_and_writing_fixes_it(tmp_path):
    repo = fake_site(tmp_path)
    assert site_links.problems(repo) == [
        "site/public/wrapped/site.css is not a copy of site/src/app/style.css (run python tools/site_links.py)"]
    assert site_links.main(["--check"], repo=repo) == 1
    assert site_links.main([], repo=repo) == 0
    assert site_links.main(["--check"], repo=repo) == 0
    copy = tmp_path / "site" / "public" / "wrapped" / "site.css"
    assert copy.read_text(encoding="utf-8") == "body { color: green; }\n"
    (tmp_path / "site" / "src" / "app" / "style.css").write_text("body { color: red; }\n", encoding="utf-8")
    assert site_links.main(["--check"], repo=repo) == 1


def test_the_served_pack_must_be_the_pinned_version(tmp_path):
    repo = fake_site(tmp_path, manifest_version="1.3.0")
    site_links.main([], repo=repo)
    [error] = site_links.problems(repo)
    assert "1.2.3 client pack, but the manifest is 1.3.0" in error
    assert "site/public/pack/" in error and "site/config.json" in error


def test_a_missing_pack_is_reported(tmp_path):
    repo = fake_site(tmp_path)
    site_links.main([], repo=repo)
    (tmp_path / "site" / "public" / "pack" / "TheRealms-Client-1.2.3.mrpack").unlink()
    assert site_links.problems(repo) == ["site: MODPACK_URL is pack/TheRealms-Client-1.2.3.mrpack, but "
                                         "site/public/pack/TheRealms-Client-1.2.3.mrpack doesn't exist"]


def test_a_pack_served_elsewhere_is_not_looked_for(tmp_path):
    repo = fake_site(tmp_path, settings=links(MODPACK_URL="https://modrinth.com/modpack/monkeysmp"))
    (tmp_path / "site" / "public" / "pack" / "TheRealms-Client-1.2.3.mrpack").unlink()
    site_links.main([], repo=repo)
    assert site_links.problems(repo) == []


def test_a_broken_config_is_reported_before_anything_else(tmp_path):
    repo = fake_site(tmp_path)
    (tmp_path / "site" / "config.json").write_text("{ not json", encoding="utf-8")
    [error] = site_links.problems(repo)
    assert error.startswith("site/config.json: ")
    (tmp_path / "site" / "config.json").write_text(json.dumps(links(LAUNCH_AT="soon")), encoding="utf-8")
    [error] = site_links.problems(repo)
    assert "LAUNCH_AT" in error


def test_built_checks_every_page(tmp_path):
    repo = fake_site(tmp_path)
    site_links.main([], repo=repo)
    out = tmp_path / "site" / "out"
    out.mkdir()
    assert site_links.main(["--check", "--built", str(out)], repo=repo) == 1
    for name in site_links.PAGES:
        (out / name).write_text(GOOD_LINKS + GOOD_LAUNCH, encoding="utf-8")
    assert site_links.main(["--check", "--built", str(out)], repo=repo) == 0
    (out / "guide.html").write_text(GOOD_LINKS.replace("discord.gg/abc", "discord.gg/old"), encoding="utf-8")
    [error] = site_links.problems(repo, built=out)
    assert error.startswith("out/guide.html: data-link=\"STORE_URL\" goes to https://discord.gg/old")


def test_a_repo_without_the_site_has_nothing_to_check(tmp_path):
    assert site_links.problems(Repo(tmp_path)) == []


def test_the_real_site_matches_its_config():
    assert site_links.problems(REPO) == []


def test_the_real_config_is_what_the_site_reads():
    # src/lib/config.ts imports config.json through the "@config" path in tsconfig.json.
    tsconfig = json.loads((site_links.site() / "tsconfig.json").read_text(encoding="utf-8"))
    assert tsconfig["compilerOptions"]["paths"]["@config"] == ["./config.json"]
    assert 'from "@config"' in (site_links.site() / "src" / "lib" / "config.ts").read_text(encoding="utf-8")
