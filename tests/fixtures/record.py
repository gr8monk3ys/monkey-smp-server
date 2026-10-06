"""Re-record the upstream fixtures the tests replay (tests/fixtures/upstream/*.json).

  python tests/fixtures/record.py

Runs a fixed set of catalog calls against the live APIs through RecordingHttp, which trims each
response to the fields the tools read. Only needed when an upstream API changes shape or a test
needs a new request; the tests themselves never touch the network. Re-recording can change which
versions are newest, so run the tests afterwards and adjust them if needed.
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from check_updates import LOADERS  # noqa: E402
from snapshot import JAVA_MAJOR  # noqa: E402
from upstream import JAVA_PLATFORMS, LiveHttp, RecordingHttp, Upstream, version_key  # noqa: E402

FOLDER = Path(__file__).resolve().parent / "upstream"
MC = "26.1.2"
MC_FABRIC = "26.3"  # Fabric meta: loader and installer lists (the launcher jar itself is built in tests)
LOADER = "0.19.5"   # ...and the launcher profile for MC_FABRIC + this loader (the client pack's)
# Projects with several stable releases for MC, so tests can pin an older one and see an update.
PROJECTS = {
    "Vebnzrzj": "plugin",    # LuckPerms: the jar name changes with every version
    "zJhgi9nK": "datapack",  # Silver's Inventory Library: file name changed, plus an alpha
    "wBo7DRiB": "datapack",  # Silver's Custom Effects Library: patched in the real manifest
}


def main():
    shutil.rmtree(FOLDER, ignore_errors=True)
    up = Upstream(RecordingHttp(LiveHttp(), FOLDER))
    up.paper_builds(MC)
    for platform in JAVA_PLATFORMS:
        release = up.adoptium_latest_jre(JAVA_MAJOR, platform)["release_name"]
        up.adoptium_release_jre(release, platform)
    lts = max(up.powershell_lts_tags(), key=version_key)
    up.powershell_release_assets(lts)
    up.fabric_loaders(MC_FABRIC)
    up.fabric_installers()
    up.fabric_profile(MC_FABRIC, LOADER)
    sha1s = []
    for project_id, kind in PROJECTS.items():
        newest = up.newest_release(project_id, MC, LOADERS[kind])
        sha1s.append(newest["files"][0]["hashes"]["sha1"])
    found = up.modrinth_versions_by_sha1(sha1s)
    up.modrinth_projects(v["project_id"] for v in found.values())
    print(f"recorded {len(list(FOLDER.glob('*.json')))} responses into {FOLDER}")


if __name__ == "__main__":
    main()
