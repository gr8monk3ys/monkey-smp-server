# Running the server (admins)

Everything below assumes the release zip is unzipped into a folder, called `TheRealms-Server` here.
Paths are written Windows-style (`server\logs`); on macOS and Linux they are `server/logs`.

## Day to day

| Do this | Windows | macOS / Linux (in Terminal, in the folder) |
|---|---|---|
| Start | `Start Server.bat` | `sh start.sh` (Mac: or double-click `Start Server.command`) |
| Stop (saves the world) | type `stop` in the server window, or `Stop Server.bat` | type `stop`, or `sh stop.sh` |
| Let someone join | `Add Player.bat`, or `whitelist add NAME` in the server window | `sh add-player.sh NAME`, or `whitelist add NAME` |
| Back up | `Backup World.bat` | `sh backup.sh` |
| Back up automatically | `Schedule Backups.bat` (a Windows scheduled task, 6 AM and 6 PM while you're signed in; each run is logged to `scheduled-backups.log`) | a cron job (`crontab -e`): `0 6,18 * * * cd /path/to/TheRealms-Server && sh backup.sh >> scheduled-backups.log 2>&1` |
| Update to a new release | stop the server, unzip the new release **over** the old folder, start again | the same (see below for the Mac) |

Backups are safe while the server runs and keep the newest 14 in `backups\`.

Updating never touches the world or your config edits. It only swaps mod/datapack/server files to the
versions pinned in the new manifest. On Linux, `unzip -o TheRealms-Server-<version>.zip` next to the
old `TheRealms-Server` folder updates it in place. The Mac's Finder doesn't unzip over a folder (it
makes `TheRealms-Server 2`): move `server` and `backups` from the old folder into the new one, or use
the same `unzip -o` in Terminal.

**Exception: 1.x (Paper) to 2.x (Fabric).** These are different servers with different worlds. Unzip 2.x
into a **new** folder; the installer refuses to install over a 1.x world so nothing gets mixed up.

The same actions from PowerShell (on macOS and Linux, `sh realms/realms.sh` takes the same commands):

```powershell
.\realms\realms.ps1 start | stop | backup | status
.\realms\realms.ps1 add-player Steve
.\realms\realms.ps1 rcon "list"           # run a console command on the running server
```

Memory is picked from the computer's RAM: 3 GB on 8 GB, 4 on 12, 5 on 16, 6 on 24 and 8 GB from 32 GB up.
8 GB is plenty of memory even for 25 players (a 25-player test peaked at about 4.3 GB in use), though the CPU
can't keep up with that many (see "How many players" below). To force a value,
set the environment variable `REALMS_MEMORY_GB` (on Windows `setx REALMS_MEMORY_GB 8`, then open a new window; on macOS/Linux
`REALMS_MEMORY_GB=8 sh start.sh`) or pass
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

| Do this | How (in `TheRealms-Server/docker`) |
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
  `realms-rules` pack sets the starting one (Rule 25) and the border acts grow it. With nobody online, in the
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
| `builder` | + switch game mode (`/gamemode`) |
| `moderator` | + warn, mute, kick and ban with a reason (BanHammer), vanish, look into inventories and ender chests (InvView, look only), x-ray alerts (MinerTrack), teleport, whitelist, Ledger inspect/search/rollback/restore (not purge) |
| `admin` | everything, including editing other players' inventories and IP bans |

```
lp user NAME parent set moderator
lp user NAME parent remove moderator
```

Ranks live in `server\mods\luckperms\yaml-storage\` as plain text files (LuckPerms' settings are in
`server\config\luckperms\luckperms.conf`).

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
`server\config\antixray.toml`. Some x-ray gets past it (the world seed, Distant Horizons' LODs, below), so
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
- **The fix below: no leak.** The player only had LODs of chunks they had loaded themselves, and every buried ore
  in them was one of AntiXray's fakes.

To close it, stop the server and set this in `server\config\DistantHorizons.toml`:

```toml
[server]
	synchronizeOnLoad = false
	enableRealTimeUpdates = false

[common.worldGenerator]
	generatorPlan = "DISABLED"
```

The cost: players no longer get distant terrain from the server, only LODs of what they have walked past, so the
far view fills in slowly on a fresh world. It isn't on by default; that's the owners' call.

The other way is Voxy with LOD Server Support (LSS) instead of Distant Horizons, which can scramble ores in what it
sends (`xrayObfuscation = "auto"` in `server\config\lss-server-config.yaml`; not tested here). Keep the Distant
Horizons settings above either way: the LSS client can also pull LODs from a Distant Horizons server, so changing
the client pack alone doesn't close anything.

## Claims and parties

Open Parties and Claims settings are in `server\config\openpartiesandclaims-server.toml` (how many chunks
each player may claim, whether claims are protected from explosions, and so on). Admins can claim land
for the server itself (for example around spawn) with the server-claim mode in the claims menu. Stop the
server before editing configs.

## Spawn protection

Vanilla `spawn-protection=48` in `server\server.properties`: within 48 blocks of spawn only admins (ops)
can build or break blocks. PvP is not blocked at spawn; make a server claim around it if you want that.

## World generation

The world is generated with Tectonic's Overkill settings (`server\config\tectonic.json`) plus Terralith,
Incendium, Nullscape and the structure mods. The seed is pinned in the manifest, so every copy of the
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
`/srv/realms/repo`) and render the maps again:

```
save-all                                    # console: the tool reads the border from the saved world
python3 /srv/realms/repo/tools/map_border.py /srv/realms/TheRealms-Server/server
bluemap reload                              # console
bluemap purge world                         # console: deletes the map's tiles and renders it again (an hour or so)
bluemap purge world_the_nether
```

The tool prints the `purge` lines for the maps it changed; `--check` changes nothing and exits 1 when a mask
is off. `bluemap reload` answers before BlueMap has finished loading: if a `purge` says "BlueMap is still
loading", run it again a few seconds later. A border still growing after `worldborder set` counts at its final size, so run it straight after.
No need to fit it to the finale's shrinking border: the land outside was open all season.

The Nether map leaves out everything from y 90 up, so it shows the caves rather than the roof. Incendium
makes the Nether 192 tall, so BlueMap's own cut (y 90 to 127) left the bedrock roof covering the map. Where
BlueMap wrote `world_the_nether.conf` itself, delete the `max-y: 127` line under `min-y: 90` in its second
`render-mask` layer, then `bluemap reload` and `bluemap purge world_the_nether`.

## Moving an existing world in

Stop the server, then replace `server\world`, `server\world_nether` and `server\world_the_end` with the
folders you want, and keep `server\world\datapacks` (the installer re-adds missing datapacks on next start).

## Events

The `realms-events` data pack (made by `tools/events.py`) has the staff side of the events in
`docs/SEASONS.md`. Run `/function realms:events/help` in game for a clickable list. Commands below are
typed in game as an op, or over RCON without the `/`.

**Arena Glory.** Build the arena in the overworld: walls and a roof, and no chests, hoppers or other
containers within the radius. Everything inside the radius is cleaned every tick (dropped items and XP
vanish), and players inside are held at Strength +3 and can't withdraw Strength.

```
/function realms:events/arena/set_lobby            # stand at the entrance; players must be within 8 blocks to join
/function realms:events/arena/set_pit              # stand in the pit; joiners and respawns go here
/function realms:events/arena/set_size {size:48}   # radius around the pit; leaving it takes a player out
/function realms:events/arena/open                 # announces a clickable join
/execute as @a[tag=ev.arena] run function realms:events/arena/kit/sword   # or archer, axe, spear, mace
/function realms:events/arena/round                # clears arrows, tridents and items between rounds
/function realms:events/arena/close                # takes everyone out
```

Players join with `/trigger arena set 1` (empty inventory, armor and offhand, survival mode, at the
entrance) and leave with `/trigger arena set 2`. Going in saves their Strength and sets +3 in adventure
mode; coming out clears the inventory, restores their Strength and puts them back in survival at the
entrance. Logging out, or being teleported out of the radius, takes them out the same way.

Kit gear is marked, so it can't be smuggled out:
- Players in the arena hold kit gear and nothing else; anything else is cleared every tick.
- While the arena is open, everything inside the radius that holds items is removed every tick with
  its contents: chest and hopper minecarts, chest boats, donkeys, mules and llamas. So is the corpse a
  death leaves (player-death-corpses), which would otherwise hold the dead player's kit for anyone to
  loot. Keep the size inside the arena's walls so nobody else's things, or corpses, are in that radius.
- Players can't join with a bundle in their ender chest (gear in a bundle would be missed), and leaving
  strips kit gear and any bundle from the ender chest.
- Kit gear that still gets out (a hopper under the floor) is cleared from any player outside
  the arena as soon as they take it; nothing else in that container is touched.

**Anarchy and Faction Raid.** Each start shows a boss bar to everyone and counts down on its own.

```
/function realms:events/anarchy/start   # 90 minutes, then a 10-minute ceasefire; then clears totems, end crystals, enchanted golden apples
/function realms:events/anarchy/stop
/function realms:events/raid/start      # 2 hours; a player who logs out during it loses any flag they carry
/function realms:events/raid/stop
```

**Flags, books and the Cup.**

```
/function realms:events/flag/make {id:"red",name:"Red Monkeys"}    # hold a banner: makes it that faction's numbered flag
/function realms:events/book/sharpness {season:"I"}                # run as the winner: a lore-tagged event book
/function realms:events/cup/faction {id:"red",name:"Red Monkeys"}  # once per faction
/function realms:events/cup/add {id:"red",points:30,why:"Build Battle, 1st"}
/function realms:events/cup/show                                   # or cup/hide
```

A flag keeps its tag and number when it is placed and broken. Copies made in a crafting grid carry the
same number, so two flags with one number means a copy. Book names are the enchantment ids (`book/protection`,
`book/efficiency`, ...); Fire Aspect, Flame, Breach, Density, Wind Burst and the curses have none.

**Attendance.** `/function realms:events/begin {name:"Faction Raid"}` starts an event; then
`/execute as <player> run function realms:events/attend` for everyone who came (joining the arena counts
on its own). Each player counts once per event, in the `rw.events` score.

**Block wheel (Build Battle).** On the maintainer's computer:

```
python tools/block_wheel.py "S1 week 3"            # three blocks, the same for anyone with that seed
python tools/block_wheel.py "S1 week 3" --spins 5
```

Announce the seed before the draw so anyone can check it. The output ends with a `tellraw` line to paste
into the console. The pool (`tools/wheel_pool.txt`) is every survival-obtainable block; rebuild it after a
Minecraft update with `--pool <data reports folder>`.

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
