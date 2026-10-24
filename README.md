# Monkey SMP

[![CI](https://github.com/gr8monk3ys/monkey-smp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/gr8monk3ys/monkey-smp-server/actions/workflows/ci.yml)

A modded Minecraft Java **factions server** with PvP and roleplay: parties, alliances and land claims,
reworked terrain (Tectonic, Terralith), new structures, mobs and magic. It is packaged so that
**anyone can host it from one download on Windows, macOS or Linux** (double-click on Windows), run it
**with Docker**, or **put it on an online Minecraft host** with one upload. No Java install and no port
forwarding needed.

| | |
|---|---|
| Minecraft | Java Edition **26.3** |
| Server | [Fabric](https://fabricmc.net) (loader pinned in the manifest) |
| Server mods | 142: Open Parties and Claims, LuckPerms, Ledger, BlueMap, Simple Voice Chat, Tectonic, Terralith, Incendium, Nullscape, Moog's structures, Epic Dungeons, Grand Capitals, Naturalist, Variants & Ventures, Strength SMP, C2ME, ... |
| Client pack | 213 mods, resource packs and shaders (required to join) |
| Players | about 10 at full speed on a 2017 desktop CPU, 25 on a current fast one ([measured](docs/ADMIN.md#how-many-players)) |

1.x releases were a Paper 26.1.2 server with Towns & Nations; see [ADR-0005](docs/adr/0005-fabric-with-the-full-mod-list.md).

## Downloads: who gets what

Every [release](https://github.com/gr8monk3ys/monkey-smp-server/releases/latest) has three small files.
[docs/SHARING.md](docs/SHARING.md) has copy-paste messages to send with them.

| File | For | |
|---|---|---|
| `TheRealms-Server-<version>.zip` | the **host** | run the server on Windows, macOS or Linux (or with Docker), or prepare it for an online host |
| `TheRealms-Player-<version>.zip` | every **player** on Windows | double-click `Install for Minecraft Launcher.bat`, then pick "Monkey SMP" in the normal Minecraft Launcher |
| `TheRealms-Client-<version>.mrpack` | players on **macOS/Linux**, or using the Modrinth App or Prism | import it into Prism Launcher or the Modrinth App (it's also inside the player zip) |

## Run it on your own computer (Windows, macOS, Linux)

Download **`TheRealms-Server-<version>.zip`** from the [latest release](https://github.com/gr8monk3ys/monkey-smp-server/releases/latest)
and unzip it somewhere permanent (e.g. Documents). The computer needs 16 GB of RAM or more (12 GB is enough for a few players).

| | Start | Stop |
|---|---|---|
| **Windows** 10/11 | double-click **`Start Server.bat`** | type `stop` in its window, or `Stop Server.bat` |
| **macOS** (Intel or Apple Silicon) | double-click **`Start Server.command`** (first time: right-click > Open), or `sh start.sh` in Terminal | type `stop`, or `sh stop.sh` |
| **Linux** (x64 or arm64) | `sh start.sh` in the folder | type `stop`, or `sh stop.sh` |

Then follow [`READ ME FIRST.txt`](package/READ%20ME%20FIRST.txt). The other launchers come in pairs too:
`Add Player.bat` / `sh add-player.sh NAME`, `Backup World.bat` / `sh backup.sh`,
`Prepare for Hosting.bat` / `sh prepare-for-hosting.sh`.

The first start downloads about 500 MB (Java for your system, the Fabric launcher, 142 mods) straight
from their official sources and checks every file's SHA-256/512 hash before using it. It then asks you
to agree to the Minecraft EULA and for your Minecraft name, which becomes the admin. Friends join through
[playit.gg](https://playit.gg) (steps in the READ ME).

On macOS and Linux the `.sh` launchers run the same installer as Windows, under PowerShell 7: if `pwsh`
isn't installed they first download a pinned, hash-checked portable copy from Microsoft (about 70 MB)
into the folder. Besides that they only need `curl` (or `wget`), `tar` and `sha256sum` (or `shasum`),
which every Mac and nearly every Linux has ([ADR-0007](docs/adr/0007-one-installer-on-every-platform.md)).

## Run it with Docker

On a Linux VPS, or anything else with Docker:

```sh
unzip TheRealms-Server-<version>.zip
cd TheRealms-Server/docker
# in .env: EULA=TRUE and OWNER=<your Minecraft name>, optionally MEMORY_GB=6
docker compose up -d
docker compose logs -f      # watch it start (Ctrl+C stops watching, not the server)
docker compose down         # stop it; the world is saved
```

The image holds no Minecraft, Java or mods. The release folder is mounted into the container, and the
same installer downloads everything into it on first start, so the world and `backups/` live in that
folder exactly as with a native run. Open 25565/tcp (game) and 24454/udp (voice chat) in the firewall.

## Run it online (hosting company or VPS)

- **Your own Linux VPS:** run the release on it directly, natively (`sh start.sh` inside `screen` or
  `tmux`) or with Docker as above. No bundle needed.
- **Minecraft hosts** (Shockbyte, Apex, BisectHosting, any Pterodactyl panel) only take a finished server:
  1. Unzip the release on your computer and run **`Prepare for Hosting.bat`** (Windows) or
     `sh prepare-for-hosting.sh` (macOS, Linux).
  2. It installs everything as above, then writes `exports/TheRealms-<version>-hosting.zip`: the finished
     server plus `start.sh`, `start.bat`, `docker-compose.yml` and `HOSTING.txt`.
  3. Extract that zip into the panel's server root, pick the Fabric launcher jar and Java 25, start.
     `HOSTING.txt` inside has the step-by-step.

The bundle is built from the official downloads on your own computer, so nothing is redistributed
([ADR-0006](docs/adr/0006-online-hosting-via-a-bundle-built-on-the-hosts-pc.md)).

## Play on it

Players need the mods (the server adds blocks, mobs and items). On **Windows**, unzip
`TheRealms-Player-<version>.zip` and double-click **`Install for Minecraft Launcher.bat`**: it installs
Fabric and every mod, resource pack and shader into a separate folder (downloaded from Modrinth, each
file hash-checked) and adds a **Monkey SMP** installation to the normal Minecraft Launcher. On **macOS
and Linux**, players import the `.mrpack` into [Prism Launcher](https://prismlauncher.org) or the
[Modrinth App](https://modrinth.com/app) instead (so can Windows players who already use one). Step by step: [docs/PLAYERS.md](docs/PLAYERS.md).

Admins: [docs/ADMIN.md](docs/ADMIN.md).

## How it works

```
package/                    <- exactly what goes in the release zip
  Start Server.bat          <- double-click launchers for a Windows host
  Stop Server.bat, Backup World.bat, Add Player.bat, Prepare for Hosting.bat
  start.sh, stop.sh, backup.sh, add-player.sh, prepare-for-hosting.sh   <- the same for macOS/Linux
  Start Server.command      <- double-click launcher for macOS (runs start.sh)
  READ ME FIRST.txt         <- plain-language guide for the host
  docker/                   <- Dockerfile + compose.yaml that run this folder in a container
  realms/
    realms.ps1              <- entry script every launcher ends up in (Windows PowerShell 5.1 or PowerShell 7)
    realms.sh               <- macOS/Linux bootstrap: finds or downloads pwsh, then runs realms.ps1
    Realms.psm1             <- the installer module: install, start/stop, backup, RCON, hosting export
    manifest.json           <- every download, pinned by URL + size + hash (Java once per platform)
    pwsh.lock               <- the portable PowerShell 7 builds realms.sh may download, pinned the same way
    defaults/               <- first-run configs (server.properties, server icon, LuckPerms ranks, Tectonic, BlueMap)
    patches/                <- small fixes applied inside downloaded mods
player/                     <- the player zip: Install for Minecraft Launcher.bat, READ ME.txt, installer
client/                     <- source of the player modpack (.mrpack) + the pinned Fabric launcher profile
tools/                      <- maintainer scripts (Python, stdlib only)
tests/                      <- pytest + Pester unit tests, smoke tests (Windows, Linux, macOS, Docker)
```

- **Nothing third-party is committed or re-uploaded.** The release zip is ~100 KB of scripts and configs;
  jars are fetched from Adoptium, Fabric and Modrinth (and PowerShell from Microsoft) on the host's machine ([ADR-0002](docs/adr/0002-download-and-verify-instead-of-redistributing.md)).
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
| [CI](.github/workflows/ci.yml) | every push and PR | ruff + pytest + manifest validation; PSScriptAnalyzer + Pester; on **Windows**: build the release zip, unzip, export a hosting bundle, install, boot the server, check every mod loads, stop; on **Linux**: the same boot natively with `start.sh` (PowerShell bootstrap included), the release folder with `docker compose`, and the hosting bundle with `docker compose`, each checked to start and shut down cleanly |
| [CI](.github/workflows/ci.yml) on **macOS** | releases and manual runs | boots the release natively on macOS (left out of pushes and PRs: macOS runners are slow and scarce) |
| [Release](.github/workflows/release.yml) | tag `v*.*.*` | runs CI (including macOS), then publishes the server zip, player zip and client `.mrpack` as a GitHub release |
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
