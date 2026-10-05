"""Where things live in a checkout of this repo.

Every tool takes a `Repo` instead of reading module-level path constants, so tests can point a tool at
a temporary copy and never write into the real checkout. `REPO` is the checkout this file lives in;
command-line entry points use it.
"""
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Repo:
    root: Path

    @property
    def package(self) -> Path:
        """Exactly what ships in the server package zip."""
        return self.root / "package"

    @property
    def realms(self) -> Path:
        return self.package / "realms"

    @property
    def manifest(self) -> Path:
        return self.realms / "manifest.json"

    @property
    def patches(self) -> Path:
        return self.realms / "patches"

    @property
    def defaults(self) -> Path:
        return self.realms / "defaults"

    @property
    def client(self) -> Path:
        """Source of the client pack (modrinth.index.json + overrides/)."""
        return self.root / "client"

    @property
    def dist(self) -> Path:
        return self.root / "dist"

    def load_manifest(self) -> dict:
        return load_json(self.manifest)

    def save_manifest(self, manifest: dict) -> None:
        save_json(self.manifest, manifest)


REPO = Repo(Path(__file__).resolve().parent.parent)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data) -> None:
    """Write JSON the way the repo stores it: 2-space indent, UTF-8, LF, trailing newline."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
