# Changelog

## [Unreleased]

### Added

- **Monkey SMP news**: one plain line in the public Discord channel for a rare Server First (the Nether, a
  raid, a mace, a beacon, the Wither, the End, the dragon, an elytra, full Netherite), the first on the server
  this season to finish a rare advancement (Monsters Hunted, A Balanced Diet, Adventuring Time...) or new
  factions: "Steve killed the Ender Dragon. First this season." At most a few a day and each once a season,
  read from the saved world every 10 minutes (`tools/news.py`, `deploy/monkey-news.sh`, `monkey-news.timer`).
  Off until the owner adds `NEWS_WEBHOOK_URL` on the VPS and installs the timer (docs/LIVE.md, "The news
  timer"). Not yet run against a live server.

## [2.9.1] - 2026-10-29

Season I's new date: it opens on Saturday 7 November, a week later. This must be live before Monday
2 November, when 2.9.0's calendar would start week 1 and the supply drops. The client pack's mods are the
same as 2.9.0's, so players don't need to update it. After it deploys, place the Town Crier again
(docs/ADMIN.md, "Spawn NPCs") and run `deploy/npc-claims.sh` once (docs/LIVE.md, "NPCs in claims").

### Added

- The Release workflow publishes the client pack on Modrinth after the GitHub release when the repo secret
  `MODRINTH_TOKEN` is set (it uploads nothing when `client/` didn't change, and only warns without the
  secret). The weekly update check runs `tools/modrinth.py --check` and says in its issue when Modrinth's
  newest version holds a different pack from main's.

### Changed

- Season I opens on Saturday 7 November 2026 at 5 PM Pacific (8 PM Eastern), a week later than 31 October.
  Week 1 starts on Monday 9 November, the finale is on 23 January 2027 and Season II is proposed for
  6 February. The launch weekend (Founder's Circlet) is 31 hours again: the clocks go back on 1 November, the
  week before. The holidays keep their dates, so Arena Glory I (Midwinter, 19 December) moves to week 6, the
  second border break to week 7 (26 December) and Build Battle II to week 8; the Town Crier says so. Release
  this before Monday 2 November, when 2.9.0 would start week 1, and place the Crier again after it
  (docs/ADMIN.md, "Spawn NPCs").

### Fixed

- Players can talk to the Guide and the Town Crier again. Spawn's server claim also protected the NPCs, so a
  right-click got Open Parties and Claims' "You are not allowed to interact with this entity in this chunk";
  only ops could use them. `defaults/config/openpartiesandclaims-server.toml` now adds
  `"hand$easy_npc:humanoid"` and `"hand$easy_npc:humanoid_slim"` to `forcedEntityProtectionExceptionList`: anyone may right-click an Easy NPC in any claim with an empty hand,
  while the claim still protects its blocks and nobody can hit the NPCs or use items on them. On the live
  server, run `deploy/npc-claims.sh` once (one restart; docs/LIVE.md, "NPCs in claims"). Not yet tried in game.
- The update check's "Verify every pinned download" step piped into `tee` without `pipefail`, so a broken
  download never reached its issue. It runs under `bash` now.
- docs: LAUNCH.md put the R2 keys in `/etc/monkey-deploy.env` (the backup reads `/etc/monkey-backup.env`) and
  the store at `monkeysmp.tebex.io` (another server's); LIVE.md said the off-site copy covers `backups/` (it
  sends `server/` only).

## [2.9.0] - 2026-10-29

Season I's release: the season opens on Saturday 31 October (below), with six new season features. The
client pack's mods are the same as 2.8.0's apart from its version number, so players on 2.8.0 don't need
to update it (`tools/modrinth.py` uploads nothing, and the live server's Discord message asks nothing of
them).

### Added

- The Sunday standings post is now a short recap, "Monkey SMP Weekly": the final table, then a line each for
  the biggest mover, the top fighter, bounties claimed, land claimed, challenges done, event turnout and next
  Saturday's event, when there is something to say (`tools/recap.py`). Same webhook, same Sunday timer, still
  under Discord's 2000 characters. A week that closes before the launch (test play) is kept but no longer
  posted. `deploy/monkey-standings.sh preview` prints the recap as it would post now. Nothing to set up on the
  VPS: the first close after this release starts counting the week's challenges, land and events, so its
  recap leaves those lines out.
- **Server Firsts**: the first player on the server to reach each of 14 milestones (find a diamond, enter the
  Nether, find a fortress or a bastion, ancient debris, a trial vault, a mace, win a raid, defeat the Wither,
  light a beacon, enter the End, slay the dragon, an elytra, full Netherite once it is allowed) is announced to
  everyone and keeps it for the season. `/trigger firsts` shows who holds each. The most firsts at the season's
  end earns the `[S1 Pioneer]` title. A new data pack, `monkey-firsts` (`tools/firsts.py`); nothing counts
  before the launch. Not yet tried in game.
- **Season Wrapped**: after the finale, every player gets a page on the site about their season: hours and
  days played, PvP kills, weekly challenges, events, their faction's best weekly rank, their Server Firsts
  and their skins, rarest first. A shared link shows their own line in Discord. Anyone can ask staff for no
  page. Made by a maintainer tool, `tools/wrapped.py`, which also keeps a starting point at the launch so test
  play doesn't count. Not yet tried on a real season's world.
- **War and pacts** (docs/SEASONS.md, "War and pacts"): a faction's leader declares war or makes a pact with
  `/trigger diplomacy`, from the launch on. A kill between two factions at war counts twice in the weekly
  Kills column until Sunday's close, when every war ends. A pact stands until either side breaks it, at most 2
  each, and every declaration is announced in chat and listed in Sunday's Discord post. Claims and the rules
  don't change. In the `monkey-standings` data pack (`tools/diplomacy.py`).
- Each faction now has a number in game (`st.faction`, `st.leader`, storage `monkey:factions`), written by
  the standings' hourly board run, for packs that need to tell factions apart (docs/MAINTAINING.md, "The
  faction number in game").
- **Outposts** (docs/SEASONS.md, "Outposts"): four capture points out in the newest border ring, one in each
  quarter, 6 or more chunks from every claim. Stand in one with your faction and nobody else for 60 seconds to
  take it; a text over it says who holds it. Each hour your faction holds one while another faction is online
  is +1 weekly standings point, at most 20 a week, on top of the usual columns. Nothing is given. They move out
  after each border act, and show on the live map. `/trigger outposts` lists them. From the launch on, in the
  new `monkey-outposts` data pack (`tools/outposts.py`), placed by a new hourly timer on the VPS.
- Omens: short world events nobody announces ahead, on one or two weekday evenings a week (6 to 10 PM
  Pacific, 4 or more online, never Saturday, never during an event or a supply drop). A Blood Moon (Hard and
  roused mobs for a night, a little extra loot per kill), a Meteor (one richer supply drop with 5 minutes'
  warning, and the night's own drop still comes), Truce Hour (no PvP for an hour) or Hunted (a 30-minute
  bounty on the longest kill streak, claimed through staff as any bounty and withdrawn when the hunt ends).
  `tools/omens.py` generates the new `monkey-omens` data pack and plans each week from a secret the pack
  keeps in the world; `monkey-omens.timer` offers the evening's omen every 10 minutes. Install it once with
  `deploy/monkey-omens.sh --install` (docs/LIVE.md). Staff commands: docs/ADMIN.md, "Omens".

### Changed

- Season I opens on Saturday 31 October 2026 at 5 PM Pacific, three weeks earlier than 21 November. Week 1
  starts on Monday 2 November, the finale is on 16 January 2027 and Season II is proposed for 30 January. The
  launch weekend (Founder's Circlet) is 32 hours, because the clocks go back that night. The holidays keep
  their dates, so Arena Glory I (Midwinter, 19 December) moves to week 7, Faction Raid II to week 4 and
  Build Battle II to week 6; the Town Crier says so. On the live server, place the Crier again after this
  release (docs/ADMIN.md, "Spawn NPCs").
- Maintainers: `tools/checks.py` runs every fast check (CI runs the same file), `tools/local_ci.py` checks PRs on a
  maintainer's machine and posts a `local-ci` status when Actions can't run, and CI boots the server only when a
  change can break the boot (none for draft PRs). Nothing changes for hosts or players.
- Maintainers: four rounds of restructuring each give one shared job a single home:
  - **`tools/datapacks.py`** holds every generated pack (PR #57). `python tools/datapacks.py` regenerates
    them all and `--check` only compares, in place of each generator's own `--check` and `pack` commands
    (docs/ADMIN.md). Generators now only define `packs(repo)`. `validate.py` reports any pack that's out of date
    and runs the checks across all packs, which now include a scoreboard objective that one pack reads and no
    pack creates. The shared objective names (`events.ARENA_TAG`, `STATE`, `STRENGTH`, `CUP`,
    `challenges.LAUNCHED`) live in the pack that owns them.
  - **`tools/rcon.py`** sends every VPS job's RCON commands and decides when the server refused one (PR #58).
    `monkey-week.sh`, `monkey-drops.sh` and `tools/standings.py` go through it; the tests use its `Recorder` fake.
  - **`deploy/lib.sh`** holds the helpers every VPS script had copied (PR #59): reading `/etc/monkey-deploy.env`
    (one parser: the last value as written wins), logging, the compose command, RCON, the deploy lock and timer
    installs. Three behaviour changes on the VPS:
    - The week and drops timers now wait up to 30 minutes for the deploy lock before sending, so they no longer
      land while a deploy, the daily restart or an off-site backup has the server stopped.
    - A script's `ERROR:` line now goes to stderr, not stdout. Under systemd both reach the journal unchanged;
      a hand run that pipes stdout sees the error on the terminal instead.
    - A deploy lock the script can't open is an error, not "busy": the script stops with an error instead of
      skipping quietly. Root never creates or opens the lock through a link someone left in `/tmp`.
  - **`tools/nbt.py`** reads every world file (PR #60): `season`, `standings`, `drops` and `map_border` used to
    decode NBT four different ways. A damaged file is now one `ValueError` that names the file (`map_border`
    prints `error: …` and exits 2) instead of a traceback, `season` and `map_border` accept files that aren't
    gzipped, and a damaged claims file with a negative list count is an error instead of reading as "no claims".

Before Season I (Saturday 31 October), once this is live, run each VPS job once against the live world, so
the new lock and RCON paths have run there: `monkey-week.sh --check` and `monkey-drops.sh --check` first, then
the jobs themselves, and `monkey-standings.sh show` then `board` (standings has no `--check`; `show` changes
nothing). The commands are in docs/LIVE.md and docs/ADMIN.md.

## [2.8.0] - 2026-10-27

A sync with the updated shared mod folder: a new End, new structures, Carry On, breakable
bedrock, loot chests that refill, and the mods the folder dropped taken out. Same Minecraft (26.3). Server mods
151 -> 166 (about 278 MB of downloads, was 213 MB); client pack 179 -> 197 mods, 216 -> 234 files, about 542 MB
(was 502 MB). Players must update the client pack: several new mods are needed on both sides, so an old pack
can't join. The new structures only generate in new land, so Season I needs a new world: on the live VPS follow
docs/LIVE.md, "A new world for Season I (2.8.0)", once this is live. A host who keeps an old world gets the
new mods, but the new structures and End only in land nobody has visited, should run
`gamerule keep_inventory false` (the dropped corpse mod had turned it on), and should place the spawn NPCs again
(docs/ADMIN.md, "Spawn NPCs"): only a newly placed one has the tag that keeps Random Mob Sizes off it.

- New, from the shared folder (needed on the client too): **Carry On**, **Breaking Bedrock**, **Emotecraft**
  (with Player Animation Library), **Friends & Foes**, **Fair Fletching**, **Polymorph+**, **Rechiseled** (with
  Fusion and SuperMartijn642's Core Lib; SuperMartijn642's Config Lib becomes required), **Ultimate
  Minecarts**, and the libraries Fzzy Config and Mixson.
- New, server side (optional on the client): **Dungeons and Taverns**, **Crazy Chambers**, **Endercon** (the
  End) and **Qrafty's End Villages**, **Better Craftables**, **Craft Tridents**, **Trident All-Weather
  Channeling** (patched, below), **Random Mob Sizes**, **Sulfur Cube Expansion**, **Enchantment Disabler**;
  server only: **Loot Restock** (patched, below), **Planting Dispensers** and **WorldEdit** (staff only:
  docs/ADMIN.md, "Ranks").
- New, optional client mods: Essential, Better Capes, MinecraftCapes, Cirrus, Windy, Real Arrow Tip, Third
  Person Death, Diorama, Bind Commands, Command Keys, Reactions, Scribble, Smooth Camera, VisualKeys (with
  WalksyLib) and WorldEdit CUI.
- Updated: Strength SMP Season 4 1.7 -> 1.8 (the tick patch re-made per ADR-0004; 1.8 adds an `overlay_26.3`
  copy of the patched function, which is the one 26.3 runs, so both are patched), Strength Restrictions 1.4 ->
  1.5 (evokers no longer drop Totems of Undying), Craftable Cobwebs (a new build of 1.0.1). The folder's Entity
  Model Features (3.3.10), Punchy (2.8d), Puzzles Lib and JEI are older than the pack's pins, so those stay.
- Removed, because the brother took them out of the shared folder after his testing showed they didn't get on
  with the rest (each came from the folder in an earlier sync):
  - server and client: Better Tridents, CreativeCore, Illager Blabber, Jade, More Babies, Realistic Bees,
    Sound Physics Remastered (2.0.0), More Mobs (the 11 October sync), player-death-corpses (1.1.0);
  - server only: Moog's Ocean Structures (2.0.0) and Nullscape (the first package; Endercon now makes the End,
    and with both a test End had no outer-island highlands, so no End cities: docs/MAINTAINING.md);
  - client only, optional: Accurate Block Placement Reborn, AmbientSounds, BadOptimizations, BetterGrassify,
    Camera Utils, Dynamic FPS, Entity Culling, More Culling, Not Enough Animations, Reese's Sodium Options,
    Sodium Extra and Visuality (the first package), with their configs in `client/overrides/config/`.
  None of them carried a shipped feature. The arena's corpse clean-up (`tools/events.py`) and the grace item's
  corpse check (`tools/rules.py`) now match nothing and do no harm: deaths drop items, which the arena already
  removes. The repo's own additions (claims, ranks, logging, anti-cheat, map, performance, worldgen, Easy NPC) stay.
  A retired optional mod moves to `RETIRED_OPTIONAL` in `tools/client_env.py`, so older releases' indexes still
  validate.
- Left out on purpose (docs/MAINTAINING.md, "Mods left out on purpose"): Slabbed and Amethyst Nether (as
  before), Koh's Death Effects (not on Modrinth), the folder's NeoForge builds of PrickleMC and Crops Love Rain
  (the pack has the Fabric ones), and Deimos (nothing needs it). Universal Shops and Polymer stay shelved, and
  Vanilla Permissions stays out.
- Patched (docs/MAINTAINING.md, "Patches this pack carries"): **Loot Restock** checks whether a chest is empty by
  rolling its loot with no player, so the "Open 8 loot chests" challenge never counted with it; the patched class
  lets the opening player roll it (`tools/lootrestock_patch.py` rebuilds it; GPL-3.0-or-later like the mod).
  **Trident All-Weather Channeling** struck every old Channeling trident in the area on each hit (a pig next to
  one became a zombified piglin on a test server); the patch strikes only the attacker's own trident in flight.
  Its lightning isn't damage a player causes, so PvP grace and the spawn claim didn't stop it: the patch strikes
  nothing within 64 blocks of spawn or within 6 blocks of a player in grace.
- Configs in `package/monkey/defaults/` (copied on start where missing, so they reach the live server too;
  docs/ADMIN.md, "Mod settings"; `tests/test_mod_defaults.py`):
  - Carry On: nothing that stores items (chests of every kind, barrels, shulker boxes, furnaces, hoppers,
    dispensers, droppers, crafters, brewing stands, pots, shelves, lecterns, jukeboxes), no spawners or trial
    spawners, vaults, banners, beds, doors, players, Easy NPCs, text displays, markers, interactions, armor
    stands, item frames, chest or hopper minecarts or chest boats. Claims apply: a non-member couldn't pick up
    blocks in someone's claim, also during a Faction Raid.
  - Loot Restock: a structure chest refills 7 days after it was emptied, only when empty; barrels, item frames
    and trial vaults are left alone; only ops can break a tracked chest.
  - Enchantment Disabler: all 17 of Dungeons and Taverns' own enchantments (`nova_structures:*`) are out of the
    table, loot and trades, so rule B18 (event rewards only) holds by itself.
  - Ultimate Minecarts: minecarts don't damage what they hit.
- Supply drops are filled when they land instead of carrying a loot table, so Loot Restock never tracks them
  and a drop spot can't become a weekly refill (`tools/drops.py`); a drop that landed before the update still
  counts as full until it's opened. The spawn NPCs get the `global.ignore` tag,
  so Random Mob Sizes leaves them at normal size (`tools/npcs.py`).
- Rules: new rules 44 to 46 under "Bedrock" (no holes into the void, no breaking End exit portals or gateways,
  nothing on the Nether roof), adopted by the owners on 27 October 2026. The short rules
  (`codeofconduct/en_us.txt`) quote them now; a live server keeps its own copy of that file, so the Season I
  switch copies the new one (docs/LIVE.md). "The mods" in docs/RULES.md has a first three entries. Admin notes
  cover Friends & Foes' Totems of Freezing and Illusion (B4 doesn't cover them), Better Craftables' cheaper
  netherite template copy (3 diamonds, not 7; it stays) and its TNT minecart recipe (B10), Craft Tridents and
  Fair Fletching (B1, B6).
- Balance: the data files of the twelve gameplay mods on the brief's list were checked against the Strength SMP
  progression, the weekly challenges, the drop loot and rule 43. None replaces a Strength SMP, Monkey SMP
  (`monkey`) or drop file. Better Craftables replaces 66 vanilla recipes (the template copy above, stone tools,
  trim templates, redstone parts and more), Friends & Foes brings its own loot tables and a beehive recipe, Ultimate
  Minecarts the furnace minecart recipe; the rest only add their own. Defaults are kept except the configs above.
  The owners' calls are in the admin notes.
- Tested on a test server (i7-8700K, Carpet fake players, RCON): Carry On against claims and the raid rules;
  Breaking Bedrock (4.6 s with a netherite pickaxe and Efficiency V, a diamond pickaxe can't, no drop, a void hole
  is possible, a claim protects, pistons push bedrock, TNT doesn't break it); Loot Restock with a 1-minute
  interval (a refill works, the challenge counts once, drops and player chests are never tracked); 0 Dungeons
  and Taverns enchantments in new structures' chests; the trident patch; the End with Endercon alone (End
  cities and Qrafty's villages within 2000 blocks). Load test (`tools/loadtest.py`, 25 players standing still,
  5 minutes after a 2-minute warm-up, same PC and seed): this branch 87.2 ms mean tick (84.8 median, 11.5 TPS)
  against main's 98.6 ms (95.8, 10.1 TPS). That run-to-run gap is bigger than 15 mods should make, so it rules
  out a large slowdown, not a small one; it was measured before Nullscape came out, with players standing still,
  and both are far over the 50 ms budget on this 2017 PC. The live VPS gets a 30-player test before launch
  (docs/LAUNCH.md). A real client
  with the new pack joined a test server with exactly the manifest's mods and stayed on, voice chat connected.
  Not tested in game: WorldEdit (fake players couldn't run it), Carry On with animals, the enchanting table and
  trades with Enchantment Disabler.
- docs: docs/LIVE.md, "A new world for Season I (2.8.0)" (the switch, the carry with `--season 1`, the checks,
  the spawn claim, pre-generation with the End, the map, NPCs and the board, and what lives only in the world);
  docs/LAUNCH.md points to it; docs/ADMIN.md has WorldEdit, "Mod settings" and Endercon; docs/PLAYERS.md the
  new size, low-end list and what's new; README, the site and the Modrinth text say Endercon and about 560 MB.

## [2.7.0] - 2026-10-26

A fix for the severe lag since 2.5.0, supply drops and spawn NPCs; shops are shelved. Same Minecraft (26.3) and
world as 2.6.0: hosts unzip over 2.6.0 or 2.5.0. Players must update the client pack: Easy NPC is needed on the
client too, so an old pack can't join. On the live VPS, once 2.7.0 is live (docs/LIVE.md): the 2.6.0 one-time
steps if they aren't done yet (`deploy/install-standings.sh`, `deploy/monkey-week.sh --install`), then
`deploy/monkey-drops.sh --install`, place the spawn NPCs (docs/ADMIN.md, "Spawn NPCs"), and run the `lp` lines
under "Existing servers" in docs/ADMIN.md that remove the rank nodes Vanilla Permissions used. Skip
`deploy/shops-claims.sh`: shops are shelved.

- Fixed: severe lag since 2.5.0. **Vanilla Permissions** (`vanilla-permissions` 0.3.6, new in 2.5.0) made every
  tick 10 to 20 times slower with players online: it checks each entity selector a player's command uses against
  the whole command tree (Brigadier's `CommandDispatcher.getPath`), and the pack runs advancement functions as
  each player every tick. On a test server (i7-8700K, Carpet fake players standing on land in generated terrain,
  the same world for every run) 10 players took 1,081 ms per tick (0.9 TPS) with it and 64 ms (15.6 TPS, about
  50 ms by the last minute) without; 18 players took 986 ms (1.0 TPS) with it and 142 ms (7 TPS) without. 0.3.6
  is its newest version, so it's gone: the installer removes the jar when a server updates. Its job, letting
  LuckPerms ranks grant vanilla commands, goes back to ops (docs/ADMIN.md, "What needs op"):
  - Moderators reach a spot with `ledger tp minecraft:overworld X Y Z`, or by clicking a position in Ledger's
    inspect and search results (Ledger's own `ledger.commands.tp`, already in the rank). Teleporting to a player,
    or moving one, is an op's job.
  - Whitelisting is an owner's job again (console, RCON, `Add Player.bat`, or `monkey add-player` on the VPS).
  - An op switches a builder's game mode, so Easy NPC's editor is for ops and players an op puts in creative.
  - The rank files drop the nodes that did nothing without the mod (builders' `minecraft.command.gamemode`;
    moderators' `minecraft.command.teleport`, `tp` and `whitelist`). Existing servers keep their copies, which
    now grant nothing; "Existing servers" under "Moderation" in docs/ADMIN.md has the `lp` lines that remove them.
- New: **supply drops** (docs/SEASONS.md's event catalog; docs/ADMIN.md, "Supply drops"). Monday to Thursday,
  6 to 10 PM Pacific, from Season I's first week, the first time 4 or more players are online in survival
  (`function monkey:drops/min {players:N}`) and no event is on: chat and a boss bar give the coordinates 10
  minutes ahead, then 1 chest per 4 players online (at most 3) lands in the newest border ring, 6 or more
  chunks from every claim, on dry natural ground. The chests despawn after 20 minutes. Modest loot (food,
  iron, coal, arrows, torches, logs, XP bottles): nothing Strength, no netherite, diamonds or emeralds.
  `tools/drops.py` picks the spots from the saved claims and border and generates the new `monkey-drops`
  data pack, which also has staff commands (`start`, `here`, `stop`, `status`, `on`, `off`). On the VPS,
  `monkey-drops.timer` offers the night's drop every 10 minutes; install it once with
  `deploy/monkey-drops.sh --install` (docs/LIVE.md).
- New: **spawn NPCs**, so a player who joins when no staff are on is met at spawn. The Guide greets new
  players and offers the short rules, how to find a faction, and buttons for this week's challenges, the faction
  standings and the wardrobe; the Town Crier shows this week's Saturday event and the next. They are Easy NPC
  7.17.1 (`easy-npc`, `easy-npc-core`, `easy-npc-config-ui`), needed on the client too: players update the
  client pack. `tools/npcs.py` writes them into the new `monkey-npcs` data pack, and
  `defaults/config/easy_npc/security.cfg` keeps Easy NPC's editor features to ops. Staff place them once per
  world, on the live VPS too, once the release is live (docs/ADMIN.md, "Spawn NPCs").
- Fixed (supply drops, before release): a staff `start`, `here` or `stop` run from the Nether or the End
  force-loaded or released chunks in that dimension instead of the Overworld, where drops land. Stopping a drop
  from the Nether left its Overworld chunks loaded for good, and starting one from the Nether loaded Nether
  chunks that stayed loaded while the drop gave up silently (both seen on a test server). The drop's chunks are
  now always the Overworld's, and `here` outside the Overworld says to stand there or use `start {x,z}`.
- docs: the one-time steps for the supply drops' timer and the spawn NPCs on the live VPS. docs/LIVE.md has a
  "The spawn NPCs" upgrade step, and its set-up steps now install the drops timer. docs/LAUNCH.md checks by
  Saturday 14 November that both are done once 2.7.0 is live: a release places no NPCs by itself.
- Shelved: **shops**. Universal Shops and Polymer (2.6.0, never on the live server) are out of the pack; no other
  mod needed Polymer. Their pins and how to bring them back: docs/MAINTAINING.md, "Shelved mods".
  `deploy/shops-claims.sh` and the shop docs stay, marked shelved, and Open Parties and Claims' default keeps the
  `universal_shops:trade_block` exception, dormant (a test boot with it is clean). Rule 43 now covers trading by
  hand: items for items, no scams, no real-money trading (docs/RULES.md; the site, docs/PLAYERS.md and the launch
  drafts follow). The paid whitelist is unchanged. Nothing to do on the VPS (skip `shops-claims.sh`), and players
  need nothing new.

2.6.0 rehearsed on a test server (Carpet fake players): the standings and bounties, the weekly challenges,
Founder's Circlet, the wardrobe, shops, the launch hour and the launch run sheet (docs/LAUNCH.md). Fixes from it:

- Fixed: `function monkey:rules/launch` opens Founder's Circlet's window only the first time (`#launched
  rw.day`, which the launch already set so a second run wipes nothing). Run again after the launch weekend, it
  opened another 31-hour window that `monkey-week.timer` no longer closes, so the Circlet could be earned
  outside the weekend. `founder/open` by hand still opens it (docs/ADMIN.md).
- Fixed: a re-run of `deploy/monkey-standings.sh` on Sunday said "board updated and announced in chat" though
  the week is announced only once; it now says it was already announced.
- docs/LAUNCH.md: a check by Saturday 14 November that the two one-time 2.6.0 steps on the VPS are done
  (`monkey-week.sh --check`, `install-standings.sh --check`), a warning that
  `rules/launch` on the live world before launch starts Founder's Circlet's window early, and the check at
  midnight on Sunday that the window has closed.

## [2.6.0] - 2026-10-26

Season I's date and launch kit, weekly faction standings, weekly challenges, item-priced shops and a lighter
client install. Same Minecraft (26.3) and world as 2.5.0: hosts unzip over 2.5.0. Players update the client pack
for the new skins' textures and the optional tick boxes; shops need nothing on the client. On the live VPS, once
2.6.0 is live, run the one-time setup for each (docs/LIVE.md): `deploy/install-standings.sh`,
`deploy/shops-claims.sh` and `deploy/monkey-week.sh --install`.

- Site: the pass wording follows `STORE_URL`. While it is empty (no store yet), the join steps, the Server
  Pass card, the invite ladder and the creator page say passes are arranged in the Discord and staff whitelist
  you by hand, instead of promising the store's whitelist "within a minute or two". Setting `STORE_URL` and
  running `tools/site_links.py` switches the pages to the store's wording (`data-store="open"` and `"soon"`).
- Weekly faction standings: one rank a week from Cup points (40), claimed land (20), the members' Strength
  (20) and their PvP kills this week outside the arena (20), each as a share of the column's leader, +5 a
  claimed bounty. `tools/standings.py` reads the saved world; the new `monkey-standings` data pack counts
  the week's kills and holds the board at spawn (`/trigger standings`). On the VPS `monkey-standings.timer`
  closes the week on Sundays at 7 PM Pacific, keeps it in `STANDINGS_DIR` and posts it to
  `STANDINGS_WEBHOOK_URL` (else `DISCORD_WEBHOOK_URL`), under the deploy lock; an hourly timer updates the
  board. The bounty board now pays the Bounty Hunter title and +5 standings points instead of coins
  (`monkey:standings/bounty/post` and `/claim`). Set up once with `deploy/install-standings.sh`
  (docs/LIVE.md).
- New: **shops** and a **lighter client install**. Universal Shops (with Polymer, server only: the client pack
  doesn't need it) lets players sell from a chest while offline, priced in items; the shop block holds the
  payments and only its owner can break it. Open Parties and Claims' default
  `forcedBlockProtectionExceptionList` gains `"hand$universal_shops:trade_block"`, so anyone may buy, empty-handed,
  from a shop in someone's claim while its chest stays protected; on the live VPS run `deploy/shops-claims.sh`
  once this release is live (docs/LIVE.md, "Shops in claims"). New rule 43 (`docs/RULES.md`, "Trading";
  adopted by the owners 26 October): shops in a claim are protected, raids included, and lying listings are scams.
  In the client pack, 126 client-side mods and every resource pack and shader pack are now `"client": "optional"`,
  ticked by default, so players can untick them in Prism or switch them off in the Modrinth App; the other 50 mods
  (those that add registry content, and the libraries they need) stay required. `tools/client_env.py` holds the list, `snapshot.py`
  writes it, `validate.py` checks it, and `tests/test_client_env.py` checks it against facts recorded from every
  jar (`tests/fixtures/record_client_mods.py`). `docs/PLAYERS.md` gets a "Low-end PC" section and the current
  `/oclaims` and `/oparties` command names. The site's "16 GB of RAM" stays: nothing here measured a smaller
  pack.
- Season I launch kit: the launch time is `LAUNCH_AT` in `site/config.js` (Saturday 21 November 2026, 5 PM
  Pacific). `tools/site_links.py` writes it into every `data-launch` element, Pacific and Eastern spelled out,
  so crawlers and link previews see it; the front page adds the visitor's own time and a countdown, then says
  the season is live. New `docs/LAUNCH.md` (the run sheet from now to a week after launch, the founding roster
  and moderator recruitment), the dated Season I calendar in `docs/SEASONS.md`, and launch announcement drafts
  in `docs/PROMOTION.md`.
- New: **weekly challenges** and **Founder's Circlet**. Three challenges a week (solo, faction, explore) from a
  rotating pool in `tools/challenges.py`, new every Monday at 12 AM Pacific, shown by `/trigger challenges` and
  a third wardrobe page. Only this week's play counts; nothing counts player kills, distance or time online, and
  blocks count mined minus placed. Challenges done (`rw.challenges`, carried to the next season) unlock
  Trailblazer at 3, the Vanguard Helm at 9 and Pinnacle at 18. Founder's Circlet is for 10 minutes online on
  Season I's launch weekend (Saturday 21 November 2026, 5 PM Pacific, to the end of Sunday): `rules/launch`
  opens it and it closes by itself; never sold. All four skins are look-only. Players update the client pack
  for the new textures. On the VPS, install the hourly week timer once this is live:
  `sudo sh /srv/monkey/repo/deploy/monkey-week.sh --install` (docs/LIVE.md).

## [2.5.0] - 2026-10-26

X-ray protection and moderation tools, more wardrobe skins and the season-end tools, onboarding and faction
rules. Same Minecraft (26.3) and world as 2.4.2: hosts unzip over 2.4.2. Players update the client pack for the
new skins' textures; everything else is server only. Default config changes reach only new servers: on the live
VPS, run `deploy/upgrade-2.5.0.sh` once after 2.5.0 is live (docs/LIVE.md).

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
- Live server: a **daily restart** at 4:30 AM Pacific (`monkey-restart.timer`, `monkey-deploy.sh --restart`), with
  the usual 5- and 1-minute warnings in chat. It shares the deploy lock, skips a server a deploy restarted that
  morning (`RESTART_MIN_UPTIME`, 6 hours), and posts a `spark health` link from just before the restart, so memory
  use can be compared from day to day.
- Live server: a **weekly update check** on Mondays (`monkey-updates.timer`): `tools/check_updates.py` against the
  live release, posted to Discord with the report attached, while the GitHub Actions check can't run.
- Live server: **`deploy/upgrade-2.5.0.sh`** does this release's one-off VPS steps in one go. The Distant Horizons,
  Code of Conduct, ServerCore and claims settings change with one restart (under the deploy lock, with warnings in
  chat and a copy of each file), then it makes the spawn claim over RCON, installs python3 for the update check,
  and installs the two timers. It skips steps already done, `--check` only reports, and it reads no secrets. See
  "One-off steps when upgrading" in `docs/LIVE.md`.
- Daily restart, update check and load-test results go to `STAFF_WEBHOOK_URL` in `/etc/monkey-deploy.env` when it
  is set (a staff-only channel), else to `DISCORD_WEBHOOK_URL`.
- Live server: **`deploy/monkey-loadtest.sh`** measures what the VPS can carry: `tools/loadtest.py` with 25 fake
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
- New: `function monkey:events/season/lock` and `unlock`. The lock puts survival players in adventure mode
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
- New: players accept the **short rules** before they join (Minecraft's Code of Conduct screen,
  `codeofconduct/en_us.txt`, `enable-code-of-conduct=true`), and again whenever the text changes.
- New: a **welcome screen** a few seconds after a first join. Its one button opens the Discord, where
  `#smp-forum` lists the factions that are recruiting. Every pause menu gets a **Monkey SMP** button with the
  Discord, the live map, the rules and the store.
- New rule 26: **48 hours of PvP grace** for a first join. Other players can't hurt a new player; attacking a
  player or `/trigger end_grace` ends it, and nobody gets it in the launch hour. Fights in the event arena don't
  count, and grace is off there. Players who joined before this update get neither grace nor the welcome
  (Minecraft's own statistics say they've played). Built into the `monkey-rules` data pack (no new mod).
- New rule 26: **spawn is a no-PvP zone**, an Open Parties and Claims server claim over the 7 x 7 chunks
  around spawn. An admin sets it up once per world with two console commands (admin notes in `docs/RULES.md`):
  the mod keeps that setting per world and doesn't let a data pack claim.
- New rules 40 to 42: **no insiding**, **no teaming** (helping anyone outside your faction in a fight;
  events are exempt), and **rollbacks** (griefing of a territory is rolled back, a legal raid isn't).
- Claims: a player claims at most 4 chunks (`maxPlayerClaims = 4`), so a faction's territory is 2 x 2 chunks
  per member, as rule 35 says.
- ServerCore: the **breeding cap** (32 of a kind within 64 blocks) and **villager lobotomization** (a villager
  stuck in a 1x1 space ticks once a second) are on.
- Updated: C2ME 0.4.2-alpha.0.89 to 0.4.2-alpha.0.106 (server only; the client pack keeps its copy).
- Kept: the combat-log mod. Its file is named `+26.1.2`, but it is the author's 26.3 build ("fix: fabric
  26.3", for Minecraft 26.1 to 26.3), and no other mod does the same job on 26.3.
- These defaults are copied only where the server doesn't have the file yet. On an existing server, set
  `enable-code-of-conduct=true`, `maxPlayerClaims = 4` and the two ServerCore switches yourself (server
  stopped), then make the spawn claim: the commands are in `docs/LIVE.md` ("The short rules, ServerCore and
  claims").

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
- Live server: **off-site backups**. Every hour `monkey-backup.timer` sends the live `server/` folder, encrypted,
  to a Cloudflare R2 bucket with restic, between `save-off` / `save-all flush` and `save-on` (saving comes back on
  also when restic fails, hangs or is killed). It leaves out what the installer downloads again (jars, libraries,
  logs, BlueMap tiles), keeps 48 hourly, 14 daily, 8 weekly and 6 monthly snapshots, and reads back 5% of the
  stored data after each run (`restic check --read-data-subset=5%`). It posts to the Discord webhook when backups
  fail and when they work again. The keys and the restic password go in a root-only `/etc/monkey-backup.env`
  (`deploy/monkey-backup.env.example`), and the password is kept off the VPS too. docs/LIVE.md covers setup,
  restores, the cost and a monthly restore drill on the home PC, which also rehearses the playit fallback.
- Live server: deploys keep only the newest 3 world backups in `backups/` (`KEEP_BACKUPS` in
  `/etc/monkey-deploy.env`; was 14), since R2 now holds the history.
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
  `/etc/monkey-deploy.env` and a release tagged during the day goes live at 4 AM; `monkey-deploy.sh --now` still
  deploys right away, and `--status` says whether the window is open. The first deploy on a new machine doesn't wait.
- Live server: the Discord "back up" message says to update the modpack only when the pack really changed, not
  on every release (each release bumps the pack's version number, which doesn't stop an old pack from joining).

## [2.4.0] - 2026-10-25

Monkey SMP: the new name, the Season I rules, event tooling and the wardrobe. Same Minecraft (26.3), mods and
world as 2.3.0: hosts can unzip over 2.3.0 and keep their world. Players update the client pack (it adds the
wardrobe resource pack).

- New: the **live server** setup in `deploy/` (`docs/LIVE.md`): a VPS pulls and deploys the newest release tag,
  with world backups, a chunky pregen and the public site.
- The GitHub repo is now **gr8monk3ys/monkey-smp-server** (was `monkey-smp-server`). GitHub redirects the old
  URLs, so existing clones, release links and installers keep working; update a clone's remote with
  `git remote set-url origin https://github.com/gr8monk3ys/monkey-smp-server.git`.
- New: a **server icon**, the Monkey SMP monkey in the multiplayer server list. It ships in `defaults/`, so it is
  copied only where the server has no `server-icon.png` yet; a host's own icon is kept. Logo, banners and the
  trailer are in `marketing/`.
- New: **event tooling**. The `monkey-events` data pack (made by `tools/events.py`) runs Arena Glory (join,
  kits, Strength held at +3, drops cleaned), the Anarchy and Faction Raid timers, official faction flags,
  event books, the Season Cup and an attendance count; `/function monkey:events/help` lists the commands.
  `tools/block_wheel.py` draws Build Battle blocks from a published seed. See the Events section of `docs/ADMIN.md`.
- Docs: `docs/SEASONS.md`, the plan for seasons and events. It covers 12-week seasons in acts (border growth, Dragon Night,
  Netherite age, a finale), one event a week from a catalog (KOTH, supply drops, bounties, tournaments), what
  carries over between seasons, and the research behind it. The owners' three pillar events (Build Battle with a block wheel, Faction Raid
  capture the flag, Arena Glory kit combat) run every season and score a faction Season Cup, plus
  Anarchy (90 minutes of suspended combat rules when the End opens; griefing, cheating and conduct rules stay).
- The server is now called **Monkey SMP** (was Monkey SMP): server list message, window titles, the launcher
  profile, the client pack and the site. Download names (`MonkeySMP-*`), the `.monkey-smp` game folder and the
  backup task keep their old names, so updating needs nothing new. The uninstaller is now "Uninstall Monkey SMP.bat".
- New: the **wardrobe**, cosmetic skins for swords and helmets (`/trigger wardrobe`), unlocked by days played,
  tenure, invites, supporter tier or being a founder. Look only: no damage, armor or durability changes.
- New: the server enforces the Season I rules it can (two data packs from `tools/rules.py`): a 2500 x 2500
  border centred on spawn, set once (the Nether's at 1:8); the launch hour (`function monkey:rules/launch`
  closes PvP and the Nether for an hour, the End stays closed until `function monkey:rules/open_end`); no
  Netherite armor until `datapack disable "file/monkey-no-netherite-armor"`; Fire Aspect and Flame disabled.
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

- New download for players: **MonkeySMP-Player-2.1.0.zip**. Double-click "Install for Minecraft Launcher.bat"
  and it sets up Fabric and every mod, resource pack and shader (downloaded from Modrinth, each file
  hash-checked) in a separate folder, then adds a "Monkey SMP" installation to the normal Minecraft
  Launcher. Running it again updates; "Uninstall Monkey SMP.bat" removes it.
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

First packaged release of Monkey SMP.

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
