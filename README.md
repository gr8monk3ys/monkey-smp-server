# The Realms

[![CI](https://github.com/gr8monk3ys/the-realms-server/actions/workflows/ci.yml/badge.svg)](https://github.com/gr8monk3ys/the-realms-server/actions/workflows/ci.yml)

A Minecraft Java **factions server** with roleplay and PvP: towns, nations, alliances, land claims and
wars (Towns & Nations), on top of reworked terrain and structures (Terralith, Tectonic, Incendium,
Nullscape, Dungeons & Taverns and more). It is packaged so that **anyone can host it on Windows by
double-clicking one file**. No Java install, no command line, no port forwarding needed.

| | |
|---|---|
| Minecraft | Java Edition **26.1.2** |
| Server | [Paper](https://papermc.io) (build pinned in the manifest) |
| Plugins | 20: Towns & Nations, LuckPerms, EssentialsX, WorldGuard, CoreProtect, BlueMap, Simple Voice Chat, ... |
| Datapacks | 28 world-gen, structure, End-fight, corpse and Strength SMP packs |
| Client pack | 126 optional mods, resource packs and shaders (Fabric) |

## I just want to run it

1. Download **`TheRealms-Server-<version>.zip`** from the [latest release](https://github.com/gr8monk3ys/the-realms-server/releases/latest).
2. Unzip it somewhere permanent (e.g. Documents).
3. Double-click **`Start Server.bat`** and follow [`READ ME FIRST.txt`](package/READ%20ME%20FIRST.txt).

The first start downloads about 300 MB (Java, Paper, plugins, datapacks) straight from their official
sources and checks every file's SHA-256/512 hash before using it. It then asks you to agree to the
Minecraft EULA and for your Minecraft name, which becomes the admin.

Players: see [docs/PLAYERS.md](docs/PLAYERS.md). Admins: see [docs/ADMIN.md](docs/ADMIN.md).

## How it works

```
package/                    <- exactly what goes in the release zip
  Start Server.bat          <- double-click launchers for the host
  Stop Server.bat, Backup World.bat, Add Player.bat
  READ ME FIRST.txt         <- plain-language guide for the host
  realms/
    realms.ps1              <- entry script the launchers call (Windows PowerShell 5.1, built into Windows)
    Realms.psm1             <- the installer module: install, start/stop, backup, RCON (Pester-tested)
    manifest.json           <- every download, pinned by URL + size + hash
    defaults/               <- first-run configs (server.properties, Towns & Nations, WorldGuard, LuckPerms ranks)
    patches/                <- small fixes applied inside downloaded datapacks
client/                     <- source of the player modpack (.mrpack)
tools/                      <- maintainer scripts (Python, stdlib only)
tests/                      <- unit tests + end-to-end smoke test
```

- **Nothing third-party is committed or re-uploaded.** The release zip is ~40 KB of scripts and configs;
  jars and datapacks are fetched from Adoptium, PaperMC and Modrinth on the host's machine.
  That keeps the repo small and respects each project's license.
- **Installs are idempotent.** `realms.ps1 install` skips files that already match the manifest,
  replaces outdated ones, and removes plugins/datapacks that were dropped from the manifest.
  Config defaults are only copied when the file doesn't exist yet, so the host's edits are never overwritten.
- **The world seed is pinned**, so every copy generates the same terrain and the spawn safe zone lines up.
- **No secrets in the repo.** The RCON password is generated on each machine at first install.

## CI/CD

| Workflow | When | What |
|---|---|---|
| [CI](.github/workflows/ci.yml) | every push and PR | ruff + pytest + manifest validation, PSScriptAnalyzer, then **builds the release zip on a Windows runner, unzips it, installs, boots the server, checks every plugin is enabled and every datapack is active, and stops it** |
| [Release](.github/workflows/release.yml) | tag `v*.*.*` | runs CI, then publishes the server zip + client `.mrpack` as a GitHub release |
| [Check for updates](.github/workflows/updates.yml) | weekly | re-verifies every pinned download (and that each datapack patch still fits) and opens/updates an issue listing newer Paper/plugin/datapack builds |

## Maintaining

See [docs/MAINTAINING.md](docs/MAINTAINING.md): updating plugins, snapshotting a live server into the
manifest, cutting a release.

```bash
pip install pytest ruff
pytest -q && ruff check tools tests && python tools/validate.py
python tools/build.py          # -> dist/
```

## License

The scripts, configs and docs in this repo are MIT licensed (see [LICENSE](LICENSE)). Minecraft, Paper,
the plugins, datapacks, mods and shaders are separate projects under their own licenses; this repo only
links to them.
