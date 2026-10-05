import hashlib

import pytest

import add
import entries
from check_updates import LOADERS
from upstream import MODRINTH, RecordedHttp, Upstream, json_query

MC = "26.1.2"


def _project(http, slug, versions, kind="datapack"):
    pid = f"id-{slug}"
    url = f"{MODRINTH}/project/{pid}/version?game_versions={json_query([MC])}&loaders={json_query(LOADERS[kind])}"
    http.add("GET", url, versions)
    return {"id": pid, "slug": slug}


def _version(slug, number, channel, date, name):
    data = f"{slug} {number}".encode()
    return {"id": f"v-{slug}-{number}", "project_id": f"id-{slug}", "version_number": number,
            "version_type": channel, "date_published": date,
            "files": [{"filename": name, "primary": True, "size": len(data),
                       "url": f"https://cdn.modrinth.com/data/id-{slug}/versions/{number}/{name}",
                       "hashes": {"sha1": hashlib.sha1(data).hexdigest(),
                                  "sha512": hashlib.sha512(data).hexdigest()}}]}


def _setup(projects):
    http = RecordedHttp()
    slugs = sorted(p["slug"] for p in projects)
    http.add("GET", f"{MODRINTH}/projects?ids={json_query(slugs)}", projects)
    return http


def _manifest(existing=()):
    return {"minecraft": MC, "plugins": [], "datapacks": list(existing)}


def test_adds_the_newest_stable_release_sorted_and_valid():
    http = RecordedHttp()
    corpses = _project(http, "player-corpses", [
        _version("player-corpses", "2.0", "release", "2026-09-01T00:00:00Z", "corpses-2.0.zip"),
        _version("player-corpses", "2.1-beta", "beta", "2026-09-20T00:00:00Z", "corpses-2.1b.zip"),
        _version("player-corpses", "1.9", "release", "2026-08-01T00:00:00Z", "corpses-1.9.zip"),
    ])
    http.add("GET", f"{MODRINTH}/projects?ids={json_query(['player-corpses'])}", [corpses])
    existing = {"slug": "terralith", "project_id": "id-terralith"}
    out, added = add.add(_manifest([existing]), "datapack", ["player-corpses"], Upstream(http))
    assert added == ["player-corpses"]
    assert [e["slug"] for e in out["datapacks"]] == ["player-corpses", "terralith"]
    entry = out["datapacks"][0]
    assert (entry["version"], entry["file"]) == ("2.0", "corpses-2.0.zip")
    assert entries.check("datapack", entry) == []


def test_projects_already_pinned_are_skipped():
    http = _setup([{"id": "id-terralith", "slug": "terralith"}])
    m = _manifest([{"slug": "terralith", "project_id": "id-terralith"}])
    out, added = add.add(m, "datapack", ["terralith"], Upstream(http))
    assert added == [] and out["datapacks"] == m["datapacks"]


def test_no_stable_build_for_our_version_adds_nothing():
    http = RecordedHttp()
    beta_only = _project(http, "shiny", [_version("shiny", "0.1", "beta", "2026-09-01T00:00:00Z", "s.zip")])
    http.add("GET", f"{MODRINTH}/projects?ids={json_query(['shiny'])}", [beta_only])
    with pytest.raises(SystemExit, match="shiny: no stable datapack release"):
        add.add(_manifest(), "datapack", ["shiny"], Upstream(http))


def test_unknown_project_fails():
    http = _setup([])
    http.add("GET", f"{MODRINTH}/projects?ids={json_query(['nope'])}", [])
    with pytest.raises(SystemExit, match="not on Modrinth: nope"):
        add.add(_manifest(), "datapack", ["nope"], Upstream(http))
