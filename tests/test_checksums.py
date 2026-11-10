import hashlib

import pytest

import checksums
from repo import REPO

A, B = b"the pack", b"the installer"


def folder(tmp_path, **files):
    for name, data in (files or {"a.mrpack": A, "b.zip": B}).items():
        (tmp_path / name).write_bytes(data)
    return tmp_path


def test_the_list_is_what_sha256sum_writes(tmp_path):
    out = checksums.write(folder(tmp_path, **{"b.zip": B, "a.mrpack": A}))
    assert out == tmp_path / "SHA256SUMS.txt"
    assert out.read_bytes() == (f"{hashlib.sha256(A).hexdigest()}  a.mrpack\n"
                                f"{hashlib.sha256(B).hexdigest()}  b.zip\n").encode()
    assert checksums.problems(tmp_path) == []
    assert checksums.load(tmp_path) == {"a.mrpack": hashlib.sha256(A).hexdigest(),
                                        "b.zip": hashlib.sha256(B).hexdigest()}


def test_writing_again_leaves_the_list_itself_out(tmp_path):
    checksums.write(folder(tmp_path))
    first = (tmp_path / "SHA256SUMS.txt").read_bytes()
    checksums.write(tmp_path)
    assert (tmp_path / "SHA256SUMS.txt").read_bytes() == first


def test_a_list_can_cover_only_some_files(tmp_path):
    folder(tmp_path)
    checksums.write(tmp_path, [tmp_path / "b.zip"])
    assert list(checksums.load(tmp_path)) == ["b.zip"]
    assert checksums.problems(tmp_path, "dist") == ["dist/SHA256SUMS.txt: doesn't list a.mrpack"]


def test_a_missing_list_is_a_problem(tmp_path):
    assert checksums.problems(folder(tmp_path), "dist") == ["dist/SHA256SUMS.txt: missing"]


def test_a_file_changed_after_the_list_was_written_is_a_problem(tmp_path):
    checksums.write(folder(tmp_path))
    (tmp_path / "a.mrpack").write_bytes(b"another pack")
    [error] = checksums.problems(tmp_path, "dist")
    assert error.startswith("dist/SHA256SUMS.txt: a.mrpack is listed as " + hashlib.sha256(A).hexdigest()[:12])


def test_a_file_that_is_gone_or_new_is_a_problem(tmp_path):
    checksums.write(folder(tmp_path))
    (tmp_path / "a.mrpack").unlink()
    (tmp_path / "c.zip").write_bytes(b"new")
    assert checksums.problems(tmp_path, "dist") == [
        "dist/SHA256SUMS.txt: lists a.mrpack, which isn't in dist/", "dist/SHA256SUMS.txt: doesn't list c.zip"]


@pytest.mark.parametrize("listing", [
    "abc  a.mrpack\n",                                  # not a SHA-256
    f"{'0' * 64} a.mrpack\n",                           # one space
    f"{'0' * 64}  sub/a.mrpack\n",                      # a path, not a name
    f"{'A' * 64}  a.mrpack\n",                          # capitals: sha256sum writes small letters
    f"{'0' * 64}  a.mrpack\r\n",                        # CRLF
    f"{'0' * 64}  a.mrpack\n{'1' * 64}  a.mrpack\n",    # the same file twice
    f"{'0' * 64}  a.mrpack\n\n",                        # an empty line
])
def test_a_list_that_is_not_one_is_refused(tmp_path, listing):
    with pytest.raises(ValueError):
        checksums.parse(listing)
    (tmp_path / "SHA256SUMS.txt").write_bytes(listing.encode())
    [error] = checksums.problems(tmp_path, "dist")
    assert error.startswith("dist/SHA256SUMS.txt: ")


def test_an_empty_folder_has_an_empty_list(tmp_path):
    checksums.write(tmp_path)
    assert (tmp_path / "SHA256SUMS.txt").read_bytes() == b""
    assert checksums.problems(tmp_path) == []


def test_two_lists_differ_only_where_both_name_a_file(tmp_path):
    site, dist = tmp_path / "site", tmp_path / "dist"
    site.mkdir()
    dist.mkdir()
    folder(site)
    folder(dist, **{"a.mrpack": A, "b.zip": B, "server.zip": b"the server"})
    checksums.write(site)
    checksums.write(dist)
    assert checksums.differences(site, dist) == []
    (dist / "b.zip").write_bytes(b"rebuilt")
    checksums.write(dist)
    [difference] = checksums.differences(site, dist)
    assert difference.startswith("b.zip: ")
    (site / "SHA256SUMS.txt").unlink()
    [error] = checksums.differences(site, dist)
    assert "can't compare" in error and "missing" in error


def test_main_writes_checks_and_compares(tmp_path, capsys):
    folder(tmp_path)
    assert checksums.main(["--check", str(tmp_path)]) == 1
    assert checksums.main([str(tmp_path)]) == 0
    assert checksums.main(["--check", str(tmp_path)]) == 0
    assert checksums.main(["--same", str(tmp_path), str(tmp_path)]) == 0
    assert checksums.main([str(tmp_path / "nowhere")]) == 1
    assert "2 files" in capsys.readouterr().out


def test_the_release_checks_the_list_before_it_publishes():
    """release.yml attaches everything in dist/, and only after `checksums.py --check dist` passed there."""
    publish = (REPO.root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    publish = publish[publish.index("\n  publish:"):publish.index("\n  modrinth:")]
    build, check, create = (publish.index(step) for step in (
        "python tools/build.py --notes notes.md", "python tools/checksums.py --check dist", "gh release create"))
    assert build < check < create
    assert ' dist/* ' in publish[create:]
