# Changelog

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
