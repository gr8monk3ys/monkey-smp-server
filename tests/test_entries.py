import copy
import hashlib

import pytest

import entries
from check_updates import LOADERS
from upstream import Upstream

MC = "26.1.2"
LUCKPERMS, INVENTORY, EFFECTS = "Vebnzrzj", "zJhgi9nK", "wBo7DRiB"


def by_number(recorded, project_id, number):
    kind = "plugin" if project_id == LUCKPERMS else "datapack"
    found = Upstream(recorded).modrinth_versions(project_id, MC, LOADERS[kind])
    return next(v for v in found if v["version_number"] == number)


def test_from_disk_records_the_name_found_on_disk(recorded):
    v = by_number(recorded, LUCKPERMS, "v5.5.53-bukkit")
    sha1 = v["files"][0]["hashes"]["sha1"]
    e = entries.from_disk(v, sha1, "luckperms", disk_name="renamed-by-host.jar")
    assert e == {"slug": "luckperms", "project_id": LUCKPERMS, "version": "v5.5.53-bukkit", "version_id": v["id"],
                 "file": "renamed-by-host.jar", "url": v["files"][0]["url"], "size": v["files"][0]["size"],
                 "hashes": {"sha512": v["files"][0]["hashes"]["sha512"]}}
    assert entries.check("plugin", e) == []


def test_update_gives_a_plugin_the_upstream_file_name(recorded):
    old = entries.from_disk(by_number(recorded, LUCKPERMS, "v5.5.53-bukkit"),
                            by_number(recorded, LUCKPERMS, "v5.5.53-bukkit")["files"][0]["hashes"]["sha1"],
                            "luckperms", disk_name="LuckPerms-Bukkit-5.5.53.jar")
    new = entries.updated("plugin", old, by_number(recorded, LUCKPERMS, "v5.5.71-bukkit"))
    assert new["file"] == "LuckPerms-Bukkit-5.5.71.jar"
    assert new["version"] == "v5.5.71-bukkit" and new["url"].endswith("LuckPerms-Bukkit-5.5.71.jar")


def test_update_keeps_a_datapack_on_disk_name(recorded):
    v11 = by_number(recorded, INVENTORY, "1.1")
    old = entries.from_disk(v11, v11["files"][0]["hashes"]["sha1"], "silvers_inventory-library",
                            disk_name=v11["files"][0]["filename"])
    new = entries.updated("datapack", old, by_number(recorded, INVENTORY, "1.2"))
    assert new["file"] == "Silver's Iventory Library - v.1.1.zip"  # the world refers to it by this name
    assert new["version"] == "1.2" and "v.1.2" in new["url"]


def test_update_refuses_a_patched_datapack(recorded):
    v27 = by_number(recorded, EFFECTS, "2.7")
    old = entries.from_disk(v27, v27["files"][0]["hashes"]["sha1"], "silvers_effects-library",
                            disk_name="effects.zip", patch={"path": "patches/x", "base_sha512": "a" * 128})
    with pytest.raises(ValueError, match="re-snapshot"):
        entries.updated("datapack", old, by_number(recorded, EFFECTS, "2.8"))


def test_pick_file_prefers_primary_with_same_extension():
    version = {"files": [
        {"filename": "x-sources.jar", "primary": False},
        {"filename": "x.jar", "primary": True},
        {"filename": "x.txt", "primary": False},
    ]}
    assert entries.pick_file(version, "old.jar")["filename"] == "x.jar"


def test_paper_and_java_entries_from_recorded_responses(recorded):
    up = Upstream(recorded)
    server = entries.paper(up.newest_stable_paper_build(MC))
    java = entries.java(up.adoptium_latest_jre(25))
    assert server["type"] == "paper" and server["file"].startswith("paper-26.1.2-")
    assert java["vendor"] == "Eclipse Temurin JRE" and java["file"].endswith(".zip")
    assert entries.check("server", server) == [] and entries.check("java", java) == []


@pytest.mark.parametrize("release", ["paper_manifest", "fabric_manifest"])
def test_every_artifact_of_a_release_has_a_strong_hash(request, release):
    manifest = request.getfixturevalue(release)
    kinds = set()
    for kind, entry in entries.artifacts(manifest):
        algo, value = entries.hash_of(entry)
        assert algo in ("sha256", "sha512") and value
        kinds.add(kind)
    assert kinds == {"paper_manifest": {"java", "server", "plugin", "datapack"},
                     "fabric_manifest": {"java", "server", "mod"}}[release]


def test_matches_checks_size_and_strongest_hash():
    data = b"artifact bytes"
    entry = {"file": "a.jar", "size": len(data), "hashes": {"sha512": hashlib.sha512(data).hexdigest(),
                                                            "sha256": "not checked when sha512 is there"}}
    assert entries.matches(entry, data)
    assert not entries.matches(entry, data + b"!")
    assert not entries.matches({**entry, "size": 1}, data)


MISTAKES = [
    (lambda e: e.update(url="http://evil.example/x.jar"), "allowed host"),
    (lambda e: e.update(hashes={"sha512": "ABC"}), "lowercase hex"),
    (lambda e: e.update(hashes={"md5": "abc"}), "no sha512/sha256"),
    (lambda e: e.update(size=0), "bad size"),
    (lambda e: e.pop("version_id"), "missing 'version_id'"),
    (lambda e: e.update(file="bad:name.jar"), "characters Windows"),
]


@pytest.mark.parametrize("kind, mutate, message", [
    *[("plugin", mutate, message) for mutate, message in MISTAKES],
    ("plugin", lambda e: e.update(patch={"path": "patches/x", "base_sha512": "a" * 128}), "only mods and datapacks"),
    ("datapack", lambda e: e.update(file="bad:name.zip"), "characters Windows"),
])
def test_check_catches_mistakes_in_paper_entries(paper_manifest, kind, mutate, message):
    e = copy.deepcopy(entries.group(paper_manifest, kind)[0])
    assert entries.check(kind, e) == []
    mutate(e)
    errors = entries.check(kind, e)
    assert any(message in x for x in errors), errors


@pytest.mark.parametrize("mutate, message", MISTAKES)
def test_check_catches_mistakes_in_mod_entries(fabric_manifest, mutate, message):
    e = copy.deepcopy(fabric_manifest["mods"][0])
    assert entries.check("mod", e) == []
    mutate(e)
    errors = entries.check("mod", e)
    assert any(message in x for x in errors), errors


@pytest.mark.parametrize("release, mutate, message", [
    ("paper_manifest", lambda s: s.pop("build"), "integer 'build'"),
    ("paper_manifest", lambda s: s.update(url="https://example.com/paper.jar"), "allowed host"),
    ("fabric_manifest", lambda s: s.pop("installer"), "needs 'installer'"),
    ("fabric_manifest", lambda s: s.update(hashes={"sha256": "x"}), "lowercase hex"),
    ("fabric_manifest", lambda s: s.update(type="quilt"), "type must be one of"),
])
def test_check_catches_mistakes_in_server_entries(request, release, mutate, message):
    server = copy.deepcopy(request.getfixturevalue(release)["server"])
    assert entries.check("server", server) == []
    mutate(server)
    errors = entries.check("server", server)
    assert any(message in x for x in errors), errors


def test_fabric_server_entry_pins_the_downloaded_launcher():
    jar = b"launcher bytes"
    e = entries.fabric("26.3", "0.19.5", "1.1.2", jar)
    assert e == {"type": "fabric", "loader": "0.19.5", "installer": "1.1.2",
                 "file": "fabric-server-mc.26.3-loader.0.19.5-launcher.1.1.2.jar",
                 "url": "https://meta.fabricmc.net/v2/versions/loader/26.3/0.19.5/1.1.2/server/jar",
                 "size": len(jar), "hashes": {"sha256": hashlib.sha256(jar).hexdigest()}}
    assert entries.check("server", e) == [] and entries.matches(e, jar)


def test_mods_name_files_like_plugins(recorded):
    v53, v71 = by_number(recorded, LUCKPERMS, "v5.5.53-bukkit"), by_number(recorded, LUCKPERMS, "v5.5.71-bukkit")
    old = entries.from_disk(v53, v53["files"][0]["hashes"]["sha1"], "luckperms", disk_name="renamed.jar")
    assert entries.updated("mod", old, v71)["file"] == "LuckPerms-Bukkit-5.5.71.jar"
    patched = {**old, "patch": {"path": "patches/luckperms", "base_sha512": old["hashes"]["sha512"]}}
    assert entries.check("mod", patched) == []
    with pytest.raises(ValueError, match="re-snapshot"):
        entries.updated("mod", patched, v71)


def test_with_all_groups_adds_mods_after_plugins():
    m = {"name": "x", "plugins": [], "datapacks": [], "world": {}}
    assert list(entries.with_all_groups(m)) == ["name", "plugins", "mods", "datapacks", "world"]
    assert entries.with_all_groups(m)["mods"] == [] and "mods" not in m
    full = {"plugins": [], "mods": [1], "datapacks": []}
    assert entries.with_all_groups(full) is full
    assert entries.group({"plugins": []}, "mod") == []


@pytest.mark.parametrize("server_type, allowed", [
    ("paper", {"plugin", "datapack"}), ("fabric", {"mod", "datapack"}), ("forge", set()),
])
def test_kind_allowed(server_type, allowed):
    assert {k for k in entries.GROUPS if entries.kind_allowed(server_type, k)} == allowed
