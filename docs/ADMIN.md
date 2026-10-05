# Running the server (admins)

Everything below assumes the release zip is unzipped into a folder, called `TheRealms-Server` here.

## Day to day

| Do this | How |
|---|---|
| Start | `Start Server.bat` |
| Stop (saves the world) | type `stop` in the server window, or `Stop Server.bat` |
| Let someone join | `Add Player.bat`, or `whitelist add NAME` in the server window |
| Back up | `Backup World.bat` (safe while running; keeps the newest 14 in `backups\`) |
| Update to a new release | stop the server, unzip the new release **over** the old folder, start again |

Updating never touches the world or your config edits. It only swaps plugin/datapack/Paper files to the
versions pinned in the new manifest.

The same actions from PowerShell:

```powershell
.\realms\realms.ps1 start | stop | backup | status
.\realms\realms.ps1 add-player Steve
.\realms\realms.ps1 rcon "list"           # run a console command on the running server
```

Memory is picked from the computer's RAM (3 to 6 GB). To force a value, set the environment variable
`REALMS_MEMORY_GB` (e.g. `8`) or pass `-MemoryGB 8`.

## Ranks (LuckPerms)

| Rank | Can |
|---|---|
| `default` | homes, spawn, tpa, msg, pay, warps, nicknames |
| `builder` | + WorldEdit, creative, fly |
| `moderator` | + kick, mute, ban, vanish, tp, social spy, CoreProtect lookups/rollbacks |
| `admin` | everything |

```
lp user NAME parent set moderator
lp user NAME parent remove moderator
```

Ranks live in `server\plugins\LuckPerms\yaml-storage\` as plain text files.

## Griefing

CoreProtect logs every block change. Common commands:

```
co inspect                      # toggle, then click a block to see who changed it
co rollback u:NAME t:2h r:30    # undo NAME's changes in the last 2 hours within 30 blocks
co restore u:NAME t:2h r:30     # redo them if you rolled back too much
```

## Towns & Nations settings

`server\plugins\TownsAndNations\config.yml`. This pack changes:

- `allowedTimeSlotsWar: ["10:00-23:30"]`: wars only during the day
- `MinimumTimeBeforeAttack: 30`: 30 minutes' warning before an attack

Everything else is the plugin default. Stop the server before editing configs.

## Spawn protection

WorldGuard region `spawn` (`server\plugins\WorldGuard\worlds\world\regions.yml`) covers
x -864..-736, z -80..48 with PvP, TNT, creeper/other explosions, fire spread and ender pearls denied.
It matches the pinned seed's spawn point. To redraw it in game: `//wand`, select two corners,
`/rg redefine spawn`.

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
