import hashlib
import json
import zipfile

import pytest

import build

RELEASES = ["paper_repo", "fabric_repo"]


@pytest.mark.parametrize("release", RELEASES)
def test_build_outputs(tmp_path, request, release):
    repo = request.getfixturevalue(release)
    manifest = repo.load_manifest()
    server = build.build_server(manifest["version"], repo, tmp_path)
    client = build.build_client(manifest["version"], repo, tmp_path)
    names = zipfile.ZipFile(server).namelist()
    assert "TheRealms-Server/Start Server.bat" in names
    assert "TheRealms-Server/realms/manifest.json" in names
    assert "TheRealms-Server/realms/patches/silvers_effects-library/pack.mcmeta" in names
    assert not any(n.endswith((".jar", ".zip")) for n in names), "release must not bundle third-party files"
    index = json.loads(zipfile.ZipFile(client).read("modrinth.index.json"))
    assert index["versionId"] == manifest["version"]
    assert index["dependencies"]["minecraft"] == manifest["minecraft"]


def test_build_ships_every_patch_of_a_fabric_release(tmp_path, fabric_repo):
    names = zipfile.ZipFile(build.build_server("2.0.0", fabric_repo, tmp_path)).namelist()
    assert {n for n in names if "/patches/" in n} == {
        "TheRealms-Server/realms/patches/silvers_effects-library/pack.mcmeta",
        "TheRealms-Server/realms/patches/silvers_strength-restrictions/pack.mcmeta"}


@pytest.mark.parametrize("release", RELEASES)
def test_build_is_reproducible(tmp_path, request, release):
    repo = request.getfixturevalue(release)
    version = repo.load_manifest()["version"]
    hashes = []
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        for path in (build.build_server(version, repo, tmp_path / sub),
                     build.build_client(version, repo, tmp_path / sub)):
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
    assert hashes[:2] == hashes[2:]


def test_build_rejects_a_tag_that_differs_from_the_manifest(tmp_path, monkeypatch, paper_repo):
    monkeypatch.setenv("GITHUB_REF_NAME", "v9.9.9")
    with pytest.raises(SystemExit, match="doesn't match"):
        build.main(paper_repo, tmp_path / "dist")
    assert not (tmp_path / "dist").exists()
