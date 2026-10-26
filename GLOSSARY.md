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
The optional set of mods, resource packs and shaders a player installs to get the intended look and feel.
_Avoid_: modpack (alone), client mods

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

## Lifecycle

**Install**:
Bringing a server folder in line with a release's manifest; running it again changes nothing unless the release changed.
_Avoid_: setup, sync, deploy

**Managed file**:
A file an install placed in the server folder and may later replace or remove; every other file belongs to the host.
_Avoid_: installed file, tracked file

**Snapshot**:
Capturing what a running server or player instance actually uses back into the manifest or client pack.
_Avoid_: export, import, scan

**Spawn safe zone**:
The protected area around the world spawn where players can't fight or blow things up.
_Avoid_: spawn protection (Minecraft uses that for something else)
