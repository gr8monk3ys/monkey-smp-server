"""Shared test fixtures. Tests never touch the network or write into the real checkout.

Sample manifests are FROZEN copies of real releases (tests/fixtures/manifests/<name>/: manifest.json,
its patches/ and a trimmed client modrinth.index.json), never whatever the repo pins today:
  paper-1.1.0   the last Paper release (a 1.x manifest: no "mods" group), one patched datapack
  fabric-2.0.0  the first Fabric release: 112 mods, two of them patched
Only test_validate.py::test_real_repo_is_valid looks at the real manifest, package and client.
Neither frozen release had a client/fabric-profile.json or a player/ folder; frozen_repo adds a profile
(derived from the recorded one) and tests that build the player zip add a fake player/ (fake_player).
"""
import copy
import hashlib
import io
import shutil
import zipfile
from pathlib import Path

import pytest

import entries
from repo import REPO, Repo, load_json, save_json
from upstream import MODRINTH, PAPER, RecordedHttp, fabric_profile_url, fabric_server_jar_url, json_query

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "upstream"
MANIFESTS = Path(__file__).resolve().parent / "fixtures" / "manifests"
PAPER_RELEASE, FABRIC_RELEASE = "paper-1.1.0", "fabric-2.0.0"
# The launcher profile recorded from Fabric meta (tests/fixtures/record.py).
RECORDED_PROFILE_MC, RECORDED_PROFILE_LOADER = "26.3", "0.19.5"
PLAYER_FILES = {
    "Install for Minecraft Launcher.bat": "@echo off\r\npowershell -File installer\\install-client.ps1\r\n",
    "READ ME.txt": "Double-click Install for Minecraft Launcher.bat\r\n",
    "installer/install-client.ps1": "Import-Module (Join-Path $PSScriptRoot PlayerInstall.psm1)\r\n",
    "installer/PlayerInstall.psm1": "function Install-Client { }\r\n",
}


@pytest.fixture
def recorded() -> RecordedHttp:
    """Responses recorded once from the live APIs (tests/fixtures/record.py)."""
    return RecordedHttp.from_folder(FIXTURES)


def frozen_manifest(name: str) -> dict:
    """A frozen release manifest as the tools read it (every group present)."""
    return entries.with_all_groups(load_json(MANIFESTS / name / "manifest.json"))


def frozen_repo(root: Path, name: str) -> Repo:
    """A throwaway repo holding a frozen release: its manifest.json, patches/ and client index, plus
    today's package files (launchers, scripts, defaults), which the release's manifest doesn't pin."""
    frozen = MANIFESTS / name

    def skip_pins(folder, names):
        return {"manifest.json", "patches"} if Path(folder) == REPO.realms else set()

    shutil.copytree(REPO.package, root / "package", ignore=skip_pins)
    repo = Repo(root)
    shutil.copy2(frozen / "manifest.json", repo.manifest)
    shutil.copytree(frozen / "patches", repo.patches)
    (repo.client / "overrides").mkdir(parents=True)
    index = load_json(frozen / "modrinth.index.json")
    save_json(repo.client / "modrinth.index.json", index)
    save_json(repo.fabric_profile, fabric_profile(index["dependencies"]["minecraft"],
                                                  index["dependencies"]["fabric-loader"]))
    return repo


def fabric_profile(mc: str, loader: str) -> dict:
    """Fabric meta's launcher profile for `mc` + `loader`: the recorded one, re-labelled for other versions."""
    recorded = RecordedHttp.from_folder(FIXTURES).get_json(
        fabric_profile_url(RECORDED_PROFILE_MC, RECORDED_PROFILE_LOADER))
    profile = copy.deepcopy(recorded)
    profile.update(id=f"fabric-loader-{loader}-{mc}", inheritsFrom=mc)
    for lib in profile["libraries"]:
        if lib["name"] == f"net.fabricmc:fabric-loader:{RECORDED_PROFILE_LOADER}":
            lib["name"] = f"net.fabricmc:fabric-loader:{loader}"
    return profile


def fake_player(repo: Repo, files: dict[str, str] | None = None) -> dict[str, bytes]:
    """A stand-in for the player installer in `repo`/player/; returns {relative path: bytes}."""
    written = {}
    for name, text in (PLAYER_FILES if files is None else files).items():
        path = repo.player / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
        written[name] = text.encode()
    return written


@pytest.fixture
def paper_manifest() -> dict:
    return frozen_manifest(PAPER_RELEASE)


@pytest.fixture
def fabric_manifest() -> dict:
    return frozen_manifest(FABRIC_RELEASE)


@pytest.fixture
def paper_repo(tmp_path) -> Repo:
    return frozen_repo(tmp_path / PAPER_RELEASE, PAPER_RELEASE)


@pytest.fixture
def fabric_repo(tmp_path) -> Repo:
    return frozen_repo(tmp_path / FABRIC_RELEASE, FABRIC_RELEASE)


def patched_entry(manifest: dict) -> tuple[str, dict]:
    """(kind, entry) of the first patched mod or datapack."""
    return next((k, e) for k in entries.PATCHABLE for e in entries.group(manifest, k) if "patch" in e)


def make_zip(files: dict[str, bytes | str]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return out.getvalue()


def zip_contents(data: bytes) -> dict[str, bytes]:
    z = zipfile.ZipFile(io.BytesIO(data))
    return {n: z.read(n) for n in z.namelist()}


class FakeModrinth:
    """Builds Modrinth responses for files a test made, keyed by their real hashes."""

    def __init__(self, http: RecordedHttp):
        self.http = http
        self.versions: dict[str, dict] = {}  # sha1 -> version
        self.slugs: dict[str, str] = {}      # project id -> slug

    def publish(self, data: bytes, slug: str, filename: str, version="1.0") -> dict:
        sha1 = hashlib.sha1(data).hexdigest()
        project_id = f"id-{slug}"
        version_id = f"v-{slug}-{version}"
        self.slugs[project_id] = slug
        self.versions[sha1] = {
            "id": version_id, "project_id": project_id, "version_number": version, "version_type": "release",
            "date_published": "2026-01-01T00:00:00Z",
            "files": [{"filename": filename, "primary": True, "size": len(data),
                       "url": f"https://cdn.modrinth.com/data/{project_id}/versions/{version_id}/{filename}",
                       "hashes": {"sha1": sha1, "sha512": hashlib.sha512(data).hexdigest()}}],
        }
        return self.versions[sha1]

    def expect_lookup(self, *sent: bytes) -> None:
        """Answer the snapshot's one SHA-1 lookup for exactly these files (known or not)."""
        sha1s = sorted({hashlib.sha1(d).hexdigest() for d in sent})
        known = {h: self.versions[h] for h in sha1s if h in self.versions}
        self.http.add("POST", f"{MODRINTH}/version_files", known, body={"hashes": sha1s, "algorithm": "sha1"})
        ids = sorted({v["project_id"] for v in known.values()})
        if ids:
            self.http.add("GET", f"{MODRINTH}/projects?ids={json_query(ids)}",
                          [{"id": i, "slug": self.slugs[i]} for i in ids])


@pytest.fixture
def fake_modrinth() -> FakeModrinth:
    return FakeModrinth(RecordedHttp())


def paper_build(build_id: int, jar: bytes, channel="STABLE") -> dict:
    sha256 = hashlib.sha256(jar).hexdigest()
    name = f"paper-26.1.2-{build_id}.jar"
    return {"id": build_id, "channel": channel, "downloads": {"server:default": {
        "name": name, "size": len(jar), "checksums": {"sha256": sha256},
        "url": f"https://fill-data.papermc.io/v1/objects/{sha256}/{name}"}}}


def paper_builds_url(mc: str) -> str:
    return f"{PAPER}/versions/{mc}/builds"


def fabric_launcher(mc: str, loader: str, installer: str, salt: bytes = b"") -> bytes:
    """A tiny jar shaped like Fabric meta's server launcher (install.properties + MANIFEST.MF)."""
    manifest_mf = ("Manifest-Version: 1.0\r\nImplementation-Title: FabricInstaller\r\n"
                   f"Implementation-Version: {installer}\r\nMain-Class: net.fabricmc.installer.ServerLauncher\r\n\r\n")
    return make_zip({
        "META-INF/MANIFEST.MF": manifest_mf,
        "install.properties": f"fabric-loader-version={loader}\ngame-version={mc}\n",
        "net/fabricmc/installer/ServerLauncher.class": b"\xca\xfe\xba\xbe" + salt,
    })


def serve_fabric_launcher(http: RecordedHttp, mc: str, loader: str, installer: str, jar: bytes | None = None) -> bytes:
    """Serve a launcher jar at Fabric meta's URL for these versions; returns its bytes."""
    jar = jar if jar is not None else fabric_launcher(mc, loader, installer)
    http.add("GET", fabric_server_jar_url(mc, loader, installer), jar)
    return jar
