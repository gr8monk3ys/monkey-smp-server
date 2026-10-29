"""Where things live in a checkout of this repo.

Every tool takes a `Repo` instead of reading module-level path constants, so tests can point a tool at
a temporary copy and never write into the real checkout. `REPO` is the checkout this file lives in;
command-line entry points use it.
"""
import json
from dataclasses import dataclass
from pathlib import Path

import entries


@dataclass(frozen=True)
class Repo:
    root: Path

    @property
    def package(self) -> Path:
        """Exactly what ships in the server package zip."""
        return self.root / "package"

    @property
    def monkey(self) -> Path:
        return self.package / "monkey"

    @property
    def manifest(self) -> Path:
        return self.monkey / "manifest.json"

    @property
    def pwsh_lock(self) -> Path:
        """The portable PowerShell monkey.sh installs on Linux and macOS (see pwsh_lock.py)."""
        return self.monkey / "pwsh.lock"

    @property
    def patches(self) -> Path:
        return self.monkey / "patches"

    @property
    def defaults(self) -> Path:
        return self.monkey / "defaults"

    @property
    def client(self) -> Path:
        """Source of the client pack (modrinth.index.json + overrides/)."""
        return self.root / "client"

    @property
    def fabric_profile(self) -> Path:
        """Fabric meta's launcher profile for the client pack's Minecraft + loader (see launcher_profile.py)."""
        return self.client / "fabric-profile.json"

    @property
    def player(self) -> Path:
        """The player installer (for the official Minecraft Launcher); the player zip ships all of it."""
        return self.root / "player"

    @property
    def dist(self) -> Path:
        return self.root / "dist"

    def load_manifest(self) -> dict:
        """The manifest, with every group present (a 1.x manifest has no "mods"; it reads as [])."""
        return entries.with_all_groups(load_json(self.manifest))

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
