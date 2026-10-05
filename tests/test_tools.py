import copy
import json
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import build  # noqa: E402
import check_updates  # noqa: E402
import common  # noqa: E402
import validate  # noqa: E402


@pytest.fixture
def manifest():
    return common.load_manifest()


def test_repo_manifest_is_valid(manifest):
    assert validate.validate(manifest) == []
    assert validate.validate_package() == []
    assert validate.validate_client(manifest) == []


def test_every_artifact_has_a_strong_hash(manifest):
    for _, entry in common.artifacts(manifest):
        algo, value = common.hash_of(entry)
        assert algo in ("sha256", "sha512") and value


@pytest.mark.parametrize("mutate, message", [
    (lambda m: m["plugins"][0].update(url="http://evil.example/x.jar"), "allowed host"),
    (lambda m: m["plugins"][0].update(hashes={"sha512": "ABC"}), "lowercase hex"),
    (lambda m: m["plugins"].append(copy.deepcopy(m["plugins"][0])), "duplicate"),
    (lambda m: m["datapacks"][0].update(file="bad:name.zip"), "characters Windows"),
    (lambda m: m["world"].update(seed="abc"), "seed"),
    (lambda m: m.update(version="1.0"), "1.2.3"),
    (lambda m: m["datapacks"][0].update(patch="patches/does-not-exist"), "missing or empty"),
])
def test_validate_catches_mistakes(manifest, mutate, message):
    mutate(manifest)
    errors = validate.validate(manifest)
    assert any(message in e for e in errors), errors


def test_build_outputs(tmp_path, monkeypatch, manifest):
    monkeypatch.setattr(build, "DIST", str(tmp_path))
    server = build.build_server(manifest["version"])
    client = build.build_client(manifest["version"])
    names = zipfile.ZipFile(server).namelist()
    assert "TheRealms-Server/Start Server.bat" in names
    assert "TheRealms-Server/realms/manifest.json" in names
    assert not any(n.endswith((".jar", ".zip")) for n in names), "release must not bundle third-party files"
    index = json.loads(zipfile.ZipFile(client).read("modrinth.index.json"))
    assert index["versionId"] == manifest["version"]
    assert index["dependencies"]["minecraft"] == manifest["minecraft"]


def test_build_is_reproducible(tmp_path, monkeypatch, manifest):
    hashes = []
    for sub in ("a", "b"):
        monkeypatch.setattr(build, "DIST", str(tmp_path / sub))
        os.makedirs(tmp_path / sub)
        hashes.append(common.digest(open(build.build_server(manifest["version"]), "rb").read(), "sha256"))
    assert hashes[0] == hashes[1]


def test_build_rejects_mismatched_tag(monkeypatch):
    monkeypatch.setenv("GITHUB_REF_NAME", "v9.9.9")
    with pytest.raises(SystemExit):
        build.main()


def test_apply_updates_keeps_datapack_file_name(manifest):
    pack = manifest["datapacks"][0]
    plugin = manifest["plugins"][0]
    updates = [
        ("datapacks", pack["slug"], pack["version"], "new", {**pack, "version": "new", "file": pack["file"]}),
        ("plugins", plugin["slug"], plugin["version"], "new", {**plugin, "version": "new", "file": "new.jar"}),
    ]
    saved = {}
    original = check_updates.save_manifest
    check_updates.save_manifest = lambda m: saved.update(m=m)
    try:
        check_updates.apply(manifest, updates)
    finally:
        check_updates.save_manifest = original
    m = saved["m"]
    assert m["datapacks"][0]["version"] == "new" and m["datapacks"][0]["file"] == pack["file"]
    assert m["plugins"][0]["file"] == "new.jar"


def test_report_without_updates(manifest):
    assert "newest stable" in check_updates.report(manifest, [])


def test_pick_file_prefers_primary_with_same_extension():
    version = {"files": [
        {"filename": "x-sources.jar", "primary": False},
        {"filename": "x.jar", "primary": True},
        {"filename": "x.txt", "primary": False},
    ]}
    assert check_updates.pick_file(version, "old.jar")["filename"] == "x.jar"
