"""pin_github.py: one of our own mods pinned from a GitHub release (ADR-0009), server and players' pack."""
import hashlib

import pytest
from conftest import make_zip

import entries
import pin_github
import validate
from repo import load_json, save_json
from upstream import RecordedHttp, Upstream

SLUG, REPO_NAME = "patina-and-chime", "gr8monk3ys/patina-and-chime"


def mod_jar(version="0.2.0+26.3", extra=b"") -> bytes:
    return make_zip({"fabric.mod.json": f'{{"id": "patinachime", "version": "{version}"}}', "extra": extra})


def load(repo):
    return repo.load_manifest(), load_json(repo.client / "modrinth.index.json")


def test_pin_adds_the_mod_to_the_server_and_the_pack(fabric_repo):
    manifest, index = load(fabric_repo)
    jar = mod_jar()
    file = "patina-and-chime-0.2.0+26.3.jar"

    out, new_index = pin_github.pin(manifest, index, SLUG, "v0.2.0", file, jar)

    url = f"https://github.com/{REPO_NAME}/releases/download/v0.2.0/patina-and-chime-0.2.0%2B26.3.jar"
    sha512 = hashlib.sha512(jar).hexdigest()
    pin = next(e for e in out["mods"] if e["slug"] == SLUG)
    assert pin == {"slug": SLUG, "github": REPO_NAME, "tag": "v0.2.0", "version": "0.2.0+26.3", "file": file,
                   "url": url, "size": len(jar), "hashes": {"sha512": sha512}}
    assert [e["slug"] for e in out["mods"]] == sorted(e["slug"] for e in manifest["mods"] + [pin])
    client = next(f for f in new_index["files"] if f["path"] == f"mods/{file}")
    assert client == {"path": f"mods/{file}", "hashes": {"sha1": hashlib.sha1(jar).hexdigest(), "sha512": sha512},
                      "env": {"client": "required", "server": "unsupported"}, "downloads": [url],
                      "fileSize": len(jar)}
    assert entries.github_pin_of(client, out) == pin
    # Nothing else moved, and the inputs are untouched.
    assert [e for e in out["mods"] if e is not pin] == manifest["mods"]
    assert [f for f in new_index["files"] if f is not client] == index["files"]
    assert SLUG not in [e["slug"] for e in manifest["mods"]]
    fabric_repo.save_manifest(out)
    save_json(fabric_repo.client / "modrinth.index.json", new_index)
    assert validate.validate(out, fabric_repo) == []
    assert validate.validate_client(out, fabric_repo) == []


def test_pin_keeps_the_index_in_its_order(fabric_repo):
    """mods/ by path ignoring case, then everything else as it was."""
    manifest, index = load(fabric_repo)
    _, new_index = pin_github.pin(manifest, index, SLUG, "v0.2.0", "patina-and-chime-0.2.0.jar", mod_jar())
    paths = [f["path"] for f in new_index["files"]]
    mods = [p for p in paths if p.startswith("mods/")]
    assert mods == sorted(mods, key=str.lower) and paths[:len(mods)] == mods
    assert paths[len(mods):] == [f["path"] for f in index["files"] if not f["path"].startswith("mods/")]


def test_pinning_a_new_release_replaces_the_old_one(fabric_repo):
    manifest, index = load(fabric_repo)
    manifest, index = pin_github.pin(manifest, index, SLUG, "v0.2.0", "patina-and-chime-0.2.0.jar", mod_jar("0.2.0"))
    newer = mod_jar("0.2.1", extra=b"a shatter switch")

    out, new_index = pin_github.pin(manifest, index, SLUG, "v0.2.1", "patina-and-chime-0.2.1.jar", newer)

    assert [(e["tag"], e["version"], e["file"]) for e in out["mods"] if e["slug"] == SLUG] == [
        ("v0.2.1", "0.2.1", "patina-and-chime-0.2.1.jar")]
    assert [f["path"] for f in new_index["files"] if "patina" in f["path"]] == ["mods/patina-and-chime-0.2.1.jar"]
    assert len(out["mods"]) == len(manifest["mods"]) and len(new_index["files"]) == len(index["files"])
    fabric_repo.save_manifest(out)
    save_json(fabric_repo.client / "modrinth.index.json", new_index)
    assert validate.validate(out, fabric_repo) == []
    assert validate.validate_client(out, fabric_repo) == []


def test_pinning_the_same_release_twice_changes_nothing(fabric_repo):
    manifest, index = load(fabric_repo)
    once = pin_github.pin(manifest, index, SLUG, "v0.2.0", "patina-and-chime-0.2.0.jar", mod_jar())
    assert pin_github.pin(*once, SLUG, "v0.2.0", "patina-and-chime-0.2.0.jar", mod_jar()) == once


@pytest.mark.parametrize("slug, jar, message", [
    ("lithium", mod_jar(), "lithium can't be pinned from GitHub"),
    (SLUG, b"not a zip", "not a Fabric mod jar"),
    (SLUG, make_zip({"plugin.yml": "name: x"}), "not a Fabric mod jar"),
    (SLUG, make_zip({"fabric.mod.json": "{not json"}), "not a Fabric mod jar"),
    (SLUG, make_zip({"fabric.mod.json": '{"id": "patinachime"}'}), "not a Fabric mod jar"),
    (SLUG, make_zip({"fabric.mod.json": '{"version": 2}'}), "has no version"),
])
def test_pin_refuses(fabric_repo, slug, jar, message):
    manifest, index = load(fabric_repo)
    with pytest.raises(SystemExit, match=message):
        pin_github.pin(manifest, index, slug, "v0.2.0", "patina-and-chime-0.2.0.jar", jar)


def test_pin_refuses_a_paper_server(paper_repo):
    manifest, index = load(paper_repo)
    with pytest.raises(SystemExit, match="a paper server can't run mods"):
        pin_github.pin(manifest, index, SLUG, "v0.2.0", "patina-and-chime-0.2.0.jar", mod_jar())


def test_pin_refuses_to_replace_a_modrinth_pin(fabric_repo):
    """Once the mod is on Modrinth and pinned from there, the GitHub pin is not put back by accident."""
    manifest, index = load(fabric_repo)
    manifest["mods"][0] = {**manifest["mods"][0], "slug": SLUG}
    with pytest.raises(SystemExit, match="pinned from Modrinth"):
        pin_github.pin(manifest, index, SLUG, "v0.2.0", "patina-and-chime-0.2.0.jar", mod_jar())


def test_main_downloads_the_release_and_writes_both_files(fabric_repo, capsys):
    jar = mod_jar()
    file = "patina-and-chime-0.2.0+26.3.jar"
    http = RecordedHttp().add("GET", entries.github_url(REPO_NAME, "v0.2.0", file), jar)

    pin_github.main([SLUG, "v0.2.0", file], repo=fabric_repo, upstream=Upstream(http))

    manifest, index = load(fabric_repo)
    pin = next(e for e in manifest["mods"] if e["slug"] == SLUG)
    assert entries.matches(pin, jar) and pin["version"] == "0.2.0+26.3"
    assert entries.github_pin_of(next(f for f in index["files"] if f["path"] == f"mods/{file}"), manifest) == pin
    assert validate.validate(manifest, fabric_repo) == []
    assert validate.validate_client(manifest, fabric_repo) == []
    assert capsys.readouterr().out == (
        f"pinned patina-and-chime 0.2.0+26.3 ({file}, {len(jar)} bytes) from {REPO_NAME} v0.2.0, "
        "server and players' pack\n")
    assert fabric_repo.manifest.read_bytes().endswith(b"}\n")


def test_main_refuses_a_mod_that_is_not_listed(fabric_repo):
    with pytest.raises(SystemExit):
        pin_github.main(["lithium", "v1.0", "lithium.jar"], repo=fabric_repo, upstream=Upstream(RecordedHttp()))
