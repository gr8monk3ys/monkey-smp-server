"""tools/staff_more.py: Java and memory, data packs, the server icon and a Modrinth modpack."""
# ruff: noqa: F811 (apex is a pytest fixture imported from test_staff_apex)
import hashlib
import io
import json
import struct
import urllib.parse
import zipfile
import zlib

import pytest
import staff_host
import staff_more
import staff_panel
from test_staff_apex import actions, apex, as_role, jar  # noqa: F401 (apex is a fixture)
from test_staff_panel import box  # noqa: F401

from repo import REPO


def url(path, name, confirm=None):
    return f"{path}?{urllib.parse.urlencode({'name': name, 'confirm': name if confirm is None else confirm})}"


def zipped(files: dict) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return out.getvalue()


def png(width, height) -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x00" * 4 * width for _ in range(height))
    return staff_more.PNG + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


# ---------------------------------------------------------------- who may ask


def test_every_new_route_is_admin_and_registered():
    for key in staff_more.ROUTES:
        assert staff_panel.ROUTES[key] is staff_more.ROUTES[key]
        assert staff_panel.NEEDS[key] == "admin"
        assert key[1] in staff_panel.PATHS
    assert set(staff_more.RAW) <= set(staff_more.ROUTES)
    for key, most in staff_more.RAW.items():
        assert staff_panel.RAW[key] == most <= 64 * staff_more.MB   # Caddyfile.staff's /api/* limit


@pytest.mark.parametrize("method,path", sorted(staff_more.ROUTES))
def test_a_moderator_is_refused_every_new_route(apex, method, path):
    body = None if method == "GET" else (b"x" if (method, path) in staff_more.RAW else {})
    code, data = apex.call(method, path, body, headers=as_role("moderator"))
    assert code == 403 and "role" in data["error"]


# ---------------------------------------------------------------- Java and memory


def test_the_java_settings_are_written_for_the_start_script(apex):
    staff_more.more(apex.panel).memory = lambda: 16.0
    code, data = apex.call("GET", "/api/java")
    assert code == 200 and data["memory_gb"] is None and data["flags"] == []
    assert data["default_gb"] == 5 and data["most_gb"] == 14
    code, data = apex.call("PUT", "/api/java", {"memory_gb": 8, "flags": [" -XX:MaxGCPauseMillis=100 ", ""]})
    assert code == 200 and data["memory_gb"] == 8 and data["flags"] == ["-XX:MaxGCPauseMillis=100"]
    saved = json.loads((apex.root / "monkey-launch.json").read_text())
    assert saved == {"memory_gb": 8, "flags": ["-XX:MaxGCPauseMillis=100"]}
    assert "java-settings" in actions(apex)
    # A second save keeps the old file; an empty one removes the file (memory is picked again).
    code, data = apex.call("PUT", "/api/java", {"memory_gb": None, "flags": []})
    assert code == 200 and not (apex.root / "monkey-launch.json").exists()
    assert list((apex.root / "staff-removed").glob("*/java/monkey-launch.json"))


@pytest.mark.parametrize("body", [
    {"memory_gb": 0, "flags": []}, {"memory_gb": 16, "flags": []}, {"memory_gb": "8", "flags": []},
    {"memory_gb": True, "flags": []}, {"memory_gb": 4.5, "flags": []}, {"memory_gb": None, "flags": "x"},
    {"memory_gb": None, "flags": ["-Xmx8G"]}, {"memory_gb": None, "flags": ["-javaagent:/tmp/a.jar"]},
    {"memory_gb": None, "flags": ["-XX:OnOutOfMemoryError=/tmp/x.sh"]}, {"memory_gb": None, "flags": ["-XX:OnError=x"]},
    {"memory_gb": None, "flags": ["-XX:Flags=/tmp/f"]}, {"memory_gb": None, "flags": ["-Dx=a b"]},
    {"memory_gb": 15, "flags": []}, {"memory_gb": None, "flags": ["-XX:LogFile=x"]},
    {"memory_gb": None, "flags": ["-XX:HeapDumpPath=x"]}, {"memory_gb": None, "flags": ["-Dx=/tmp/a"]},
    {"memory_gb": None, "flags": ["-Dfabric.addMods=x"]}, {"memory_gb": None, "flags": ["-Djava.library.path=x"]},
    {"memory_gb": None, "flags": ["-Dlog4j2.configurationFile=x"]},
    {"memory_gb": None, "flags": ["-Dcom.sun.management.jmxremote.authenticate=false"]},
    {"memory_gb": None, "flags": ["-XX:+UnlockDiagnosticVMOptions"]}, {"memory_gb": None, "flags": ["-XX:+useg1gc"]},
    {"memory_gb": None, "flags": ["-XX:+UseG1GC"] * 21},
])
def test_bad_java_settings_are_refused(apex, body):
    staff_more.more(apex.panel).memory = lambda: 16.0
    assert apex.call("PUT", "/api/java", body)[0] == 400
    assert not (apex.root / "monkey-launch.json").exists()


def test_the_flag_rules_match_the_start_scripts():
    psm = (REPO.root / "package" / "monkey" / "Monkey.psm1").read_text(encoding="utf-8")
    assert f"$script:LaunchFlag = '^{staff_more.FLAG.pattern}$'" in psm
    assert f"$script:LaunchXXAllowed = '^({staff_more.XX_ALLOWED.pattern})$'" in psm
    assert f"$script:LaunchPropAllowed = '^({staff_more.PROP_ALLOWED.pattern})$'" in psm
    assert f"$script:LaunchFlagsMax = {staff_more.FLAGS_MAX}" in psm


@pytest.mark.parametrize("flag", ["-XX:+UseG1GC", "-XX:G1HeapRegionSize=8M", "-XX:MaxGCPauseMillis=130",
                                  "-XX:-UseNUMA", "-Dfile.encoding=UTF-8", "-Dusing.aikars.flags=https:"])
def test_the_usual_tuning_flags_are_taken(apex, flag):
    staff_more.more(apex.panel).memory = lambda: 16.0
    assert apex.call("PUT", "/api/java", {"memory_gb": None, "flags": [flag]})[0] == 200


def test_the_default_memory_matches_get_memorygb():
    # The table in tests/Monkey.Tests.ps1, Describe 'Get-MemoryGB'.
    for total, want in ((4, 3), (8.5, 3), (12, 4), (16.5, 5), (24, 6), (32, 8), (3.5, 2), (2, 1), (0, 3)):
        assert staff_more.default_memory(total) == want, total


# ---------------------------------------------------------------- data packs


def world(b):
    folder = b.root / "world" / "datapacks"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


PACK = zipped({"pack.mcmeta": json.dumps({"pack": {"pack_format": 80, "description": {"text": "§aMore loot"}}}),
               "data/x/function/a.mcfunction": "say hi"})


def test_a_data_pack_upload_is_checked_then_added(apex):
    packs = world(apex)
    assert apex.call("POST", url("/api/datapack-upload", "loot.zip", "nope"), PACK)[0] == 400
    for bad in ("../loot.zip", "loot.jar", "a b.zip"):
        assert apex.call("POST", url("/api/datapack-upload", bad), PACK)[0] == 400, bad
    assert apex.call("POST", url("/api/datapack-upload", "junk.zip"), b"not a zip")[0] == 400
    nested = zipped({"loot/pack.mcmeta": "{}", "loot/data/x.json": "{}"})
    code, data = apex.call("POST", url("/api/datapack-upload", "nested.zip"), nested)
    assert code == 400 and "top of the zip" in data["error"]
    sneaky = zipped({"pack.mcmeta": "{}", "../evil.json": "{}"})
    assert apex.call("POST", url("/api/datapack-upload", "sneaky.zip"), sneaky)[0] == 400
    code, data = apex.call("POST", url("/api/datapack-upload", "loot.zip"), PACK)
    assert code == 200 and (packs / "loot.zip").read_bytes() == PACK and data["kept_in"] is None
    code, data = apex.call("POST", url("/api/datapack-upload", "loot.zip"), PACK)
    assert code == 200 and data["kept_in"].startswith("staff-removed/")
    assert not list(packs.glob(".incoming-*")) and not list((apex.root / "staff-removed").glob(".incoming-*"))
    assert "datapack-add loot.zip" in actions(apex)


def test_the_data_pack_list_reads_each_pack_and_the_release_ones(apex):
    packs = world(apex)
    (packs / "loot.zip").write_bytes(PACK)
    (packs / "monkey-rules").mkdir()
    (packs / "monkey-rules" / "pack.mcmeta").write_text(json.dumps({"pack": {"description": "Rules"}}))
    (packs / "stray.txt").write_text("x")
    (apex.live / "monkey" / "datapacks" / "monkey-rules").mkdir(parents=True)
    apex.docker.answers["datapack list enabled"] = ("There are 2 data pack(s) enabled: [vanilla (built-in)], "
                                                    "[file/monkey-rules (world)]")
    code, data = apex.call("GET", "/api/datapacks")
    assert code == 200 and data["running"]
    rows = {r["name"]: r for r in data["packs"]}
    assert set(rows) == {"loot.zip", "monkey-rules"}
    assert rows["loot.zip"]["description"] == "More loot" and rows["loot.zip"]["enabled"] is False
    assert rows["monkey-rules"]["release"] and rows["monkey-rules"]["enabled"] is True
    # The release's own packs come back at every start, so they stay.
    code, data = apex.call("POST", "/api/datapack-remove", {"name": "monkey-rules", "confirm": "monkey-rules"})
    assert code == 409 and (packs / "monkey-rules").is_dir()
    assert apex.call("POST", "/api/datapack-remove", {"name": "loot.zip", "confirm": "x"})[0] == 400
    code, data = apex.call("POST", "/api/datapack-remove", {"name": "loot.zip", "confirm": "loot.zip"})
    assert code == 200 and not (packs / "loot.zip").exists()
    assert list((apex.root / "staff-removed").glob("*/datapacks/loot.zip"))
    assert apex.call("POST", "/api/datapack-remove", {"name": "../x", "confirm": "../x"})[0] == 400


def test_a_data_pack_is_turned_on_and_off_by_the_server(apex):
    packs = world(apex)
    (packs / "loot.zip").write_bytes(PACK)
    apex.docker.answers['datapack enable "file/loot.zip"'] = "Enabling pack [file/loot.zip (world)]"
    apex.docker.answers["reload"] = "Reloading!"
    code, data = apex.call("POST", "/api/datapack-toggle", {"name": "loot.zip", "enabled": True})
    assert code == 200 and "Enabling" in data["said"]
    assert apex.call("POST", "/api/datapack-toggle", {"name": "loot.zip", "enabled": "yes"})[0] == 400
    assert apex.call("POST", "/api/datapack-toggle", {"name": "gone.zip", "enabled": True})[0] == 404
    assert apex.call("POST", "/api/datapack-reload", {})[0] == 200
    assert "datapack-enable loot.zip" in actions(apex) and "datapack-reload" in actions(apex)


# ---------------------------------------------------------------- the server icon


def test_the_server_icon_must_be_a_64_pixel_png(apex):
    icon = apex.root / "server-icon.png"
    assert apex.call("GET", "/api/server-icon")[1]["icon"] is None
    assert apex.call("POST", "/api/server-icon", b"GIF89a....")[0] == 400
    code, data = apex.call("POST", "/api/server-icon", png(128, 128))
    assert code == 400 and "128 by 128" in data["error"]
    good = png(64, 64)
    code, data = apex.call("POST", "/api/server-icon", good)
    assert code == 200 and icon.read_bytes() == good and data["icon"].startswith("data:image/png;base64,")
    code, data = apex.call("POST", "/api/server-icon", good)
    assert code == 200 and data["kept_in"].endswith("/icon")
    code, data = apex.call("POST", "/api/server-icon-remove", {})
    assert code == 200 and not icon.exists()
    assert apex.call("POST", "/api/server-icon-remove", {})[0] == 404
    assert "server-icon" in actions(apex)


# ---------------------------------------------------------------- a Modrinth modpack


class FakeCdn:
    def __init__(self, files):
        self.files, self.urls = files, []

    def __call__(self, url, most):
        self.urls.append(url)
        return self.files[url]


def mrpack(files, deps=None, extra=None) -> bytes:
    index = {"formatVersion": 1, "game": "minecraft", "name": "Test pack", "versionId": "1",
             "dependencies": deps if deps is not None else {"minecraft": "26.2", "fabric-loader": "0.19.5"},
             "files": files}
    return zipped({"modrinth.index.json": json.dumps(index), **(extra or {})})


def entry(name, data, url=None, server="required"):
    return {"path": f"mods/{name}", "hashes": {"sha512": hashlib.sha512(data).hexdigest()},
            "env": {"client": "required", "server": server},
            "downloads": [url or f"https://cdn.modrinth.com/data/AAAAAAAA/versions/BBBBBBBB/{name}"]}


def pack_setup(b, tmp_path):
    (b.live / "monkey").mkdir(exist_ok=True)
    (b.live / "monkey" / "manifest.json").write_text(json.dumps({"minecraft": "26.2"}))
    lithium = tmp_path / "lithium.jar"
    jar(lithium, {"id": "lithium", "name": "Lithium", "version": "1", "environment": "*"})
    sodium = tmp_path / "sodium.jar"
    jar(sodium, {"id": "sodium", "name": "Sodium", "version": "1", "environment": "client"})
    extra = tmp_path / "extra.jar"
    jar(extra, {"id": "extra", "name": "Extra", "version": "1"})
    return lithium.read_bytes(), sodium.read_bytes(), extra.read_bytes()


def test_a_modpack_installs_its_server_mods_all_or_nothing(apex, tmp_path):
    lithium, sodium, extra = pack_setup(apex, tmp_path)
    good = [entry("lithium.jar", lithium), entry("sodium.jar", sodium),
            entry("skip.jar", b"x", server="unsupported")]
    cdn = FakeCdn({e["downloads"][0]: d for e, d in zip(good, (lithium, sodium, b"x"), strict=True)})
    staff_more.more(apex.panel).fetch = cdn
    body = mrpack(good, extra={"overrides/mods/extra.jar": extra, "overrides/config/a.toml": "x=1"})
    assert apex.call("POST", url("/api/modpack", "test.mrpack", "nope"), body)[0] == 400
    code, data = apex.call("POST", url("/api/modpack", "test.mrpack"), body)
    assert code == 200, data
    assert sorted(data["installed"]) == ["extra.jar", "lithium.jar"] and data["skipped"] == 1
    mods = apex.root / "mods"
    assert (mods / "lithium.jar").read_bytes() == lithium and not (mods / "sodium.jar").exists()
    assert not (apex.root / "config" / "a.toml").exists()
    assert all("skip.jar" not in u for u in cdn.urls)
    assert "modpack test.mrpack: 2 mod(s)" in actions(apex)


def test_a_modpack_with_two_jars_for_one_mod_is_refused(apex, tmp_path):
    lithium, _, _ = pack_setup(apex, tmp_path)
    twice = [entry("lithium.jar", lithium), entry("lithium-copy.jar", lithium)]
    staff_more.more(apex.panel).fetch = FakeCdn({e["downloads"][0]: lithium for e in twice})
    before = sorted(p.name for p in (apex.root / "mods").iterdir())
    code, data = apex.call("POST", url("/api/modpack", "twice.mrpack"), mrpack(twice))
    assert code == 400 and "two jars for the mod lithium" in data["error"]
    assert sorted(p.name for p in (apex.root / "mods").iterdir()) == before


@pytest.mark.parametrize("problem", ["version", "loader", "sha", "host", "notmod"])
def test_a_bad_modpack_installs_nothing(apex, tmp_path, problem):
    lithium, _, _ = pack_setup(apex, tmp_path)
    deps = {"minecraft": "26.1", "fabric-loader": "1"} if problem == "version" else \
        {"minecraft": "26.2", "quilt-loader": "1"} if problem == "loader" else None
    good = entry("good.jar", lithium)
    bad = entry("bad.jar", b"not a jar" if problem == "notmod" else lithium,
                url="https://evil.example/bad.jar" if problem == "host" else None)
    if problem == "sha":
        bad["hashes"]["sha512"] = "0" * 128
    staff_more.more(apex.panel).fetch = FakeCdn({good["downloads"][0]: lithium,
                                                 bad["downloads"][0]: b"not a jar" if problem == "notmod" else lithium})
    before = sorted(p.name for p in (apex.root / "mods").iterdir())
    code, _ = apex.call("POST", url("/api/modpack", "bad.mrpack"), mrpack([good, bad], deps))
    assert code in (400, 502)
    assert sorted(p.name for p in (apex.root / "mods").iterdir()) == before


def test_staff_host_registers_this_module():
    assert staff_more.ROUTES and all(staff_panel.ROUTES[k] is v for k, v in staff_more.ROUTES.items())
    assert staff_host.MOD_MAX == 64 * staff_more.MB
