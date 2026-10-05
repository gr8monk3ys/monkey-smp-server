"""Shared helpers for the maintainer tools (stdlib only)."""
import hashlib
import json
import os
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "package")
REALMS = os.path.join(PACKAGE, "realms")
MANIFEST = os.path.join(REALMS, "manifest.json")
CLIENT = os.path.join(ROOT, "client")
UA = {"User-Agent": "gr8monk3ys/the-realms-server (github.com/gr8monk3ys/the-realms-server)"}
MODRINTH = "https://api.modrinth.com/v2"


def http_json(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {**UA, **({"Content-Type": "application/json"} if data else {})}
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=60) as r:
        return json.load(r)


def http_bytes(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read()


def q(value):
    return urllib.parse.quote(json.dumps(value))


def digest(data, algo):
    return hashlib.new(algo, data).hexdigest()


def load_manifest(path=MANIFEST):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest, path=MANIFEST):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")


def artifacts(manifest):
    """Every downloadable file in the manifest as (kind, entry)."""
    yield "java", manifest["java"]
    yield "server", manifest["server"]
    for p in manifest["plugins"]:
        yield "plugin", p
    for d in manifest["datapacks"]:
        yield "datapack", d


def hash_of(entry):
    """(algorithm, hex) of the strongest hash an entry carries."""
    for algo in ("sha512", "sha256"):
        if algo in entry["hashes"]:
            return algo, entry["hashes"][algo]
    raise KeyError(f"{entry['file']} has no sha512/sha256")
