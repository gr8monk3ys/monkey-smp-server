"""Build the release files into dist/.

  dist/TheRealms-Server-<version>.zip     unzip anywhere on Windows, double-click Start Server.bat
  dist/TheRealms-Client-<version>.mrpack  import into Prism Launcher / Modrinth App to play

Neither file contains third-party jars or datapacks: the server downloads them on first start
and the launcher downloads the client mods, both from their official sources.
"""
import json
import os
import zipfile
from pathlib import Path

from repo import REPO, load_json

TOP = "TheRealms-Server"
# Fixed timestamp so the same inputs give byte-identical zips.
EPOCH = (2026, 1, 1, 0, 0, 0)


def _add(z: zipfile.ZipFile, arcname: str, data: bytes) -> None:
    info = zipfile.ZipInfo(arcname, EPOCH)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    z.writestr(info, data)


def _walk(folder: Path):
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        for f in sorted(files):
            yield Path(root) / f


def build_server(version: str, repo=REPO, dist: Path | None = None) -> Path:
    out = Path(dist or repo.dist) / f"TheRealms-Server-{version}.zip"
    with zipfile.ZipFile(out, "w") as z:
        for path in _walk(repo.package):
            _add(z, f"{TOP}/{path.relative_to(repo.package).as_posix()}", path.read_bytes())
    return out


def build_client(version: str, repo=REPO, dist: Path | None = None) -> Path:
    index = load_json(repo.client / "modrinth.index.json")
    index["versionId"] = version
    out = Path(dist or repo.dist) / f"TheRealms-Client-{version}.mrpack"
    with zipfile.ZipFile(out, "w") as z:
        _add(z, "modrinth.index.json", json.dumps(index, indent=2, ensure_ascii=False).encode())
        for path in _walk(repo.client / "overrides"):
            _add(z, path.relative_to(repo.client).as_posix(), path.read_bytes())
    return out


def main(repo=REPO, dist: Path | None = None):
    version = repo.load_manifest()["version"]
    tag = os.environ.get("GITHUB_REF_NAME", "")
    if tag.startswith("v") and tag[1:] != version:
        raise SystemExit(f"tag {tag} doesn't match manifest version {version}")
    dist = Path(dist or repo.dist)
    dist.mkdir(parents=True, exist_ok=True)
    for path in (build_server(version, repo, dist), build_client(version, repo, dist)):
        print(f"{path}  {path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
