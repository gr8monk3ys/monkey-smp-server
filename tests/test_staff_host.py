"""tools/staff_host.py: the mod manager, the version switch, the world reset and upload, and the SFTP card; and their
root-helper jobs (deploy/monkey-staff-helper.sh) and owner scripts (deploy/monkey-sftp.sh)."""
# ruff: noqa: F811 (apex and helper are pytest fixtures imported from test_staff_apex)
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import staff_apex
import staff_host
import staff_panel
from test_staff_apex import (  # noqa: F401 (apex and helper are fixtures)
    RID,
    actions,
    apex,
    as_role,
    helper,
    installed,
    jar,
)
from test_staff_panel import box  # noqa: F401

from repo import REPO

DEPLOY = REPO.root / "deploy"
UID = "20261106T090000Z-00aa11bb"


# ---------------------------------------------------------------- who may ask


def test_every_new_route_is_admin_and_registered():
    assert staff_host.ROUTES
    for key in staff_host.ROUTES:
        assert staff_panel.ROUTES[key] is staff_host.ROUTES[key]
        assert staff_panel.NEEDS[key] == "admin" == staff_host.NEEDS[key]
        assert key[1] in staff_panel.PATHS
    assert set(staff_host.RAW) <= set(staff_host.ROUTES)
    assert staff_panel.RAW[("POST", "/api/world-upload")] == 8_000_000_000
    assert "max_size 8GB" in (DEPLOY / "Caddyfile.staff").read_text()


@pytest.mark.parametrize("method,path", sorted(staff_host.ROUTES))
def test_a_moderator_is_refused_every_new_route(apex, method, path):
    body = None if method == "GET" else (b"x" if (method, path) in staff_host.RAW else {})
    code, data = apex.call(method, path, body, headers=as_role("moderator"))
    assert code == 403 and "role" in data["error"]


# ---------------------------------------------------------------- the mod manager


def jar_bytes(tmp_path, meta, name="m.jar") -> bytes:
    path = tmp_path / name
    jar(path, meta)
    return path.read_bytes()


def mod_url(name, confirm=None):
    query = staff_host.urllib.parse.urlencode({"name": name, "confirm": name if confirm is None else confirm})
    return f"/api/mod-upload?{query}"


def test_a_jar_upload_is_checked_then_installed(apex, tmp_path):
    good = jar_bytes(tmp_path, {"id": "lithium", "name": "Lithium", "version": "1.0", "environment": "*"})
    mods = apex.root / "mods"
    assert apex.call("POST", mod_url("lithium.jar", "nope"), good)[0] == 400
    assert apex.call("POST", mod_url("lithium.jar"), {"not": "a file"})[0] == 415
    for bad in ("../lithium.jar", "lithium.zip", ".hidden.jar", "a b.jar"):
        assert apex.call("POST", mod_url(bad), good)[0] == 400, bad
    assert apex.call("POST", mod_url("junk.jar"), b"not a zip")[0] == 400
    assert apex.call("POST", mod_url("nometa.jar"), jar_bytes(tmp_path, None))[0] == 400
    client = jar_bytes(tmp_path, {"id": "sodium", "name": "Sodium", "environment": "client"})
    code, body = apex.call("POST", mod_url("sodium.jar"), client)
    assert code == 400 and "client-only" in body["error"]
    assert sorted(p.name for p in mods.iterdir()) == ["a.jar"]
    code, done = apex.call("POST", mod_url("lithium.jar"), good)
    assert code == 200 and done["id"] == "lithium" and done["kept_in"] is None
    assert (mods / "lithium.jar").read_bytes() == good
    assert "diego mod-install lithium.jar (uploaded)" in actions(apex)
    # Nothing half-written is left behind, and nothing outside mods/ was touched.
    assert not list((apex.root / "mods-removed").glob(".incoming-*"))
    assert not (apex.root.parent / "lithium.jar").exists()


def test_a_jar_over_the_cap_is_refused(apex, tmp_path, monkeypatch):
    monkeypatch.setitem(staff_panel.RAW, ("POST", "/api/mod-upload"), 100)
    good = jar_bytes(tmp_path, {"id": "big", "name": "Big"})
    assert apex.call("POST", mod_url("big.jar"), good + b"\0" * 200)[0] == 413
    assert not (apex.root / "mods" / "big.jar").exists()


def test_a_new_version_of_a_mod_moves_the_old_one_aside(apex, tmp_path):
    mods = apex.root / "mods"
    jar(mods / "lithium-1.0.jar", {"id": "lithium", "name": "Lithium", "version": "1.0"})
    old = (mods / "lithium-1.0.jar").read_bytes()
    new = jar_bytes(tmp_path, {"id": "lithium", "name": "Lithium", "version": "1.1"})
    code, done = apex.call("POST", mod_url("lithium-1.1.jar"), new)
    assert code == 200 and done["replaced"] == ["lithium-1.0.jar"]
    assert not (mods / "lithium-1.0.jar").exists()
    kept = list((apex.root / "mods-removed").glob("*/lithium-1.0.jar"))
    assert len(kept) == 1 and kept[0].read_bytes() == old and done["kept_in"].startswith("mods-removed/")


def test_mods_turn_off_on_and_are_removed_without_deleting(apex):
    mods = apex.root / "mods"
    jar(mods / "lithium.jar", {"id": "lithium", "name": "Lithium"})
    (apex.root / ".monkey-state.json").write_text(json.dumps({"mods": ["lithium.jar"]}))
    rows = {r["file"]: r for r in apex.call("GET", "/api/mods")[1]["mods"]}
    assert rows["lithium.jar"]["enabled"] is True and rows["lithium.jar"]["pinned"] is True
    off = {"file": "lithium.jar", "enabled": False, "confirm": "lithium.jar"}
    assert apex.call("POST", "/api/mod-toggle", {**off, "confirm": "lithium"})[0] == 400
    assert apex.call("POST", "/api/mod-toggle", {**off, "file": "../../server.properties",
                                                 "confirm": "../../server.properties"})[0] == 400
    code, done = apex.call("POST", "/api/mod-toggle", off)
    assert code == 200 and done["file"] == "lithium.jar.disabled" and done["pinned"] is True
    assert (mods / "lithium.jar.disabled").exists() and not (mods / "lithium.jar").exists()
    rows = {r["file"]: r for r in apex.call("GET", "/api/mods")[1]["mods"]}
    assert rows["lithium.jar.disabled"]["enabled"] is False
    assert apex.call("POST", "/api/mod-toggle", {**off, "file": "lithium.jar.disabled",
                                                 "confirm": "lithium.jar.disabled"})[0] == 409
    # Turning it back on while another jar has its mod id is refused.
    jar(mods / "lithium-2.jar", {"id": "lithium", "name": "Lithium"})
    on = {"file": "lithium.jar.disabled", "enabled": True, "confirm": "lithium.jar.disabled"}
    assert apex.call("POST", "/api/mod-toggle", on)[0] == 409
    (mods / "lithium-2.jar").unlink()
    assert apex.call("POST", "/api/mod-toggle", on)[0] == 200 and (mods / "lithium.jar").exists()
    assert apex.call("POST", "/api/mod-remove", {"file": "lithium.jar", "confirm": "x"})[0] == 400
    assert apex.call("POST", "/api/mod-remove", {"file": "missing.jar", "confirm": "missing.jar"})[0] == 404
    code, done = apex.call("POST", "/api/mod-remove", {"file": "lithium.jar", "confirm": "lithium.jar"})
    assert code == 200 and not (mods / "lithium.jar").exists()
    assert len(list((apex.root / "mods-removed").glob("*/lithium.jar"))) == 1
    log = actions(apex)
    assert "mod-disable lithium.jar" in log and "mod-enable lithium.jar.disabled" in log and "mod-remove" in log


# ---------------------------------------------------------------- Modrinth


class FakeModrinth:
    def __init__(self, data: bytes, sha=None, url="https://cdn.modrinth.com/data/AANobbMI/versions/abcd1234/lithium.jar",
                 name="lithium-fabric-0.15.jar"):
        self.data, self.urls = data, []
        self.answers = {
            "/project/lithium": {"slug": "lithium", "id": "gvQqBUqZ"},
            "/project/gvQqBUqZ/version": [
                {"version_type": "beta", "files": []},
                {"version_type": "release", "version_number": "0.15", "dependencies": [
                    {"project_id": "P7dR8mSH", "dependency_type": "required"},
                    {"project_id": "x", "dependency_type": "optional"}],
                 "files": [{"primary": True, "filename": name, "url": url,
                            "hashes": {"sha512": sha or hashlib.sha512(data).hexdigest()}}]}],
            "/search": {"hits": [{"slug": "lithium", "title": "Lithium", "description": "Fast", "downloads": 9,
                                  "server_side": "optional", "client_side": "optional"},
                                 {"slug": "../evil", "title": "x"}]},
        }

    def __call__(self, url, most):
        self.urls.append(url)
        if url.startswith("https://cdn.modrinth.com/"):
            return self.data
        path = url.removeprefix(staff_host.MODRINTH).split("?")[0]
        return json.dumps(self.answers[path]).encode()


def with_modrinth(b, fake):
    (b.live / "monkey").mkdir(exist_ok=True)
    (b.live / "monkey" / "manifest.json").write_text(json.dumps({"minecraft": "26.2"}))
    staff_host.host(b.panel).fetch = fake
    return fake


def test_a_modrinth_search_asks_for_fabric_server_mods_of_this_version(apex):
    fake = with_modrinth(apex, FakeModrinth(b""))
    code, data = apex.call("GET", "/api/modrinth?q=lith")
    assert code == 200 and data["game_version"] == "26.2"
    assert [h["slug"] for h in data["hits"]] == ["lithium"]
    url = fake.urls[0]
    assert url.startswith("https://api.modrinth.com/v2/search?")
    for facet in ("categories:fabric", "versions:26.2", "server_side:required"):
        assert facet in staff_host.urllib.parse.unquote_plus(url)
    assert apex.call("GET", "/api/modrinth?q=")[0] == 400


def test_a_modrinth_install_checks_the_sha512_and_the_host(apex, tmp_path):
    data = jar_bytes(tmp_path, {"id": "lithium", "name": "Lithium", "version": "0.15"})
    mods = apex.root / "mods"
    with_modrinth(apex, FakeModrinth(data, sha="0" * 128))
    assert apex.call("POST", "/api/modrinth-install", {"project": "lithium", "confirm": "lithium"})[0] == 502
    with_modrinth(apex, FakeModrinth(data, url="https://evil.example/lithium.jar"))
    assert apex.call("POST", "/api/modrinth-install", {"project": "lithium", "confirm": "lithium"})[0] == 502
    with_modrinth(apex, FakeModrinth(data, name="../lithium.jar"))
    assert apex.call("POST", "/api/modrinth-install", {"project": "lithium", "confirm": "lithium"})[0] == 502
    assert sorted(p.name for p in mods.iterdir()) == ["a.jar"]
    fake = with_modrinth(apex, FakeModrinth(data))
    assert apex.call("POST", "/api/modrinth-install", {"project": "lithium", "confirm": "Lithium"})[0] == 400
    assert apex.call("POST", "/api/modrinth-install", {"project": "../x", "confirm": "../x"})[0] == 400
    code, done = apex.call("POST", "/api/modrinth-install", {"project": "lithium", "confirm": "lithium"})
    assert code == 200 and done["file"] == "lithium-fabric-0.15.jar" and done["requires"] == ["P7dR8mSH"]
    assert (mods / "lithium-fabric-0.15.jar").read_bytes() == data
    versions = next(u for u in fake.urls if "/version?" in u)
    assert "fabric" in versions and "26.2" in staff_host.urllib.parse.unquote(versions)
    assert "mod-install lithium-fabric-0.15.jar (Modrinth lithium 0.15)" in actions(apex)


# ---------------------------------------------------------------- the version switch


def git_repo(root: Path, tags: dict, loose=None):
    git = root / ".git"
    (git / "refs" / "tags").mkdir(parents=True, exist_ok=True)
    lines = ["# pack-refs with: peeled fully-peeled sorted"]
    for tag, sha in tags.items():
        lines.append(f"{sha} refs/tags/{tag}")
    lines.append(f"{'f' * 40} refs/tags/not-a-release")
    (git / "packed-refs").write_text("\n".join(lines) + "\n")
    for tag, sha in (loose or {}).items():
        (git / "refs" / "tags" / tag).write_text(sha + "\n")


def test_release_tags_are_read_from_the_checkout(tmp_path):
    git_repo(tmp_path, {"v1.2.0": "a" * 40, "v1.10.0": "b" * 40}, loose={"v2.0.0": "c" * 40, "evil;rm": "d" * 40})
    tags = staff_host.release_tags(tmp_path)
    assert set(tags) == {"v1.2.0", "v1.10.0", "v2.0.0"}
    assert tags["v1.2.0"] == "a" * 40 and tags["v2.0.0"] is None     # a loose ref to an object that isn't here
    assert sorted(tags, key=staff_host.tag_key) == ["v1.2.0", "v1.10.0", "v2.0.0"]


def test_a_version_switch_needs_a_listed_tag_typed_back(apex):
    repo = apex.tmp / "repo"
    git_repo(repo, {"v3.1.0": "a" * 40, "v3.1.1": "b" * 40})
    (apex.live / ".deployed").write_text("a" * 40 + "\n")
    code, data = apex.call("GET", "/api/versions")
    assert code == 200 and data["newest"] == "v3.1.1" and data["installed"] is False
    assert [t["tag"] for t in data["tags"] if t["live"]] == ["v3.1.0"]
    assert apex.call("POST", "/api/version-switch", {"tag": "v3.1.0", "confirm": "v3.1.0"})[0] == 503
    installed(apex)
    assert apex.call("POST", "/api/version-switch", {"tag": "v3.1.0", "confirm": "v3.1.1"})[0] == 400
    assert apex.call("POST", "/api/version-switch", {"tag": "v9.9.9", "confirm": "v9.9.9"})[0] == 400
    assert apex.call("POST", "/api/version-switch", {"tag": "v3.1.0; reboot", "confirm": "v3.1.0; reboot"})[0] == 400
    assert not list(apex.x.requests.iterdir())
    code, done = apex.call("POST", "/api/version-switch", {"tag": "v3.1.0", "confirm": "v3.1.0"})
    assert code == 200
    text = (apex.x.requests / f"{done['request']}.req").read_text()
    assert text == "action=deploy\nuser=diego\ntag=v3.1.0\n"
    # One world or version job at a time.
    assert apex.call("POST", "/api/version-switch", {"tag": "v3.1.1", "confirm": "v3.1.1"})[0] == 409
    assert apex.call("POST", "/api/world-reset", {"confirm": "RESET"})[0] == 409
    assert "diego version-switch v3.1.0" in actions(apex)


def test_a_running_job_from_a_dead_helper_stops_blocking_after_the_service_timeout(apex):
    installed(apex)
    now = staff_host.dt.datetime.now(staff_host.dt.timezone.utc)

    def running(stamp, rid):
        text = json.dumps({"action": "deploy", "state": "running", "time": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "message": "x"})
        (apex.x.results / f"{rid}.json").write_text(text)

    running(now - staff_host.dt.timedelta(minutes=30), "20261106T090000Z-00aa11bb")
    assert apex.call("POST", "/api/world-reset", {"confirm": "RESET"})[0] == 409
    (apex.x.results / "20261106T090000Z-00aa11bb.json").unlink()
    running(now - staff_host.dt.timedelta(hours=6), "20261106T080000Z-00aa11bb")
    assert apex.call("POST", "/api/world-reset", {"confirm": "RESET"})[0] == 200
    # The helper's timeout is what the limit follows.
    unit = (DEPLOY / "monkey-staff-helper.service").read_text()
    assert "TimeoutStartSec=4h" in unit and staff_host.dt.timedelta(hours=4) < staff_host.STALE_JOB


def test_a_replaced_jar_that_is_pinned_under_another_name_is_reported_pinned(apex, tmp_path):
    mods = apex.root / "mods"
    jar(mods / "lithium-1.0.jar", {"id": "lithium", "name": "Lithium", "version": "1.0"})
    (apex.root / ".monkey-state.json").write_text(json.dumps({"mods": ["lithium-1.0.jar"]}))
    new = jar_bytes(tmp_path, {"id": "lithium", "name": "Lithium", "version": "1.1"})
    code, done = apex.call("POST", mod_url("lithium-1.1.jar"), new)
    assert code == 200 and done["replaced"] == ["lithium-1.0.jar"] and done["pinned"] is True


# ---------------------------------------------------------------- the world reset


def test_a_reset_needs_reset_typed_and_never_logs_the_seed(apex):
    installed(apex)
    assert apex.call("POST", "/api/world-reset", {"confirm": "reset"})[0] == 400
    for bad in ("a b", "x;reboot", "$(id)", "a" * 65, 12):
        assert apex.call("POST", "/api/world-reset", {"confirm": "RESET", "seed": bad})[0] == 400, bad
    assert not list(apex.x.requests.iterdir())
    code, done = apex.call("POST", "/api/world-reset", {"confirm": "RESET", "seed": "-Secret_Seed42"})
    assert code == 200
    assert (apex.x.requests / f"{done['request']}.req").read_text() == \
        "action=reset\nuser=diego\nseed=-Secret_Seed42\n"
    log = actions(apex)
    assert "Secret_Seed42" not in log and "diego world-reset seed changed" in log
    (apex.x.requests / f"{done['request']}.req").unlink()
    code, done = apex.call("POST", "/api/world-reset", {"confirm": "RESET", "seed": ""})
    assert code == 200 and (apex.x.requests / f"{done['request']}.req").read_text() == "action=reset\nuser=diego\n"
    assert "world-reset same seed" in actions(apex)


# ---------------------------------------------------------------- world zips


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
    with pytest.raises(staff_host.Problem, match=words):
        staff_host.check_world_zip(path)


def test_a_backslash_path_and_junk_are_refused(tmp_path):
    path = tmp_path / "w.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("level.dat", "x")
        z.writestr(zipfile.ZipInfo("..\\evil"), "x")
    # (zipfile on Windows reads the \ as a /, so there it is caught as a ..)
    with pytest.raises(staff_host.Problem, match=r"absolute|\.\."):
        staff_host.check_world_zip(path)
    (tmp_path / "junk.zip").write_bytes(b"not a zip")
    with pytest.raises(staff_host.Problem, match="not a zip"):
        staff_host.check_world_zip(tmp_path / "junk.zip")


def test_a_world_zip_unpacks_only_its_world_folder(tmp_path):
    src = world_zip({"myworld/level.dat": "lvl", "myworld/region/r.0.0.mca": "mca", "myworld/session.lock": "x",
                     "__MACOSX/._level.dat": "x"}, tmp_path / "w.zip")
    assert staff_host.check_world_zip(src) == {"prefix": "myworld/", "files": 3, "size": 8}
    dest = tmp_path / "dest"
    dest.mkdir()
    world = staff_host.unzip_world(src, dest)
    found = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    assert found == ["world/level.dat", "world/region/r.0.0.mca"] and (world / "level.dat").read_text() == "lvl"
    with pytest.raises(staff_host.Problem, match="empty folder"):
        staff_host.unzip_world(src, dest)
    # The command line the helper runs.
    other = tmp_path / "other"
    other.mkdir()
    cli = [sys.executable, "-B", "-I", str(REPO.root / "tools" / "staff_host.py"), "unzip-world"]
    assert subprocess.run([*cli, str(src), str(other)], capture_output=True).returncode == 0
    assert (other / "world" / "level.dat").read_text() == "lvl"
    bad = world_zip({"level.dat": "x", "../x": "x"}, tmp_path / "bad.zip")
    third = tmp_path / "third"
    third.mkdir()
    done = subprocess.run([*cli, str(bad), str(third)], capture_output=True, text=True)
    assert done.returncode == 1 and done.stderr.startswith("staff_host: ") and not list(third.iterdir())


# ---------------------------------------------------------------- the world upload


def test_a_world_upload_is_checked_kept_and_swapped_in_only_when_typed(apex, monkeypatch):
    monkeypatch.setattr(staff_host, "SPARE", 0)
    good = world_zip({"world/level.dat": "new", "world/region/r.mca": "m"})
    assert apex.call("POST", "/api/world-upload", good)[0] == 503       # no helper, nothing kept
    installed(apex)
    assert apex.call("POST", "/api/world-upload", {"zip": "no"})[0] == 415
    code, body = apex.call("POST", "/api/world-upload", world_zip({"level.dat": "x", "../../evil": "x"}))
    assert code == 400 and ".." in body["error"]
    uploads = apex.staff / "uploads"
    assert not list(uploads.iterdir())
    assert apex.call("GET", "/api/world-upload")[1]["upload"] is None
    code, done = apex.call("POST", "/api/world-upload", good)
    assert code == 200 and done["files"] == 2 and done["folder"] == "world"
    assert [p.name for p in uploads.iterdir()] == [f"{done['upload']}.zip"]
    waiting = apex.call("GET", "/api/world-upload")[1]
    assert waiting["upload"] == done["upload"] and waiting["files"] == 2
    assert apex.call("POST", "/api/world-upload-apply", {"upload": done["upload"], "confirm": "replace"})[0] == 400
    assert apex.call("POST", "/api/world-upload-apply", {"upload": "../../x", "confirm": "REPLACE"})[0] == 400
    assert apex.call("POST", "/api/world-upload-apply", {"upload": UID, "confirm": "REPLACE"})[0] == 400
    assert not list(apex.x.requests.iterdir())
    code, asked = apex.call("POST", "/api/world-upload-apply", {"upload": done["upload"], "confirm": "REPLACE"})
    assert code == 200
    assert (apex.x.requests / f"{asked['request']}.req").read_text() == \
        f"action=world-upload\nuser=diego\nupload={done['upload']}\n"
    assert (apex.root / "world" / "level.dat").read_text() == "nbt"     # the page itself changes no world
    log = actions(apex)
    assert "diego world-upload" in log and "diego world-replace" in log


def test_a_world_upload_needs_room_on_the_disk(apex, monkeypatch):
    installed(apex)
    monkeypatch.setattr(staff_host, "SPARE", 10 ** 18)
    code, body = apex.call("POST", "/api/world-upload", world_zip({"level.dat": "x"}))
    assert code == 507 and "disk" in body["error"]


# ---------------------------------------------------------------- SFTP


@pytest.mark.parametrize("text,shown", [
    (None, False), ("not json", False), ('{"host": "h", "port": 22, "users": []}', False),
    ('{"host": "bad host;", "port": 22, "users": ["diego"]}', False),
    ('{"host": "h", "port": "22", "users": ["diego"]}', False),
    ('{"host": "sftp.example.org", "port": 2222, "users": ["diego", "Bad;"]}', True),
])
def test_the_sftp_card_reads_only_a_good_file(apex, text, shown):
    if text is not None:
        apex.staff.mkdir(parents=True, exist_ok=True)
        (apex.staff / "sftp.json").write_text(text)
    code, data = apex.call("GET", "/api/sftp")
    assert code == 200 and data["set_up"] is shown
    if shown:
        data.pop("ok", None)
        assert data == {"set_up": True, "host": "sftp.example.org", "port": 2222, "users": ["diego"], "you": "diego"}


def test_the_sftp_script_is_root_only_key_only_and_checked_before_a_reload():
    raw = (DEPLOY / "monkey-sftp.sh").read_bytes()
    assert b"\r\n" not in raw and raw.isascii()
    text = raw.decode()
    assert text.startswith("#!/bin/sh\n") and "set -eu" in text and "eval" not in text
    for line in ("Match Group $GROUP", "ChrootDirectory $CHROOTS/%u", "ForceCommand internal-sftp",
                 "PasswordAuthentication no", "KbdInteractiveAuthentication no", "AllowTcpForwarding no",
                 "X11Forwarding no", "AllowAgentForwarding no", "PermitTunnel no", "PermitTTY no", "Match all"):
        assert line in text, line
    assert '"$SSHD" -t' in text and text.index("sshd_right") < text.index("reload_sshd\n")
    assert "rm -rf" not in text and "rm -r " not in text
    assert "PRIVATE KEY" in text and "ssh-keygen -l -f" in text
    staff = (DEPLOY / "monkey-staff.sh").read_text()
    assert '--add-sftp-user | --remove-sftp-user) exec sh "$(dirname -- "$0")/monkey-sftp.sh" "$@"' in staff
    shell = shutil.which("dash")
    if shell:
        for name in ("monkey-sftp.sh", "monkey-staff.sh", "monkey-deploy.sh", "monkey-staff-helper.sh"):
            subprocess.run([shell, "-n", str(DEPLOY / name)], check=True)


@pytest.mark.parametrize("args", [[], ["--add-sftp-user", "diego"], ["--add-sftp-user", "Diego", "k.pub"],
                                  ["--add-sftp-user", "a;b", "k.pub"], ["--remove-sftp-user", "diego", "extra"],
                                  ["--add-sftp-user", "x" * 32, "k.pub"], ["--remove-sftp-user", "-r"]])
def test_the_sftp_script_refuses_bad_arguments_before_anything(args, tmp_path):
    shell = shutil.which("dash")
    if not shell:
        pytest.skip("needs dash")
    done = subprocess.run([shell, (DEPLOY / "monkey-sftp.sh").as_posix(), *args], capture_output=True, text=True,
                          env={**os.environ, "MONKEY_DEPLOY_ENV": (tmp_path / "none").as_posix()})
    assert done.returncode == 2 and "usage" in done.stderr


# ---------------------------------------------------------------- the deploy script's --tag


def test_the_deploy_script_takes_a_tag_only_when_it_tracks_tags():
    text = (DEPLOY / "monkey-deploy.sh").read_text()
    assert "--tag=*)" in text and ".deploy-pin" in text and "/.deploy-pin" in text


# ---------------------------------------------------------------- the helper's new jobs


def helper_extras(tmp_path, git_ok=True, deploy_ok=True):
    bin_dir, repo = tmp_path / "bin", tmp_path / "repo"
    (bin_dir / "git").write_text(f'#!/bin/sh\necho "git $*" >>"$FAKE_CALLS"\nexit {0 if git_ok else 1}\n',
                                 newline="\n")
    (bin_dir / "git").chmod(0o755)
    (repo / "deploy" / "monkey-deploy.sh").write_text(
        f'#!/bin/sh\necho "deploy.sh $*" >>"$FAKE_CALLS"\nexit {0 if deploy_ok else 1}\n', newline="\n")
    shutil.copy(REPO.root / "tools" / "staff_host.py", repo / "tools" / "staff_host.py")


def test_the_helper_deploys_a_checked_tag(helper, tmp_path):
    helper_extras(tmp_path)
    helper.request(RID, "action=deploy\nuser=diego\ntag=v3.1.0\n")
    done = helper.run()
    assert done.code == 0, done.out
    assert done.results[RID]["state"] == "done" and "v3.1.0" in done.results[RID]["message"]
    assert any(c.startswith("git -C") and "refs/tags/v3.1.0^{commit}" in c for c in done.calls)
    assert any(c == "deploy.sh --tag=v3.1.0" for c in done.calls)


@pytest.mark.parametrize("text", ["action=deploy\ntag=v3.1\n", "action=deploy\ntag=v3.1.0;reboot\n",
                                  "action=deploy\ntag=$(reboot)\n", "action=deploy\n"])
def test_the_helper_refuses_a_bad_tag(helper, tmp_path, text):
    helper_extras(tmp_path)
    helper.request(RID, text)
    done = helper.run()
    assert done.results[RID]["state"] == "refused"
    assert not [c for c in done.calls if c.startswith(("git", "deploy.sh"))]


def test_the_helper_refuses_a_tag_the_checkout_lacks(helper, tmp_path):
    helper_extras(tmp_path, git_ok=False)
    helper.request(RID, "action=deploy\ntag=v9.9.9\n")
    done = helper.run()
    assert done.results[RID]["state"] == "refused" and not [c for c in done.calls if c.startswith("deploy.sh")]


def test_the_helper_resets_the_world_keeping_it_and_never_shows_the_seed(helper, tmp_path):
    helper_extras(tmp_path)
    server = helper.live / "server"
    (server / "world_nether").mkdir()
    (server / "server.properties").write_text("level-name=world\nlevel-seed=old\nrcon.password=hidden\n",
                                              newline="\n")
    helper.request(RID, "action=reset\nuser=diego\nseed=-Secret_Seed42\n")
    done = helper.run()
    assert done.code == 0, done.out
    result = done.results[RID]
    assert result["state"] == "done", result
    props = (server / "server.properties").read_text()
    assert "level-seed=-Secret_Seed42\n" in props and "level-seed=old" not in props and "rcon.password=hidden" in props
    assert not (server / "world").exists() and not (server / "world_nether").exists()
    kept = list((helper.live / "backups").glob("before-reset-*"))
    assert len(kept) == 1 and (kept[0] / "world" / "level.dat").read_text() == "live"
    assert "level-seed=old" in (kept[0] / "server.properties").read_text()
    assert "Secret_Seed42" not in json.dumps(done.results) and "Secret_Seed42" not in done.out
    assert "seed changed" in result["message"]
    stop = next(i for i, c in enumerate(done.calls) if c.endswith("stop monkey"))
    start = next(i for i, c in enumerate(done.calls) if c.endswith("up -d --no-build monkey"))
    assert stop < start


@pytest.mark.parametrize("seed", ["a;reboot", "$(reboot)", "a b", "x" * 70])
def test_the_helper_refuses_a_bad_seed_instead_of_keeping_the_old_one(helper, tmp_path, seed):
    helper_extras(tmp_path)
    helper.request(RID, f"action=reset\nseed={seed}\n")
    done = helper.run()
    assert done.results[RID]["state"] == "refused"
    assert (helper.live / "server" / "world" / "level.dat").read_text() == "live"
    assert not [c for c in done.calls if c.endswith("stop monkey")]


def test_the_helper_swaps_in_an_uploaded_world(helper, tmp_path):
    helper_extras(tmp_path)
    uploads = tmp_path / "staff" / "uploads"
    uploads.mkdir()
    world_zip({"myworld/level.dat": "uploaded", "myworld/region/r.mca": "m"}, uploads / f"{UID}.zip")
    helper.request(RID, f"action=world-upload\nuser=diego\nupload={UID}\n")
    done = helper.run()
    assert done.code == 0, done.out
    assert done.results[RID]["state"] == "done", done.results[RID]
    world = helper.live / "server" / "world"
    assert (world / "level.dat").read_text() == "uploaded" and (world / "region" / "r.mca").read_text() == "m"
    kept = list((helper.live / "backups").glob("before-upload-*/world/level.dat"))
    assert len(kept) == 1 and kept[0].read_text() == "live"
    assert not (uploads / f"{UID}.zip").exists() and not list(helper.live.glob(".upload.*"))


def test_the_helper_leaves_the_world_alone_when_an_upload_is_bad(helper, tmp_path):
    helper_extras(tmp_path)
    uploads = tmp_path / "staff" / "uploads"
    uploads.mkdir()
    world_zip({"level.dat": "x", "../../evil": "x"}, uploads / f"{UID}.zip")
    helper.request(RID, f"action=world-upload\nupload={UID}\n")
    done = helper.run()
    result = done.results[RID]
    assert result["state"] == "failed" and ".." in result["message"]
    assert (helper.live / "server" / "world" / "level.dat").read_text() == "live"
    assert not [c for c in done.calls if c.endswith("stop monkey")]
    assert not (tmp_path / "evil").exists() and not (tmp_path / "staff" / "evil").exists()


@pytest.mark.parametrize("value", ["../../etc/passwd", "20261106T090000Z-00AA11BB", "x", ""])
def test_the_helper_refuses_an_upload_id_it_did_not_make(helper, tmp_path, value):
    helper_extras(tmp_path)
    helper.request(RID, f"action=world-upload\nupload={value}\n")
    done = helper.run()
    assert done.results[RID]["state"] == "refused"
    assert not [c for c in done.calls if c.startswith(("docker", "python"))]


def test_the_request_fields_are_the_helpers():
    text = (DEPLOY / "monkey-staff-helper.sh").read_text()
    for key in staff_apex.REQUEST_FIELDS:
        assert re.search(rf"sed -n 's/\^{key}=", text), key
