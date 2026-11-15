"""tools/helper_queue.py: the backup helper's queue (requests, results, the snapshot list) and the world zips, as the
staff page and the root helper (deploy/monkey-staff-helper.sh) use them. No panel here: the page's side is in
test_staff_apex.py and test_staff_host.py, the helper's in their `helper` tests."""
import ast
import contextlib
import io
import json
import re
import subprocess
import sys
import zipfile

import helper_queue as hq
import pytest

from repo import REPO

DEPLOY = REPO.root / "deploy"
TOOL = REPO.root / "tools" / "helper_queue.py"
SNAPS = [{"id": "a" * 64, "time": "2026-11-05T10:00:00Z", "tags": ["world"], "summary": {"total_bytes_processed": 9}},
         {"id": "b" * 64, "time": "2026-11-06T10:00:00Z", "tags": ["world", "bad tag;rm"]},
         {"id": "not-hex", "time": "2026-11-06T11:00:00Z"}]


def world_zip(entries, path=None, links=()):
    raw = io.BytesIO() if path is None else path
    with zipfile.ZipFile(raw, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
        for name in links:
            info = zipfile.ZipInfo(name)
            info.external_attr = (0o120777 << 16)
            z.writestr(info, "/etc/passwd")
    return raw.getvalue() if path is None else path


# ---------------------------------------------------------------- what root runs


def test_root_runs_only_this_file_so_it_imports_only_the_standard_library():
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert names and names <= set(sys.stdlib_module_names), names - set(sys.stdlib_module_names)
    # The copy root runs, the helper's calls and install-helper's check name this file, and no other tool.
    roots = re.search(r"^ROOT_FILES='([^']*)'", (DEPLOY / "lib.sh").read_text(), re.M).group(1).split()
    assert "tools/helper_queue.py" in roots and "tools/staff_apex.py" not in roots
    helper = (DEPLOY / "monkey-staff-helper.sh").read_text()
    assert re.findall(r'python3 -B -I "\$(\w+)/(\w+\.py)"', helper) == [("ROOT_TOOLS", "helper_queue.py")] * 2
    assert "tools/helper_queue.py; do" in (DEPLOY / "monkey-staff.sh").read_text()


def test_the_helper_checks_every_action_and_field_again_itself():
    text = (DEPLOY / "monkey-staff-helper.sh").read_text()
    assert re.findall(r"^        ([a-z-]+)\) do_", text, re.M) == list(hq.HELPER_ACTIONS)
    for key in (*hq.REQUEST_FIELDS, "action", "snapshot", "user"):
        assert re.search(rf"sed -n 's/\^{key}=", text), key


# ---------------------------------------------------------------- requests


def test_a_request_holds_only_fixed_words_and_checked_values(tmp_path):
    rid = hq.write_request(tmp_path, "reset", "diego", seed="-Secret_Seed42")
    assert hq.REQUEST_ID.fullmatch(rid)
    assert [p.name for p in tmp_path.iterdir()] == [f"{rid}.req"]
    assert (tmp_path / f"{rid}.req").read_text() == "action=reset\nuser=diego\nseed=-Secret_Seed42\n"
    rid2 = hq.write_request(tmp_path, "restore", "bad user;", "a" * 64)
    assert (tmp_path / f"{rid2}.req").read_text() == f"action=restore\nuser=unknown\nsnapshot={'a' * 64}\n"
    assert hq.pending(tmp_path) == sorted([rid, rid2])
    assert sorted(hq.pending_actions(tmp_path)) == ["reset", "restore"]


@pytest.mark.parametrize("action,snapshot,fields", [
    ("stop", "", {}), ("restore", "abc;reboot", {}), ("deploy", "", {"tag": "v3.1"}),
    ("reset", "", {"seed": "a b"}), ("reset", "", {"motd": "x"}), ("world-upload", "", {"upload": "../../x"}),
])
def test_a_request_outside_the_rules_is_never_written(tmp_path, action, snapshot, fields):
    with pytest.raises(ValueError):
        hq.write_request(tmp_path, action, "diego", snapshot, **fields)
    assert not list(tmp_path.iterdir())


def test_waiting_requests_that_cant_be_read_name_no_action(tmp_path):
    assert hq.pending(tmp_path / "missing") == [] and hq.pending_actions(tmp_path / "missing") == []
    (tmp_path / "20261106T100000Z-0000aaaa.req").write_text("user=diego\naction=deploy\ntag=v1.0.0\n")
    (tmp_path / "20261106T110000Z-0000bbbb.req").write_text("action=rm -rf\n")
    (tmp_path / "20261106T120000Z-0000cccc.req").mkdir()
    assert hq.pending_actions(tmp_path) == ["deploy"]


# ---------------------------------------------------------------- results


def test_the_results_are_read_newest_first_and_bad_ones_skipped(tmp_path):
    def write(name, data):
        (tmp_path / name).write_text(data if isinstance(data, str) else json.dumps(data))

    write("20261106T100000Z-0000aaaa.json", {"action": "list-snapshots", "state": "done"})
    write("20261106T110000Z-0000bbbb.json", {"action": "rm -rf", "state": "done"})
    write("20261106T120000Z-0000cccc.json", "not json")
    write("nonsense.json", {"action": "backup-now"})
    write("20261106T130000Z-0000dddd.json", {"action": "backup-now", "state": "running"})
    with contextlib.suppress(OSError):                      # (no links without rights on Windows)
        (tmp_path / "20261106T140000Z-0000eeee.json").symlink_to(tmp_path / "20261106T130000Z-0000dddd.json")
    assert [rid for rid, _ in hq.results(tmp_path)] == ["20261106T130000Z-0000dddd", "20261106T100000Z-0000aaaa"]
    assert list(hq.results(tmp_path / "missing")) == []
    big = tmp_path / "20261106T150000Z-0000ffff.json"
    big.write_text(json.dumps({"action": "backup-now", "pad": "x" * hq.RESULT_MAX}))
    assert hq.read_result(big) is None


def test_the_snapshot_list_is_cut_down_newest_first():
    rows = hq.reduce_snapshots(SNAPS)
    assert [r["short_id"] for r in rows] == ["b" * 8, "a" * 8]
    assert rows[0]["tags"] == ["world"] and rows[0]["size"] is None and rows[1]["size"] == 9
    assert hq.reduce_snapshots(rows) == rows                # a list cut down already stays as it is
    assert hq.reduce_snapshots({"not": "a list"}) == []


def test_the_snapshot_cli_reads_restics_json():
    done = subprocess.run([sys.executable, "-B", "-I", str(TOOL), "snapshots"],
                          input=json.dumps(SNAPS), capture_output=True, text=True, check=True)
    assert [r["short_id"] for r in json.loads(done.stdout)] == ["b" * 8, "a" * 8]
    bad = subprocess.run([sys.executable, "-B", "-I", str(TOOL), "snapshots"], input="", capture_output=True, text=True)
    assert bad.returncode == 1 and bad.stderr.startswith("helper_queue: ")


# ---------------------------------------------------------------- world zips


@pytest.mark.parametrize("entries,links,words", [
    ({"world/level.dat": "x", "../evil.sh": "x"}, (), ".."),
    ({"world/level.dat": "x", "world/../../evil": "x"}, (), ".."),
    ({"/etc/cron.d/x": "x", "level.dat": "x"}, (), "absolute"),
    ({"C:/x": "x", "level.dat": "x"}, (), "absolute"),
    ({"level.dat": "x"}, ("region",), "link"),
    ({"a/level.dat": "x", "b/level.dat": "x"}, (), "more than one"),
    ({"a/b/level.dat": "x"}, (), "exactly one"),
    ({"readme.txt": "x"}, (), "exactly one"),
])
def test_a_bad_world_zip_is_refused(tmp_path, entries, links, words):
    path = world_zip(entries, tmp_path / "w.zip", links)
    with pytest.raises(hq.Problem, match=words):
        hq.check_world_zip(path)


def test_a_backslash_path_and_junk_are_refused(tmp_path):
    path = tmp_path / "w.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("level.dat", "x")
        z.writestr(zipfile.ZipInfo("..\\evil"), "x")
    # (zipfile on Windows reads the \ as a /, so there it is caught as a ..)
    with pytest.raises(hq.Problem, match=r"absolute|\.\."):
        hq.check_world_zip(path)
    (tmp_path / "junk.zip").write_bytes(b"not a zip")
    with pytest.raises(hq.Problem, match="not a zip"):
        hq.check_world_zip(tmp_path / "junk.zip")


def test_a_world_zip_unpacks_only_its_world_folder(tmp_path):
    src = world_zip({"myworld/level.dat": "lvl", "myworld/region/r.0.0.mca": "mca", "myworld/session.lock": "x",
                     "__MACOSX/._level.dat": "x"}, tmp_path / "w.zip")
    assert hq.check_world_zip(src) == {"prefix": "myworld/", "files": 3, "size": 8}
    dest = tmp_path / "dest"
    dest.mkdir()
    world = hq.unzip_world(src, dest)
    found = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    assert found == ["world/level.dat", "world/region/r.0.0.mca"] and (world / "level.dat").read_text() == "lvl"
    with pytest.raises(hq.Problem, match="empty folder"):
        hq.unzip_world(src, dest)
    # The command line the helper runs.
    other = tmp_path / "other"
    other.mkdir()
    cli = [sys.executable, "-B", "-I", str(TOOL), "unzip-world"]
    assert subprocess.run([*cli, str(src), str(other)], capture_output=True).returncode == 0
    assert (other / "world" / "level.dat").read_text() == "lvl"
    bad = world_zip({"level.dat": "x", "../x": "x"}, tmp_path / "bad.zip")
    third = tmp_path / "third"
    third.mkdir()
    done = subprocess.run([*cli, str(bad), str(third)], capture_output=True, text=True)
    assert done.returncode == 1 and done.stderr.startswith("helper_queue: ") and not list(third.iterdir())


def test_a_world_zip_needs_room_to_unpack(tmp_path, monkeypatch):
    monkeypatch.setattr(hq, "SPARE", 10 ** 18)
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(hq.Problem, match="disk space"):
        hq.unzip_world(world_zip({"level.dat": "x"}, tmp_path / "w.zip"), dest)
    assert not list(dest.iterdir())
