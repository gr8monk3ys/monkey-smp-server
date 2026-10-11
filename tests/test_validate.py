import copy
import hashlib
import zipfile

import pytest
from conftest import PLAYER_FILES, fake_player, make_zip, patched_entry

import build
import defaults
import entries
import patches
import pwsh_lock
import validate
from repo import REPO, load_json, save_json
from upstream import RecordedHttp, Upstream


def test_real_repo_is_valid():
    """The one test that looks at the real checkout: whatever it pins must validate cleanly."""
    manifest = REPO.load_manifest()
    assert validate.validate(manifest) == []
    assert validate.validate_package() == []
    assert validate.validate_client(manifest) == []
    assert validate.main([]) == 0
    text = (REPO.defaults / "server.properties").read_text(encoding="utf-8")
    assert defaults.placeholders(text) == set(defaults.TOKENS)


@pytest.mark.parametrize("release", ["paper_repo", "fabric_repo"])
def test_frozen_releases_are_valid(request, release):
    repo = request.getfixturevalue(release)
    assert validate.main([], repo=repo) == 0


# --- offline mistakes, Paper (the frozen 1.1.0 release) --------------------------------------------

def patched(m):
    return patched_entry(m)[1]


@pytest.mark.parametrize("mutate, message", [
    (lambda m: m["plugins"][0].update(url="http://evil.example/x.jar"), "allowed host"),
    (lambda m: m["plugins"][0].update(hashes={"sha512": "ABC"}), "lowercase hex"),
    (lambda m: m["plugins"].append(copy.deepcopy(m["plugins"][0])), "plugins: duplicate file"),
    (lambda m: m["datapacks"][1].update(slug=m["datapacks"][0]["slug"]), "datapacks: duplicate project"),
    (lambda m: m["datapacks"][0].update(file="bad:name.zip"), "characters Windows"),
    (lambda m: m["world"].update(seed="abc"), "seed"),
    (lambda m: m.update(version="1.0"), "1.2.3"),
    (lambda m: m.pop("world"), "missing 'world'"),
    (lambda m: m["server"].pop("build"), "integer 'build'"),
    (lambda m: m["datapacks"][0].update(patch={"path": "patches/does-not-exist",
                                               "base_sha512": m["datapacks"][0]["hashes"]["sha512"]}),
     "missing or empty"),
    (lambda m: patched(m)["hashes"].update(sha512="0" * 128), "base_sha512"),
    (lambda m: [d.pop("patch", None) for d in m["datapacks"]], "not used by any mod or datapack"),
    (lambda m: m["mods"].append(copy.deepcopy(m["plugins"][0])), "mods: a paper server can't use mods (1 listed)"),
])
def test_validate_catches_paper_mistakes(paper_manifest, paper_repo, mutate, message):
    assert validate.validate(paper_manifest, paper_repo) == []
    mutate(paper_manifest)
    errors = validate.validate(paper_manifest, paper_repo)
    assert any(message in e for e in errors), errors


# --- offline mistakes, Fabric (the frozen 2.0.0 release) -------------------------------------------

@pytest.mark.parametrize("mutate, message", [
    (lambda m: m["mods"][0].update(url="http://evil.example/x.jar"), "allowed host"),
    (lambda m: m["mods"][0].update(hashes={"sha512": "ABC"}), "lowercase hex"),
    (lambda m: m["mods"].append(copy.deepcopy(m["mods"][0])), "mods: duplicate file"),
    (lambda m: m["mods"][1].update(slug=m["mods"][0]["slug"]), "mods: duplicate project"),
    (lambda m: m["mods"][0].update(file="bad:name.jar"), "characters Windows"),
    (lambda m: m["world"].update(seed="abc"), "seed"),
    (lambda m: m["plugins"].append(copy.deepcopy(m["mods"][0])), "plugins: a fabric server can't use plugins"),
    (lambda m: m["server"].update(url=m["server"]["url"].replace("0.19.5", "0.19.4")), "server: url must be"),
    (lambda m: m["server"].update(file="fabric-server.jar"), "server: file must be"),
    (lambda m: m.update(minecraft="26.4"), "server: url must be"),
    (lambda m: m["server"].pop("loader"), "needs 'loader'"),
    (lambda m: m["server"].update(type="forge"), "type must be one of paper, fabric"),
    (lambda m: m["mods"][0].update(patch={"path": "patches/nope", "base_sha512": m["mods"][0]["hashes"]["sha512"]}),
     "missing or empty"),
    (lambda m: patched(m)["hashes"].update(sha512="0" * 128), "base_sha512"),
    (lambda m: m["datapacks"].append({**copy.deepcopy(patched(m)), "file": "other.zip", "slug": "other"}),
     "is also used by mod"),
    (lambda m: [e.pop("patch", None) for e in m["mods"]], "not used by any mod or datapack"),
    (lambda m: m.update(mods={"not": "a list"}), "'mods' must be a list"),
])
def test_validate_catches_fabric_mistakes(fabric_manifest, fabric_repo, mutate, message):
    assert validate.validate(fabric_manifest, fabric_repo) == []
    mutate(fabric_manifest)
    errors = validate.validate(fabric_manifest, fabric_repo)
    assert any(message in e for e in errors), errors


def test_a_1x_manifest_without_mods_still_validates_and_builds(paper_repo, tmp_path):
    raw = load_json(paper_repo.manifest)
    raw.pop("mods", None)
    save_json(paper_repo.manifest, raw)
    assert "mods" not in load_json(paper_repo.manifest)
    assert validate.validate(raw, paper_repo) == []
    assert validate.main([], repo=paper_repo) == 0
    assert paper_repo.load_manifest()["mods"] == []  # readers see an empty group
    names = zipfile.ZipFile(build.build_server(raw["version"], paper_repo, tmp_path)).namelist()
    assert "TheRealms-Server/realms/manifest.json" in names


# --- the package: defaults template and launchers ----------------------------------------------------

@pytest.mark.parametrize("edit, message", [
    (lambda t: t + "motd={{MOTD}}\n", "unsupported placeholder {{MOTD}}"),
    (lambda t: t.replace("{{SEED}}", "12345"), "missing {{SEED}}"),
    (lambda t: t.replace("rcon.password={{RCON_PASSWORD}}", "rcon.password=hunter2"), "real RCON password"),
])
def test_validate_package_checks_the_server_properties_template(paper_repo, edit, message):
    props = paper_repo.defaults / "server.properties"
    props.write_text(edit(props.read_text(encoding="utf-8")), encoding="utf-8")
    errors = validate.validate_package(paper_repo)
    assert any(message in e for e in errors), errors


def test_validate_package_requires_the_launchers(paper_repo):
    (paper_repo.package / "Start Server.bat").unlink()
    assert "package/Start Server.bat is missing" in validate.validate_package(paper_repo)


# --- the player installer (checked once player/ exists) ---------------------------------------------

def test_validate_package_checks_the_player_installer_only_once_it_exists(fabric_repo):
    assert not fabric_repo.player.exists()
    assert validate.validate_package(fabric_repo) == []
    fake_player(fabric_repo)
    assert validate.validate_package(fabric_repo) == []
    assert validate.main([], repo=fabric_repo) == 0


@pytest.mark.parametrize("missing", list(PLAYER_FILES))
def test_validate_package_requires_the_player_files(fabric_repo, missing):
    fake_player(fabric_repo, {k: v for k, v in PLAYER_FILES.items() if k != missing})
    assert validate.validate_package(fabric_repo) == [f"player/{missing} is missing"]


@pytest.mark.parametrize("name", ["installer/PlayerInstall.psm1", "installer/install-client.ps1",
                                  "Install for Minecraft Launcher.bat", "installer/tools/Helper.bat"])
def test_validate_package_requires_ascii_player_scripts(fabric_repo, name):
    fake_player(fabric_repo, {**PLAYER_FILES, name: "Write-Host 'café'\r\n"})
    errors = validate.validate_package(fabric_repo)
    assert errors == [f"player/{name} {validate.ASCII_NOTE}"]


@pytest.mark.parametrize("name", ["package/READ ME FIRST.txt", "player/READ ME.txt", "package/realms/Realms.psm1",
                                  "CHANGELOG.md", "docs/ADMIN.md"])
def test_validate_package_rejects_control_characters_in_texts(fabric_repo, name):
    fake_player(fabric_repo)
    text = fabric_repo.root / name
    text.parent.mkdir(parents=True, exist_ok=True)
    text.write_bytes(b"open  server\\config\x0boicechat\x0boicechat-server.properties\r\n")
    assert validate.validate_package(fabric_repo) == [f"{name} {validate.CONTROL_NOTE}"]


# --- the client's Fabric launcher profile ----------------------------------------------------------

def edit_profile(repo, change):
    profile = load_json(repo.fabric_profile)
    change(profile)
    save_json(repo.fabric_profile, profile)


def libs(p):
    return p["libraries"]


@pytest.mark.parametrize("change, message", [
    (lambda p: p.update(id="fabric-loader-0.19.4-26.3"), "id must be fabric-loader-0.19.5-26.3"),
    (lambda p: p.update(inheritsFrom="26.2"), "inheritsFrom must be 26.3"),
    (lambda p: p.pop("mainClass"), "missing mainClass"),
    (lambda p: libs(p)[0].update(url="https://evil.example/maven/"), "not an allowed maven repository"),
    (lambda p: libs(p)[0].update(url="http://maven.fabricmc.net/"), "not an allowed maven repository"),
    (lambda p: [libs(p)[0].pop(k) for k in ("sha1", "sha256")], "org.ow2.asm:asm:9.10.1: needs a sha1 or sha256"),
    (lambda p: libs(p)[0].update(sha1="ABC"), "sha1 must be 40 lowercase hex"),
    (lambda p: libs(p).pop(), "must include net.fabricmc:fabric-loader:0.19.5"),
    (lambda p: p.update(libraries=[]), "libraries must be a non-empty list"),
])
def test_validate_client_checks_the_launcher_profile(fabric_repo, change, message):
    manifest = fabric_repo.load_manifest()
    assert validate.validate_client(manifest, fabric_repo) == []
    edit_profile(fabric_repo, change)
    errors = validate.validate_client(manifest, fabric_repo)
    assert any(message in e for e in errors), errors


def test_validate_client_matches_the_profile_to_the_client_index(fabric_repo):
    index = load_json(fabric_repo.client / "modrinth.index.json")
    index["dependencies"]["fabric-loader"] = "0.19.6"  # a loader bump without re-pinning the profile
    save_json(fabric_repo.client / "modrinth.index.json", index)
    errors = validate.validate_client(fabric_repo.load_manifest(), fabric_repo)
    assert any("id must be fabric-loader-0.19.6-26.3" in e for e in errors), errors


def test_validate_client_requires_a_readable_profile(fabric_repo):
    manifest = fabric_repo.load_manifest()
    fabric_repo.fabric_profile.write_text("{not json", encoding="utf-8")
    assert "not valid JSON" in validate.validate_client(manifest, fabric_repo)[0]
    fabric_repo.fabric_profile.unlink()
    assert validate.validate_client(manifest, fabric_repo) == [
        "client/fabric-profile.json is missing (pin it with `python tools/snapshot.py profile`)"]


def test_verify_profile_online(fabric_repo, recorded, capsys):
    up = Upstream(recorded)
    assert validate.verify_profile_online(up, fabric_repo) == []
    assert "ok  profile  fabric-loader-0.19.5-26.3" in capsys.readouterr().out
    # Meta stamps each generated profile with the time; that alone is not a difference.
    later = "2027-01-01T00:00:00+0000"
    edit_profile(fabric_repo, lambda p: p.update(time=later, releaseTime=later))
    assert validate.verify_profile_online(up, fabric_repo) == []
    edit_profile(fabric_repo, lambda p: libs(p)[0].update(sha1="0" * 40))
    assert validate.verify_profile_online(up, fabric_repo) == [
        "client/fabric-profile.json differs from what Fabric meta serves now "
        "(re-pin it with `python tools/snapshot.py profile`)"]


# --- online: downloads and patch fit, served by RecordedHttp ---------------------------------------

def serve(http, entry, data, algo="sha512"):
    """Pin `entry` to `data` and serve `data` at its URL."""
    entry.update(size=len(data), hashes={algo: hashlib.new(algo, data).hexdigest()})
    http.add("GET", entry["url"], data)


@pytest.fixture(params=["paper_repo", "fabric_repo"])
def online(request):
    """A frozen release cut down to Java, the server, one unpatched plugin/mod and every patched
    mod/datapack, whose downloads are tiny recorded files; every patch fits its download."""
    repo = request.getfixturevalue(request.param)
    m = repo.load_manifest()
    http = RecordedHttp()
    serve(http, m["java"], b"java bytes", "sha256")
    serve(http, m["server"], f"{m['server']['type']} server bytes".encode(), "sha256")
    content_kind = "plugin" if m["server"]["type"] == "paper" else "mod"
    plain = next(e for e in entries.group(m, content_kind) if "patch" not in e)
    serve(http, plain, b"plugin or mod bytes")
    kept = {id(plain)}
    for kind in entries.PATCHABLE:
        for e in entries.group(m, kind):
            if "patch" in e:
                files = patches.read(patches.folder(repo, e))
                serve(http, e, make_zip({**{name: b"upstream" for name in files}, "data/a.json": b"{}"}))
                e["patch"]["base_sha512"] = e["hashes"]["sha512"]
                kept.add(id(e))
    for group in entries.GROUPS.values():
        m[group] = [e for e in m[group] if id(e) in kept]
    assert validate.validate(m, repo) == []
    return m, http, repo, content_kind, plain


def test_verify_online_downloads_and_applies_patches(online, capsys):
    m, http, repo, _, _ = online
    assert validate.verify_online(m, Upstream(http), repo) == []
    out = capsys.readouterr().out
    assert f"ok  server   {m['server']['file']}" in out
    assert out.count("(patch fits)") == sum("patch" in e for kind in entries.PATCHABLE for e in entries.group(m, kind))


def test_verify_online_catches_a_changed_download(online):
    m, http, repo, kind, plain = online
    http.add("GET", plain["url"], b"plugin or mod bytes, re-uploaded")
    errors = validate.verify_online(m, Upstream(http), repo)
    assert errors == [f"{kind} {plain['file']}: download doesn't match the pinned size/hash"]


def test_verify_online_catches_a_changed_server_jar(online):
    m, http, repo, _, _ = online
    http.add("GET", m["server"]["url"], b"a different launcher")
    errors = validate.verify_online(m, Upstream(http), repo)
    assert errors == [f"server {m['server']['file']}: download doesn't match the pinned size/hash"]


def test_verify_online_catches_a_patch_that_no_longer_fits(online):
    m, http, repo, _, _ = online
    kind, entry = patched_entry(m)
    patches.write(patches.folder(repo, entry), {"pack.mcmeta": b"patched", "data/gone.json": b"{}"})
    errors = validate.verify_online(m, Upstream(http), repo)
    assert len(errors) == 1 and errors[0].startswith(f"{kind} {entry['file']}:")
    assert "doesn't fit" in errors[0] and "data/gone.json" in errors[0]


# --- Linux and macOS: the sh launchers and pwsh.lock ------------------------------------------------

@pytest.mark.parametrize("name", ["start.sh", "Start Server.command", "realms/realms.sh", "realms/pwsh.lock"])
def test_validate_package_requires_the_unix_launchers(paper_repo, name):
    (paper_repo.package / name).unlink()
    assert f"package/{name} is missing" in validate.validate_package(paper_repo)


@pytest.mark.parametrize("name", ["stop.sh", "Start Server.command", "realms/realms.sh"])
def test_validate_package_rejects_crlf_in_sh_scripts(paper_repo, name):
    path = paper_repo.package / name
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert f"{name} must have LF line endings (it is run by sh)" in validate.validate_package(paper_repo)


def test_validate_package_requires_ascii_sh_scripts(paper_repo):
    path = paper_repo.package / "backup.sh"
    path.write_bytes(path.read_bytes() + "# café\n".encode())
    assert f"backup.sh {validate.ASCII_NOTE}" in validate.validate_package(paper_repo)


def test_validate_package_checks_docker_files_once_the_folder_exists(paper_repo):
    docker = paper_repo.package / "docker"
    docker.mkdir()
    (docker / "Dockerfile").write_bytes(b"FROM debian:12-slim\r\n")
    errors = validate.validate_package(paper_repo)
    assert "package/docker/entrypoint.sh is missing" in errors
    assert "docker/Dockerfile must have LF line endings (it is run by sh)" in errors


def lock_lines(repo):
    return repo.pwsh_lock.read_text().splitlines(keepends=True)


@pytest.mark.parametrize("change, message", [
    (lambda ls: [x for x in ls if not x.startswith("mac-aarch64 ")], "pwsh.lock: no line for mac-aarch64"),
    (lambda ls: ls + ["windows-x64 https://example.com/x.zip " + "a" * 64 + "\n"], "url must be a PowerShell release"),
    (lambda ls: [x.replace("osx-x64", "osx-arm64") if x.startswith("mac-x64 ") else x for x in ls],
     "pwsh.lock mac-x64: url is the osx-arm64 build, not osx-x64"),
    (lambda ls: [x.replace("7.6.6", "7.6.5") if x.startswith("linux-x64 ") else x for x in ls],
     "same PowerShell version"),
    (lambda ls: [x.upper() if x.startswith("linux-aarch64 ") else x for x in ls], "unknown platform LINUX-AARCH64"),
    (lambda ls: ls + [ls[-1]], "listed twice"),
    (lambda ls: ls + ["linux-x64 https://two-words-only\n"], "expected '<platform> <url> <sha256>'"),
])
def test_validate_package_checks_pwsh_lock(paper_repo, change, message):
    assert validate.validate_package(paper_repo) == []
    paper_repo.pwsh_lock.write_text("".join(change(lock_lines(paper_repo))), newline="\n")
    errors = validate.validate_package(paper_repo)
    assert any(message in e for e in errors), errors


def test_verify_pwsh_online(paper_repo, capsys):
    http = RecordedHttp()
    pins = pwsh_lock.parse(paper_repo.pwsh_lock.read_text())
    text = "".join(f"{p.platform} {p.url} {hashlib.sha256(p.platform.encode()).hexdigest()}\n" for p in pins)
    paper_repo.pwsh_lock.write_text(text, newline="\n")
    for p in pins:
        http.add("GET", p.url, p.platform.encode())
    assert validate.verify_pwsh_online(Upstream(http), paper_repo) == []
    assert "ok  pwsh     powershell-7.6.6-osx-arm64.tar.gz" in capsys.readouterr().out
    http.add("GET", pins[0].url, b"tampered")
    assert validate.verify_pwsh_online(Upstream(http), paper_repo) == [
        "pwsh.lock linux-x64 powershell-7.6.6-linux-x64.tar.gz: download doesn't match the pinned sha256"]


def test_verify_online_downloads_every_java_build(capsys):
    m = copy.deepcopy(REPO.load_manifest())
    http = RecordedHttp()
    for _, jre in entries.java_builds(m):
        serve(http, jre, jre["file"].encode(), "sha256")
    m["server"] = {**m["server"]}
    serve(http, m["server"], b"server", "sha256")
    m["mods"] = []
    assert validate.verify_online(m, Upstream(http)) == []
    assert capsys.readouterr().out.count("ok  java ") == 5
