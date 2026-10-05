import copy
import hashlib

import pytest
from conftest import make_zip

import defaults
import patches
import validate
from repo import REPO
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
    (lambda m: [d.pop("patch", None) for d in m["datapacks"]], "not used by any datapack"),
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
