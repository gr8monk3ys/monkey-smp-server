# Monkey SMP

A Minecraft factions server packaged so that anyone can host it on Windows, macOS or Linux from a single download, and kept reproducible by pinning everything it runs.

Formerly **The Realms**. Only the name players see changed: code, folders, the `realms` command, the `realms:` data pack namespace, the `TheRealms-*` download names and the `.the-realms` game folder keep the old name so existing installs and the live deploy keep working.

## People

**Host**:
The person who runs the server, on their own computer or on a server they rent.
_Avoid_: admin, operator, server owner

**Owner**:
The Minecraft account given the admin rank and op status when a server is first installed; usually the host's own account.
_Avoid_: admin, host

**Player**:
Anyone who joins the server with Minecraft.
_Avoid_: user, client, member

**Rank**:
A named set of in-game permissions a player holds: default, builder, moderator or admin.
_Avoid_: role, group

## What ships

**Release**:
One numbered version of Monkey SMP, made of a server package, a player zip and a client pack built from the same manifest.
_Avoid_: build, version (alone)

**Server package**:
The small download a host unzips and starts the server from; it holds instructions and configuration, never third-party files.
_Avoid_: installer, bundle, modpack

**Player zip**:
The download every player gets: the client pack plus a one-click installer for the normal Minecraft Launcher and a plain-language guide.
_Avoid_: client zip, installer (alone)

**Client pack**:
The mods, resource packs and shaders a player installs to join: the required files the server needs, plus optional files for the intended look and feel.
_Avoid_: modpack (alone), client mods

**Optional file**:
A file of the client pack a player may leave out and still join (`"client": "optional"` in its index, from `tools/client_env.py`). Every other file is required.
_Avoid_: client-only mod (some optional mods also run on the server)

**Server listing**:
The server's entry in Modrinth's server discovery: its address and tags, and which version of the client pack (published on Modrinth as the Monkey SMP modpack) players get.
_Avoid_: server project, server page

**Manifest**:
The pinned list of every artifact a release's server needs, plus the world settings every copy shares.
_Avoid_: lockfile, config, dependency list

**Artifact**:
One downloadable file the server runs: the Java runtime, the server software, a mod, a plugin or a datapack.
_Avoid_: dependency, asset

**Mod**:
An add-on the Fabric server loads from its mods folder; many also have to be installed by players.
_Avoid_: plugin (that is the Paper kind), addon

**Manifest entry**:
The manifest's record of one artifact: where it comes from, what it is called on disk, and the hash it must match.
_Avoid_: pin, lock, package

**Upstream**:
The official source an artifact is downloaded from (Modrinth, PaperMC, Adoptium).
_Avoid_: mirror, CDN, registry

**Patch**:
A small set of file replacements applied inside one downloaded mod or datapack, tied to the exact upstream file it was made from.
_Avoid_: fix, override, mod

**Generated pack**:
A data pack (or the wardrobe's resource pack) written by `tools/datapacks.py` from the tables in a `tools/` generator; edit the generator, never the pack.
_Avoid_: hand-written pack, build output

**Defaults**:
The configuration a server starts with on its first install; once a file exists, the host's version wins.
_Avoid_: templates, config overrides

## Where it runs

**Platform**:
An operating system and processor pair the server package runs on natively: Windows x64, Linux x64 or arm64, macOS Intel or Apple Silicon. The manifest pins a Java runtime for each.
_Avoid_: OS (alone), target, arch

**PowerShell bootstrap**:
The first step on macOS and Linux: find PowerShell 7, or download the pinned portable copy into the server folder, so the same install as on Windows can run.
_Avoid_: installer, wrapper, launcher

**Docker setup**:
The `docker` folder in the server package that runs a host's own server folder in a container; its image holds no third-party files.
_Avoid_: Docker image (alone), container

**Hosting bundle**:
The zip "Prepare for Hosting" makes from an installed server folder, for online Minecraft hosts that only accept a finished server.
_Avoid_: export, server pack, server package

**Join address**:
A second hostname for the live server, one per place it's promoted (`yt.monkeysmp.lscaturchio.xyz`), with its own SRV and A records, so joins can be counted by where players found it (docs/PROMOTION.md).
_Avoid_: vanity domain, referral link, alias

**Timed job**:
A systemd timer on the live VPS that sends a tool's RCON commands to the server on the wall clock, under the deploy lock: the week (hourly), the supply drops (every 10 minutes) and the day (midnight UTC). Each is a thin `deploy/realms-<job>.sh` over `timed_job` in `deploy/lib.sh`, with `--check` and `--install`, and its tool has `commands` and `send`.
_Avoid_: cron job, scheduled task, timer (alone: the deploy, backup and standings timers do more than send commands)

## Lifecycle

**Install**:
Bringing a server folder in line with a release's manifest; running it again changes nothing unless the release changed.
_Avoid_: setup, sync, deploy

**Managed file**:
A file an install placed in the server folder and may later replace or remove; every other file belongs to the host.
_Avoid_: installed file, tracked file

**Saved world**:
What the tools read from a world folder's files (scores, parties and claims, each dimension's border), as the server last saved them (every few minutes, and when it stops), never asked of the running server. `tools/saved_world.py` reads it.
_Avoid_: live world, world state, save (alone)

**Season calendar**:
When a season happens, in Pacific time: its launch, the launch weekend (week 0), each week from its Monday at 12 AM, each week's Saturday (event night) and the weeknight drop nights, all worked out from the launch (week 1 starts the Monday after it). `tools/season_calendar.py` keeps it and every tool asks it; the website's launch time (`LAUNCH_AT` in `site/config.js`) must match it.
_Avoid_: schedule (that is the challenge rotation), season dates

**Server First**:
Being the first player on the server, this season, to reach one of the milestones in `tools/firsts.py` (enter the Nether, slay the dragon...). It is announced to everyone and held for the season; the most firsts earns the Pioneer title. A first is claimed; staff can reopen one.
_Avoid_: achievement, advancement (the game's own; a first is server-wide and only one player holds it), record

**Snapshot**:
Capturing what a running server or player instance actually uses back into the manifest or client pack.
_Avoid_: export, import, scan

**Spawn safe zone**:
The protected area around the world spawn where players can't fight or blow things up.
_Avoid_: spawn protection (Minecraft uses that for something else)

**Spawn NPC**:
The Guide or the Town Crier: an Easy NPC character at spawn that answers new players when no staff are on.
Staff place each one once per world from the `realms-npcs` data pack.
_Avoid_: bot, villager
