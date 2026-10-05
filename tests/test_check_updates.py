"""The update check, against responses recorded from the live APIs.

The test manifest pins real projects to older real versions, so every "newer" release here is one
that actually exists upstream.
"""
import copy

import pytest
from conftest import paper_builds_url

import check_updates
import entries
import patches
import validate
from check_updates import LOADERS, NEEDS_PATCH
from upstream import Upstream

MC = "26.1.2"
LUCKPERMS, INVENTORY, EFFECTS = "Vebnzrzj", "zJhgi9nK", "wBo7DRiB"


def pinned(up, project_id, kind, slug, number, **kw):
    v = next(v for v in up.modrinth_versions(project_id, MC, LOADERS[kind]) if v["version_number"] == number)
    return entries.from_disk(v, v["files"][0]["hashes"]["sha1"], slug, disk_name=v["files"][0]["filename"], **kw)


def make_manifest(up, real, *, paper=72, luckperms="v5.5.53-bukkit", inventory="1.1", effects="2.7"):
    m = copy.deepcopy(real)
    build = next(b for b in up.paper_builds(MC) if b["id"] == paper)
    m["server"] = entries.paper(build)
    m["plugins"] = [pinned(up, LUCKPERMS, "plugin", "luckperms", luckperms)]
    effects_entry = pinned(up, EFFECTS, "datapack", "silvers_effects-library", effects)
    effects_entry["patch"] = patches.reference("silvers_effects-library", effects_entry["hashes"]["sha512"])
    m["datapacks"] = [pinned(up, INVENTORY, "datapack", "silvers_inventory-library", inventory), effects_entry]
    return m


@pytest.fixture
def up(recorded):
    return Upstream(recorded)


@pytest.fixture
def old(up, real_manifest):
    return make_manifest(up, real_manifest)


def by_slug(updates):
    return {u.slug: u for u in updates}


def test_finds_every_newer_stable_build(up, old):
    found = by_slug(check_updates.find_updates(old, up))
    assert set(found) == {"paper", "luckperms", "silvers_inventory-library", "silvers_effects-library"}
    assert (found["paper"].pinned, found["paper"].newest) == ("72", "74")
    assert found["silvers_inventory-library"].newest == "1.2"  # 1.0 is an alpha and older anyway


def test_newest_stable_paper_build_is_picked_regardless_of_order(recorded, old):
    builds = recorded.get_json(paper_builds_url(MC))
    recorded.add("GET", paper_builds_url(MC), sorted(builds, key=lambda b: b["id"]))  # oldest first
    server = by_slug(check_updates.find_updates(old, Upstream(recorded)))["paper"]
    assert server.entry["build"] == 74 and server.entry["file"] == "paper-26.1.2-74.jar"


def test_plugin_update_takes_the_new_file_name(up, old):
    entry = by_slug(check_updates.find_updates(old, up))["luckperms"].entry
    assert entry["file"] == "LuckPerms-Bukkit-5.5.71.jar" and entry["version"] == "v5.5.71-bukkit"


def test_datapack_update_keeps_the_on_disk_name(up, old):
    entry = by_slug(check_updates.find_updates(old, up))["silvers_inventory-library"].entry
    assert entry["file"] == "Silver's Iventory Library - v.1.1.zip"
    assert entry["version"] == "1.2" and "v.1.2" in entry["url"]


def test_patched_datapack_is_reported_but_not_applied(up, old):
    updates = check_updates.find_updates(old, up)
    effects = by_slug(updates)["silvers_effects-library"]
    assert effects.entry is None and effects.note == NEEDS_PATCH and effects.newest == "2.8"

    new = check_updates.apply(old, updates)
    assert new["datapacks"][1] == old["datapacks"][1]  # pin, hash and patch all stay on 2.7
    assert new["plugins"][0]["version"] == "v5.5.71-bukkit" and new["server"]["build"] == 74
    assert old["plugins"][0]["version"] == "v5.5.53-bukkit", "apply must not mutate its input"

    text = check_updates.report(old, updates)
    assert "| datapack | silvers_effects-library | 2.7 | 2.8 | patched - re-snapshot needed |" in text


def test_no_updates_when_everything_is_newest(up, real_manifest):
    m = make_manifest(up, real_manifest, paper=74, luckperms="v5.5.71-bukkit", inventory="1.2", effects="2.8")
    assert check_updates.find_updates(m, up) == []
    assert "newest stable" in check_updates.report(m, [])


def test_main_apply_writes_a_valid_manifest_and_counts_all_updates(up, old, repo_copy, tmp_path, monkeypatch):
    repo_copy.save_manifest(old)
    out, gh = tmp_path / "report.md", tmp_path / "gh_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(gh))
    check_updates.main(["--apply", "--out", str(out)], repo=repo_copy, upstream=up)

    saved = repo_copy.load_manifest()
    assert saved["server"]["build"] == 74
    assert next(d for d in saved["datapacks"] if "patch" in d)["version"] == "2.7"
    assert validate.validate(saved, repo_copy) == []  # patch still consistent with its pin
    assert "re-snapshot needed" in out.read_text()
    assert gh.read_text() == "count=4\n"
