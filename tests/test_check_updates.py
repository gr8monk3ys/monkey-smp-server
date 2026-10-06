"""The update check, against responses recorded from the live APIs.

The Paper test manifest (the frozen 1.1.0 release, re-pinned) pins real projects to older real
versions, so every "newer" release here is one that actually exists upstream. The Fabric tests start
from the frozen 2.0.0 release with the recorded Fabric meta and mods built in the test.
"""
import copy
import hashlib

import pytest
from conftest import paper_builds_url, serve_fabric_launcher

import check_updates
import entries
import patches
import validate
from check_updates import LOADERS, NEEDS_PATCH
from repo import Repo
from upstream import MODRINTH, Upstream, json_query

MC = "26.1.2"
LUCKPERMS, INVENTORY, EFFECTS = "Vebnzrzj", "zJhgi9nK", "wBo7DRiB"


def pinned(up, project_id, kind, slug, number, **kw):
    v = next(v for v in up.modrinth_versions(project_id, MC, LOADERS[kind]) if v["version_number"] == number)
    return entries.from_disk(v, v["files"][0]["hashes"]["sha1"], slug, disk_name=v["files"][0]["filename"], **kw)


def make_manifest(up, base, *, paper=72, luckperms="v5.5.53-bukkit", inventory="1.1", effects="2.7"):
    m = copy.deepcopy(base)
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
def old(up, paper_manifest):
    return make_manifest(up, paper_manifest)


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


def test_no_updates_when_everything_is_newest(up, paper_manifest):
    m = make_manifest(up, paper_manifest, paper=74, luckperms="v5.5.71-bukkit", inventory="1.2", effects="2.8")
    assert check_updates.find_updates(m, up) == []
    assert "newest stable" in check_updates.report(m, [])


def test_main_apply_writes_a_valid_manifest_and_counts_all_updates(up, old, paper_repo, tmp_path, monkeypatch):
    paper_repo.save_manifest(old)
    out, gh = tmp_path / "report.md", tmp_path / "gh_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(gh))
    check_updates.main(["--apply", "--out", str(out)], repo=paper_repo, upstream=up)

    saved = paper_repo.load_manifest()
    assert saved["server"]["build"] == 74
    assert next(d for d in saved["datapacks"] if "patch" in d)["version"] == "2.7"
    assert validate.validate(saved, paper_repo) == []  # patch still consistent with its pin
    assert "re-snapshot needed" in out.read_text()
    assert gh.read_text() == "count=4\n"


# --- re-listed files and pre-release pins -------------------------------------------------------

def _version(vid, number, channel, date, data: bytes, name="Plugin.jar"):
    return {"id": vid, "project_id": "id-plug", "version_number": number, "version_type": channel,
            "date_published": date,
            "files": [{"filename": name, "primary": True, "size": len(data),
                       "url": f"https://cdn.modrinth.com/data/id-plug/versions/{vid}/{name}",
                       "hashes": {"sha1": hashlib.sha1(data).hexdigest(),
                                  "sha512": hashlib.sha512(data).hexdigest()}}]}


def _only_plugin(up, paper_manifest, pinned_version, listed):
    """A manifest whose only update candidate is one plugin, with `listed` as its Modrinth versions."""
    m = make_manifest(up, paper_manifest, paper=74)
    m["plugins"] = [entries.from_disk(pinned_version, pinned_version["files"][0]["hashes"]["sha1"], "plug",
                                      disk_name="Plugin.jar")]
    m["datapacks"] = []
    url = f"{MODRINTH}/project/id-plug/version?game_versions={json_query([MC])}&loaders={json_query(LOADERS['plugin'])}"
    up.http.add("GET", url, listed)
    return m


def test_same_file_listed_under_a_new_version_id_is_not_an_update(up, paper_manifest):
    pinned_v = _version("old-id", "6.2.0", "release", "2026-09-10T00:00:00Z", b"tab 6.2.0")
    relisted = _version("new-id", "6.2.0", "release", "2026-09-17T00:00:00Z", b"tab 6.2.0")
    m = _only_plugin(up, paper_manifest, pinned_v, [relisted])  # the pinned id is gone upstream
    assert check_updates.find_updates(m, up) == []


def test_a_pre_release_pin_is_not_downgraded_to_an_older_release(up, paper_manifest):
    beta = _version("beta", "2.12.1+377", "beta", "2026-09-28T00:00:00Z", b"npcs beta 377")
    release = _version("rel", "2.12.1", "release", "2026-09-21T00:00:00Z", b"npcs 2.12.1")
    m = _only_plugin(up, paper_manifest, beta, [beta, release])
    assert check_updates.find_updates(m, up) == []


def test_a_release_after_the_pre_release_pin_is_an_update(up, paper_manifest):
    beta = _version("beta", "2.12.1+377", "beta", "2026-09-28T00:00:00Z", b"npcs beta 377")
    newer = _version("rel2", "2.12.2", "release", "2026-10-02T00:00:00Z", b"npcs 2.12.2", "Plugin-2.12.2.jar")
    m = _only_plugin(up, paper_manifest, beta, [newer, beta])
    (update,) = check_updates.find_updates(m, up)
    assert (update.pinned, update.newest, update.entry["file"]) == ("2.12.1+377", "2.12.2", "Plugin-2.12.2.jar")


# --- Fabric: loader/installer from recorded Fabric meta, mods built in the test ----------------------

FABRIC_MC = "26.3"  # recorded meta: newest stable loader 0.19.5, newest stable installer 1.1.2


def _mods_url(project_id):
    return (f"{MODRINTH}/project/{project_id}/version?game_versions={json_query([FABRIC_MC])}"
            f"&loaders={json_query(LOADERS['mod'])}")


def _mod_version(project_id, vid, number, date, name):
    data = f"{project_id} {number}".encode()
    return {"id": vid, "project_id": project_id, "version_number": number, "version_type": "release",
            "date_published": date,
            "files": [{"filename": name, "primary": True, "size": len(data),
                       "url": f"https://cdn.modrinth.com/data/{project_id}/versions/{vid}/{name}",
                       "hashes": {"sha1": hashlib.sha1(data).hexdigest(),
                                  "sha512": hashlib.sha512(data).hexdigest()}}]}


def fabric_pins(up, base, loader="0.19.5", installer="1.1.2", mods=()):
    """A Fabric manifest pinned to `loader`/`installer`; each mod is (slug, pinned, listed, patched)."""
    m = copy.deepcopy(base)
    m.update(minecraft=FABRIC_MC, server=entries.fabric(FABRIC_MC, loader, installer, b"pinned launcher"),
             plugins=[], mods=[], datapacks=[])
    for slug, pinned_v, listed, patched in mods:
        e = entries.from_disk(pinned_v, pinned_v["files"][0]["hashes"]["sha1"], slug,
                              disk_name=pinned_v["files"][0]["filename"])
        if patched:
            e["patch"] = patches.reference(slug, e["hashes"]["sha512"])
        m["mods"].append(e)
        up.http.add("GET", _mods_url(pinned_v["project_id"]), listed)
    return m


@pytest.mark.parametrize("loader, installer, newest", [
    ("0.19.4", "1.1.2", "loader 0.19.5, installer 1.1.2"),  # newer loader
    ("0.19.5", "1.1.1", "loader 0.19.5, installer 1.1.2"),  # newer installer
    ("0.19.3", "1.0.3", "loader 0.19.5, installer 1.1.2"),  # both: still one server update
])
def test_fabric_server_update_pins_the_new_launcher(up, fabric_manifest, loader, installer, newest):
    jar = serve_fabric_launcher(up.http, FABRIC_MC, "0.19.5", "1.1.2")
    m = fabric_pins(up, fabric_manifest, loader, installer)
    (update,) = check_updates.find_updates(m, up)
    assert (update.kind, update.slug) == ("server", "fabric")
    assert (update.pinned, update.newest) == (f"loader {loader}, installer {installer}", newest)
    assert update.entry == entries.fabric(FABRIC_MC, "0.19.5", "1.1.2", jar)
    new = check_updates.apply(m, [update])
    assert new["server"]["file"] == "fabric-server-mc.26.3-loader.0.19.5-launcher.1.1.2.jar"
    assert entries.check("server", new["server"]) == [] and entries.check_types(new) == []


def test_fabric_server_is_not_downgraded_or_updated_when_newest(up, fabric_manifest):
    assert check_updates.find_updates(fabric_pins(up, fabric_manifest), up) == []
    ahead = fabric_pins(up, fabric_manifest, loader="0.19.10", installer="1.2.0")  # pre-release pins
    assert check_updates.find_updates(ahead, up) == []


def test_fabric_mod_update_takes_the_new_file_name_and_patched_mods_are_left(up, fabric_manifest, tmp_path):
    old_mod = _mod_version("id-lith", "l1", "0.26.1", "2026-09-01T00:00:00Z", "lithium-fabric-0.26.1+mc26.3.jar")
    new_mod = _mod_version("id-lith", "l2", "0.26.2", "2026-09-20T00:00:00Z", "lithium-fabric-0.26.2+mc26.3.jar")
    old_fx = _mod_version("id-fx", "f1", "2.7", "2026-09-01T00:00:00Z", "silvers_effects-library-2.7.jar")
    new_fx = _mod_version("id-fx", "f2", "2.8", "2026-09-20T00:00:00Z", "silvers_effects-library-2.8.jar")
    m = fabric_pins(up, fabric_manifest, mods=[("lithium", old_mod, [new_mod, old_mod], False),
                                                 ("silvers_effects-library", old_fx, [new_fx, old_fx], True)])
    updates = by_slug(check_updates.find_updates(m, up))
    assert set(updates) == {"lithium", "silvers_effects-library"}
    lith, fx = updates["lithium"], updates["silvers_effects-library"]
    assert (lith.kind, lith.entry["version"]) == ("mod", "0.26.2")
    assert lith.entry["file"] == "lithium-fabric-0.26.2+mc26.3.jar"  # upstream's new name, like a plugin
    assert (fx.kind, fx.entry, fx.note, fx.newest) == ("mod", None, NEEDS_PATCH, "2.8")

    new = check_updates.apply(m, list(updates.values()))
    assert new["mods"][0]["version"] == "0.26.2" and new["mods"][1] == m["mods"][1]
    assert "| mod | silvers_effects-library | 2.7 | 2.8 | patched - re-snapshot needed |" in check_updates.report(
        m, list(updates.values()))
    # The applied manifest is still consistent: the patch stays pinned to the file it was made against.
    repo = Repo(tmp_path)
    patches.write(repo.patches / "silvers_effects-library", {"pack.mcmeta": b"patched"})
    assert validate.validate(new, repo) == []


def test_main_apply_on_the_fabric_release_keeps_patched_mods_and_stays_valid(up, fabric_repo, tmp_path, monkeypatch):
    """The frozen 2.0.0 release, cut down to its two patched mods plus one mod with an update."""
    m = fabric_repo.load_manifest()
    patched = [e for e in m["mods"] if "patch" in e]
    for e in patched:  # upstream has a newer release of each patched mod
        newer = _mod_version(e["project_id"], f"new-{e['slug']}", "99.0", "2099-01-01T00:00:00Z", f"{e['slug']}-99.jar")
        up.http.add("GET", _mods_url(e["project_id"]), [newer])
    old_mod = _mod_version("id-lith", "l1", "0.26.1", "2026-09-01T00:00:00Z", "lithium-0.26.1.jar")
    new_mod = _mod_version("id-lith", "l2", "0.26.2", "2026-09-20T00:00:00Z", "lithium-0.26.2.jar")
    up.http.add("GET", _mods_url("id-lith"), [new_mod, old_mod])
    m["mods"] = sorted(patched + [entries.from_disk(old_mod, old_mod["files"][0]["hashes"]["sha1"], "lithium",
                                                    disk_name="lithium-0.26.1.jar")], key=lambda e: e["slug"])
    fabric_repo.save_manifest(m)
    out, gh = tmp_path / "report.md", tmp_path / "gh_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(gh))
    check_updates.main(["--apply", "--out", str(out)], repo=fabric_repo, upstream=up)

    saved = fabric_repo.load_manifest()
    assert saved["server"] == m["server"]  # 0.19.5 / 1.1.2 are the newest stable in the recorded meta
    assert [e for e in saved["mods"] if "patch" in e] == patched
    assert next(e for e in saved["mods"] if e["slug"] == "lithium")["file"] == "lithium-0.26.2.jar"
    assert validate.validate(saved, fabric_repo) == []
    assert out.read_text().count("re-snapshot needed") == 2
    assert gh.read_text() == "count=3\n"
