import hashlib
import json
import zipfile

import pytest

import build
from repo import REPO


def test_build_outputs(tmp_path, real_manifest):
    server = build.build_server(real_manifest["version"], REPO, tmp_path)
    client = build.build_client(real_manifest["version"], REPO, tmp_path)
    names = zipfile.ZipFile(server).namelist()
    assert "TheRealms-Server/Start Server.bat" in names
    assert "TheRealms-Server/realms/manifest.json" in names
    assert "TheRealms-Server/realms/patches/silvers_effects-library/pack.mcmeta" in names
    assert not any(n.endswith((".jar", ".zip")) for n in names), "release must not bundle third-party files"
    index = json.loads(zipfile.ZipFile(client).read("modrinth.index.json"))
    assert index["versionId"] == real_manifest["version"]
    assert index["dependencies"]["minecraft"] == real_manifest["minecraft"]


def test_build_is_reproducible(tmp_path, real_manifest):
    hashes = []
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        for path in (build.build_server(real_manifest["version"], REPO, tmp_path / sub),
                     build.build_client(real_manifest["version"], REPO, tmp_path / sub)):
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
    assert hashes[:2] == hashes[2:]


def test_build_rejects_a_tag_that_differs_from_the_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_REF_NAME", "v9.9.9")
    with pytest.raises(SystemExit, match="doesn't match"):
        build.main(REPO, tmp_path / "dist")
    assert not (tmp_path / "dist").exists()
