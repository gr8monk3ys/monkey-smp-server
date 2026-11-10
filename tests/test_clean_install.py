"""tools/clean_install.py with a made-up pack, recorded downloads and a stand-in for the Windows installer.

The real downloads and the real installer run in the Clean install workflow (.github/workflows/install.yml).
"""
import hashlib
import json
import zipfile

import pytest

import build
import clean_install
from repo import REPO
from upstream import RecordedHttp

MOD, PACK_ART, LIBRARY = b"a mod's jar", b"a resource pack", b"a library the server keeps to itself"
CDN = "https://cdn.modrinth.com/data/AAAAaaaa/versions/BBBBbbbb/"
OVERRIDES = {"overrides/options.txt": b"fov:0.5\n", "overrides/config/shared.toml": b"from overrides\n",
             "client-overrides/config/shared.toml": b"from client-overrides\n",
             "server-overrides/server-only.txt": b"never on a player's computer\n"}
FABRIC_PROFILE = b'{"id":"fabric-loader-0.20.1-26.2","inheritsFrom":"26.2"}'
VERSION_FILE = "versions/fabric-loader-0.20.1-26.2/fabric-loader-0.20.1-26.2.json"


def entry(path: str, data: bytes, **more) -> dict:
    hashes = {"sha1": hashlib.sha1(data).hexdigest(), "sha512": hashlib.sha512(data).hexdigest()}
    return {"path": path, "hashes": hashes,
            "downloads": [CDN + path.rsplit("/", 1)[-1]], "fileSize": len(data), **more}


def good_index() -> dict:
    return {"formatVersion": 1, "game": "minecraft", "versionId": "1.2.3", "name": "Monkey SMP - Client",
            "summary": "A test pack.", "dependencies": {"minecraft": "26.2", "fabric-loader": "0.20.1"},
            "files": [entry("mods/mod.jar", MOD, env={"client": "required", "server": "unsupported"}),
                      entry("resourcepacks/art.zip", PACK_ART, env={"client": "optional", "server": "unsupported"}),
                      entry("mods/library.jar", LIBRARY, env={"client": "unsupported", "server": "required"})]}


def write_pack(path, index=None, extra=None):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("modrinth.index.json", json.dumps(good_index() if index is None else index))
        for name, data in {**OVERRIDES, **(extra or {})}.items():
            z.writestr(name, data)
    return path


def downloads() -> RecordedHttp:
    http = RecordedHttp()
    for name, data in (("mod.jar", MOD), ("art.zip", PACK_ART), ("library.jar", LIBRARY)):
        http.add("GET", CDN + name, data)
    return http


def tree(folder) -> dict:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


# ------------------------------------------------------------------------------------------------ the pack

def test_a_good_pack_has_no_problems(tmp_path):
    assert clean_install.pack_problems(write_pack(tmp_path / "pack.mrpack")) == []


def test_the_pack_the_build_makes_is_a_valid_pack(tmp_path):
    """The real client/ folder, built as a release builds it."""
    pack = build.build_client("1.2.3", REPO, tmp_path)
    assert clean_install.pack_problems(pack) == []
    index, overrides = clean_install.read_pack(pack)
    assert index["versionId"] == "1.2.3" and clean_install.client_files(index) and "options.txt" in overrides


def change(index: dict, **top) -> dict:
    return {**index, **top}


def file_with(**fields) -> dict:
    index = good_index()
    index["files"][0] = {k: v for k, v in {**index["files"][0], **fields}.items() if v is not ...}
    return index


@pytest.mark.parametrize("index, message", [
    ([], "is not an object"),
    (change(good_index(), formatVersion=2), "formatVersion must be 1"),
    (change(good_index(), formatVersion=1.0), "formatVersion must be 1"),
    (change(good_index(), game="minecraft-bedrock"), 'game must be "minecraft"'),
    (change(good_index(), versionId=""), "versionId must be text"),
    (change(good_index(), name=None), "name must be text"),
    (change(good_index(), summary=3), "summary must be text"),
    (change(good_index(), dependencies=[]), "dependencies must be an object"),
    (change(good_index(), dependencies={"fabric-loader": "0.20.1"}), "dependencies has no minecraft version"),
    (change(good_index(), dependencies={"minecraft": "26.2", "fabric": "0.20.1"}), "'fabric' is not one of"),
    (change(good_index(), dependencies={"minecraft": ""}), "dependencies.minecraft must be a version"),
    (change(good_index(), files={}), "files must be a list"),
    (change(good_index(), files=["mods/mod.jar"]), "files[0] is not an object"),
    (file_with(path="../mods/mod.jar"), "not a safe path"),
    (file_with(path="C:/mods/mod.jar"), "not a safe path"),
    (file_with(path="mods\\mod.jar"), "not a safe path"),
    (file_with(path="/mods/mod.jar"), "not a safe path"),
    (file_with(path="mods/mod.jar."), "not a safe path"),
    (file_with(path="mods//mod.jar"), "not a safe path"),
    (file_with(path=...), "not a safe path"),
    (file_with(path="MODS/Library.jar"), "mods/library.jar is listed twice"),
    (file_with(hashes={"sha512": hashlib.sha512(MOD).hexdigest()}), "hashes.sha1 must be 40 small hex digits"),
    (file_with(hashes={"sha1": hashlib.sha1(MOD).hexdigest(), "sha512": hashlib.sha512(MOD).hexdigest().upper()}),
     "hashes.sha512 must be 128 small hex digits"),
    (file_with(hashes=...), "hashes.sha1 must be"),
    (file_with(downloads=[]), "no download"),
    (file_with(downloads=...), "no download"),
    (file_with(downloads=["http://cdn.modrinth.com/data/x.jar"]), "is not an https download from"),
    (file_with(downloads=["https://example.com/x.jar"]), "is not an https download from"),
    (file_with(downloads=[CDN + "mod.jar", 5]), "is not an https download from"),
    (file_with(fileSize=0), "fileSize must be"),
    (file_with(fileSize="11"), "fileSize must be"),
    (file_with(fileSize=True), "fileSize must be"),
    (file_with(fileSize=2 ** 32), "fileSize must be"),
    (file_with(env={"client": "yes"}), "env must say"),
    (file_with(env={"client": "required", "host": "required"}), "env must say"),
    (file_with(env=[]), "env must say"),
])
def test_an_index_a_launcher_cannot_read_is_a_problem(tmp_path, index, message):
    errors = clean_install.pack_problems(write_pack(tmp_path / "pack.mrpack", index))
    assert any(message in e for e in errors), errors


def test_a_pack_that_is_not_a_pack_is_a_problem(tmp_path):
    (tmp_path / "text.mrpack").write_bytes(b"not a zip")
    [error] = clean_install.pack_problems(tmp_path / "text.mrpack")
    assert error.startswith("not a zip file")
    [error] = clean_install.pack_problems(tmp_path / "nowhere.mrpack")
    assert error.startswith("not a zip file")
    with zipfile.ZipFile(tmp_path / "empty.mrpack", "w") as z:
        z.writestr("overrides/options.txt", b"")
    assert clean_install.pack_problems(tmp_path / "empty.mrpack") == ["no modrinth.index.json at the top of the zip"]
    with zipfile.ZipFile(tmp_path / "broken.mrpack", "w") as z:
        z.writestr("modrinth.index.json", "{")
    [error] = clean_install.pack_problems(tmp_path / "broken.mrpack")
    assert error.startswith("modrinth.index.json is not valid JSON")


@pytest.mark.parametrize("name, message", [
    ("mods/extra.jar", "a launcher only reads"),
    ("overrides/../../outside.txt", "is not a safe path"),
    ("overrides/mods/mod.jar", "would replace the download mods/mod.jar"),
    ("client-overrides/Mods/MOD.jar", "would replace the download Mods/MOD.jar"),
])
def test_a_zip_entry_a_launcher_would_not_install_is_a_problem(tmp_path, name, message):
    errors = clean_install.pack_problems(write_pack(tmp_path / "pack.mrpack", extra={name: b"x"}))
    assert len(errors) == 1 and message in errors[0], errors


# ------------------------------------------------------------------------------------------------ the launcher's way

def test_a_launcher_install_downloads_checks_and_unpacks(tmp_path):
    lines = []
    errors = clean_install.launcher_install(write_pack(tmp_path / "pack.mrpack"), tmp_path / "instance", downloads(),
                                            log=lines.append)
    assert errors == []
    # Not the server-only library, not server-overrides/; client-overrides/ over overrides/.
    assert tree(tmp_path / "instance") == {
        "mods/mod.jar": MOD, "resourcepacks/art.zip": PACK_ART, "options.txt": b"fov:0.5\n",
        "config/shared.toml": b"from client-overrides\n"}
    assert "2 files" in lines[-1] and "3 override files" not in lines[-1] and "2 override files" in lines[-1]


def test_a_download_that_is_not_the_pinned_file_fails_the_install(tmp_path):
    http = downloads().add("GET", CDN + "mod.jar", b"another jar!")
    pauses = []
    errors = clean_install.launcher_install(write_pack(tmp_path / "pack.mrpack"), tmp_path / "instance", http,
                                            pause=pauses.append, log=lambda line: None)
    assert errors == [f"mods/mod.jar: {CDN}mod.jar is 12 bytes, the pack says 11"]
    assert pauses == [5, 10]      # three tries
    assert "mods/mod.jar" not in tree(tmp_path / "instance")

    http.add("GET", CDN + "mod.jar", b"A mod's jar")    # the right size, other bytes
    errors = clean_install.launcher_install(write_pack(tmp_path / "pack.mrpack"), tmp_path / "second", http,
                                            pause=pauses.append, log=lambda line: None)
    assert errors == [f"mods/mod.jar: {CDN}mod.jar has another sha1 than the pack says"]


def test_a_download_that_is_gone_fails_the_install_unless_another_serves_it(tmp_path):
    http = downloads()
    del http.responses["GET " + CDN + "art.zip"]
    [error] = clean_install.launcher_install(write_pack(tmp_path / "pack.mrpack"), tmp_path / "instance", http,
                                             pause=lambda seconds: None, log=lambda line: None)
    assert error.startswith(f"resourcepacks/art.zip: {CDN}art.zip: UnrecordedRequest")

    index = good_index()
    index["files"][1]["downloads"].append("https://github.com/gr8monk3ys/art/releases/download/v1/art.zip")
    http.add("GET", "https://github.com/gr8monk3ys/art/releases/download/v1/art.zip", PACK_ART)
    assert clean_install.launcher_install(write_pack(tmp_path / "two.mrpack", index), tmp_path / "second", http,
                                          pause=lambda seconds: None, log=lambda line: None) == []
    assert tree(tmp_path / "second")["resourcepacks/art.zip"] == PACK_ART


def test_a_launcher_install_needs_a_valid_pack_and_an_empty_folder(tmp_path):
    pack = write_pack(tmp_path / "pack.mrpack")
    (tmp_path / "used").mkdir()
    (tmp_path / "used" / "world.dat").write_bytes(b"someone's world")
    [error] = clean_install.launcher_install(pack, tmp_path / "used", downloads())
    assert "is not an empty folder" in error
    assert tree(tmp_path / "used") == {"world.dat": b"someone's world"}
    bad = write_pack(tmp_path / "bad.mrpack", change(good_index(), game="other"))
    assert clean_install.launcher_install(bad, tmp_path / "instance", downloads()) == [
        'bad.mrpack: game must be "minecraft"']
    assert not (tmp_path / "instance").exists()


# ------------------------------------------------------------------------------------------------ the installer's way

def player_zip(tmp_path, pack=None):
    pack = pack or write_pack(tmp_path / "MonkeySMP-Client-1.2.3.mrpack")
    top = "MonkeySMP-Player-1.2.3"
    with zipfile.ZipFile(tmp_path / f"{top}.zip", "w") as z:
        z.writestr(f"{top}/{clean_install.BAT}", "@echo off\r\n")
        z.writestr(f"{top}/{pack.name}", pack.read_bytes())
        z.writestr(f"{top}/installer/fabric-profile.json", FABRIC_PROFILE)
    return tmp_path / f"{top}.zip"


def installer(spoil=None):
    """A stand-in for the .bat: leaves what the real installer leaves, then `spoil(minecraft, game)` changes it."""
    def run(bat, appdata):
        assert bat.name == clean_install.BAT and bat.is_file()
        minecraft, game = appdata / ".minecraft", appdata / ".monkey-smp"
        assert tree(minecraft) == {"launcher_profiles.json": clean_install.SEED_PROFILES}, "not an empty folder"
        files = {"mods/mod.jar": MOD, "resourcepacks/art.zip": PACK_ART, "options.txt": b"fov:0.5\n",
                 "config/shared.toml": b"from client-overrides\n",
                 ".monkey-client-state.json": json.dumps({
                     "pack": "Monkey SMP - Client", "version": "1.2.3",
                     "files": ["mods/mod.jar", "resourcepacks/art.zip"]}).encode()}
        profiles = json.loads(clean_install.SEED_PROFILES)
        profiles["profiles"]["monkey-smp"] = {
            "name": "Monkey SMP 1.2.3", "type": "custom", "lastVersionId": "fabric-loader-0.20.1-26.2",
            "gameDir": str(game), "javaArgs": "-Xmx6G -Xms6G -XX:+UseG1GC", "icon": "Grass",
            "created": "2026-11-09T12:00:00.000Z", "lastUsed": "2026-11-09T12:00:00.000Z"}
        launcher = {"launcher_profiles.json": json.dumps(profiles, indent=2).encode(),
                    "launcher_profiles.json.monkey-smp-backup": clean_install.SEED_PROFILES,
                    VERSION_FILE: FABRIC_PROFILE}
        for folder, content in ((game, files), (minecraft, launcher)):
            for rel, data in content.items():
                (folder / rel).parent.mkdir(parents=True, exist_ok=True)
                (folder / rel).write_bytes(data)
        return spoil(minecraft, game) if spoil else ""
    return run


def edit_profiles(minecraft, edit):
    path = minecraft / "launcher_profiles.json"
    data = json.loads(path.read_bytes())
    edit(data)
    path.write_bytes(json.dumps(data).encode())


def test_a_clean_installer_run_has_no_problems(tmp_path):
    lines = []
    assert clean_install.installer_install(player_zip(tmp_path), tmp_path / "scratch", run=installer(),
                                           log=lines.append) == []
    assert "2 pack files and 2 override files" in lines[-1]


def spoiled(change_it):
    def spoil(minecraft, game):
        change_it(minecraft, game)
        return ""
    return spoil


def profile(data):
    return data["profiles"]["monkey-smp"]


@pytest.mark.parametrize("change_it, message", [
    (lambda mc, game: (game / "mods" / "mod.jar").unlink(), "game folder: mods/mod.jar is missing"),
    (lambda mc, game: (game / "mods" / "mod.jar").write_bytes(b"A mod's jar"),
     "game folder: mods/mod.jar has another sha1 than the pack says"),
    (lambda mc, game: (game / "mods" / ".download-1234.part").write_bytes(b"half"),
     "game folder: mods/.download-1234.part was left behind"),
    (lambda mc, game: (game / "mods" / "library.jar").write_bytes(LIBRARY),
     "game folder: mods/library.jar was left behind"),
    (lambda mc, game: (game / "options.txt").unlink(), "game folder: options.txt is missing"),
    (lambda mc, game: (game / "config" / "shared.toml").write_bytes(b"from overrides\n"),
     "game folder: config/shared.toml is not the pack's copy"),
    (lambda mc, game: (game / ".monkey-client-state.json").write_bytes(b"{"),
     "game folder: .monkey-client-state.json is not valid JSON"),
    (lambda mc, game: (game / ".monkey-client-state.json").write_bytes(
        b'{"pack": "Monkey SMP - Client", "version": "1.2.3", "files": ["mods/mod.jar"]}'),
     "game folder: .monkey-client-state.json doesn't list this pack's files"),
    (lambda mc, game: (mc / VERSION_FILE).write_bytes(b"{}"), "is not the zip's installer/fabric-profile.json"),
    (lambda mc, game: (mc / VERSION_FILE).unlink(), f"launcher folder: {VERSION_FILE} is missing"),
    (lambda mc, game: (mc / "launcher_profiles.json.monkey-smp-backup").unlink(),
     "launcher folder: launcher_profiles.json.monkey-smp-backup is missing"),
    (lambda mc, game: (mc / "launcher_profiles.json.monkey-smp-backup").write_bytes(b"{}"),
     "is not the file as it was before the install"),
    (lambda mc, game: (mc / "launcher_accounts.json").write_bytes(b"{}"),
     "launcher folder: launcher_accounts.json was left behind"),
    (lambda mc, game: (mc / "launcher_profiles.json").write_bytes(b"\xef\xbb\xbf{}"), "has no readable 'monkey-smp'"),
    (lambda mc, game: edit_profiles(mc, lambda d: d["profiles"].pop("monkey-smp")), "has no readable 'monkey-smp'"),
    (lambda mc, game: edit_profiles(mc, lambda d: d["settings"].update(soundOn=True)),
     "changed outside the 'monkey-smp' profile"),
    (lambda mc, game: edit_profiles(mc, lambda d: d["profiles"].pop("0000000000000000000000000000bbbb")),
     "changed outside the 'monkey-smp' profile"),
    (lambda mc, game: edit_profiles(mc, lambda d: profile(d).update(name="Monkey SMP")),
     "the profile's name is 'Monkey SMP', not 'Monkey SMP 1.2.3'"),
    (lambda mc, game: edit_profiles(mc, lambda d: profile(d).update(lastVersionId="latest-release")),
     "the profile's lastVersionId is 'latest-release'"),
    (lambda mc, game: edit_profiles(mc, lambda d: profile(d).update(gameDir=str(mc))), "the profile plays from"),
    (lambda mc, game: edit_profiles(mc, lambda d: profile(d).update(javaArgs="-Xmx5G -Xms5G -XX:+UseG1GC")),
     "javaArgs don't start with one of the installer's memory sizes"),
    (lambda mc, game: edit_profiles(mc, lambda d: profile(d).update(javaArgs="-Xmx6G -Xms3G -XX:+UseG1GC")),
     "javaArgs don't start with one of the installer's memory sizes"),
    (lambda mc, game: edit_profiles(mc, lambda d: profile(d).pop("lastUsed")), "the profile has no lastUsed"),
    (lambda mc, game: (mc.parent / ".stray-folder").mkdir(), "appdata: .stray-folder was made beside"),
])
def test_what_a_broken_installer_leaves_is_a_problem(tmp_path, change_it, message):
    errors = clean_install.installer_install(player_zip(tmp_path), tmp_path / "scratch",
                                             run=installer(spoiled(change_it)), log=lambda line: None)
    assert len(errors) == 1 and message in errors[0], errors


def test_an_installer_that_does_nothing_fails(tmp_path):
    errors = clean_install.installer_install(player_zip(tmp_path), tmp_path / "scratch", run=lambda bat, appdata: "",
                                             log=lambda line: None)
    assert "game folder: mods/mod.jar is missing" in errors
    assert "launcher folder: launcher_profiles.json.monkey-smp-backup is missing" in errors
    assert any("has no readable 'monkey-smp' profile" in e for e in errors)


def test_an_installer_that_does_not_finish_fails(tmp_path):
    assert clean_install.installer_install(player_zip(tmp_path), tmp_path / "scratch",
                                           run=lambda bat, appdata: "it didn't finish", log=lambda line: None) == [
        "it didn't finish"]


def test_the_installer_test_needs_a_whole_player_zip_and_an_empty_folder(tmp_path):
    zip_path = player_zip(tmp_path)
    (tmp_path / "used").mkdir()
    (tmp_path / "used" / "mine.txt").write_bytes(b"mine")
    [error] = clean_install.installer_install(zip_path, tmp_path / "used", run=installer())
    assert "is not an empty folder" in error and tree(tmp_path / "used") == {"mine.txt": b"mine"}

    with zipfile.ZipFile(tmp_path / "half.zip", "w") as z:
        z.writestr(f"MonkeySMP-Player-1.2.3/{clean_install.BAT}", "@echo off\r\n")
    [error] = clean_install.installer_install(tmp_path / "half.zip", tmp_path / "a", run=installer())
    assert "must hold one .mrpack" in error
    with zipfile.ZipFile(tmp_path / "none.zip", "w") as z:
        z.writestr("READ ME.txt", "hello")
    [error] = clean_install.installer_install(tmp_path / "none.zip", tmp_path / "b", run=installer())
    assert "must hold one folder with Install for Minecraft Launcher.bat" in error
    (tmp_path / "text.zip").write_bytes(b"not a zip")
    [error] = clean_install.installer_install(tmp_path / "text.zip", tmp_path / "c", run=installer())
    assert "is not a zip file" in error


def test_the_seed_is_a_launcher_file_without_our_profile():
    seed = json.loads(clean_install.SEED_PROFILES)
    assert "monkey-smp" not in seed["profiles"] and len(seed["profiles"]) == 2
    assert any(ord(c) > 127 for c in clean_install.SEED_PROFILES.decode("utf-8"))   # a name that isn't ASCII


def test_the_names_are_the_installers_own():
    """The module's constants: what the check looks for is what PlayerInstall.psm1 writes."""
    module = (REPO.player / "installer" / "PlayerInstall.psm1").read_text(encoding="ascii")
    for line in (f"$script:ProfileKey = '{clean_install.PROFILE_KEY}'",
                 f"$script:StateFileName = '{clean_install.STATE_FILE}'",
                 f"$script:BackupSuffix = '{clean_install.BACKUP_SUFFIX}'",
                 "(8 GB or less: 3, up to 12 GB: 4, up to 16 GB: 6, more: 8)"):
        assert line in module
    assert (REPO.player / clean_install.BAT).is_file()
    assert clean_install.MEMORY_GB == (3, 4, 6, 8)


# ------------------------------------------------------------------------------------------------ the command

def test_main_checks_a_pack_and_installs_like_a_launcher(tmp_path, capsys):
    pack = write_pack(tmp_path / "pack.mrpack")
    assert clean_install.main(["pack", str(pack)]) == 0
    assert "a valid pack, 3 files to download, 2 overrides" in capsys.readouterr().out
    assert clean_install.main(["launcher", str(pack), str(tmp_path / "instance")], http=downloads()) == 0
    assert clean_install.main(["launcher", str(pack), str(tmp_path / "instance")], http=downloads()) == 1
    assert "is not an empty folder" in capsys.readouterr().out
    bad = write_pack(tmp_path / "bad.mrpack", change(good_index(), formatVersion=2))
    assert clean_install.main(["pack", str(bad)]) == 1
    assert "ERROR formatVersion must be 1" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------------ the workflows

def workflow(name: str) -> str:
    return (REPO.root / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_a_release_waits_for_the_clean_install():
    release = workflow("release.yml")
    assert "\n  install:\n    uses: ./.github/workflows/install.yml\n" in release
    publish = release[release.index("\n  publish:"):release.index("\n  modrinth:")]
    assert "\n    needs: [ci, install]\n" in publish


def test_the_clean_install_runs_both_ways_and_not_on_every_pull_request():
    install = workflow("install.yml")
    triggers = install[install.index("\non:\n"):install.index("\njobs:\n")]
    assert "workflow_call:" in triggers and "workflow_dispatch:" in triggers and "push:" not in triggers
    # A pull request starts it only when it touches the pack, the installer, the build or the test itself.
    paths = triggers[triggers.index("pull_request:"):]
    for path in ("client/**", "tools/build.py", "player/**", "tools/clean_install.py", ".github/workflows/install.yml"):
        assert f'- "{path}"' in paths
    assert "paths:" in paths and "site/" not in paths and "package/" not in paths
    jobs = install[install.index("\njobs:\n"):]
    assert "python tools/clean_install.py launcher dist/" in jobs
    assert "python tools/clean_install.py installer " in jobs and "runs-on: windows-latest" in jobs

