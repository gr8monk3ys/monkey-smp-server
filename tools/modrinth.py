"""Publish the client pack on Modrinth, and keep the Modrinth server listing on the newest version.

  python tools/modrinth.py --dry-run    build the .mrpack and print what would be uploaded (no token, no network)
  python tools/modrinth.py              upload it, then point the server listing at it (needs MODRINTH_TOKEN)
  python tools/modrinth.py --check      does Modrinth's newest version hold this checkout's pack? (exit 1 if not,
                                        2 if the check itself failed)

Run it from a clean checkout of the release tag, after the GitHub release (docs/MAINTAINING.md, "Releasing").
The token is a Modrinth personal access token with the scopes Read projects, Write projects, Read versions and
Create versions. It is read from the MODRINTH_TOKEN environment variable only (never a file in the repo or an
argument, so it stays out of git and shell history) and is sent to api.modrinth.com and nowhere else.

Every step checks before it acts, so a re-run after a failure picks up where it stopped:
  1. builds dist/MonkeySMP-Client-<version>.mrpack (the same bytes tools/build.py writes)
  2. reads the modpack project (--project) and its versions
  3. uploads the pack as version <version>, unless Modrinth already has that version with the same file, or
     the newest version holds the same pack apart from its version number (the deploy script's rule: a
     release that didn't touch client/ asks nothing of players); --force uploads it anyway
  4. points the server listing (--server) at the newest version, so the Modrinth App's linked instances
     update to it before they join; skipped while the server listing doesn't exist

The version's release notes are its `## [x.y.z]` section of CHANGELOG.md, as on the GitHub release.
Project setup, listing text and review: docs/MODRINTH.md.
"""
import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

import build
from repo import REPO, load_json
from upstream import MODRINTH, USER_AGENT

API_V3 = "https://api.modrinth.com/v3"
# The slugs the listings were created with (docs/MODRINTH.md). The modpack holds the versions; the server
# listing links to one of them. A server listing that carries its own pack is --project and --server at once.
PACK_PROJECT = "monkeysmp"
SERVER_PROJECT = "monkeysmp-server"
TOKEN_ENV = "MODRINTH_TOKEN"
TOKEN_SCOPES = "Read projects, Write projects, Read versions, Create versions"
# The pack index's loader dependency -> Modrinth's loader id.
LOADERS = {"fabric-loader": "fabric", "quilt-loader": "quilt", "forge": "forge", "neoforge": "neoforge"}


class NotFound(LookupError):
    pass


class ModrinthHttp:
    """api.modrinth.com with the token, plus anonymous downloads from Modrinth's CDN."""

    def __init__(self, token: str, timeout: float = 120):
        self.token = token
        self.timeout = timeout

    def request(self, method: str, url: str, body: bytes | None = None, content_type: str | None = None):
        """The JSON reply (None for 204 No Content). Raises NotFound for 404, SystemExit for other errors."""
        if not url.startswith(("https://api.modrinth.com/", "https://staging-api.modrinth.com/")):
            raise ValueError(f"the token only goes to Modrinth's API, not {url}")
        headers = {"User-Agent": USER_AGENT}
        if self.token:  # --check reads a public project without one
            headers["Authorization"] = self.token
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NotFound(url) from None
            raise SystemExit(f"Modrinth refused {method} {url}: {e.code} {_error_text(e.read())}") from None
        return json.loads(data) if data else None

    def download(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.read()


def _error_text(body: bytes) -> str:
    """Modrinth's {"error", "description"} reply as one line, or the raw body."""
    try:
        reply = json.loads(body)
        return f"{reply.get('error', '')}: {reply.get('description', '')}".strip(": ")
    except ValueError:
        return body.decode(errors="replace")[:500]


def changelog(repo, version: str) -> str:
    """The version's notes on Modrinth: its CHANGELOG.md section, as on the GitHub release."""
    return build.changelog_section((repo.root / "CHANGELOG.md").read_text(encoding="utf-8"), version)


def pack_contents(mrpack: bytes) -> dict[str, bytes]:
    """Every file in a .mrpack, with the index's versionId left out: what a player's install depends on."""
    z = zipfile.ZipFile(io.BytesIO(mrpack))
    files = {name: z.read(name) for name in z.namelist()}
    index = json.loads(files["modrinth.index.json"])
    index.pop("versionId", None)
    files["modrinth.index.json"] = json.dumps(index, sort_keys=True).encode()
    return files


def version_data(project_id: str, version: str, index: dict, filename: str, notes: str) -> dict:
    """The `data` part of Modrinth's create-version request (API v2) for one .mrpack."""
    deps = index["dependencies"]
    loaders = [LOADERS[dep] for dep in deps if dep in LOADERS]
    if not loaders:
        raise SystemExit(f"the pack index names no loader Modrinth knows ({', '.join(deps)})")
    return {
        "project_id": project_id,
        "name": f"Monkey SMP {version}",
        "version_number": version,
        "changelog": notes,
        "dependencies": [],
        "game_versions": [deps["minecraft"]],
        # A .mrpack with the pack's loader: Modrinth files it as a modpack ("mrpack") for that loader.
        "loaders": loaders,
        "version_type": "release",
        "featured": False,
        "status": "listed",
        "file_parts": [filename],
        "primary_file": filename,
    }


def multipart(data: dict, filename: str, payload: bytes, boundary: str) -> bytes:
    """multipart/form-data with the JSON `data` part and the file as a part named after itself."""
    return b"".join([
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="data"\r\nContent-Type: application/json\r\n\r\n',
        json.dumps(data).encode(), b"\r\n",
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{filename}"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: application/x-modrinth-modpack+zip\r\n\r\n",
        payload, b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])


def build_pack(repo, version: str, dist: Path | None = None) -> Path:
    dist = Path(dist or repo.dist)
    dist.mkdir(parents=True, exist_ok=True)
    return build.build_client(version, repo, dist)


def _primary_file(version: dict) -> dict:
    return next((f for f in version["files"] if f.get("primary")), version["files"][0])


def _newest(versions: list[dict]) -> dict | None:
    return max(versions, key=lambda v: v["date_published"], default=None)


def publish(repo, http, project: str, server: str | None, dist: Path | None = None, force: bool = False,
            log=print) -> str:
    """Upload this checkout's pack if Modrinth needs it and re-point the server listing; returns the version id."""
    version = repo.load_manifest()["version"]
    mrpack = build_pack(repo, version, dist)
    payload = mrpack.read_bytes()
    sha512 = hashlib.sha512(payload).hexdigest()
    project_id = http.request("GET", f"{MODRINTH}/project/{project}")["id"]
    versions = http.request("GET", f"{MODRINTH}/project/{project_id}/version")
    newest = _newest(versions)
    same = next((v for v in versions if v["version_number"] == version), None)
    if same:
        if _primary_file(same)["hashes"]["sha512"] != sha512:
            raise SystemExit(f"Modrinth already has {version} with a different file. A version's file can't be "
                             "replaced: release a new version instead.")
        log(f"{project} {version} is already on Modrinth ({same['id']})")
        target = same
    elif newest and not force and pack_contents(http.download(_primary_file(newest)["url"])) == pack_contents(payload):
        log(f"the pack is the same as {project} {newest['version_number']} apart from its version number: "
            "nothing to upload (--force uploads it anyway)")
        target = newest
    else:
        index = load_json(repo.client / "modrinth.index.json")
        data = version_data(project_id, version, index, mrpack.name, changelog(repo, version))
        boundary = uuid.uuid4().hex
        body = multipart(data, mrpack.name, payload, boundary)
        target = http.request("POST", f"{MODRINTH}/version", body, f"multipart/form-data; boundary={boundary}")
        log(f"uploaded {mrpack.name} to {project} as {version} ({target['id']})")
        newest = target
    if server:
        if target["id"] != newest["id"]:
            log(f"{version} isn't {project}'s newest version ({newest['version_number']}): "
                "the server listing stays put")
        else:
            point_server(http, server, target["id"], log)
    return target["id"]


def check(repo, http, project: str, dist: Path | None = None, log=print) -> bool:
    """Whether Modrinth's newest version holds this checkout's pack (its version number aside), so players who
    install from Modrinth get what the server expects. A project Modrinth doesn't show (still under review, and
    no token) has nothing to compare yet: that passes, with a note."""
    version = repo.load_manifest()["version"]
    try:
        project_id = http.request("GET", f"{MODRINTH}/project/{project}")["id"]
    except NotFound:
        log(f"{project} isn't public on Modrinth yet (under review?): nothing to compare. "
            f"With {TOKEN_ENV} set, the check reads it anyway")
        return True
    newest = _newest(http.request("GET", f"{MODRINTH}/project/{project_id}/version"))
    if newest is None:
        log(f"{project} has no versions on Modrinth: publish {version} with tools/modrinth.py")
        return False
    payload = build_pack(repo, version, dist).read_bytes()   # built only when there is something to compare
    if (_primary_file(newest)["hashes"]["sha512"] == hashlib.sha512(payload).hexdigest()
            or pack_contents(http.download(_primary_file(newest)["url"])) == pack_contents(payload)):
        log(f"{project} {newest['version_number']} on Modrinth holds the same pack as {version}")
        return True
    log(f"{project}'s newest version on Modrinth is {newest['version_number']}, and its pack isn't {version}'s: "
        f"publish it with tools/modrinth.py from the tag v{version} (docs/MODRINTH.md)")
    return False


def point_server(http, server: str, version_id: str, log=print) -> None:
    """Make the server listing's linked modpack `version_id` (API v3; other server settings stay as they are)."""
    try:
        listing = http.request("GET", f"{API_V3}/project/{server}")
    except NotFound:
        log(f"no server listing '{server}' on Modrinth yet: skipped (docs/MODRINTH.md)")
        return
    content = (listing.get("minecraft_java_server") or {}).get("content") or {}
    if content.get("version_id") == version_id:
        log(f"the server listing '{server}' already links {version_id}")
        return
    edit = {"minecraft_java_server": {"content": {"kind": "modpack", "version_id": version_id}}}
    http.request("PATCH", f"{API_V3}/project/{listing['id']}", json.dumps(edit).encode(), "application/json")
    log(f"the server listing '{server}' now links {version_id}")


def release_checkout_problems(root: Path, version: str) -> list[str]:
    """Why this checkout isn't the release tag's pack (empty list = it is); what Modrinth gets can't be replaced."""
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)

    problems = []
    tagged = git("tag", "--points-at", "HEAD").stdout.split()
    if f"v{version}" not in tagged:
        problems.append(f"HEAD isn't the tag v{version} (check it out first: git switch --detach v{version})")
    if git("status", "--porcelain", "--", "client", "CHANGELOG.md", "package/monkey/manifest.json").stdout.strip():
        problems.append("client/, CHANGELOG.md or the manifest has uncommitted changes")
    return problems


def main(argv=None, repo=REPO, http=None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--project", default=PACK_PROJECT, help=f"modpack project slug or id (default {PACK_PROJECT})")
    p.add_argument("--server", default=SERVER_PROJECT,
                   help=f"server listing slug or id to point at the new version (default {SERVER_PROJECT}; '' skips)")
    p.add_argument("--dry-run", action="store_true", help="build and print the upload; no token, no network")
    p.add_argument("--force", action="store_true", help="upload even if the newest version holds the same pack")
    p.add_argument("--check", action="store_true",
                   help="exit 1 unless Modrinth's newest version holds this checkout's pack; token optional")
    p.add_argument("--any-checkout", action="store_true", help="skip the check that HEAD is the release tag")
    args = p.parse_args(argv)
    version = repo.load_manifest()["version"]
    if args.dry_run:
        mrpack = build_pack(repo, version)
        data = version_data(f"<id of {args.project}>", version, load_json(repo.client / "modrinth.index.json"),
                            mrpack.name, changelog(repo, version))
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"{mrpack}  {mrpack.stat().st_size / 1e6:.1f} MB")
        return
    if args.check:
        # Exit 2 when the check itself failed (Modrinth down, a bad token): that isn't "Modrinth is behind".
        try:
            ok = check(repo, http or ModrinthHttp(os.environ.get(TOKEN_ENV, "").strip()), args.project)
        except (SystemExit, OSError) as e:
            print(f"the check failed: {e.code if isinstance(e, SystemExit) else e}", file=sys.stderr)
            raise SystemExit(2) from None
        raise SystemExit(0 if ok else 1)
    if http is None:
        token = os.environ.get(TOKEN_ENV, "").strip()
        if not token:
            raise SystemExit(f"set {TOKEN_ENV} to a Modrinth personal access token ({TOKEN_SCOPES}); "
                             "see docs/MODRINTH.md")
        http = ModrinthHttp(token)
    if not args.any_checkout and (problems := release_checkout_problems(repo.root, version)):
        raise SystemExit("not publishing: " + "; ".join(problems))
    publish(repo, http, args.project, args.server or None)


if __name__ == "__main__":
    sys.exit(main())
