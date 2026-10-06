"""Snapshots of fake Paper and Fabric server folders and a client instance, with Modrinth/Paper/Fabric
answers keyed to the hashes of the tiny files each test makes."""
import json

import pytest
from conftest import (
    fabric_launcher,
    fabric_profile,
    make_zip,
    paper_build,
    paper_builds_url,
    serve_fabric_launcher,
    zip_contents,
)

import entries
import patches
import snapshot
import validate
from repo import load_json
from upstream import RecordedHttp, Upstream, fabric_profile_url

MC = "26.1.2"
PACK = {"pack.mcmeta": b'{"pack": {"pack_format": 55}}', "data/x/tags/a.json": b'{"values": []}'}
EDITED = {**PACK, "pack.mcmeta": b'{"pack": {"pack_format": 99}}'}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    return data


class FakeServer:
    """A server folder with a non-default level-name, one plugin, one datapack and one edited datapack."""

    def __init__(self, root, modrinth, level="realm_world"):
        self.root, self.modrinth, self.level = root, modrinth, level
        write(root / "version_history.json", json.dumps({"currentVersion": f"26.1.2-74-abc (MC: {MC})"}))
        write(root / "server.properties", f"#comment\nlevel-name={level}\nrcon.password=hunter2\n")
        self.paper = write(root / "paper.jar", b"paper jar bytes")
        modrinth.http.add("GET", paper_builds_url(MC), [paper_build(73, b"other"), paper_build(74, self.paper)])
        self.plugin = write(root / "plugins" / "Plugin-1.0.jar", b"plugin jar")
        write(root / "plugins" / "config.yml", b"not a jar")
        self.pack = write(self.datapacks / "Pack v1.zip", make_zip({**PACK, "x": b"plain"}))
        self.original = write(root / "datapack-originals" / "Edited Pack.zip", make_zip(PACK))
        self.edited = write(self.datapacks / "Edited Pack.zip", make_zip(EDITED))
        modrinth.publish(self.plugin, "plugin", "Plugin-1.0.jar")
        modrinth.publish(self.pack, "pack", "Pack v1.zip")
        self.original_version = modrinth.publish(self.original, "edited-pack", "edited-pack-upstream.zip")

    @property
    def datapacks(self):
        return self.root / self.level / "datapacks"

    def expect_lookup(self, *extra):
        self.modrinth.expect_lookup(self.plugin, self.pack, self.original, self.edited, *extra)


@pytest.fixture
def server(tmp_path, fake_modrinth):
    return FakeServer(tmp_path / "server", fake_modrinth)


def test_snapshot_server_writes_a_valid_manifest(server, paper_repo):
    server.expect_lookup()
    m = snapshot.snapshot_server(server.root, repo=paper_repo, upstream=Upstream(server.modrinth.http))

    assert paper_repo.load_manifest() == m
    assert m["minecraft"] == MC and m["server"]["build"] == 74
    assert m["java"] == paper_repo.load_manifest()["java"]  # kept by default
    assert [p["file"] for p in m["plugins"]] == ["Plugin-1.0.jar"]
    assert m["mods"] == []
    assert [d["slug"] for d in m["datapacks"]] == ["edited-pack", "pack"]
    assert m["world"] == paper_repo.load_manifest()["world"]  # same type and Minecraft version: kept
    assert validate.validate(m, paper_repo) == []


def test_snapshot_server_turns_an_edited_datapack_into_a_patch(server, paper_repo):
    server.expect_lookup()
    m = snapshot.snapshot_server(server.root, repo=paper_repo, upstream=Upstream(server.modrinth.http))

    edited = next(d for d in m["datapacks"] if d["slug"] == "edited-pack")
    upstream_sha512 = server.original_version["files"][0]["hashes"]["sha512"]
    assert edited["file"] == "Edited Pack.zip"  # the name the world uses, not upstream's
    assert edited["hashes"]["sha512"] == upstream_sha512
    assert edited["patch"] == {"path": "patches/edited-pack", "base_sha512": upstream_sha512}
    files = patches.read(patches.folder(paper_repo, edited))
    assert files == {"pack.mcmeta": EDITED["pack.mcmeta"]}
    assert zip_contents(patches.apply(server.original, files)) == EDITED
    assert not (paper_repo.patches / "silvers_effects-library").exists(), "patch of a dropped pack is removed"


def test_snapshot_server_reads_datapacks_from_the_level_name(server, paper_repo):
    # A stray pack in the default world folder must be ignored: the server uses realm_world.
    write(server.root / "world" / "datapacks" / "stray.zip", make_zip({"pack.mcmeta": b"{}"}))
    server.expect_lookup()
    m = snapshot.snapshot_server(server.root, repo=paper_repo, upstream=Upstream(server.modrinth.http))
    assert len(m["datapacks"]) == 2


def test_snapshot_server_fails_on_files_not_on_modrinth_and_writes_nothing(server, paper_repo):
    unknown = write(server.root / "plugins" / "Homemade.jar", b"homemade")
    server.expect_lookup(unknown)
    before = paper_repo.manifest.read_bytes()
    with pytest.raises(SystemExit, match="Homemade.jar"):
        snapshot.snapshot_server(server.root, repo=paper_repo, upstream=Upstream(server.modrinth.http))
    assert paper_repo.manifest.read_bytes() == before
    assert (paper_repo.patches / "silvers_effects-library").exists()


def test_snapshot_server_refuses_a_datapack_edit_that_adds_files(server, paper_repo):
    server.edited = write(server.datapacks / "Edited Pack.zip", make_zip({**EDITED, "data/x/new.json": b"{}"}))
    server.expect_lookup()
    with pytest.raises(SystemExit, match="added"):
        snapshot.snapshot_server(server.root, repo=paper_repo, upstream=Upstream(server.modrinth.http))


def test_snapshot_server_can_pin_the_newest_java(server, paper_repo, recorded):
    server.expect_lookup()
    http = server.modrinth.http
    http.responses.update({k: v for k, v in recorded.responses.items() if "adoptium" in k})
    m = snapshot.snapshot_server(server.root, repo=paper_repo, upstream=Upstream(http), keep_java=False)
    assert m["java"]["file"].startswith("OpenJDK25U-jre_x64_windows")


# --- Fabric --------------------------------------------------------------------------------------

FABRIC_MC, LOADER = "26.3", "0.19.5"
INSTALLER = "1.1.2"  # the newest stable installer in the recorded Fabric meta response
JAR = {"fabric.mod.json": b'{"id": "edited"}', "data/edited/effects.json": b'{"strength": 1}'}
EDITED_JAR = {**JAR, "data/edited/effects.json": b'{"strength": 3}'}


class FakeFabricServer:
    """A Fabric server folder: launcher jar, version caches, three mods (one patched, one identical
    to its original), a datapack in a non-default world folder, and a folder inside mods/."""

    def __init__(self, root, modrinth, recorded, level="smp_world", seed="12345"):
        self.root, self.modrinth, self.level = root, modrinth, level
        http = modrinth.http
        http.responses.update({k: v for k, v in recorded.responses.items() if "meta.fabricmc.net" in k})
        write(root / "server.properties", f"level-name={level}\nlevel-seed={seed}\nrcon.password=hunter2\n")
        self.launcher = write(root / "fabric-server.jar", fabric_launcher(FABRIC_MC, LOADER, INSTALLER))
        self.meta_jar = serve_fabric_launcher(http, FABRIC_MC, LOADER, INSTALLER, self.launcher)
        write(root / "versions" / FABRIC_MC / f"server-{FABRIC_MC}.jar", b"vanilla server")
        write(root / ".fabric" / "server" / f"fabric-loader-server-{LOADER}-minecraft-{FABRIC_MC}.jar", b"loader")
        write(root / "mods" / "luckperms" / "config.yml", b"a mod's folder, not a mod")
        self.mod = write(root / "mods" / "Mod-1.0+26.3.jar", make_zip({"fabric.mod.json": b'{"id": "mod"}'}))
        self.same = write(root / "mods" / "same-1.0.jar", make_zip({"fabric.mod.json": b'{"id": "same"}'}))
        write(root / "mod-originals" / "same-1.0.jar", self.same)
        self.original = write(root / "mod-originals" / "edited-2.8.jar", make_zip(JAR))
        self.edited = write(root / "mods" / "edited-2.8.jar", make_zip(EDITED_JAR))
        self.pack = write(root / level / "datapacks" / "Pack.zip", make_zip(PACK))
        modrinth.publish(self.mod, "mod", "Mod-1.0+26.3.jar")
        modrinth.publish(self.same, "same", "same-1.0.jar")
        self.original_version = modrinth.publish(self.original, "edited", "edited-2.8.jar")
        modrinth.publish(self.pack, "pack", "Pack.zip")

    def expect_lookup(self, *extra):
        self.modrinth.expect_lookup(self.mod, self.same, self.original, self.edited, self.pack, *extra)

    def snapshot(self, repo, **kw):
        return snapshot.snapshot_server(self.root, repo=repo, upstream=Upstream(self.modrinth.http), **kw)


@pytest.fixture
def fabric(tmp_path, fake_modrinth, recorded):
    return FakeFabricServer(tmp_path / "smp", fake_modrinth, recorded)


def test_snapshot_fabric_server_writes_a_valid_manifest(fabric, paper_repo, capsys):
    """Snapshot over the frozen Paper release: a switch from Paper to Fabric."""
    fabric.expect_lookup()
    m = fabric.snapshot(paper_repo)

    assert paper_repo.load_manifest() == m
    assert list(m) == ["name", "version", "minecraft", "java", "server", "world", "plugins", "mods", "datapacks"]
    assert m["minecraft"] == FABRIC_MC
    assert m["server"] == entries.fabric(FABRIC_MC, LOADER, INSTALLER, fabric.meta_jar)
    assert m["server"]["file"] == "fabric-server-mc.26.3-loader.0.19.5-launcher.1.1.2.jar"
    assert m["server"]["url"] == "https://meta.fabricmc.net/v2/versions/loader/26.3/0.19.5/1.1.2/server/jar"
    assert m["plugins"] == []
    assert [(e["slug"], e["file"]) for e in m["mods"]] == [
        ("edited", "edited-2.8.jar"), ("mod", "Mod-1.0+26.3.jar"), ("same", "same-1.0.jar")]
    assert [d["file"] for d in m["datapacks"]] == ["Pack.zip"]
    assert m["java"] == paper_repo.load_manifest()["java"]
    # The old manifest was Paper on another Minecraft version, so the world comes from server.properties.
    assert m["world"] == {"level_name": "smp_world", "seed": "12345"}
    assert validate.validate(m, paper_repo) == []
    assert sorted(p.name for p in paper_repo.patches.iterdir()) == ["edited"], "the Paper pack's patch is gone"
    assert "note:" not in capsys.readouterr().out  # the local launcher is meta's jar


def test_snapshot_fabric_server_turns_an_edited_mod_into_a_patch(fabric, fabric_repo):
    fabric.expect_lookup()
    m = fabric.snapshot(fabric_repo)

    edited = next(e for e in m["mods"] if e["slug"] == "edited")
    upstream_sha512 = fabric.original_version["files"][0]["hashes"]["sha512"]
    assert edited["hashes"]["sha512"] == upstream_sha512
    assert edited["patch"] == {"path": "patches/edited", "base_sha512": upstream_sha512}
    files = patches.read(patches.folder(fabric_repo, edited))
    assert files == {"data/edited/effects.json": EDITED_JAR["data/edited/effects.json"]}
    assert zip_contents(patches.apply(fabric.original, files)) == EDITED_JAR
    assert "patch" not in next(e for e in m["mods"] if e["slug"] == "same"), "identical to its original"
    assert sorted(p.name for p in fabric_repo.patches.iterdir()) == ["edited"], "the old release's patches are gone"


def test_snapshot_fabric_server_pins_meta_launcher_even_if_the_local_one_differs(fabric, fabric_repo, capsys):
    write(fabric.root / "fabric-server.jar", fabric_launcher(FABRIC_MC, LOADER, "1.0.3"))  # an older installer
    fabric.expect_lookup()
    m = fabric.snapshot(fabric_repo)
    assert m["server"] == entries.fabric(FABRIC_MC, LOADER, INSTALLER, fabric.meta_jar)
    out = capsys.readouterr().out
    assert "note: fabric-server.jar (installer 1.0.3) is not byte-identical" in out and "installer 1.1.2" in out


def test_snapshot_fabric_server_keeps_the_world_when_type_and_version_are_unchanged(fabric, fabric_repo):
    frozen = fabric_repo.load_manifest()  # Fabric on 26.3, like the fake server
    fabric.expect_lookup()
    m = fabric.snapshot(fabric_repo)
    assert m["world"] == frozen["world"] != {"level_name": "smp_world", "seed": "12345"}
    assert (m["name"], m["version"], m["java"]) == (frozen["name"], frozen["version"], frozen["java"])
    assert validate.validate(m, fabric_repo) == []


def test_snapshot_fabric_server_fails_on_mods_not_on_modrinth(fabric, fabric_repo):
    unknown = write(fabric.root / "mods" / "homemade-1.0.jar", make_zip({"fabric.mod.json": b"{}"}))
    fabric.expect_lookup(unknown)
    before = fabric_repo.manifest.read_bytes()
    with pytest.raises(SystemExit, match="homemade-1.0.jar"):
        fabric.snapshot(fabric_repo)
    assert fabric_repo.manifest.read_bytes() == before


@pytest.mark.parametrize("seed, expected", [
    ("", ""), ("-5", "-5"), ("abc", "96354"), ("polygenelubricants", "-2147483648"),
    ("99999999999999999999", "1260560192"),  # too big for a long: Minecraft hashes it like text
])
def test_level_seed_is_the_number_minecraft_uses(tmp_path, seed, expected):
    write(tmp_path / "server.properties", f"level-seed={seed}\n")
    assert snapshot.level_seed(tmp_path) == expected


def test_read_fabric_launcher(tmp_path):
    write(tmp_path / "fabric-server.jar", fabric_launcher("26.3", "0.19.5", "1.1.2"))
    found = snapshot.read_fabric_launcher(tmp_path / "fabric-server.jar")
    assert found == snapshot.FabricLauncher(tmp_path / "fabric-server.jar", "26.3", "0.19.5", "1.1.2")
    write(tmp_path / "paper.jar", make_zip({"META-INF/MANIFEST.MF": b"Main-Class: io.papermc.paperclip.Main\n"}))
    write(tmp_path / "broken.jar", b"not a zip")
    assert snapshot.read_fabric_launcher(tmp_path / "paper.jar") is None
    assert snapshot.read_fabric_launcher(tmp_path / "broken.jar") is None


def test_detect_server_refuses_unclear_folders(tmp_path, fabric, server):
    with pytest.raises(SystemExit, match="neither a Paper server"):
        snapshot.detect_server(tmp_path / "empty")
    assert snapshot.detect_server(server.root) is None
    assert snapshot.detect_server(fabric.root).loader == LOADER
    write(server.root / "fabric-server.jar", fabric_launcher(FABRIC_MC, LOADER, INSTALLER))
    with pytest.raises(SystemExit, match="both paper.jar and a Fabric launcher"):
        snapshot.detect_server(server.root)
    (server.root / "paper.jar").unlink()
    with pytest.raises(SystemExit, match="no mods/ folder"):
        snapshot.detect_server(server.root)


def client_instance(root, modrinth, mc, loader):
    """A Prism instance with one mod and one shader on Modrinth, one private mod, configs and options."""
    instance = root / "Factions Client" / "minecraft"
    write(instance.parent / "mmc-pack.json", json.dumps(
        {"components": [{"uid": "net.minecraft", "version": mc},
                        {"uid": "net.fabricmc.fabric-loader", "version": loader}]}))
    mod = write(instance / "mods" / "sodium.jar", b"sodium")
    private = write(instance / "mods" / "private.jar", b"not on modrinth")
    shader = write(instance / "shaderpacks" / "shader.zip", b"shader")
    write(instance / "shaderpacks" / "shader.zip.txt", "profile=HIGH")
    write(instance / "config" / "sodium.json", "{}")
    write(instance / "config" / "sodium.json.bak", "{}")
    write(instance / "options.txt", "fov:0.5")
    modrinth.publish(mod, "sodium", "sodium-fabric.jar")
    modrinth.publish(shader, "shader", "shader.zip")
    modrinth.expect_lookup(mod, private, shader)
    return instance


@pytest.mark.parametrize("release", ["paper_repo", "fabric_repo"])
def test_snapshot_client(tmp_path, fake_modrinth, request, release):
    repo = request.getfixturevalue(release)
    mc = repo.load_manifest()["minecraft"]  # the client pack follows the server manifest
    instance = client_instance(tmp_path, fake_modrinth, mc, "0.99.0")
    profile = fabric_profile(mc, "0.99.0")
    fake_modrinth.http.add("GET", fabric_profile_url(mc, "0.99.0"), profile)

    index = snapshot.snapshot_client(instance, repo=repo, upstream=Upstream(fake_modrinth.http))

    assert [f["path"] for f in index["files"]] == ["mods/sodium.jar", "shaderpacks/shader.zip"]
    assert index["dependencies"] == {"minecraft": mc, "fabric-loader": "0.99.0"}
    assert index["versionId"] == repo.load_manifest()["version"]
    overrides = repo.client / "overrides"
    assert sorted(p.relative_to(overrides).as_posix() for p in overrides.rglob("*") if p.is_file()) == [
        "config/sodium.json", "options.txt", "shaderpacks/shader.zip.txt"]
    assert load_json(repo.fabric_profile) == profile
    assert validate.validate_client(repo.load_manifest(), repo) == []


def test_snapshot_client_pins_the_recorded_launcher_profile(tmp_path, fake_modrinth, recorded, fabric_repo, capsys):
    fabric_repo.fabric_profile.unlink()
    instance = client_instance(tmp_path, fake_modrinth, "26.3", "0.19.5")
    fake_modrinth.http.responses.update({k: v for k, v in recorded.responses.items() if "meta.fabricmc.net" in k})

    snapshot.snapshot_client(instance, repo=fabric_repo, upstream=Upstream(fake_modrinth.http))

    pinned = load_json(fabric_repo.fabric_profile)
    assert pinned == recorded.get_json(fabric_profile_url("26.3", "0.19.5"))
    assert pinned["id"] == "fabric-loader-0.19.5-26.3" and pinned["inheritsFrom"] == "26.3"
    assert fabric_repo.fabric_profile.read_bytes().endswith(b"}\n"), "stored like every repo JSON file"
    assert "client/fabric-profile.json: fabric-loader-0.19.5-26.3\n" in capsys.readouterr().out
    assert validate.validate_client(fabric_repo.load_manifest(), fabric_repo) == []


def test_snapshot_client_refuses_a_bad_profile_and_writes_nothing(tmp_path, fake_modrinth, fabric_repo):
    instance = client_instance(tmp_path, fake_modrinth, "26.3", "0.19.6")
    fake_modrinth.http.add("GET", fabric_profile_url("26.3", "0.19.6"), fabric_profile("26.3", "0.19.5"))
    index_before = (fabric_repo.client / "modrinth.index.json").read_bytes()
    profile_before = fabric_repo.fabric_profile.read_bytes()
    with pytest.raises(SystemExit, match="id must be fabric-loader-0.19.6-26.3"):
        snapshot.snapshot_client(instance, repo=fabric_repo, upstream=Upstream(fake_modrinth.http))
    assert (fabric_repo.client / "modrinth.index.json").read_bytes() == index_before
    assert fabric_repo.fabric_profile.read_bytes() == profile_before


def test_snapshot_profile_repins_only_the_profile(fabric_repo, recorded):
    fabric_repo.fabric_profile.unlink()
    index_before = (fabric_repo.client / "modrinth.index.json").read_bytes()
    snapshot.main(["profile"], repo=fabric_repo, upstream=Upstream(recorded))
    assert load_json(fabric_repo.fabric_profile) == recorded.get_json(fabric_profile_url("26.3", "0.19.5"))
    assert (fabric_repo.client / "modrinth.index.json").read_bytes() == index_before


def test_snapshot_profile_keeps_the_file_when_only_the_generation_time_changed(fabric_repo, capsys):
    served = fabric_profile("26.3", "0.19.5")
    served.update(time="2027-01-01T00:00:00+0000", releaseTime="2027-01-01T00:00:00+0000")
    http = RecordedHttp().add("GET", fabric_profile_url("26.3", "0.19.5"), served)
    before = fabric_repo.fabric_profile.read_bytes()
    snapshot.main(["profile"], repo=fabric_repo, upstream=Upstream(http))
    assert fabric_repo.fabric_profile.read_bytes() == before
    assert "(unchanged)" in capsys.readouterr().out
    served["mainClass"] = "net.fabricmc.loader.impl.launch.knot.KnotClientNew"
    snapshot.main(["profile"], repo=fabric_repo, upstream=Upstream(http))
    assert load_json(fabric_repo.fabric_profile) == served


@pytest.mark.parametrize("what", ["server", "client"])
def test_snapshot_needs_a_path_for_server_and_client(what, capsys):
    with pytest.raises(SystemExit):
        snapshot.main([what])
    assert f"'{what}' needs a path" in capsys.readouterr().err
