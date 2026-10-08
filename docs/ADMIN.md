# Running the server (admins)

Everything below assumes the release zip is unzipped into a folder, called `TheRealms-Server` here.

## Day to day

| Do this | How |
|---|---|
| Start | `Start Server.bat` |
| Stop (saves the world) | type `stop` in the server window, or `Stop Server.bat` |
| Let someone join | `Add Player.bat`, or `whitelist add NAME` in the server window |
| Back up | `Backup World.bat` (safe while running; keeps the newest 14 in `backups\`) |
| Back up automatically | `Schedule Backups.bat` (Windows scheduled task, 6 AM and 6 PM while you're signed in; each run is logged to `scheduled-backups.log`) |
| Update to a new release | stop the server, unzip the new release **over** the old folder, start again |

Updating never touches the world or your config edits. It only swaps mod/datapack/server files to the
versions pinned in the new manifest.

**Exception: 1.x (Paper) to 2.x (Fabric).** These are different servers with different worlds. Unzip 2.x
into a **new** folder; the installer refuses to install over a 1.x world so nothing gets mixed up.

The same actions from PowerShell:

```powershell
.\realms\realms.ps1 start | stop | backup | status
.\realms\realms.ps1 add-player Steve
.\realms\realms.ps1 rcon "list"           # run a console command on the running server
```

Memory is picked from the computer's RAM: 3 GB on 8 GB, 4 on 12, 5 on 16, 6 on 24 and 8 GB from 32 GB up.
8 GB is plenty of memory even for 25 players (a 25-player test peaked at about 4.3 GB in use), though the CPU
can't keep up with that many (see "How many players" below). To force a value,
set the environment variable `REALMS_MEMORY_GB` (`setx REALMS_MEMORY_GB 8`, then open a new window) or pass
`-MemoryGB 8`. Size it from spark's numbers rather than giving it everything: the whole heap is reserved at
start, so more than the server uses only takes RAM from everything else. The "Prepare for Hosting" bundle
defaults to `MEMORY_GB=6` (use 8 for a big group); give that machine about 2 GB more RAM.

## How many players

Fewer than 2.2.2 said. Memory isn't the limit; one CPU core is, because the world ticks on a single thread and
needs under 50 ms per tick for full speed (20 TPS). Measured on an Intel i7-8700K (2017) with Carpet fake
players, after the world was generated:

| Players | Tick time | TPS |
|---|---|---|
| 10, moving around | ~115-125 ms | ~8 |
| 25, standing still | ~230-280 ms | ~4 |
| 25, standing still, without Strength SMP (and its 4 libraries) | ~90 ms | ~11 |
| 25, exploring new land | stalls of 10-20 s | under 1 |

So plan on **about 10 players on a typical home PC**, and expect it to feel sluggish even then. With 25 players
about 60% of the tick goes to datapack commands, mostly the ones Strength SMP runs for every player on every
tick, and it hits Minecraft's limit of 65,536 commands per tick hundreds of times a run (the rest of that
tick's commands are skipped, so its mechanics misbehave under load too). A rented
host with a current Ryzen (7000 or 9000 series) is roughly twice as fast per core; many budget plans run older
Xeons that are slower than a 2017 desktop. `tools/loadtest.py` re-runs these measurements (see MAINTAINING.md).

## Before a big group joins

- **Pre-generate the world.** Generating new terrain on the main thread is what drags the tick rate down when
  many players explore at once, and Tectonic's tall terrain makes each chunk expensive. With nobody online, in the
  server console: `chunky radius 5000`, `chunky start` (hours; `chunky progress` shows how far), then
  `worldborder set 10000` (the border takes a diameter). For the Nether (1 block there is 8 in the Overworld):
  `chunky world minecraft:the_nether` and `chunky radius 625` before `chunky start`, and
  `execute in minecraft:the_nether run worldborder set 1250`.
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
| `moderator` | + kick, ban, pardon, teleport, whitelist, Ledger inspect/search/rollback/restore (not purge) |
| `admin` | everything |

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
server gets the same terrain.

## The live map

BlueMap serves a 3D web map on port **8100**: http://localhost:8100 on the host.
Players outside your network can't reach it unless you tunnel that port too (playit.gg TCP tunnel).

## Moving an existing world in

Stop the server, then replace `server\world`, `server\world_nether` and `server\world_the_end` with the
folders you want, and keep `server\world\datapacks` (the installer re-adds missing datapacks on next start).

## Troubleshooting

| Message | Fix |
|---|---|
| `The server is running. Stop it first` | It's already open in another window. |
| `Failed to bind to port` | Something else uses port 25565. Close it, or change `server-port` in `server\server.properties`. |
| `hash mismatch` | A download was corrupted or changed upstream. Run again; if it persists, report it. |
| `Could not download ...` | Check the internet connection; sites like Modrinth occasionally have outages. |

Logs: `server\logs\latest.log`.
