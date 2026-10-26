# Changelog

## [Unreleased]

- Fix: Chunky pre-generation resumes after a restart. `config/chunky/config.json` ships with `continueOnRestart`
  on (Chunky's own default is off). Defaults only reach new servers: on an existing one, run `chunky continue`
  after a restart (docs/LIVE.md).
- The live map no longer shows where players are: `config/bluemap/plugin.conf` ships with
  `live-player-markers: false` (and `skin-download: false`, which only fed the markers), since the map is
  public and raiding is allowed. An existing server keeps BlueMap's own file; docs/ADMIN.md "The live map"
  says how to switch it off there.
- Docs: pre-generation no longer widens the border. docs/ADMIN.md and docs/LIVE.md said to set it to
  10000-12000 wide first, which undid Season I's 2500 start (Rule 25) and the border acts. Chunky now
  centres on the border (`chunky worldborder`; its own default is 0,0, while the border is centred on spawn)
  and generates out to the season's largest border plus the view distance.
- The live map stops at the world border instead of showing all the land Chunky generated for later border
  acts. `config/bluemap/maps/` ships with each map's `render-mask` on Season I's starting border (2500 wide
  around spawn, 312.5 in the Nether; the End has none), and the new `tools/map_border.py` fits the masks to
  the border saved in the world after each border act. Then `bluemap reload` and `bluemap purge <map>`
  (docs/ADMIN.md, "The live map"; docs/SEASONS.md's border acts now include it). Defaults only reach new
  servers: on an existing one, run the tool once.
- Fix: the Nether map shows the caves instead of the bedrock roof. Incendium makes the Nether 192 tall, and
  BlueMap's own ceiling cut stopped at y 127; the shipped `world_the_nether.conf` cuts everything from y 90 up.
  On an existing server, delete `max-y: 127` from that layer (docs/ADMIN.md, "The live map").
- Live server: the public map moves to https://map.monkeysmp.lscaturchio.xyz, served by Caddy with a Let's
  Encrypt certificate in front of BlueMap, which is now published on 127.0.0.1 only (`MAP_PORT`). The site
  links there, and port 8100 is no longer opened (docs/LIVE.md, steps 2, 5, 8 and 9).
- Live server: **off-site backups**. Every hour `realms-backup.timer` sends the live `server/` folder, encrypted,
  to a Cloudflare R2 bucket with restic, between `save-off` / `save-all flush` and `save-on` (saving comes back on
  also when restic fails, hangs or is killed). It leaves out what the installer downloads again (jars, libraries,
  logs, BlueMap tiles), keeps 48 hourly, 14 daily, 8 weekly and 6 monthly snapshots, and reads back 5% of the
  stored data after each run (`restic check --read-data-subset=5%`). It posts to the Discord webhook when backups
  fail and when they work again. The keys and the restic password go in a root-only `/etc/realms-backup.env`
  (`deploy/realms-backup.env.example`), and the password is kept off the VPS too. docs/LIVE.md covers setup,
  restores, the cost and a monthly restore drill on the home PC, which also rehearses the playit fallback.
- Live server: deploys keep only the newest 3 world backups in `backups/` (`KEEP_BACKUPS` in
  `/etc/realms-deploy.env`; was 14), since R2 now holds the history.

## [2.4.1] - 2026-10-25

Fixes and live-server tooling. Same Minecraft (26.3), mods, client pack and world as 2.4.0: hosts unzip over
2.4.0; players need nothing new.

- Fix: Arena Glory no longer leaves a death corpse wearing the kit inside the arena, so nobody loots a second
  kit. The arena tick and the between-rounds clear remove `player-death-corpses` mannequins in the radius.
- Live server: updates wait for a deploy window. Set `DEPLOY_WINDOW` (e.g. `04:00-05:00`) and `DEPLOY_TZ` in
  `/etc/realms-deploy.env` and a release tagged during the day goes live at 4 AM; `realms-deploy.sh --now` still
  deploys right away, and `--status` says whether the window is open. The first deploy on a new machine doesn't wait.
- Live server: the Discord "back up" message says to update the modpack only when the pack really changed, not
  on every release (each release bumps the pack's version number, which doesn't stop an old pack from joining).

## [2.4.0] - 2026-10-25

Monkey SMP: the new name, the Season I rules, event tooling and the wardrobe. Same Minecraft (26.3), mods and
world as 2.3.0: hosts can unzip over 2.3.0 and keep their world. Players update the client pack (it adds the
wardrobe resource pack).

- New: the **live server** setup in `deploy/` (`docs/LIVE.md`): a VPS pulls and deploys the newest release tag,
  with world backups, a chunky pregen and the public site.
- The GitHub repo is now **gr8monk3ys/monkey-smp-server** (was `the-realms-server`). GitHub redirects the old
  URLs, so existing clones, release links and installers keep working; update a clone's remote with
  `git remote set-url origin https://github.com/gr8monk3ys/monkey-smp-server.git`.
- New: a **server icon**, the Monkey SMP monkey in the multiplayer server list. It ships in `defaults/`, so it is
  copied only where the server has no `server-icon.png` yet; a host's own icon is kept. Logo, banners and the
  trailer are in `marketing/`.
- New: **event tooling**. The `realms-events` data pack (made by `tools/events.py`) runs Arena Glory (join,
  kits, Strength held at +3, drops cleaned), the Anarchy and Faction Raid timers, official faction flags,
  event books, the Season Cup and an attendance count; `/function realms:events/help` lists the commands.
  `tools/block_wheel.py` draws Build Battle blocks from a published seed. See the Events section of `docs/ADMIN.md`.
- Docs: `docs/SEASONS.md`, the plan for seasons and events. It covers 12-week seasons in acts (border growth, Dragon Night,
  Netherite age, a finale), one event a week from a catalog (KOTH, supply drops, bounties, tournaments), what
  carries over between seasons, and the research behind it. The owners' three pillar events (Build Battle with a block wheel, Faction Raid
  capture the flag, Arena Glory kit combat) run every season and score a faction Season Cup, plus
  Anarchy (90 minutes of suspended combat rules when the End opens; griefing, cheating and conduct rules stay).
- The server is now called **Monkey SMP** (was The Realms): server list message, window titles, the launcher
  profile, the client pack and the site. Download names (`TheRealms-*`), the `.the-realms` game folder and the
  backup task keep their old names, so updating needs nothing new. The uninstaller is now "Uninstall Monkey SMP.bat".
- New: the **wardrobe**, cosmetic skins for swords and helmets (`/trigger wardrobe`), unlocked by days played,
  tenure, invites, supporter tier or being a founder. Look only: no damage, armor or durability changes.
- New: the server enforces the Season I rules it can (two data packs from `tools/rules.py`): a 2500 x 2500
  border centred on spawn, set once (the Nether's at 1:8); the launch hour (`function realms:rules/launch`
  closes PvP and the Nether for an hour, the End stays closed until `function realms:rules/open_end`); no
  Netherite armor until `datapack disable "file/realms-no-netherite-armor"`; Fire Aspect and Flame disabled.
  Factions (Open Parties and Claims parties) hold at most 4 players on new installs. See the admin notes
  in `docs/RULES.md`.
- New: `tools/retention.py` reports D1/D7/D30 return rates and weekly players from the server logs.

## [2.3.0] - 2026-10-11

Host the server on a Mac, on Linux or with Docker. Same Minecraft (26.3) and world as 2.2.x: hosts can unzip
over 2.2.x and keep their world. Players reinstall the client pack (the mod list changed).

- New: the server zip runs natively on **macOS** (Intel and Apple Silicon) and **Linux** (x64 and arm64).
  On a Mac, double-click "Start Server.command"; on a Mac or Linux, `sh start.sh`. `stop.sh`, `backup.sh`,
  `add-player.sh` and `prepare-for-hosting.sh` do what the .bat files do on Windows. Nothing to install
  first: Java for that system is downloaded and hash-checked like everything else, and so is PowerShell 7
  (about 70 MB) if it isn't installed, because the same installer as on Windows runs it (ADR-0007).
- New: **Docker**. The `docker` folder in the server zip runs the server in a container: put `EULA=TRUE`
  and `OWNER=<your Minecraft name>` in `.env`, then `docker compose up -d`. The image holds no Minecraft
  files; it uses the release folder, so the world and backups are the same as in a native run.
- Prepare for Hosting now works on a Mac or Linux too (`sh prepare-for-hosting.sh`). A Linux VPS no longer
  needs it: run the release there natively or with Docker. Panel hosts (Pterodactyl and the like) still
  use the hosting zip.
- Windows hosts: the launchers work as before.
- Docs: Mac and Linux players import the .mrpack into Prism Launcher or the Modrinth App (the player
  installer stays Windows-only).
- CI also boots the server natively on Linux, with Docker on Linux, and natively on macOS (macOS on
  releases and manual runs).
- **Mod list synced** with the shared folder: 142 server mods, 213 client files. New on the server: Epic
  Dungeons, Moog's Voyager Structures, Grand Capitals, Better Underwater Ruins, Slabs & Stairs, Copper Rails,
  More Villagers, More Mobs, Stormie's Spiders, Sulfur Caves Plus and about 20 smaller ones. Gone: Dungeons and
  Taverns (the base mod; its structure overhauls stay) and Epic Structures: Villages. In a world that already has
  Dungeons and Taverns buildings they stay, and the log says "Unknown structure start: nova_structures:..." when
  it loads them. **Players must reinstall the client pack** (about 520 MB).
- Left out of that list, with the measurements in docs/ADMIN.md: Slabbed, The Sift and Amethyst Nether. Also
  not included because they aren't on Modrinth: Just Enough Professions, Improved Inventory Tabs, Villager News.
- **Performance.** 2.2.2 said it was ready for 25 players; load tests on an i7-8700K gave about 4 TPS. Now, on
  the same PC: 10 players at 20 TPS and 25 at about 13 (docs/ADMIN.md, "How many players"). What changed:
  - Two patches inside the Strength SMP mods, which ran tens of thousands of commands every tick and went past
    Minecraft's 65,536 limit (docs/MAINTAINING.md, "Patches this pack carries"). Strength SMP itself is unchanged
    apart from noticing a newly placed enchanting table or anvil within half a second instead of at once.
  - New: ServerCore. Mobs far from players tick less often, and while the server is behind it lowers mob caps
    and tick distances, then raises them again. Its config is a first-run default
    (`server\config\servercore\config.yml`).
  - `tools/loadtest.py` re-runs the measurement (docs/MAINTAINING.md, "Load testing").
- Memory: the server takes at most 8 GB (5 GB on a 16 GB PC, 6 on 24, 8 from 32 up). 2.2.2 took up to 10 GB,
  but a 25-player test peaked at about 4.3 GB in use, and the whole heap is reserved at start. The
  "Prepare for Hosting" bundle defaults to `MEMORY_GB=6` (was 10), which fits an 8 GB VPS, and its
  instructions say 6 GB or more for hosting panels (8 for a big group).
- "Schedule Backups.bat" logs every run to `scheduled-backups.log`, errors included, and now works from a
  folder with a long path. Backups run at 6 AM and 6 PM. Run it again to update an existing task.
- docs/ADMIN.md: the Nether pre-generation numbers are 1/8 of the Overworld's (radius 625, border 1250).
- `validate.py` also checks the docs, the changelog and the package scripts for control characters.

## [2.2.2] - 2026-10-06

Ready for a bigger group (about 25 players). Same Minecraft (26.3), world and client pack: hosts unzip over
2.2.x and keep their world; **players don't need to reinstall** (spark is server-only).

- Fixed: READ ME FIRST's voice chat step showed a garbled path; it is
  `server\config\voicechat\voicechat-server.properties`.
- Memory: the server now takes up to 10 GB (6 GB on a 16 GB PC, 8 on 24, 10 from 32 up; was 3 to 6 GB).
  The "Prepare for Hosting" bundle defaults to `MEMORY_GB=10` (was 4).
- `max-players` is 30 (was 20) and BlueMap renders with 1 thread (was 3) so the map doesn't slow the game.
  These are first-run defaults: **an existing install keeps its own `server\server.properties` and
  `server\config\bluemap\core.conf`**, so change those two values there by hand.
- Added: spark, the performance profiler (`spark tps`, `spark profiler`). 115 server mods.
- New "Schedule Backups.bat": a Windows scheduled task backs up the world every 12 hours.
- READ ME FIRST and docs/ADMIN.md: what to do before a big group joins (memory, pre-generating the world with
  Chunky plus a matching world border, spark, off-site copies of backups).
- `validate.py` now fails if a READ ME contains a control character, so a garbled path can't ship again.

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
