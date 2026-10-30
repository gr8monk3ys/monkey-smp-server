# Running the server (admins)

Everything below assumes the release zip is unzipped into a folder, called `MonkeySMP-Server` here.
Paths are written Windows-style (`server\logs`); on macOS and Linux they are `server/logs`.

## Day to day

| Do this | Windows | macOS / Linux (in Terminal, in the folder) |
|---|---|---|
| Start | `Start Server.bat` | `sh start.sh` (Mac: or double-click `Start Server.command`) |
| Stop (saves the world) | type `stop` in the server window, or `Stop Server.bat` | type `stop`, or `sh stop.sh` |
| Let someone join | `Add Player.bat`, or `whitelist add NAME` in the server window | `sh add-player.sh NAME`, or `whitelist add NAME` |
| Back up | `Backup World.bat` | `sh backup.sh` |
| Back up automatically | `Schedule Backups.bat` (a Windows scheduled task, 6 AM and 6 PM while you're signed in; each run is logged to `scheduled-backups.log`) | a cron job (`crontab -e`): `0 6,18 * * * cd /path/to/MonkeySMP-Server && sh backup.sh >> scheduled-backups.log 2>&1` |
| Update to a new release | stop the server, unzip the new release **over** the old folder, start again | the same (see below for the Mac) |

Backups are safe while the server runs and keep the newest 14 in `backups\`.

Updating never touches the world or your config edits. It only swaps mod/datapack/server files to the
versions pinned in the new manifest. On Linux, `unzip -o MonkeySMP-Server-<version>.zip` next to the
old `MonkeySMP-Server` folder updates it in place. The Mac's Finder doesn't unzip over a folder (it
makes `MonkeySMP-Server 2`): move `server` and `backups` from the old folder into the new one, or use
the same `unzip -o` in Terminal.

**Exception: 1.x (Paper) to 2.x (Fabric).** These are different servers with different worlds. Unzip 2.x
into a **new** folder; the installer refuses to install over a 1.x world so nothing gets mixed up.

The same actions from PowerShell (on macOS and Linux, `sh monkey/monkey.sh` takes the same commands):

```powershell
.\monkey\monkey.ps1 start | stop | backup | status
.\monkey\monkey.ps1 add-player Steve
.\monkey\monkey.ps1 rcon "list"           # run a console command on the running server
```

Memory is picked from the computer's RAM: 3 GB on 8 GB, 4 on 12, 5 on 16, 6 on 24 and 8 GB from 32 GB up.
8 GB is plenty of memory even for 25 players (a 25-player test peaked at about 4.3 GB in use), though the CPU
can't keep up with that many (see "How many players" below). To force a value,
set the environment variable `MONKEY_MEMORY_GB` (on Windows `setx MONKEY_MEMORY_GB 8`, then open a new window; on macOS/Linux
`MONKEY_MEMORY_GB=8 sh start.sh`) or pass
`-MemoryGB 8`. Size it from spark's numbers rather than giving it everything: the whole heap is reserved at
start, so more than the server uses only takes RAM from everything else. The "Prepare for Hosting" bundle
defaults to `MEMORY_GB=6` (use 8 for a big group); give that machine about 2 GB more RAM.

On macOS and Linux the launchers use PowerShell 7 (`pwsh`) if it is installed; otherwise the first
start downloads a pinned, hash-checked portable copy from Microsoft (about 70 MB) into the folder, next
to `java` (ADR-0007). On a Linux VPS without Docker, start the server inside `screen` or `tmux` so it
keeps running when you log out.

## Docker

The release has a `docker` folder for running it in a container on Linux (or anywhere with Docker).
The image has no Minecraft, Java or mods in it: it mounts the release folder and the same installer
downloads everything into it, so `server\`, `backups\` and the world are the same files a native run
uses, and you can switch between the two (stop one before starting the other).

| Do this | How (in `MonkeySMP-Server/docker`) |
|---|---|
| First start | put `EULA=TRUE` and `OWNER=<your Minecraft name>` in `.env`, then `docker compose up -d` |
| Watch the console | `docker compose logs -f` (Ctrl+C stops watching, not the server) |
| Stop (saves the world) | `docker compose down` |
| Memory | `MEMORY_GB=<n>` in `.env`, then `docker compose up -d` again |
| Let someone join | as the owner, type `/whitelist add NAME` in game |
| Back up | `docker compose down`, copy `server` somewhere safe, `docker compose up -d` |
| Update to a new release | `docker compose down`, unzip the new release over the folder, `docker compose up -d --build` |

Open 25565/tcp (game) and 24454/udp (voice chat) in the VPS firewall. For a public live map, put it behind
HTTPS as docs/LIVE.md does (step 9) rather than opening 8100/tcp.

## How many players

One CPU core is the limit, not memory: the world ticks on a single thread and needs under 50 ms per tick for
full speed (20 TPS). Measured with `tools/loadtest.py` on an Intel i7-8700K (2017) with Carpet fake players
standing spread out in generated terrain:

| Players | Typical tick | TPS |
|---|---|---|
| 5 | 19 ms | 20 |
| 10 | 48 ms | 20 |
| 25 | 71 ms | about 13 |

So a PC like that runs **about 10 players at full speed**; with 25 it stays playable but slow. A rented host
with a current Ryzen (7000 or 9000 series) is roughly twice as fast per core, which is what 25 players need;
many budget plans run older Xeons that are slower than a 2017 desktop. Exploring ungenerated land costs far
more than these numbers (see the next section).

What keeps it there:

- **ServerCore** (`server\config\servercore\config.yml`). Mobs far from every player tick less often
  (`activation-range`), and while a tick takes over 45 ms it steps mob caps and tick/view distances down, then
  back up when the server recovers (`dynamic`; never above view distance 8 / simulation distance 6).
  `/servercore status` shows the current values. Mob farms that depend on distant mobs can be slower: set
  `activation-range.enabled: false` for vanilla behaviour, at about a quarter more tick time.
- **Two patches in the Strength SMP mods** (docs/MAINTAINING.md lists them). Unpatched, they ran tens of
  thousands of commands per tick and went past Minecraft's limit of 65,536, which cut their effects off.
- **Three mods from the shared mod list are left out**: Slabbed (alpha; about doubles the tick, and has an open
  report of freezing servers on 26.3), The Sift (adds about 65% to the tick), and Amethyst Nether (replaces the
  whole Nether, as Incendium does; its page lists them as incompatible). To add one anyway, drop its jar into
  `server\mods` (and players into their mods folder): the installer leaves files it doesn't manage alone.

## Before a big group joins

- **Pre-generate the world.** Generating new terrain on the main thread is what drags the tick rate down when
  many players explore at once, and Tectonic's tall terrain makes each chunk expensive. Generate out to the
  season's largest border (6000 wide, docs/SEASONS.md) plus the view distance, without changing the border: the
  `monkey-rules` pack sets the starting one (Rule 25) and the border acts grow it. With nobody online, in the
  server console: `chunky worldborder` (centres on the border, which is on spawn, not 0,0), `chunky radius 3200`
  and `chunky start` (hours; `chunky progress` shows how far). For the Nether (1 block there is 8 in the
  Overworld): `chunky world minecraft:the_nether`, `chunky worldborder`, `chunky radius 500` and `chunky start`.
  Chunky picks up after a restart (`continueOnRestart` in `server\config\chunky\config.json`), so `chunky pause`
  lasts only until the next restart; `chunky cancel` stops it for good.
- **Watch it with spark.** `spark tps` shows TPS and tick time (MSPT; under 50 ms keeps 20 TPS), `spark health`
  memory and GC, and `spark profiler start` / `spark profiler stop` uploads a profile that shows which mod or
  area is slow.
- **Player slots:** `max-players=30` in `server\server.properties` for new installs. A server installed before
  2.2.2 keeps its own file (defaults are only copied when missing), so raise it there by hand.
- **BlueMap** renders with one thread (`render-thread-count: 1` in `server\config\bluemap\core.conf`) so the map
  doesn't compete with the game. Same note: an existing install keeps its old value (3) until you change it.

## Ranks (LuckPerms)

| Rank | Can |
|---|---|
| `default` | normal play: parties and claims (Open Parties and Claims), voice chat |
| `builder` | the same as `default` for now: an op switches a builder's game mode (below) |
| `moderator` | + warn, mute, kick and ban with a reason (BanHammer), vanish, look into inventories and ender chests (InvView, look only), x-ray alerts (MinerTrack), teleport to a spot (`ledger tp`), Ledger inspect/search/rollback/restore (not purge) |
| `admin` | every mod's commands, including editing other players' inventories and IP bans; vanilla commands need op as well (below) |

```
lp user NAME parent set moderator
lp user NAME parent remove moderator
```

Ranks live in `server\mods\luckperms\yaml-storage\` as plain text files (LuckPerms' settings are in
`server\config\luckperms\luckperms.conf`).

**What needs op.** A rank can only grant mods' commands. Vanilla commands (`/gamemode`, `/tp`, `/whitelist`,
`/give` and the rest) follow op status, which the owner has from the install (`ops.json`). Don't op moderators
to give them one of these: level 2 already includes `/give` and `/gamemode`. In 2.5.0 and 2.6.0 the Vanilla
Permissions mod let ranks grant some vanilla commands, but it made every tick 10 to 20 times slower with
players online (CHANGELOG), so it is gone. Who does what now:

- **Teleport.** A moderator goes to a spot with Ledger: `ledger tp minecraft:overworld X Y Z` (the Nether is
  `minecraft:the_nether`), or by clicking a position ("Click to teleport") in Ledger's inspect and search
  results. It's Ledger's own `ledger.commands.tp` node, already in the rank. It can't take them to a player or
  move someone else; that's an op's job (`tp NAME X Y Z`, `tp NAME OTHER`).
- **Whitelist.** An owner, from the console or RCON: `whitelist add NAME`, `Add Player.bat`, or on the live VPS
  `docker compose exec monkey monkey add-player NAME` (docs/LIVE.md).
- **A builder's game mode.** An op, in the console: `gamemode creative NAME`, and `gamemode survival NAME`
  when the job is done.

**WorldEdit (since 2.8.0).** WorldEdit is on the server only, for staff. Only `admin` has it, through `*`;
`default`, `builder` and `moderator` have no `worldedit.*` node, so players can't use it. To lend it to a
builder for a job, and take it back after:

```
lp user NAME permission set worldedit.* true
lp user NAME permission unset worldedit.*
```

The wand is `//wand`; WorldEdit CUI is an optional client mod that draws the selection. Undo a WorldEdit job
with `//undo`; don't count on Ledger seeing WorldEdit's changes (not tested). WorldEdit was only checked to load
on a test server, and the ranks above come from the rank files. The test players (Carpet bots) couldn't run
`//set` even as ops, so nothing was tried in game: with a real client, try `//pos1`, `//pos2`, `//set stone` and
`//undo` as an admin, and the same as a plain player (it should refuse), before the first real job.

## Griefing

Ledger logs every block change. Common commands:

```
ledger inspect                                  # toggle, then click a block to see who changed it
ledger search source:NAME range:30 after:2h     # what NAME did in the last 2 hours within 30 blocks
ledger rollback source:NAME range:30 after:2h   # undo it
ledger restore source:NAME range:30 after:2h    # redo it if you rolled back too much
```

Claimed land (Open Parties and Claims) is already protected from outsiders, so most griefing happens
in the wild.

## Moderation

**Punishments (BanHammer).** Every punishment takes a reason, which the player sees, and goes into a history kept
in `server\banhammer-sqlite.db`, so the next admin can see what happened before. Durations are written like
`30m`, `12h`, `3d` or `1d12h`.

```
warn NAME reason                  # step 1 of the rules' enforcement
tempban NAME 3d reason            # step 2: the rules' temporary ban (1 to 7 days)
ban NAME reason                   # step 3, or straight away for cheating, hate and doxxing
tempmute NAME 1h reason           # no chat; also blocks me, msg, tell, w and teammsg
mute NAME reason
kick NAME reason
unban NAME / unmute NAME / unwarn NAME
```

Start the reason with `-s` (`tempban NAME 3d -s reason`) to keep it out of public chat. Five warnings give an
automatic temporary ban of 5 hours (`warnActions` in `server\config\banhammer\config.json`). A text mute
doesn't cover voice chat; to mute someone's voice for a day:
`lp user NAME permission settemp voicechat.speak false 1d`. IP bans (`ban-ip`) are admin only, because an IP is
often a whole household.

**Watching quietly.** `vanish` hides you from players, the tab list and the server list until you run it again.
`view inv NAME` and `view echest NAME` (InvView) open a player's inventory or ender chest. Moderators can only
look; admins can also take items out. Admins' own inventories can't be opened by others. Ledger (above) shows who
broke or placed what, and who took what from a chest.

**X-ray.** AntiXray hides ores and other valuables in what the server sends: a player can only see ores that touch
air, water or lava, and x-ray mods, packs and F3+A see fake ores everywhere instead. The settings are in
`server\config\antixray.toml`. Some x-ray gets past it (a cracked world seed; Distant Horizons' LODs if its
server-side LODs are switched back on, below), so
MinerTrack watches how people mine: someone who tunnels straight from one buried diamond or emerald vein to the
next (or to ancient debris in the Nether) builds up a violation level (VL), and moderators get a chat alert at VL 2,
4 and 5. It never kicks or bans; that's your call. `mtrack check NAME` shows a player's violations, `mtrack verbose`
alerts you on every VL increase, `mtrack logs FILE.log` shows one of the daily logs (they're in
`server\config\MinerTrack\logs`) and `mtrack reset NAME` clears a player you've cleared. Lucky players set it off
too, so check before you act. Settings are in `server\config\MinerTrack\` (`config.yml`, plus one file per
dimension in `Configuration\`). It only watches vanilla diamond, emerald and ancient debris; to watch a modded ore
too, add its id (e.g. `sulfurcavesplus:sulfur_diamond_ore`) to `rare-ores` in that dimension's file and run
`mtrack reload`.

The saved query for diamonds: every diamond ore broken in the last day, newest first (add `source:NAME` for one
player, or change `after:1d` to `after:7d`):

```
ledger search action:block-break object:#c:ores/diamond object:nether_ores_reborn:diamond_ore object:nether_ores_reborn:end_diamond_ore after:1d
```

`#c:ores/diamond` covers the vanilla diamond ores and Sulfur Caves Plus's; Nether Ores Reborn's aren't in that tag,
so they're named.

A player whose diamonds come one after another, with little stone broken in between, is worth a
`ledger search source:NAME action:block-break range:100 after:1d` around where they were mining.

**Existing servers.** Rank files are only copied when missing, so a server installed before these tools keeps its
old ranks. If you never edited them, stop the server, delete `moderator.yml` and `admin.yml` in
`server\mods\luckperms\yaml-storage\groups\` and start it again. Otherwise add the new nodes in the console:

```
lp group moderator permission set banhammer.punish.warn true
lp group moderator permission set banhammer.punish.tempwarn true
lp group moderator permission set banhammer.punish.mute true
lp group moderator permission set banhammer.punish.tempmute true
lp group moderator permission set banhammer.punish.kick true
lp group moderator permission set banhammer.punish.tempban true
lp group moderator permission set banhammer.punish.ban true
lp group moderator permission set banhammer.unpunish.unwarn true
lp group moderator permission set banhammer.unpunish.unmute true
lp group moderator permission set banhammer.unpunish.unban true
lp group moderator permission set banhammer.unpunish.pardon true
lp group moderator permission set banhammer.commands.list true
lp group moderator permission set vanish.command.vanish true
lp group moderator permission set vanish.feature.view true
lp group moderator permission set invview.command.root true
lp group moderator permission set invview.command.inv true
lp group moderator permission set invview.command.echest true
lp group moderator permission set invview.can_modify false
lp group admin permission set invview.can_modify true
lp group moderator permission set minertrack.notify true
lp group moderator permission set minertrack.check true
lp group moderator permission set minertrack.verbose true
lp group moderator permission set minertrack.logs true
lp group moderator permission set minertrack.reset true
lp group moderator permission set minertrack.help true
```

Older rank files also hold `minecraft.command.*` nodes (builder's `gamemode`; moderator's `teleport`, `tp`,
`whitelist`, and before 2.5.0 `ban`, `kick` and `pardon`). They do nothing without Vanilla Permissions. Take
them out anyway, so a permissions mod added later can't quietly switch them back on:

```
lp group builder permission unset minecraft.command.gamemode
lp group moderator permission unset minecraft.command.teleport
lp group moderator permission unset minecraft.command.tp
lp group moderator permission unset minecraft.command.whitelist
lp group moderator permission unset minecraft.command.ban
lp group moderator permission unset minecraft.command.kick
lp group moderator permission unset minecraft.command.pardon
```

## Distant Horizons and x-ray

Distant Horizons runs on the server too: it builds the far-away terrain (LODs) from the real world and sends it to
players, who keep it in their own `DistantHorizons.sqlite`. AntiXray only changes chunks, not LODs, so out of the
box the LODs carry every real ore, buried or not, and anyone can read them out of that file. This was tested on
26.3 with the client pack (October 2026):

- **Default settings: leaks.** Of 32 ores read from a player's LOD file 140 to 270 blocks away, 31 were the real
  block at that spot, 21 of them buried with no air, water or lava next to them.
- **`maxGenerationRequestDistance` doesn't help.** Its lowest value still sends the 64 x 64 area the player is
  standing in, with real ores, so walking around collects them anyway.
- **The settings below: no leak.** The player only had LODs of chunks they had loaded themselves, and every buried
  ore in them was one of AntiXray's fakes.

So the server ships with them on, in `server\config\DistantHorizons.toml` (`defaults/config/DistantHorizons.toml`
in the package; Distant Horizons fills in the rest of the file on the first start):

```toml
[server]
	synchronizeOnLoad = false
	enableRealTimeUpdates = false

[common.worldGenerator]
	generatorPlan = "DISABLED"
```

The cost: players no longer get distant terrain from the server, only LODs of what they have walked past, so the
far view fills in slowly on a fresh world. It also takes Distant Horizons' world generation off the server's CPU.
A server set up before this default keeps its old file: change it as in "Distant Horizons stops sending its own
LODs" in `docs/LIVE.md`.

To send server-built LODs again (only if ores in them stop mattering, say on a creative or event server), stop
the server and put back Distant Horizons' own values: `synchronizeOnLoad = true`, `enableRealTimeUpdates = true`
and `generatorPlan = "SURFACE_THEN_CHUNKS"`.

The other way is Voxy with LOD Server Support (LSS) instead of Distant Horizons, which can scramble ores in what it
sends (`xrayObfuscation = "auto"` in `server\config\lss-server-config.yaml`; not tested here). Keep the Distant
Horizons settings above either way: the LSS client can also pull LODs from a Distant Horizons server, so changing
the client pack alone doesn't close anything.

## Claims and parties

Open Parties and Claims settings are in `server\config\openpartiesandclaims-server.toml` (how many chunks
each player may claim, whether claims are protected from explosions, and so on). Admins can claim land
for the server itself (for example around spawn) with the server-claim mode in the claims menu. Stop the
server before editing configs.

## Shops (shelved)

**Shelved on 26 October 2026, not in the current release.** The owners took shops out for now: Universal Shops
and Polymer aren't in the pack, and players trade by hand (rule 43). Their pins, and the steps to bring shops back,
are in `docs/MAINTAINING.md`, "Shelved mods". The rest of this section is how shops worked in 2.6.0.

Players sell from chests while they're offline with *Universal Shops* (Patbox), priced in items: there is no
currency, `/pay` or auction house. It runs on the server only, through Polymer (players see a Trade Shop as a
player head and its menus as ordinary inventory screens), so the client pack doesn't change. Polymer pushes no
resource pack (its auto-host is off). How players use shops: "Playing" in `docs/PLAYERS.md`; the rule: 43 in
`docs/RULES.md`.

- **What protects a shop.** The shop block holds the payments, and only its owner can break it; explosions
  can't. Its stock sits in an ordinary chest or barrel behind or under it, which only the claim protects. In the
  owner's claim nobody else can open, break or hopper that chest, raid or not. A shop in the wild can be robbed
  (rule 35), and with the shop's own **Allow Hoppers** setting on, a hopper under the block empties its
  payments. Tell players to build shops in their claim.
- **Buying in a claim.** `forcedBlockProtectionExceptionList` in `server\config\openpartiesandclaims-server.toml`
  holds `"hand$universal_shops:trade_block"`: anyone may right-click a Trade Shop in someone's claim, with an
  empty hand. `hand$` matters: with an item in the hand the same click could place blocks inside the claim. A
  shop can't be put on someone else's chest in a claim either: placing it means clicking the chest. The entry
  applies after a restart. A server installed before shops shipped keeps its old file: add the entry with the
  server stopped, or on the live VPS run `deploy/shops-claims.sh` (`docs/LIVE.md`, "Shops in claims"). Without
  it, only the owner's party can buy from shops in a claim.
- **No limits to set.** The mod has no setting for shops per player or for which containers count: any
  container next to the block works. Claims (4 chunks a player) are the practical limit.
- **Admin shops** sell without stock and swallow the payment: for event prizes or a spawn shop. With the
  `universal_shops.admin` permission (the `admin` rank, or op level 3), `/universal_shops get true` gives you
  one, `/universal_shops get false` a normal one. Anyone with that permission can change an admin shop.
- **Scam reports** (rule 43). Universal Shops keeps no record of purchases. Ask for screenshots
  (the sign or chat message, and the shop's menu, which shows the real item and price), and `ledger inspect` the
  chest for who put in or took out what. Only the owner can change a shop's settings or break it. To remove one,
  `setblock <x> <y> <z> air destroy`; the mod drops the payments inside when its block goes (untested here:
  check the ground).

## Spawn protection

Vanilla `spawn-protection=48` in `server\server.properties`: within 48 blocks of spawn only admins (ops)
can build or break blocks. PvP is blocked by a server claim over spawn (rule 26), which an admin makes once
per world: see the admin notes at the end of `docs/RULES.md`.

## Spawn NPCs

Two Easy NPC characters stand at spawn for whoever joins when no staff are on. The **Guide** (gold name) greets
anyone who comes within 8 blocks with a speech bubble. Right-clicked, it offers the short rules, how to find a
faction (`#smp-forum`), and buttons that open this week's challenges, the faction standings and the wardrobe
(what `/trigger challenges`, `standings` and `wardrobe` do). The rules and faction pages have a button for the
Monkey SMP links, the Discord first. The **Town Crier** (yellow) calls out every 5 minutes. Right-clicked, it
shows this week's Saturday event and next week's, picked by the challenges' week number, so it turns over on
Monday with them. Their text is in `tools/npcs.py`, which writes the `monkey-npcs` data pack.

Place them once per world. In game, as an op, stand where each one goes, facing the way it should face:

```
/function monkey:npcs/guide/here
/function monkey:npcs/crier/here
```

It stands in the middle of your block. From the console or RCON (on the live VPS,
`docker compose exec monkey monkey rcon "..."`), give the spot instead. Someone has to be near it so its chunk
is loaded; otherwise nothing appears and the log says "Error importing preset".

```
function monkey:npcs/guide/place {x:0.5,y:72,z:3.5,yaw:180}   # y: the block it stands on + 1; yaw: 0 south, 90 west, 180 north, 270 east
function monkey:npcs/crier/remove                              # near it
```

- **Placing again** moves it and resets it to this release's version: each has a fixed UUID, so there is only
  ever one. Do it after a release that changes their text, for example when an event moves (the changelog says
  so). If the old spot is far away and nobody is near it, run `remove` there first, or the old one can stay.
- **Talking to them in a claim.** Spawn is a server claim, and Open Parties and Claims protects entities in a
  claim too. `forcedEntityProtectionExceptionList` in `server\config\openpartiesandclaims-server.toml` holds
  `"hand$easy_npc:humanoid"` and `"hand$easy_npc:humanoid_slim"` (named ids: the mod documents ids and tags, not
  wildcards): anyone may right-click an Easy NPC in any claim with an empty hand. With an item in the
  hand the click is refused (the mod says to try an empty hand), so nobody can put a name tag or a lead on
  one. The entry applies after a restart. A server installed before it shipped keeps its old file: add the
  entry with the server stopped, or on the live VPS run `deploy/npc-claims.sh` (`docs/LIVE.md`, "NPCs in
  claims"). Without it only ops can talk to them.
- **Who can change them.** They have no owner. Easy NPC lets ops, and anyone in creative mode, edit, move or
  delete any NPC. No rank can switch to creative by itself, so that is ops plus anyone an op has put in creative
  (a builder at work, say); moderators and players can't. That creative override is built into Easy NPC and no
  setting removes it. `server\config\easy_npc\security.cfg` (copied on first start) puts every editor feature
  that matters behind an op: someone in creative can still change an NPC's look or delete it, but can't give it
  commands, scores, dialogs or trades.
- **Nobody can hurt them**: hits in survival or creative and arrows do nothing, and players can't push them.
  `/kill` still removes them, like any entity.
- **Cost**: none measurable. On a test server with a player standing next to them, the median tick was 3.3 ms
  with no NPCs and 3.3 ms with these two; 50 of them added 0.4 ms (spark, one-minute figures).

## Mod settings (since 2.8.0)

These configs ship in `package/monkey/defaults/` and are copied on start only when the file is missing, so an
edit on the server sticks. Stop the server before editing one. `tests/test_mod_defaults.py` keeps the shipped
values.

- **Carry On** (`server\config\carryon-common.json`). Sneak + right-click with empty hands picks up a block
  entity (an enchanting table, a beehive with its bees, a sign and so on) or a passive mob. On top of Carry On's
  own blacklist it can't lift anything that stores items: chests, trapped chests, copper chests, barrels,
  shulker boxes, furnaces, smokers, blast furnaces, hoppers, dispensers, droppers, crafters, brewing stands,
  decorated pots, shelves, chiseled bookshelves, lecterns and jukeboxes. Supply drops are chests; a carried
  container would skip the raid rules' container checks and the arena's empty-inventory check; and Ledger
  probably doesn't log a carried block (untested), so a container moved outside a claim could leave no trail.
  Nor spawners (the owners decided on 27 October 2026 that they stay put, as in vanilla), trial spawners,
  vaults, banners, beds, doors, players, Easy NPCs (the Guide and the Town Crier), text displays, markers and
  interactions (the standings board), armor stands, item frames, chest and hopper minecarts or chest boats.
  Open Parties and Claims applies to it like any other use: on a test server a non-member couldn't pick up a
  spawner or a barrel inside someone else's claim, also during a Faction Raid. (Picking up animals couldn't be
  driven with the test players, so that wasn't checked.)
- **Loot Restock** (`server\lootrestock.properties`). A structure loot chest refills from its loot table 7 days
  after it was emptied, and only when it is completely empty. Barrels, item frames and trial vaults are left
  alone. Only ops can break a tracked loot chest. It tracks only chests opened while they still have a loot
  table, so player chests are never refilled, and since 2.8.0 supply drops are filled when they land instead of
  carrying a loot table, so a drop spot doesn't turn into a weekly drop. Its record of chests is
  `world\chest_reset_data.json`, which goes with the world. The jar is patched so that opening a loot chest
  still counts for the "Open 8 loot chests" challenge (docs/MAINTAINING.md, "Patches this pack carries"); a
  refilled chest doesn't count again, so it can't be farmed. All of this was checked on a test server with a
  1-minute interval.
- **Breaking Bedrock** has no config. A netherite pickaxe breaks bedrock in about 5 seconds with Efficiency V
  (4.6 s measured); a diamond one can't; bedrock never drops, and breaking the bottom layer leaves a hole into
  the void. TNT can't break it, but pistons can push bedrock. A claim protects its bedrock from non-members like
  any block, and spawn protection covers spawn. The mod changes the bedrock block itself, so the Nether roof and
  the End's exit portal break the same way (only the Overworld floor was tried). Rules 44 to 46 cover the rest.
- **Enchantment Disabler** (`server\config\enchantmentdisabler\config.toml`). It turns off all 17 of Dungeons and
  Taverns' own enchantments (`nova_structures:*`) at the enchanting table, in loot and in villager trades, so
  they come only from events (rule B18). Event books made with `/give` or the staff kits still work. On a test
  server 0 of these enchantments turned up in the new structures' chests; the table and trades are off in the
  config but weren't checked in game.
- **Ultimate Minecarts** (`server\config\ultimate_minecarts_server.json`): linking carts with chains is on, and
  minecarts don't hurt players or mobs they hit.

## World generation

The world is generated with Tectonic's Overkill settings (`server\config\tectonic.json`) plus Terralith,
Incendium, Endercon (the End) and the structure mods. The seed is pinned in the manifest, so every copy of the
server gets the same terrain. Players never get it: it isn't in the client pack, the player zip, the site or the
rules (`tests/test_build.py` fails if it turns up there), Minecraft only sends them a hash of it, and only admins
can run `/seed`. Keep it that way, because the seed shows where every ore and structure is: don't post it, and
don't hand the server zip or a hosting bundle to players. A determined cheater can still work it out from the
terrain with a seed cracker, which is one reason MinerTrack watches how people mine.

## The live map

BlueMap serves a 3D web map on port **8100**: http://localhost:8100 on the host.
Players outside your network can't reach it unless you tunnel that port too (playit.gg TCP tunnel). The
live server serves it over HTTPS at https://map.monkeysmp.lscaturchio.xyz (docs/LIVE.md, step 9).
It shows the world, not the players: `live-player-markers: false` in `server\config\bluemap\plugin.conf`,
because on a raiding server live positions would lead everyone to their targets. Builds still show, as on
any map. Where BlueMap wrote `plugin.conf` itself (a server installed before this default shipped), markers
are on: set it to `false` there and run `bluemap reload`.

It also stops at the world border. Chunky generates out to the season's largest border (docs/LIVE.md, step
6), so a map of everything generated would show the land the border acts haven't opened yet. The first
`render-mask` layer of each map in `server\config\bluemap\maps\` is a box on its dimension's border: the
shipped files fit Season I's start (2500 wide around spawn, 312.5 in the Nether), and the End has no border.
After each border act, and once on a server whose map files BlueMap wrote itself, fit the masks to the
border with `tools/map_border.py` from this repo (Python 3; on the live server the repo is at
`/srv/monkey/repo`) and render the maps again:

```
save-all                                    # console: the tool reads the border from the saved world
python3 /srv/monkey/repo/tools/map_border.py /srv/monkey/MonkeySMP-Server/server
bluemap reload                              # console
bluemap purge world                         # console: deletes the map's tiles and renders it again (an hour or so)
bluemap purge world_the_nether
```

The tool prints the `purge` lines for the maps it changed; `--check` changes nothing and exits 1 when a mask
is off. `bluemap reload` answers before BlueMap has finished loading: if a `purge` says "BlueMap is still
loading", run it again a few seconds later. A border still growing after `worldborder set` counts at its final size, so run it straight after.
No need to fit it to the finale's shrinking border: the land outside was open all season.
From Season II the border timer (`deploy/monkey-border.sh`, docs/LIVE.md) grows the border and does this fit,
the reload and the purges by itself.

The Nether map leaves out everything from y 90 up, so it shows the caves rather than the roof. Incendium
makes the Nether 192 tall, so BlueMap's own cut (y 90 to 127) left the bedrock roof covering the map. Where
BlueMap wrote `world_the_nether.conf` itself, delete the `max-y: 127` line under `min-y: 90` in its second
`render-mask` layer, then `bluemap reload` and `bluemap purge world_the_nether`.

## Moving an existing world in

Stop the server, then replace `server\world`, `server\world_nether` and `server\world_the_end` with the
folders you want, and keep `server\world\datapacks` (the installer re-adds missing datapacks on next start).

## Events

The `monkey-events` data pack (made by `tools/events.py`) has the staff side of the events in
`docs/SEASONS.md`. Run `/function monkey:events/help` in game for a clickable list. Commands below are
typed in game as an op, or over RCON without the `/`.

**Arena Glory.** Build the arena in the overworld, outside the no-PvP spawn claim (the 7 x 7 chunks around
spawn): walls and a roof, and no chests, hoppers or other containers within the radius. Everything inside the radius is cleaned every tick (dropped items and XP
vanish), and players inside are held at Strength +3 and can't withdraw Strength.

```
/function monkey:events/arena/set_lobby            # stand at the entrance; players must be within 8 blocks to join
/function monkey:events/arena/set_pit              # stand in the pit; joiners and respawns go here
/function monkey:events/arena/set_size {size:48}   # radius around the pit; leaving it takes a player out
/function monkey:events/arena/open                 # announces a clickable join
/execute as @a[tag=ev.arena] run function monkey:events/arena/kit/sword   # or archer, axe, spear, mace
/function monkey:events/arena/round                # clears arrows, tridents and items between rounds
/function monkey:events/arena/close                # takes everyone out
```

Players join with `/trigger arena set 1` (empty inventory, armor and offhand, survival mode, at the
entrance) and leave with `/trigger arena set 2`. Going in saves their Strength and sets +3 in adventure
mode; coming out clears the inventory, restores their Strength and puts them back in survival at the
entrance. Logging out, or being teleported out of the radius, takes them out the same way.

Kit gear is marked, so it can't be smuggled out:
- Players in the arena hold kit gear and nothing else; anything else is cleared every tick.
- While the arena is open, everything inside the radius that holds items is removed every tick with
  its contents: chest and hopper minecarts, chest boats, donkeys, mules and llamas. A death drops the
  kit as items, which the tick clean removes. (Until 2.8.0 a death left a corpse, from player-death-corpses,
  and the arena removed that too; the pack-side lines stay, harmless, for an older world.) Keep the size
  inside the arena's walls so nobody else's things are in that radius.
- Players can't join with a bundle in their ender chest (gear in a bundle would be missed), and leaving
  strips kit gear and any bundle from the ender chest.
- Kit gear that still gets out (a hopper under the floor) is cleared from any player outside
  the arena as soon as they take it; nothing else in that container is touched.

**Anarchy and Faction Raid.** Each start shows a boss bar to everyone and counts down on its own.

```
/function monkey:events/anarchy/start   # 90 minutes, then a 10-minute ceasefire; then clears totems, end crystals, enchanted golden apples
/function monkey:events/anarchy/stop
/function monkey:events/raid/start      # 2 hours; a player who logs out during it loses any flag they carry
/function monkey:events/raid/stop
```

**Flags, books and the Cup.**

```
/function monkey:events/flag/make {id:"red",name:"Red Monkeys"}    # hold a banner: makes it that faction's numbered flag
/function monkey:events/book/sharpness {season:"I"}                # run as the winner: a lore-tagged event book
/function monkey:events/cup/faction {id:"red",name:"Red Monkeys"}  # once per faction
/function monkey:events/cup/add {id:"red",points:30,why:"Build Battle, 1st"}
/function monkey:events/cup/show                                   # or cup/hide
```

A flag keeps its tag and number when it is placed and broken. Copies made in a crafting grid carry the
same number, so two flags with one number means a copy. Book names are the enchantment ids (`book/protection`,
`book/efficiency`, ...); Fire Aspect, Flame, Breach, Density, Wind Burst and the curses have none.

**Weekly standings and bounties.** The `monkey-standings` data pack (made by `tools/standings.py`) counts
the week's kills and holds the board; the VPS works the standings out and posts them on Sundays
(`docs/SEASONS.md`, "Weekly standings"; `docs/LIVE.md`). `/function monkey:standings/help` lists these:

```
/function monkey:standings/place                                        # stand at spawn: puts the board there
/function monkey:standings/remove                                       # next to it: removes it (to move it)
/function monkey:standings/bounty/post {target:"Alex"}                  # posts a bounty in chat
/function monkey:standings/bounty/claim {hunter:"Steve",target:"Alex"}  # once you have checked the kill
/function monkey:wanted/on                                              # the wanted board: players post bounties
/function monkey:wanted/off                                             # (docs/SEASONS.md, "Switches")
```

- **Bounties.** Post them on the top Strength holders. Claim one only for a fair kill outside the arena
  (not a friend handing over a kill, B13). The hunter's faction gets +5 standings points that week, and
  the hunter the Bounty Hunter title (a red `[Bounty Hunter]` before the name) if they show no other
  title or supporter color; one they paid for is never replaced, and the command tells you so. The title
  lasts the season. Nothing is sold and nothing else comes with it.
- **The wanted board** (`docs/SEASONS.md`, "The wanted board"; off until `wanted/on`): players post bounties
  with `/trigger wanted`, and a kill claims them by itself, giving only the title and a chat line (never
  standings points). Over RCON: `scoreboard players get NAME st.wanted` (bounties on them now),
  `scoreboard players set NAME st.wanted 0` (clears the bounties on them, say ones posted to harass),
  `scoreboard players remove NAME st.hunts 1` (takes back a claim from fed kills, B13; take the title with
  `team leave NAME` if it came with it), `scoreboard players reset NAME wt.last` (lets them post again now).
- **The Cup column** matches `cup/faction` names to parties: give each faction's Cup entry the party's
  name (`/openpac` shows it), or its owner's name, so the Cup points land on the right row. An entry
  that matches no party shows on its own row, and the VPS logs a warning.
- **Taking back fed kills (B13)** or a wrong claim, over RCON: `scoreboard players remove NAME st.kills 3`
  or `scoreboard players remove NAME st.bounty 1`. Only what is above the week's starting snapshot
  counts, so it can't go below zero for the week.
- **The board** updates every hour with this week so far. It's an entity, so it only changes while
  spawn is loaded; it catches up within a second of someone coming near. `/trigger standings` shows the
  same in chat, anywhere.
- **The Sunday recap** ("Monkey SMP Weekly", docs/SEASONS.md) is worked out when the week closes. To see what
  it would say now, on the VPS: `sudo -u monkey sh /srv/monkey/repo/deploy/monkey-standings.sh preview`
  (changes nothing). Kills or a bounty you take back after the close stay in that week's recap; take them back
  before Sunday 7 PM Pacific. Events count in its turnout line only when begun with `events/begin`.

**War and pacts.** Faction leaders (party owners) declare war and make pacts with `/trigger diplomacy`
(`docs/SEASONS.md`, "War and pacts"). The hourly board run gives each party its faction number in game; a
party made since can't take part until the next run. `/function monkey:diplomacy/help` lists these:

```
/function monkey:diplomacy/staff/factions          # every faction's number and name
/function monkey:diplomacy/staff/end {a:3,b:7}      # ends the war or pact between factions 3 and 7, announced
/function monkey:diplomacy/staff/wars_on            # declarations are 7-day wars from now (off by default)
/function monkey:diplomacy/staff/wars_off           # back to wars until Sunday's close; running 7-day wars go on
/function monkey:diplomacy/staff/wars               # on or off, the 7-day wars running, and the game's clock
```

- **7-day wars** (`docs/SEASONS.md`, "7-day wars") need the sieges timer (`docs/LIVE.md`): without its clock a
  leader is told the time isn't set yet. A staff `end`, peace and a faction gone end one early. To move a
  war's end by hand: `scoreboard players set #3.7 dp.until <minute>` (the lower faction number first; the
  minute is Unix time / 60, as `staff/wars` shows the clock). A faction can declare again 48 hours after
  its last declaration (`#f3 dp.next`; `scoreboard players reset #f3 dp.next` lifts it). A kill on a player
  who respawned less than 10 minutes ago doesn't count (rule 5).

- **Ending one by hand.** Use `staff/end` when a war or pact breaks the rules (a pact that is really a
  confederation, rule 31) or was made by mistake. Everyone is told it was staff, and it goes in the Sunday
  post.
- **Taking back fed war kills (B13)**, over RCON: `scoreboard players remove NAME st.warkills 3`, as well
  as `st.kills` (above). A war kill counts in both.
- **Before the launch** nobody can declare. The first second after `rules/launch`, every war, pact, offer
  and war kill from before it is cleared.
- Wars and offers end at Sunday's close; pacts stand. The close ends the ones running when the world last
  saved, so a war declared in the last few minutes before it runs to the next close. If the close couldn't
  reach the server, its next run ends those same ones, never a war declared since.
- **"faction N (name) is missing from the parties read"** in the board run's log: one read didn't find the party. If the
  next run still doesn't, its wars and pacts end. A run that reads no parties at all ends nothing and says so.

**Outpost sieges.** Twice a week the outposts are the prize (`docs/SEASONS.md`, "Outpost sieges"): a capture
during a window earns a bonus hour held, once per outpost per window. Faction claims are never opened. Off by
default. `/function monkey:sieges/help` lists these:

```
/function monkey:sieges/staff/on        # outpost sieges on (a window due now opens within a second)
/function monkey:sieges/staff/off       # off, and a window open now closes at once
/function monkey:sieges/staff/status    # on or off, open or not, and the next window
```

- A window opens and closes by itself on the sieges timer's clock (`docs/LIVE.md`); without the timer
  nothing opens.
- Each siege is a staff event: rule 41's exemption holds inside an outpost's square while the window is open,
  and nowhere else. Every other rule holds; a claim griefed during a siege is rolled back as always (rule 42).
- To take back a bonus given by mistake: `scoreboard players remove #f3 op.min 60` (faction 3).

**Attendance.** `/function monkey:events/begin {name:"Faction Raid"}` starts an event; then
`/execute as <player> run function monkey:events/attend` for everyone who came (joining the arena counts
on its own). Each player counts once per event, in the `rw.events` score. Rallier unlocks at 3 events and
the Plumed Helm at 10 (`docs/RETENTION.md`). An event begun this week also counts for the weekly challenge
"Come to an event" when it is on, so always start events with `begin`. On the launch weekend, begin the
Build Battle after `rules/launch`: the launch starts challenge progress from zero.

**Holidays.** At Hallowtide, Midwinter and Midsummer (`docs/SEASONS.md`, "Holidays"), stand with the
crowd near the end and give everyone there the holiday's skin, as well as running `attend`:

```
/scoreboard players set @a[distance=..48] rw.hallowtide 1     # or rw.midwinter, rw.midsummer
scoreboard players set NAME rw.hallowtide 1                   # one player, over RCON
```

These are never sold or granted outside the event.

**Ending a season.** `docs/SEASONS.md`, "Ending a season", is the full runbook. The world lock:

```
/function monkey:events/season/lock     # survival players to adventure, PvP off, peaceful; kept across restarts
/function monkey:events/season/unlock   # back to survival, PvP on, normal difficulty
```

`tools/season.py download` zips the final backup's world for players, and `tools/season.py carry` puts
the wardrobe scores, hours played and title teams into the next season's world.

`tools/wrapped.py start` keeps where everyone's counts stand right after `rules/launch` (`save-all flush`
first), and `tools/wrapped.py build` makes the season's Season Wrapped pages from the final world after the
finale; players on its opt-out list get no page and aren't named.

**Block wheel (Build Battle).** On the maintainer's computer:

```
python tools/block_wheel.py "S1 week 3"            # three blocks, the same for anyone with that seed
python tools/block_wheel.py "S1 week 3" --spins 5
```

Announce the seed before the draw so anyone can check it. The output ends with a `tellraw` line to paste
into the console. The pool (`tools/wheel_pool.txt`) is every survival-obtainable block; rebuild it after a
Minecraft update with `--pool <data reports folder>`.

## Weekly challenges

Three challenges a week, from the pool in `tools/challenges.py`, with skins at 3, 9 and 18 done (players'
side: `docs/RETENTION.md`, "Weekly challenges"). They live in the `monkey-wardrobe` data pack. A new week
starts every Monday at 12 AM Pacific; week 1 is the week of Monday 9 November 2026, and the launch
weekend before it is week 0. The dates are `tools/season_calendar.py`'s, shared with the drops and the Crier.

What runs when, on the maintainer's computer or the VPS:

```
python tools/challenges.py schedule                 # this week and the next 11
python tools/challenges.py schedule --from 0 --weeks 13
python tools/challenges.py commands                 # what monkey-week.timer sends this hour
```

The server has no calendar: `monkey-week.timer` sends the week every hour (`docs/LIVE.md`, step 7), and
`sh /srv/monkey/repo/deploy/monkey-week.sh --check` on the VPS shows the commands and whether the timer runs.
Over RCON (or in game with `/`):

```
scoreboard players get #week rc.week                # the week the server is on (-1: it was never told)
function monkey:challenges/sync {week:5}            # start week 5 unless it is already on (clears this week's progress)
function monkey:challenges/restart                  # clear everyone's progress this week; finished ones stay counted
scoreboard players get NAME rw.challenges           # a player's challenges done, all seasons
```

The timer sends the real week every hour, so a `sync` to another week lasts until the next hour, and each
switch clears the week's progress: use it on a test server, not the live one.

**Editing the pool.** `POOL` in `tools/challenges.py` is the one place. Each entry has an `id` (short,
lowercase; it names the challenge's scores), a `kind` (solo, faction or explore), a `name` (at most 30
characters, so the menu line fits), a `goal`, an `about` (the hover text: what counts) and one way of
counting: `mine` (blocks mined minus the same blocks placed), `stat` (a statistic from the allowed list in
`tests/test_challenges.py`), `kill` (mob types, never players), `loot`, `visit` (kinds of structure),
`days` or `event`. Week N runs entry N mod (how many of that kind) of each kind, in the order listed, so:

- Change the pool between weeks, and deploy before Monday 12 AM Pacific. Adding or removing an entry
  shifts the rotation of every later week: check `schedule` before and after, and tell players if a week
  you announced changes.
- Don't rename or remove the challenge that is on this week (its progress is in scores named after its id).
- Keep two or more of each kind, so no kind repeats two weeks running, and about one to three hours of play a
  week in all.
- Nothing that rewards PvP kills, forces griefing, or can be farmed with an alt, a water stream or a vehicle.
  Distance and time online are out for that reason; the tests check the statistics and the kill lists.
- Known limit: `mine` subtracts only the miner's own placing, so a friend who places blocks for someone to
  mine farms it. That costs the friend the blocks (logs and ancient debris drop themselves; ores need Silk
  Touch), so keep `mine` rewards small and look at anyone who finishes one in minutes.

Then `python tools/datapacks.py` (it writes the challenges into the wardrobe pack), run the checks, and
release. Players need a new client pack only when skins change.

**The launch weekend (Founder's Circlet).** `function monkey:rules/launch` opens it, and it closes by itself
at the end of Sunday 8 November, Pacific (31 hours of game time, kept to the wall clock by
`monkey-week.timer`). It works in Season I only. If something goes wrong:

```
function monkey:wardrobe/founder/open               # open it as the launch does, if rules/launch didn't run
function monkey:wardrobe/founder/open_for {hours:6} # open it, or keep it open, for 6 hours of game time from now
function monkey:wardrobe/founder/close              # close it now
scoreboard players get #founder.open rw.day         # 1 while it is open
scoreboard players get NAME rw.launchtime           # seconds NAME was online while it was open (600 unlocks)
```

`open_for` is manual: the wall clock no longer moves its end, so close it yourself at the end of Sunday if
it runs past. Game time stops while the server is empty, so a manual window can last longer than its hours.
Founder's Circlet is never sold. Setting `rw.launch` by hand is only for making good an outage during the
window. The first `rules/launch` in Season I clears what test play earned (challenges done, `rw.launch` and
`rw.launchtime` from a window opened to try it) and sets `#launched rw.day`, so running it again later
clears nothing and doesn't open the window again (use `founder/open` above if it has to).

## First-week quest and server goal

Players' side: `docs/RETENTION.md`, "The first week" and "The weekly server goal". The on and off switches
are in `docs/SEASONS.md`, "Switches". Both live in the `monkey-wardrobe` data pack, and nothing in them
runs before `rules/launch`; the first launch clears what test play did.

```
scoreboard players get NAME rq.state                # quest: unset not seen yet, 0 not taking part, 1 on, 2 done, 3 hidden
scoreboard players get NAME rq                      # quest: steps done
scoreboard players set NAME rq.state 1              # sign a player up by hand (a returning friend, say)
function monkey:goal/target {n:3000}                # this week's goal target, until the week turns
scoreboard players get #total rg                    # this week's goal total so far (#target rg: the target)
python tools/goal.py schedule                       # which goal runs in which week
```

The Guide's "Talk to the Guide" step and its "Your first week" button come with its preset: after a release
that changes them, place the Guide again (`function monkey:npcs/guide/here`, "Spawn NPCs" above). The
Pathfinder blade needs the new client pack.

**Editing the goal pool.** `POOL` in `tools/goal.py`, as the challenges' pool: an `id` (it names the goal's
scores, so don't rename the one that is on), a `name` (at most 24 characters), a `target` for about 20 to 30
active players, an `about`, and `mine` (blocks, mined minus placed) or `stat` (a `minecraft.custom` statistic
that takes real play: never distance or time online). Week N runs entry N mod how many.

## Supply drops

On weeknight evenings, once enough people are on, chests of supplies land outside every territory
(`docs/SEASONS.md`, "Supply drop"). They live in the `monkey-drops` data pack, generated by `tools/drops.py`,
and `monkey-drops.timer` on the VPS starts them (`docs/LIVE.md`, "The supply drops' timer").

- **When.** Monday to Thursday, 6 to 10 PM Pacific, from Season I's first week (9 November 2026). Every 10
  minutes in those hours the timer offers the night's drop; it starts the first time 4 or more players are
  online in survival, no drop has run that night, and no event is on (the arena, a raid, Anarchy, the season
  lock). One drop a night at most. Saturday is event night, so there are none Friday to Sunday.
- **Where.** The timer picks up to 6 spots from the saved world: chunk middles in the newest border ring
  (before the first border act, anywhere 400 or more blocks from spawn; after an act, only the land it
  added), 64 or more blocks inside the border and 6 or more chunks (96+ blocks) from every claimed chunk, the
  spawn claim included, so no territory is touched (rules 34, 37 and 39). The pack then takes the first spot
  whose surface is dry, natural ground (grass, dirt, sand, stone, snow: not water or anything built)
  and tries the rest if not. Claims are read from what Open Parties and Claims last saved (every 10 minutes),
  so a claim made in the last few minutes may not count yet; the ground check still keeps a drop off a build.
- **What players see.** A chat message with the coordinates and a boss bar counting down 10 minutes, with
  reminders at 5 and 1 minute. Then 1 chest per 4 survival players online (at most 3), with a "Supply drop"
  label over them. The chests despawn 20 minutes after landing with whatever is still in them (a chest
  emptied before then goes at once), and the boss bar says when. The usual rules apply out there (the
  announcement says so): the weeknight drop isn't a staff event, so rule 41's event exemption for teaming
  doesn't cover it.
- **Loot** (`LOOT` in `tools/drops.py`): food (bread, beef, baked potatoes, a few golden carrots), iron
  ingots, coal, arrows, torches, logs, string, leather, redstone, bottles o' enchanting, lapis, the odd name
  tag or saddle. Nothing Strength, no netherite, diamonds, emeralds, golden apples, potions or enchanted gear:
  a drop must never beat progression or what players trade. The tests reject those.

Over RCON (or in game with `/`; `function monkey:drops/help` lists them, clickable):

```
function monkey:drops/status                        # what's on: state, seconds left, the settings, where
function monkey:drops/start {x:1200,z:-300}         # a drop there now, whoever is online (it still checks the ground)
function monkey:drops/here                          # a drop where you stand, now
function monkey:drops/stop                          # end it now; its chests go with what's in them
function monkey:drops/min {players:6}               # players needed for the weeknight drop (and per extra chest)
function monkey:drops/off                           # no weeknight drops until /function monkey:drops/on
function monkey:drops/on
```

A staff `start` doesn't use up the night: the weeknight drop can still come after it. A Meteor (an omen, "Omens" below) is
the same drop with a 5-minute warning and one richer chest; `status` shows it. Pick a spot outside
every territory yourself (`/openpac-claims` or the live map). Settings and a drop in progress survive a
restart. To see what the timer would do, on the VPS (it changes nothing):

```sh
sh /srv/monkey/repo/deploy/monkey-drops.sh --check   # tonight's spots, the commands, whether the timer runs
python3 /srv/monkey/repo/tools/drops.py spots /srv/monkey/MonkeySMP-Server/server/world --at 2026-11-24T03:00:00Z
journalctl -u monkey-drops --since today             # each try and why it didn't start
```

The timer logs why a night had no drop: automatic drops off, a drop already on, tonight's done, an event
on, too few players, or no spots. Times, counts, the ring and the loot are constants at the top of
`tools/drops.py`; change them there, run `python tools/datapacks.py` and the checks, and release.

## Server Firsts

The first player on the server to reach each of 14 milestones (find a diamond, enter the Nether, find a
fortress and a bastion, ancient debris, a trial vault, a mace, win a raid, defeat the Wither, light a beacon,
enter the End, slay the dragon, an elytra, wear full Netherite) is announced to everyone, with a title on
screen and a sound, and keeps that first for the season. `/trigger firsts` lists them all and who holds each.
They live in the `monkey-firsts` data pack, generated by `tools/firsts.py` (`MILESTONES` is the list). No
timer: the pack does it all.

Nothing counts before `function monkey:rules/launch`, after `function monkey:events/season/lock` (the
season's end), in the event arena, or in creative or spectator. Enter the End counts only while the End is open (`rules/open_end`), and full Netherite only once rule 24 is lifted
(`datapack disable "file/monkey-no-netherite-armor"`; the pack's own heartbeat tells the firsts, so there is
nothing else to run). The first launch of a world clears any first claimed before it; a launch run again
later clears nothing.

Over RCON (or in game with `/`):

```
function monkey:firsts/reopen/wither                # nobody holds it now; the next to do it claims it
execute as NAME at @s run function monkey:firsts/claim/wither   # give an open one by hand (an outage); NAME online
data get storage monkey:firsts held                 # every claim: name, order, week
scoreboard players get NAME rf.wither               # NAME's claim order for it (none: not theirs)
function monkey:firsts/clear                        # every first open again: test servers only
```

On the VPS, from the saved world (changes nothing; `save-all` first for the last few minutes):

```sh
python3 /srv/monkey/repo/tools/firsts.py list /srv/monkey/MonkeySMP-Server/server/world
python3 /srv/monkey/repo/tools/firsts.py champion /srv/monkey/MonkeySMP-Server/server/world --season 1
```

`reopen` is for a first taken by an exploit or a mistake; say so in Discord when you use it. A claim by hand
needs the player online and standing somewhere loaded (the pack reads their name there). Players can't bring
the dragon back (end crystals are banned), so a reopened dragon stays open unless staff respawn the dragon by
hand; to move the dragon to the right player, reopen it and run `claim/dragon` as them.

An item first (diamond, debris, mace, elytra) counts for a player only once the pack has seen them without
that item on them since the launch (the tag `rf.clean.<id>`, checked every second), so one carried over from
test play never claims it. One left in a chest, ender chest or shulker box before launch and taken out after
still would: staff who play before launch don't stash those (docs/LAUNCH.md). To change a milestone, edit `MILESTONES` before the season starts (an id names its
scores and storage, so never rename one mid-season), run `python tools/datapacks.py` and the checks, and
release.

## Monkey SMP news

One plain line in the public Discord channel (#monkey-smp) when something notable happens, a few a week at
most (`tools/news.py`, run by `monkey-news.timer`; set up in docs/LIVE.md, "The news timer"):

- **A Server First** from a short list (the early ones, diamond, fortress, bastion, debris and a vault, stay
  in game): `Steve reached the Nether.` / `won a raid.` / `got a mace.` / `lit a beacon.` /
  `defeated the Wither.` / `entered the End.` / `killed the Ender Dragon.` / `found an elytra.` /
  `is wearing full Netherite.`, each followed by `First this season.` Whoever the firsts pack says holds it
  (above), so a reopened first already posted isn't posted again.
- **The first on the server this season to finish a rare advancement**: Monsters Hunted, Adventuring Time,
  Sniper Duel, Arbalistic, Smithing with Style, A Balanced Diet, Two by Two, A Complete Catalogue, The Whole
  Pack, Serious Dedication, How Did We Get Here?, A Furious Cocktail, Hot Tourist Destinations, Uneasy
  Alliance, Return to Sender, Beaconator, The Next Generation: `Steve completed Monsters Hunted. First this
  season.` From each player's saved advancements, which keep when each was done: the earliest since the launch.
- **New factions**: `New faction: Red Wolves, led by Steve.`, or several found together in one line,
  `New factions: Red Wolves, Steve's faction and The Cartographers.`

Only players' Minecraft names and faction names go out, escaped so none can be a link or a mention, and the
posts ping nobody: never coordinates, chat, addresses or anything from a ticket. It reads only the saved world
(the server saves every 5 minutes), so a post lands 5 to 25 minutes after the moment. Nothing posts before
the launch.

The limits, in `LIMITS` and below it in `tools/news.py`: in any 24 hours at most 4 firsts, 2 challenges and
2 faction lines, 6 in all, and 2 a run. What is over a limit waits for a later run, in the order it happened,
and is dropped once it has waited 3 days. A challenge waits 15 minutes first, in case an earlier finish is
still to be saved. Each season keeps `NEWS_DIR/season-<n>.json`: every item seen and whether it was posted.
It is written before and after each post, so a run killed mid-post, or a post Discord took without
answering (a timeout, a dropped connection, a 5xx), loses that line rather than ever posting it twice; only a
refusal (a 4xx) or a failure to connect is tried again. The runs before the launch date the season, so it
counts from the launch whenever that is; turned on mid-season, or back on after more than 3 hours off, it keeps
what turned up meanwhile as baseline and posts only what is new. To change what is news, edit `FIRST_LINES` or `CHALLENGES` (an advancement id from the game's own
files) and release.

On the VPS (changes nothing):

```sh
sh /srv/monkey/repo/deploy/monkey-news.sh --check      # what the next run would post, and what waits
python3 /srv/monkey/repo/tools/news.py found /srv/monkey/MonkeySMP-Server/server/world   # all in the world, test play too
```

To leave one out (a first taken by an exploit and reopened before it posted, say), set its item's `"status"`
to `"dropped"` in that season's file, as monkey (`sudo -u monkey nano /srv/monkey/news/season-1.json`).

## Outposts

Four capture points in the newest border ring that factions take and hold for standings points
(`docs/SEASONS.md`, "Outposts"). They live in the `monkey-outposts` data pack, generated by
`tools/outposts.py`, and `monkey-outposts.timer` on the VPS places them (`docs/LIVE.md`, "The outposts' timer").

- **Where.** Every hour the timer reads the saved world. After the launch (`#launched rw.day`), and after a
  border act has finished growing, it sends up to 4 spots for each outpost: chunk middles in that outpost's
  quarter (North, East, South, West of the border's centre) of the newest border ring, 64 or more blocks
  inside the border and 6 or more chunks from every claimed chunk, the spawn claim included (as supply
  drops). The pack takes the first spot that is dry, natural ground. An outpost with a claim within 3 chunks
  moves (its holder keeps it); one with no dry spot yet is tried again the next hour with new spots. While a
  border act is still growing, or the season is locked, nothing moves.
- **Capturing.** Survival players with a faction number (`st.faction`) inside the 25-block square, 60
  seconds, one faction alone. Two factions: contested, the count waits. Nobody: it starts over.
- **Hours.** `op.min` holds each faction's minutes held since the launch (`#f3` for faction 3). A minute
  counts only while a survival player of another faction is online, so holding it overnight alone earns
  nothing. The standings count each whole hour held this week as +1 point, at most 20 (`POINTS_PER_HOUR`,
  `MAX_POINTS`). A faction whose party is gone loses what it holds within a minute of its name going
  (diplomacy removes it at the second board run without the party), and its minutes at the next hourly
  run. Taking minutes off (below) lowers that faction's hours for the week, never under 0; the launch draws
  a new `#epoch op`, so a week that began before it counts every minute from the launch.
- **The live map.** The timer writes an "Outposts" marker set into the Overworld map's
  `config/bluemap/maps/*.conf` (between two `# Monkey SMP outposts` lines; leave them) and sends
  `bluemap reload` after it wrote a changed one. Only the spots, not the holders. A config it can't write
  is left as it is, with a `map:` line in the journal each hour and no reload.

Over RCON (or in game with `/`; `function monkey:outposts/help` lists them, clickable):

```
function monkey:outposts/status                     # each outpost: where, holder's number, who is capturing it
function monkey:outposts/release {i:1}              # free outpost 1 (1 North, 2 East, 3 South, 4 West), announced
function monkey:outposts/off                        # no captures, no hours and no new spots until on
function monkey:outposts/on
scoreboard players remove #f3 op.min 120            # take 2 hours off faction 3's week (B13), not below 0
function monkey:diplomacy/staff/factions            # which number is which faction
```

Holders, capture counts and hours survive a restart. Turning outposts off or locking the season stops a
survey that is running: it lets the chunk it was checking go and announces nothing. To see what the timer would do, on the VPS (it changes
nothing):

```sh
sh /srv/monkey/repo/deploy/monkey-outposts.sh --check   # the outposts, the commands, whether the timer runs
python3 /srv/monkey/repo/tools/outposts.py status /srv/monkey/MonkeySMP-Server/server/world
journalctl -u monkey-outposts --since today              # each survey and what it returned
```

To place them all again now (a bad spot, say), set `#ring op` to 0 over RCON
(`scoreboard players set #ring op 0`) and wait for the next hour: holders start over. The square, the
capture time, the points and the gaps are constants at the top of `tools/outposts.py`; change them there,
run `python tools/datapacks.py` and the checks, and release.

## Omens

Short world events that nobody announces ahead, on one or two weekday evenings a week (`docs/SEASONS.md`,
the event catalog). They live in the `monkey-omens` data pack, generated by `tools/omens.py`, and
`monkey-omens.timer` on the VPS starts them (`docs/LIVE.md`, "The omens' timer").

- **When.** Two evenings a week, Monday to Friday, from Season I's first week. Each has a start time between
  6:00 and 8:50 PM Pacific; from then until 10 PM the timer offers the evening's omen every 10 minutes, and
  it starts the first time 4 or more are online in survival, the season has launched (`#launched rw.day`),
  no omen has run that evening, no event is on (the arena, a raid, Anarchy, the season lock) and no supply
  drop is on. An evening that never gets 4 players has none, so a week has 0 to 2. Never Saturday or Sunday.
- **The surprise.** The pack draws two random numbers the first time it loads and keeps them in the world's
  scoreboard (`#key1` and `#key2` in `om`). `tools/omens.py` reads them from the saved world and works out each
  week's evenings, start times and the order the omens are tried in. Nothing in the repo gives them away.
  Don't show or change those two scores: a new world gets new ones. `tools/omens.py plan` prints the week
  (below), for staff who need to know.
- **The omens.** The pack tries them in the week's order and starts the first that can:
  - **Blood Moon.** "The moon is coming up red tonight", then at the next nightfall (it rises only at the
    start of a night, never just before dawn) a title and a boss bar: the game goes to Hard, and hostile night
    mobs within 48 blocks of a survival player in the Overworld get a few seconds of Speed and Resistance,
    given again every second while the moon is up, so they wear off by themselves after dawn. Each one a
    player kills drops a little extra at their feet (bones, string, gunpowder, arrows, iron and gold nuggets,
    bottles o' enchanting; at most 20 a player); a mob roused at an earlier Blood Moon gives nothing. It ends
    at dawn, after 15 minutes at most, or when everyone sleeps through it, and the difficulty goes back to
    what it was (unless staff changed it meanwhile). If night doesn't come within 21 minutes (daylight cycle
    off), it fades. Not on Peaceful, and it fades if staff set Peaceful before it rises.
  - **Meteor.** A supply drop announced 5 minutes ahead with a purple boss bar, one chest with more in it
    (`METEOR_LOOT` in `tools/drops.py`, on top of the usual loot: more iron, gold, copper, obsidian, magma,
    amethyst, bottles o' enchanting). It lands like any drop, in the newest ring away from claims, and is
    extra: the night's own drop still comes after it. From 9:25 PM on a drop night (Monday to Thursday) it
    only comes once that night's drop has happened, since it holds the drop for up to 25 minutes and the
    night's drop would miss its last chance before 10 PM. If none of its spots is dry ground, it never comes
    and the evening's next omen is tried at once. Not while automatic drops are off.
  - **Truce Hour.** `gamerule pvp false` for 60 minutes, with a boss bar; PvP comes back on at the end. Not
    when PvP is off already, and an event that starts during it ends it first.
  - **Hunted.** The online player with the longest kill streak (3 or more players killed without dying,
    outside the arena, counted from the launch) is hunted for 30 minutes: a title, a boss bar, and the
    standings bounty posted on them (`standings/bounty/post`). Whoever kills them is named in chat. As for
    any bounty, check the kill was fair, then claim it:
    `function monkey:standings/bounty/claim {hunter:"Steve",target:"Alex"}` (+5 standings points and the
    Bounty Hunter title). Nothing shows where the hunted player is. The hunt ends if they die some other way
    or log off; when it ends without a kill, chat says the bounty is withdrawn, so a kill after that line
    doesn't claim it.
- An event that starts during an omen ends it (a Meteor's drop carries on). Nothing an omen gives helps in a
  fight: no Strength, nothing the rules ban, no diamonds.

Over RCON (or in game with `/`; `function monkey:omens/help` lists them, clickable):

```
function monkey:omens/status                 # what's on, seconds left, the settings, last evening with one
function monkey:omens/start/blood_moon       # a Blood Moon at the next nightfall
function monkey:omens/start/truce            # a Truce Hour now
function monkey:omens/hunt {name:"Alex"}     # hunt Alex for 30 minutes (online, in survival, any streak)
function monkey:omens/stop                   # end the omen now (a Meteor's drop: function monkey:drops/stop)
function monkey:omens/min {players:6}        # players needed for an evening's omen
function monkey:omens/off                    # no automatic omens until /function monkey:omens/on
function monkey:omens/on
```

A Meteor by hand is a supply drop (`function monkey:drops/start`, above). A staff start doesn't use up the
evening. Settings and an omen in progress survive a restart. On the VPS (it changes nothing):

```sh
sh /srv/monkey/repo/deploy/monkey-omens.sh --check   # the commands for now (none outside an evening), the timer
python3 /srv/monkey/repo/tools/omens.py plan /srv/monkey/MonkeySMP-Server/server/world   # this week: spoils it
journalctl -u monkey-omens --since today             # each try and why it didn't start
```

The timer logs why an evening had no omen: automatic omens off, the season not launched, an omen or a drop
already on, tonight's done, an event on, too few players, or none of the omens could start (Peaceful, PvP off,
drops off or no dry ground, nobody with a streak online). The evenings, times, lengths and loot are constants
at the top of `tools/omens.py`; change them there, run `python tools/datapacks.py` and the checks, and release.

## The season story

The Town Crier's weekly line and the hidden pages of the season's story (docs/SEASONS.md, "The season story";
`tools/lore.py`). Off until `lore/on` (docs/SEASONS.md, "Switches").

```
python tools/lore.py plan                                   # each week's page and where it goes
/function monkey:lore/hide/3                                # in game, standing at the spot: hides week 3's page
/function monkey:lore/unhide                                # removes the hidden page nearest you (5 blocks)
/execute as NAME run function monkey:lore/find/3            # counts week 3's page as found for NAME (once)
/execute as NAME run function monkey:lore/book/3            # gives NAME another copy of week 3's book
scoreboard players get NAME lr.found                        # pages NAME has found
```

- **Hide every page once per world**, where `plan` says (spawn, an outpost, near the border, the Nether, by the
  arena), all before the launch if you like: a page shows and can be found only from its own week. Put it
  somewhere a player can stand within 4 blocks of; a marker works only while its chunk is loaded, so not
  inside a spawn chunk nobody visits is fine, but don't bury it in a wall. Hide one page in two spots if the
  first is hard to reach; each player still finds it once.
- The outposts move with the border, so for "at one of the outposts" pick one in the week it is announced.
- A player who lost a book: `book/<week>` gives a copy and changes nothing else.

## Monument of the Month

A monthly faction build contest, voted on in Discord (docs/SEASONS.md, "Monument of the Month";
`tools/monuments.py`). Off until `monuments/on` (docs/SEASONS.md, "Switches").

```
python tools/monuments.py plan                              # the months, their themes and open commands
/function monkey:monuments/open/2026-11                     # opens November's contest (The Gate): empty entries
/function monkey:monuments/close                            # no more entries; lists them for you
/function monkey:monuments/entries                          # the entries, by faction number
python3 tools/monuments.py entries WORLD                    # the same, as Discord posts (save-all first)
/function monkey:monuments/win {faction:2}                  # faction 2's entry wins: announced, kept in the hall
python3 tools/monuments.py hall WORLD                       # every winner kept, with its number
/execute as NAME run function monkey:monuments/warp {n:1}   # takes NAME to monument 1
```

The month, by hand:
1. On the 1st (or the first Saturday), `open/<YYYY-MM>`; everyone online is told the theme. Post it in
   `#monkey-smp` too.
2. Around the 25th, `close`. Run `entries` on the VPS and post each entry as its own thread in `#monkey-smp`
   (faction and coordinates); ask each faction to add a screenshot to its thread. React with a star on each to
   start the vote.
3. After 48 hours, count the stars (a tie goes to the owners) and run `win {faction:N}` with the faction number
   from the post. The Sunday recap names it that week.
4. Next season: `tools/season.py carry` copies the hall. Give each monument a warp at spawn: an Easy NPC button
   with a COMMAND action, permission level 2, `/execute as @initiator run function monkey:monuments/warp {n:N}`
   (as the Guide's Discord button does, docs/ADMIN.md "Spawn NPCs").

Undoing a wrong winner: `data remove storage monkey:monuments hall[{n:N}]` (only the last one, so the numbers stay
in order), then `data remove storage monkey:monuments contest.won` and run `win` again.

## The border boss

A boss on each Season II border act (`docs/SEASONS.md`, "The border boss"), in the `monkey-boss` data pack
generated by `tools/boss.py`. The border timer (`tools/border.py`) sends the act's boss after the act itself; it
only rises with the switch on, from Season II, after the launch and before the lock. Over RCON:

```
function monkey:boss/on                                   # the switch (refused in a Season I world)
function monkey:boss/off                                  # no boss on the next act; one up or waiting leaves now
function monkey:boss/status                               # switch, last act, state, seconds left, the records
function monkey:boss/act {act:1,x:-985,z:1952,delay:615}  # what the timer sends: act 1's boss at X Z, rising in
                                                          # 615 seconds (delay:0 for now). Once an act.
function monkey:boss/reset                                # TEST SERVERS ONLY: forget every act (and switch off)
```

The act command answers with a number the timer's log turns into words (`journalctl -u monkey-border`): 1 the
boss is announced, 10 the switch is off, 11 not Season II, 12 not launched, 13 the season is locked, 14 that act
already had its boss, 15 a boss is already up. To hold one back, turn the switch off before the act. On the VPS
(it changes nothing):

```sh
python3 /srv/monkey/repo/tools/boss.py spot --season 2      # where each act's boss rises
python3 /srv/monkey/repo/tools/boss.py status /srv/monkey/MonkeySMP-Server/server/world   # risen, slain (by whom), left
```

## The finale

The finale's border close (`docs/SEASONS.md`, "The finale"), in the `monkey-finale` data pack generated by
`tools/finale.py`. The border timer sends `function monkey:finale/start {x:X,z:Z,cx:CX,cz:CZ}` (the monument, 192
blocks east of spawn, and the Overworld border's centre, spawn) from 6 PM Pacific on week 11's Saturday, once the
saved world shows the switch on. Build the monument there before week 11: `finale.py plan --world` prints where.
Over RCON:

```
function monkey:finale/on                  # the switch (refused in a Season I world)
function monkey:finale/off                 # the timer won't start it (a running finale goes on)
function monkey:finale/status              # switch, phase, second of the finale, the result
function monkey:finale/start {x:192,z:0,cx:0,cz:0}   # start it now: monument X Z, border centre CX CZ (the
                                           # timer does this; finale.py plan --world prints it). Once a world.
function monkey:finale/stop                # end a running finale: the border stays where it is, no winner
function monkey:finale/reset               # TEST SERVERS ONLY: forget it so it can start again
```

The start answers 1 started, 10 switch off, 11 not Season II, 12 not launched, 13 locked, 14 already started,
15 the monument is more than 2400 blocks (either way) from the border's centre. `finale/stop` leaves the border
where it is, its size and its centre: a border still growing from an act stops growing too.
The timer checks the saved world, so after `finale/on` wait for the next autosave (or `save-all`) before 6 PM.
After the close (`docs/SEASONS.md`, "Ending a season", step 4):

```sh
python3 /srv/monkey/repo/tools/finale.py plan --season 2 --world /srv/monkey/MonkeySMP-Server/server/world
                                                               # the stages, the monument and the start command
python3 /srv/monkey/repo/tools/finale.py result /srv/monkey/MonkeySMP-Server/server/world
```

`result` prints each faction's points, the winner's roster (faction numbers as of the last hourly board run) and
the title and `rw.champion` commands. Paste them only for the season's champion by Cup points, which is usually,
but not always, the finale's winner. A tie names nobody: staff decide.

## Clip markers

A line in the server log at each big moment, for whoever cuts highlight clips from a recording of the server
(the streaming repo's clips tool reads them). They live in the `monkey-clips` data pack, generated by
`tools/clips.py`. Nothing new runs on the VPS and nothing is sent anywhere: the marker is a line in the log
the server already writes. **Off by default.**

- **The moments.** A Server First claimed (`first`), a supply drop or Meteor landing (`drop`, `meteor`), the
  Hunted player killed (`hunted`), an outpost taken (`outpost`).
- **The line.** Data packs can't write to the log, but the server logs every villager's death with its name,
  so the pack summons a silent villager at y -100 under the moment (below every dimension's floor), names it
  with the marker and kills it the same tick (it drops nothing, nobody sees it):

  ```
  [21:42:05] [Server thread/INFO]: Villager Villager['MONKEY-CLIP v=2|key=...|kind=first|title=Server First:
  Enter the Nether|players=;Steve|factions=;Red Monkeys|dim=the_nether|pos=12,64,-30'/123, l=...] died, message: '...'
  ```

  `key=value` fields split by `|`: the format version, the world's key, `kind`, `title`, `players` and `factions` (lists split
  by `;`, the moment's player first, then a second player such as the Hunted one; a player in no faction adds
  none), `dim` and the block `pos`. The time is the log's, Pacific on the VPS. `FORMAT_VERSION` in
  `tools/clips.py` goes up when a field changes meaning.
- **Forged lines don't count.** Players can put text in the log (chat) and name villagers, so the reader only
  takes the server thread's own villager-death line, at y -100, carrying the world's key: two random numbers
  the pack draws once (`#key1` and `#key2` in `cl`, like the omens' secret). Don't show them to players; a new
  world gets new ones. A line whose fields aren't exactly the format (another key, one twice, a name holding
  `|`, `;` or `=`) is left out too. It reports how many lines it left out.

```
function monkey:clips/on        # write markers
function monkey:clips/off       # stop
```

To hand a night's markers to whoever edits, copy the server's `logs/` folder (`latest.log` and the dated
`.log.gz` files) off the VPS, or print them there (it changes nothing):

```sh
S=/srv/monkey/MonkeySMP-Server/server
python3 /srv/monkey/repo/tools/clips.py markers $S/logs --world $S/world --since 2026-11-07
python3 /srv/monkey/repo/tools/clips.py key $S/world   # the key, to send with a copy of the logs (staff only)
```

Whoever reads a copy of the logs needs the key (`--key`): send it with the logs to that person only.

One JSON line a marker, with its date and time. A new feature marks its own moment with one command, as and
at its player (or at a place): `function monkey:clips/mark {kind:"boss",title:"The boss is down",other:""}`
(`clips.mark()` in Python checks the text: lowercase kinds, no `"`, `|` or `;`). `other` names a second player.

## Creator camera

Approved creators film the server in spectator: `/trigger camera` toggles it, with a clickable menu of camera
warps (spawn, the standings board, the four outposts, the event on now: the arena's entrance or a supply
drop). Toggling it off puts them back exactly where they were, in the game mode they were in. It lives in the
`monkey-camera` data pack, generated by `tools/camera.py`. **Off by default**, and it only works in a camera
window staff open.

A spectator sees through walls, so on a factions server the camera must not be a scouting tool. The rules:

- **Staff approve each creator by name** and can revoke it. Only a player in no faction (no `st.faction`
  number) can be approved or go in, and a creator who joins a faction is taken out. The faction number is as
  fresh as the hourly board run, so for up to an hour a new faction member could still go in: approve people
  you trust, and revoke at once if they join one.
- **Only in an announced window.** `camera/open` announces it in chat, and chat names each creator going in
  and out of camera.
- **Only public places, checked every tick.** Going in always starts at the camera's spawn point (staff set
  it; until then nobody can go in), and the camera stays in the Overworld within 64 blocks (either way) of its
  last warp: spawn, the board, an outpost, the arena's entrance, a supply drop. Drops and outposts are placed
  96 blocks or more from claims, so the leash doesn't reach a base next to them when they're placed.
  Spectator teleports to players and anything farther are snapped back the next tick.
- **Not from the event arena, and not within 15 seconds of being hurt** (so it isn't a way out of a fight).
- **Rule 10 and the creator's word.** Approving shows them the rules, and going in shows them again: stream
  the camera with a delay of 5 minutes or more, so nobody can snipe from it (rule 10, `docs/RULES.md`), and
  share no coordinates, bases or player positions with anyone, on stream or off. A creator who breaks it loses the camera (revoke)
  and is dealt with like any rule break (`docs/RULES.md`, "Moderation" above).

Every second the pack checks the rest again and puts back whoever no longer passes, so closing the window,
revoking, `camera/off` or a faction number end it within a second; a creator who was offline is put back at
their next login.

Over RCON (or in game with `/`; `function monkey:camera/help` lists them, clickable):

```
function monkey:camera/on                       # the switch (then open a window)
function monkey:camera/set_spawn                # once, as staff standing at spawn in the Overworld
function monkey:camera/approve {name:"Steve"}   # a creator in no faction
function monkey:camera/open {minutes:120}       # an announced camera window for an event
function monkey:camera/status                   # switch, seconds left, who is approved and in camera
function monkey:camera/close                    # end the window: everyone in camera is put back
function monkey:camera/revoke {name:"Steve"}
function monkey:camera/off
```

The creator: `/trigger camera` to go in or out, `/trigger camera set 2` for the menu again (the menu's buttons
run the warps: 3 spawn, 4 board, 5 to 8 the north, east, south and west outposts, 9 the event).
Not tried yet: a creator streaming it live with real players on the server, and the Docker or VPS server
(it was tested on a local server with fake players).

## Telling players what changed

Players read changes in two places, with the same words in both:

- **`site/src/content/changes.mdx`**, the "What changed" page on the site (`/changes`): newest first, one dated entry per update
  that players notice. It is the record a player can link to in an argument about a rule.
- **`#changelog` in Discord**, an announcement channel nobody else posts in, on the day the change goes
  live, linking to the page.

What goes in: rule changes (and the rule's number), mods added or removed, anything the client pack
needs, new wardrobe skins, config that changes play (the border, Netherite age, disabled enchantments),
and season dates. What stays out: server internals, fixes nobody could see, and anything that helps a
cheater. Write it for players: what changed, from when, and what they have to do ("Update the modpack").

When a release has a player-facing change, add its entry to `site/src/content/changes.mdx` in the same pull request (an `<Entry>` on top; the
file's first lines say how)
(`docs/MAINTAINING.md`, "Releasing"). A change made by hand on the live server (a rule ruling, a config
edit) gets an entry the same day. The site deploys from `main` (`site/README.md`).

## Troubleshooting

| Message | Fix |
|---|---|
| `The server is running. Stop it first` | It's already open in another window. |
| `Failed to bind to port` | Something else uses port 25565. Close it, or change `server-port` in `server\server.properties`. |
| `hash mismatch` | A download was corrupted or changed upstream. Run again; if it persists, report it. |
| `Could not download ...` | Check the internet connection; sites like Modrinth occasionally have outages. |
| Mac: `Start Server.command` "cannot be opened" / "could not be verified" | Right-click > Open, or System Settings > Privacy & Security > Open Anyway. Or run `sh start.sh` in Terminal, which always works. |
| macOS/Linux: `permission denied` on a `.sh` file | The unzip tool dropped the permissions. Run it as `sh start.sh` (not `./start.sh`). |
| Linux: `curl` / `wget` / `tar` not found | Install it (`sudo apt install curl`); the launchers need it to fetch PowerShell and Java. |
| Players are kicked with `Connection Throttled.` | Hostname Catcher's allow-list isn't empty. Set `allowed-domains: []` in `server\config\hostname-catcher.yml` and restart (docs/PROMOTION.md, "Counting joins per address"). |

Logs: `server\logs\latest.log`.
