"""Snapshots of a fake server folder and client instance, with Modrinth/Paper answers keyed to the
hashes of the tiny files each test makes."""
import json

import pytest
from conftest import make_zip, paper_build, paper_builds_url, zip_contents

import patches
import snapshot
import validate
from upstream import Upstream

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


def test_snapshot_server_writes_a_valid_manifest(server, repo_copy):
    server.expect_lookup()
    m = snapshot.snapshot_server(server.root, repo=repo_copy, upstream=Upstream(server.modrinth.http))

    assert repo_copy.load_manifest() == m
    assert m["minecraft"] == MC and m["server"]["build"] == 74
    assert m["java"] == repo_copy.load_manifest()["java"]  # kept by default
    assert [p["file"] for p in m["plugins"]] == ["Plugin-1.0.jar"]
    assert [d["slug"] for d in m["datapacks"]] == ["edited-pack", "pack"]
    assert validate.validate(m, repo_copy) == []


def test_snapshot_server_turns_an_edited_datapack_into_a_patch(server, repo_copy):
    server.expect_lookup()
    m = snapshot.snapshot_server(server.root, repo=repo_copy, upstream=Upstream(server.modrinth.http))

    edited = next(d for d in m["datapacks"] if d["slug"] == "edited-pack")
    upstream_sha512 = server.original_version["files"][0]["hashes"]["sha512"]
    assert edited["file"] == "Edited Pack.zip"  # the name the world uses, not upstream's
    assert edited["hashes"]["sha512"] == upstream_sha512
    assert edited["patch"] == {"path": "patches/edited-pack", "base_sha512": upstream_sha512}
    files = patches.read(patches.folder(repo_copy, edited))
    assert files == {"pack.mcmeta": EDITED["pack.mcmeta"]}
    assert zip_contents(patches.apply(server.original, files)) == EDITED
    assert not (repo_copy.patches / "silvers_effects-library").exists(), "patch of a dropped pack is removed"


def test_snapshot_server_reads_datapacks_from_the_level_name(server, repo_copy):
    # A stray pack in the default world folder must be ignored: the server uses realm_world.
    write(server.root / "world" / "datapacks" / "stray.zip", make_zip({"pack.mcmeta": b"{}"}))
    server.expect_lookup()
    m = snapshot.snapshot_server(server.root, repo=repo_copy, upstream=Upstream(server.modrinth.http))
    assert len(m["datapacks"]) == 2


def test_snapshot_server_fails_on_files_not_on_modrinth_and_writes_nothing(server, repo_copy):
    unknown = write(server.root / "plugins" / "Homemade.jar", b"homemade")
    server.expect_lookup(unknown)
    before = repo_copy.manifest.read_bytes()
    with pytest.raises(SystemExit, match="Homemade.jar"):
        snapshot.snapshot_server(server.root, repo=repo_copy, upstream=Upstream(server.modrinth.http))
    assert repo_copy.manifest.read_bytes() == before
    assert (repo_copy.patches / "silvers_effects-library").exists()


def test_snapshot_server_refuses_a_datapack_edit_that_adds_files(server, repo_copy):
    server.edited = write(server.datapacks / "Edited Pack.zip", make_zip({**EDITED, "data/x/new.json": b"{}"}))
    server.expect_lookup()
    with pytest.raises(SystemExit, match="added"):
        snapshot.snapshot_server(server.root, repo=repo_copy, upstream=Upstream(server.modrinth.http))


def test_snapshot_server_can_pin_the_newest_java(server, repo_copy, recorded):
    server.expect_lookup()
    http = server.modrinth.http
    http.responses.update({k: v for k, v in recorded.responses.items() if "adoptium" in k})
    m = snapshot.snapshot_server(server.root, repo=repo_copy, upstream=Upstream(http), keep_java=False)
    assert m["java"]["file"].startswith("OpenJDK25U-jre_x64_windows")


def test_snapshot_client(tmp_path, fake_modrinth, repo_copy):
    instance = tmp_path / "Factions Client" / "minecraft"
    write(instance.parent / "mmc-pack.json", json.dumps(
        {"components": [{"uid": "net.minecraft", "version": MC},
                        {"uid": "net.fabricmc.fabric-loader", "version": "0.99.0"}]}))
    mod = write(instance / "mods" / "sodium.jar", b"sodium")
    private = write(instance / "mods" / "private.jar", b"not on modrinth")
    shader = write(instance / "shaderpacks" / "shader.zip", b"shader")
    write(instance / "shaderpacks" / "shader.zip.txt", "profile=HIGH")
    write(instance / "config" / "sodium.json", "{}")
    write(instance / "config" / "sodium.json.bak", "{}")
    write(instance / "options.txt", "fov:0.5")
    fake_modrinth.publish(mod, "sodium", "sodium-fabric.jar")
    fake_modrinth.publish(shader, "shader", "shader.zip")
    fake_modrinth.expect_lookup(mod, private, shader)

    index = snapshot.snapshot_client(instance, repo=repo_copy, upstream=Upstream(fake_modrinth.http))

    assert [f["path"] for f in index["files"]] == ["mods/sodium.jar", "shaderpacks/shader.zip"]
    assert index["dependencies"] == {"minecraft": MC, "fabric-loader": "0.99.0"}
    assert index["versionId"] == repo_copy.load_manifest()["version"]
    overrides = repo_copy.client / "overrides"
    assert sorted(p.relative_to(overrides).as_posix() for p in overrides.rglob("*") if p.is_file()) == [
        "config/sodium.json", "options.txt", "shaderpacks/shader.zip.txt"]
    assert validate.validate_client(repo_copy.load_manifest(), repo_copy) == []
