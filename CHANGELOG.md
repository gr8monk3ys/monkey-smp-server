# Changelog

## [Unreleased]

X-ray protection and moderation tools, more wardrobe skins and the season-end tools. Players update the
client pack for the new skins' textures; everything else is server only.

- New: **AntiXray** (DrexHD) is on by default (`defaults/config/antixray.toml`). Buried ores are never sent to
  players: in the Overworld they hide among fake ores, in the Nether and the End they show as netherrack or end
  stone. It covers Skniro's Nether and End ores too, which aren't in the `c:ores` tag. This is what now enforces
  B15 (x-ray), B17 and B19 (`docs/RULES.md`).
- New: **MinerTrack**, alert only (`defaults/config/MinerTrack/config.yml`). It flags players who mine from one
  buried diamond, emerald or ancient debris vein straight to the next, and alerts moderators at VL 2, 4 and 5
  instead of kicking. For x-ray that gets past AntiXray (a cracked seed, say). ADMIN.md also has the saved Ledger
  query for diamond-ore breaks.
- New: a test that the world seed never ends up in what players get (the client pack, the player zip, the site,
  RULES.md). It isn't in any of them today; only the server zip has it.
- New: **BanHammer** (warn, mute, kick, timed and permanent bans, each with a reason and a history), **Vanish** and
  **InvView** (look into a player's inventory and ender chest). The rules' "temporary ban (1 to 7 days)" is now
  `tempban NAME 3d reason`. See "Moderation" in `docs/ADMIN.md`.
- New: **Vanilla Permissions**, so LuckPerms ranks can grant vanilla commands. Builders' `/gamemode` and
  moderators' teleport and whitelist now work without op.
- Ranks: moderators get the BanHammer, Vanish and InvView commands (InvView look only); admins can also move items
  in other players' inventories. Rank files are only copied where missing, so an existing server keeps its old
  ranks: see "Existing servers" under "Moderation" in `docs/ADMIN.md`.
- Changed: Distant Horizons on the server no longer builds or sends LODs (`defaults/config/DistantHorizons.toml`:
  `synchronizeOnLoad` and `enableRealTimeUpdates` off, `generatorPlan = "DISABLED"`). Its LODs came from the real
  world, so they carried every real ore, buried or not, past AntiXray. Players still see LODs of land they have
  walked past, but no longer get far terrain from the server, and the server saves the CPU it spent generating it.
  A server set up before this keeps its old file: see "Distant Horizons stops sending its own LODs" in
  `docs/LIVE.md` (the steps work on any server). How to switch it back is in `docs/ADMIN.md`.
- Live server: a **daily restart** at 4:30 AM Pacific (`realms-restart.timer`, `realms-deploy.sh --restart`), with
  the usual 5- and 1-minute warnings in chat. It shares the deploy lock, skips a server a deploy restarted that
  morning (`RESTART_MIN_UPTIME`, 6 hours), and posts a `spark health` link from just before the restart, so memory
  use can be compared from day to day.
- Live server: a **weekly update check** on Mondays (`realms-updates.timer`): `tools/check_updates.py` against the
  live release, posted to Discord with the report attached, while the GitHub Actions check can't run.
- Live server: **`deploy/upgrade-2.5.0.sh`** does this release's one-off VPS steps in one go: the Distant Horizons
  change above (under the deploy lock, with warnings in chat and a copy of the old file), python3 for the update
  check, and the two timers. It skips steps already done, `--check` only reports, and it reads no secrets. See
  "One-off steps when upgrading" in `docs/LIVE.md`.
- Daily restart, update check and load-test results go to `STAFF_WEBHOOK_URL` in `/etc/realms-deploy.env` when it
  is set (a staff-only channel), else to `DISCORD_WEBHOOK_URL`.
- Live server: **`deploy/realms-loadtest.sh`** measures what the VPS can carry: `tools/loadtest.py` with 25 fake
  players on a throwaway copy of the live server (no Tebex, no published ports), with the live server stopped
  and always started again. `tools/loadtest.py --spark` adds a spark profile of every thread, and `summary.json`
  now records ServerCore's status. docs/LIVE.md has how to run it, the decision rule (about 40 ms at 25 players),
  uptime monitoring from the home PC, and the DDoS plan (a question for Reizor first, TCPShield if needed).
- New: the client pack can go on **Modrinth** as the Monkey SMP modpack, with a Modrinth server listing that
  links to it (`docs/MODRINTH.md`: the listing text, the owner's one-time setup, review times, and Modrinth's
  rule against listing paid-access servers). `tools/modrinth.py` uploads a release's `.mrpack` with the token
  from `MODRINTH_TOKEN`, skips a release that left `client/` alone, and keeps the server listing on the newest
  version. Every file in the pack is hosted on Modrinth, so nothing blocks publishing.
- Players: the Modrinth App is now the recommended install on every OS (`docs/PLAYERS.md`), and it updates the
  pack itself. The Windows installer for the normal Minecraft Launcher stays as the fallback. Until Modrinth
  approves the pack, Modrinth App players import the `.mrpack` as before.
- Releasing by hand while GitHub Actions doesn't run: `python tools/build.py --notes notes.md` writes the
  release notes the workflow wrote (the workflow now uses it too), and `docs/MAINTAINING.md` ("Releasing
  without Actions") lists the steps.
- New wardrobe skins: the Oathblades I, II and III at 1, 2 and 3 months of pass (the tenure ladder used to
  start at 6), Rallier at 3 events attended and the Plumed Helm at 10, and three holiday skins earned only
  by being at that holiday's event, never sold: Gravelight (Hallowtide), Midwinter Cap (Midwinter) and
  Solstice (Midsummer). Look only, like every skin; `tests/test_wardrobe.py` checks the new ones too. Players
  update the client pack for the new textures.
- The wardrobe menu has two pages (earned in game; pass and supporter), so it fits in open chat, and a player
  gets an "Unlocked ..." line in chat when the store, staff or an event raises their months, events or a
  holiday score (at their next login if they were offline).
- New: `tools/season.py`. `download` zips a season's final world for singleplayer and leaves out the Ledger
  database, mod server config and session files. `carry` writes a one-shot data pack into the next season's
  world that puts back every wardrobe score, hours played (as `rw.playbase`) and the supporter, title and
  champion teams.
- New: `function realms:events/season/lock` and `unlock`. The lock puts survival players in adventure mode
  with PvP off and peaceful difficulty, and holds across restarts.
- New: `tools/funnel.py` matches a Tebex payments export to the server logs: purchase, first join, 30 minutes
  played, D7 and renewal, with the month-2 renewal rate as the headline and a list of buyers who never
  joined. Payment exports are ignored by git (`*.csv`); the test fixture is made up.
- Fix: `tools/retention.py` reads 26.3's join lines (`System chat: NAME joined the game`), so it no longer
  reports zero players, and reads rotated logs in order (`-10` after `-9`).
- New: `site/changes.html`, the player changelog ("What changed"), seeded with the player-facing changes
  since 2.0.0.
- Docs: `docs/SEASONS.md` gains the holidays, Base of the Month, the season champion (a held faction name
  and a roster title), faction charters at sign-up, and the season-end runbook. `docs/RETENTION.md` gains
  the pass funnel and DMs to passes that show Ending in Tebex; `docs/ADMIN.md` the season and holiday
  commands and how to tell players what changed.
- Tests: `tests/smoke.ps1` checks its ports before it installs and again before it starts. If the game, RCON or
  map TCP port or the voice chat UDP port is already in use, it stops and names the port and what holds it (the
  process and PID, on Windows). Until now, a test server that already held UDP 24454 made the boot die a few
  seconds after "Done" (Simple Voice Chat 2.6.24 stops the server when it can't bind its port), and the test
  blamed RCON. If the server stops by itself after "Done", the test now says so and shows the end of its console
  output.
- Tests: new `-VoicePort` (default 24454) and `-MapPort` (default 8100) set the test copy's Simple Voice Chat
  and BlueMap ports, so test boots can run side by side. Nothing in the release changes.
- Fix: a smoke test re-run in the same folder no longer takes the previous boot's "Done" line for this one's:
  it ignores `server/logs/latest.log` until the new server has written to it.

## [2.4.2] - 2026-10-25

Live-server tooling and one server-only mod. Same Minecraft (26.3), client pack and world as 2.4.1: hosts
unzip over 2.4.1; players need nothing new. Default config changes reach only new servers; the entries
below say what to change on an existing one.

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
- Store: the prices and perks are settled before the first sale (ADR-0008). The 3-month pass is $14 (was
  $12), Crown's extra is a landmark it names each season instead of a vote (every pass holder votes on the
  twist), and priority slots aren't sold. docs/LIVE.md "The store" lists the Tebex packages, a 7-day trial
  on the monthly pass to test and switch on, and creator codes (20%, no buyer discount); docs/RETENTION.md's
  budget uses Tebex's real fees.
- Site: links work without JavaScript. `tools/site_links.py` writes `site/config.js`'s URLs into the pages,
  and validate.py fails when they drift. The site serves the client pack and player zip from `site/pack/`,
  since the GitHub releases are private, and validate.py checks they're the pinned version (a new release
  step in docs/MAINTAINING.md). The pricing section says what a PC needs and the 48-hour refund, the FAQ
  says 30 players, and the new `creators.html` has the creator code terms.
- docs/PROMOTION.md: the listing kit for free server lists and the Official Minecraft Server List, join
  addresses per channel (DNS records and how to count them), a creator outreach template and the plan for
  clips from real event nights.
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
- New server-only mod: [Hostname Catcher](https://modrinth.com/mod/hostname-catcher) 0.2 logs the join address
  each player came in through, and the new `tools/join_addresses.py` counts joins, players and new players per
  address from the server logs (docs/PROMOTION.md, "Counting joins per address"). It ships with
  `config/hostname-catcher.yml` letting every address in (the mod's own default turns away every real player).
  Modrinth lists it for 26.2 only, so it's pinned by hand after a test on 26.3 (docs/MAINTAINING.md, "Mods
  pinned by hand"). Players need nothing new: it isn't in the client pack.

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
