import hashlib
import zipfile

import pytest

import build
import checksums
from repo import REPO

RELEASES = ["paper_repo", "fabric_repo"]


@pytest.mark.parametrize("release", RELEASES)
def test_build_outputs(tmp_path, request, release):
    repo = request.getfixturevalue(release)
    manifest = repo.load_manifest()
    server = build.build_server(manifest["version"], repo, tmp_path)
    names = zipfile.ZipFile(server).namelist()
    assert "MonkeySMP-Server/Start Server.bat" in names
    assert "MonkeySMP-Server/monkey/manifest.json" in names
    assert "MonkeySMP-Server/monkey/patches/silvers_effects-library/pack.mcmeta" in names
    assert not any(n.endswith((".jar", ".zip")) for n in names), "release must not bundle third-party files"


def test_build_ships_every_patch_of_a_fabric_release(tmp_path, fabric_repo):
    names = zipfile.ZipFile(build.build_server("2.0.0", fabric_repo, tmp_path)).namelist()
    assert {n for n in names if "/patches/" in n} == {
        "MonkeySMP-Server/monkey/patches/silvers_effects-library/pack.mcmeta",
        "MonkeySMP-Server/monkey/patches/silvers_strength-restrictions/pack.mcmeta"}


@pytest.mark.parametrize("release", RELEASES)
def test_build_is_reproducible(tmp_path, request, release):
    repo = request.getfixturevalue(release)
    version = repo.load_manifest()["version"]
    hashes = []
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        hashes.append(hashlib.sha256(build.build_server(version, repo, tmp_path / sub).read_bytes()).hexdigest())
    assert hashes[0] == hashes[1]


def test_build_rejects_a_tag_that_differs_from_the_manifest(tmp_path, monkeypatch, paper_repo):
    monkeypatch.setenv("GITHUB_REF_NAME", "v9.9.9")
    with pytest.raises(SystemExit, match="doesn't match"):
        build.main(paper_repo, tmp_path / "dist")
    assert not (tmp_path / "dist").exists()


def test_build_main_writes_the_server_zip_and_its_checksum(tmp_path, fabric_repo, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    dist = tmp_path / "dist"
    build.main(fabric_repo, dist)
    assert sorted(p.name for p in dist.iterdir()) == ["MonkeySMP-Server-2.0.0.zip", "SHA256SUMS.txt"]
    out = capsys.readouterr().out
    assert all(name in out for name in ("MonkeySMP-Server-2.0.0.zip", "SHA256SUMS.txt"))
    assert checksums.problems(dist) == [], "what the release workflow checks before it publishes"
    assert (dist / "SHA256SUMS.txt").read_bytes() == (
        f"{hashlib.sha256((dist / 'MonkeySMP-Server-2.0.0.zip').read_bytes()).hexdigest()}  "
        "MonkeySMP-Server-2.0.0.zip\n").encode()


def test_build_has_no_site_build_any_more(tmp_path, fabric_repo, monkeypatch):
    """--site-build rebuilt the client pack and player zip for the website; neither exists since the relaunch."""
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    with pytest.raises(SystemExit):
        build.main(fabric_repo, tmp_path / "dist", ["--site-build", "ships"])
    assert not (tmp_path / "dist").exists()


CHANGELOG = ("# Changelog\n\n## [Unreleased]\n\n## [2.0.0] - 2026-10-01\n\nFabric.\n\n- New mods.\n\n"
             "## [1.1.0]\n\nOld.\n")


def test_changelog_section_is_one_versions_section():
    assert build.changelog_section(CHANGELOG, "2.0.0") == "Fabric.\n\n- New mods."
    assert build.changelog_section(CHANGELOG, "1.1.0") == "Old."
    with pytest.raises(SystemExit, match=r"no '## \[9.9.9\]' section"):
        build.changelog_section(CHANGELOG, "9.9.9")
    with pytest.raises(SystemExit, match="no"):
        build.changelog_section(CHANGELOG, "Unreleased")


def test_build_main_writes_the_release_notes(tmp_path, fabric_repo, monkeypatch):
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    (fabric_repo.root / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    build.main(fabric_repo, tmp_path / "dist", ["--notes", str(tmp_path / "notes.md")])
    notes = (tmp_path / "notes.md").read_text(encoding="utf-8")
    assert notes == "Fabric.\n\n- New mods.\n\n" + build.DOWNLOADS
    assert notes.splitlines()[4] == "### Downloads" and notes.endswith("`sha256sum <file>` on Linux.\n")
    assert "- **SHA256SUMS.txt** - the SHA-256 of the zip above." in notes
    assert ".mrpack" not in notes and "MonkeySMP-Player" not in notes, "players download nothing"


def test_build_main_needs_a_changelog_section_for_the_notes(tmp_path, fabric_repo, monkeypatch):
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    (fabric_repo.root / "CHANGELOG.md").write_text("# Changelog\n\n## [1.1.0]\n\nOld.\n", encoding="utf-8")
    with pytest.raises(SystemExit, match=r"no '## \[2.0.0\]' section"):
        build.main(fabric_repo, tmp_path / "dist", ["--notes", str(tmp_path / "notes.md")])
    assert not (tmp_path / "dist").exists() and not (tmp_path / "notes.md").exists()


# --- Linux and macOS ---------------------------------------------------------------------------------

def test_build_marks_sh_launchers_executable_and_is_made_on_unix(tmp_path, fabric_repo):
    z = zipfile.ZipFile(build.build_server("2.0.0", fabric_repo, tmp_path))
    modes = {i.filename.split("/", 1)[1]: (i.external_attr >> 16) & 0o777 for i in z.infolist()}
    for name in ("start.sh", "stop.sh", "backup.sh", "add-player.sh", "prepare-for-hosting.sh",
                 "Start Server.command", "monkey/monkey.sh"):
        assert modes[name] == 0o755, name
    assert modes["Start Server.bat"] == modes["monkey/pwsh.lock"] == modes["monkey/manifest.json"] == 0o644
    assert {i.create_system for i in z.infolist()} == {3}
    assert b"\r" not in z.read("MonkeySMP-Server/start.sh")


def test_build_leaves_out_what_a_local_install_or_docker_left_in_package(tmp_path, fabric_repo):
    pkg = fabric_repo.package
    for junk in ("server/server.properties", "java/linux-x64/jdk/bin/java", "pwsh/linux-x64/p/pwsh", "backups/x/a",
                 "exports/MonkeySMP-2.0.0-hosting.zip", "downloads/a.part", ".monkey-launch", "smoke-console.log.err",
                 "docker/.env"):
        (pkg / junk).parent.mkdir(parents=True, exist_ok=True)
        (pkg / junk).write_text("junk")
    (pkg / "docker" / "entrypoint.sh").write_text("#!/bin/sh\n")
    z = zipfile.ZipFile(build.build_server("2.0.0", fabric_repo, tmp_path))
    names = {n.split("/", 1)[1] for n in z.namelist()}
    assert not {n for n in names if n.split("/")[0] in build.RUNTIME_DIRS or n in (".monkey-launch", "docker/.env")
                or n.startswith("smoke-console")}
    assert "docker/entrypoint.sh" in names
    assert (z.getinfo("MonkeySMP-Server/docker/entrypoint.sh").external_attr >> 16) & 0o777 == 0o755


# --- the world seed --------------------------------------------------------------------------------

def test_nothing_public_contains_the_world_seed():
    """The seed shows where every ore and structure is (seed-based x-ray), so only the server zip has it."""
    seed = REPO.load_manifest()["world"]["seed"].lstrip("-").encode()
    public = [*REPO.root.joinpath("site").rglob("*"), REPO.root / "docs" / "RULES.md"]
    assert not [p for p in public if p.is_file() and seed in p.read_bytes()]


def test_the_server_zip_holds_the_world_seed(tmp_path):
    seed = REPO.load_manifest()["world"]["seed"].lstrip("-").encode()
    server = zipfile.ZipFile(build.build_server("0.0.0", REPO, tmp_path))
    assert seed in server.read("MonkeySMP-Server/monkey/manifest.json")  # the check above can see it where it is
