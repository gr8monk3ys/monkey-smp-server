# Maintaining the pack

Tools are plain Python 3.11+ with no dependencies (tests use `pytest`, lint uses `ruff`).

## Where things live

| Path | What | Edited by |
|---|---|---|
| `package/monkey/manifest.json` | pinned Java (one build per platform), server (Paper or Fabric), plugins or mods, datapacks | `tools/snapshot.py`, `tools/add.py`, `tools/check_updates.py --apply`, `tools/pin_github.py` |
| `package/monkey/pwsh.lock` | the portable PowerShell 7 build per platform that `monkey.sh` downloads when `pwsh` is missing | by hand (see below) |
| `package/*.bat`, `package/*.sh`, `package/Start Server.command`, `package/monkey/monkey.sh` | the host's launchers: `.bat` for Windows, POSIX `sh` for macOS/Linux | by hand |
| `package/docker/` | the Docker setup (`Dockerfile`, `compose.yaml`) | by hand |
| `package/monkey/defaults/` | first-run configs, copied only if missing | by hand |
| `package/monkey/datapacks/monkey-*/`, `client/overrides/resourcepacks/Monkey SMP Wardrobe/`, `defaults/config/easy_npc/security.cfg` | the generated packs (edit the tables in `tools/events.py`, `wardrobe.py`, `challenges.py`, `npcs.py`, `rules.py`, `standings.py`, `diplomacy.py`, `drops.py`, `firsts.py`, `outposts.py`, `omens.py`, `sieges.py`, `clips.py`, `camera.py`) | `python tools/datapacks.py` |
| `package/monkey/patches/<slug>/` | files replaced inside a downloaded mod jar or datapack | `tools/snapshot.py` |
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
| `deploy/lib.sh` | what every VPS script in `deploy/` shares, sourced right after `set -eu`: settings from the env file, the log, the server's container (`compose`, `running`, `rcon`), a restart's lifecycle (`players_online`, `warn_players`, `wait_for_live`, and `whole_number`, which stops a script on a WARN_MINUTES or BOOT_TIMEOUT that isn't one), Discord posts (`discord`, the one place that turns a message into a JSON string: quotes, backslashes, newlines, tabs, control characters), the deploy lock (`deploy_lock`), installing a timer's units, and the timed jobs' runner (`timed_job`: `monkey-week.sh`, `monkey-drops.sh`, `monkey-omens.sh`, `monkey-day.sh` and `monkey-sieges.sh` only say their tool, wording and arguments; a job that gave up posts a staff alert). `tests/test_deploy_lib.py` runs it under dash with fake `docker`, `flock`, `python3`, `curl` and `sleep` |
| `tools/nbt.py` | reading the world's NBT files (level.dat, scoreboard.dat, world_border.dat, Open Parties and Claims' `*.nbt`): `nbt.read(path or bytes)` gives the root compound as plain Python values, gzipped or not. Only `tools/saved_world.py` reads through it; `tests/nbt_writer.py` writes NBT for the tests |
| `tools/season_calendar.py` | the season calendar: the Pacific time zone, the launch and launch weekend, the start of week N, week N's Saturday, the drop nights, the next season's date, and dates and times in words (the same in any locale). challenges, drops, omens, npcs, wardrobe, standings and site_links ask it. Every date follows from the launch, so moving a season is one edit (the launch) and `python tools/datapacks.py`. Without the time zone database (`tzdata`) it stops with a message saying to install it |
| `tools/season_ics.py` | the calendar file players add to their phones, `site/public/monkey-smp-season-1.ics`: the launch, each Saturday's event and each Sunday's standings close, only as the site already tells players (the other names in `status.SCHEDULE` stay out until the site publishes them: add one to `ANNOUNCED`). Times are UTC instants from Pacific, DTSTAMP is `PUBLISHED` (bump it when the schedule changes; nothing reads the clock), UIDs never contain a time. Moving the season or an event means `python tools/season_ics.py`; `validate.py` and a test fail on a file that is out of date. `.gitattributes` keeps it `-text` so its CRLF line endings survive |
| `tools/saved_world.py` | the saved world: where each file sits in a world folder and how it is saved, so standings, season, drops, omens and map_border ask it rather than walk the files. `scoreboard(folder)` gives scores by objective and holder (a score of 0 is left out of the file), display names and teams; `parties`, `claims(folder, dimension)` (claim file, then that dimension's chunks) and `claim_counts` (chunks per claim file, every dimension) read Open Parties and Claims; `border(folder, dimension)` gives a border's centre, size now and target size; `command_storage(folder, namespace)` gives a namespace's command storage (`data/<namespace>/command_storage.dat`), key by key. Callers keep their own rules (which border size counts, ranking). None for a file not saved yet, and each caller decides what that means; a file not shaped as the server saves it is a ValueError naming it; `tests/fake_world.py` builds the tests' made-up worlds |
| `tools/rcon.py` | sending console commands to the running server for the VPS jobs (challenges, drops, omens, standings): the container's own `monkey rcon` behind one adapter, a recording fake for tests, the one list of answers that mean the server refused, `coded` (the timer's log line for drops' and omens' try, which returns a code), and a timed job's command line (`job_subcommands`, `run_job`, `job_time`, `parse_time`, the exit codes `NOT_RUNNING` and `GAVE_UP`: `commands [--at]` and `send --docker` in challenges, drops, omens and wardrobe) |
| `tools/border.py` | the border acts (`docs/SEASONS.md`): `ACTS` gives each season's acts (week and Overworld width; the Nether is 1:8), dated from `season_calendar.SEASONS`. Once an act is due and the season is launched and not locked, it grows both borders (never shrinking one) and records the act in `#border_act ev.state`; once the saved world shows the borders at the act's size, it fits the live map with `map_border.fit_maps`, then purges the changed maps the run after (`config/bluemap/monkey-map-purge.txt`). After an act it sends the act's border boss (`tools/boss.py`); from the finale's time it starts the finale (`tools/finale.py`) once the saved world shows its switch on. `plan`, `status`, `commands`, `send`. Run hourly by `deploy/monkey-border.sh` from Season II |
| `tools/repairs.py` | generates the `monkey-armor-repair` pack: diamonds repair netherite armor, for Strength SMP's Armor power (docs/ADMIN.md, "Mod settings") |
| `tools/boss.py` | the border boss (`docs/SEASONS.md`, "The border boss"): generates the `monkey-boss` pack; `spot` (where each act's boss rises), `status WORLD` (each act's boss: risen, slain by whom, left) |
| `tools/finale.py` | the finale's border close (`docs/SEASONS.md`, "The finale"): generates the `monkey-finale` pack; `plan` (the stages), `result WORLD` (points, winner's roster, the champion commands) |
| `tools/recap.py` | the Sunday recap, "Monkey SMP Weekly", that `standings.py close` posts: the launch gate (`#launched rw.day`), what a week's sections count from (kept in `week.json`), the sections (each a function in `SECTIONS` that takes the closing `Week` and returns its lines, `[]` when nothing happened or `None` when it can't tell; a new one is one function added there), the week's counters `standings.py` imports (`gained`, `folded`, `KILLS`, `BOUNTY`), and fitting the post under Discord's 2000 characters. The sections are worked out once at the close and kept in the closed week's file, so a retry posts the same words |
| `tools/firsts.py` | Server Firsts: the milestones, the `monkey-firsts` pack, and reading who holds each from the saved world for other tools: `holders(world)` gives every claim in order as `First(id, milestone, player, order, week)`; `claimed_in(firsts, week)` one challenge week's of that list, and `standings`/`champion` the season title (most firsts; a tie goes to whoever reached that number first). Runs on Python 3.10 too (staff run it on the VPS) |
| `tools/wrapped.py` | Season Wrapped: `start` keeps every player's rw.* and st.* scores at the launch, `build` makes `site/public/wrapped/season-<n>/` from the final world (a page per player, an index, the skins' pictures): the season's counts are the end's minus the launch's, the best weekly rank comes from the standings' closed weeks, firsts from `firsts.holders`. Pages are made beside the folder and swapped in, so a failed build leaves the last one; a folder holding anything else is refused |
| `tools/datapacks.py` | the generated packs: the Minecraft version and pack format they target, writing and checking them, and the cross-pack checks (every function called exists, every scoreboard objective read is created, macros are marked); each generator only says what its packs hold (`packs(repo)`) |
| `tools/checks.py` | the one list of fast checks (ruff, pytest, validate, datapacks, `dash -n`, Pester, the site with bun) that CI and maintainers run, and which of CI's boot jobs a run needs (`--boots`, `boots()`) |
| `tools/local_ci.py` | CI on a maintainer's machine: checks a PR's head in a temporary worktree with checks.py and posts a `local-ci` commit status through `gh` (see "Tests") |
| `tools/diplomacy.py` | the in-game faction identity (below) and war and pacts (`docs/SEASONS.md`): numbering parties and writing the number in game over RCON, diffed against the saved world so a run sends only what changed (`sync`, called by `standings.py board`), reading the monkey namespace's command storage (`saved_storage`, `numbers`, `names`), the war and pact functions and the kill advancements it adds to the `monkey-standings` pack, and the week's lines for the Sunday post (`report`) |
| `tools/outposts.py` | outposts (`docs/SEASONS.md`): their spots in the newest border ring from the saved world (as drops picks its spots), the `monkey-outposts` pack that checks the ground and runs the captures by faction number, the live map's marker set, and what standings asks of it: a week's `baseline`, `hours` held and their `points`. `recap_lines` is an "outposts this week" section for a Sunday recap. Run hourly by `deploy/monkey-outposts.sh`; Python 3.10, no tomllib |

### The faction number in game

Data packs can't see Open Parties and Claims' parties, so `tools/diplomacy.py` gives each party a number and
writes it in game. Anything in a pack that needs "which faction is this player in" (war and pacts and
outposts) reads it here rather than asking the parties:

| Where | What |
|---|---|
| `st.faction` score, by player name | the number (1 to 99) of the player's faction, offline players too. No score: in no faction, or in one made since the last board run |
| `st.leader` score | 1 for each party's owner, the faction's leader |
| storage `monkey:factions` `names.f<N>` | faction N's name as the board shows it, as a text component: `{text:"Red Monkeys"}` (plain ASCII, no quotes). Show it with `{"nbt":"names.f<N>","storage":"monkey:factions","interpret":true}`. Removed when the party is gone from two board runs in a row (a run that reads no parties removes nothing) |
| storage `monkey:factions` `ids.f<N>` | the party id behind number N. Kept after the party is gone, so the number is never given again |

- A number belongs to one party for the life of the world. A new season's world numbers again from 1.
- It is only as fresh as the last board run (`deploy/monkey-standings.sh board`, hourly), plus the up to
  5 minutes the saved world can be behind. Nothing else writes these, and staff shouldn't by hand.
- Same faction: `execute if score @s st.faction = <other> st.faction run ...` (no score never matches).
- From Python, `diplomacy.numbers(world)` (party id to number) and `diplomacy.names(world)` (number to name)
  read it back from the saved world.
- A pack that keeps a score per faction holds it as `#f<N>` and should end what it holds for a faction whose
  `names.f<N>` is gone (the sync runs `monkey:diplomacy/dissolve` for war and pacts before it removes one).
  Rather than test all the numbers in a function, check the ones it holds (outposts does this for each held
  outpost each minute) or let its Python job reset the rest from the saved storage (outposts' minutes, hourly).
- The sync sends its changes many to an RCON command: a list in storage `monkey:diplomacy batch` that
  `monkey:diplomacy/batch/run` makes in order, each the function `monkey:diplomacy/<f>` with its entry.
- None of it starts with `rw.`, so `tools/season.py` carries none of it into a new world.

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

One installer (`monkey.ps1` + `Monkey.psm1`) runs everywhere: on Windows PowerShell 5.1, and on
PowerShell 7 on macOS and Linux, where `monkey/monkey.sh` starts it (ADR-0007). Two kinds of pins
depend on the platform:

| Pin | Where | Platforms |
|---|---|---|
| Java (Eclipse Temurin JRE from Adoptium) | `manifest.json` `java`, one build per platform, each with URL + size + hash | Windows x64 (`.zip`), Linux x64 and aarch64, macOS x64 and aarch64 (`.tar.gz`) |
| PowerShell 7 (portable, from `PowerShell/PowerShell` GitHub releases) | `monkey/pwsh.lock`, one line per platform: URL + SHA-256 | Linux x64 and arm64, macOS x64 and arm64 (`.tar.gz`); Windows uses its built-in 5.1 |

`pwsh.lock` is a plain-text file, not JSON, because `monkey.sh` reads it with POSIX `sh` before any
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
python tools/pin_github.py patina-and-chime <tag> <jar>   # our own mod, from its GitHub release (below)
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

The Enchant Disabler data pack names Dungeons and Taverns' enchantments and replaces 30 of its tags, so an update to
either needs checking against the other: its file is named for DnT 5.3.0 while DnT is pinned at 5.3.2. It has to load after
DnT's own packs for its tags to win, which it does on a new world. Its inventory strip does nothing while the Enchantment
Disabler mod is installed (docs/RULES.md, B18).

`python tools/build.py` writes three files to `dist/` (it fails if `player/` is missing):

| File | For | Contents |
|---|---|---|
| `MonkeySMP-Server-X.Y.Z.zip` | the host | `package/` under `MonkeySMP-Server/` (the `.sh` and `.command` launchers marked executable) |
| `MonkeySMP-Client-X.Y.Z.mrpack` | players with Prism Launcher or the Modrinth App | `client/modrinth.index.json` + `client/overrides/` |
| `MonkeySMP-Player-X.Y.Z.zip` | players with the official Minecraft Launcher | `player/` under `MonkeySMP-Player-X.Y.Z/`, plus that same `.mrpack` (byte-identical) and `installer/fabric-profile.json` (a copy of `client/fabric-profile.json`) |

All three are reproducible (fixed timestamps, sorted entries) and contain no third-party files.

Then boot it locally on spare ports (doesn't disturb a server already running on this machine):

```powershell
python tools/build.py
Expand-Archive dist\MonkeySMP-Server-*.zip $env:TEMP\monkey-test -Force
.\tests\smoke.ps1 -Root $env:TEMP\monkey-test\MonkeySMP-Server -Port 25566 -RconPort 25576 -VoicePort 24455 -MapPort 8101
```

A server uses four ports: the game (`-Port`, TCP), RCON (`-RconPort`, TCP), Simple Voice Chat (`-VoicePort`,
UDP, default 24454) and the BlueMap web map (`-MapPort`, TCP, default 8100). The smoke test writes the last
two into the test copy's `config/voicechat/voicechat-server.properties` and `config/bluemap/webserver.conf`.
Before it installs, and again before it starts, it stops with the port's name if one of the four is already in use
on this machine. Voice chat and BlueMap shut the whole server down when they can't bind their port (seconds
after "Done"), and on a taken RCON port the test would stop the other server. When another server or test boot
is running, give each run its own four ports. Re-running in the same folder is fine: the test waits for this
boot's "Done" line, not the one the last boot left in `server/logs/latest.log`.

All three boot tests (`tests/smoke.ps1`, `tests/docker-smoke.sh`, `tests/hosting-smoke.sh`) also fail on data
that failed to load. The server starts anyway and the pack still counts as enabled, so the log is the only place
it shows. What counts: any function (`Failed to load function`), any tag (`Couldn't load tag`, `Couldn't read tag
list`), any data file that doesn't parse (`Couldn't parse data file`) or doesn't pass validation (`Found
validation problems in advancement`, `Found loot table element validation problem`), and a `Couldn't load
advancements` line that names a `monkey:` one (it lists other mods' on every boot). One function with a typo is
enough to fail the boot, whoever ships it: ours are generated by `tools/datapacks.py`, and `monkey/patches`
rewrites other mods'.

Data a pinned mod ships broken fails on every boot, so the tests carry a short list of what is known. Today
that is More Villagers: nine advancements and the `gilded_station` recipe don't parse on 26.2. The known pattern
names those files (the mod's `advancement/` folder and that one recipe), not the mod: any other More Villagers
file that stops loading fails the boot. When a mod update adds a new line, look at what the mod loses by it
first (a recipe players need is a reason to patch or drop the mod, not to list it), then add the file to the
known pattern in all three scripts. `tests/test_hosting_smoke.py` fails when the three differ, and runs each
script's lines against sample log lines: add one there too.

On macOS or Linux, unzip the same way and run `sh start.sh` in the folder: the first run exercises the
PowerShell bootstrap too (uninstall or hide `pwsh` from the `PATH` to test the download).

To test the Docker setup locally (Linux, or Docker Desktop on Windows/macOS), with no other server on
25565:

```sh
python tools/build.py
rm -rf /tmp/monkey-docker && mkdir -p /tmp/monkey-docker
unzip -q dist/MonkeySMP-Server-*.zip -d /tmp/monkey-docker
cd /tmp/monkey-docker/MonkeySMP-Server/docker
printf 'EULA=TRUE\nOWNER=YourName\nMEMORY_GB=4\n' > .env
docker compose up -d --build      # --build picks up Dockerfile changes
docker compose logs -f            # wait for "Done (", then Ctrl+C
docker compose down               # must log "All dimensions are saved"
```

The world, `java/` (the Linux build) and the downloaded PowerShell end up in
`/tmp/monkey-docker/MonkeySMP-Server`, exactly where a native run puts them.

Open a PR. CI checks every push to it and boots the release on clean runners when the change can break the
boot (`python tools/checks.py --boots` decides; Windows minutes count double and macOS 10x on this private
repo, and the included minutes ran out in October 2026):

| Job | Runs on | What |
|---|---|---|
| Checks, build | every push and PR | `tools/checks.py --strict` (ruff, pytest, `validate.py`, `datapacks.py --check`, `dash -n`, Pester on PowerShell 7, the site: bun install, lint, typecheck, unit tests, build), pytest again on Python 3.11 (the oldest the tools support, Debian 12's), `build.py` |
| Linux (native) | PRs out of draft that touch `package/`, the build (`build.py`, `repo.py`) or the boot tests; pushes to `main` that do; tags; manual runs | unzip, boot with the `.sh` launchers (PowerShell bootstrap included), check every mod and datapack loads, stop |
| Linux (Docker) | as Linux (native) | the release folder under `docker compose` from `package/docker/`: reaches "Done", shuts down cleanly |
| Windows | PRs out of draft that touch the installer, the manifest, `pwsh.lock`, `package/docker/`, the launchers (`.bat`), `player/`, the build or the PowerShell tests; tags; manual runs | PSScriptAnalyzer, Pester (with the player installer's), build, unzip, export a hosting bundle, boot with `tests/smoke.ps1`, check every mod loads, stop |
| Hosting bundle (Docker) | when Windows runs | the Windows-made hosting bundle under its own `docker-compose.yml` (`tests/hosting-smoke.sh`) |
| macOS | release tags and manual runs | native boot like Linux; start it with **Actions > CI > Run workflow** (or `gh workflow run ci.yml --ref <branch>`) before tagging if you touched the launchers, `monkey.sh`, `pwsh.lock` or Java |

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
`package/monkey/patches/<slug>/` plus `"patch": {"path": "patches/<slug>", "base_sha512": ...}` on
the entry, pinned to the original's hash. (Jars are zips, so mods and datapacks are patched the same
way.) A file identical to its original simply pins the original, with no patch. A patch may only
replace files that exist in the upstream file (adding or removing files fails the snapshot), and
patch folders no mod or datapack uses are deleted. `validate.py` checks that every patch matches its
entry's pinned hash, and `--online` applies each patch to the real download to prove it still fits.

The patch rules (which hash an entry is checked against, the patch id, and replacing files inside a zip) are
written twice, in `tools/patches.py`/`tools/entries.py` and in the installer's `Monkey.psm1`, because the
installer must stay PowerShell 5.1 (ADR-0003, ADR-0007). One golden fixture pins both:
`tests/fixtures/patch-golden/` holds a dummy `input.zip`, a patch in the real layout and the answers in
`expected.json`, which `tests/test_patches.py` and the `Patch rules golden fixture` block of
`tests/Monkey.Tests.ps1` both check. If you change a rule on purpose, change it on both sides, re-record with
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
`docs/PLAYERS.md`). `tools/client_env.py` decides which (`OPTIONAL_MODS`, plus every resource
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
Config defaults are curated by hand: copy changed configs into `package/monkey/defaults/` yourself, and
never copy files containing secrets (`server.properties` from a live server has the RCON password).

## Patches this pack carries

Each one is a whole replaced file under `package/monkey/patches/<slug>/`, pinned to the upstream jar it was made
against (ADR-0004). When `check_updates.py` reports a patched mod as "patched - re-snapshot needed", re-make the
patch against the new upstream file: carry the change below over, then check it is still needed.

| Mod | File | What the patch does, and why |
|---|---|---|
| `lootrestock` | `org/oldskooler/lootrestock/handler/ChestInteractionHandler.class` | A Java class, not a data file. Loot Restock checks whether a structure chest is empty the first time a player opens it, and that check rolls the chest's loot with no player, so vanilla's "a player opened a loot chest" advancement never fired and the weekly "Open 8 loot chests" challenge never counted. The patch answers "not empty" there without rolling (the code only runs for a chest that still has its loot table). Make it again with `python tools/lootrestock_patch.py LootRestock-<version>.jar OUT.jar`, put `OUT.jar` in the test server's `mods`, and snapshot; the script's docstring has the details. Loot Restock is GPL-3.0-or-later and its source is public, so shipping a changed class is fine as long as the change stays published: it is, in this repo. |
| `mace-limiterrr` | `com/maka/macelimiter/mixin/ItemStackMixin.class` | A Java class, not a data file. Mace Limiter frees a mace's slot when a stack's count is set to 0, and vanilla's `Inventory.add` does that to the undamaged stack it just took in, so picking a fresh mace up off the ground freed its slot and the cap didn't hold. One byte turns that route off. A mace that breaks and a dropped mace that's destroyed still free theirs, through the mod's other two hooks; one removed with `/clear` stays counted until `/macelimit reset`. Make it again with `python tools/macelimiter_patch.py macelimiter-<version>.jar OUT.jar`, put `OUT.jar` in the test server's `mods`, and snapshot; the script's docstring has the details. Mace Limiter is CC0-1.0, so shipping a changed class is fine. |
| `silvers_effects-library` | `overlay_26.2/data/s_effects_lib/function/technical/effects.mcfunction` | Upstream runs 97 commands for every loaded mob, every tick, so about 675 loaded mobs pass Minecraft's limit of 65,536 commands per tick, which cuts off whatever runs next. One command on top returns early for a non-player with none of the library's 19 `*_duration` scores. Players are never skipped, because the file's last line re-arms their tick advancement. 26.2 reads `overlay_26.2/`, not the `overlay_26.3/` the last patch replaced, so check the overlay when the Minecraft version moves. |
| `silvers_strength-restrictions-season-5` | `data/strength_restrictions/function/technical/main/tick/public.mcfunction` | Upstream calls a 41-slot macro 22 times per player per tick, 20 of them the same two calls repeated. Shared with other packs' argument sets, the macro is re-parsed on most calls. Each call now runs only when an `if items` check finds the item in a slot, and fire enchants are only removed from items that have them. |
| `silvers_strength-restrictions-season-5` | `data/strength_restrictions/item_modifier/mace/nerfed.json` | The mace cooldown turns a mace into a look-alike poisonous potato. Upstream sets the potato's marker through `set_components`, which replaces all of `custom_data` and wiped the id Mace Limiter keeps there, so that mace could never free its slot. `set_custom_data` merges the marker in instead. The tick function's `custom_data~` test still matches, and the marker stays on the mace after the cooldown, where nothing reads it. The merge also keeps the arena kit's `monkey_kit` mark, so the arena's clear of unmarked items no longer takes a kit mace at its first hit. |
| `silvers_strength-smp-season-5` | `overlay_26.2/data/strength_smp/function/technical/main/powers/spear.mcfunction`, `enchant/main.mcfunction` | The same guard on its 9 calls to that macro. No speed guard on the armor power: one on its `HurtTime` read stopped the hit counter ever starting (`tests/test_perf_patches.py`). |
| `silvers_strength-smp-season-5` | `overlay_26.2/data/strength_smp/function/technical/main/enchant/main.mcfunction`, `tick/public.mcfunction`, `powers/armor.mcfunction`, `predicate/armor_check.json`, `item_modifier/remove_enchants.json` | Upstream never undid two ultimates. The crossbow ultimate's `strength_smp:crossbow_ult` enchant stayed on the crossbow for good: `enchant/main` now takes it off every crossbow a player holds (all slots and the cursor) once their ultimate's duration is over, and the table clear removes it too. The armor ultimate's duration and cooldown were never counted down, so its knockback modifiers lasted until death: `tick/public` counts both down like the other powers and takes the modifiers off for every player, whatever their power (they now have their own names, `armor_ultimate-*`; the old shared `shield_ultimate-*` names come off as well, the knockback one only when no shield ultimate runs). The armor power no longer swaps diamond armor for netherite (one way, and rule 24 took it off), and its ultimate takes a full diamond or netherite set. Its hit counter lines are upstream's, unchanged. `tests/test_strength_ults.py`. |
| `silvers_effects-library` | `overlay_26.2/data/s_effects_lib/function/technical/tick/public.mcfunction` | Upstream encodes each whole player every tick to copy `Fire` into a score that only eternal flame and undead curse read. It now reads `Fire` only while one of those is running. |
| `dynamic-lights` | `data/dynamiclights/function/internal/main.mcfunction` | Lights update every other tick instead of every tick. TNT is still counted every tick and a fuse about to end forces a pass, because a light block stops explosion damage. Walking with a torch, the light can trail by one tick. |
| `warden-with-loot` | `data/warden_with_loot/advancement/deep_dark/spawn_warden.json`, `trigger_sculk_shrieker.json` | Two cosmetic `tick` advancements encode the whole player twice per player per tick: 15% of the main thread at 30 players. They now test the biome first, as conditions run in order. A warning raised just outside the deep dark unlocks on next entering it. |
| `silvers_effects-library` | `overlay_26.2/data/s_effects_lib/function/technical/tick/private.mcfunction` | Upstream scans every loaded entity 20 times a tick for two kinds of short-lived entity: twice for the stun boxes and 18 times for the eternal flame displays, one scan per lifetime step. One pass for each now runs the same function again as that entity, which runs upstream's lines for it alone. Its 18 duration countdowns (one tick in 21) stay upstream. |
| `colorful-trims` | `data/colorful_trims/function/tick.mcfunction` | Upstream scans every loaded entity 16 times a tick, `@e[type=item,name="<Color> Dye"]` once per dye, and rewrites each dropped dye every tick. One pass now picks out dropped dyes that aren't a trim material yet and runs the tick function again as each: its top lines set the material, as upstream did. A renamed dye on the ground now gets its material too; upstream only matched the default names, and it got one anyway once picked up. Upstream also gave a material to any dropped item renamed to a dye's name; the patch checks the item, not the name. |
| `glowing-glow-squids` | `data/gsg/function/light.mcfunction` | Each glow squid summoned its light marker and then found it with a world-wide `@e` scan: one scan per glow squid per tick. It now looks only where it summoned it. Only the new marker carries `gsg.light`, so it finds the same one. |
| `sulfur-cube-expansion` | `data/more_archetypes/function/tick.mcfunction` | Upstream scans every loaded entity about 45 times a tick: 33 `@e[type=sulfur_cube]` scans, one per archetype, 7 for the Herobrine mannequin and 2 for dropped Boomboxes, whose NBT it read for every item. One pass each for cubes, mannequins and Boomboxes (the item id checked before the NBT) now runs the tick function again as that entity, which runs upstream's lines for it in upstream's order. Each cube now runs all its checks before the next cube starts. Archetypes only read the cube's own body item, and cubes touch each other only through effects and damage nearby, so the order inside one tick shows no difference. The cube list is taken once per tick: a cube spawned by a resize gets its archetypes from the next tick, and a cube removed by another cube's explosion that tick still runs its lines once (upstream re-selected live cubes for each line). Both last one tick. The mannequin pass keeps upstream's position (no `at @s`), so it faces the same player. |

The last four are one pattern, for a tick function full of world-wide `@e` scans that each pick a few entities:
one scan picks them all and runs the same function again as each, so its top lines run as that entity. That
function is also the pack's tick function, run by the server with no entity, so a line that stops the entity must
never stop the server first: `tests/test_perf_patches.py` walks each one as the server to check it. Not patched:
Blaze Attack Animation and TNT Timer run one world-wide scan a tick when nothing is happening, and their other scans
only while a blaze attacks or TNT is lit. Cutting the blaze's idle scan would leave a fireball stuck in the air when
its chunk unloads mid-shot. Measured on a bare Fabric server with only these four mods and 1,725 loaded entities
(1,700 markers, plus a few cubes, glow squids and items), on the i7-8700K: 5.9 ms a tick upstream, 3.3 ms patched
(`tick query`, six 100-tick samples each). That bench is mostly markers, which no patched scan visits, so it
measures the saved scans, not a live tick: on the live server most entities are mobs, and Silver's Effects
Library still runs its effects function once per mob each tick (not patched). The full-pack `tools/loadtest.py`
run was not done before 3.2.0. Both passed the same checks: dropped dyes get their material, a glow
squid keeps one light, cube archetypes still apply, and the mannequin, Boombox, stun box and flame still despawn.

Measure a change like these with `tools/loadtest.py` (below): on an i7-8700K with 25 fake players the effects
patch took the command-limit hits from 3,359 a run to none. The typical tick didn't drop (132 ms before, 133 ms
after), because the unpatched runs were being cut off and the patched ones run everything. Strength SMP Season 5
needs no patch of its own: its enchant check runs from a placed-block advancement, not every tick, and it costs
about 23 ms a tick at 25 players (133 ms with it, 110 ms without). Check `players_online_min` in `summary.json`
before believing a run: it must equal the players asked for.

## Mods pinned by hand

`add.py` and `check_updates.py` only see releases Modrinth lists for the manifest's Minecraft version. A mod
that works on it but isn't listed for it is pinned by hand: the same entry `add.py` writes (`entries.added`,
from the Modrinth version), after a smoke test and a test join. `check_updates.py` never reports its updates,
so look at its Modrinth page when updating the pack, and when changing Minecraft version.

None since 3.0.0: every mod in the manifest is listed for 26.2.

## Our own mods, pinned from GitHub

A mod the owners wrote may be pinned from a release of its own GitHub repository instead of Modrinth
([ADR-0009](adr/0009-our-own-mods-may-be-pinned-from-a-github-release.md)). Today that is one mod, Patina & Chime
(`gr8monk3ys/patina-and-chime`), which is waiting for Modrinth's moderation. The repositories are listed in
`entries.GITHUB_PINS`; `validate.py` refuses a GitHub download from anywhere else, and refuses one in the players'
pack that isn't exactly the server's pin.

```bash
python tools/pin_github.py patina-and-chime v0.2.0 patina-and-chime-0.2.0+26.2.jar
python tools/validate.py --online
```

That downloads the jar from the release and writes its size and hashes in two places: the mod's entry in
`package/monkey/manifest.json` (`github` and `tag` where a Modrinth entry has `project_id` and `version_id`) and
the same file in `client/modrinth.index.json`, replacing the release pinned before. The mod adds blocks and
items, so both sides need the same build: a release that moves this pin is a new players' pack, and players who
haven't updated are refused with "registry entries that are unknown to this client".

Nothing else moves the pin. `check_updates.py` and `add.py` skip it, and a snapshot keeps it only while the jar on
the server is still the pinned file (a different jar under that name fails the snapshot: pin the new release
first). `pack_sync.py` refuses the jar like any other that Modrinth doesn't know. So for each new release of the
mod: publish it on GitHub, run the command above, then the smoke test and a test join.

Patina & Chime on this server (0.2.0, tested 2026-11-09 on a scratch 3.3.0 server):

- The shatter note (a note block on an amethyst block, tuned to its top note) breaks grown amethyst clusters
  within 8 blocks. It breaks them with no player behind it, so Open Parties and Claims has nobody to refuse: a
  note block outside a claim should reach clusters inside it. That follows from the mod's code; it was not tried
  inside a real claim. 0.2.0 has no switch for it. 0.2.1 adds one, the game rule `patinachime:shatter_note`
  (patina-and-chime pull request 6, not released yet). When 0.2.1 is out, move the pin to it and run
  `/gamerule patinachime:shatter_note false` once on the server; the value is saved with the world.
- Enchanting with amethyst shards is off wherever Easy Magic is installed, which is this server. Everything else
  the mod adds works next to the pack.

When Modrinth approves the mod, take the entry out of both files and pin it with `add.py mod patina-and-chime`,
so that the update check sees it again.

## Mods left out on purpose

The shared mod folder has these; the pack doesn't. Check the reason still holds before adding one in a sync. Since 3.0.0 the folder is the list (docs/ADMIN.md), so this is short.

| Mod | Why (measured 2026-10-11, 25 fake players, i7-8700K) |
|---|---|
| Improved Inventory Tabs | Not on Modrinth, so it can't be pinned (ADR-0002). |
| Arrow In The Knee (`aitk`) | Says it runs on servers, but a mixin into a client class stops one from starting. Client pack only. |
| PrickleMC, Crops Love Rain (NeoForge files) | The folder's `cropsloverain-3.2.1.jar` is the NeoForge build, and PrickleMC's NeoForge jar sits next to its Fabric one. The pack has the Fabric build of each. |
| Vanilla Permissions (0.3.6+26.1.2) | Shipped in 2.5.0 and 2.6.0, then removed: measured 2026-10-26 (fake players on land, i7-8700K), 10 players took 1,081 ms per tick with it and 64 ms without, 18 players 986 ms and 142 ms. It checks each entity selector a player's command uses against the whole command tree (`CommandDispatcher.getPath`, from `ArgumentPermission.validate`), and the pack runs advancement functions as each player every tick. Its job, ranks granting vanilla commands, went to ops (docs/ADMIN.md, "What needs op"). Measure a newer version the same way before adding it back. |

After a sync, launch the client pack and join a test server before releasing: CI boots the server but can't
start a game client, and a mod on one side only shows up as "registry entries that are unknown to this client".

## Shelved mods

Mods that were in a release and that the owners took out for now. Each keeps its exact manifest entry here, so
bringing it back is a copy: paste the entries into `mods` in `package/monkey/manifest.json` (it's sorted by slug),
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
   (`site/src/content/rules.tsx`) and "How does trading work?" (`site/src/content/front.tsx`) on the site, and
   the shop lines in `docs/PROMOTION.md`'s drafts. Drop the "shelved" notes in `docs/ADMIN.md` ("Shops") and `docs/LIVE.md` ("Shops in claims").
4. Add a `site/src/content/changes.mdx` entry for players, and once that release is live, run
   `deploy/shops-claims.sh` on the VPS (`docs/LIVE.md`, "Shops in claims").

## Tests

```bash
pip install pytest ruff tzdata   # tzdata: Windows has no time zone database of its own
python tools/checks.py            # ruff, pytest, validate.py, datapacks.py --check, dash -n, Pester, site
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
starts an installed copy of the package (the one the smoke test above leaves in `$env:TEMP\monkey-test`),
spawns fake players with [Carpet](https://modrinth.com/mod/carpet) over RCON and records tick times plus a
CPU profile of the main thread:

```powershell
python tools/loadtest.py $env:TEMP\monkey-test\MonkeySMP-Server --carpet C:\Downloads\fabric-carpet-26.2.jar --players 25
# what one mod costs: the same run without it (and its libraries)
python tools/loadtest.py $env:TEMP\monkey-test\MonkeySMP-Server --carpet C:\Downloads\fabric-carpet-26.2.jar --players 25 --without silvers_strength-smp-season-5
```

Results go to `<copy>\loadtest\<name>\`: `summary.json` (mean and typical tick time, TPS, the slowest ticks, how often the 65,536-commands
limit was hit), `samples.jsonl`, `profile.txt` (which mod and which methods the main thread spent its time
in) and `perf.txt` (Minecraft's own 10-second profile from halfway through: the tick by section, entity type
and datapack function). `--scenario walk` or `explore` measures world generation instead of the steady cost. Run on an idle
machine and compare runs made on the same copy: fake players stand in for real ones but don't send network
traffic, and walk/explore change the world for every later run. The numbers in docs/ADMIN.md ("How many
players") came from this harness on an i7-8700K.

## Releasing

0. If the staff page's Mods tab lists "Players' pack: waiting for a release", bring the owner's mod changes into
   the repo first: `python tools/pack_sync.py --ssh HOST` (add `--dry-run` to only look, `--include-off` to also
   take out mods that are only turned off, `--pr` for a draft pull request). It reads
   `server/.monkey-pack-changes.json` over SSH, pins the server's exact Modrinth files in
   `client/modrinth.index.json` and `package/monkey/manifest.json` (or drops them), runs `validate.py` and
   re-records `tests/fixtures/client_mods.json` when the pack gained or lost a mod. A jar Modrinth doesn't know,
   a split client/server jar or a patched mod is refused: do those by hand. Merge that pull request before the
   steps below; the release then takes the pack to players (docs/LIVE.md, "The staff page").
1. Bump `version` in `package/monkey/manifest.json` (semver: patch = plugin bumps, minor = new content,
   major = new Minecraft version or a world reset).
2. Add a `## [x.y.z]` section to `CHANGELOG.md`. If players will notice anything (rules, mods, the client
   pack, the wardrobe, events), date its entry at the top of `site/src/content/changes.mdx` too, in players' words
   (`docs/ADMIN.md`, "Telling players what changed").
3. Put the new player files on the site, since the GitHub releases are private and players download the pack
   from there: `python tools/build.py`, replace the files in `site/public/pack/` with
   `dist/MonkeySMP-Client-X.Y.Z.mrpack` and `dist/MonkeySMP-Player-X.Y.Z.zip` and point `MODPACK_URL` and
   `INSTALLER_URL` in `site/config.json` at them. `validate.py` fails while the site serves another version's pack.
   (Once the pack has its Modrinth project, `MODPACK_URL` points there and this step goes.)
   Between releases, when the live server gains a mod players need and no tag may go out yet, the site can serve a
   rebuild of the same version: `python tools/build.py --site-build LABEL` names the files and the pack
   `X.Y.Z-LABEL`. Never attach those to a release; the next release's pack replaces them, and its redirects in
   `site/vercel.json` come out then too.
4. Merge to `main`, then tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
5. Put the client pack on Modrinth. The Release workflow's `modrinth` job does it when the repo secret
   `MODRINTH_TOKEN` is set; otherwise run `python tools/modrinth.py` from a checkout of the tag, with the token in
   `MODRINTH_TOKEN` ([MODRINTH.md](MODRINTH.md#publishing-a-version)). It uploads nothing when the release
   left `client/` alone, and moves the server listing to the newest version.

The release workflow re-runs CI (including macOS), refuses to publish if the tag and manifest version differ, and attaches
`MonkeySMP-Server-X.Y.Z.zip`, `MonkeySMP-Client-X.Y.Z.mrpack` and `MonkeySMP-Player-X.Y.Z.zip`.

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
`dist/MonkeySMP-Server-X.Y.Z.zip` somewhere temporary and run `./tests/smoke.ps1 -Root <that folder>\MonkeySMP-Server -MemoryGB 4`.
Do it right after pushing the tag: the live server deploys a new tag in its next deploy window (docs/LIVE.md)
whether or not the release exists, and players need the new pack by then.

## Changing Minecraft version

Every plugin, mod and datapack needs a build for the new version. `check_updates.py` only looks within
the pinned version, so upgrade a server by hand and run `snapshot.py` against it (it takes the Minecraft
version from the server, and re-reads the world settings from `server.properties` because the version
changed). Expect world-gen changes to affect new chunks only. Switching between Paper and Fabric works
the same way: snapshot a server of the new type.
