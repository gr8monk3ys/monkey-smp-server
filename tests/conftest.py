"""Shared test fixtures. Tests never touch the network or write into the real checkout."""
import hashlib
import io
import shutil
import zipfile
from pathlib import Path

import pytest

from repo import REPO, Repo
from upstream import MODRINTH, PAPER, RecordedHttp, json_query

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "upstream"


@pytest.fixture
def recorded() -> RecordedHttp:
    """Responses recorded once from the live APIs (tests/fixtures/record.py)."""
    return RecordedHttp.from_folder(FIXTURES)


@pytest.fixture
def real_manifest() -> dict:
    return REPO.load_manifest()


@pytest.fixture
def repo_copy(tmp_path) -> Repo:
    """A throwaway copy of the repo's package/ and client/ to run tools against."""
    root = tmp_path / "repo"
    shutil.copytree(REPO.package, root / "package")
    shutil.copytree(REPO.client, root / "client")
    return Repo(root)


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
