"""Re-record tests/fixtures/client_mods.json: facts about every mod jar in the client pack.

  python -I tests/fixtures/record_client_mods.py [--jars FOLDER]

For each mods/ file in client/modrinth.index.json this reads the jar's fabric.mod.json (and those of the
jars nested inside it) and counts the block, item and entity assets it ships, and asks Modrinth whether
the project calls its client and server halves required, optional or unsupported. tests/test_client_env.py
checks tools/client_env.py against these facts. Run it after the client pack gains a mod (the tests say
so); version bumps don't need it.

Jars are downloaded from the index's Modrinth CDN URLs and checked against its sha512, or read from
--jars FOLDER when a file of that name and hash is there. They are only unzipped in memory, never run.
"""
import argparse
import contextlib
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import client_env  # noqa: E402
from repo import REPO, load_json  # noqa: E402
from upstream import LiveHttp, Upstream  # noqa: E402

OUT = Path(__file__).resolve().parent / "client_mods.json"
BUILTIN = {"minecraft", "java", "fabricloader", "mixinextras"}  # what Fabric Loader itself provides
CONTENT = {
    "blockstates": re.compile(r"assets/[^/]+/blockstates/.+\.json$"),
    "items": re.compile(r"assets/[^/]+/items/.+\.json$"),
    "entity_textures": re.compile(r"assets/[^/]+/textures/entity/.+"),
}


def fabric_mod_json(raw: bytes) -> dict:
    text = raw.decode("utf-8-sig", "replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:  # a few mods put raw newlines inside strings
        return json.loads(re.sub(r"[\x00-\x1f]", " ", text))


def jar_mods(z: zipfile.ZipFile) -> list[dict]:
    """fabric.mod.json of a jar and of every jar nested in it (jar-in-jar), depth first."""
    if "fabric.mod.json" not in z.namelist():
        return []
    fm = fabric_mod_json(z.read("fabric.mod.json"))
    mods = [fm]
    for nested in fm.get("jars") or []:
        with contextlib.suppress(KeyError, zipfile.BadZipFile):  # a listed jar that isn't there
            mods += jar_mods(zipfile.ZipFile(io.BytesIO(z.read(nested["file"]))))
    return mods


def has_code(z: zipfile.ZipFile) -> bool:
    """Any class file in the jar or a jar nested in it (a datapack packaged as a mod has none)."""
    for n in z.namelist():
        if n.endswith(".class"):
            return True
        if n.endswith(".jar"):
            with contextlib.suppress(zipfile.BadZipFile):
                if has_code(zipfile.ZipFile(io.BytesIO(z.read(n)))):
                    return True
    return False


def jar_facts(data: bytes) -> dict:
    z = zipfile.ZipFile(io.BytesIO(data))
    mods = jar_mods(z)
    if not mods:
        raise ValueError("no fabric.mod.json")
    names = z.namelist()
    ids = set()
    depends = set()
    for m in mods:
        ids.add(m["id"])
        ids.update(p if isinstance(p, str) else p["id"] for p in m.get("provides") or [])
        depends.update(m.get("depends") or {})
    return {
        "id": mods[0]["id"],
        "environment": mods[0].get("environment", "*"),
        "ids": sorted(ids),
        "depends": sorted(depends - BUILTIN - ids),
        "code": has_code(z),
        **{k: sum(1 for n in names if rx.match(n)) for k, rx in CONTENT.items()},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jars", type=Path, help="folder of already-downloaded jars to read first")
    args = ap.parse_args(argv)
    up = Upstream(LiveHttp())
    index = load_json(REPO.client / "modrinth.index.json")
    files = [f for f in index["files"] if f["path"].startswith("mods/")]
    projects = up.modrinth_projects(client_env.project_id(f) for f in files)
    facts = {}
    for f in files:
        name = f["path"].split("/", 1)[1]
        local = args.jars / name if args.jars else None
        data = local.read_bytes() if local and local.is_file() else None
        if data is None or hashlib.sha512(data).hexdigest() != f["hashes"]["sha512"]:
            data = up.download(f["downloads"][0])
            if hashlib.sha512(data).hexdigest() != f["hashes"]["sha512"]:
                raise SystemExit(f"{f['path']}: download doesn't match the index's sha512")
        pid = client_env.project_id(f)
        p = projects[pid]
        facts[pid] = {"slug": p["slug"], "modrinth": {"client": p["client_side"], "server": p["server_side"]},
                      **jar_facts(data)}
    OUT.write_text(json.dumps(dict(sorted(facts.items())), indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"recorded {len(facts)} mods into {OUT}")


if __name__ == "__main__":
    main()
