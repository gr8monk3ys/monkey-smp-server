"""Build the release files into dist/.

  dist/TheRealms-Server-<version>.zip     unzip anywhere on Windows, double-click Start Server.bat
  dist/TheRealms-Client-<version>.mrpack  import into Prism Launcher / Modrinth App to play

Neither file contains third-party jars or datapacks: the server downloads them on first start
and the launcher downloads the client mods, both from their official sources.
"""
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CLIENT, PACKAGE, ROOT, load_manifest  # noqa: E402

DIST = os.path.join(ROOT, "dist")
TOP = "TheRealms-Server"
# Fixed timestamp so the same inputs give byte-identical zips.
EPOCH = (2026, 1, 1, 0, 0, 0)


def add(z, path, arcname):
    info = zipfile.ZipInfo(arcname, EPOCH)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    with open(path, "rb") as f:
        z.writestr(info, f.read())


def walk(folder):
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        for f in sorted(files):
            yield os.path.join(root, f)


def build_server(version):
    out = os.path.join(DIST, f"TheRealms-Server-{version}.zip")
    with zipfile.ZipFile(out, "w") as z:
        for path in walk(PACKAGE):
            rel = os.path.relpath(path, PACKAGE).replace("\\", "/")
            add(z, path, f"{TOP}/{rel}")
    return out


def build_client(version):
    index = json.load(open(os.path.join(CLIENT, "modrinth.index.json"), encoding="utf-8"))
    index["versionId"] = version
    out = os.path.join(DIST, f"TheRealms-Client-{version}.mrpack")
    with zipfile.ZipFile(out, "w") as z:
        info = zipfile.ZipInfo("modrinth.index.json", EPOCH)
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, json.dumps(index, indent=2, ensure_ascii=False))
        for path in walk(os.path.join(CLIENT, "overrides")):
            add(z, path, os.path.relpath(path, CLIENT).replace("\\", "/"))
    return out


def main():
    version = load_manifest()["version"]
    tag = os.environ.get("GITHUB_REF_NAME", "")
    if tag.startswith("v") and tag[1:] != version:
        raise SystemExit(f"tag {tag} doesn't match manifest version {version}")
    os.makedirs(DIST, exist_ok=True)
    for path in (build_server(version), build_client(version)):
        print(f"{path}  {os.path.getsize(path) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
