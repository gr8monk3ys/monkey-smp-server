"""The client pack's optional files (tools/client_env.py), checked against facts recorded from every mod jar
(tests/fixtures/client_mods.json; re-record with `python -I tests/fixtures/record_client_mods.py`)."""
from pathlib import Path

import pytest

import client_env
from repo import REPO, load_json

FACTS = load_json(Path(__file__).parent / "fixtures" / "client_mods.json")
INDEX = load_json(REPO.client / "modrinth.index.json")
MODS = {client_env.project_id(f): f for f in INDEX["files"] if f["path"].startswith("mods/")}
SERVER = {e["project_id"] for e in REPO.load_manifest()["mods"]}
REQUIRED = sorted(pid for pid in MODS if pid not in client_env.OPTIONAL_MODS)
RECORD = "re-record tests/fixtures/client_mods.json with `python -I tests/fixtures/record_client_mods.py`"

# Client-side although Modrinth calls its client half "required" (Modrinth's way of saying "a client mod"):
AUDITED = {
    "qyVF9oeo": "Sound Physics Remastered: client audio; its server half only sends settings to clients that have it",
}


def providers(mod_id: str) -> set[str]:
    """The projects in the pack whose jar (or a jar nested in it) provides this mod id."""
    return {pid for pid, f in FACTS.items() if mod_id in f["ids"]}


def test_facts_cover_exactly_the_mods_in_the_pack():
    assert set(FACTS) == set(MODS), RECORD


def test_the_index_marks_exactly_what_client_env_says():
    assert client_env.check(INDEX) == []


def test_every_optional_mod_is_in_the_pack_with_a_known_kind():
    assert set(client_env.OPTIONAL_MODS) <= set(MODS)
    assert {kind for _, kind in client_env.OPTIONAL_MODS.values()} <= set(client_env.KINDS)
    assert {pid: slug for pid, (slug, _) in client_env.OPTIONAL_MODS.items()} == {
        pid: FACTS[pid]["slug"] for pid in client_env.OPTIONAL_MODS}


def test_resource_packs_and_shaders_are_optional():
    others = [f for f in INDEX["files"] if not f["path"].startswith("mods/")]
    assert others and all(f["env"]["client"] == "optional" for f in others)
    assert {f["path"].split("/")[0] for f in others} == {"resourcepacks", "shaderpacks"}


@pytest.mark.parametrize("pid", sorted(client_env.OPTIONAL_MODS))
def test_every_optional_mod_really_is_client_side(pid):
    """Off the server, client-only by fabric.mod.json, or a server mod whose client half Modrinth calls optional."""
    f = FACTS[pid]
    assert (pid not in SERVER or f["environment"] == "client"
            or f["modrinth"]["client"] in ("optional", "unsupported") or pid in AUDITED), f["slug"]


@pytest.mark.parametrize("pid", sorted(pid for pid in client_env.OPTIONAL_MODS if pid in SERVER))
def test_no_optional_server_mod_adds_blocks_items_or_entities(pid):
    """Registry content (here: a mod with code that ships block, item or entity assets) must be on both
    sides, or Fabric refuses the join. Datapacks packaged as mods have no code and can't add any."""
    f = FACTS[pid]
    if f["environment"] == "client":
        return  # the server doesn't even load it
    assert not (f["code"] and (f["blockstates"] or f["items"] or f["entity_textures"])), f["slug"]


@pytest.mark.parametrize("pid", REQUIRED)
def test_required_mods_never_need_an_optional_one(pid):
    """Unticking every optional file must still leave a pack that launches."""
    for dep in FACTS[pid]["depends"]:
        found = providers(dep)
        assert found, f"{FACTS[pid]['slug']} depends on {dep}, which nothing in the pack provides"
        assert found - set(client_env.OPTIONAL_MODS), (
            f"{FACTS[pid]['slug']} depends on {dep}, which only optional mods provide: "
            f"{sorted(FACTS[p]['slug'] for p in found)}")


def test_every_dependency_of_an_optional_mod_is_in_the_pack():
    missing = [(f["slug"], dep) for pid, f in FACTS.items() if pid in client_env.OPTIONAL_MODS
               for dep in f["depends"] if not providers(dep)]
    assert missing == []


def test_audited_mods_are_optional_and_on_the_server():
    assert set(AUDITED) <= set(client_env.OPTIONAL_MODS)
    assert set(AUDITED) <= SERVER  # off the server they would need no audit


def test_client_env_of_index_entries():
    def entry(path, url):
        return {"path": path, "downloads": [url]}

    sodium = next(pid for pid, (slug, _) in client_env.OPTIONAL_MODS.items() if slug == "sodium")
    url = "https://cdn.modrinth.com/data/{}/versions/abc/x.jar"
    assert client_env.client_env(entry("mods/sodium.jar", url.format(sodium))) == "optional"
    assert client_env.client_env(entry("mods/fabric-api.jar", url.format("P7dR8mSH"))) == "required"
    assert client_env.client_env(entry("mods/unknown.jar", url.format("zzzzzzzz"))) == "required"
    assert client_env.client_env(entry("shaderpacks/a.zip", url.format("zzzzzzzz"))) == "optional"
    assert client_env.env(entry("resourcepacks/b.zip", url.format("zzzzzzzz"))) == {
        "client": "optional", "server": "unsupported"}
    drifted = {"files": [{**entry("mods/sodium.jar", url.format(sodium)),
                          "env": {"client": "required", "server": "unsupported"}}]}
    assert client_env.check(drifted) == ["client mods/sodium.jar: env must be "
                                         "{'client': 'optional', 'server': 'unsupported'} (see tools/client_env.py)"]
