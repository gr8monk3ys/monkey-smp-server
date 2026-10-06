# Changelog

## [2.2.1] - 2026-10-06

Docs only: same mods, server and world as 2.2.0. Nobody needs to reinstall.

- Fixed: the player READ ME and docs said the player download is about 1 GB; it is about 450 MB.

## [2.2.0] - 2026-10-06

Synced with the updated mod list. Same Minecraft (26.3) and world seed: hosts can unzip over 2.1 and keep
their world; players run the new player installer (or import the new .mrpack).

- Added: Craftable Cobwebs, Epic Structures: Villages, Players Drop Heads (replaces Just Player Heads),
  Very Many Players (server performance), Visible Traders.
- Removed: Dragonkind Evolved, Dungeons and Taverns Mineshaft Overhaul, Just Player Heads.
  Structures they already generated stay in existing worlds.
- Updated: Silver's Effects Library 2.10 (still needs our small compatibility patch, now made against
  2.10), Strength Restrictions 1.4 (fixed upstream, so its patch is gone), Xaero's Minimap and World Map,
  JEI, Punchy, Puzzles Lib.
- 114 server mods, 170 client files. A client with this pack joined a server with these mods.

## [2.1.0] - 2026-10-06

Easier for players: no Modrinth App or Prism needed.

- New download for players: **TheRealms-Player-2.1.0.zip**. Double-click "Install for Minecraft Launcher.bat"
  and it sets up Fabric and every mod, resource pack and shader (downloaded from Modrinth, each file
  hash-checked) in a separate folder, then adds a "The Realms" installation to the normal Minecraft
  Launcher. Running it again updates; "Uninstall The Realms.bat" removes it.
- The player zip also contains the .mrpack for Modrinth App / Prism users, and a plain-language READ ME.
- New docs/SHARING.md: which file to send to whom, with copy-paste messages for the host and players.
- playit.gg instructions now cover the second tunnel voice chat needs.

## [2.0.0] - 2026-10-05

The server moves from Paper 26.1.2 to **Fabric 26.3** so the whole mod list runs (ADR-0005). This is a
new world: unzip 2.0 into a new folder, and every player needs the 2.0 client pack.

- Fabric 26.3 (loader 0.19.5) with 112 server mods, including Moog's structures, Naturalist, Variants &
  Ventures, Easy Magic, More Babies, Nature's Compass, Dragonkind Evolved, Terralith, Tectonic (Overkill),
  Incendium, Nullscape, Dungeons and Taverns, Strength SMP S4 and C2ME.
- Factions are parties, allies and land claims (Open Parties and Claims); Towns & Nations wars are gone.
  Ranks via LuckPerms, rollbacks via Ledger (moderators can't purge its logs), live map via BlueMap.
- New pinned world seed; spawn is protected by vanilla spawn-protection (48 blocks).
- Client pack for 26.3: 167 mods, resource packs and shaders. Required to join.
- New: "Prepare for Hosting.bat" builds an upload-ready zip for online Minecraft hosts and Linux VPSes
  (start.sh, docker-compose.yml, HOSTING.txt) (ADR-0006).
- The installer refuses to install 2.x over a 1.x world, so the two can't get mixed up.
- Left out (not on Modrinth, so they can't be pinned): Villager News, Improved Inventory Tabs,
  JustEnoughProfessions, Bliss shader.

## [1.1.0] - 2026-10-05

Synced with the updated mod list.

- New datapacks: Dragonkind Evolved (End battle rework), Player Corpses, DnT Pillager Outpost Overhaul,
  DnT Stronghold Overhaul. New structures only appear in newly generated chunks.
- Client pack: added Cape Provider (replaces Capes), Reach Behind and MidnightLib; removed AFK Cinematics,
  FWA, Inventory Particles, Presence Footsteps and Punchy to match the list.
- Kept the Epic Structures packs and Spawn Animations on the server (their list replacements are
  Fabric-only and can't run on Paper).
- Update check no longer proposes re-listed files or downgrades from a newer pre-release pin.
- Installer: file names with [ ] (like Player Corpses') no longer break the download.
- RCON (Stop Server, Add Player, backups) reconnects if a server still warming up drops it.
- Known issue: Silver's Custom Effects Library logs parse errors on 26.1.2 (some of its effects
  don't work); this predates 1.1.0 and is an upstream compatibility problem.
- Installer and tools split into testable modules (Pester + pytest), patches pinned to their upstream
  file, glossary and ADRs.

## [1.0.0] - 2026-10-04

First packaged release of The Realms.

- Paper 26.1.2 build 74 on Eclipse Temurin JRE 25.0.4.1.
- 20 plugins: Towns & Nations (+ BlueMap addon, SphereLib), LuckPerms, EssentialsX (+ Spawn), VaultUnlocked,
  PlaceholderAPI, WorldGuard, FastAsyncWorldEdit, CoreProtect, PvPManager, CharacterCard, ChestShop, Chunky,
  Distant Horizons Support, BlueMap, Simple Voice Chat, TAB, FancyNpcs.
- 24 datapacks: Terralith, Tectonic (Terratonic), Incendium, Nullscape, Structory, Dungeons & Taverns + 5 overhauls,
  Towns & Towers, Explorify, Epic Structures (5), Spawn Animations, Strength SMP S4 + Restrictions and Silver's libraries.
- Pinned world seed; spawn safe zone (no PvP/explosions); wars allowed 10:00-23:30 with 30 min notice.
- Ranks: default, builder, moderator, admin.
- One-click Windows launcher: downloads and hash-checks everything, EULA prompt, owner becomes admin,
  backups, whitelist helper.
- Client modpack (.mrpack) with 129 mods/resource packs/shaders.
