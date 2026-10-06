# The Realms

[![CI](https://github.com/gr8monk3ys/the-realms-server/actions/workflows/ci.yml/badge.svg)](https://github.com/gr8monk3ys/the-realms-server/actions/workflows/ci.yml)

A modded Minecraft Java **factions server** with PvP and roleplay: parties, alliances and land claims,
reworked terrain (Tectonic, Terralith), new structures, mobs and magic. It is packaged so that
**anyone can host it by double-clicking one file on Windows**, or **put it on an online host or VPS**
with one upload. No Java install, no command line, no port forwarding needed.

| | |
|---|---|
| Minecraft | Java Edition **26.3** |
| Server | [Fabric](https://fabricmc.net) (loader pinned in the manifest) |
| Server mods | 112: Open Parties and Claims, LuckPerms, Ledger, BlueMap, Simple Voice Chat, Tectonic, Terralith, Incendium, Nullscape, Moog's structures, Dungeons and Taverns, Naturalist, Variants & Ventures, Strength SMP, C2ME, ... |
| Client pack | 167 mods, resource packs and shaders (required to join) |

1.x releases were a Paper 26.1.2 server with Towns & Nations; see [ADR-0005](docs/adr/0005-fabric-with-the-full-mod-list.md).

## Downloads: who gets what

Every [release](https://github.com/gr8monk3ys/the-realms-server/releases/latest) has three small files.
[docs/SHARING.md](docs/SHARING.md) has copy-paste messages to send with them.

| File | For | |
|---|---|---|
| `TheRealms-Server-<version>.zip` | the **host** | run the server on a PC, or prepare it for an online host |
| `TheRealms-Player-<version>.zip` | every **player** | double-click `Install for Minecraft Launcher.bat`, then pick "The Realms" in the normal Minecraft Launcher |
| `TheRealms-Client-<version>.mrpack` | players using the Modrinth App or Prism | import it (it's also inside the player zip) |

## Run it on your own PC (Windows)

1. Download **`TheRealms-Server-<version>.zip`** from the [latest release](https://github.com/gr8monk3ys/the-realms-server/releases/latest).
2. Unzip it somewhere permanent (e.g. Documents).
3. Double-click **`Start Server.bat`** and follow [`READ ME FIRST.txt`](package/READ%20ME%20FIRST.txt).

The first start downloads about 500 MB (Java, the Fabric launcher, 112 mods) straight from their
official sources and checks every file's SHA-256/512 hash before using it. It then asks you to agree to
the Minecraft EULA and for your Minecraft name, which becomes the admin. Friends join through
[playit.gg](https://playit.gg) (steps in the READ ME).

## Run it online (hosting company or VPS)

1. Unzip the release on a Windows PC and double-click **`Prepare for Hosting.bat`**.
2. It installs everything as above, then writes `exports\TheRealms-<version>-hosting.zip`: the finished
   server plus `start.sh`, `start.bat`, `docker-compose.yml` and `HOSTING.txt`.
3. Upload that zip:
   - **Minecraft hosts** (Shockbyte, Apex, BisectHosting, any Pterodactyl panel): extract it into the
     server root, pick the Fabric launcher jar and Java 25, start.
   - **Your own Linux VPS:** `docker compose up -d` (or install Java 25 and run `sh start.sh`).

`HOSTING.txt` inside the zip has the step-by-step for each. The bundle is built from the official
downloads on your own PC, so nothing is redistributed ([ADR-0006](docs/adr/0006-online-hosting-via-a-bundle-built-on-the-hosts-pc.md)).

## Play on it

Players need the mods (the server adds blocks, mobs and items). Unzip `TheRealms-Player-<version>.zip` and
double-click **`Install for Minecraft Launcher.bat`**: it installs Fabric and every mod, resource pack and
shader into a separate folder (downloaded from Modrinth, each file hash-checked) and adds a
**The Realms** installation to the normal Minecraft Launcher. Modrinth App and Prism users import the
`.mrpack` instead. Step by step: [docs/PLAYERS.md](docs/PLAYERS.md).

Admins: [docs/ADMIN.md](docs/ADMIN.md).

## How it works

```
package/                    <- exactly what goes in the release zip
  Start Server.bat          <- double-click launchers for the host
  Stop Server.bat, Backup World.bat, Add Player.bat, Prepare for Hosting.bat
  READ ME FIRST.txt         <- plain-language guide for the host
  realms/
    realms.ps1              <- entry script the launchers call (Windows PowerShell 5.1, built into Windows)
    Realms.psm1             <- the installer module: install, start/stop, backup, RCON, hosting export
    manifest.json           <- every download, pinned by URL + size + hash
    defaults/               <- first-run configs (server.properties, LuckPerms ranks, Tectonic, BlueMap)
    patches/                <- small fixes applied inside downloaded mods
player/                     <- the player zip: Install for Minecraft Launcher.bat, READ ME.txt, installer
client/                     <- source of the player modpack (.mrpack) + the pinned Fabric launcher profile
tools/                      <- maintainer scripts (Python, stdlib only)
tests/                      <- pytest + Pester unit tests, Windows smoke test, Docker hosting test
```

- **Nothing third-party is committed or re-uploaded.** The release zip is ~100 KB of scripts and configs;
  jars are fetched from Adoptium, Fabric and Modrinth on the host's machine ([ADR-0002](docs/adr/0002-download-and-verify-instead-of-redistributing.md)).
- **Installs are idempotent.** `realms.ps1 install` skips files that already match the manifest,
  replaces outdated ones, and removes mods that were dropped from the manifest. Config defaults are only
  copied when the file doesn't exist yet, so the host's edits are never overwritten.
- **The world seed is pinned**, so every copy (local or hosted) generates the same terrain.
- **No secrets in the repo.** The RCON password is generated on each machine at first install.
- **The installer understands both Fabric and Paper manifests**, and refuses to install a release over a
  world from the other kind.

## CI/CD

| Workflow | When | What |
|---|---|---|
| [CI](.github/workflows/ci.yml) | every push and PR | ruff + pytest + manifest validation; PSScriptAnalyzer + Pester; on **Windows**: build the release zip, unzip, export a hosting bundle, install, boot the server, check every mod loads, stop; on **Linux**: boot that hosting bundle with `docker compose` and check it starts and shuts down cleanly |
| [Release](.github/workflows/release.yml) | tag `v*.*.*` | runs CI, then publishes the server zip + client `.mrpack` as a GitHub release |
| [Check for updates](.github/workflows/updates.yml) | weekly | re-verifies every pinned download (and that each patch still fits) and opens/updates an issue listing newer Fabric/mod builds |

## Maintaining

See [docs/MAINTAINING.md](docs/MAINTAINING.md): updating mods, snapshotting a live server into the
manifest, cutting a release. Domain terms are in [GLOSSARY.md](GLOSSARY.md), decisions in [docs/adr/](docs/adr/).

```bash
pip install pytest ruff
python -m pytest -q && python -m ruff check tools tests && python tools/validate.py
python tools/build.py          # -> dist/
```

## License

The scripts, configs and docs in this repo are MIT licensed (see [LICENSE](LICENSE)). Minecraft, Fabric,
the mods, datapacks, resource packs and shaders are separate projects under their own licenses; this repo
only links to them.
