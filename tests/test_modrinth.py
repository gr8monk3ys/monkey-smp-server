import hashlib
import json
import subprocess
from email import policy
from email.parser import BytesParser

import pytest

import build
import modrinth
from modrinth import API_V3, NotFound
from repo import load_json, save_json
from upstream import MODRINTH

VERSION = "2.0.0"  # the frozen fabric release's manifest version
CHANGELOG = ("# Changelog\n\n## [Unreleased]\n\n## [2.0.0] - 2026-10-01\n\nFabric.\n\n- New mods.\n\n"
             "## [1.1.0]\n\nOld.\n")
SERVER_URL = f"{API_V3}/project/{modrinth.SERVER_PROJECT}"


@pytest.fixture
def repo(fabric_repo):
    (fabric_repo.root / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    return fabric_repo


def built_pack(repo, tmp_path, version=VERSION) -> bytes:
    """The .mrpack this repo builds for `version` (versionId is the only thing a version changes)."""
    out = tmp_path / f"pack-{version}"
    out.mkdir(exist_ok=True)
    return build.build_client(version, repo, out).read_bytes()


def remote_version(vid: str, number: str, pack: bytes, published: str) -> dict:
    url = f"https://cdn.modrinth.com/data/PACK/versions/{vid}/TheRealms-Client-{number}.mrpack"
    return {"id": vid, "version_number": number, "date_published": published,
            "files": [{"url": url, "primary": True, "hashes": {"sha512": hashlib.sha512(pack).hexdigest()}}]}


class FakeModrinth:
    """Modrinth's API as the tool uses it: one modpack (id PACK), an optional server listing, CDN files."""

    def __init__(self, versions=(), packs=(), server_links: str | None = "OLD"):
        """`packs` are the .mrpack bytes of `versions`, in the same order (only the ones a test downloads)."""
        self.versions = list(versions)
        self.files = {v["files"][0]["url"]: data for v, data in zip(self.versions, packs, strict=False)}
        self.server = None if server_links is None else {
            "id": "SRV", "minecraft_java_server": {"address": "monkeysmp.lscaturchio.xyz",
                                                   "content": {"kind": "modpack", "version_id": server_links}}}
        self.calls, self.uploads, self.edits = [], [], []

    def request(self, method, url, body=None, content_type=None):
        self.calls.append((method, url))
        if (method, url) == ("GET", f"{MODRINTH}/project/{modrinth.PACK_PROJECT}"):
            return {"id": "PACK"}
        if (method, url) == ("GET", f"{MODRINTH}/project/PACK/version"):
            return self.versions
        if (method, url) == ("POST", f"{MODRINTH}/version"):
            self.uploads.append(parse_multipart(body, content_type))
            return {"id": "NEW", "version_number": self.uploads[-1]["data"]["version_number"],
                    "date_published": "2099-01-01T00:00:00Z", "files": []}
        if (method, url) == ("GET", SERVER_URL):
            if self.server is None:
                raise NotFound(url)
            return self.server
        if (method, url) == ("PATCH", f"{API_V3}/project/SRV"):
            assert content_type == "application/json"
            self.edits.append(json.loads(body))
            return None
        raise AssertionError(f"unexpected request {method} {url}")

    def download(self, url):
        return self.files[url]


def parse_multipart(body: bytes, content_type: str) -> dict:
    msg = BytesParser(policy=policy.HTTP).parsebytes(b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body)
    parts = {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        parts[name] = part.get_payload(decode=True)
    parts["data"] = json.loads(parts["data"])
    return parts


def publish(repo, http, tmp_path, **kw):
    log = []
    vid = modrinth.publish(repo, http, modrinth.PACK_PROJECT, kw.pop("server", modrinth.SERVER_PROJECT),
                           tmp_path / "dist", log=log.append, **kw)
    return vid, log


# --- release notes and the upload request ----------------------------------------------------------------

def test_the_versions_notes_are_its_changelog_section(repo):
    assert modrinth.changelog(repo, "2.0.0") == "Fabric.\n\n- New mods."
    assert modrinth.changelog(repo, "1.1.0") == "Old."


def test_version_data_files_the_mrpack_as_a_fabric_modpack(repo):
    index = load_json(repo.client / "modrinth.index.json")
    data = modrinth.version_data("PACK", VERSION, index, "TheRealms-Client-2.0.0.mrpack", "notes")
    assert data["project_id"] == "PACK"
    assert data["version_number"] == VERSION and data["name"] == "Monkey SMP 2.0.0"
    assert data["game_versions"] == [index["dependencies"]["minecraft"]]
    assert data["loaders"] == ["fabric"]
    assert data["file_parts"] == ["TheRealms-Client-2.0.0.mrpack"] == [data["primary_file"]]
    assert data["version_type"] == "release" and data["status"] == "listed" and data["dependencies"] == []


def test_version_data_needs_a_loader():
    with pytest.raises(SystemExit, match="no loader"):
        modrinth.version_data("PACK", VERSION, {"dependencies": {"minecraft": "26.3"}}, "x.mrpack", "notes")


def test_pack_contents_ignores_only_the_version_number(repo, tmp_path):
    before = modrinth.pack_contents(built_pack(repo, tmp_path, "2.0.0"))
    assert modrinth.pack_contents(built_pack(repo, tmp_path, "2.0.1")) == before
    index = load_json(repo.client / "modrinth.index.json")
    index["files"] = index["files"][1:]
    save_json(repo.client / "modrinth.index.json", index)
    assert modrinth.pack_contents(built_pack(repo, tmp_path, "2.0.0")) != before


# --- publish -----------------------------------------------------------------------------------------------

def test_publish_uploads_the_first_version_and_points_the_server_at_it(repo, tmp_path):
    http = FakeModrinth()
    vid, _ = publish(repo, http, tmp_path)
    assert vid == "NEW"
    [upload] = http.uploads
    assert upload["data"]["version_number"] == VERSION
    assert upload["data"]["changelog"] == "Fabric.\n\n- New mods."
    assert upload["TheRealms-Client-2.0.0.mrpack"] == (tmp_path / "dist" / "TheRealms-Client-2.0.0.mrpack").read_bytes()
    assert http.edits == [{"minecraft_java_server": {"content": {"kind": "modpack", "version_id": "NEW"}}}]


def test_publish_skips_a_release_that_left_the_pack_alone(repo, tmp_path):
    old = built_pack(repo, tmp_path, "1.9.0")
    newest = remote_version("V19", "1.9.0", old, "2026-09-01T00:00:00Z")
    http = FakeModrinth([newest], [old])
    vid, log = publish(repo, http, tmp_path)
    assert vid == "V19" and http.uploads == []
    assert "nothing to upload" in log[0]
    assert http.edits == [{"minecraft_java_server": {"content": {"kind": "modpack", "version_id": "V19"}}}]


def test_publish_uploads_a_changed_pack(repo, tmp_path):
    old = built_pack(repo, tmp_path, "1.9.0")
    newest = remote_version("V19", "1.9.0", old, "2026-09-01T00:00:00Z")
    http = FakeModrinth([newest], [old])
    (repo.client / "overrides" / "options.txt").write_text("renderDistance:8\n", encoding="utf-8")
    vid, _ = publish(repo, http, tmp_path)
    assert vid == "NEW" and len(http.uploads) == 1


def test_force_uploads_an_unchanged_pack(repo, tmp_path):
    old = built_pack(repo, tmp_path, "1.9.0")
    newest = remote_version("V19", "1.9.0", old, "2026-09-01T00:00:00Z")
    http = FakeModrinth([newest], [old])
    vid, _ = publish(repo, http, tmp_path, force=True)
    assert vid == "NEW" and len(http.uploads) == 1


def test_a_rerun_finds_the_version_it_uploaded(repo, tmp_path):
    mine = remote_version("V20", VERSION, built_pack(repo, tmp_path), "2026-10-01T00:00:00Z")
    http = FakeModrinth([mine], server_links="V20")
    vid, log = publish(repo, http, tmp_path)
    assert vid == "V20" and http.uploads == [] and http.edits == []
    assert "already on Modrinth" in log[0] and "already links V20" in log[1]


def test_a_version_cannot_be_uploaded_twice_with_different_files(repo, tmp_path):
    other = remote_version("V20", VERSION, b"another pack", "2026-10-01T00:00:00Z")
    with pytest.raises(SystemExit, match="different file"):
        publish(repo, FakeModrinth([other]), tmp_path)


def test_an_older_version_leaves_the_server_listing_alone(repo, tmp_path):
    mine = remote_version("V20", VERSION, built_pack(repo, tmp_path), "2026-10-01T00:00:00Z")
    later = remote_version("V21", "2.1.0", b"newer", "2026-10-20T00:00:00Z")
    http = FakeModrinth([later, mine], server_links="V21")
    vid, log = publish(repo, http, tmp_path)
    assert vid == "V20" and http.edits == []
    assert ("GET", SERVER_URL) not in http.calls
    assert "stays put" in log[1]


def test_no_server_listing_yet_is_skipped(repo, tmp_path):
    http = FakeModrinth(server_links=None)
    vid, log = publish(repo, http, tmp_path)
    assert vid == "NEW" and http.edits == []
    assert "no server listing" in log[-1]


def test_an_empty_server_skips_the_listing(repo, tmp_path):
    http = FakeModrinth()
    publish(repo, http, tmp_path, server=None)
    assert ("GET", SERVER_URL) not in http.calls



# --- check -------------------------------------------------------------------------------------------------

def check(repo, http, tmp_path):
    log = []
    return modrinth.check(repo, http, modrinth.PACK_PROJECT, tmp_path / "dist", log=log.append), log


def test_check_passes_when_the_newest_version_is_this_one(repo, tmp_path):
    http = FakeModrinth([remote_version("V2", VERSION, built_pack(repo, tmp_path), "2026-10-01T00:00:00Z")])
    ok, log = check(repo, http, tmp_path)
    assert ok and "same pack" in log[0]


def test_check_passes_when_only_the_version_number_moved(repo, tmp_path):
    old = built_pack(repo, tmp_path, "1.9.0")
    ok, _ = check(repo, FakeModrinth([remote_version("V19", "1.9.0", old, "2026-09-01T00:00:00Z")], [old]), tmp_path)
    assert ok


def test_check_fails_when_the_pack_changed_since_the_newest_version(repo, tmp_path):
    old = built_pack(repo, tmp_path, "1.9.0")
    http = FakeModrinth([remote_version("V19", "1.9.0", old, "2026-09-01T00:00:00Z")], [old])
    (repo.client / "overrides" / "options.txt").write_text("renderDistance:8\n", encoding="utf-8")
    ok, log = check(repo, http, tmp_path)
    assert not ok and "isn't 2.0.0's" in log[0] and http.uploads == []


def test_check_fails_with_no_versions_and_passes_while_the_project_is_hidden(repo, tmp_path):
    assert check(repo, FakeModrinth(), tmp_path)[0] is False

    class Hidden(FakeModrinth):
        def request(self, method, url, body=None, content_type=None):
            raise NotFound(url)
    ok, log = check(repo, Hidden(), tmp_path)
    assert ok and "isn't public" in log[0]


def test_main_check_exits_1_when_behind_and_needs_no_token(repo, monkeypatch):
    monkeypatch.delenv(modrinth.TOKEN_ENV, raising=False)
    with pytest.raises(SystemExit) as stop:
        modrinth.main(["--check"], repo, http=FakeModrinth())
    assert stop.value.code == 1


def test_main_check_exits_2_when_modrinth_errors(repo, capsys):
    class Down(FakeModrinth):
        def request(self, method, url, body=None, content_type=None):
            raise SystemExit(f"Modrinth refused {method} {url}: 503 down")
    with pytest.raises(SystemExit) as stop:
        modrinth.main(["--check"], repo, http=Down())
    assert stop.value.code == 2 and "503" in capsys.readouterr().err


def test_a_check_without_a_token_sends_no_authorization(monkeypatch):
    sent = {}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    def urlopen(req, timeout):
        sent.update(req.headers)
        return Reply()
    monkeypatch.setattr(modrinth.urllib.request, "urlopen", urlopen)
    modrinth.ModrinthHttp("").request("GET", f"{MODRINTH}/project/x")
    assert "Authorization" not in sent

# --- the command line and the token -------------------------------------------------------------------------

def test_publishing_needs_the_token(repo, monkeypatch):
    monkeypatch.delenv(modrinth.TOKEN_ENV, raising=False)
    with pytest.raises(SystemExit, match=modrinth.TOKEN_ENV):
        modrinth.main([], repo)


def test_the_token_goes_only_to_modrinths_api():
    with pytest.raises(ValueError, match="only goes to Modrinth"):
        modrinth.ModrinthHttp("mrp_secret").request("GET", "https://example.com/upload")


def test_dry_run_prints_the_upload_without_a_token(repo, monkeypatch, capsys):
    monkeypatch.delenv(modrinth.TOKEN_ENV, raising=False)
    modrinth.main(["--dry-run"], repo)
    out = capsys.readouterr().out
    assert '"version_number": "2.0.0"' in out and "<id of monkeysmp>" in out
    assert (repo.dist / "TheRealms-Client-2.0.0.mrpack").is_file()


def test_main_refuses_a_checkout_that_is_not_the_release_tag(repo, monkeypatch):
    monkeypatch.setattr(modrinth, "release_checkout_problems", lambda root, version: ["HEAD isn't the tag v2.0.0"])
    with pytest.raises(SystemExit, match="not publishing: HEAD isn't the tag"):
        modrinth.main([], repo, http=FakeModrinth())


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   check=True, capture_output=True)


def test_release_checkout_problems(repo):
    root = repo.root
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "release")
    assert modrinth.release_checkout_problems(root, VERSION) == [
        "HEAD isn't the tag v2.0.0 (check it out first: git switch --detach v2.0.0)"]
    _git(root, "tag", "v2.0.0")
    assert modrinth.release_checkout_problems(root, VERSION) == []
    (repo.client / "overrides" / "options.txt").write_text("changed\n", encoding="utf-8")
    assert modrinth.release_checkout_problems(root, VERSION) == [
        "client/, CHANGELOG.md or the manifest has uncommitted changes"]
