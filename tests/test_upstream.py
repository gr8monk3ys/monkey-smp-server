import random

import pytest
from conftest import paper_build, paper_builds_url

from check_updates import LOADERS
from upstream import MODRINTH, RecordedHttp, RecordingHttp, UnrecordedRequest, Upstream, request_key

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
