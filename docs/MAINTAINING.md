# Maintaining the pack

Tools are plain Python 3.11+ with no dependencies (tests use `pytest`, lint uses `ruff`).

## Where things live

| Path | What | Edited by |
|---|---|---|
| `package/realms/manifest.json` | pinned Java (one build per platform), server (Paper or Fabric), plugins or mods, datapacks | `tools/snapshot.py`, `tools/add.py`, `tools/check_updates.py --apply` |
| `package/realms/pwsh.lock` | the portable PowerShell 7 build per platform that `realms.sh` downloads when `pwsh` is missing | by hand (see below) |
| `package/*.bat`, `package/*.sh`, `package/Start Server.command`, `package/realms/realms.sh` | the host's launchers: `.bat` for Windows, POSIX `sh` for macOS/Linux | by hand |
| `package/docker/` | the Docker setup (`Dockerfile`, `compose.yaml`) | by hand |
| `package/realms/defaults/` | first-run configs, copied only if missing | by hand |
| `package/realms/patches/<slug>/` | files replaced inside a downloaded mod jar or datapack | `tools/snapshot.py` |
| `client/` | the player modpack (`modrinth.index.json` + `overrides/`) | `tools/snapshot.py client` |
| `client/fabric-profile.json` | Fabric meta's launcher profile for the client pack's Minecraft + loader | `tools/snapshot.py client` or `profile` |
| `player/` | the player installer for the official Minecraft Launcher (shipped whole in the player zip) | by hand |
| `tests/fixtures/upstream/` | API responses the unit tests replay | `tests/fixtures/record.py` |

The command-line tools (`snapshot`, `check_updates`, `validate`, `build`) are thin; the knowledge
lives in a few modules they share:

| Module | Owns |
|---|---|
| `tools/entries.py` | the manifest entry shape, server types and which groups they use, the `file` naming rule, entry validation, hash choice |
| `tools/patches.py` | making, storing, applying and checking patches |
| `tools/upstream.py` | the Upstream catalog (Modrinth, PaperMC, Fabric meta, Adoptium) behind a swappable HTTP adapter |
| `tools/defaults.py` | the `{{TOKEN}}` placeholders the installer fills into `defaults/server.properties` |
| `tools/launcher_profile.py` | the Fabric launcher profile: its expected id, checks, and comparing profiles while ignoring their generation time |
| `tools/repo.py` | where things live in the repo (tools take a `Repo`, so tests can use a temp copy) |

## Server types: Paper or Fabric

The manifest's `server.type` says which server software runs, and that decides which groups it may use:

| `server.type` | Pinned server download | Runs | Must be empty |
|---|---|---|---|
| `paper` | the Paper build's jar (`build`) | `plugins` + `datapacks` | `mods` |
| `fabric` | Fabric meta's server launcher for `minecraft` + `loader` + `installer` | `mods` + `datapacks` | `plugins` |

All three groups are written to every manifest; a 1.x manifest without `mods` still reads, validates
and builds (the group counts as empty). The Fabric launcher URL is
`https://meta.fabricmc.net/v2/versions/loader/<minecraft>/<loader>/<installer>/server/jar`. Meta
generates that jar, but the same three versions always give the same bytes, so its size and sha256
are pinned like any other download. On first start the launcher fetches the loader and the vanilla
server itself.

## Platforms: Java and PowerShell pins

One installer (`realms.ps1` + `Realms.psm1`) runs everywhere: on Windows PowerShell 5.1, and on
PowerShell 7 on macOS and Linux, where `realms/realms.sh` starts it (ADR-0007). Two kinds of pins
depend on the platform:

| Pin | Where | Platforms |
|---|---|---|
| Java (Eclipse Temurin JRE from Adoptium) | `manifest.json` `java`, one build per platform, each with URL + size + hash | Windows x64 (`.zip`), Linux x64 and aarch64, macOS x64 and aarch64 (`.tar.gz`) |
| PowerShell 7 (portable, from `PowerShell/PowerShell` GitHub releases) | `realms/pwsh.lock`, one line per platform: URL + SHA-256 | Linux x64 and arm64, macOS x64 and arm64 (`.tar.gz`); Windows uses its built-in 5.1 |

`pwsh.lock` is a plain-text file, not JSON, because `realms.sh` reads it with POSIX `sh` before any
PowerShell exists. Bump Java for every platform at once (same release on each), and PowerShell only
when needed (a security fix, or a feature the installer starts using). After changing either, run
`python tools/validate.py --online`, which downloads and hash-checks every pin, then let CI boot it on
each platform. On macOS that means starting CI by hand (see Tests).

The installer code must keep working on both PowerShell 5.1 and 7, and stay plain ASCII (ADR-0003):
put Windows-only calls (CIM, robocopy, `\` paths, `java.exe`) behind a platform check. The `.sh`
launchers are POSIX `sh` (Debian's `dash` and macOS's `sh` must both run them) with LF line endings.

## Updating the server, plugins and mods

```bash
python tools/check_updates.py            # what's newer (same Minecraft version, stable only)
python tools/check_updates.py --apply    # pin them
python tools/add.py datapack <slug>...    # add new Modrinth projects at their newest stable build
python tools/add.py mod <slug>...         # (Fabric) ...or mods; `plugin` on Paper
python tools/validate.py --online        # download + hash-check everything
```

An update has to be a stable release with a different file, published after the pinned version, so a
re-listed file (same jar, new version id) or a newer pre-release pin is never "updated" backwards.
Plugins are looked up with the Paper-family loaders and mods with the `fabric` loader, both for the
manifest's Minecraft version. For a Fabric server, a newer stable loader for that Minecraft version
and/or a newer stable installer is one server update; `--apply` downloads the new launcher from meta
to pin its size and hash. `add.py` refuses a kind the server type doesn't run (mods on Paper,
plugins on Fabric).

Patched mods and datapacks are the exception: `check_updates.py` lists a newer release as
"patched - re-snapshot needed" and `--apply` leaves its pin alone, because the patch was made against
the old file and may not fit the new one (see `docs/adr/0004-patched-datapacks-are-not-auto-updated.md`;
it applies to mods the same way). To take it, put the new upstream file in the server's
`mod-originals/` or `datapack-originals/` and the edited copy in `mods/` or the world's datapacks
folder, then snapshot the server as below; that re-makes the patch against the new file.

`python tools/build.py` writes three files to `dist/` (it fails if `player/` is missing):

| File | For | Contents |
|---|---|---|
| `TheRealms-Server-X.Y.Z.zip` | the host | `package/` under `TheRealms-Server/` (the `.sh` and `.command` launchers marked executable) |
| `TheRealms-Client-X.Y.Z.mrpack` | players with Prism Launcher or the Modrinth App | `client/modrinth.index.json` + `client/overrides/` |
| `TheRealms-Player-X.Y.Z.zip` | players with the official Minecraft Launcher | `player/` under `TheRealms-Player-X.Y.Z/`, plus that same `.mrpack` (byte-identical) and `installer/fabric-profile.json` (a copy of `client/fabric-profile.json`) |

All three are reproducible (fixed timestamps, sorted entries) and contain no third-party files.

Then boot it locally on spare ports (doesn't disturb a server already on 25565):

```powershell
python tools/build.py
Expand-Archive dist\TheRealms-Server-*.zip $env:TEMP\realms-test -Force
.\tests\smoke.ps1 -Root $env:TEMP\realms-test\TheRealms-Server -Port 25566 -RconPort 25576
```

On macOS or Linux, unzip the same way and run `sh start.sh` in the folder: the first run exercises the
PowerShell bootstrap too (uninstall or hide `pwsh` from the `PATH` to test the download).

To test the Docker setup locally (Linux, or Docker Desktop on Windows/macOS), with no other server on
25565:

```sh
python tools/build.py
rm -rf /tmp/realms-docker && mkdir -p /tmp/realms-docker
unzip -q dist/TheRealms-Server-*.zip -d /tmp/realms-docker
cd /tmp/realms-docker/TheRealms-Server/docker
printf 'EULA=TRUE\nOWNER=YourName\nMEMORY_GB=4\n' > .env
docker compose up -d --build      # --build picks up Dockerfile changes
docker compose logs -f            # wait for "Done (", then Ctrl+C
docker compose down               # must log "All dimensions are saved"
```

The world, `java/` (the Linux build) and the downloaded PowerShell end up in
`/tmp/realms-docker/TheRealms-Server`, exactly where a native run puts them.

Open a PR. CI boots the release on clean runners:

| Job | Runs on | What |
|---|---|---|
| Lint, unit tests, manifest | every push and PR | ruff, pytest, `validate.py` |
| Windows | every push and PR | PSScriptAnalyzer, Pester, build, unzip, export a hosting bundle, boot with `tests/smoke.ps1`, check every mod loads, stop |
| Linux (native) | every push and PR | unzip, boot with the `.sh` launchers (PowerShell bootstrap included), same checks |
| Linux (Docker) | every push and PR | the release folder under `docker compose` from `package/docker/`: reaches "Done", shuts down cleanly |
| Hosting bundle (Docker) | every push and PR | the Windows-made hosting bundle under its own `docker-compose.yml` (`tests/hosting-smoke.sh`) |
| macOS | release tags and manual runs | native boot like Linux; start it with **Actions > CI > Run workflow** (or `gh workflow run ci.yml --ref <branch>`) before tagging if you touched the launchers, `realms.sh`, `pwsh.lock` or Java |

## Capturing changes from a live server

If you add or update plugins/mods/datapacks on a running server by hand, snapshot it back into the
manifest (stop the server first so nothing is mid-write):

```bash
python tools/snapshot.py server C:/MCServer/factions     # Paper
python tools/snapshot.py server C:/MCServer/smp          # Fabric
python tools/snapshot.py client "C:/Games/PrismLauncher/instances/Factions Client/minecraft"
python tools/snapshot.py profile     # re-pin only client/fabric-profile.json (see below)
```

The snapshot tells the server type from the folder:

- **Paper**: `paper.jar` + `version_history.json`. The Minecraft version comes from
  `version_history.json`, the Paper build is matched by hash, plugins come from `plugins/*.jar`.
- **Fabric**: a Fabric server launcher jar in the folder (`fabric-server.jar`, preferred if there are
  several) + a `mods/` folder. The Minecraft and loader versions are read from the launcher jar's
  `install.properties`: the launcher reads exactly that file to decide what to download and run, it
  is there before the first start, and unlike `versions/`, `.fabric/` and `libraries/` it can't hold
  leftovers from an older version. The launcher is pinned to meta's jar for those versions and the
  newest stable installer. If the local jar isn't byte-identical to it (it came from another
  installer), the snapshot still pins meta's jar, which runs the same loader and Minecraft version,
  and prints a note. Mods come from `mods/*.jar` only; folders inside `mods/` (LuckPerms keeps its
  data in `mods/luckperms/`) and other files are ignored.

Every plugin, mod and datapack must be on Modrinth (matched by SHA-1), or the snapshot fails and lists
the files that aren't. Datapacks are read from the world folder named by `level-name` in the server's
`server.properties` (on Fabric this may be empty; datapack mods live in `mods/`).

The `world` settings are kept from the old manifest when the server type and Minecraft version are
unchanged; otherwise they are read from `server.properties` (`level-name`, and `level-seed`: empty
stays empty, meaning a random seed; a text seed is turned into the number Minecraft would use).

A mod or datapack you edited in place is matched against `mod-originals/<same file name>` or
`datapack-originals/<same file name>` in the server folder, and the changed files become a patch:
`package/realms/patches/<slug>/` plus `"patch": {"path": "patches/<slug>", "base_sha512": ...}` on
the entry, pinned to the original's hash. (Jars are zips, so mods and datapacks are patched the same
way.) A file identical to its original simply pins the original, with no patch. A patch may only
replace files that exist in the upstream file (adding or removing files fails the snapshot), and
patch folders no mod or datapack uses are deleted. `validate.py` checks that every patch matches its
entry's pinned hash, and `--online` applies each patch to the real download to prove it still fits.

`snapshot.py client` also pins `client/fabric-profile.json`: Fabric meta's launcher profile for the
client pack's Minecraft and loader versions (the `minecraft` and `fabric-loader` dependencies in
`client/modrinth.index.json`), from
`https://meta.fabricmc.net/v2/versions/loader/<minecraft>/<loader>/profile/json`. The player installer
gives it to the official Minecraft Launcher as the `fabric-loader-<loader>-<minecraft>` version. After
changing the loader in the client index by hand, run `python tools/snapshot.py profile` to re-pin just
this file. Meta generates the profile on request and stamps it with the time (`time`, `releaseTime`);
everything else is the same for the same versions, so the tools compare profiles ignoring those two
keys, and a re-pin that only differs in them leaves the file alone. `validate.py` checks the profile's
`id` and `inheritsFrom` match the client index, and that every library comes over https from Fabric's
maven or Minecraft's/Maven Central with a sha1 or sha256 (except the loader itself, which meta lists
without hashes); `--online` checks meta still serves the same profile.

Plugins, mods and datapacks keep the file name they have on the server. On `check_updates.py --apply`,
plugins and mods take the new upstream file name, but datapacks keep theirs, because the world refers
to datapacks by file name (the rule is written down once, in `tools/entries.py`).
Config defaults are curated by hand: copy changed configs into `package/realms/defaults/` yourself, and
never copy files containing secrets (`server.properties` from a live server has the RCON password).

## Patches this pack carries

Each one is a whole replaced file under `package/realms/patches/<slug>/`, pinned to the upstream jar it was made
against (ADR-0004). When `check_updates.py` reports a patched mod as "patched - re-snapshot needed", re-make the
patch against the new upstream file: carry the change below over, then check it is still needed.

| Mod | File | What the patch does, and why |
|---|---|---|
| `silvers_effects-library` | `pack.mcmeta` | Raises the highest supported pack format so the pack loads on Minecraft 26.3. |
| `silvers_effects-library` | `overlay_26.3/.../technical/effects.mcfunction` | One command at the top returns early for a non-player entity with none of the 19 `*_duration` scores. Upstream runs the function's 97 commands for every loaded mob on every tick; none can match a mob without a score, and with about 1,900 mobs loaded that went past Minecraft's 65,536-commands-per-tick limit, cutting the function off before it reached every mob. Players must never be skipped: the last line re-arms their tick advancement. |
| `silvers_strength-smp-season-4` | `.../main/enchant/check.mcfunction` | A per-player counter at the top makes the 968 block checks below it (markers on enchanting tables, anvils and grindstones near the player) run every 10 ticks instead of every tick. It was 26% of the server tick with 25 players. The markers persist, so the only change is that a newly placed block is noticed within half a second. |

Measure a change like these with `tools/loadtest.py` (below): on an i7-8700K with 25 fake players the two
performance patches took the typical tick from 184 ms to 143 ms and the command-limit hits from about 2,100 a
run to none.

## Mods left out on purpose

The shared mod folder has these; the pack doesn't. Check the reason still holds before adding one in a sync.

| Mod | Why (measured 2026-10-11, 25 fake players, i7-8700K) |
|---|---|
| Slabbed (0.6.2-alpha) | About 140 ms more per tick, and an open report of 0 TPS deadlocks on 26.3 ([slabbed#102](https://github.com/peetsamods/slabbed/issues/102)). |
| The Sift | About 90 ms more per tick: it adds an ichor fluid state to block-state definitions and hooks the fluid lookup. It also replaces the same ancient-city centres as the Dungeons and Taverns ancient-city overhaul. |
| Amethyst Nether | Defines `minecraft:the_nether`, as Incendium does; only one can generate, and its Modrinth page lists Incendium as incompatible. |
| Just Enough Professions, Improved Inventory Tabs, Villager News | Not on Modrinth, so they can't be pinned (ADR-0002). |
| PrickleMC | The file in the folder is a NeoForge jar. |

After a sync, launch the client pack and join a test server before releasing: CI boots the server but can't
start a game client, and a mod on one side only shows up as "registry entries that are unknown to this client".

## Tests

```bash
pip install pytest ruff
python -m pytest -q && python -m ruff check tools tests && python tools/validate.py
```

The unit tests never touch the network or the real checkout: tools take an `Upstream` catalog and
a `Repo`, and tests pass a `RecordedHttp` adapter (replaying `tests/fixtures/upstream/*.json`, or
responses built in the test) and a temporary copy of the repo. A request with no recorded response
fails loudly. Sample manifests are frozen releases in `tests/fixtures/manifests/` (`paper-1.1.0`, the
last Paper release, and `fabric-2.0.0`, each with its patches and a trimmed client index), so a new
release never breaks the tests; only `test_real_repo_is_valid` checks what the repo pins today.
If an upstream API changes shape, or a test needs a new request, re-record the
fixtures from the live APIs (responses are trimmed to the fields the tools read):

```bash
python tests/fixtures/record.py
```

## Load testing

Before claiming a player count, or after adding a mod that runs every tick, measure it. `tools/loadtest.py`
starts an installed copy of the package (the one the smoke test above leaves in `$env:TEMP\realms-test`),
spawns fake players with [Carpet](https://modrinth.com/mod/carpet) over RCON and records tick times plus a
CPU profile of the main thread:

```powershell
python tools/loadtest.py $env:TEMP\realms-test\TheRealms-Server --carpet C:\Downloads\fabric-carpet-26.3.jar --players 25
# what one mod costs: the same run without it (and its libraries)
python tools/loadtest.py $env:TEMP\realms-test\TheRealms-Server --carpet C:\Downloads\fabric-carpet-26.3.jar --players 25 --without silvers_strength-smp-season-4
```

Results go to `<copy>\loadtest\<name>\`: `summary.json` (mean and typical tick time, TPS, the slowest ticks, how often the 65,536-commands
limit was hit), `samples.jsonl`, `profile.txt` (which mod and which methods the main thread spent its time
in) and `perf.txt` (Minecraft's own 10-second profile from halfway through: the tick by section, entity type
and datapack function). `--scenario walk` or `explore` measures world generation instead of the steady cost. Run on an idle
machine and compare runs made on the same copy: fake players stand in for real ones but don't send network
traffic, and walk/explore change the world for every later run. The numbers in docs/ADMIN.md ("How many
players") came from this harness on an i7-8700K.

## Releasing

1. Bump `version` in `package/realms/manifest.json` (semver: patch = plugin bumps, minor = new content,
   major = new Minecraft version or a world reset).
2. Add a `## [x.y.z]` section to `CHANGELOG.md`. If players will notice anything (rules, mods, the client
   pack, the wardrobe, events), date its entry at the top of `site/changes.html` too, in players' words
   (`docs/ADMIN.md`, "Telling players what changed").
3. Merge to `main`, then tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.

The release workflow re-runs CI (including macOS), refuses to publish if the tag and manifest version differ, and attaches
`TheRealms-Server-X.Y.Z.zip`, `TheRealms-Client-X.Y.Z.mrpack` and `TheRealms-Player-X.Y.Z.zip`.

## Changing Minecraft version

Every plugin, mod and datapack needs a build for the new version. `check_updates.py` only looks within
the pinned version, so upgrade a server by hand and run `snapshot.py` against it (it takes the Minecraft
version from the server, and re-reads the world settings from `server.properties` because the version
changed). Expect world-gen changes to affect new chunks only. Switching between Paper and Fabric works
the same way: snapshot a server of the new type.
