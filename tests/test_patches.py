import shutil

import pytest
from conftest import make_zip, patched_entry, zip_contents

import patches

ORIGINAL = {"pack.mcmeta": b'{"pack": {"pack_format": 55}}', "data/x/function/a.mcfunction": b"say a",
            "data/x/function/b.mcfunction": b"say b"}


def test_make_returns_only_the_edited_files():
    edited = {**ORIGINAL, "pack.mcmeta": b'{"pack": {"pack_format": 99}}'}
    assert patches.make(make_zip(ORIGINAL), make_zip(edited)) == {"pack.mcmeta": b'{"pack": {"pack_format": 99}}'}


@pytest.mark.parametrize("edited, word", [
    ({**ORIGINAL, "data/x/function/new.mcfunction": b"say new"}, "added"),
    ({k: v for k, v in ORIGINAL.items() if k != "pack.mcmeta"}, "removed"),
])
def test_make_refuses_added_or_removed_files(edited, word):
    with pytest.raises(patches.PatchError, match=word):
        patches.make(make_zip(ORIGINAL), make_zip(edited))


def test_write_then_read_round_trips_nested_paths(tmp_path):
    files = {"pack.mcmeta": b"x", "data/x/function/a.mcfunction": b"y"}
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "stale.txt").write_bytes(b"old")
    patches.write(tmp_path / "p", files)
    assert patches.read(tmp_path / "p") == files


def test_apply_replaces_files_and_keeps_the_rest():
    out = patches.apply(make_zip(ORIGINAL), {"data/x/function/a.mcfunction": b"say patched"})
    assert zip_contents(out) == {**ORIGINAL, "data/x/function/a.mcfunction": b"say patched"}


def test_apply_inverts_make():
    edited = {**ORIGINAL, "data/x/function/b.mcfunction": b"say edited"}
    patch = patches.make(make_zip(ORIGINAL), make_zip(edited))
    assert zip_contents(patches.apply(make_zip(ORIGINAL), patch)) == edited


def test_apply_refuses_a_file_the_zip_does_not_have():
    with pytest.raises(patches.PatchError, match="data/x/missing.json"):
        patches.apply(make_zip(ORIGINAL), {"data/x/missing.json": b"{}"})


# --- check: a manifest's patches against the repo (a Paper release patches a datapack, Fabric mods) ---

RELEASES = ["paper_repo", "fabric_repo"]


@pytest.fixture(params=RELEASES)
def release(request):
    """A frozen release repo, and its manifest with the first patched mod/datapack."""
    repo = request.getfixturevalue(request.param)
    manifest = repo.load_manifest()
    kind, entry = patched_entry(manifest)
    return repo, manifest, kind, entry


def test_release_patches_check_out(release):
    repo, manifest, kind, _ = release
    assert patches.check(manifest, repo) == []
    assert kind == ("datapack" if repo.root.name.startswith("paper") else "mod")


def test_reference_pins_the_base_hash():
    assert patches.reference("slug", "ab" * 64) == {"path": "patches/slug", "base_sha512": "ab" * 64}


def test_check_catches_a_patch_made_against_another_upstream_file(release):
    repo, manifest, kind, entry = release
    entry["hashes"]["sha512"] = "0" * 128  # the pin moved, the patch didn't
    errors = patches.check(manifest, repo)
    assert any(e.startswith(f"{kind} {entry['file']}:") and "base_sha512" in e for e in errors), errors


def test_check_catches_an_orphan_folder(release):
    repo, manifest, _, _ = release
    (repo.patches / "nobody").mkdir()
    (repo.patches / "nobody" / "pack.mcmeta").write_text("{}")
    assert patches.check(manifest, repo) == ["patches/nobody is not used by any mod or datapack"]


def test_check_catches_a_folder_used_twice(fabric_repo):
    m = fabric_repo.load_manifest()
    _, entry = patched_entry(m)
    other = next(e for e in m["mods"] if "patch" not in e)
    other["patch"] = dict(entry["patch"], base_sha512=other["hashes"]["sha512"])
    errors = patches.check(m, fabric_repo)
    first, second = sorted([other, entry], key=lambda e: e["slug"])  # the first in manifest order owns it
    assert errors == [f"mod {second['file']}: patch {entry['patch']['path']} is also used by mod {first['file']}"]


@pytest.mark.parametrize("break_it, message", [
    (lambda repo, entry: shutil.rmtree(patches.folder(repo, entry)), "missing or empty"),
    (lambda repo, entry: entry.update(patch=entry["patch"]["path"]), "patch must be"),  # the old string shape
    (lambda repo, entry: entry["patch"].update(path="patches/../defaults"), "must be patches/<folder>"),
    (lambda repo, entry: entry["patch"].pop("base_sha512"), "patch must be"),
])
def test_check_catches_broken_references(release, break_it, message):
    repo, manifest, _, entry = release
    break_it(repo, entry)
    errors = patches.check(manifest, repo)
    assert any(message in e for e in errors), errors
