import hashlib
import io
import json
import zipfile

import pytest
from conftest import PLAYER_FILES, fake_player

import build
from repo import REPO

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
    fake_player(repo)
    version = repo.load_manifest()["version"]
    hashes = []
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        mrpack = build.build_client(version, repo, tmp_path / sub)
        for path in (build.build_server(version, repo, tmp_path / sub), mrpack,
                     build.build_player(version, mrpack, repo, tmp_path / sub)):
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
    assert hashes[:3] == hashes[3:]


def test_build_rejects_a_tag_that_differs_from_the_manifest(tmp_path, monkeypatch, paper_repo):
    monkeypatch.setenv("GITHUB_REF_NAME", "v9.9.9")
    with pytest.raises(SystemExit, match="doesn't match"):
        build.main(paper_repo, tmp_path / "dist")
    assert not (tmp_path / "dist").exists()


# --- the player zip --------------------------------------------------------------------------------

def test_build_player_zip(tmp_path, fabric_repo):
    player = fake_player(fabric_repo)
    mrpack = build.build_client("2.0.0", fabric_repo, tmp_path)
    out = build.build_player("2.0.0", mrpack, fabric_repo, tmp_path)

    assert out.name == "TheRealms-Player-2.0.0.zip"
    z = zipfile.ZipFile(out)
    top = "TheRealms-Player-2.0.0/"
    added = ["TheRealms-Client-2.0.0.mrpack", "installer/fabric-profile.json"]
    assert z.namelist() == sorted(top + name for name in [*player, *added])
    assert z.read(top + "TheRealms-Client-2.0.0.mrpack") == mrpack.read_bytes()
    assert z.read(top + "installer/fabric-profile.json") == fabric_repo.fabric_profile.read_bytes()
    assert all(z.read(top + name) == data for name, data in player.items())
    assert {i.date_time for i in z.infolist()} == {build.EPOCH}


def test_build_main_writes_all_three_files(tmp_path, fabric_repo, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    fake_player(fabric_repo)
    build.main(fabric_repo, tmp_path / "dist")
    assert sorted(p.name for p in (tmp_path / "dist").iterdir()) == [
        "TheRealms-Client-2.0.0.mrpack", "TheRealms-Player-2.0.0.zip", "TheRealms-Server-2.0.0.zip"]
    out = capsys.readouterr().out
    assert all(name in out for name in ("TheRealms-Server-2.0.0.zip", "TheRealms-Client-2.0.0.mrpack",
                                        "TheRealms-Player-2.0.0.zip"))


def test_build_fails_clearly_without_player_folder(tmp_path, fabric_repo, monkeypatch):
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    assert not fabric_repo.player.exists()
    with pytest.raises(SystemExit, match="player.* is missing"):
        build.main(fabric_repo, tmp_path / "dist")
    assert not (tmp_path / "dist").exists(), "nothing is built when the player zip can't be"
    mrpack = build.build_client("2.0.0", fabric_repo, tmp_path)
    with pytest.raises(SystemExit, match="player.* is missing"):
        build.build_player("2.0.0", mrpack, fabric_repo, tmp_path)


def test_build_player_needs_the_launcher_profile(tmp_path, fabric_repo):
    fake_player(fabric_repo)
    fabric_repo.fabric_profile.unlink()
    mrpack = build.build_client("2.0.0", fabric_repo, tmp_path)
    with pytest.raises(SystemExit, match="fabric-profile.json is missing"):
        build.build_player("2.0.0", mrpack, fabric_repo, tmp_path)


def test_build_player_refuses_files_it_would_overwrite(tmp_path, fabric_repo):
    fake_player(fabric_repo, {**PLAYER_FILES, "installer/fabric-profile.json": "{}"})
    mrpack = build.build_client("2.0.0", fabric_repo, tmp_path)
    with pytest.raises(SystemExit, match="must not contain installer/fabric-profile.json"):
        build.build_player("2.0.0", mrpack, fabric_repo, tmp_path)


# --- Linux and macOS ---------------------------------------------------------------------------------

def test_build_marks_sh_launchers_executable_and_is_made_on_unix(tmp_path, fabric_repo):
    z = zipfile.ZipFile(build.build_server("2.0.0", fabric_repo, tmp_path))
    modes = {i.filename.split("/", 1)[1]: (i.external_attr >> 16) & 0o777 for i in z.infolist()}
    for name in ("start.sh", "stop.sh", "backup.sh", "add-player.sh", "prepare-for-hosting.sh",
                 "Start Server.command", "realms/realms.sh"):
        assert modes[name] == 0o755, name
    assert modes["Start Server.bat"] == modes["realms/pwsh.lock"] == modes["realms/manifest.json"] == 0o644
    assert {i.create_system for i in z.infolist()} == {3}
    assert b"\r" not in z.read("TheRealms-Server/start.sh")


def test_build_leaves_out_what_a_local_install_or_docker_left_in_package(tmp_path, fabric_repo):
    pkg = fabric_repo.package
    for junk in ("server/server.properties", "java/linux-x64/jdk/bin/java", "pwsh/linux-x64/p/pwsh", "backups/x/a",
                 "exports/TheRealms-2.0.0-hosting.zip", "downloads/a.part", ".realms-launch", "smoke-console.log.err",
                 "docker/.env"):
        (pkg / junk).parent.mkdir(parents=True, exist_ok=True)
        (pkg / junk).write_text("junk")
    (pkg / "docker" / "entrypoint.sh").write_text("#!/bin/sh\n")
    z = zipfile.ZipFile(build.build_server("2.0.0", fabric_repo, tmp_path))
    names = {n.split("/", 1)[1] for n in z.namelist()}
    assert not {n for n in names if n.split("/")[0] in build.RUNTIME_DIRS or n in (".realms-launch", "docker/.env")
                or n.startswith("smoke-console")}
    assert "docker/entrypoint.sh" in names
    assert (z.getinfo("TheRealms-Server/docker/entrypoint.sh").external_attr >> 16) & 0o777 == 0o755


# --- the world seed --------------------------------------------------------------------------------

def _members(z: zipfile.ZipFile):
    """(name, bytes) of every file, including the files inside a zipped .mrpack."""
    for name in z.namelist():
        data = z.read(name)
        if name.endswith(".mrpack"):
            yield from ((f"{name}/{inner}", d) for inner, d in _members(zipfile.ZipFile(io.BytesIO(data))))
        else:
            yield name, data


def test_nothing_players_get_contains_the_world_seed(tmp_path):
    """The seed shows where every ore and structure is (seed-based x-ray), so only the server zip has it."""
    seed = REPO.load_manifest()["world"]["seed"].lstrip("-").encode()
    mrpack = build.build_client("0.0.0", REPO, tmp_path)
    player = build.build_player("0.0.0", mrpack, REPO, tmp_path)
    for out in (mrpack, player):
        assert not [name for name, data in _members(zipfile.ZipFile(out)) if seed in data], out.name
    server = zipfile.ZipFile(build.build_server("0.0.0", REPO, tmp_path))
    assert seed in server.read("TheRealms-Server/realms/manifest.json")  # the check can see it where it is
    public = [*REPO.root.joinpath("site").rglob("*"), REPO.root / "docs" / "RULES.md"]
    assert not [p for p in public if p.is_file() and seed in p.read_bytes()]
