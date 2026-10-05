import random

import pytest
from conftest import paper_build, paper_builds_url

from check_updates import LOADERS
from upstream import (
    FABRIC_META,
    MODRINTH,
    RecordedHttp,
    RecordingHttp,
    UnrecordedRequest,
    Upstream,
    fabric_server_jar_url,
    request_key,
    version_key,
)

MC = "26.1.2"


def test_recorded_http_refuses_unrecorded_requests(recorded):
    with pytest.raises(UnrecordedRequest, match="GET https://example.invalid/nope"):
        recorded.get_json("https://example.invalid/nope")
    with pytest.raises(UnrecordedRequest):
        Upstream(recorded).newest_release("not-a-project", MC, ["datapack"])


def test_recorded_http_downloads_only_recorded_bytes():
    http = RecordedHttp().add("GET", "https://cdn.modrinth.com/a.zip", b"zip").add("GET", "https://x/j", {"a": 1})
    assert Upstream(http).download("https://cdn.modrinth.com/a.zip") == b"zip"
    with pytest.raises(UnrecordedRequest, match="not a download"):
        http.get_bytes("https://x/j")


def test_request_key_ignores_body_key_order():
    assert request_key("post", "u", {"a": 1, "b": [2, 1]}) == request_key("POST", "u", {"b": [2, 1], "a": 1})
    assert request_key("POST", "u", {"b": [2, 1]}) != request_key("POST", "u", {"b": [1, 2]})


def test_newest_stable_paper_build_does_not_trust_list_order(recorded):
    builds = recorded.get_json(paper_builds_url(MC))
    newest = max(b["id"] for b in builds)
    shuffled = builds[::-1] + [paper_build(newest + 50, b"experimental", channel="ALPHA")]
    random.Random(1).shuffle(shuffled)
    http = RecordedHttp().add("GET", paper_builds_url(MC), shuffled)
    assert Upstream(http).newest_stable_paper_build(MC)["id"] == newest


def test_newest_stable_paper_build_is_none_without_stable_builds():
    http = RecordedHttp().add("GET", paper_builds_url(MC), [paper_build(9, b"x", channel="BETA")])
    assert Upstream(http).newest_stable_paper_build(MC) is None


def test_newest_release_skips_alphas_and_picks_the_latest(recorded):
    up = Upstream(recorded)
    all_versions = up.modrinth_versions("zJhgi9nK", MC, ["datapack"])
    assert {v["version_type"] for v in all_versions} == {"release", "alpha"}
    assert up.newest_release("zJhgi9nK", MC, ["datapack"])["version_number"] == "1.2"


def test_modrinth_lookup_is_order_insensitive_and_names_projects(recorded):
    up = Upstream(recorded)
    newest = [up.newest_release("Vebnzrzj", MC, LOADERS["plugin"]),
              up.newest_release("zJhgi9nK", MC, LOADERS["datapack"]),
              up.newest_release("wBo7DRiB", MC, LOADERS["datapack"])]
    sha1s = [v["files"][0]["hashes"]["sha1"] for v in newest]
    found = up.modrinth_versions_by_sha1(reversed(sha1s))
    assert [found[h]["id"] for h in sha1s] == [v["id"] for v in newest]
    projects = up.modrinth_projects(v["project_id"] for v in found.values())
    assert projects["Vebnzrzj"]["slug"] == "luckperms"
    assert up.modrinth_versions_by_sha1([]) == {} and up.modrinth_projects([]) == {}


def test_recording_trims_responses_and_replays_them(tmp_path):
    url = f"{MODRINTH}/projects?ids=%5B%22p%22%5D"
    live = RecordedHttp().add("GET", url, [{"id": "p", "slug": "s", "body": "a long description", "downloads": 9}])
    recorder = Upstream(RecordingHttp(live, tmp_path))
    assert recorder.modrinth_projects(["p"]) == {"p": {"id": "p", "slug": "s"}}
    assert Upstream(RecordedHttp.from_folder(tmp_path)).modrinth_projects(["p"]) == {"p": {"id": "p", "slug": "s"}}


# --- Fabric meta -----------------------------------------------------------------------------------

def test_newest_stable_fabric_loader_and_installer_from_recorded_meta(recorded):
    up = Upstream(recorded)
    assert {x["stable"] for x in up.fabric_loaders("26.3")} == {True, False}
    assert up.newest_stable_fabric_loader("26.3") == "0.19.5"
    assert up.newest_stable_fabric_installer() == "1.1.2"


def test_newest_stable_fabric_versions_do_not_trust_list_order():
    loaders = [{"loader": {"version": v, "stable": s}} for v, s in
               [("0.9.9", True), ("0.19.10", True), ("0.19.11", False), ("0.19.2", True)]]
    http = RecordedHttp().add("GET", f"{FABRIC_META}/versions/loader/26.3", loaders)
    http.add("GET", f"{FABRIC_META}/versions/installer", [{"version": "1.0.9", "stable": False}])
    up = Upstream(http)
    assert up.newest_stable_fabric_loader("26.3") == "0.19.10"  # numerically, not as text
    assert up.newest_stable_fabric_installer() is None


def test_version_key_orders_dotted_versions():
    assert version_key("0.19.10") > version_key("0.19.9") > version_key("0.19")
    assert version_key("0.16.10+build.1") == (0, 16, 10)


def test_fabric_server_jar_url():
    assert fabric_server_jar_url("26.3", "0.19.5", "1.1.2") == \
        "https://meta.fabricmc.net/v2/versions/loader/26.3/0.19.5/1.1.2/server/jar"


def test_recording_trims_fabric_meta_responses(tmp_path):
    url = f"{FABRIC_META}/versions/loader/26.3"
    full = [{"loader": {"separator": ".", "build": n, "maven": "x", "version": f"0.19.{n}", "stable": n == 5},
             "intermediary": {"version": "0.0.0"}, "launcherMeta": {"libraries": {"common": ["big"]}}}
            for n in range(9)]
    recorder = Upstream(RecordingHttp(RecordedHttp().add("GET", url, full), tmp_path))
    assert [x["version"] for x in recorder.fabric_loaders("26.3")] == ["0.19.8", "0.19.7", "0.19.6", "0.19.5", "0.19.4"]
    replayed = Upstream(RecordedHttp.from_folder(tmp_path))
    assert replayed.fabric_loaders("26.3")[3] == {"version": "0.19.5", "stable": True}
