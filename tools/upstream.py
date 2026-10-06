"""The Upstream catalog: what Modrinth, PaperMC, Fabric meta, Adoptium and PowerShell say about artifacts.

  Upstream(http)                                   the catalog, over an HTTP adapter
    .modrinth_versions_by_sha1(sha1s)              {sha1: version} for files Modrinth knows
    .modrinth_projects(ids)                        {project id: project}
    .modrinth_versions(project_id, mc, loaders)    every version of a project for a Minecraft version
    .newest_release(project_id, mc, loaders)       newest stable ("release") version, or None
    .paper_builds(mc)                              every Paper build for a Minecraft version
    .newest_stable_paper_build(mc)                 the highest STABLE build id, or None
    .fabric_loaders(mc)                            every Fabric loader for a Minecraft version
    .newest_stable_fabric_loader(mc)               the highest stable loader version, or None
    .fabric_installers()                           every Fabric installer (= server launcher) version
    .newest_stable_fabric_installer()              the highest stable installer version, or None
    .fabric_profile(mc, loader)                    Fabric meta's launcher profile JSON for a client
    .adoptium_latest_jre(major, platform)          newest Temurin JRE for a Java major on one platform
    .adoptium_release_jre(release, platform)       one Temurin JRE release on one platform (to re-check pins)
    .powershell_lts_tags()                         the PowerShell release tags that are LTS ("v7.6.6", ...)
    .powershell_release_assets(tag)                {file name: {"url", "size", "sha256"}} of one release
    .download(url)                                 the bytes at a URL

Platforms are the installer's ids (JAVA_PLATFORMS): windows-x64, linux-x64, linux-aarch64, mac-x64 and
mac-aarch64, which are Adoptium's os-architecture names.

The seam is the HTTP adapter (get_json, post_json, get_bytes):
  LiveHttp       the real internet (urllib, our User-Agent, timeouts)
  RecordedHttp   serves recorded responses keyed by method + URL + body, and raises
                 UnrecordedRequest for anything else; built from a dict or from a fixtures folder
  RecordingHttp  wraps another adapter and saves each JSON response (trimmed to the fields the
                 catalog reads) into a fixtures folder; used by tests/fixtures/record.py
"""
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

MODRINTH = "https://api.modrinth.com/v2"
PAPER = "https://fill.papermc.io/v3/projects/paper"
ADOPTIUM = "https://api.adoptium.net/v3"
POWERSHELL_METADATA = "https://raw.githubusercontent.com/PowerShell/PowerShell/master/tools/metadata.json"
POWERSHELL_RELEASES = "https://api.github.com/repos/PowerShell/PowerShell/releases"
FABRIC_META = "https://meta.fabricmc.net/v2"
USER_AGENT = "gr8monk3ys/the-realms-server (github.com/gr8monk3ys/the-realms-server)"


# The platforms the installer runs on, as Adoptium's (os, architecture).
JAVA_PLATFORMS = {
    "windows-x64": ("windows", "x64"),
    "linux-x64": ("linux", "x64"),
    "linux-aarch64": ("linux", "aarch64"),
    "mac-x64": ("mac", "x64"),
    "mac-aarch64": ("mac", "aarch64"),
}


def json_query(value) -> str:
    return urllib.parse.quote(json.dumps(value))


def fabric_server_jar_url(mc: str, loader: str, installer: str) -> str:
    """Fabric meta's server launcher jar for one Minecraft, loader and installer version.

    The jar is generated, but deterministically: the same three versions always give the same bytes,
    so a manifest can pin its size and hash like any other download.
    """
    return f"{FABRIC_META}/versions/loader/{mc}/{loader}/{installer}/server/jar"


def fabric_profile_url(mc: str, loader: str) -> str:
    """Fabric meta's launcher profile (a versions/<id>/<id>.json for the official Minecraft Launcher)."""
    return f"{FABRIC_META}/versions/loader/{mc}/{loader}/profile/json"


def version_key(version: str) -> tuple[int, ...]:
    """Sort key for dotted versions such as Fabric's 0.19.5 (build metadata after '+' ignored)."""
    return tuple(int(n) for n in re.findall(r"\d+", version.split("+")[0]))


class Upstream:
    def __init__(self, http):
        self.http = http

    def modrinth_versions_by_sha1(self, sha1s) -> dict[str, dict]:
        hashes = sorted(set(sha1s))
        if not hashes:
            return {}
        return self.http.post_json(f"{MODRINTH}/version_files", {"hashes": hashes, "algorithm": "sha1"})

    def modrinth_projects(self, ids) -> dict[str, dict]:
        ids = sorted(set(ids))
        if not ids:
            return {}
        return {p["id"]: p for p in self.http.get_json(f"{MODRINTH}/projects?ids={json_query(ids)}")}

    def modrinth_versions(self, project_id: str, mc: str, loaders) -> list[dict]:
        """Every version of a project for one Minecraft version and loader set (any channel)."""
        query = f"game_versions={json_query([mc])}&loaders={json_query(list(loaders))}"
        return self.http.get_json(f"{MODRINTH}/project/{project_id}/version?{query}")

    def newest_release(self, project_id: str, mc: str, loaders) -> dict | None:
        releases = [v for v in self.modrinth_versions(project_id, mc, loaders) if v["version_type"] == "release"]
        return max(releases, key=lambda v: v["date_published"]) if releases else None

    def paper_builds(self, mc: str) -> list[dict]:
        return self.http.get_json(f"{PAPER}/versions/{mc}/builds")

    def newest_stable_paper_build(self, mc: str) -> dict | None:
        # The API happens to list newest first today; don't depend on it.
        stable = [b for b in self.paper_builds(mc) if b.get("channel") == "STABLE"]
        return max(stable, key=lambda b: b["id"]) if stable else None

    def fabric_loaders(self, mc: str) -> list[dict]:
        """[{"version": "0.19.5", "stable": True}, ...] for the loaders Fabric meta lists for `mc`."""
        return [item["loader"] for item in self.http.get_json(f"{FABRIC_META}/versions/loader/{mc}")]

    def newest_stable_fabric_loader(self, mc: str) -> str | None:
        return _newest_stable(self.fabric_loaders(mc))

    def fabric_installers(self) -> list[dict]:
        """[{"version": "1.1.2", "stable": True}, ...]; the installer version is the launcher's version."""
        return self.http.get_json(f"{FABRIC_META}/versions/installer")

    def newest_stable_fabric_installer(self) -> str | None:
        return _newest_stable(self.fabric_installers())

    def fabric_profile(self, mc: str, loader: str) -> dict:
        """The launcher profile for Fabric `loader` on Minecraft `mc` (see tools/launcher_profile.py)."""
        return self.http.get_json(fabric_profile_url(mc, loader))

    def adoptium_latest_jre(self, major: int, platform: str = "windows-x64") -> dict:
        """{"release_name", "binary": {"package": {name, link, size, checksum}}} of the newest JRE."""
        os_, arch = JAVA_PLATFORMS[platform]
        assets = self.http.get_json(
            f"{ADOPTIUM}/assets/latest/{major}/hotspot?os={os_}&architecture={arch}&image_type=jre")
        if not assets:
            raise LookupError(f"Adoptium has no {platform} JRE for Java {major}")
        return assets[0]

    def adoptium_release_jre(self, release_name: str, platform: str) -> dict:
        """The same shape as adoptium_latest_jre, for one named release (e.g. jdk-25.0.4.1+1)."""
        os_, arch = JAVA_PLATFORMS[platform]
        release = self.http.get_json(
            f"{ADOPTIUM}/assets/release_name/eclipse/{urllib.parse.quote(release_name, safe='')}"
            f"?os={os_}&architecture={arch}&image_type=jre&jvm_impl=hotspot&project=jdk")
        binaries = release.get("binaries") or []
        if not binaries:
            raise LookupError(f"Adoptium has no {platform} JRE in {release_name}")
        return {"release_name": release["release_name"], "binary": binaries[0]}

    def powershell_lts_tags(self) -> list[str]:
        """The release tags PowerShell's own build metadata marks as LTS (several majors may be)."""
        tags = self.http.get_json(POWERSHELL_METADATA)["LTSReleaseTag"]
        return [tags] if isinstance(tags, str) else list(tags)

    def powershell_release_assets(self, tag: str) -> dict[str, dict]:
        """{file name: {"url", "size", "sha256"}}; GitHub computes each asset's sha256 digest itself."""
        release = self.http.get_json(f"{POWERSHELL_RELEASES}/tags/{tag}")
        out = {}
        for a in release["assets"]:
            digest = a.get("digest") or ""
            if digest.startswith("sha256:"):
                out[a["name"]] = {"url": a["browser_download_url"], "size": a["size"], "sha256": digest[7:]}
        return out

    def download(self, url: str) -> bytes:
        return self.http.get_bytes(url)


def _newest_stable(versions: list[dict]) -> str | None:
    # Fabric meta lists newest first today; don't depend on it.
    stable = [v["version"] for v in versions if v.get("stable")]
    return max(stable, key=version_key) if stable else None


# --- adapters -----------------------------------------------------------------------------------

class LiveHttp:
    def __init__(self, timeout_json: float = 60, timeout_download: float = 300):
        self.timeout_json = timeout_json
        self.timeout_download = timeout_download

    def _open(self, url, data=None, headers=None, timeout=60):
        req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
        return urllib.request.urlopen(req, timeout=timeout)

    def get_json(self, url):
        with self._open(url, timeout=self.timeout_json) as r:
            return json.load(r)

    def post_json(self, url, body):
        with self._open(url, json.dumps(body).encode(), {"Content-Type": "application/json"},
                        self.timeout_json) as r:
            return json.load(r)

    def get_bytes(self, url):
        with self._open(url, timeout=self.timeout_download) as r:
            return r.read()


def request_key(method: str, url: str, body=None) -> str:
    """Deterministic identity of a request: method, URL and (canonical JSON) body."""
    key = f"{method.upper()} {url}"
    if body is not None:
        key += " " + json.dumps(body, sort_keys=True, separators=(",", ":"))
    return key


class UnrecordedRequest(LookupError):
    pass


class RecordedHttp:
    """Serves recorded responses. `responses` maps request_key(...) to a JSON value (or bytes)."""

    def __init__(self, responses: dict | None = None):
        self.responses = dict(responses or {})

    @classmethod
    def from_folder(cls, folder) -> "RecordedHttp":
        responses = {}
        for path in sorted(Path(folder).glob("*.json")):
            rec = json.loads(path.read_text(encoding="utf-8"))
            r = rec["request"]
            responses[request_key(r["method"], r["url"], r.get("body"))] = rec["response"]
        return cls(responses)

    def add(self, method: str, url: str, response, body=None) -> "RecordedHttp":
        self.responses[request_key(method, url, body)] = response
        return self

    def _serve(self, key):
        if key not in self.responses:
            raise UnrecordedRequest(f"no recorded response for {key}\n"
                                    "(record it with `python tests/fixtures/record.py` or add it to the test)")
        return self.responses[key]

    def get_json(self, url):
        return self._serve(request_key("GET", url))

    def post_json(self, url, body):
        return self._serve(request_key("POST", url, body))

    def get_bytes(self, url):
        data = self._serve(request_key("GET", url))
        if not isinstance(data, bytes):
            raise UnrecordedRequest(f"recorded response for GET {url} is JSON, not a download")
        return data


class RecordingHttp:
    """Passes requests to `inner` and saves each JSON response, trimmed, into `folder`."""

    def __init__(self, inner, folder):
        self.inner = inner
        self.folder = Path(folder)

    def _save(self, method, url, body, response):
        response = trim(url, response)
        key = request_key(method, url, body)
        tail = re.sub(r"[^a-z0-9]+", "-", urllib.parse.urlsplit(url).path.lower()).strip("-")[-50:]
        name = f"{method.lower()}-{tail}-{hashlib.sha256(key.encode()).hexdigest()[:10]}.json"
        request = {"method": method, "url": url, **({"body": body} if body is not None else {})}
        self.folder.mkdir(parents=True, exist_ok=True)
        with open(self.folder / name, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"request": request, "response": response}, f, indent=1, ensure_ascii=False)
            f.write("\n")
        return response

    def get_json(self, url):
        return self._save("GET", url, None, self.inner.get_json(url))

    def post_json(self, url, body):
        return self._save("POST", url, body, self.inner.post_json(url, body))

    def get_bytes(self, url):
        return self.inner.get_bytes(url)


# --- fixture trimming: keep only what the catalog and entries.py read -----------------------------

KEEP_LIST_ITEMS = 5


def _pick(d: dict, *keys) -> dict:
    return {k: d[k] for k in keys if k in d}


def _version(v: dict) -> dict:
    out = _pick(v, "id", "project_id", "version_number", "version_type", "date_published")
    out["files"] = [{**_pick(f, "filename", "url", "size", "primary"),
                     "hashes": _pick(f["hashes"], "sha1", "sha512")} for f in v["files"]]
    return out


def trim(url: str, response):
    """A recorded response cut down to the fields the tools use (and lists to a few newest items)."""
    if url.startswith(f"{MODRINTH}/version_files"):
        return {h: _version(v) for h, v in response.items()}
    if url.startswith(f"{MODRINTH}/projects"):
        return [_pick(p, "id", "slug") for p in response]
    if url.startswith(f"{MODRINTH}/project/"):
        newest = sorted(response, key=lambda v: v["date_published"], reverse=True)[:KEEP_LIST_ITEMS]
        return [_version(v) for v in newest]
    if url.startswith(PAPER):
        newest = sorted(response, key=lambda b: b["id"], reverse=True)[:KEEP_LIST_ITEMS]
        return [{**_pick(b, "id", "channel"), "downloads": {"server:default": {
            **_pick(b["downloads"]["server:default"], "name", "url", "size"),
            "checksums": _pick(b["downloads"]["server:default"]["checksums"], "sha256")}}} for b in newest]
    if url.startswith(f"{FABRIC_META}/versions/loader/") and url.endswith("/profile/json"):
        return response  # small, and stored whole: the launcher reads all of it
    if url.startswith(f"{FABRIC_META}/versions/loader/"):
        newest = sorted(response, key=lambda x: version_key(x["loader"]["version"]), reverse=True)[:KEEP_LIST_ITEMS]
        return [{"loader": _pick(x["loader"], "version", "stable")} for x in newest]
    if url.startswith(f"{FABRIC_META}/versions/installer"):
        newest = sorted(response, key=lambda x: version_key(x["version"]), reverse=True)[:KEEP_LIST_ITEMS]
        return [_pick(x, "version", "stable") for x in newest]
    if url.startswith(f"{ADOPTIUM}/assets/release_name/"):
        return {"release_name": response["release_name"],
                "binaries": [{"package": _pick(b["package"], "name", "link", "size", "checksum")}
                             for b in response["binaries"]]}
    if url.startswith(ADOPTIUM):
        return [{"release_name": a["release_name"],
                 "binary": {"package": _pick(a["binary"]["package"], "name", "link", "size", "checksum")}}
                for a in response]
    if url == POWERSHELL_METADATA:
        return _pick(response, "LTSReleaseTag", "StableReleaseTag")
    if url.startswith(POWERSHELL_RELEASES):
        return {"tag_name": response["tag_name"],
                "assets": [_pick(a, "name", "browser_download_url", "size", "digest") for a in response["assets"]
                           if a["name"].endswith(".tar.gz")]}
    return response
