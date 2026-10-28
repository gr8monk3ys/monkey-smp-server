"""Writes every generated data pack and checks that the committed ones match their generators.

    python tools/datapacks.py            # regenerate every pack
    python tools/datapacks.py --check    # fail if a committed pack is out of date (validate.py runs this)

A generator is a module in tools/ with `packs(repo)`: {pack folder: {path inside it: text or bytes}}. Each
folder is wholly generated, so a file in it that the generator no longer makes is reported (and removed by a
write). Two optional hooks: `files(repo)`, single generated files outside any pack folder ({path: text}), and
`after_write(repo)`, run once the files are written. Text files always end with one newline.

The helpers below are the ones every generator writes its commands and text with.
"""
import argparse
import importlib
import json
import re
import shutil
import sys
from pathlib import Path

from repo import REPO, Repo

MINECRAFT = "26.3"     # DATA_FORMAT is this version's; a test fails when the manifest moves on
DATA_FORMAT = 121
NS = "realms"
# challenges writes into wardrobe's
GENERATORS = ("events", "wardrobe", "npcs", "rules", "standings", "drops", "firsts")

# Objectives the generated packs read but another data pack or mod creates.
EXTERNAL_OBJECTIVES = {
    "Strength_SMP+Strength_Level": "the Strength SMP data pack",
    "Withdraw_Strength": "the Strength SMP data pack",
}


# ---------------------------------------------------------------- writing commands and text


def text(*parts) -> str:
    """A text component as compact JSON: one part as itself, several as a list."""
    value = parts[0] if len(parts) == 1 else list(parts)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def lines(*items) -> str:
    return "\n".join(items) + "\n"


def say(*parts) -> str:
    return "tellraw @s " + text(*parts)


def refuse(msg: str) -> str:
    return "return run " + say({"text": msg, "color": "red"})


def mcmeta(description: str, fmt: int = DATA_FORMAT) -> str:
    return json.dumps({"pack": {"description": description, "min_format": fmt, "max_format": fmt}}, indent=2) + "\n"


def function_tag(*functions: str) -> str:
    """minecraft:load or minecraft:tick's function tag."""
    return json.dumps({"values": list(functions)}, indent=2) + "\n"


# ---------------------------------------------------------------- the generators


def generators() -> dict[str, object]:
    return {name: importlib.import_module(name) for name in GENERATORS}


def outputs(gen, repo: Repo) -> dict[Path, bytes]:
    def data(v: str | bytes) -> bytes:
        if isinstance(v, bytes):
            return v
        return v.encode()
    out = {root / k: data(v) for root, files in gen.packs(repo).items() for k, v in files.items()}
    if hasattr(gen, "files"):
        out.update({p: data(v) for p, v in gen.files(repo).items()})
    return out


def differences(repo: Repo, gens=None) -> list[str]:
    """Files that differ from what the generators make, or that sit in a pack folder and aren't made."""
    diff = []
    for gen in (gens or generators().values()):
        want = outputs(gen, repo)
        have = {p for r in gen.packs(repo) if r.is_dir() for p in r.rglob("*") if p.is_file()}
        diff += [str(p.relative_to(repo.root)) for p, data in want.items()
                 if not p.is_file() or p.read_bytes() != data]
        diff += [str(p.relative_to(repo.root)) + " (not generated)" for p in have - set(want)]
    return sorted(diff)


def write(repo: Repo, gens=None) -> int:
    n = 0
    for gen in (gens or generators().values()):
        for root in gen.packs(repo):
            shutil.rmtree(root, ignore_errors=True)
        out = outputs(gen, repo)
        for path, data in out.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        n += len(out)
        if hasattr(gen, "after_write"):
            gen.after_write(repo)
    return n


# ---------------------------------------------------------------- checks across every pack


FUNCTION_FILE = re.compile(r"data/([\w.-]+)/function/(.+)\.mcfunction")
CALL = re.compile(r"\bfunction ([\w.-]+):([\w/$()]+)")
ADD_OBJECTIVE = re.compile(r"scoreboard objectives add (\S+)")
READS = (
    re.compile(r"\bscore (?:\S+) ([\w.+-]+) (?:matches|[<>=]{1,2})"),
    re.compile(r"\bscore \S+ [\w.+-]+ [<>=]{1,2} \S+ ([\w.+-]+)"),
    re.compile(r"\bstore (?:result|success) score \S+ ([\w.+-]+)"),
    re.compile(r"\bscoreboard players (?:set|add|remove|get|reset|enable|display \w+) (?:\S+) ([\w.+-]+)"),
    re.compile(r"\bscoreboard players operation \S+ ([\w.+-]+) \S+ \S+ ([\w.+-]+)"),
    re.compile(r'"objective": ?"([\w.+-]+)"'),
)
SCORES = re.compile(r"scores=\{([^}]*)\}")


def all_files(repo: Repo = REPO) -> dict[str, str]:
    """Every generated text file, keyed by its path inside its pack (the packs ship and load together)."""
    out = {}
    for gen in generators().values():
        for root, files in gen.packs(repo).items():
            for k, v in files.items():
                if isinstance(v, str):
                    out[f"{root.name}/{k}"] = v
    return out


def problems(files: dict[str, str]) -> list[str]:
    """What's wrong across the packs: calls to missing functions, unmarked macros, bad JSON, wrong formats,
    line endings, and objectives read that no pack creates."""
    errors = []
    defined = {f"{m[1]}:{m[2]}" for k in files if (m := FUNCTION_FILE.search(k))}
    created = set(EXTERNAL_OBJECTIVES)
    for body in files.values():
        for line in body.splitlines():
            if not line.lstrip().startswith("#"):
                created |= set(ADD_OBJECTIVE.findall(line))
    data_packs = {k.split("/", 1)[0] for k in files if k.split("/", 1)[1].startswith("data/")}
    for path, body in files.items():
        pack, name = path.split("/", 1)
        if "\r" in body or not body.endswith("\n"):
            errors.append(f"{path}: not LF line endings with a final newline")
        if name.endswith((".json", ".mcmeta")):
            try:
                data = json.loads(body)
            except ValueError as e:
                errors.append(f"{path}: {e}")
                continue
            if name == "pack.mcmeta" and pack in data_packs:
                fmt = data.get("pack", {}) if isinstance(data, dict) else {}
                if not fmt.get("min_format") == fmt.get("max_format") == DATA_FORMAT:
                    errors.append(f"{path}: format isn't {DATA_FORMAT}")
            if "tags/function/" in name:
                for v in data.get("values", []):
                    if v not in defined and not v.startswith("minecraft:"):
                        errors.append(f"{path} lists {v}, which no pack defines")
        elif not name.endswith(".mcfunction"):
            continue
        # .json files are scanned too: dialogs and text components run commands and show scores.
        for line in body.splitlines():
            if line.startswith("#"):
                continue
            if name.endswith(".mcfunction") and ("$(" in line) != line.startswith("$"):
                errors.append(f"{path}: macro marker: {line}")
            for ns, fn in CALL.findall(line):
                pattern = re.escape(f"{ns}:{fn}").replace(r"\$", "$")
                pattern = re.sub(r"\$\\\(\w+\\\)", r"[\\w/]+", pattern)
                if not any(re.fullmatch(pattern, d) for d in defined):
                    errors.append(f"{path} calls {ns}:{fn}, which no pack defines")
            for rx in READS:
                for m in rx.finditer(line):
                    for obj in m.groups():
                        if "$(" not in obj and obj not in created:
                            errors.append(f"{path} reads objective {obj}, which no pack creates")
            for selector in SCORES.findall(line):
                for obj in (part.split("=", 1)[0].strip() for part in selector.split(",") if part.strip()):
                    if "$(" not in obj and obj not in created:
                        errors.append(f"{path} reads objective {obj}, which no pack creates")
    return sorted(set(errors))


# ---------------------------------------------------------------- main


def main(argv=None, repo: Repo = REPO) -> int:
    ap = argparse.ArgumentParser(description="Builds every generated data pack.")
    ap.add_argument("--check", action="store_true", help="fail if a committed pack is out of date")
    args = ap.parse_args(argv)
    if args.check:
        diff = differences(repo)
        if diff:
            print("generated packs are out of date (run python tools/datapacks.py):\n  " + "\n  ".join(diff))
            return 1
        print("generated packs are up to date")
        return 0
    print(f"wrote {write(repo)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
