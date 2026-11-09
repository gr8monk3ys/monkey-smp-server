"""tools/pack_sync.py: the panel's list of mod changes players need becomes a change to the players' pack."""
import hashlib
import json
import subprocess

import pytest

import client_env
import entries
import pack_sync
from repo import Repo, load_json, save_json
from upstream import MODRINTH, RecordedHttp, Upstream, json_query

MC = "26.2"


def cdn(project, version, name):
    return f"https://cdn.modrinth.com/data/{project}/versions/{version}/{name}"


def file_of(project, version, name, data=None):
    data = data or f"{project} {version} {name}".encode()
    return {"filename": name, "primary": True, "size": len(data), "url": cdn(project, version, name),
            "hashes": {"sha1": hashlib.sha1(data).hexdigest(), "sha512": hashlib.sha512(data).hexdigest()}}


def version_of(project, number, files, mc=MC, loaders=("fabric",)):
    return {"id": f"V{number.replace('.', '')}{project}"[:8], "project_id": project, "version_number": number,
            "game_versions": [mc], "loaders": list(loaders), "files": files}


def client(f, project, version):
    url = cdn(project, version, f["filename"])
    return {"path": f"mods/{f['filename']}", "hashes": dict(f["hashes"]),
            "env": client_env.env({"path": f"mods/{f['filename']}", "downloads": [url]}),
            "downloads": [url], "fileSize": f["size"]}


def pinned(version, f, slug):
    return entries.from_disk(version, f["hashes"]["sha1"], slug, disk_name=f["filename"])


CLAIMS = file_of("Claims12", "c1", "claims-1.0.jar")
CLAIMS_V = version_of("Claims12", "1.0", [CLAIMS])
TRIMS = file_of("Trims123", "t1", "Trims-2.0.jar")
TRIMS_V = version_of("Trims123", "2.0", [TRIMS])
PACK = {"path": "resourcepacks/Fresh.zip", "hashes": {"sha1": "a" * 40, "sha512": "b" * 128},
        "env": {"client": "optional", "server": "unsupported"},
        "downloads": ["https://cdn.modrinth.com/data/Pack1234/versions/p1/Fresh.zip"], "fileSize": 3}


@pytest.fixture
def repo(tmp_path):
    r = Repo(tmp_path)
    (tmp_path / "client").mkdir()
    (tmp_path / "package" / "monkey").mkdir(parents=True)
    save_json(r.client / "modrinth.index.json", {
        "formatVersion": 1, "game": "minecraft", "versionId": "3.1.0", "name": "Monkey SMP - Client",
        "files": [client(CLAIMS, "Claims12", "c1"), client(TRIMS, "Trims123", "t1"), PACK],
        "dependencies": {"minecraft": MC, "fabric-loader": "0.20.1"}})
    r.save_manifest({"name": "Monkey SMP", "version": "3.1.1", "minecraft": MC, "plugins": [], "datapacks": [],
                     "mods": [pinned(CLAIMS_V, CLAIMS, "claims"), pinned(TRIMS_V, TRIMS, "trims")]})
    return r


class Runs:
    """subprocess.run stand-in: answers ssh with the panel's list, and every other command with success."""

    def __init__(self, listing=None, fail=()):
        self.listing, self.fail, self.calls = listing, fail, []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if cmd[0] == "ssh":
            if self.listing is None:
                return subprocess.CompletedProcess(cmd, 1, "", "cat: x: No such file or directory")
            return subprocess.CompletedProcess(cmd, 0, json.dumps({"changes": self.listing}), "")
        return subprocess.CompletedProcess(cmd, 1 if any(f in cmd for f in self.fail) else 0, "", "")

    def ran(self, word):
        return [c for c in self.calls if word in c or any(word in str(x) for x in c)]


def modrinth(found, projects=(), asked=()):
    """Modrinth knowing the versions in `found` ({sha512: version}), asked about those and `asked`."""
    http = RecordedHttp()
    hashes = sorted(set(found) | set(asked))
    if hashes:
        http.add("POST", f"{MODRINTH}/version_files", found, body={"hashes": hashes, "algorithm": "sha512"})
    ids = sorted({v["project_id"] for v in found.values()})
    if ids:
        http.add("GET", f"{MODRINTH}/projects?ids={json_query(ids)}",
                 [{"id": p, "slug": s} for p, s in projects if p in ids])
    return Upstream(http)


def add_line(f, name=None):
    return {"file": name or f["filename"], "action": "add", "project": None, "sha512": f["hashes"]["sha512"],
            "by": "owner", "at": "2026-11-08T20:00:00Z"}


def files(repo):
    return [f["path"] for f in load_json(repo.client / "modrinth.index.json")["files"]]


def mods(repo):
    return [(e["slug"], e["version"], e["file"]) for e in repo.load_manifest()["mods"]]


def test_an_add_pins_the_same_modrinth_file_in_the_pack_and_the_manifest(repo):
    ships = file_of("Ships123", "s1", "ships-0.9.jar")
    runs = Runs([add_line(ships, "Ships upload.jar")])
    up = modrinth({ships["hashes"]["sha512"]: version_of("Ships123", "0.9", [ships])}, [("Ships123", "ships")])
    assert pack_sync.main(["--ssh", "owner@monkey"], repo=repo, upstream=up, run=runs) == 0
    assert runs.calls[0] == ["ssh", "owner@monkey", "cat", "--", pack_sync.REMOTE]
    assert files(repo) == ["mods/claims-1.0.jar", "mods/ships-0.9.jar", "mods/Trims-2.0.jar", "resourcepacks/Fresh.zip"]
    entry = load_json(repo.client / "modrinth.index.json")["files"][1]
    assert entry == client(ships, "Ships123", "s1") and entry["env"]["client"] == "required"
    assert mods(repo) == [("claims", "1.0", "claims-1.0.jar"), ("ships", "0.9", "ships-0.9.jar"),
                          ("trims", "2.0", "Trims-2.0.jar")]
    assert all(not entries.check("mod", e) for e in repo.load_manifest()["mods"])
    assert not client_env.check(load_json(repo.client / "modrinth.index.json"))
    assert runs.ran("tools/validate.py") and runs.ran("tests/fixtures/record_client_mods.py")  # a new mod: re-record
    assert not runs.ran("git") and not runs.ran("gh")


def test_a_new_version_replaces_the_old_one_and_keeps_the_slug(repo):
    newer = file_of("Claims12", "c2", "claims-1.1.jar")
    runs = Runs([add_line(newer)])
    up = modrinth({newer["hashes"]["sha512"]: version_of("Claims12", "1.1", [newer])})  # slug from the manifest
    assert pack_sync.main(["--ssh", "monkey"], repo=repo, upstream=up, run=runs) == 0
    assert files(repo) == ["mods/claims-1.1.jar", "mods/Trims-2.0.jar", "resourcepacks/Fresh.zip"]
    assert mods(repo)[0] == ("claims", "1.1", "claims-1.1.jar")
    assert runs.ran("tools/validate.py") and not runs.ran("tests/fixtures/record_client_mods.py")  # same mods


def test_a_removal_drops_the_project_from_both_and_only_turned_off_waits_for_include_off(repo):
    lines = [{"file": "claims-1.0.jar", "action": "remove", "how": "held", "project": "Claims12"},
             {"file": "Trims-2.0.jar", "action": "remove", "how": "off", "project": "Trims123"}]
    assert pack_sync.main(["--ssh", "monkey"], repo=repo, upstream=modrinth({}), run=Runs(lines)) == 0
    assert files(repo) == ["mods/Trims-2.0.jar", "resourcepacks/Fresh.zip"] and [m[0] for m in mods(repo)] == ["trims"]
    assert pack_sync.main(["--ssh", "monkey", "--include-off"], repo=repo, upstream=modrinth({}), run=Runs(lines)) == 0
    assert files(repo) == ["resourcepacks/Fresh.zip"] and mods(repo) == []


@pytest.mark.parametrize("found, why", [
    ({}, "Modrinth doesn't know this jar"),
    ("other-game", "is not for Fabric 26.2"),
    ("split", "has 2 jars"),
])
def test_a_jar_the_tool_cant_pin_safely_is_refused_and_changes_nothing(repo, capsys, found, why):
    ships = file_of("Ships123", "s1", "ships-0.9.jar")
    if found == "other-game":
        found = {ships["hashes"]["sha512"]: version_of("Ships123", "0.9", [ships], mc="26.1.2")}
    elif found == "split":
        both = [ships, file_of("Ships123", "s1", "ships-client.jar")]
        found = {ships["hashes"]["sha512"]: version_of("Ships123", "0.9", both)}
    before = (repo.client / "modrinth.index.json").read_bytes(), repo.manifest.read_bytes()
    runs = Runs([add_line(ships)])
    up = modrinth(found, [("Ships123", "ships")], asked=[ships["hashes"]["sha512"]])
    assert pack_sync.main(["--ssh", "monkey"], repo=repo, upstream=up, run=runs) == 1
    assert why in capsys.readouterr().out
    assert ((repo.client / "modrinth.index.json").read_bytes(), repo.manifest.read_bytes()) == before
    assert runs.calls == [runs.calls[0]]                        # only the ssh read: no validate, no git


def test_a_patched_mod_is_left_for_a_hand_edit(repo, capsys):
    manifest = repo.load_manifest()
    manifest["mods"][0]["patch"] = {"file": "claims.json"}
    repo.save_manifest(manifest)
    newer = file_of("Claims12", "c2", "claims-1.1.jar")
    up = modrinth({newer["hashes"]["sha512"]: version_of("Claims12", "1.1", [newer])})
    lines = [add_line(newer), {"file": "claims-1.0.jar", "action": "remove", "how": "held", "project": "Claims12"}]
    assert pack_sync.main(["--ssh", "monkey"], repo=repo, upstream=up, run=Runs(lines)) == 1
    assert capsys.readouterr().out.count("patched") == 2 and mods(repo)[0][1] == "1.0"


def test_dry_run_and_an_empty_list_write_nothing(repo, capsys):
    ships = file_of("Ships123", "s1", "ships-0.9.jar")
    up = modrinth({ships["hashes"]["sha512"]: version_of("Ships123", "0.9", [ships])}, [("Ships123", "ships")])
    before = repo.manifest.read_bytes()
    runs = Runs([add_line(ships)])
    assert pack_sync.main(["--ssh", "monkey", "--dry-run"], repo=repo, upstream=up, run=runs) == 0
    assert "would have added" in capsys.readouterr().out and repo.manifest.read_bytes() == before
    assert len(runs.calls) == 1
    assert pack_sync.main(["--ssh", "monkey"], repo=repo, upstream=modrinth({}), run=Runs(None)) == 0  # no file yet
    assert "nothing for the players' pack" in capsys.readouterr().out


def test_pr_commits_the_two_lists_on_a_new_branch_and_opens_a_draft(repo):
    lines = [{"file": "claims-1.0.jar", "action": "remove", "how": "removed", "project": "Claims12",
              "by": "owner", "at": "2026-11-08T20:00:00Z"}]
    runs = Runs(lines)
    assert pack_sync.main(["--ssh", "monkey", "--pr"], repo=repo, upstream=modrinth({}), run=runs) == 0
    git = [c for c in runs.calls if c[0] in ("git", "gh")]
    assert git[0][:3] == ["git", "switch", "-c"] and git[0][3].startswith("pack-sync/")
    assert git[1] == ["git", "add", "--", "client/modrinth.index.json", "package/monkey/manifest.json",
                      pack_sync.FIXTURE]
    assert git[3][:3] == ["git", "push", "-u"] and git[3][4] == git[0][3]   # its own branch, never main
    assert git[4][:4] == ["gh", "pr", "create", "--draft"] and "removed claims-1.0.jar" in git[4][-1]


def test_a_failed_validate_stops_before_any_pull_request(repo):
    lines = [{"file": "claims-1.0.jar", "action": "remove", "how": "held", "project": "Claims12"}]
    runs = Runs(lines, fail=("tools/validate.py",))
    assert pack_sync.main(["--ssh", "monkey", "--pr"], repo=repo, upstream=modrinth({}), run=runs) == 1
    assert not runs.ran("git")


def test_running_again_after_the_change_is_made_changes_nothing(repo, capsys):
    lines = [{"file": "claims-1.0.jar", "action": "remove", "how": "held", "project": "Claims12"}]
    assert pack_sync.main(["--ssh", "monkey"], repo=repo, upstream=modrinth({}), run=Runs(lines)) == 0
    capsys.readouterr()
    runs = Runs(lines)                          # the panel keeps the line until the release is deployed
    assert pack_sync.main(["--ssh", "monkey", "--pr"], repo=repo, upstream=modrinth({}), run=runs) == 0
    out = capsys.readouterr().out
    assert "already out" in out and "have these changes already" in out and not runs.ran("git")


@pytest.mark.parametrize("argv", [["--ssh", "host;rm -rf /"], ["--ssh", "monkey", "--path", "/srv/x y.json"],
                                  ["--ssh", "-oProxyCommand=x"]])
def test_the_ssh_host_and_path_are_plain_words(repo, argv):
    runs = Runs([])
    with pytest.raises(SystemExit):
        pack_sync.main(argv, repo=repo, upstream=modrinth({}), run=runs)
    assert runs.calls == []


def test_a_copy_of_the_list_can_be_read_from_a_file(repo, tmp_path):
    copy = tmp_path / "changes.json"
    copy.write_text(json.dumps({"changes": [{"file": "Trims-2.0.jar", "action": "remove", "how": "removed",
                                             "project": "Trims123"}, {"file": 5}, "junk"]}))
    runs = Runs()
    assert pack_sync.main(["--file", str(copy)], repo=repo, upstream=modrinth({}), run=runs) == 0
    assert "mods/Trims-2.0.jar" not in files(repo) and not runs.ran("ssh")
