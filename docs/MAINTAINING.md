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
| `package/realms/datapacks/realms-*/`, `client/overrides/resourcepacks/Monkey SMP Wardrobe/`, `defaults/config/easy_npc/security.cfg` | the generated packs (edit the tables in `tools/events.py`, `wardrobe.py`, `challenges.py`, `npcs.py`, `rules.py`, `standings.py`, `drops.py`) | `python tools/datapacks.py` |
| `package/realms/patches/<slug>/` | files replaced inside a downloaded mod jar or datapack | `tools/snapshot.py` |
| `client/` | the player modpack (`modrinth.index.json` + `overrides/`) | `tools/snapshot.py client` |
| `client/fabric-profile.json` | Fabric meta's launcher profile for the client pack's Minecraft + loader | `tools/snapshot.py client` or `profile` |
| `player/` | the player installer for the official Minecraft Launcher (shipped whole in the player zip) | by hand |
| `tests/fixtures/upstream/` | API responses the unit tests replay | `tests/fixtures/record.py` |
| `tests/fixtures/patch-golden/expected.json` | the patch rules' answers for one fixed zip and patch, checked by both the Python and the PowerShell tests | `tests/fixtures/patch-golden/record.py` |

The command-line tools (`snapshot`, `check_updates`, `validate`, `build`, `modrinth`) are thin; the knowledge
lives in a few modules they share:

| Module | Owns |
|---|---|
| `tools/entries.py` | the manifest entry shape, server types and which groups they use, the `file` naming rule, entry validation, hash choice |
| `tools/patches.py` | making, storing, applying and checking patches |
| `tools/upstream.py` | the Upstream catalog (Modrinth, PaperMC, Fabric meta, Adoptium) behind a swappable HTTP adapter |
| `tools/defaults.py` | the `{{TOKEN}}` placeholders the installer fills into `defaults/server.properties` |
| `tools/launcher_profile.py` | the Fabric launcher profile: its expected id, checks, and comparing profiles while ignoring their generation time |
| `tools/repo.py` | where things live in the repo (tools take a `Repo`, so tests can use a temp copy) |
| `deploy/lib.sh` | what every VPS script in `deploy/` shares, sourced right after `set -eu`: settings from the env file, the log, the server's container (`compose`, `running`, `rcon`), a restart's lifecycle (`players_online`, `warn_players`, `wait_for_live`, and `whole_number`, which stops a script on a WARN_MINUTES or BOOT_TIMEOUT that isn't one), Discord posts (`discord`, the one place that turns a message into a JSON string: quotes, backslashes, newlines, tabs, control characters), the deploy lock (`deploy_lock`), installing a timer's units, and the timed jobs' runner (`timed_job`: `realms-week.sh`, `realms-drops.sh` and `realms-day.sh` only say their tool, wording and arguments; a job that gave up posts a staff alert). `tests/test_deploy_lib.py` runs it under dash with fake `docker`, `flock`, `python3`, `curl` and `sleep` |
| `tools/nbt.py` | reading the world's NBT files (level.dat, scoreboard.dat, world_border.dat, Open Parties and Claims' `*.nbt`): `nbt.read(path or bytes)` gives the root compound as plain Python values, gzipped or not. Only `tools/saved_world.py` reads through it; `tests/nbt_writer.py` writes NBT for the tests |
| `tools/season_calendar.py` | the season calendar: the Pacific time zone, the launch and launch weekend, the start of week N, week N's Saturday, the drop nights, the next season's date, and dates and times in words (the same in any locale). challenges, drops, npcs, wardrobe, standings and site_links ask it. Every date follows from the launch, so moving a season is one edit (the launch) and `python tools/datapacks.py`. Without the time zone database (`tzdata`) it stops with a message saying to install it |
| `tools/saved_world.py` | the saved world: where each file sits in a world folder and how it is saved, so standings, season, drops and map_border ask it rather than walk the files. `scoreboard(folder)` gives scores by objective and holder (26.3 leaves a score of 0 out), display names and teams; `parties`, `claims(folder, dimension)` (claim file, then that dimension's chunks) and `claim_counts` (chunks per claim file, every dimension) read Open Parties and Claims; `border(folder, dimension)` gives a border's centre, size now and target size. Callers keep their own rules (which border size counts, ranking). None for a file not saved yet, and each caller decides what that means; a file not shaped as the server saves it is a ValueError naming it; `tests/fake_world.py` builds the tests' made-up worlds |
| `tools/rcon.py` | sending console commands to the running server for the VPS jobs (challenges, drops, standings): the container's own `realms rcon` behind one adapter, a recording fake for tests, the one list of answers that mean the server refused, and a timed job's command line (`job_subcommands`, `run_job`, `job_time`, `parse_time`, the exit codes `NOT_RUNNING` and `GAVE_UP`: `commands [--at]` and `send --docker` in challenges, drops and wardrobe) |
| `tools/datapacks.py` | the generated packs: the Minecraft version and pack format they target, writing and checking them, and the cross-pack checks (every function called exists, every scoreboard objective read is created, macros are marked); each generator only says what its packs hold (`packs(repo)`) |
| `tools/checks.py` | the one list of fast checks (ruff, pytest, validate, datapacks, `dash -n`, Pester) that CI and maintainers run, and which of CI's boot jobs a run needs (`--boots`, `boots()`) |
| `tools/local_ci.py` | CI on a maintainer's machine: checks a PR's head in a temporary worktree with checks.py and posts a `local-ci` commit status through `gh` (see "Tests") |

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

Then boot it locally on spare ports (doesn't disturb a server already running on this machine):

```powershell
python tools/build.py
Expand-Archive dist\TheRealms-Server-*.zip $env:TEMP\realms-test -Force
.\tests\smoke.ps1 -Root $env:TEMP\realms-test\TheRealms-Server -Port 25566 -RconPort 25576 -VoicePort 24455 -MapPort 8101
```

A server uses four ports: the game (`-Port`, TCP), RCON (`-RconPort`, TCP), Simple Voice Chat (`-VoicePort`,
UDP, default 24454) and the BlueMap web map (`-MapPort`, TCP, default 8100). The smoke test writes the last
two into the test copy's `config/voicechat/voicechat-server.properties` and `config/bluemap/webserver.conf`.
Before it installs, and again before it starts, it stops with the port's name if one of the four is already in use
on this machine. Voice chat and BlueMap shut the whole server down when they can't bind their port (seconds
after "Done"), and on a taken RCON port the test would stop the other server. When another server or test boot
is running, give each run its own four ports. Re-running in the same folder is fine: the test waits for this
boot's "Done" line, not the one the last boot left in `server/logs/latest.log`.

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

Open a PR. CI checks every push to it and boots the release on clean runners when the change can break the
boot (`python tools/checks.py --boots` decides; Windows minutes count double and macOS 10x on this private
repo, and the included minutes ran out in October 2026):

| Job | Runs on | What |
|---|---|---|
| Checks, build | every push and PR | `tools/checks.py --strict` (ruff, pytest, `validate.py`, `datapacks.py --check`, `dash -n`, Pester on PowerShell 7), pytest again on Python 3.11 (the oldest the tools support, Debian 12's), `build.py` |
| Linux (native) | PRs out of draft that touch `package/`, the build (`build.py`, `repo.py`) or the boot tests; pushes to `main` that do; tags; manual runs | unzip, boot with the `.sh` launchers (PowerShell bootstrap included), check every mod and datapack loads, stop |
| Linux (Docker) | as Linux (native) | the release folder under `docker compose` from `package/docker/`: reaches "Done", shuts down cleanly |
| Windows | PRs out of draft that touch the installer, the manifest, `pwsh.lock`, `package/docker/`, the launchers (`.bat`), `player/`, the build or the PowerShell tests; tags; manual runs | PSScriptAnalyzer, Pester (with the player installer's), build, unzip, export a hosting bundle, boot with `tests/smoke.ps1`, check every mod loads, stop |
| Hosting bundle (Docker) | when Windows runs | the Windows-made hosting bundle under its own `docker-compose.yml` (`tests/hosting-smoke.sh`) |
| macOS | release tags and manual runs | native boot like Linux; start it with **Actions > CI > Run workflow** (or `gh workflow run ci.yml --ref <branch>`) before tagging if you touched the launchers, `realms.sh`, `pwsh.lock` or Java |

Draft PRs get the checks only. Label a PR `boot` to boot it everywhere (draft or not) from its next push on, or
start a manual run to boot it now (adding a label doesn't start a run).

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

The patch rules (which hash an entry is checked against, the patch id, and replacing files inside a zip) are
written twice, in `tools/patches.py`/`tools/entries.py` and in the installer's `Realms.psm1`, because the
installer must stay PowerShell 5.1 (ADR-0003, ADR-0007). One golden fixture pins both:
`tests/fixtures/patch-golden/` holds a dummy `input.zip`, a patch in the real layout and the answers in
`expected.json`, which `tests/test_patches.py` and the `Patch rules golden fixture` block of
`tests/Realms.Tests.ps1` both check. If you change a rule on purpose, change it on both sides, re-record with
`python -I tests/fixtures/patch-golden/record.py` and check that both suites pass. Compression and entry order
inside the patched zip are not part of the rules: the installer moves replaced files to the end of the zip, while
the Python tools keep them in place. So a patch must never replace a file whose place in the zip matters, above
all `META-INF/MANIFEST.MF` (Java's `JarInputStream` only finds it as the first or second entry); `snapshot.py`
and `validate.py` refuse one (`ORDER_SENSITIVE` in `tools/patches.py`). The patch id sorts paths ordinally, so it
is the same on every platform.

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

Each file in `client/modrinth.index.json` is `"client": "required"` or `"optional"`: an optional one gets a tick
box in Prism and the Modrinth App, so a player on a slow computer can leave it out ("Low-end PC" in
`docs/PLAYERS.md`). `tools/client_env.py` decides which (`OPTIONAL_MODS`, plus every resource pack and shader
pack); `snapshot.py client` writes it and `validate.py` checks the index still matches. A mod that isn't on the
list is required, so a new mod is safe until someone sorts it. A mod belongs on the list only when the player
can join without it: it isn't on the server, or it is client-only, or Modrinth calls its client half optional,
and never when it adds blocks, items, entities or other registry entries (Fabric refuses a join that lacks
them). `tests/test_client_env.py` checks the list against facts recorded from every jar
(`tests/fixtures/client_mods.json`). When the client pack gains or loses a mod, those tests fail until you
re-record the facts, then sort the new mod. An optional mod that leaves the pack moves from `OPTIONAL_MODS` to
`RETIRED_OPTIONAL`, so the indexes of earlier releases under `tests/fixtures/manifests` still validate:

```bash
python -I tests/fixtures/record_client_mods.py            # downloads the mod jars (about 340 MB)
python -I tests/fixtures/record_client_mods.py --jars DIR # or reads them from a folder first
```

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
| `silvers_strength-smp-season-4` | `.../main/enchant/check.mcfunction`, and its copy in `overlay_26.3/` | A per-player counter at the top makes the 968 block checks below it (markers on enchanting tables, anvils and grindstones near the player) run every 10 ticks instead of every tick. It was 26% of the server tick with 25 players. The markers persist, so the only change is that a newly placed block is noticed within half a second. Version 1.8 added the `overlay_26.3` copy, which is the one 26.3 runs, so both carry the change. |
| `lootrestock` | `org/oldskooler/lootrestock/handler/ChestInteractionHandler.class` | A Java class, not a data file. Loot Restock checks whether a structure chest is empty the first time a player opens it, and that check rolls the chest's loot with no player, so vanilla's "a player opened a loot chest" advancement never fired and the weekly "Open 8 loot chests" challenge never counted. The patch answers "not empty" there without rolling (the code only runs for a chest that still has its loot table). Make it again with `python tools/lootrestock_patch.py LootRestock-<version>.jar OUT.jar`, put `OUT.jar` in the test server's `mods`, and snapshot; the script's docstring has the details. Loot Restock is GPL-3.0-or-later and its source is public, so shipping a changed class is fine as long as the change stays published: it is, in this repo. |
| `trident-all-weather-channeling` | `.../function/app/trident_hit_entity.mcfunction` and `.../app/summon_lightning.mcfunction` | Upstream calls lightning on every Channeling trident that has ever hit something, including ones left in the ground, so one hit struck every old trident nearby (on a test server, a pig next to an old trident turned into a zombified piglin). The patch marks only the attacker's own trident still in flight (`on owner`, so another player's trident nearby is never picked; tested the earlier "nearest in flight" version the same way, only the pig by the trident that hit was struck). The strike is scheduled a tick later so it runs from the server at the world spawn, and lightning, which isn't damage a player causes, leaves out two places PvP is off (rule 26): nothing within 64 blocks of spawn, and nothing within 6 blocks of a player in grace. Patches can't add files, so this uses the mod's two functions. |

Measure a change like these with `tools/loadtest.py` (below): on an i7-8700K with 25 fake players the two
performance patches took the typical tick from 184 ms to 143 ms and the command-limit hits from about 2,100 a
run to none.

## Mods pinned by hand

`add.py` and `check_updates.py` only see releases Modrinth lists for the manifest's Minecraft version. A mod
that works on it but isn't listed for it is pinned by hand: the same entry `add.py` writes (`entries.added`,
from the Modrinth version), after a smoke test and a test join. `check_updates.py` never reports its updates,
so look at its Modrinth page when updating the pack, and when changing Minecraft version.

| Mod | Listed for | Tested on 26.3 |
|---|---|---|
| `hostname-catcher` 0.2 | 26.1 to 26.2 | 2026-10-25: boots, lets a login through a join address in, logs a real client's join |

## Mods left out on purpose

The shared mod folder has these; the pack doesn't. Check the reason still holds before adding one in a sync.

| Mod | Why (measured 2026-10-11, 25 fake players, i7-8700K) |
|---|---|
| Slabbed (0.6.2-alpha) | About 140 ms more per tick, and an open report of 0 TPS deadlocks on 26.3 ([slabbed#102](https://github.com/peetsamods/slabbed/issues/102)). |
| The Sift | About 90 ms more per tick: it adds an ichor fluid state to block-state definitions and hooks the fluid lookup. It also replaces the same ancient-city centres as the Dungeons and Taverns ancient-city overhaul. (Gone from the folder by 2.8.0.) |
| Amethyst Nether | Defines `minecraft:the_nether`, as Incendium does; only one can generate, and its Modrinth page lists Incendium as incompatible. |
| Just Enough Professions, Improved Inventory Tabs, Villager News, Koh's Death Effects | Not on Modrinth, so they can't be pinned (ADR-0002). |
| PrickleMC, Crops Love Rain (NeoForge files) | The folder's `cropsloverain-3.2.1.jar` is the NeoForge build, and PrickleMC's NeoForge jar sits next to its Fabric one. The pack has the Fabric build of each. |
| Deimos (2.7.1) | A library, and nothing in the pack or the folder needs it (every jar's `fabric.mod.json`, checked 2026-10-26). |
| Nullscape | In the pack until 2.8.0, then gone from the folder. Don't bring it back next to Endercon: with both, a test server's End had no outer-island highlands or midlands, so no End cities and none of Qrafty's End Villages. Endercon alone generates both. |
| Vanilla Permissions (0.3.6+26.1.2) | Shipped in 2.5.0 and 2.6.0, then removed: measured 2026-10-26 (fake players on land, i7-8700K), 10 players took 1,081 ms per tick with it and 64 ms without, 18 players 986 ms and 142 ms. It checks each entity selector a player's command uses against the whole command tree (`CommandDispatcher.getPath`, from `ArgumentPermission.validate`), and the pack runs advancement functions as each player every tick. Its job, ranks granting vanilla commands, went to ops (docs/ADMIN.md, "What needs op"). Measure a newer version the same way before adding it back. |

After a sync, launch the client pack and join a test server before releasing: CI boots the server but can't
start a game client, and a mod on one side only shows up as "registry entries that are unknown to this client".

## Shelved mods

Mods that were in a release and that the owners took out for now. Each keeps its exact manifest entry here, so
bringing it back is a copy: paste the entries into `mods` in `package/realms/manifest.json` (it's sorted by slug),
then run `python tools/validate.py --online`. `check_updates.py` doesn't see them, so look on Modrinth for a newer
build for the manifest's Minecraft version first.

### Shops: Universal Shops and Polymer (shelved 26 October 2026)

Item-priced player shops from 2.6.0, never on the live server. The owners don't want an economy system for now:
players trade by hand (rule 43), and the paid whitelist is unchanged. Polymer was only there for Universal Shops:
no other mod in the pack needs it, on Modrinth or in its `fabric.mod.json` (checked 26 October 2026).

```json
  {
    "slug": "polymer",
    "project_id": "xGdtZczs",
    "version": "0.18.5+26.3",
    "version_id": "3fDXSiRx",
    "file": "polymer-bundled-0.18.5+26.3.jar",
    "url": "https://cdn.modrinth.com/data/xGdtZczs/versions/3fDXSiRx/polymer-bundled-0.18.5%2B26.3.jar",
    "size": 1438885,
    "hashes": {
      "sha512": "9a8c31e505048571b8679d3406794ba1b75bb072758aaff5ee956fb2ff33db00a12b420fb8953a390cab4ea9c93e43e5eff37e7f3ae2e07bbecffa5a58193a47"
    }
  },
  {
    "slug": "universal-shops",
    "project_id": "cnIatHrN",
    "version": "1.16.0+26.3",
    "version_id": "nQOUyX9T",
    "file": "universal_shops-1.16.0+26.3.jar",
    "url": "https://cdn.modrinth.com/data/cnIatHrN/versions/nQOUyX9T/universal_shops-1.16.0%2B26.3.jar",
    "size": 619888,
    "hashes": {
      "sha512": "5617c900118ab3fdc9bcc63efc1da54d6c1481b5d3393ee0112b61c2256d8d7f03c7b28bbb995dae7bf37de25efb38ecec2963def6c3bd64e6376234741d165f"
    }
  }
```

To bring shops back:

1. Paste both entries into the manifest's `mods` and run `python tools/validate.py --online`.
2. Nothing to do for claims in the package: `defaults/config/openpartiesandclaims-server.toml` kept
   `"hand$universal_shops:trade_block"` (dormant without the mod; a test boot with it on 26 October 2026 was clean).
3. Put the shop wording back, as it was before they were shelved (`git show aa9a7a5:<file>`): rule 43 in
   `docs/RULES.md` (the owners adopt it again), "Shops" under "Playing" in `docs/PLAYERS.md`, the "Fair trades" rule
   and "How does trading work?" in `site/index.html`, and the shop lines in `docs/PROMOTION.md`'s drafts. Drop the
   "shelved" notes in `docs/ADMIN.md` ("Shops") and `docs/LIVE.md` ("Shops in claims").
4. Add a `site/changes.html` entry for players, and once that release is live, run `deploy/shops-claims.sh` on the
   VPS (`docs/LIVE.md`, "Shops in claims").

## Tests

```bash
pip install pytest ruff tzdata   # tzdata: Windows has no time zone database of its own
python tools/checks.py            # ruff, pytest, validate.py, datapacks.py --check, dash -n, Pester
python tools/checks.py pytest     # just one; --list says what each runs
```

`tools/checks.py` is the one list of checks a change needs before review; CI runs the same file
(`--strict`, so a tool missing on the runner fails instead of being skipped). Locally a missing tool is
skipped and said: Pester needs Pester 5.5+ in every PowerShell it runs on (on Windows, Windows PowerShell 5.1
and pwsh too when it's installed, since both must pass; elsewhere pwsh), `sh` needs `dash` (on Windows, Git for Windows'
own dash is found from `git`, which also lets the pytest tests of `deploy/lib.sh` run).

### CI on this machine (local CI)

When Actions can't run, check PRs here and post the result on GitHub as a commit status named `local-ci`:

```bash
python tools/local_ci.py 68 70      # these PRs
python tools/local_ci.py --open     # every open PR whose head commit has no local-ci result yet
```

It checks each PR's head in a temporary worktree with this checkout's `tools/checks.py` (so a PR made before
checks.py existed is checked the same way) with `--strict`, so `success` means every check ran on this machine.
It needs an authenticated `gh`, never runs a PR from a fork, posts `error` if a run stops partway, and keeps
each run's output in `.git/local-ci/<sha>.log`. It doesn't boot the server: for a PR that changes the
manifest, the installer or the launchers, run `tests/smoke.ps1` too (see "Releasing without Actions").

### Review

Before a PR leaves draft, run `/code-review` on it (Claude Code) and fix what it finds in one commit, "<area>:
fix the review of #N", with a test for each correctness fix. Say in the PR what wasn't fixed and why.

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
3. Put the new player files on the site, since the GitHub releases are private and players download the pack
   from there: `python tools/build.py`, replace the files in `site/pack/` with `dist/TheRealms-Client-X.Y.Z.mrpack`
   and `dist/TheRealms-Player-X.Y.Z.zip`, point `MODPACK_URL` and `INSTALLER_URL` in `site/config.js` at them
   and run `python tools/site_links.py`. `validate.py` fails while the site serves another version's pack.
   (Once the pack has its Modrinth project, `MODPACK_URL` points there and this step goes.)
4. Merge to `main`, then tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
5. Put the client pack on Modrinth: `python tools/modrinth.py` from a checkout of the tag, with the token in
   `MODRINTH_TOKEN` ([MODRINTH.md](MODRINTH.md#publishing-a-version)). It uploads nothing when the release
   left `client/` alone, and moves the server listing to the newest version.

The release workflow re-runs CI (including macOS), refuses to publish if the tag and manifest version differ, and attaches
`TheRealms-Server-X.Y.Z.zip`, `TheRealms-Client-X.Y.Z.mrpack` and `TheRealms-Player-X.Y.Z.zip`.

### Releasing without Actions

GitHub Actions doesn't start in this private repo right now (billing), so the tag push in step 4 publishes
nothing. Do the workflow's job by hand, after step 4, in a fresh worktree of the tag so nothing uncommitted
gets in:

```bash
git fetch origin --tags
git worktree add --detach ../release-vX.Y.Z vX.Y.Z
cd ../release-vX.Y.Z
python tools/checks.py   # on Windows, Pester runs on Windows PowerShell 5.1 and on pwsh when it's installed
GITHUB_REF_NAME=vX.Y.Z python tools/build.py --notes notes.md
gh release create vX.Y.Z dist/* --title "Monkey SMP vX.Y.Z" --notes-file notes.md --verify-tag
python tools/modrinth.py      # step 5, with MODRINTH_TOKEN set (MODRINTH.md)
cd - && git worktree remove --force ../release-vX.Y.Z   # --force: notes.md is untracked
```

In PowerShell, set the tag with `$env:GITHUB_REF_NAME = 'vX.Y.Z'` before `python tools/build.py --notes notes.md`.
`build.py` refuses a tag that doesn't match the manifest version, and `--notes` writes the release notes the
workflow would: the version's CHANGELOG section, then what each download is for (it fails if the CHANGELOG has
no section for the version). `--verify-tag` stops `gh` from making a tag that isn't on GitHub yet.

What this skips is CI's boot tests (the server started natively on Windows, Linux and macOS, and in Docker).
For a release that changes the manifest, the installer or the launchers, boot it first: unzip
`dist/TheRealms-Server-X.Y.Z.zip` somewhere temporary and run `./tests/smoke.ps1 -Root <that folder>\TheRealms-Server -MemoryGB 4`.
Do it right after pushing the tag: the live server deploys a new tag in its next deploy window (docs/LIVE.md)
whether or not the release exists, and players need the new pack by then.

## Changing Minecraft version

Every plugin, mod and datapack needs a build for the new version. `check_updates.py` only looks within
the pinned version, so upgrade a server by hand and run `snapshot.py` against it (it takes the Minecraft
version from the server, and re-reads the world settings from `server.properties` because the version
changed). Expect world-gen changes to affect new chunks only. Switching between Paper and Fabric works
the same way: snapshot a server of the new type.
