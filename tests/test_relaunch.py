import hashlib

import pytest
import relaunch
from conftest import FABRIC_RELEASE, frozen_manifest, paper_build, paper_builds_url

import check_updates
import entries
from check_updates import LOADERS
from upstream import MODRINTH, RecordedHttp, Upstream, json_query

MC = "26.3"


def _version(slug, number, channel, date, deps=()):
    data = f"{slug} {number}".encode()
    name = f"{slug}-{number}.jar"
    return {"id": f"v-{slug}-{number}", "project_id": f"id-{slug}", "version_number": number,
            "version_type": channel, "date_published": date,
            "dependencies": [{"project_id": f"id-{d}", "dependency_type": "required"} for d in deps],
            "files": [{"filename": name, "primary": True, "size": len(data),
                       "url": f"https://cdn.modrinth.com/data/id-{slug}/versions/{number}/{name}",
                       "hashes": {"sha1": hashlib.sha1(data).hexdigest(),
                                  "sha512": hashlib.sha512(data).hexdigest()}}]}


def _serve(http, versions_by_slug, known=None):
    known = sorted(known if known is not None else versions_by_slug)
    http.add("GET", f"{MODRINTH}/projects?ids={json_query(sorted(versions_by_slug))}",
             [{"id": f"id-{s}", "slug": s} for s in known])
    for slug, versions in versions_by_slug.items():
        url = (f"{MODRINTH}/project/id-{slug}/version?game_versions={json_query([MC])}"
               f"&loaders={json_query(LOADERS['plugin'])}")
        http.add("GET", url, versions)


def test_paper_replaces_fabric_and_empties_mods_and_datapacks():
    http = RecordedHttp()
    http.add("GET", paper_builds_url(MC), [paper_build(261, b"a"), paper_build(262, b"b"),
                                           paper_build(263, b"c", channel="BETA")])
    fabric = frozen_manifest(FABRIC_RELEASE)
    out = relaunch.pin_paper(fabric, MC, Upstream(http))
    assert out["minecraft"] == MC
    assert (out["server"]["type"], out["server"]["build"]) == ("paper", 262)
    assert out["mods"] == out["plugins"] == out["datapacks"] == []
    assert (out["java"], out["world"]) == (fabric["java"], fabric["world"])
    assert entries.check_types(out) == []


def test_no_stable_paper_build_stops():
    http = RecordedHttp()
    http.add("GET", paper_builds_url(MC), [paper_build(5, b"a", channel="BETA")])
    with pytest.raises(SystemExit, match="no STABLE build"):
        relaunch.pin_paper(frozen_manifest(FABRIC_RELEASE), MC, Upstream(http))


def test_pins_releases_takes_geyser_beta_and_reports_gaps():
    http = RecordedHttp()
    _serve(http, {
        "geyser": [_version("geyser", "2.12.0-b1269", "beta", "2026-10-22T00:00:00Z")],
        "luckperms": [_version("luckperms", "5.6", "beta", "2026-11-01T00:00:00Z"),
                      _version("luckperms", "5.5", "release", "2026-10-01T00:00:00Z")],
        "grimac": [_version("grimac", "2.4", "release", "2026-10-01T00:00:00Z", deps=["packetevents"])],
        "essentialsx": [_version("essentialsx", "2.23-dev", "beta", "2026-11-01T00:00:00Z")],
        "nope": [],
    }, known=["geyser", "luckperms", "grimac", "essentialsx"])
    http.add("GET", f"{MODRINTH}/projects?ids={json_query(['id-packetevents'])}",
             [{"id": "id-packetevents", "slug": "packetevents"}])
    manifest = {"minecraft": MC, "plugins": [], "mods": [], "datapacks": []}
    out, rows = relaunch.pin_stack(manifest, ["geyser", "luckperms", "grimac", "essentialsx", "nope"], Upstream(http))
    pinned = {e["slug"]: e["version"] for e in out["plugins"]}
    assert pinned == {"geyser": "2.12.0-b1269", "luckperms": "5.5", "grimac": "2.4"}
    assert all(entries.check("plugin", e) == [] for e in out["plugins"])
    by = {r["slug"]: r for r in rows}
    assert by["grimac"]["needs"] == ["packetevents"]
    assert "release build" in by["essentialsx"]["problem"]
    assert "not on Modrinth" in by["nope"]["problem"]
    text = relaunch.report({**out, "server": {"build": 262}}, rows)
    assert "| geyser | 2.12.0-b1269 | beta |" in text and "**not pinned:**" in text


def test_check_updates_moves_geyser_along_its_beta_channel():
    old = _version("geyser", "b1260", "beta", "2026-10-01T00:00:00Z")
    new = _version("geyser", "b1269", "beta", "2026-10-22T00:00:00Z")
    entry = entries.added("plugin", "geyser", old)
    assert check_updates.newer_release([old, new], entry) is None
    assert check_updates.newer_release([old, new], entry, entries.channels("geyser"))["id"] == new["id"]
    assert entries.channels("luckperms") == ("release",)


def _geysermc_build(build_id: int, jar: bytes) -> dict:
    return {"project_id": "floodgate", "version": "2.2.5", "build": build_id,
            "downloads": {"spigot": {"name": "floodgate-spigot.jar", "sha256": hashlib.sha256(jar).hexdigest()}}}


def test_floodgate_is_pinned_from_geysermc_and_checked():
    http = RecordedHttp()
    jar = b"floodgate 141"
    http.add("GET", f"{entries.GEYSERMC}/floodgate/versions/latest/builds/latest", _geysermc_build(141, jar))
    http.add("GET", entries.geysermc_url("floodgate", "2.2.5", 141), jar)
    out, rows = relaunch.pin_geysermc({"plugins": []}, ["floodgate"], Upstream(http))
    (e,) = out["plugins"]
    assert (e["build"], e["size"], e["file"]) == (141, len(jar), "floodgate-spigot.jar")
    assert entries.check("plugin", e) == []
    assert rows == [{"slug": "floodgate", "version": "2.2.5 b141", "channel": "GeyserMC"}]
    assert entries.check("mod", e)  # only a plugin may come from GeyserMC
    assert entries.check("plugin", {**e, "url": e["url"].replace("spigot", "velocity")})
    assert entries.check("plugin", {**e, "geysermc": "geyser", "slug": "geyser"})


def test_geysermc_download_must_match_its_sha256():
    with pytest.raises(ValueError, match="sha256"):
        entries.geysermc("floodgate", _geysermc_build(141, b"real"), b"tampered")


def test_check_updates_follows_floodgate_builds():
    old = entries.geysermc("floodgate", _geysermc_build(141, b"a"), b"a")
    http = RecordedHttp()
    http.add("GET", f"{entries.GEYSERMC}/floodgate/versions/latest/builds/latest", _geysermc_build(142, b"b"))
    http.add("GET", entries.geysermc_url("floodgate", "2.2.5", 142), b"b")
    found = check_updates.geysermc_update("plugin", old, Upstream(http))
    assert found.entry["build"] == 142
    http2 = RecordedHttp()
    http2.add("GET", f"{entries.GEYSERMC}/floodgate/versions/latest/builds/latest", _geysermc_build(141, b"a"))
    assert check_updates.geysermc_update("plugin", old, Upstream(http2)) is None


def test_candidates_are_reported_but_never_pinned():
    http = RecordedHttp()
    _serve(http, {"openeco": [_version("openeco", "1.0", "release", "2026-11-01T00:00:00Z")],
                  "zauctionhouse": [_version("zauctionhouse", "4.0-dev", "beta", "2026-11-01T00:00:00Z")]})
    rows = relaunch.check_candidates(MC, ["openeco", "zauctionhouse"], Upstream(http))
    assert rows[0] == {"slug": "openeco", "version": "1.0", "channel": "release"}
    assert "release build" in rows[1]["problem"]
    text = relaunch.report({"minecraft": MC, "server": {"build": 262}, "plugins": []}, [], rows)
    assert "## Candidates (checked, not pinned)" in text and "| openeco | 1.0 | release |" in text
    assert "**no build:**" in text
