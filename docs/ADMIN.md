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

Memory is picked from the computer's RAM (3 to 6 GB). To force a value, set the environment variable
`REALMS_MEMORY_GB` (e.g. `8`; on macOS/Linux `REALMS_MEMORY_GB=8 sh start.sh`) or pass `-MemoryGB 8`.

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

Open 25565/tcp (game) and 24454/udp (voice chat) in the VPS firewall; 8100/tcp too if you want
players to reach the live map.

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
| Mac: `Start Server.command` "cannot be opened" / "could not be verified" | Right-click > Open, or System Settings > Privacy & Security > Open Anyway. Or run `sh start.sh` in Terminal, which always works. |
| macOS/Linux: `permission denied` on a `.sh` file | The unzip tool dropped the permissions. Run it as `sh start.sh` (not `./start.sh`). |
| Linux: `curl` / `wget` / `tar` not found | Install it (`sudo apt install curl`); the launchers need it to fetch PowerShell and Java. |

Logs: `server\logs\latest.log`.
