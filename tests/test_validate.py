import copy
import hashlib
import zipfile

import pytest
from conftest import make_zip, serve_fabric_launcher

import build
import defaults
import entries
import patches
import validate
from repo import REPO, load_json, save_json
from upstream import RecordedHttp, Upstream


def test_real_repo_is_valid(real_manifest):
    assert validate.validate(real_manifest) == []
    assert validate.validate_package() == []
    assert validate.validate_client(real_manifest) == []
    assert validate.main([]) == 0


@pytest.mark.parametrize("mutate, message", [
    (lambda m: m["plugins"][0].update(url="http://evil.example/x.jar"), "allowed host"),
    (lambda m: m["plugins"][0].update(hashes={"sha512": "ABC"}), "lowercase hex"),
    (lambda m: m["plugins"].append(copy.deepcopy(m["plugins"][0])), "duplicate file"),
    (lambda m: m["datapacks"][1].update(slug=m["datapacks"][0]["slug"]), "duplicate project"),
    (lambda m: m["datapacks"][0].update(file="bad:name.zip"), "characters Windows"),
    (lambda m: m["world"].update(seed="abc"), "seed"),
    (lambda m: m.update(version="1.0"), "1.2.3"),
    (lambda m: m.pop("world"), "missing 'world'"),
    (lambda m: m["datapacks"][0].update(patch={"path": "patches/does-not-exist",
                                               "base_sha512": m["datapacks"][0]["hashes"]["sha512"]}),
     "missing or empty"),
    (lambda m: next(d for d in m["datapacks"] if "patch" in d)["hashes"].update(sha512="0" * 128), "base_sha512"),
    (lambda m: [d.pop("patch", None) for d in m["datapacks"]], "not used by any mod or datapack"),
])
def test_validate_catches_mistakes(real_manifest, mutate, message):
    mutate(real_manifest)
    errors = validate.validate(real_manifest)
    assert any(message in e for e in errors), errors


def test_template_placeholders_are_exactly_the_supported_tokens():
    text = (REPO.defaults / "server.properties").read_text(encoding="utf-8")
    assert defaults.placeholders(text) == set(defaults.TOKENS)


@pytest.mark.parametrize("edit, message", [
    (lambda t: t + "motd={{MOTD}}\n", "unsupported placeholder {{MOTD}}"),
    (lambda t: t.replace("{{SEED}}", "12345"), "missing {{SEED}}"),
    (lambda t: t.replace("rcon.password={{RCON_PASSWORD}}", "rcon.password=hunter2"), "real RCON password"),
])
def test_validate_package_checks_the_server_properties_template(repo_copy, edit, message):
    props = repo_copy.defaults / "server.properties"
    props.write_text(edit(props.read_text(encoding="utf-8")), encoding="utf-8")
    errors = validate.validate_package(repo_copy)
    assert any(message in e for e in errors), errors


def test_validate_package_requires_the_launchers(repo_copy):
    (repo_copy.package / "Start Server.bat").unlink()
    assert "package/Start Server.bat is missing" in validate.validate_package(repo_copy)


# --- online: downloads and patch fit, served by RecordedHttp ---------------------------------------

def serve(http, entry, data, algo="sha512"):
    """Pin `entry` to `data` and serve `data` at its URL."""
    entry.update(size=len(data), hashes={algo: hashlib.new(algo, data).hexdigest()})
    http.add("GET", entry["url"], data)


@pytest.fixture
def online(repo_copy, real_manifest):
    """A manifest whose downloads are tiny recorded files; the patched datapack's patch fits."""
    m = copy.deepcopy(real_manifest)
    http = RecordedHttp()
    serve(http, m["java"], b"java bytes", "sha256")
    serve(http, m["server"], b"paper bytes", "sha256")
    m["plugins"] = m["plugins"][:1]
    serve(http, m["plugins"][0], b"plugin bytes")
    m["datapacks"] = [d for d in m["datapacks"] if "patch" in d]
    effects = m["datapacks"][0]
    serve(http, effects, make_zip({"pack.mcmeta": b"upstream", "data/a.json": b"{}"}))
    effects["patch"]["base_sha512"] = effects["hashes"]["sha512"]
    assert validate.validate(m, repo_copy) == []
    return m, http, repo_copy


def test_verify_online_downloads_and_applies_patches(online):
    m, http, repo = online
    assert validate.verify_online(m, Upstream(http), repo) == []


def test_verify_online_catches_a_changed_download(online):
    m, http, repo = online
    http.add("GET", m["plugins"][0]["url"], b"plugin bytes, re-uploaded")
    errors = validate.verify_online(m, Upstream(http), repo)
    assert errors == [f"plugin {m['plugins'][0]['file']}: download doesn't match the pinned size/hash"]


def test_verify_online_catches_a_patch_that_no_longer_fits(online):
    m, http, repo = online
    effects = m["datapacks"][0]
    patches.write(patches.folder(repo, effects), {"pack.mcmeta": b"patched", "data/gone.json": b"{}"})
    errors = validate.verify_online(m, Upstream(http), repo)
    assert len(errors) == 1 and "doesn't fit" in errors[0] and "data/gone.json" in errors[0]


# --- server types, mods, and 1.x manifests ---------------------------------------------------------

@pytest.fixture
def fabric_manifest(real_manifest):
    """A Fabric manifest made from the real one: plugins become mods, the patched pack a patched mod."""
    m = copy.deepcopy(real_manifest)
    patched = next(d for d in m["datapacks"] if "patch" in d)
    m.update(minecraft="26.3", server=entries.fabric("26.3", "0.19.5", "1.1.2", b"launcher bytes"),
             plugins=[], mods=m["plugins"][:3] + [patched],
             datapacks=[d for d in m["datapacks"] if "patch" not in d])
    return m


def test_a_fabric_manifest_with_a_patched_mod_is_valid(fabric_manifest, repo_copy):
    assert validate.validate(fabric_manifest, repo_copy) == []


@pytest.mark.parametrize("mutate, message", [
    (lambda m: m["plugins"].append(copy.deepcopy(m["mods"][0])), "a fabric server can't use plugins"),
    (lambda m: m["server"].update(url=m["server"]["url"].replace("0.19.5", "0.19.4")), "server: url must be"),
    (lambda m: m["server"].update(file="fabric-server.jar"), "server: file must be"),
    (lambda m: m.update(minecraft="26.4"), "server: url must be"),
    (lambda m: m["server"].pop("loader"), "needs 'loader'"),
    (lambda m: m["server"].update(type="forge"), "type must be one of paper, fabric"),
    (lambda m: m["mods"].append(copy.deepcopy(m["mods"][0])), "mods: duplicate file"),
    (lambda m: m["mods"][-1].update(patch={"path": "patches/nope", "base_sha512": m["mods"][-1]["hashes"]["sha512"]}),
     "missing or empty"),
    (lambda m: m["mods"][-1]["hashes"].update(sha512="0" * 128), "base_sha512"),
    (lambda m: m["datapacks"].append({**copy.deepcopy(m["mods"][-1]), "file": "other.zip", "slug": "other"}),
     "is also used by mod"),
    (lambda m: m["mods"][-1].pop("patch"), "not used by any mod or datapack"),
    (lambda m: m.update(mods={"not": "a list"}), "'mods' must be a list"),
])
def test_validate_catches_fabric_mistakes(fabric_manifest, repo_copy, mutate, message):
    mutate(fabric_manifest)
    errors = validate.validate(fabric_manifest, repo_copy)
    assert any(message in e for e in errors), errors


def test_a_paper_server_cannot_use_mods(real_manifest):
    real_manifest["mods"] = [copy.deepcopy(real_manifest["plugins"][0])]
    assert "mods: a paper server can't use mods (1 listed)" in validate.validate(real_manifest)


def test_a_1x_manifest_without_mods_still_validates_and_builds(repo_copy, tmp_path):
    raw = load_json(repo_copy.manifest)
    raw.pop("mods", None)
    save_json(repo_copy.manifest, raw)
    assert "mods" not in load_json(repo_copy.manifest)
    assert validate.validate(raw, repo_copy) == []
    assert validate.main([], repo=repo_copy) == 0
    assert repo_copy.load_manifest()["mods"] == []  # readers see an empty group
    names = zipfile.ZipFile(build.build_server(raw["version"], repo_copy, tmp_path)).namelist()
    assert "TheRealms-Server/realms/manifest.json" in names


def test_verify_online_covers_the_fabric_launcher_and_patched_mods(fabric_manifest, repo_copy):
    m, http = fabric_manifest, RecordedHttp()
    serve(http, m["java"], b"java bytes", "sha256")
    m["server"] = entries.fabric("26.3", "0.19.5", "1.1.2", serve_fabric_launcher(http, "26.3", "0.19.5", "1.1.2"))
    m["mods"] = m["mods"][-1:]
    m["datapacks"] = []
    patched = m["mods"][0]
    serve(http, patched, make_zip({"pack.mcmeta": b"upstream", "fabric.mod.json": b"{}"}))
    patched["patch"]["base_sha512"] = patched["hashes"]["sha512"]
    assert validate.verify_online(m, Upstream(http), repo_copy) == []
    patches.write(patches.folder(repo_copy, patched), {"pack.mcmeta": b"x", "gone.json": b"{}"})
    (error,) = validate.verify_online(m, Upstream(http), repo_copy)
    assert error.startswith("mod ") and "doesn't fit" in error
