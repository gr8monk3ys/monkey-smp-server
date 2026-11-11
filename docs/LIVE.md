# The live server (monkeysmp.lscaturchio.xyz)

How the paid, always-on copy of Monkey SMP runs: one Linux VPS running the Docker setup from the release,
kept in step with this repo by `deploy/monkey-deploy.sh`, with a home PC on playit.gg as the fallback.
The business side (prices, costs, referrals) is in the plan linked from the PR that added this file; the
public site is `site/`.

```
players --> monkeysmp.lscaturchio.xyz (SRV record) --> play.monkeysmp.lscaturchio.xyz (A) --> VPS :25565
                                                     \-> failover: SRV target swapped to the playit.gg address
browsers --> https://map.monkeysmp.lscaturchio.xyz (A) --> VPS: Caddy :443 --> BlueMap 127.0.0.1:8100
                                                                      \-> /status.json: /srv/monkey/status (monkey-status.timer)
                                                                      \-> /standings.json: /srv/monkey/status (monkey-standings timers)
staff --> https://staff.monkeysmp.lscaturchio.xyz (A) --> VPS: Caddy :443, password --> the page: deploy/staff, /srv/monkey/staff (monkey-staff.timer)
repo (tag vX.Y.Z) <-- git fetch every 5 min -- VPS: monkey-deploy.timer --> docker compose (the release's docker/)
```

## Why releases, not every push

A deploy restarts the server, and when `client/` changed every player has to update their pack before they
can join again. A release tag is the point where both exist: the release workflow publishes the matching
`.mrpack`. So the VPS follows the newest `vX.Y.Z` tag. To make any merge to `main` go live instead, set
`TRACK=main` in `/etc/monkey-deploy.env`. GitHub Actions doesn't start in this private repo right now
(billing), and the VPS pulls rather than being pushed to, so nothing here depends on Actions or on an
SSH key into the server.

### The release gate

A tag alone doesn't go live. Before a deploy warns anyone, backs up or copies a file, it asks
`tools/release_gate.py`: GitHub must have a **published** release for that tag (not a draft), the release must
point at the tagged commit, and CI must have passed on that commit. "Not yet" and "can't tell" (GitHub down, a
rate limit) both mean the deploy waits; the next run asks again. A tag pushed by mistake, or one whose CI failed,
never goes live. `--status` shows the gate's answer. Protect `v*` tags on GitHub too (a tag ruleset), so a tag
can't be moved to another commit.

Emergency only: `RELEASE_GATE=off` in `/etc/monkey-deploy.env` lets every tag through (GitHub is down and a fix
can't wait). Put it back to `on` straight after. `install-root.sh` says so while it is off.

## The machine

One fast core matters more than anything else (docs/ADMIN.md, "How many players"): a current Ryzen
(7000/9000 series) at about 5 GHz is roughly twice a 2017 desktop per core; an old Xeon runs fewer than a 2017
desktop. Pick a VPS or dedicated server that names the CPU model, with 16 GB of RAM, NVMe and a US West or
central location (the group plays evenings Pacific). Debian 12 or Ubuntu 24.04.

Running now (since October 2026): a Reizor Hosting "Ryzen 9 9950X VPS 16GB" in Dallas (2 dedicated threads,
16 GB, 200 GB NVMe, $45 a month), Debian 12, set up with the steps below.

## Set up (once)

1. **User and Docker.** As root: install Docker Engine with the compose plugin, `git`, `rsync` and `curl`;
   `adduser --disabled-password monkey`; `usermod -aG docker monkey`; `mkdir -p /srv/monkey && chown monkey: /srv/monkey`.
2. **Firewall.** Open 25565/tcp (game), 24454/udp (voice chat), and 80/tcp, 443/tcp and 443/udp for Caddy,
   which serves the live map over HTTPS (step 9). Don't open 8100: BlueMap is published on 127.0.0.1 only
   (`MAP_PORT` in step 5), because ports Docker publishes skip ufw's rules, so ufw alone could not keep it
   private. Keep SSH key-only. RCON (25575) stays unpublished (compose.yaml).
3. **Clone with a read-only deploy key.** As `monkey`: `ssh-keygen -t ed25519 -f ~/.ssh/monkey_deploy -N ''`,
   add the `.pub` file as a read-only deploy key in the repo settings on GitHub, then trust GitHub's host
   key as GitHub publishes it (fingerprint `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU` in its docs)
   rather than whatever key the network answers with, and clone:
   ```sh
   printf 'Host github.com\n  IdentityFile ~/.ssh/monkey_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config
   echo 'github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl' >> ~/.ssh/known_hosts
   git clone git@github.com:gr8monk3ys/monkey-smp-server.git /srv/monkey/repo
   ```
4. **Settings.** Back on your admin account (`monkey` has no sudo): `sudo cp /srv/monkey/repo/deploy/monkey-deploy.env.example /etc/monkey-deploy.env`, edit
   it (the Discord webhook is optional; `DEPLOY_WINDOW` is when updates may go live), then
   `sudo chown root:monkey /etc/monkey-deploy.env && sudo chmod 640 /etc/monkey-deploy.env` (the deploy
   service runs as `monkey`, so it has to be able to read the file).
5. **First deploy.** As `monkey` (`sudo -iu monkey`): `sh /srv/monkey/repo/deploy/monkey-deploy.sh` copies the release folder to
   `/srv/monkey/MonkeySMP-Server` and stops, asking for `docker/.env`: copy `.env.example` to `.env`
   there, set `EULA=TRUE`, `OWNER=<your Minecraft name>`, `MEMORY_GB=10`, `TZ=America/Los_Angeles` and
   `MAP_PORT=127.0.0.1:8100` (the map is reached through Caddy, step 9).
   To keep an existing world, copy its `server` folder into `/srv/monkey/MonkeySMP-Server/` now. Run the
   script again: it downloads about 500 MB, starts the server and records the deployed commit.
6. **Pre-generate the world** before anyone joins: exploring new land costs far more tick time than
   anything else. Leave the border alone: the `monkey-rules` pack sets Season I's starting border (5000
   wide, 625 in the Nether, centred on spawn) and the border acts in docs/SEASONS.md grow it by hand.
   Generate out to the season's largest border (6000) plus the view distance. In the console:
   `chunky worldborder` (centres Chunky on the border, not on 0,0), `chunky radius 3200` and `chunky start`
   (hours). The Nether is 1/8 the size: `chunky world minecraft:the_nether`, `chunky worldborder`,
   `chunky radius 500` and `chunky start`. It carries on after a restart because the default
   `config/chunky/config.json` sets `continueOnRestart`; on a server set up before that, set it to `true`
   in that file once and run `chunky continue`.
7. **Timers.** `sudo cp /srv/monkey/repo/deploy/monkey-deploy.{service,timer} /etc/systemd/system/`,
   `sudo systemctl daemon-reload && sudo systemctl enable --now monkey-deploy.timer`. Then
   `sudo sh /srv/monkey/repo/deploy/monkey-day.sh --install` for the day timer, which counts "days played" for
   the wardrobe (docs/RETENTION.md) at midnight UTC (`--check` shows what it sends and whether it runs). Then
   `sudo sh /srv/monkey/repo/deploy/monkey-week.sh --install` for the week timer: every hour it tells the
   server which weekly challenge week it is and keeps Season I's launch weekend on the wall clock
   (docs/ADMIN.md, "Weekly challenges"). `sh /srv/monkey/repo/deploy/monkey-week.sh --check` shows what it
   sends and whether it runs. Then `sudo sh /srv/monkey/repo/deploy/monkey-drops.sh --install` for the
   weeknight supply drops (docs/ADMIN.md, "Supply drops"), and place the spawn NPCs once the server is up
   (docs/ADMIN.md, "Spawn NPCs").
8. **DNS** (Cloudflare, which holds the lscaturchio.xyz zone): an `A` record `play.monkeysmp` to the VPS
   address with the proxy off ("DNS only": Cloudflare's proxy carries only web traffic), and an `SRV` record `_minecraft._tcp.monkeysmp` with priority 0, weight 5, port 25565, target
   `play.monkeysmp.lscaturchio.xyz`, TTL 60. Players then type `monkeysmp.lscaturchio.xyz` with no
   port, while the same name serves the website. Voice chat finds the server by itself. For the map, an `A`
   record `map.monkeysmp` to the same address, also "DNS only": Caddy gets the certificate itself. The zone has
   a wildcard record that sends any other name to Vercel, so without its own record the map name lands there.
9. **The live map over HTTPS** (after step 8, so Let's Encrypt can reach the VPS by name). As root, install
   Caddy from its apt repository (https://caddyserver.com/docs/install), copy the repo's `deploy/Caddyfile`
   to `/etc/caddy/Caddyfile` and run `systemctl reload caddy`. It proxies the map to BlueMap and serves the
   website's status file beside it ("The website's status", below). Caddy gets and renews the certificate and redirects `http://` to `https://`. The site's `MAP_URL` links
   there. Then fit the map to the border (docs/ADMIN.md, "The live map"): before the first fit the map
   shows everything Chunky generated, which is land the border acts haven't opened yet.
   Caddy rather than Cloudflare's proxy: the proxy would hide the address, but the game's own record shows
   it anyway, and it would need an Origin Rule for port 8100 plus a firewall list of Cloudflare's address
   ranges kept up to date by hand.
10. **Off-site backups**: see "Set up the off-site copy" under "Backups off the machine" below.

## Day to day

| Do this | How (on the VPS, as `monkey`) |
|---|---|
| Ship a change | merge to `main`, then tag a release as in docs/MAINTAINING.md. In the next deploy window (`DEPLOY_WINDOW`, 4-5 AM Pacific in the example settings) the VPS warns anyone online, backs up, updates and restarts |
| Ship it right now | `sh /srv/monkey/repo/deploy/monkey-deploy.sh --now` (ignores the window and skips the warning) |
| When will it go live? | `sh /srv/monkey/repo/deploy/monkey-deploy.sh --status`: the newest tag, what is live, and whether the window is open |
| What is live? | `sh /srv/monkey/repo/deploy/monkey-deploy.sh --status` |
| Deploy log | `journalctl -u monkey-deploy -n 100` |
| Console | `cd /srv/monkey/MonkeySMP-Server/docker && docker compose attach monkey` (leave with Ctrl+P, Ctrl+Q) |
| A command | `docker compose exec monkey monkey rcon "say hi"` |
| Let a player in by hand | `docker compose exec monkey monkey add-player NAME` |
| Grow the border (a border act) | Season I grows the Overworld only: `docker compose exec monkey monkey rcon "worldborder set 5500 12000"` on 21 November and `... "worldborder set 6000 12000"` on 26 December (the time is in ticks: 12000 is 10 minutes). Leave the Nether at the 2500 set by hand: the 1:8 sizes (687.5, 750) would shrink it and shut the fortress and bastion out. Then fit the map to it: docs/ADMIN.md, "The live map". From Season II the border timer does all of it (below) |
| Store or staff grants (wardrobe) | `docker compose exec monkey monkey rcon "scoreboard players set NAME rw.tier 2"`; the full list is in docs/RETENTION.md |
| Retention numbers | `python3 /srv/monkey/repo/tools/retention.py /srv/monkey/MonkeySMP-Server/server/logs` |
| Joins per join address | `python3 /srv/monkey/repo/tools/join_addresses.py /srv/monkey/MonkeySMP-Server/server/logs` (docs/PROMOTION.md) |
| This week's standings so far | `sh /srv/monkey/repo/deploy/monkey-standings.sh show` (changes nothing); log: `journalctl -u monkey-standings -u monkey-standings-board -n 50` |
| The Sunday recap, as it would post now | `sh /srv/monkey/repo/deploy/monkey-standings.sh preview` (changes nothing) |
| Backup log (as root) | `journalctl -u monkey-backup -n 50` |
| Off-site snapshots (as root) | `sh /opt/monkey/deploy/monkey-backup.sh --restic snapshots` |
| Is a release cleared to go live? | `--status` above prints a `gate:` line for a release that isn't live yet ("The release gate") |
| Old server logs | `sh /srv/monkey/repo/deploy/monkey-logs.sh --check` lists what the daily prune would delete ("Log pruning") |

Logged in as root, become `monkey` for these, for example
`runuser -u monkey -- sh /srv/monkey/repo/deploy/monkey-deploy.sh --now`. As root the deploy stops at
"cannot create /tmp/monkey-deploy.lock: Permission denied": the lock belongs to `monkey`, and the kernel's
`fs.protected_regular` keeps even root from opening another user's file in `/tmp`.

If a new release doesn't answer within `BOOT_TIMEOUT`, the script puts the previous release back, restarts
it, posts to Discord, and skips the failed commit until a newer one appears. The world backup it took
before the update is the newest folder in `backups/`. To try a skipped commit again (say, once the cause is
fixed), delete `.deploy-failed` in `/srv/monkey/MonkeySMP-Server` and run the deploy with `--now`.

## The server is down

One page for when players say they can't join. Work down the list; stop at the first thing that explains it.
All on the VPS over SSH, as `monkey` unless it says root.

1. **Is it really down?** Uptime Kuma's Discord channel says since when. Then
   `cd /srv/monkey/MonkeySMP-Server/docker && docker compose ps`.
   - `Up`, and players still can't join: go to 5.
   - `Restarting`, `Exited` or missing: go to 2.
2. **Is a deploy, the daily restart or a backup running?** `sh /srv/monkey/repo/deploy/monkey-deploy.sh --status`
   and `systemctl list-units 'monkey-*' --state=activating`. One of them can hold the server down for up to 15
   minutes. Wait for it; don't start the server by hand while one runs.
3. **Why did it stop?** `docker compose logs --tail 200 monkey`. Common causes:
   - `OutOfMemoryError`, or the container killed with code 137: memory. Run `free -g`, and check `MEMORY_GB` in
     `docker/.env` against the 16 GB.
   - A mod error at start: a release went live that doesn't start. The deploy rolls back by itself after
     `BOOT_TIMEOUT`; read `journalctl -u monkey-deploy -n 100`.
   - `No space left on device`: `df -h /srv`. Delete old folders in `/srv/monkey/MonkeySMP-Server/backups/`
     (never `server/`).
4. **Start it.** `docker compose up -d`, then `docker compose logs -f monkey` until `Done`. Then
   `docker compose exec monkey monkey rcon list`.
5. **Up, but nobody can join.**
   - DNS: `dig +short SRV _minecraft._tcp.monkeysmp.lscaturchio.xyz` names `play.monkeysmp.lscaturchio.xyz`,
     and `dig +short play.monkeysmp.lscaturchio.xyz` is the VPS address.
   - Firewall: `sudo ufw status` lists 25565/tcp.
   - The provider: their status page. A network or host problem is theirs.
6. **The machine itself is gone** (no SSH, the provider says hours): run the home PC ("Fallback: home PC on
   playit.gg") from the newest backup. Only one copy may run the world at a time.
7. **Tell players.** One line in Discord: what is down, since when, and when you will look again.
8. **After.** Check that backups ran (`journalctl -u monkey-backup -n 20`, as root) and write one line in the
   staff channel on what happened.

Failure alerts ("Monitoring, the daily restart and the update check") post to the staff channel when any
`monkey-*` job fails. The line names the unit and the `journalctl` command to read.

## Root's own copies

The off-site backup, the staff page's helper and the restore drill run as root. Root runs only copies that root
owns, in `/opt/monkey` (`deploy/` and `tools/`), never the checkout in `/srv/monkey/repo`. That checkout
belongs to `monkey`. A script there that root ran would let anyone who gets in as `monkey` (or through the
staff page) run code as root.

`deploy/install-root.sh` makes and updates the copies, as root. It fetches the release from GitHub into root's
own clone, `/opt/monkey/src`, asks the release gate, copies the files, and installs the systemd units that
changed. It also installs the new units it knows (the failure alert, log pruning and the restore drill) and starts
the log pruning timer. It never enables the restore drill's timer. It never touches the world, the backups or the
settings.

The first time, as root:

```sh
install -d -m 755 -o root -g root /opt/monkey
git clone https://github.com/gr8monk3ys/monkey-smp-server.git /opt/monkey/src
sh /opt/monkey/src/deploy/install-root.sh
```

After that, when a release changes them (the deploy posts "Root's copies ... are from another release" to the
staff channel):

```sh
sh /opt/monkey/deploy/install-root.sh --check     # what would change; any user, changes nothing
sudo sh /opt/monkey/deploy/install-root.sh        # the newest release; --tag=vX.Y.Z for another
```

`/opt/monkey/INSTALLED` holds the release and commit that are installed.

Not covered yet: `--install` of the timed jobs and of the staff page (`monkey-staff.sh --install`) still copy
their units from `/srv/monkey/repo` when root runs them. Those units run as `monkey`, so a changed unit gives
`monkey` little it didn't have, but read the diff before you run them.

## One-off steps when upgrading

A deploy never overwrites files in `server/`, and a new default config only reaches a server that doesn't have
that file yet. When a release changes a default the live server already has, its steps are here. They work
before or after the release goes live.

For 2.5.0, `deploy/upgrade-2.5.0.sh` did the Distant Horizons change (gone with the mod in 3.0.0) and the section below (the short rules, ServerCore
and claims) with a single restart, then the spawn claim, python3 and the two timers ("Monitoring, the daily
restart and the update check"). It skips whatever is already done, so it is safe to run again. Run it as root
once 2.5.0 is live, `--check` first (it says what is left and changes nothing). Under `systemd-run` it carries on
if SSH drops while the server is stopped:

```sh
sudo sh /srv/monkey/repo/deploy/upgrade-2.5.0.sh --check
sudo systemd-run --unit=monkey-upgrade --collect -p TimeoutStopSec=20min sh /srv/monkey/repo/deploy/upgrade-2.5.0.sh
journalctl -fu monkey-upgrade
```

It warns players online `WARN_MINUTES` (5) and 1 minute ahead (`--now` skips that), stops the server for about
3 minutes, keeps the old files (`DistantHorizons.toml.before-2.5.0`, the others `.pre-onboarding`) and starts the
server again whatever happens. A setting it can't find (a mod renamed it) is left for you, with the rest done.
It reads no secrets from `/etc/monkey-deploy.env` and of `server.properties` only the `enable-code-of-conduct`
line; its log is `/var/log/monkey-upgrade-2.5.0.log`. The off-site backups stay a manual step ("Backups off the
machine"): they need keys the owner makes.

### Monkey SMP names (2.10.0)

Before 2.10.0 the server's folders, user, timers, settings file and data pack namespace had the server's old
name. 2.10.0 renames all of them (CHANGELOG), so a VPS set up before it is switched over once, with the server
stopped, before 2.10.0 deploys. In this order, as root:

1. Stop and disable every old timer, the deploy timer first, so nothing deploys or sends commands mid-switch.
2. Stop the server (`docker compose down` in the old `docker` folder: the Compose project's name changed too, so
   the new one wouldn't stop the old container) and keep a copy of `server/`.
3. Move the folders to `/srv/monkey/repo` and `/srv/monkey/MonkeySMP-Server`, rename the user and its group to
   `monkey` (same uid, so the files keep their owner), its deploy key to `~/.ssh/monkey_deploy` (and in
   `~/.ssh/config`), the settings file to `/etc/monkey-deploy.env` with its `REPO_DIR` and `LIVE_DIR` updated, and
   `/var/lib/` state folders to their `monkey-` names.
4. As `monkey`, check out 2.10.0 in the repo and move the world and the server folder over with
   `python3 /srv/monkey/repo/tools/migrate_names.py /srv/monkey/MonkeySMP-Server` (lists the changes), then the
   same with `--apply`.
5. Remove the old units from `/etc/systemd/system`, install the `monkey-*` units for the same jobs from the
   checkout, enable their timers, and start `monkey-deploy.service` once: it deploys 2.10.0 and starts the server.

Worlds kept outside `MonkeySMP-Server` (`/srv/monkey/seasons/...`) keep the old names until one is put back:
run `migrate_names.py` on it first.

### The deploy timer that fires on start (the release after 3.3.0)

The release changes `monkey-deploy.timer` so it checks 1 minute after it starts (`OnActiveSec`). The old unit, once
stopped and started again, never fired: 11-04 to 11-09 no release could deploy itself. Nothing installs this unit,
so once the release is live, as root:

```sh
cp /srv/monkey/repo/deploy/monkey-deploy.timer /etc/systemd/system/
systemctl daemon-reload && systemctl restart monkey-deploy.timer
systemctl list-timers monkey-deploy.timer   # NEXT shows a time, not "-"
```

Until then, if NEXT shows "-", `systemctl start monkey-deploy.service` runs one check and restarts the 5-minute
cycle (outside `DEPLOY_WINDOW` it deploys nothing).

### 3.1.1: Mace Limiter

3.1.1 adds one server-only mod. Players keep the 3.1.0 pack and nothing they install changes. It adds no blocks, items
or world generation, so it stays on the world it finds.

Its settings and its count live in `world/macelimiter_maces.json`, made on the first start with a limit of 3. They belong
to the world, so a new world starts at 3 again. For another limit, `monkey rcon "macelimit set 5"`. Check with
`monkey rcon "macelimit"` and `monkey rcon "macelimit count"`.

### 3.1.0: the final mod list and the speed patches

3.1.0 stays on Minecraft 26.2, so the deploy loads the world it finds. Its new structures only appear in land
generated after it, so nothing else about the world changes until the launch world replaces it.

A world Amethyst Nether generated still loads without it. That was tested on a small fresh Nether, not the test world
itself: the log warns of two missing data packs and prints a "Recoverable errors when loading section" line for each
section with an `an:` biome, which falls back to a default. It looks alarming and is harmless until the reset.

**Two configs a deploy doesn't replace.** Do both while the server is stopped for the launch world.

- The live server keeps the Enchantment Disabler config 3.0.0 made, which disables nothing, so rule B18 doesn't hold
  until it is copied: `diff ../server/config/enchantmentdisabler/config.toml ../monkey/defaults/config/enchantmentdisabler/config.toml`,
  then `cp ../monkey/defaults/config/enchantmentdisabler/config.toml ../server/config/enchantmentdisabler/config.toml`.
  Check with `grep -o 'nova_structures:' ../server/config/enchantmentdisabler/config.toml | wc -l`, which prints `17`.
- Anti-xray still stops at Amethyst Nether's height: `diff ../server/config/antixray.toml ../monkey/defaults/config/antixray.toml`,
  then `cp ../monkey/defaults/config/antixray.toml ../server/config/antixray.toml` (the Nether is 128 tall again).

**The data pack needs no console step.** The Enchant Disabler data pack is a manifest pin, so the installer puts it in
`world/datapacks` before a new world's first start. It loads after Dungeons and Taverns' own packs, so its tags win, and
the disable-then-enable steps in its FAQ aren't needed. Check with `monkey rcon "datapack list enabled"`.

The launch world then follows the next section. The new jars change one number in its steps: the seed now has a fortress
about 410 blocks from the Nether's centre and a bastion about 840, both still outside the pack's 625 (312 either way), so the Nether's
border stays 2500 (the 440 and 1500 below are the 3.0.0 terrain). The spawn area, monuments and NPC spots still need the
walk, on land this release changed again.

### 3.0.0: Minecraft 26.2 and a new world

3.0.0 moves the server from Minecraft 26.3 back to 26.2 and to the owners' mod list. A world can't go back a
Minecraft version, so Season I gets a new one. Follow "A new world for Season I (2.8.0)" below, with these changes. It takes hours.

**The order differs: the old world leaves before the deploy.** A 26.2 server can't load the 26.3 world, so letting
the release deploy first would fail its boot and roll back. Pause deploys, run `monkey backup` while the server is
up and keep that backup, stop the server, move the world aside, carry, and only then run
`sh /srv/monkey/repo/deploy/monkey-deploy.sh --now`. It skips its own backup when the server is stopped, and its
first start makes the new world.

Before the first start on 3.0.0, while the server is stopped:

1. **One Tebex jar.** Tebex is now a managed mod, but its file name (`tebex-fabric-26.2-2.4.6-0096441.jar`) differs
   from the jar placed by hand on the live server (`tebex-fabric-26.2-2.4.6.jar`), so a deploy leaves both. They
   were the same bytes and the server still started, but remove the hand-placed one:
   `ls ../server/mods/*tebex*.jar | wc -l` prints `1`. Leave the `tebex` folder beside it: it holds the store's key.
2. **Configs a deploy doesn't replace.** The live server keeps its own copy of a config, so copy the one that
   changed: `diff ../server/config/antixray.toml ../monkey/defaults/config/antixray.toml` first, as the copy
   replaces any tuning made on the server, then
   `cp ../monkey/defaults/config/antixray.toml ../server/config/antixray.toml` (the Nether was 160 tall
   then; 3.1.0 sets it back to 128). Leftovers from mods that left (Carry On, Tectonic, Distant Horizons, MinerTrack) are harmless; delete
   them if you like.

Changes to the steps below:

- **Step 1:** the folder to keep is `/srv/monkey/seasons/pre-3.0/`, with the backup taken just before the world moved.
- **Step 4:** move the old world to `/srv/monkey/seasons/pre-3.0/world`. The short rules didn't change.
- **Step 5:** carry from that folder, still `--season 1`. The wardrobe scores, tiers and grants come across, and
  so do `rw.months` and tier from any staff test purchase. Skip the step if the owners want those gone.
- **Step 6: the seed is the owners' call.** The land differs either way, because the terrain mods left.
- **After the first start: the Nether's border goes to 2500.** On this seed nothing is inside the pack's 625 (312 either way): the
  nearest fortress is about 440 blocks from the Nether's centre and the nearest bastion about 1500. Without a
  fortress there are no blaze rods, so no eyes of ender for Dragon Night. So on every copy of this seed, the fresh
  launch world included: `monkey rcon "execute in minecraft:the_nether run worldborder set 2500"`, before the map
  fit in step 9. A portal still lands inside the Overworld's border, because the game clamps it.
- **Step 10:** the Nether's radius is 1300, not 500. Qrafty's End Villages left; End cities are the reason to
  pre-generate the End.
- **After step 12, look around:** the terrain is new, so the spawn area, monuments and NPC spots all need a walk
  (docs/LAUNCH.md, "Ops readiness"). Then render the map and fit its border (`tools/map_border.py`).

### A new world for Season I (2.8.0)

2.8.0's structures and its new End (Dungeons and Taverns, Crazy Chambers, Endercon, Qrafty's End Villages) only
appear in land generated after it, and the live world is already pre-generated, so Season I needs a new world.
The old world also holds blocks and mobs from mods 2.8.0 drops (CHANGELOG). Do this once 2.8.0 is live, well
before launch: the pre-generation takes hours (docs/LAUNCH.md checks it), and before the deploy freeze. Avoid
midnight UTC (the day timer) and weeknights 6 to 10 PM Pacific (the drops timer). The old world plus a backup
copy need about twice the world's size free: `du -sh ../server/world` and `df -h /srv` first.

What stays by itself, because it lives outside `server/world`: the whitelist, ops and bans, BanHammer's records,
ranks (LuckPerms), every config (including the new 2.8.0 ones), the map's settings and the timers.

What lives only in the old world and stays with it: every build, inventory, ender chest and stat
(`world/players`); claims and parties (`world/data/openpartiesandclaims`); the spawn claim and its no-PvP setting
(`world/serverconfig/openpartiesandclaims-server-claim-config.toml`); Ledger's history (`world/ledger.sqlite`);
Strength levels (`world/data/strength_smp`, `strength_restrictions`); the scoreboard (`world/data/minecraft/
scoreboard.dat`: the wardrobe, store and staff grants, challenges, standings, event points); the spawn NPCs and
the standings board; gamerules, the border and the launch-hour timer; Loot Restock's chest list
(`world/chest_reset_data.json`). The carry in step 5 brings the wardrobe scores (tiers and grants included) and
the supporter, title and champion teams over; claims, parties and Strength start again, as they would at launch.
`keep_inventory` was on in the old world (the corpse mod 2.8.0 drops turned it on); the new world starts with it
off, so deaths drop items. If the owners ever keep the old world instead, run `gamerule keep_inventory false`
there.

As `monkey` (`sudo -iu monkey`), in `/srv/monkey/MonkeySMP-Server/docker` (`monkey rcon` is short for
`docker compose exec monkey monkey rcon`), and the two `systemctl` lines on your admin account:

1. Let 2.8.0 deploy as usual. The deploy backs the world up first, so the newest folder in `../backups/` from
   before the update is the old world as 2.7.0 left it. Keep it out of the rotation:
   `mkdir -p /srv/monkey/seasons/pre-season && cp -a ../backups/<that folder> /srv/monkey/seasons/pre-season/backup-2.7`.
   The off-site backups copy `server/` only (not `backups/` or `/srv/monkey/seasons`), so keep a copy of
   `/srv/monkey/seasons` off the VPS by hand.
2. Pause deploys: `sudo systemctl stop monkey-deploy.timer`.
3. Warn and stop: `monkey rcon "say The server restarts in 1 minute for the new world."`, wait a minute,
   `docker compose stop`.
4. Move the old world aside (keep it): `mv ../server/world /srv/monkey/seasons/pre-season/world`. Then put
   2.8.0's short rules in place (they quote rules 44 to 46, and the server keeps its own copy, so an update
   doesn't replace it): `cp ../monkey/defaults/codeofconduct/en_us.txt ../server/codeofconduct/en_us.txt`.
   Everyone accepts them on their first join.
5. Carry the wardrobe over, before the first start:

   ```sh
   python3 /srv/monkey/repo/tools/season.py carry /srv/monkey/seasons/pre-season/world \
       --into /srv/monkey/MonkeySMP-Server/server/world --season 1
   ```

   `--season 1`: it's still Season I, so everyone who plays stays a founder and Founder's Circlet still opens
   at launch.
6. Keep the seed: `level-seed` in `../server/server.properties` stays, so the land is the same, now with the
   new structures. A new seed is the owners' call; it stays as secret as the old one (docs/ADMIN.md, "World
   generation").
7. Start: `docker compose up -d`. The installer adds the data packs, the rules pack sets the starting border
   (5000 wide, 625 in the Nether) and keeps the End closed, and the console says "Carried N players' wardrobe
   scores and K teams into season 1."
8. Check:

   ```sh
   monkey rcon "scoreboard players get #carried rw.day"     # 1
   monkey rcon "scoreboard players get #season rw.day"      # 1
   monkey rcon "scoreboard players get NAME rw.tier"        # a supporter: the same as in the old world
   monkey rcon "gamerule keep_inventory"                    # false
   monkey rcon "worldborder get"                            # 5000
   grep -o 'nova_structures:' ../server/config/enchantmentdisabler/config.toml | wc -l   # 17 (rule B18)
   grep -E '^(reset_time_value|reset_time_unit|only_reset_when_empty)=' ../server/lootrestock.properties   # 7, days, true
   ```

   The last two are the new 2.8.0 configs, copied because the live server didn't have them (docs/ADMIN.md,
   "Mod settings").
9. The no-PvP spawn claim, as in docs/RULES.md (rule 26):
   `monkey rcon "opac server-claims-config set claims.protection.exceptions.playersByPlayers false"`, then
   `monkey rcon "oclaims server claim in minecraft:overworld ~-48 ~-48 ~48 ~48"`.
10. Pre-generate as on the first setup (step 6 above): `monkey rcon "chunky worldborder"`,
    `monkey rcon "chunky radius 3200"`, `monkey rcon "chunky start"`; the Nether with
    `monkey rcon "chunky world minecraft:the_nether"`, `"chunky worldborder"`, `"chunky radius 500"`,
    `"chunky start"`. The End has no border, so give it a centre:
    `monkey rcon "chunky world minecraft:the_end"`, `"chunky center 0 0"`, `"chunky radius 2000"`,
    `"chunky start"` (on a test server, End cities and Qrafty's villages were 400 to 2000 blocks out).
    `monkey rcon "chunky progress"` shows how far it is.
11. Clear the old world off the live map: `monkey rcon "bluemap purge world"`, and the same for
    `world_the_nether` and `world_the_end` (if one says "BlueMap is still loading", run it again a few
    seconds later). The map's border masks are config, not world: they still fit Season I's start.
12. In game, as an op at spawn: `/function monkey:npcs/guide/here` and `/function monkey:npcs/crier/here` where
    each should stand, and `/function monkey:standings/place` for the board (docs/ADMIN.md, "Spawn NPCs" and
    "Weekly standings and bounties").
13. Turn deploys back on: `sudo systemctl start monkey-deploy.timer` (unless the launch freeze has started:
    docs/LAUNCH.md).

The week, day, drops and standings timers need nothing: they find the world by its path and talk over RCON,
so a run during the switch just fails and the next one works. Within the hour `monkey-week.timer` tells the new
world the challenge week. The launch itself is unchanged: `function monkey:rules/launch` at 5 PM on the day.
The old world stays in `/srv/monkey/seasons/pre-season/`: to go back to it, stop the server, move the new
`world` aside and move the old one back (`backup-2.7` is the same world before 2.8.0 touched it).

### The weekly challenges' timer (the release with the weekly challenges)

Once that release is live, install `monkey-week.timer` from the deployed checkout. It is safe to run again
(it copies only units that changed), and `--check` says what it would send and changes nothing:

```sh
sh /srv/monkey/repo/deploy/monkey-week.sh --check
sudo sh /srv/monkey/repo/deploy/monkey-week.sh --install
```

Do it before the launch (Saturday 7 November 2026, 5 PM Pacific): without the timer the challenge week never
turns over, and the launch weekend's window ends on game time alone, which stops while the server is empty.
It needs python3 3.10 or newer (`deploy/upgrade-2.5.0.sh` installs it) and reads only `REPO_DIR` and
`LIVE_DIR` from `/etc/monkey-deploy.env`.

### The supply drops' timer (the release with supply drops)

Once that release is live, install `monkey-drops.timer` the same way (`docs/ADMIN.md`, "Supply drops"):

```sh
sh /srv/monkey/repo/deploy/monkey-drops.sh --check
sudo sh /srv/monkey/repo/deploy/monkey-drops.sh --install
```

It runs every 10 minutes as `monkey`, sends nothing outside Monday to Thursday, 6 to 10 PM Pacific, and
reads only `REPO_DIR` and `LIVE_DIR` from `/etc/monkey-deploy.env`, plus the saved claims and border from
the world. Without it there are no automatic drops; staff can still start one by hand.

### The outposts' timer (the release with outposts)

Once that release is live, install `monkey-outposts.timer` the same way (`docs/ADMIN.md`, "Outposts"):

```sh
sh /srv/monkey/repo/deploy/monkey-outposts.sh --check
sudo sh /srv/monkey/repo/deploy/monkey-outposts.sh --install
```

It runs every hour at 45 past as `monkey`, sends nothing before the launch or when every outpost has its
spot, and reads only `REPO_DIR` and `LIVE_DIR` from `/etc/monkey-deploy.env`, plus the saved claims, border,
scores and storage from the world. It also writes the "Outposts" marker set into the Overworld map's config
under `server/config/bluemap/maps/` and sends `bluemap reload` when that changed. Without the timer there
are no outposts: the pack waits for spots.

### The border timer (Season II)

Install `monkey-border.timer` once Season II has launched (docs/SEASONS.md, "Season II checklist"; it can
go in sooner: it sends nothing before the launch or for a season it has no acts for, and Season I has none,
since staff grow Season I's border by hand):

```sh
sh /srv/monkey/repo/deploy/monkey-border.sh --check
sudo sh /srv/monkey/repo/deploy/monkey-border.sh --install
```

It runs every hour at 1 past as `monkey`. On an act's date (6 PM Pacific) it grows the Overworld's and the
Nether's (1:8) borders over 10 minutes with a line in chat, once, and never shrinks one; an hour later it fits
the live map's masks with `tools/map_border.py` and sends `bluemap reload`; the hour after, `bluemap purge` for
each changed map. `python3 tools/border.py plan --season 2` prints the dates. It reads `REPO_DIR` and
`LIVE_DIR` from `/etc/monkey-deploy.env`, the saved borders and scores, and writes only the map configs and
`server/config/bluemap/monkey-map-purge.txt`.

### The omens' timer (the release with omens)

Once that release is live, install `monkey-omens.timer` the same way (`docs/ADMIN.md`, "Omens"):

```sh
sh /srv/monkey/repo/deploy/monkey-omens.sh --check
sudo sh /srv/monkey/repo/deploy/monkey-omens.sh --install
```

It runs every 10 minutes (5 minutes after the drops' timer) as `monkey`, sends nothing outside an omen
evening (two weekday evenings a week, from a start between 6:00 and 8:50 PM until 10 PM Pacific), and reads
only `REPO_DIR` and `LIVE_DIR` from `/etc/monkey-deploy.env`, plus the saved scoreboard, claims and border
from the world. `--check` doesn't show the week's plan. Without the timer there are no automatic omens;
staff can still start one by hand.

### The website's status (the release with `tools/status.py`)

The front page and the guide show whether the server is online, how many are playing (a count, never names),
the next event and the border. They read `https://map.monkeysmp.lscaturchio.xyz/status.json`
(`site/config.json`'s `STATUS_URL`), which `monkey-status.timer` writes every 2 minutes and Caddy serves next to
the map on 443, so no port opens. Until it is set up, the site shows a quiet fallback ("Pre-season" before the
launch, "Status not available" after it). Once the release is live:

1. Caddy: `sudo cp /srv/monkey/repo/deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy`. The
   new part is the `handle /status.json` block: it serves `/srv/monkey/status/status.json` with
   `Access-Control-Allow-Origin: *` (the file is public and fetched without cookies, so the website, its
   previews and a local `bun dev` can all read it) and `Cache-Control: public, max-age=60`. Caddy runs as
   `caddy`, so others must be able to enter `/srv/monkey` (`chmod o+x /srv/monkey`; the default `mkdir` mode allows it).
2. The timer, which also makes `/srv/monkey/status`:

```sh
sudo sh /srv/monkey/repo/deploy/monkey-status.sh --install
sh /srv/monkey/repo/deploy/monkey-status.sh --check
curl -sI https://map.monkeysmp.lscaturchio.xyz/status.json   # 200, with access-control-allow-origin
```

It runs as `monkey`, reads `REPO_DIR`, `LIVE_DIR` and `STATUS_DIR` (default `/srv/monkey/status`) from
`/etc/monkey-deploy.env`, the saved Overworld border, and `list` over RCON for the count (the container's own
`monkey rcon`; the names in `list`'s answer are never written). It takes no deploy lock: during a deploy or the
daily restart the file says offline, which is true. Before the launch it writes no player count (only staff
are on). `python3 /srv/monkey/repo/tools/status.py schedule` prints the dates it counts down to; they come from
`tools/season_calendar.py` and the event names from `tools/status.py`'s `SCHEDULE` (a copy of the Season I table
in docs/SEASONS.md, kept in step by a test). A new season needs its rows there.

### The website's standings (3.2.0)

The site's standings page reads `https://map.monkeysmp.lscaturchio.xyz/standings.json`. The hourly and the Sunday
standings runs write it (below, "The weekly standings"), from what they already read from the saved world: no new
timer, no RCON, nothing in game. They write `STATUS_DIR/standings.json`, next to `status.json`, as a temporary file
renamed over the old one with mode 644: the timers run as `monkey`, Caddy reads as `caddy`.

**The file is public, so it holds faction names, ranks and points only:** never a member, a player's name, a
coordinate, a kill count or a claim (`public_rows` in `tools/standings.py` is the allow-list, and a test feeds it a
full world). Many players are under 18 and faction names get no review, so:

- Formatting codes, control characters and invisible characters are stripped, piles of combining marks are thinned,
  and a name is cut at 32 characters. A name left with no letter or digit (blank, or only symbols or emoji) shows as
  `null`.
- A name that is a player's (the "NAME's faction" of a party with no name, or a faction called exactly what a player
  is called) shows as `null`, and the page says "A faction". This needs `server/usercache.json`: with it missing or
  empty nothing is written.
- `/srv/monkey/standings/hidden-names.txt` (`STANDINGS_DIR`, not the public folder) hides a name, which also shows as
  `null`. See below for how staff use it.
- Nothing is written before the launch (`#launched rw.day`), so test play never shows, and a week closed before the
  launch is never `last_week`. A world made later keeps the old file until its own launch; `rm` it to take it down.

A write that fails (a bad folder, bad permissions, a `hidden-names.txt` that can't be read, no `usercache.json`) is logged
in `journalctl -u monkey-standings-board -u monkey-standings`, and the last good file stays up. The board and the close
still do everything else, then the run ends in failure so it shows in `systemctl --failed`. The board tries again next
hour; the close retries every 10 minutes, and its retries post and close nothing twice. `checked` in the file says how
old it is, and `week_closes` is `null` after the season's last close. The file updates at 20 past each hour, and skips the
hour a deploy, restart or backup holds the deploy lock.

Ranks are the board's: ties on points go to more Cup points, then more kills, and only a tie on all three shares a
rank. So two factions can show the same points on different ranks.

Once 3.2.0 is live, one step by hand, as the owner:

```sh
sudo cp /srv/monkey/repo/deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy
```

The timers need nothing: the service files don't change, and the deploy brings the new script. To check it, after the
launch (the first file comes at 20 past the hour, or start it now):

```sh
sudo systemctl start monkey-standings-board
stat -c '%a %U %n' /srv/monkey/status/standings.json   # 644 monkey
python3 -m json.tool /srv/monkey/status/standings.json
curl -sI https://map.monkeysmp.lscaturchio.xyz/standings.json   # 200, with access-control-allow-origin
```

To hide a name, staff with a shell on the VPS add it to the list, one name per line (the leading newline keeps it off the
end of a last line with none). `checked` moving on confirms the file was rewritten; if it hasn't, the start above failed
and the journal says why:

```sh
printf '\n%s\n' 'The bad name' | sudo -u monkey tee -a /srv/monkey/standings/hidden-names.txt
sudo systemctl start monkey-standings-board   # or wait for 20 past the hour
grep -o '"checked":"[^"]*"' /srv/monkey/status/standings.json; date -u +%FT%TZ
```

A line starting with `#` is a comment. A comment can't follow a name on its line, since `#` can be part of a name; a name
that starts with `#` goes in without it, as only letters and digits count.

It is compared on letters and digits alone, without regard to case, accents, colours, spacing or symbols, so colour
codes can't dodge it, and staff can paste the name from the page or the game. It works on the whole name, not on words
in it. It applies when the file is written, so hiding a name fixes last week's table too, and deleting the line brings
the name back. The game, the board and the Discord post are untouched: a name bad enough to hide is also a matter for
staff in game. The file should be UTF-8 (a bad byte spoils only its own line, and the journal says so) and must be
readable by `monkey`: if it can't be read, nothing is written until it can, so a hidden name never comes back by accident.

### The sieges timer (the release with outpost sieges and 7-day wars)

Once that release is live, install `monkey-sieges.timer` (`docs/SEASONS.md`, "Outpost sieges" and "7-day
wars"):

```sh
sh /srv/monkey/repo/deploy/monkey-sieges.sh --check
sudo sh /srv/monkey/repo/deploy/monkey-sieges.sh --install
```

It runs every 5 minutes (40 seconds past 2, 7, 12... minutes) as `monkey` and sends one command, the time
and the next siege window, whether or not windows are on: the game has no calendar, and 7-day wars and the
windows count from it. It reads only `REPO_DIR` and `LIVE_DIR` from `/etc/monkey-deploy.env` and no world
files. `--check` lists the coming windows. It changes nothing in game by itself: outpost sieges and 7-day wars
stay off until staff turn them on (`docs/ADMIN.md`, "Outpost sieges").

### The news timer (the release with Monkey SMP news)

Monkey SMP news posts one plain line to the public channel for a rare first, the first finish of a rare
challenge or a new faction (`docs/ADMIN.md`, "Monkey SMP news"). Once that release is live:

1. In Discord, open the channel (#monkey-smp) > Edit Channel > Integrations > Webhooks > New Webhook, name it
   Monkey SMP, and Copy Webhook URL. It may be the standings' webhook if that already posts there.
2. Put it in the settings file, which stays root:monkey, mode 640 (`sudo nano /etc/monkey-deploy.env`):
   `NEWS_WEBHOOK_URL=https://discord.com/api/webhooks/...`. Nowhere else: never in git, a ticket or chat.
3. Install the timer and look at what it would post:

```sh
sudo sh /srv/monkey/repo/deploy/monkey-news.sh --install
sh /srv/monkey/repo/deploy/monkey-news.sh --check
```

It runs every 10 minutes (2 minutes past, clear of the drops and omens) as `monkey`, reads `REPO_DIR`,
`LIVE_DIR`, `LOCK_FILE`, `NEWS_DIR` (default `/srv/monkey/news`) and `NEWS_WEBHOOK_URL` from
`/etc/monkey-deploy.env`, and only the saved world (no RCON). `--check` says whether the webhook is set, never
its value. Install it, webhook set, before the launch, so launch night posts: nothing posts before
`monkey:rules/launch`, and the runs before it are what date the launch (no calendar date is used). A season
whose first launched run had no run in the 3 hours before it (the webhook added mid-season), or a gap of more
than 3 hours between runs (the webhook emptied for a while, the VPS down), keeps what turned up meanwhile as
baseline and posts only what is new after it. To stop it, empty `NEWS_WEBHOOK_URL` (or
`sudo systemctl disable --now monkey-news.timer`). A new season needs nothing as long as the webhook stays set
across it: a new world is a new `season-<n>.json` in `NEWS_DIR`, so every first is news again.

### The day timer as a job (the release with `deploy/monkey-day.sh`)

The week, drops, omens and day timers are timed jobs (GLOSSARY.md): one runner in `deploy/lib.sh` takes the deploy
lock and reads each answer for a refusal. Before this release `monkey-day.service` ran `docker compose ... rcon`
itself, without either. It now sends `function monkey:wardrobe/day_once {stamp:YYYYMMDD}`, the UTC date, and the
wardrobe pack starts one day per date, so a retry after a run that reached the server never counts a second day.
Once the release is live (its wardrobe pack has `day_once`), replace the unit from the deployed checkout (it
copies only the units that changed, and restarting the timer doesn't start a new day):

```sh
sh /srv/monkey/repo/deploy/monkey-day.sh --check
sudo sh /srv/monkey/repo/deploy/monkey-day.sh --install
```

Until then the old unit keeps working: it runs `function monkey:wardrobe/day`, which the release keeps (staff can
run it for an extra day). Like the old one, the new one tries again every 10 minutes while the server is down; it
now also does when the server turns the command down. A data pack staff turned off (the wardrobe pack) isn't a
failure: the job logs that and sends nothing (`JOB_PACKS`, the next release). It gives up after 6 hours
of tries: it posts to the staff channel and stops, and the next midnight's run starts afresh. `journalctl -u
monkey-day` shows each try; to start the given-up day later, run `sh /srv/monkey/repo/deploy/monkey-day.sh` as
`monkey` (by hand it has no limit, and a date already started is left alone).

### The spawn NPCs (the release with spawn NPCs)

The release adds the `monkey-npcs` data pack but places no one. Once it is live, an op places the Guide and
the Town Crier at spawn once, in game: `/function monkey:npcs/guide/here` and `/function monkey:npcs/crier/here`
where each should stand (docs/ADMIN.md, "Spawn NPCs"). Until then there are no NPCs at spawn. Place them again
after a release that changes their text.

### NPCs in claims (2.9.1)

Spawn is a server claim, so up to 2.9.0 Open Parties and Claims answered a player's right-click on the Guide or
the Town Crier with "You are not allowed to interact with this entity in this chunk (easy_npc:humanoid)"; only
ops could talk to them. 2.9.1 ships `"hand$easy_npc:humanoid"` and `"hand$easy_npc:humanoid_slim"` in
`forcedEntityProtectionExceptionList` in
`defaults/config/openpartiesandclaims-server.toml`: anyone may right-click an Easy NPC with an empty hand in any
claim (docs/ADMIN.md, "Spawn NPCs"). A deploy doesn't touch the live `config/openpartiesandclaims-server.toml`,
whose list still reads `["minecraft:minecart"]`. `deploy/npc-claims.sh` adds the entries with one restart and
skips them when they're already there (only those exact entries count). Run it as root, `--check` first:

```sh
sudo sh /srv/monkey/repo/deploy/npc-claims.sh --check
sudo systemd-run --unit=monkey-npcs --collect -p TimeoutStopSec=20min sh /srv/monkey/repo/deploy/npc-claims.sh
journalctl -fu monkey-npcs
```

It works like `deploy/shops-claims.sh` ("Shops in claims"): it warns players online (`--now` skips that), takes
the deploy lock, stops the server for about 3 minutes (the mod reads the list only on start), keeps the old file
as `openpartiesandclaims-server.toml.before-npcs` and starts the server again whatever happens; its log is
`/var/log/monkey-npc-claims.log`. It prints only the `forcedEntityProtectionExceptionList` line. If that list is
missing or spread over several lines, it changes nothing and says so: add the entries it names to it by hand
with the server stopped. Nothing to do in game: the NPCs stay where they are.

### The short rules, ServerCore and claims (the release after 2.4.2)

The release brings the short rules (`server/codeofconduct/en_us.txt`, a new file), but the live server keeps its
own copies of three files, so four settings in them stay off: the Code of Conduct (`server.properties`), ServerCore's
breeding cap and villager lobotomization (`config/servercore/config.yml`) and Open Parties and Claims' 4 chunks per
player (`config/openpartiesandclaims-server.toml`). Spawn's no-PvP claim belongs to the world, so it's made from the
console. Do this after the release is live: `ls /srv/monkey/MonkeySMP-Server/server/codeofconduct/en_us.txt` must
list the file. Then, as `monkey` (`sudo -iu monkey`):

```sh
cd /srv/monkey/MonkeySMP-Server/docker
exec 9>/tmp/monkey-deploy.lock && flock 9    # the deploy lock, as above
S=/srv/monkey/MonkeySMP-Server/server
P=$S/server.properties C=$S/config/servercore/config.yml O=$S/config/openpartiesandclaims-server.toml
docker compose exec -T monkey monkey rcon "say The server restarts in 1 minute for a settings update." && sleep 60
docker compose stop monkey
for f in "$P" "$C" "$O"; do [ -e "$f.pre-onboarding" ] || cp -p "$f" "$f.pre-onboarding"; done   # once
grep -q '^enable-code-of-conduct=' "$P" || echo 'enable-code-of-conduct=true' >> "$P"
sed -i 's/^enable-code-of-conduct=.*/enable-code-of-conduct=true/' "$P"
awk '$1 == "lobotomize-villagers:" || $1 == "breeding-cap:" { f = 1; print; next }
     f && $1 == "enabled:" { sub(/enabled:.*/, "enabled: true"); f = 0 } { print }' "$C" > "$C.new"
cat "$C.new" > "$C" && rm "$C.new"
sed -i 's/^\([[:space:]]*maxPlayerClaims[[:space:]]*=\).*/\1 4/' "$O"
grep -h -E '^enable-code-of-conduct=|^[[:space:]]*maxPlayerClaims[[:space:]]*=' "$P" "$O"
grep -A2 -E '^[[:space:]]*(lobotomize-villagers|breeding-cap):' "$C" | grep 'enabled:'
docker compose start monkey
until docker compose exec -T monkey monkey rcon list >/dev/null 2>&1; do sleep 10; done
docker compose exec -T monkey monkey rcon "opac server-claims-config set claims.protection.exceptions.playersByPlayers false"
docker compose exec -T monkey monkey rcon "oclaims server claim in minecraft:overworld ~-48 ~-48 ~48 ~48"
exec 9>&-                                    # let deploys and backups run again
```

The first `grep` must print `enable-code-of-conduct=true` and `maxPlayerClaims = 4`, the second `enabled: true`
twice. The two `rcon` lines turn off PvP in server claims and claim the 7 x 7 chunks around spawn (the console's
`~ ~` is the world spawn). The claim runs in the background for a few seconds, and it skips chunks a player
already claimed (those stay out of the no-PvP zone). Everything here is safe to run again; each run restarts
the server once. To undo the file changes, copy the `.pre-onboarding` files back with the server stopped.

## Shops in claims (shelved)

**Not a step for now.** The owners shelved shops on 26 October 2026, so no release ships Universal Shops and there
is nothing to run: skip `deploy/shops-claims.sh` when upgrading (it refuses to run without the mod's jar anyway).
This stays for when shops come back ("Shelved mods" in docs/MAINTAINING.md).

Universal Shops arrives with the release like any mod, but buying from a shop in someone else's claim needs one
more entry in the live `config/openpartiesandclaims-server.toml`, which a deploy doesn't touch:
`"hand$universal_shops:trade_block"` in `forcedBlockProtectionExceptionList` (rule 43; "Shops" in
docs/ADMIN.md). Until it's there, shops work for their owner's party and in the wild, and other players get
Open Parties and Claims' "can't interact" message in a claim. `deploy/shops-claims.sh` adds it with one restart
and skips it when it's already there. Run it as root once that release is live, `--check` first:

```sh
sudo sh /srv/monkey/repo/deploy/shops-claims.sh --check
sudo systemd-run --unit=monkey-shops --collect -p TimeoutStopSec=20min sh /srv/monkey/repo/deploy/shops-claims.sh
journalctl -fu monkey-shops
```

Like `upgrade-2.5.0.sh` it warns players online (`--now` skips that), takes the deploy lock, stops the server for
about 3 minutes, keeps the old file as `openpartiesandclaims-server.toml.before-shops`, and starts the server
again whatever happens; its log is `/var/log/monkey-shops-claims.log`. It prints only the
`forcedBlockProtectionExceptionList` line. If that list is missing or spread over several lines, it changes
nothing and says so: add the entry by hand with the server stopped, as in the section above.

## Backups off the machine

`backups/` is on the same disk as the world, so a dead disk or a lost VPS takes both. So every hour the VPS
also sends the live server folder, encrypted, to a Cloudflare R2 bucket with [restic](https://restic.net).
`monkey-backup.timer` runs `deploy/monkey-backup.sh` on the hour:

1. It waits for a running deploy, and keeps deploys out until it is done with the world (a deploy check
   that comes meanwhile logs "another deploy is running" and goes ahead 5 minutes later).
2. If the server answers: `save-off` and `save-all flush`, so the world on disk is whole and stays still
   while restic reads it. Players keep playing; the server just doesn't save until step 4.
3. restic backs up `server/` itself, not `backups/` (which is only as new as the last deploy). It leaves out
   what the installer downloads again or the server rebuilds: jars, logs, libraries, BlueMap tiles and
   `session.lock`. Only what changed since the last hour is sent, usually within a minute or two.
4. `save-on`, also when restic fails. A restic run that takes over 45 minutes is stopped, and if the backup
   itself is killed, the unit turns saving back on after it.
5. R2 keeps the last 48 hours, then one snapshot a day for 14 days, one a week for 8 weeks and one a month
   for 6 months (`KEEP_*` in the settings). Data no snapshot needs is pruned once a day.
6. `restic check --read-data-subset=5%` reads back a random 5% of the stored data and checks it, so damage in
   the bucket shows up within days instead of at restore time.

When backups fail it posts to the staff webhook in `/etc/monkey-deploy.env` (`STAFF_WEBHOOK_URL`, else
`DISCORD_WEBHOOK_URL`), once, and again when they work.

**When the server doesn't answer.** The backup asks the server (`list`) up to 4 times, 30 seconds apart. If it
still gets no answer, it backs up anyway instead of skipping the hour:

- The container is stopped: the files on disk are whole (a stopped server saved as it stopped). The snapshot is
  tagged `stopped`.
- The container runs but doesn't answer (a hang, a long start): the files may be up to 5 minutes old (the
  server's own autosave) and a file may be caught mid-write. The snapshot is tagged `unflushed` and the log says
  WARNING.

The trade-off: an `unflushed` snapshot may be imperfect, but an hour with no copy at all is worse. The tags keep
the cost small. Pruning keeps tagged and untagged snapshots apart (`--group-by host,paths,tags`), so an
`unflushed` one never pushes a whole one out of the 48 hours, days, weeks or months. The restore drill skips
`unflushed` ones; when you restore by hand, `--restic snapshots` shows the tags, so pick the newest without
`unflushed` unless that one is much older. On the third silent hour in a row the backup tells staff once. Before
this change such hours were skipped, and only a 3-hour silence posted.

**The dead-man's ping.** After each good backup it calls `PING_URL` from `/etc/monkey-backup.env`, if set (an
https check URL, for example healthchecks.io with a 1-hour period and 2 hours' grace). When the pings stop, for
any reason (the VPS is down, the timer stopped, backups fail), that service emails you. Empty means no ping and
no error. The URL is never printed or logged. A deploy still backs up into `backups/` before it
updates, and keeps the newest 3 there (`KEEP_BACKUPS` in `/etc/monkey-deploy.env`): R2 holds the history.

**Cost.** R2's free tier (October 2026) is 10 GB-month of storage, 1 million writes and 10 million reads a
month, with free downloads and no minimum storage time. restic keeps each piece of data once, so the bucket
holds about one copy of the server folder plus six months of changes: free while that stays under 10 GB,
then $0.015 per GB-month (20 GB is $0.15 a month). The hourly runs, the read-back included, come to tens of
thousands of operations a month, far under the free amounts, and downloads cost nothing.
`--restic stats --mode raw-data` (below) shows what the bucket holds.

### Set up the off-site copy (once)

1. **Bucket and key**, in the Cloudflare dashboard (Cloudflare asks for a card to turn R2 on, even within the
   free tier): R2 > Create bucket, e.g. `monkey-smp-backups`. Its Settings page shows the S3 API address,
   `https://<ACCOUNT_ID>.r2.cloudflarestorage.com/monkey-smp-backups`. Then R2 > Manage API tokens > Create
   API token with **Object Read & Write** on that bucket only, and copy its Access Key ID and Secret Access
   Key (shown once). Make a second token with **Object Read** only for the home PC (the restore drill below).
2. **The restic password.** Make a long random one in your password manager and save it there with the keys
   and the address. **Keep it off the VPS**: it is the only way to read the backups, and a VPS that dies takes
   `/etc/monkey-backup.env` with it, leaving the bucket unreadable. Lost R2 keys can be made again; a lost
   password can't.
3. **restic and the settings**, on the VPS as root. restic 0.19.1 from its release (Debian 12's package is
   0.14, too old for the restore commands below; `apt install bzip2` if `bunzip2` is missing):
   ```sh
   curl -fsSLO https://github.com/restic/restic/releases/download/v0.19.1/restic_0.19.1_linux_amd64.bz2
   echo 'f415415624dcc452f2a02b8c33641791a8c6d6d3b65bbb3543fcf9a25151585c  restic_0.19.1_linux_amd64.bz2' | sha256sum -c
   bunzip2 restic_0.19.1_linux_amd64.bz2 && install -m 755 restic_0.19.1_linux_amd64 /usr/local/bin/restic
   install -m 600 -o root -g root /srv/monkey/repo/deploy/monkey-backup.env.example /etc/monkey-backup.env
   nano /etc/monkey-backup.env
   ```
   Type the address (as `s3:https://...`), the two keys and the password into the file. It stays root-only:
   never copy the values into the repo or a chat.
4. **The unit, the first backup and the timer:**
   ```sh
   cp /srv/monkey/repo/deploy/monkey-backup.{service,timer} /etc/systemd/system/ && systemctl daemon-reload
   sh /opt/monkey/deploy/monkey-backup.sh --init
   systemctl start monkey-backup
   systemctl enable --now monkey-backup.timer
   ```
   `--init` creates the repository in the bucket. The first backup sends the whole server folder, so the
   server doesn't save until it is done (players can keep playing); later ones send only the changes.
   Root runs the backup from its own copy in `/opt/monkey`, not from `/srv/monkey/repo` ("Root's own copies"
   above): install those first.
5. **The restore drill.** Run it by hand once ("The restore drill on the VPS", below); when it passes, turn on
   its monthly timer. Do the home PC drill a few times a year too.

The VPS's token can delete (pruning needs to), so the bucket doesn't guard against someone who takes over the
VPS. For that, now and then copy a drill's restored `server` folder (below) to a disk at home before
deleting it.

### Restore

Every snapshot holds the server folder at its path on the VPS, `/srv/monkey/MonkeySMP-Server/server`.
Restoring `latest:/srv/monkey/MonkeySMP-Server/server` gives the newest one; `--restic snapshots` lists the
others by ID and time, and `<ID>:/srv/monkey/MonkeySMP-Server/server` restores one of them. On the VPS the
script reads the keys from the settings file, so none go on the command line.

**On the VPS** (the world broke, or a mistake needs undoing), as root:

```sh
sh /opt/monkey/deploy/monkey-backup.sh --restic restore latest:/srv/monkey/MonkeySMP-Server/server --target /srv/monkey/restore
cd /srv/monkey/MonkeySMP-Server/docker && docker compose stop
mv ../server/world ../server/world.before-restore && mv /srv/monkey/restore/world ../server/world
chown -R monkey: ../server/world && docker compose up -d
```

Only the world goes back. The whitelist, bans, LuckPerms and the mods stay as they are, so nobody who paid
since then loses access. The last 3 deploys' backups are also in `backups/`, with no download: move
`../backups/<time>/world` in instead. Delete `world.before-restore` and `/srv/monkey/restore` once the server
is fine.

**On a new VPS**: set it up as in "Set up (once)" above. In step 5, before running the deploy script the
second time, do steps 2 and 3 of the off-site setup with the values from your password manager, then
`sh /opt/monkey/deploy/monkey-backup.sh --restic restore latest:/srv/monkey/MonkeySMP-Server/server --target /srv/monkey/MonkeySMP-Server/server`
and `chown -R monkey: /srv/monkey/MonkeySMP-Server/server`. Then run the deploy script, and finish with step 4
of the off-site setup. The Tebex jar comes with the manifest and its key with the restore (`server/mods/tebex`). The new VPS carries on the same series of snapshots.

### The restore drill on the VPS

`deploy/monkey-restore-drill.sh` (root, its own copy in `/opt/monkey`) proves that the newest backup can be read
and that the world in it loads. It changes nothing that is live:

1. It checks there is room: free disk for a copy of the server folder and a release plus 1 GB, and free memory
   for a 2 GB server plus 1 GB. Not enough: it stops before it does anything, and says so.
2. It restores the newest snapshot that is not tagged `unflushed` into a new folder under `/var/tmp`
   (`monkey-drill.XXXXXX`, root only). It reads R2 only through `monkey-backup.sh --restic-read`, which runs
   only `snapshots`, `ls` and `restore`, with `--no-lock`, and with the read-only token when
   `READ_AWS_ACCESS_KEY_ID` is set. So it writes nothing to the bucket.
3. It checks the restored world: `level.dat` and region files.
4. It copies in the live release's files (read only; the live `docker/.env` is left out) and boots the copy in
   its own container, `monkey-drill-<time>`, with **no network** (`--network none`): no port, no Discord bot, no
   store, no players. It is a separate container, not the live one.
5. It waits up to 15 minutes for the copy to answer, then reads the world's clock. A pass needs the clock at or
   past the one saved in `level.dat`: the world loaded; it didn't start a new one.
6. It stops and removes the container, deletes the folder, and posts PASSED or FAILED with the snapshot's time
   to the staff webhook.

Run it by hand the first time, as root (about 10 to 25 minutes; my guess, not timed on the VPS):

```sh
systemctl start monkey-restore-drill && journalctl -u monkey-restore-drill -n 40
```

A pass ends with `PASSED: snapshot <id> from <time>`. When it passed once, turn on the monthly run (the first
Monday of the month, 11 AM Pacific): `systemctl enable --now monkey-restore-drill.timer`. A drill keeps
nothing; run it by hand with `DRILL_KEEP=1 sh /opt/monkey/deploy/monkey-restore-drill.sh` to keep the folder to
look at (then delete it).

It needs the Docker image the live server built (`monkey-smp-monkey`). If the copy can't boot without the
network (a download the install wants), the drill fails and says so; that is worth knowing too.

### Restore drill on the home PC

A few times a year, restore the newest snapshot onto the home PC and start it there. It proves the backups can be
read and the world loads, and it rehearses the playit.gg fallback below, which starts the same way.

1. **Make room.** Stop any other Minecraft server on the PC first, test servers included: two servers fight
   over BlueMap's port 8100, and the one that loses shuts down. Check that about 12 GB of memory is free.
2. **The release.** Download the zip of the release that is live (`monkey-deploy.sh --status` on the VPS)
   from the repo's GitHub releases, and unzip it into a new, empty folder, e.g. `C:\MonkeySMP-drill`.
3. **restic** (once): get `restic_0.19.1_windows_amd64.zip` from https://github.com/restic/restic/releases
   and unzip `restic.exe` to `C:\Tools\restic`.
4. **Restore**, in PowerShell in the release folder, with the read-only token (the secret is typed hidden
   and stays out of the history; restic then asks for the password itself):
   ```powershell
   $env:RESTIC_REPOSITORY = 's3:https://<ACCOUNT_ID>.r2.cloudflarestorage.com/monkey-smp-backups'
   $env:AWS_DEFAULT_REGION = 'auto'
   $env:AWS_ACCESS_KEY_ID = '<read-only Access Key ID>'
   $env:AWS_SECRET_ACCESS_KEY = [Net.NetworkCredential]::new('', (Read-Host -AsSecureString 'Secret Access Key')).Password
   C:\Tools\restic\restic.exe --no-lock snapshots --latest 1
   C:\Tools\restic\restic.exe --no-lock restore latest:/srv/monkey/MonkeySMP-Server/server --target server
   ```
   `--no-lock` is needed because a read-only token can't write restic's lock file (without it, restic stops
   with `Access Denied`). Paste the keys with a right-click: Ctrl+V in a hidden prompt can paste one character.
   The newest snapshot should be from the last hour or two.
5. **Take the store's key out, then start it.** Delete `server\mods\tebex` first: it holds Tebex's secret key,
   and with it this copy would carry out store purchases meant for the VPS. Then `Start Server.bat`. Backups leave
   the jars out, so the first start downloads Java, Fabric and the mods (about 300 MB), then loads the restored
   world.
6. **Join it** through playit.gg: start the agent and join its tunnel address (not `monkeysmp.lscaturchio.xyz`:
   DNS stays on the VPS during a drill). Your base should be there as it was at the snapshot's time.
7. **Stop it and delete the folder.** It is a copy: nothing done on it counts. Note the date and what
   failed, if anything; a failed drill is the cheap time to find out.

## Fallback: home PC on playit.gg

When the VPS or its provider is down for longer than a restart:

1. On the home PC, do steps 1 to 5 of the restore drill above, in a folder you keep, but keep
   `server\mods\tebex` this time: here the store should deliver (see "Payments and Discord").
2. Start the playit.gg agent (set up once, as in `READ ME FIRST.txt`). Its tunnel address and port stay
   the same between runs; a premium playit.gg account adds a UDP tunnel for voice chat.
3. In Cloudflare DNS, point the `_minecraft._tcp.monkeysmp` SRV record at the playit address and port,
   and each join address's SRV record (`_minecraft._tcp.yt.monkeysmp` and the rest, docs/PROMOTION.md)
   too. With TTL 60, players reconnect to the same name within minutes.
4. When the VPS is back, stop the home server, copy its `server` folder back to the VPS, swap the SRV
   records back, and start the VPS.

Only one copy may run the world at a time: two live copies split the world into two histories.

## Payments and Discord

- **Tebex** sells the pass and the supporter tiers, collects sales tax as the merchant of record, and runs
  commands on the server after a purchase: `whitelist add {username}` for the pass (`whitelist remove` when
  it ends), and the wardrobe scoreboard and team commands for supporter tiers (the full list, with the
  reverse on expiry, is in docs/RETENTION.md). Both passes renew (monthly, or every 2 months) until the buyer cancels from
  Tebex's payment history page; after 3 failed renewals it expires and the expiry commands run. Since
  3.0.0 Tebex's Fabric mod (2.4.6) is in the manifest like any other mod, so a deploy, a restore or a new VPS
  gets it by itself. Its secret key is not in the repo: it sits in `server/mods/tebex`, outside the world, and
  `tebex secret` in the console sets it.
- **Discord**: optional for buyers. Since 2026-11-06 neither pass has a Discord action (with one, checkout forced
  a Discord login even with "Discord after checkout" on), so Tebex gives no role: staff give **SMP Member** by
  hand. A buyer still gets the whitelist and the pass from the package's command. The forum, announcements, ban
  appeals and the `monkey` bridge live in the Discord server repo (gr8monk3ys/discord-server). The bridge
  talks RCON, which is plain text: reach the VPS over Tailscale or WireGuard, never by publishing 25575.

### The store (set up once, before the first sale)

Status (2026-11-02): the Tebex project "Monkey SMP" is approved, published and connected to the live server, so
the store takes real payments. Delivery (`tebex secret` in the console), all five packages (checked in the panel
against the table below), the support contact, the payout wallet and the storefront are all done. The paid role is
**SMP Member**. Tebex's bot gave it until 2026-11-06; staff give it by hand now (see **Discord** above). If a
Discord action comes back, the bot's role must stay above SMP Member.
The address is `https://monkey-smp-store.tebex.store` (`tebex info` in the console prints it; `monkeysmp.tebex.io`
belongs to another server). The site has linked to it since `STORE_URL` merged on 2026-11-04 (#110).
Make a test purchase, check that the buyer is on the whitelist (the server log shows Tebex's command), and
only after that fill in `STORE_URL` (below). If Tebex's review asked for package changes, check the prices
and terms against the table below before the first real sale.

Tebex can't change the price of a subscription already sold, so set these before the store link goes on
the site (the reasons are in docs/adr/0008-pass-prices-settled-before-the-first-sale.md):

| Package | Price | Charged | Commands (docs/RETENTION.md) |
| --- | --- | --- | --- |
| Server Pass | $5 | monthly subscription | whitelist, `rw.months 1` on renewal |
| Server Pass, 2 months | $8 | subscription, every 2 months (since 2026-11-07) | whitelist, `rw.months 2` on purchase and on renewal, taken back on refund or chargeback |
| Ember, Banner, Crown | $3, $7, $15 | monthly subscription | `rw.tier`, `tier_*` team |

- **No priority or reserved slots, and no coupons for single people.** Mojang's rules ask for one price
  for access; a sale has to be open to everyone.
- **Free trial on the monthly pass: 7 days, off at launch (docs/LAUNCH.md).** Tebex added native trials for subscription packages (1, 3,
  7, 10, 14 or 30 days; Packages > the package > Trials). It takes card details at checkout and charges
  when the trial ends; a trial on the package is the same for every buyer, so it stays within the
  one-price rule. Seven days always includes a Saturday event (docs/SEASONS.md). Tebex's docs don't say
  which commands run when a trial starts or is cancelled, so test once with a real purchase before
  switching it on for everyone: the whitelist command has to run when the trial starts, the removal when
  it is cancelled, and `rw.months` mustn't count the trial's first charge twice. If the whitelist waits for
  the first charge, leave trials off and run open-house evenings instead: the whitelist off for one
  announced evening a month with staff online, listed in docs/SEASONS.md and on the site. Once trials are
  on, add this to the site's FAQ (`faq` in `site/src/content/front.tsx`), under "Refunds?":
  "**Can I try it first?** Yes: the monthly pass starts with 7 free days. Tebex asks for a card and charges
  the first month when the 7 days end, unless you cancel before then on its payment history page."
- **Creator codes** (Creator Codes in the Tebex panel): a 20% revenue share, no customer discount, limited
  to the 2-month pass if Tebex offers that. Tebex pays a code's share only on a subscription's first
  payment, takes 1% more on payments made with a code, and settles the creator's Tebex Wallet after 30
  working days. The public terms are the site's `/creators` page (`terms` in `site/src/content/rules.tsx`);
  finding creators is in docs/PROMOTION.md.
- **The site.** Put the webstore's address in `STORE_URL` in `site/config.json`; the site's next build writes
  it into the pages. Do it only once a test purchase has whitelisted someone: while `STORE_URL` is empty the
  pages say passes are arranged in the Discord and staff whitelist buyers by hand, and setting it switches them
  to the store's wording ("on the whitelist within a minute or two"), the `<Store when="open">` and
  `when="soon"` text in `site/src/app/page.tsx`.

## Monitoring, the daily restart and the update check

| What | Runs on | Does |
|---|---|---|
| Uptime Kuma | the home PC (fleet repo, `services/uptime-kuma.md`) | every minute: a Minecraft status ping to `monkeysmp.lscaturchio.xyz` (through the SRV record, as players connect) and an HTTP check of the live map; alerts in a Discord channel; quiet 4-5 AM Pacific, when deploys and the daily restart happen |
| `monkey-restart.timer` | the VPS | restarts the server at 4:30 AM Pacific and posts a spark health link |
| `monkey-updates.timer` | the VPS | Mondays at 10 AM Pacific: lists newer builds of what the live release pins |
| `monkey-standings.timer` | the VPS | Sundays at 7 PM Pacific: closes the week's faction standings and posts them (below) |
| `monkey-standings-board.timer` | the VPS | every hour at :20: puts this week so far on the in-game board |
| `monkey-news.timer` | the VPS | every 10 minutes: Monkey SMP news to the public channel, a few lines a week ("The news timer") |
| `monkey-staff.timer` | the VPS | every 2 minutes: a reading for the staff page, and the health alerts to the staff channel ("The staff page") |
| `monkey-report.timer` | the VPS | Mondays at 1:15 AM Pacific: last week's rule check for the staff page's Reports tab; it only reports ("The weekly rule check") |

Uptime Kuma runs on the home PC because a monitor on the VPS goes down with the VPS, and the home PC is on all
the time anyway. The update check runs on the VPS rather than the home PC: it uses the webhook that is already
in `/etc/monkey-deploy.env` (no second copy of it), and it checks the release that is actually live.

Install the two timers once the release after 2.4.1 is live (they run from the deployed checkout):

```sh
sudo apt-get install -y python3    # the update check runs tools/check_updates.py (3.10 or newer)
sudo cp /srv/monkey/repo/deploy/monkey-{restart,updates}.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now monkey-restart.timer monkey-updates.timer
```

Both post to `STAFF_WEBHOOK_URL` in `/etc/monkey-deploy.env` when it is set (a staff-only channel), and to
`DISCORD_WEBHOOK_URL` otherwise.

**The daily restart** keeps memory from creeping up over days of uptime (BlueMap and mod
caches). It runs inside the deploy window but after the deploy check: when a release went live that morning,
the server is younger than `RESTART_MIN_UPTIME` hours (6) and the restart skips. It waits up to 30 minutes for
the deploy lock, so it never overlaps a deploy or an off-site backup. It warns anyone online 5 minutes and 1
minute ahead, like a deploy, takes `spark health` just before stopping, and posts "back up (had been up N h)"
with that link. If memory use in those reports keeps climbing from day to day, something leaks and the
restart only hides it. Log: `journalctl -u monkey-restart -n 50`. To restart now as the timer would, as
`monkey`: `RESTART_MIN_UPTIME=0 sh /srv/monkey/repo/deploy/monkey-deploy.sh --restart`.

**The weekly update check** runs `tools/check_updates.py` against the live release, since the GitHub Actions
check can't run in this private repo. It posts every Monday, with the report attached when there is anything
newer, so a Monday without a post means the timer is broken. It changes nothing: taking an update is still
`check_updates.py --apply` on a PC, the smoke test and a release (docs/MAINTAINING.md). Run it now with
`sudo systemctl start monkey-updates`; log: `journalctl -u monkey-updates`.

**The weekly standings** (docs/SEASONS.md, "Weekly standings") run `tools/standings.py` from the deployed
checkout, through `deploy/monkey-standings.sh`, as `monkey`. They read the world's saved files (parties,
claims, scoreboard) and send only the board's text to the game, over RCON through the container. Set them up
once a release with them is live and the server has started on it, as root, `--check` first:

```sh
sudo sh /srv/monkey/repo/deploy/install-standings.sh --check
sudo sh /srv/monkey/repo/deploy/install-standings.sh
```

It skips whatever is already done: python3 (3.11 or newer), a check that the `monkey-standings` data pack is
on, the folder the weeks are kept in (`STANDINGS_DIR`, default `/srv/monkey/standings`), the first week's
snapshot, and the two timers. Two things stay by hand:

- The channel: `STANDINGS_WEBHOOK_URL` in `/etc/monkey-deploy.env`, a public channel such as `#monkey-smp`.
  Empty, the post goes to `DISCORD_WEBHOOK_URL`. The webhook is never printed or logged.
- The board: an op stands at spawn and runs `/function monkey:standings/place` (docs/ADMIN.md).

On Sunday at 7 PM Pacific the timer closes the week: it keeps the final table in
`STANDINGS_DIR/weeks/<date>.json`, starts the next week from a new snapshot, puts both on the board, announces
it in chat and posts it to Discord as the Sunday recap ("Monkey SMP Weekly": the table and a few lines on the
week, worked out at the close and kept in the same file). Before the launch (`function monkey:rules/launch`
sets `#launched rw.day`) it keeps the week but posts nothing. It waits up to 30 minutes for the deploy lock, so it never runs during a
deploy, the daily restart or an off-site backup. If the board or Discord fails, the service fails and systemd
tries again every 10 minutes for 2 hours; a retry finishes what is left and never closes the week twice (a
week closes only when it is at least 3 days old). The hourly board update skips its turn when the lock is
busy. To run the Sunday job now (it still closes only a week at least 3 days old):
`sudo systemctl start monkey-standings`; log: `journalctl -u monkey-standings -n 50`.

Both runs also write the public `standings.json` for the website, after the launch ("The website's standings", above).
A retry of the close writes it again, the same but for `checked`.
**Failure alerts.** Every `monkey-*` service has `OnFailure=monkey-alert@%n.service`. When one fails, systemd
starts `monkey-alert@<unit>.service`, which runs `deploy/monkey-alert.sh` as `monkey`. It posts one line to the
staff webhook: "Monkey SMP: <unit> failed. Check: journalctl -u <unit>". It reuses `STAFF_WEBHOOK_URL` (else
`DISCORD_WEBHOOK_URL`) from `/etc/monkey-deploy.env`; there is no new secret. Repeats: at most one post per unit
in 6 hours. More failures in that time are counted, and the next post says how many. A job that exits 4 has
already told staff itself (a timed job that gave up, a deploy or daily restart that posted "DOWN"), so the alert
posts nothing for it. The backup and the restore drill post their own results and have no `OnFailure=`. Log:
`journalctl -u 'monkey-alert@*' -n 20`. `install-root.sh` installs the alert unit.

**Log pruning.** The privacy page says server logs are kept as long as reports, bans and appeals need them, then
deleted. `monkey-logs.timer` (daily, 4:30 AM UTC) runs `deploy/monkey-logs.sh` as `monkey`. In `server/logs`
only, it deletes the rolled daily logs (`YYYY-MM-DD-N.log.gz`) older than `LOG_KEEP_DAYS` days, by the date in
their name, and `debug-N.log.gz` files not written for that long. It never touches `latest.log`, `debug.log` or
any other folder. `LOG_KEEP_DAYS` is in `/etc/monkey-deploy.env`: default 90, at least 14. The privacy page
names no number of days yet; when it does, set the same number here. Before a report or appeal that needs an
older log, copy that file out of `server/logs`. `sh /srv/monkey/repo/deploy/monkey-logs.sh --check` lists what
the next run deletes. Not covered: the action log (the mod's own database) and Caddy's logs; they follow their
own settings.

## The staff page

`https://staff.monkeysmp.lscaturchio.xyz`, behind a password, for the people who run the server. It opens on one
word for how the server is doing (Healthy, Busy, Slow, Offline, Not answering), with recent problems, tick time,
players and the machine's memory and CPU in use over the last 24 hours, what the problems probably are, who is online, memory, swap, CPU in use (and the load average under it), disk, the release and the last backup. Its
other tabs (Console, Files, Players, Server) are the controls: they let staff run the server without a shell ("The
controls", below). It names players, which the public status never does, so it is not linked from the website: pass the
address on privately. Uptime Kuma still does the alerting; the Status tab only answers "how is it doing right now?".

`monkey-staff.timer` runs `deploy/monkey-staff.sh` as `monkey` every 2 minutes, which writes
`/srv/monkey/staff/staff.json` (`tools/staff_status.py`) from `tick query` and `list` through the container's own
`monkey rcon`, plus `/proc`, the disk, the backup folder and the server's log. It takes no deploy lock: during a
deploy or the daily restart the page says offline, which is true. The file keeps 24 hours of readings. Caddy serves
it, the page (`deploy/staff/`, from the checkout, so a deploy updates it) and the site's fonts, and nothing else.

Recent problems comes from `server/logs/latest.log` and `server/crash-reports/`: errors since the server finished
starting, stalls of 2 seconds or more (`Can't keep up!`) and crashes, each kept for a day after its last line. Warnings
and the errors logged during a start aren't listed. A mod can log an error that does no harm, so a listed error is
worth a look, not a reason to act. Each reading reads only what is new in the log, so it costs next to nothing. Log
text is filtered first: a line that mentions a secret is replaced whole, addresses, links and long numbers are masked,
and only the description of a crash report is read, because the rest can hold the seed. Log lines carry no date, so
what the very first reading finds is marked as from before the page started watching. Lines logged between the last
reading and a restart are missed, since each start replaces the log; a crash still shows, from its report.

**What it probably is** sits above them (`tools/staff_watch.py`): each problem matched to a cause this kind of server
has, in plain words with what to do, marked "Needs a look", "Worth a look" or "Usually harmless". From the log and
the crash reports: the game out of memory, the disk full, the watchdog stopping a frozen game, an entity or block
that crashes every tick, a mod missing a dependency, a mod's mixin failing, the port taken, a damaged chunk, a broken
data pack, dropped connections (harmless). From the numbers: lag past the 50 ms limit for three readings in a row (6
minutes), less than 10% of memory or disk free, over half the swap in use, the off-site backup failing. It is a guess
from words in the log: check before acting on it. A line it doesn't know is left as it is.

**Health alerts.** With `STAFF_WEBHOOK_URL` set in `/etc/monkey-deploy.env`, the same 2-minute job tells the staff
channel (never the public one) what needs a look, as one message a reading:

- a number (lag, memory, disk, the off-site backup) when it first shows, then "(still)" at most once in 6 hours while
  it lasts, and "Cleared" once it has stayed back to normal for 10 minutes. After that it isn't raised again for an
  hour, so a number hovering at its line doesn't post on every reading.
- a cause from the log (out of memory, a missing dependency, the port taken...) once while it is in the day's list,
  never "(still)". Errors that stop the server starting are kept for this; the dozen every start logs are only
  counted, as before.
- each new crash, with its description and likely cause, at most one message in 30 minutes; crashes in between are
  counted in the next ("3 crash reports since the last message").

What it posted is kept in `staff.json` (`alerts`), which is written before anything is posted, so a restart of the job
doesn't post again. If the file can't be written (a full disk), the job can't remember, so it posts only in its first
run of each hour. The first reading after it is set up is quiet about what was there before it watched: older log
lines and crash reports already in the folder. The job reads the webhook from the env file and hands it over in the environment, never
on a command line. Without it nothing is posted, and Uptime Kuma still says when the server is down.

Set it up once, on a quiet day, after a release that has it is live:

1. In Cloudflare, an `A` record `staff.monkeysmp` to the same address as `map.monkeysmp`, "DNS only": Caddy gets the
   certificate itself. Without its own record the name falls to the zone's wildcard and lands on Vercel.
2. A login for each person. The password is random, shown once and kept only as a hash in `/etc/caddy/staff-logins`,
   so put it straight in a password manager and pass it on privately:

```sh
sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --login NAME
```

3. The status job and the site. `--install` refuses without a login, adds one `import` line to the live Caddyfile
   rather than copying the repo's over it, and takes the site back out if a visit with no password gets anything but
   a 401. `--check` repeats that test and changes nothing:

```sh
sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --install
sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --check
curl -sI https://staff.monkeysmp.lscaturchio.xyz | head -1   # 401
```

The first reading comes within 2 minutes; until then the page says "No reading yet". Run `--install` again when a
release changes the units or `deploy/Caddyfile.staff`.

To set it up before a release has it, with no tag, deploy or restart, take its files from `main` before step 2. The
checkout stays on the running tag, the package a deploy copies doesn't change, and the next deploy's forced checkout
replaces them with the release's own copies:

```sh
sudo -u monkey git -C /srv/monkey/repo fetch --quiet origin main
sudo -u monkey git -C /srv/monkey/repo checkout FETCH_HEAD -- deploy/staff deploy/monkey-staff.sh \
    deploy/monkey-staff.service deploy/monkey-staff.timer deploy/monkey-panel.service deploy/Caddyfile.staff \
    deploy/Caddyfile.staff-login deploy/monkey-staff-helper.path deploy/monkey-staff-helper.service \
    deploy/monkey-staff-helper.sh deploy/monkey-sftp.sh tools/staff_status.py tools/staff_panel.py tools/staff_auth.py \
    tools/staff_apex.py tools/staff_host.py tools/staff_more.py tools/staff_modcfg.py tools/staff_events.py \
    tools/staff_desk.py tools/staff_spark.py tools/staff_watch.py tools/staff_lookup.py tools/staff_trends.py
```

If the page is already set up, that and `sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --install` again add the
controls: it copies `monkey-panel.service`, starts it and puts the new `Caddyfile.staff` in place. A deploy updates
`tools/staff_panel.py` in the checkout but not the copy that is running: run `--install` again after a release that
changes it (or `sudo systemctl restart monkey-panel`).

A new person or a new password is `--login NAME` again, and `--remove-login NAME` takes one away; either works at once,
with no restart. To close the page (the `import` line stays and then matches nothing, which Caddy accepts):

```sh
sudo rm /etc/caddy/staff.caddy && sudo systemctl reload caddy
sudo systemctl disable --now monkey-staff.timer monkey-panel
```

### The controls

`monkey-panel.service` runs `tools/staff_panel.py` as `monkey`, listening on `127.0.0.1:8130` only. Caddy sends the
page's `/api/*` calls to it after the password check, with the login's name (`lorenzo`, `diego`) in a header Caddy
sets itself. It changes nothing in how the server runs: the container, compose and the timers stay as they are.

- **Console**: the server log as it is written (the same masking as the Status tab: a line that mentions a secret is
  left out, addresses and links are masked) and a command box. Commands run as the server console, through the
  container's own `monkey rcon`, one line at a time, with a 20-second limit. Above the log: Everything, Chat (what
  players and the server said, and joins and leaves) or Warnings and errors, and a box that keeps only lines with
  some text. Under Chat the box says what you type to everyone (`say`), unless it starts with `/`. Warnings and errors
  are coloured, with their WARN or ERROR still in the line. **Saved commands** (admin): a label and a command, shared
  by every admin, checked as the console checks a typed one, and Run sends it as if typed
  (`/srv/monkey/staff/commands.json`, at most 40).
- **Server**: running, stopped or restarting, and four buttons. Restart is the daily restart
  (`monkey-deploy.sh --restart`): players get the 5-minute warning, and it waits for the deploy lock. It is started
  apart from the controls, its output in `/srv/monkey/staff/power.log`, so it finishes even if the controls restart.
  It runs with `RESTART_MIN_UPTIME=0`, so it doesn't skip a server that started less than 6 hours ago, unless
  `/etc/monkey-deploy.env` sets `RESTART_MIN_UPTIME` itself (the script reads that file last). Chat and the staff
  channel call it the daily restart.
  Restart now (`docker compose restart monkey`, no warning: the deploy script has no restart without one), Stop and
  Start (`docker compose up -d --no-build monkey`) take the deploy lock first; when a deploy, the daily restart, a timed
  job or an off-site backup holds it, the button says so and nothing happens. One power action at a time. Also here:
  the timers' next and last runs, the last backup and every change made on the page, newest first, 100 at a time,
  with a search by login, kind of change and text, and a download of the search as a `.csv` (a cell a spreadsheet
  would run as a formula gets a `'` in front). The search reads the last 8 MB of `actions.log`, and says so when the
  file is longer.
- **Files**: `server/` of the live release: browse, find by name in a folder, edit text files, download, upload,
  delete, make a new file or folder, and rename or move a file within `server/`. **Search all files** (admin): every
  file the page can open whose name has the text, or with "In the text" whose lines do (plain-text settings files
  only, never `logs/` or `crash-reports/`). It searches the text as the editor shows it, secrets masked, so a search
  never finds (or lets anyone guess) a password's value: searching `rcon.password` shows the line, `********`. It stops
  after 20,000 files, 5 seconds or 200 results, and says so. A rename never replaces anything (a
  name already taken is refused) and keeps no copy, since nothing is lost; it follows the same rules as a save, under
  both its old name and its new one, so only an owner renames a jar, anything in `mods/` or `server.properties`.
- **Players**: who is online, the whitelist, ops and bans, with add and remove. They are console commands
  (`whitelist add NAME`, `op`, `ban`, `kick`...), and the controls refuse one whose name isn't a real player name. A
  kick can have a reason, which the player sees.
  **Temporary bans** (admin; moderators see the list): the game's own ban, with a reason that starts "Banned until"
  and the time it ends in UTC, so the player sees when. The page keeps them in `/srv/monkey/staff/tempbans.json` and
  pardons the player at that time (its scheduler looks every 20 seconds), but only if the ban in
  `banned-players.json` is still that one, word for word: a player pardoned by hand, or banned again, is left as staff
  left them. While the server is off it waits, sending nothing, and pardons once it is back. "Lift now" pardons early.
  1 hour to 30 days. A player banned already can't be banned for a time, nor banned for good over a temporary ban:
  the game keeps the ban that is there ("Nothing changed"), so the page says to pardon or lift it first.
  **Everyone who has joined** (moderator): every name in `usercache.json`, the last seen first, with when the server
  last saved them (`world/players/data/UUID.dat`'s time, so a player who is on shows the last few minutes), hours
  played (`minecraft:play_time` in their stats file, nothing else of it) and whether they are an operator,
  whitelisted or banned. Nothing is asked over RCON. **Notes** are for staff only: a line of text per note, signed
  with the login and the time, kept by the player's UUID so they follow a change of name
  (`/srv/monkey/staff/player-notes.json`, mode 600, at most 50 a player). Any moderator adds one; an admin deletes
  one. `actions.log` (and so the staff channel) says who wrote a note about whom, never what it says.

What Diego can do: anything the server console can, but the two below; edit `config/`, `defaultconfigs/`, `mods/`,
`server.properties`, the `.json` lists and the other config files in `server/`; upload a mod; restart, stop and start
the server. What he cannot do, whatever the page sends:

- see or run `seed` (the seed is secret), or `stop` in the console (the container would start again at once: use
  Stop). `execute ... run seed` and `minecraft:stop` are refused too.
- open the worlds (`world*`: listed by name only), `libraries/`, `versions/`, `bluemap/` or any `*.db` file; change
  `logs/` or `crash-reports/` (read-only); reach anything outside `server/` (no `..`, no absolute path, no link that
  leads out: every path is checked again once links are followed).
- see a password or the seed: in any file, the value of a key with password, secret, token or seed in its name
  (`rcon.password` and `level-seed` in `server.properties`, a bot's token in `config/`) shows as `********`, a download
  too. Saving a line that still says `********` keeps the value on disk; typing a new value replaces it. In `logs/` and
  `crash-reports/` every line is masked as the console's are (a crash report can hold the seed and addresses), and one
  over 2 MB can't be downloaded here.
- delete a folder, or save over someone else's change: a save made after someone else saved the same file is refused
  ("open it again"). A save writes a whole new file and keeps its mode.
- touch backups (the off-site copy runs as root) or anything outside the release's folder.

The history: before any save, upload over a file, restore or delete, the file as it was is copied to
`/srv/monkey/staff/history/<UTC time>-<login>/<path>` (only `monkey` can read it: it holds `server.properties`). A
delete moves the file there; nothing is ever removed from `server/` for good. The newest 200 entries are kept, at most 2 GB of them (old mod jars add up). To undo
an edit, open Files, find it in History and press Restore (which keeps the current file in the history first), or by
hand:

```sh
sudo ls -t /srv/monkey/staff/history | head                       # the newest entries
sudo -u monkey cp -p /srv/monkey/staff/history/ENTRY/config/x.toml /srv/monkey/MonkeySMP-Server/server/config/x.toml
```

Every change (a command, a save, an upload, a delete, a restore, a power action and how it ended) is one line in
`/srv/monkey/staff/actions.log`: the time in UTC, the login, the action and the file or the command, never a file's
text. With `STAFF_WEBHOOK_URL` set it is also posted to that Discord channel; empty, nothing is posted (never to the
public webhook). The controls log only their own failures, to `journalctl -u monkey-panel`.

The safety rules behind that: only requests from the machine itself, with a login name, are answered; a change must
also carry the page's own `X-Monkey-Staff: 1` header and not come from another site (`Sec-Fetch-Site`), since the
browser keeps sending the password once it has it; JSON bodies are at most 1 MB (a file being saved up to 2 MB of
text), uploads 64 MB. No program is run through a shell, and each has a time limit. The service is capped at 128 MB
of memory and runs at low priority (`Nice=10`). Check it with `sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --check`
("the controls answer a request with no login: 403" is right). To turn the controls off and keep the Status tab:
`sudo systemctl disable --now monkey-panel` (the tabs then say the request failed).

**Find what causes lag** (Server tab) runs `spark profiler start --timeout SECONDS` over RCON, with
`--only-ticks-over 100` for lag spikes or `--alloc` for memory, one run at a time, and Stop now runs `spark profiler
stop`. spark answers on its own thread, so the report link doesn't come back over RCON: the page reads the server's
log from where it was when the run started, for a `https://spark.lucko.me/...` link, and shows the first it finds
(for up to 3 minutes after the run ends, while spark uploads). A restart during a run ends the search. This was built
from spark's documentation and not tried on the live server yet: if a finished run shows no link, the Console tab
has spark's own words. A report shows the mods, the machine and the players online; spark keeps it on its own site.

What it costs on the 2-thread machine: a reading took about 0.9 CPU-seconds, at low priority (measured on the VPS on
4 November 2026, nobody online, `Nice=10`). A password check is bcrypt at cost 8, about 25 ms, not Caddy's default of 14,
about 600 ms: the machine has no spare CPU for slow hashes, and a random 24-character password doesn't need one.
Caddy has no limit on guesses. They can't get in, but a flood of them does take CPU from the game; if a tick time
ever climbs with Caddy near the top of `top`, close the page as above.

### The login page

The page can have its own login page instead of the browser's password box: a name and a password at `/login`, a
"Forgot password?" link, each person's own password and email, a Log out button, and roles. The browser's password
box stays the default and the way back. One switch changes which one is live; `--install` keeps whichever is live.

- **Logins and roles**: `tools/staff_auth.py` keeps them in `/srv/monkey/staff/auth/auth.json` (only `monkey` can
  read it). Roles are `moderator`, `admin` and `owner`. Only an owner sees the Users tab: add a login, change a role,
  disable or delete one, log one out everywhere, or make a new password link. The last owner can't be demoted,
  disabled or deleted. Names are 2 to 32 small letters, digits or `_`.
- **Passwords**: at least 12 characters, not the name. Kept as scrypt hashes, each with its own salt (about 16 MB and
  a fraction of a second per check). Five wrong passwords lock a name for 15 minutes; 20 wrong ones from one address
  in 15 minutes block that address for a while. Every failed login gets the same sentence, a name that doesn't exist
  included.
- **Sessions**: a random token in the `monkey_staff` cookie (HttpOnly, Secure, SameSite=Strict); only its hash is
  stored. A session ends after 12 hours unused or 7 days in all, at Log out, and when the password is reset. A
  password change logs out the other sessions.
- **Links**: a new login's first password, a reset and an email check are one-time links. A reset email lasts 30
  minutes; a link from the owner or the CLI and an email check last 24 hours. The token is after `#` in the link, so
  it never reaches a server log. "Forgot password?" always gives the same answer, and only sends to an email that was
  confirmed. Changing the email needs the current password; the old address is told when the email or the password
  changes.
- **Caddy**: `deploy/Caddyfile.staff-login` first removes any `X-Staff-*` header a browser sends, then asks the
  controls (`forward_auth` to `/auth/check`) about every request but the login pages themselves. With a session,
  Caddy passes on the name and role the controls give; with none, a page visit goes to `/login` and the rest gets a
  401. It needs Caddy 2.11.4 or newer: older versions could let a browser's own `X-Staff-User` header through
  (CVE-2026-30851, CVE-2026-52845). `caddy version` says which one runs. The controls must be running: they hold the
  logins.

Email is optional. With none set up, "Forgot password?" says to ask the owner, and the owner hands out links from the
Users tab or the CLI. To set it up, pick one: Resend (an API key, and a sending domain checked in Resend) or any SMTP
service with STARTTLS on port 587. Then write `/etc/monkey-staff-mail.env`, `root:monkey`, mode `640`:

```sh
# Resend
MAIL_FROM=Monkey SMP staff <staff@monkeysmp.lscaturchio.xyz>
RESEND_API_KEY=re_...
# or SMTP (both set: MAIL_BACKEND=resend or smtp picks one)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
```

```sh
sudo install -m 640 -o root -g monkey /dev/null /etc/monkey-staff-mail.env   # then fill it in with sudoedit
sudo -u monkey python3 /srv/monkey/repo/tools/staff_auth.py mail-test YOUR@EMAIL
```

A key or a token is never logged; a failed send logs only its kind (`journalctl -u monkey-panel`). The file is read
again at each send, so a change needs no restart.

Switch on, once a release that has it is live and `--install` has run (that restarts the controls):

```sh
sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --add-user lorenzo owner YOUR@EMAIL   # prints a link, or emails it
sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --add-user diego admin HIS@EMAIL
# open the link, choose a password; then:
sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --use-new-login
sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --check
curl -sI https://staff.monkeysmp.lscaturchio.xyz | head -1   # 302, to /login
```

`--use-new-login` refuses while the controls don't answer or no owner has a password. It puts the new site in, and
puts the old one back if Caddy refuses it or a visit with no session isn't sent to the login page. A lost password with
no email is `--reset-link NAME` (a new one-time link, printed once). To go back to the password box (the
`staff-logins` file is untouched, so the old passwords still work):

```sh
sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --use-basic-auth
```

The CLI also has `list`, `set-role`, `send-verify` and `end-sessions`: `sudo -u monkey python3
/srv/monkey/repo/tools/staff_auth.py --help`. It refuses to run as root, so the store stays `monkey`'s.
### Hosting controls (Settings, Mods, and more on Players and Server)

`tools/staff_apex.py` and `tools/staff_host.py` add what a game host's panel has. They run inside the same controls
(`monkey-panel.service`), with the same login, header and change checks. Every change is one line in `actions.log`.
Who may use what: the login's role (`moderator`, `admin`, `owner`). The page greys out or hides what a login can't use;
the controls refuse it whatever the page sends. With the new login (`tools/staff_auth.py`), an admin or owner login
without two-step login works as a moderator until it turns two-step on from the account menu, which says so. The menu
shows a QR code to scan with an authenticator app and the key to type by hand. Pressing it twice in the same session
gives the same key; after 15 minutes, a password change or a reset, it gives a new one. The
password box (`--use-basic-auth`) has no two-step login and gives owner: keep it for emergencies. **Before a deploy
that brings this in, every admin turns two-step on**, and never deploy it during an event (17:00 to 21:30 on event
nights): an admin without it can't run the event timer until they do.

A jar runs as the server, so only an owner adds one: uploading a jar, installing a `.mrpack`, uploading a data pack
(game code: functions, loot, recipes; turning packs on or off stays admin), and, in Files, saving,
uploading, restoring or renaming a `.jar` or anything in `mods/` or `.fabric/`, or making a folder there (checked
again after links are followed; a rename under both its old and its new name). Only
an owner changes which jars run at all (owner, 2026-11-08): installing from Modrinth, turning a jar off or on,
removing it, and keeping a pinned mod off or allowing it again. Admins see those buttons greyed out. An admin still
searches Modrinth and answers "do players need it?", which only notes the answer and moves no jar.

| What | Who | What it does |
|---|---|---|
| Settings | admin | `server.properties` as typed fields. RCON, ports, query, seed, world name, online mode and secrets are locked. A save keeps the old file in the history. |
| Game rules | admin | `gamerule NAME VALUE` over RCON, for known rules only. |
| Back up now, list snapshots | admin | Asks the root helper (below). |
| Restore a snapshot | owner | Types the snapshot's short ID. The live world is kept in `backups/before-restore-TIME`. |
| Schedules | admin | A command, a restart (with warnings) or a backup, daily, weekly or every N minutes; whoever is online, only when nobody is, or only when someone is. A run whose condition doesn't hold is skipped and says so; so is one when the server won't say who is on. A restart only when empty checks again after its warnings, and is called off if someone joined (chat then says so). A stopped server counts as nobody online. |
| Mods list | moderator | Each jar's name, version and side, whether it is off, pinned or kept off, and whether players need it. The mods players need that their pack lacks, and the mod changes waiting for a release of the players' pack. |
| Upload a jar, install a modpack | owner | A jar or `.mrpack` from the owner's computer. |
| Search Modrinth | admin | Fabric mods for the server's game version that run on a server. |
| Mod manager | owner | Install from Modrinth, turn a jar off or on, remove it. Types the jar's file name (Modrinth: the mod's short name). |
| Keep a pinned mod off | owner | Turning off or removing a pinned mod asks "Keep it off after restarts" (ticked), when the live release supports it. Allow again undoes it. Types the jar's file name. |
| Do players need it | admin | Yes, no or don't know, for a mod Modrinth doesn't know. Saved with the mod. |
| Upload a data pack | owner | A data pack `.zip`, checked, then into the world's `datapacks/`. |
| Data pack troubleshooting | admin | Turn all off (types `ALL OFF`) saves which packs are on and turns them off; Turn saved set back on puts them back in order. |
| World download | owner | A one-time link to a zip of the world. Saving is off while it streams. |
| Bans by address | admin | `ban-ip` and `pardon-ip`. Public addresses only. The log never holds the address. |
| Version switch | admin | The helper runs `monkey-deploy.sh --tag=vX.Y.Z` for a release tag from the checkout. Types the tag. |
| Reset the world | admin | Types `RESET`. Optional new seed. The old world is moved aside, never deleted. |
| Upload a world | admin | A `.zip`, up to 8 GB, checked on arrival. Swapped in only when `REPLACE` is typed. |
| SFTP card | admin | Host, port and user names, or "ask the owner". |
| Event timer | admin | `tools/staff_events.py`: start (name and minutes), end now with "Event over", or stop early, over RCON (`monkey:events/timer/*`, from 3.2.0's data pack; while `monkey-events` is off the card says so). |
| Everyone who has joined, notes | moderator | The Players tab's list, and adding a note. Deleting a note is admin; it stays in `player-notes.json`'s `deleted` list (the newest 200), so it can be put back by hand. |
| Saved commands | admin | The Console tab's list: save, run, delete. A run is an ordinary console command. |
| Search and download the changes | moderator | The Server tab's record of changes, searched, and as a `.csv`. |
| Temporary bans | admin | Ban for 1 hour to 30 days; lifted by the page at that time, or now with "Lift now". Moderators see the list. |
| Search all files | admin | The Files tab's search, by name or in the text of settings files. |
| Find what causes lag | admin | `tools/staff_spark.py`: spark's profiler for 1 to 10 minutes (everything, lag spikes only, or memory), then a link to its report. Moderators see the state and the link. |
| Console commands | moderator | A moderator login runs only the commands on the owner's list (Console tab, "Commands moderators can run"; `staff/mod-commands.json`, mode 600). The standard list: `list`, `say`, `msg`, `tell`, `w`, `kick`, `whitelist add`, `whitelist remove`, `whitelist list`. An entry of two words allows only that pair. Entries can only start with known commands that can't run others, make operators, place a command block or send a click (`list`, `say`, `msg`, `kick`, `ban`, `pardon`, `whitelist`, `tp`, `spectate`, `gamemode`, `effect`, `clear`, `kill`, `weather`, `time`, `gamerule`, `ledger` and a few more: `CAN_ALLOW` in `tools/staff_lookup.py`). `gamemode` only as survival, adventure or spectator (creative lets a client make any item) and `ledger` only as search, page or status (purge deletes the history, rollback and restore change the world): `SECOND_WORDS`. `setblock`, `give`, `data` or `summon` could make a command block, which runs as the server, and `tellraw`, `team` or `bossbar` text can carry a click that runs a command as an operator who clicks it. A list that can't be read allows nothing. Admins and owners run any command, as before. Changing the list is owner. |
| A player's history | moderator | The Players tab: one player's lists, ban and reason, temporary ban, notes and every change in the record that names them (the newest 200 of the current `actions.log`). |
| Who changed this block | moderator | The Players tab: Ledger's rows for one block or up to 8 around it, in the last 6 hours to 30 days, everything or only blocks, chests or kills, optionally one player. It only reads (`world/ledger.sqlite`, through its location index, at most 500 rows and 3 seconds); a rollback is still Ledger's own command in game. |
| Updates on Modrinth | admin | The Mods tab: each enabled jar's sha512 is sent to Modrinth's `version_files/update` with the loader and game version, and the jars with a newer file are listed with a changelog link (kept 30 minutes; "Check for updates" asks again). Nothing else about the server is sent. An owner presses Update and types the mod's short name: the same install as the mod manager's, so the old jar moves to `mods-removed/`. A pinned mod has no Update button: it comes with a release. |
| Update the leaderboard now | admin | `save-all flush` over RCON, then `sh deploy/monkey-standings.sh board` as `monkey`, so Cup points given a minute ago show. A busy deploy lock answers "skipped". |
| Mod settings | admin | Each mod's config file (`config/`, and `.properties` files next to `server.properties`) as a form: `.toml`, `.properties`, `.json`, `.json5`. A save changes only the edited values, so comments and order stay. Secrets are hidden and locked. A file the form can't read opens in Files. Takes effect after a restart. `deploy/staff/mod-settings.json` names each mod's main keys. |
| Strength SMP | admin | The Mod settings tab's Strength SMP card: the 9 ultimate cooldowns and 9 lifetimes (seconds, 2 to 86400), the armor ultimate charge and "powers only for tagged players", as `scoreboard players set $Config Strength_SMP+Config-...` over RCON. Takes effect at once and stays after a restart (the scores live in the world). Reset to defaults types `RESET`. Needs the server running. |

The mod manager:

- An upload must be a Fabric jar (a zip with a `fabric.mod.json` that names a mod id), at most 64 MB, with a plain
  file name (letters, digits, `. _ + -`, ending in `.jar`). A client-only mod is refused: it belongs in the players'
  pack.
- A jar with the same name, or another enabled jar with the same mod id, moves to `server/mods-removed/TIME-XXXX/`
  first. Remove and turn-off move or rename too: nothing in `mods/` is ever deleted. To undo by hand, move the jar
  back from `mods-removed/`.
- Modrinth: a search asks `api.modrinth.com/v2` for Fabric mods for the server's game version
  (`monkey/manifest.json`) that run on a server. An install takes that version's newest release file, only from
  `cdn.modrinth.com`, and checks its sha512 against Modrinth's. It lists the required mods; it doesn't install them.
  The API parameters are from memory, not checked against a live answer.
- Two warnings, shown on the page too. A mod players need must match in their pack, or they can't join. And the
  release's own mods are pinned (`server/.monkey-state.json`): the server puts a pinned jar back each time it starts,
  so turning one off or replacing it lasts only until the next start, and the next release deploy puts `mods/` back
  to that release's list. A change takes effect at the next restart.
- **Keep it off**: turning off or removing a pinned mod asks "Keep it off after restarts?" (ticked). Then the
  mod's slug (from the release's `monkey/manifest.json`) goes in `server/.monkey-held.json` with who, when, why and
  the jar's name then: `{"mods": {"<slug>": {"by", "at", "why", "file"}}}`. The start script (`Monkey.psm1`,
  `Get-HeldMods`, `Sync-ManagedFiles`) doesn't download a manifest mod whose slug is held: the start log says
  `held  <slug> (kept off by staff, <jar> not put in)`. It stays in the install state, so **Allow again**
  (`POST /api/mod-hold`), turning the jar back on, or installing a jar of the release's name puts it back at the
  next start. A hold lasts across restarts and release deploys (`monkey-deploy.sh` never touches `server/`, and a
  release that bumps the jar's version keeps the same slug) until someone allows it again. Only mods the release's
  manifest lists can be held. Every key that looks like a slug holds, whatever its value; a missing or broken file
  holds nothing, and the start never fails on it. A held mod whose jar is gone from `mods/` stays in the list, with
  Allow again. When players have the mod in their pack and their game needs it, the page says that keeping it off
  may stop players joining. The page offers the box only when the live package's `Monkey.psm1` has `Get-HeldMods`:
  after a rollback to a release without it, a hold is refused (turn the mod off without keeping it off). If the
  move works but the held file can't be written, the mod stays moved and the page says the hold wasn't saved.
- **Do players need it**: after each install the page asks Modrinth: an upload by its sha512
  (`/v2/version_file/HASH?algorithm=sha512`, then the project's `client_side`), a Modrinth install from the project
  it already has, a modpack from its own `env`. It is noted in `server/.monkey-mod-sides.json`. A failed lookup is
  "unknown" and never stops the install; the page then asks staff (yes, no, don't know). Staff's answer always
  replaces the note; a lookup's "unknown" never replaces a known answer. `required` and not in the players' pack
  shows a red notice: players must install it too, and until the owner adds it to the players' pack in a release
  they may not be able to join. The mods list names every enabled mod players need that the players' pack lacks: the pack is
  `client/modrinth.index.json` in the repo checkout, matched by Modrinth project or jar name. When the checkout has
  no readable pack, the list is every mod marked as needed. The page never changes the players' pack.
- **Players' pack: waiting for a release** (owner, 2026-11-08): the Mods tab lists the mod changes players need in
  their pack too, worked out afresh from the mods folder each time:
  - *add*: an enabled jar players need (`required`) that the owner put in, whose file the pack lacks. A new version
    of a mod the pack has counts too: the pack must have the server's version.
  - *remove*: a mod players need that is in the pack but no longer runs here: a jar the owner put in and then turned
    off or removed, or a release mod kept off. A release mod that is only off or removed comes back at the next
    start, so it isn't one.

  After each mod change the page writes the list to `server/.monkey-pack-changes.json` (who, when, and for an add
  the jar's sha512). A line goes by itself once the deployed release's pack matches the server, or when the owner
  undoes the change. Nothing on the VPS writes to the repo or to Modrinth: on the owner's PC,
  `python tools/pack_sync.py --ssh HOST` reads that file over the owner's SSH login and changes
  `client/modrinth.index.json` and `package/monkey/manifest.json` (`--pr` opens a draft pull request). Players get
  it once the owner merges that and tags a release (docs/MAINTAINING.md, "Releasing").

The data packs box (admin, Mods tab) has a troubleshooting mode for "which pack breaks it":

- **Turn all off** (types `ALL OFF`, the server must be running) reads `datapack list enabled`, saves the world's
  own packs (`file/...`, in their order) to `/srv/monkey/staff/packs-saved.json` with who and when, then runs
  `datapack disable` for each. A pack is found in the list by its exact name in the datapacks folder, so names with
  spaces work. Vanilla, Fabric's and the mods' built-in packs stay on. One saved set at a time.
- While a set is saved, the box says "Troubleshooting since TIME by NAME: N of M saved packs still off" (what the
  server has on now). Turn packs on one at a time to find the trouble.
- **Turn saved set back on** runs `datapack enable` for each saved pack in the old order (each goes on top, so the
  order comes back) and names any that failed: gone from the folder, or refused by the server. The file stays, so a
  second try is safe. **Clear the saved set** forgets it.
- Both read each answer ("Unknown data pack" and the like mean it did nothing), then list the packs again and
  report what the server really has. A pack still in the wrong state is tried once more (the server can drop a
  change made while it reloads, MC-200471), then listed again.
- After a restart or start pressed on the Server tab, the power card lists the errors logged since the server
  started again (its start time from the power card, not the time of the press: a normal restart waits 5 minutes).
  It reads `staff.json`'s error groups, so it is up to 2 minutes late, and says when each was last seen.

The root helper (`monkey-staff-helper.path` and `.service`, root) does the jobs the panel can't, as `monkey`: backups,
restores, version switches, resets and world swaps. The panel writes a request file of fixed words and checked values
into `/srv/monkey/staff/requests`. The helper reads only those values, and only six actions. One world or version job
runs at a time. Install it once (owner):

```sh
sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --install-helper
```

The helper runs root's copies in `/opt/monkey` ("Root's own copies"): install them first. `--install-helper`
takes its units from root's clone, `/opt/monkey/src`.

- **Version switch**: players are warned (5 minutes if anyone is on), a backup is taken, the server restarts on that
  release's files. The tag is pinned in `/srv/monkey/MonkeySMP-Server/.deploy-pin`, so the nightly deploy stays on it.
  Picking the newest release takes the pin away. An older release leaves the repo checkout where it is.
  By hand: `sudo -u monkey sh /srv/monkey/repo/deploy/monkey-deploy.sh --tag=vX.Y.Z`.
- **Reset**: a 1-minute warning, the server stops, `world`, `world_nether` and `world_the_end` and
  `server.properties` are kept in `backups/before-reset-TIME/`, the new seed (if any) goes into `server.properties`,
  and the server starts and makes a new world. The seed is never logged or shown: the log says "seed changed".
- **World upload**: the zip streams to `/srv/monkey/staff/uploads/` (a free-disk check first: twice the zip and 2 GB
  spare). It needs exactly one `level.dat`, at the top or one folder in, and no absolute path, `..`, link or
  encrypted entry. Only one upload waits at a time. On `REPLACE`, the helper unpacks it again as `monkey` beside the
  world (checked again), then warns, stops, keeps the live world in `backups/before-upload-TIME/`, swaps the new one
  in and starts the server.

Old worlds in `backups/` are never removed by the page. Check the disk now and then: `df -h /srv/monkey`.

#### SFTP logins (owner step)

An SFTP login can use SFTP only: no shell, no forwarding, no tty. It logs in with a key only and sees one folder,
`server/` of the live release, through a chroot. The owner makes one as root, with the person's public key file:

```sh
sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --add-sftp-user diego /tmp/diego.pub
sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --remove-sftp-user diego
```

`--add-sftp-user` (in `deploy/monkey-sftp.sh`):

- adds the group `monkey-sftp` and the user (no home, `nologin`, no password)
- puts the key in `/etc/ssh/monkey-sftp-keys/NAME`
- makes `/srv/monkey-sftp/NAME` (root's, as sshd needs; it is outside `/srv/monkey`, which the monkey user owns; an
  older `/srv/monkey/sftp` is left as it is: remove its logins first with `--remove-sftp-user`, then add them again) with `server/` in it, a bind mount (also in `/etc/fstab`; the
  old fstab is copied first)
- gives NAME read and write on `server/` through ACLs (needs `sudo apt install acl`)
- writes `/etc/ssh/sshd_config.d/monkey-sftp.conf`: `Match Group monkey-sftp` with `ChrootDirectory`,
  `ForceCommand internal-sftp`, key only, no forwarding
- runs `sshd -t` and `sshd -T` for NAME and for root before it reloads sshd. If any check fails, the old drop-in is
  put back and sshd is not reloaded
- writes `/srv/monkey/staff/sftp.json` (host, port, user names: no secrets) for the page's SFTP card

`/etc/ssh/sshd_config` must `Include /etc/ssh/sshd_config.d/*.conf` (Ubuntu's does). Set `SFTP_HOST` in
`/etc/monkey-deploy.env` to show a name other than `hostname -f`. Keep a second SSH session open while you add the
first login, in case sshd misbehaves. `--remove-sftp-user` unmounts, takes the fstab line and the ACLs out and
removes the user and key; the server's files stay as they are. Not run on a real machine yet: the tests check only
its arguments and its text, so watch the first run.

### Trends: a month of numbers

`staff.json` holds one day. For longer charts the same 2-minute job runs `tools/staff_trends.py update` after it, under
`nice` and without the webhook, and keeps three files in `/srv/monkey/staff/trends/` (mode 600: they hold names). A
run that fails leaves its file as it was and never stops the status file or the other two parts. A kept file the
page can't read (cut short, hand-edited) is started again, and the run log says so.

- `history.json`: the readings folded into hours, 30 days of them (about 50 KB): tick average, the worst P95, players
  on average and at most, memory and CPU in use. Every run works out again the hours `staff.json` still has, so a
  restart of the job loses nothing. The oldest hour, which `staff.json` may hold only part of, keeps the row made from
more readings.
- `players.json`, at most every 10 minutes: who played each day and for how long, from the game's own "joined the
  game" and "left the game" lines. Each finished `logs/*.log.gz` is read once, in order; `latest.log` is kept apart
  and read as a stream from where the last run stopped (only the lines it needs are held), from its start again once
  it is a new file. A session ends at its leave line, at "Stopping server", at the next start (a crash: where
  the log last spoke), or, for someone still on, now (those minutes count; it is no finished session yet). Days are
  Pacific. A renamed player counts as new, and so does one back after a year. Everyone in the first log looks new, so
  that day's "new" is left blank, its players are left out of retention, and that week's row is `partial`.
- `world.json`, at most every hour: Ledger's block breaks and places by players, per hour and per player per day,
  with stone, diamond ore and ancient debris counted apart. It opens `world/ledger.sqlite` read-only and asks only
  through its `player_id` index, one player at a time, starting after the last row it counted, so it never touches
  Dynamic Lights' rows. A run stops after 300,000 rows or 4 seconds of the database's time, or when the game holds
  the database, keeps what it counted and goes on at the next 2-minute run; the first run reads each player's rows
  once and keeps the last 30 days. Without that index it counts nothing, says so in `note`, and tries again hourly.

The page asks the controls for them (all `GET`, moderator and up, the same login and role checks as the rest):

| Request | Answer |
| --- | --- |
| `/api/trend-history?days=30` (1-30) | one row an hour: `[hour (unix), avg, p95, players, players_max, memory, cpu, readings]` |
| `/api/trend-players?days=30` (1-45) | per day: players, new players, hours played, sessions, the median session; session lengths in six buckets; per week of new players, how many joined again 1 and 7 days after their first day (`due_*` is how many have had that long) |
| `/api/trend-world?days=7` (1-30) | blocks broken and placed per hour, and this week's top 10 by blocks broken |
| `/api/trend-ores?days=7` (1-30) | per player: stone, diamond ore and ancient debris mined, per 1,000 stone, and `outlier` by the weekly report's x-ray test (at least 500 stone and 10 ores, 3 times the median). A hint for a closer look, never proof |
| `/api/trend-standings` | each closed week's faction table from `STANDINGS_DIR/weeks/` (rank, points, Cup, Strength, kills, bounties, outposts), never the members |

Before the first run the answers are 404 "No trends yet"; a damaged file is 503 until the next run starts it again. `sudo -u monkey python3 /srv/monkey/repo/tools/staff_trends.py
show /srv/monkey/MonkeySMP-Server --staff /srv/monkey/staff` prints what a run would keep and changes nothing. The
routes need the panel restarted after a deploy, as the other controls do; the job picks up the new tool by itself.

### The weekly rule check (the Reports tab)

The Reports tab shows, for each ISO week (Monday to Monday, Pacific), which server rules each player may have broken,
as a grid: players down the side, rules across, a count in each cell. **It only reports.** It punishes nobody, messages
nobody and rolls nothing back; staff look at the rows and decide. Moderators and up can see it.

`monkey-report.timer` runs `deploy/monkey-report.sh` as `monkey` on Mondays at 1:15 AM Pacific (Nice 19, idle disk
priority, so the game never waits on it), which runs `tools/staff_report.py write` for the week that just ended. It
writes `/srv/monkey/staff/reports/2026-W46.json` (one file per week) and `reports/stats/2026-W46.json`, a copy of
everyone's game stats, which the next week counts from. A week already written is skipped, so a missed or repeated
run is safe. It reads only, never through RCON:

- Ledger's database, opened read-only (`?mode=ro`), only the week's rows. Rows from the `command` source (Dynamic
  Lights' light and air blocks, about 40 million a day) are left out.
- the game's stats (the week's change against last week's copy), the parties (Open Parties and Claims), the
  usercache, `level.dat` (the spawn) and the server's logs.

Ledger and log times are Pacific. Logins' addresses are hashed in memory with a key made for that run and then
dropped: the report says only which players shared a connection, never an address. Each cell has a level:

- **clear** (solid gold): the logs show it plainly.
- **likely** (dimmer): probably, for example a kill in the launch hour or one-way takes from another faction's chest.
- **unclear** (dashed): worth a look, for example a pickup of a banned item, a kill in the victim's first 48 hours or
  a combat log just after a time-out.

Clicking a cell shows its rows (time, world, position, what happened). Below the grid: the checks that came back
clean, the ones skipped because a file was missing, notes and the week's mining table. "Copy for Discord" makes
code-block messages under 2,000 characters each and copies the first. The checks and their rules (docs/RULES.md):
portal trapping (4, 7), pearls (B3), enchanted golden apples (B5), totems (B4), end crystals (B7), netherite armor
(24), kills in the launch hour (23, launch week only), kills in a victim's first 48 hours (26), combat logs (3),
chest takes from another faction (39), a faction over 4 (29), a group over 4 (32), shared connections (21), the
x-ray ratio (B15), TNT near spawn (B11), broken bedrock (44, 45) and the Nether roof (46). The game's stats can't be
split by time, so pearls, gapples, totems, crystals and netherite count the whole week; everything before the launch
(staff test play) is left out of the rest.

Install it once the release with it is live (owner step; nothing else needs restarting but `monkey-panel`, which
loads the new routes):

```sh
sudo sh /srv/monkey/repo/deploy/monkey-report.sh --install   # the units, the reports folder, the timer
sudo systemctl restart monkey-panel
sh /srv/monkey/repo/deploy/monkey-report.sh --check            # this week so far, as JSON; writes nothing
```

To write last week now: `sudo systemctl start monkey-report.service`. `python3 tools/staff_report.py show
/srv/monkey/MonkeySMP-Server` prints this week so far (`--week 2026-W45` for another) and writes nothing; on the live
world it takes about 15 seconds. Log: `journalctl -u monkey-report -n 50`.

## Load test

The player table in docs/ADMIN.md was measured on an i7-8700K with nothing else running. The VPS core is
faster, but it has only two threads, shared by the game thread, BlueMap's renderer and the garbage collector, so its number has to be measured on the VPS.
`deploy/monkey-loadtest.sh` runs `tools/loadtest.py` there: 30 Carpet fake players with a survival inventory (`--kit`),
standing spread out in generated terrain, 5 minutes measured, with a spark profile of every thread. 30 is the owners'
worst case for launch night.

Run it as root at a quiet time, after Chunky has finished pre-generating (it refuses before that; `FORCE=1`
overrides) and not around midnight UTC (monkey-day.timer). The server is offline for about 15 minutes: the
script says so on Discord and warns anyone online. Started with `systemd-run`, it carries on if SSH drops:

```sh
systemd-run --unit=monkey-loadtest --collect -p TimeoutStopSec=20min sh /srv/monkey/repo/deploy/monkey-loadtest.sh
journalctl -fu monkey-loadtest
```

To compare with the 3.1.0 rows below, run `monkey rcon "bluemap stop"` first, because the copy inherits that state, and
add `--setenv=SCENARIOS='still walk'` (the default is `still` only). Both scenarios took about 20 minutes offline on
2026-11-04. Run `monkey rcon "bluemap start"` only after the script has finished: the copy takes the state from the
script's second `rsync`, once the server has stopped, so starting it earlier puts the map in the numbers.

Before a release ships the script, copy `deploy/monkey-loadtest.sh`, `deploy/lib.sh` (it sources it from its own folder) and `tools/loadtest.py` together to `/root/`, as the script passes `--kit`, and
run `systemd-run --unit=monkey-loadtest --collect -p TimeoutStopSec=20min --setenv=LOADTEST_PY=/root/loadtest.py sh /root/monkey-loadtest.sh`.

Why it is safe for the live world and for players:

- It holds the deploy lock: no deploy, daily restart or off-site backup runs meanwhile.
- It tests a copy. `rsync` copies the live folder while the server runs, then once more (only what changed)
  after the server has stopped and saved. The live folder is only read.
- Tebex is taken out of the copy, which would otherwise claim real purchases and run their commands there,
  and Chunky won't resume pre-generating in it.
- The copy runs in a one-off container that publishes no ports: nobody can join it, and its ports (25565,
  RCON, BlueMap's 8100) can't clash with the live ones.
- The live server is stopped meanwhile (the machine can't hold both heaps, and both would share the two
  threads). It is started again whatever happens, including a failed test, and the copy is deleted.

Results stay in `/root/loadtest-results/<time>/` (`summary.json` per scenario, with the spark link and
ServerCore's status); the headline goes to the staff webhook.

| Date | Release | Players | Median tick | Worst p95 | TPS | spark profile |
|---|---|---|---|---|---|---|
| 2026-10-25 | v2.4.1 | 24 of 25 | 23.6 ms | 74.3 ms | 20.0 | https://spark.lucko.me/fyE6dSvpV0 |
| 2026-11-02 | v3.0.0, still, no kit | 30 of 30 | 53.8 ms | 129.7 ms | 18.0 | https://spark.lucko.me/yHTlfc2FXO |
| 2026-11-02 | v3.0.0, walk, no kit | 30 of 30 | 63.5 ms | 170.3 ms | 15.2 | https://spark.lucko.me/S9do0Sa6Ff |
| 2026-11-04 | v3.1.0, still, kit | 30 of 30 | 47.5 ms | 85.0 ms | 20.0 | https://spark.lucko.me/z6sharFj5R |
| 2026-11-04 | v3.1.0, walk, kit | 30 of 30 | 53.2 ms | 145.1 ms | 18.2 | https://spark.lucko.me/Jj9CMiEacO |
| 2026-11-04 | v3.1.1, still, kit, map on | 30 of 30 | 57.4 ms | 171.5 ms | 17.0 | https://spark.lucko.me/a4GsPv9toP |
| 2026-11-04 | v3.1.1, walk, kit, map on | 30 of 30 | 63.4 ms | 278.9 ms | 14.7 | https://spark.lucko.me/0iiEUSnbat |
| 2026-11-04 | v3.1.1, still, kit | 30 of 30 | 49.0 ms | 91.4 ms | 20.0 | https://spark.lucko.me/LGNIWKwj2K |
| 2026-11-04 | v3.1.1, walk, kit | 30 of 30 | 55.8 ms | 142.6 ms | 17.8 | https://spark.lucko.me/thVMPRbhTA |

The first run, on 2026-10-25 at 22:30 Pacific. One fake player (Load08) didn't join, so it ran with 24. The
median sample stayed at 13-31 ms: about 30 ms for a minute or two, then about 15 ms. No 10-second sample
averaged over 50 ms. The worst p95 was 74 ms and the worst p99 105 ms, with two "can't keep up" warnings.
ServerCore kept the full distances (simulation 6, view 8), so the numbers aren't flattered. **Decision:
leave it.** The run's `summary.json` and staff post hold a docs link that spark printed while stopping;
`tools/loadtest.py` now skips those. The profile link above came from the run's `server.log`.

**Don't rely on that row.** Until 3.0.0 the tool lost most of its fake players in the first two minutes and didn't
say so (CHANGELOG, 3.0.0), and the tick dropping from about 30 ms to about 15 ms fits that. The tool now records
`players_online_min` and the staff post gives it: a run only counts if it equals the players asked for.

**3.1.0 on the launch world**, 2026-11-04 at 19:00 Pacific, after pre-generation. Lower than the 3.0.0 rows in both
scenarios, though the runs differ: these had a kit and the launch world, and the map's state in 3.0.0's isn't recorded.
Still over 40 ms. BlueMap's render threads were paused (`render-threads-enabled: false` in
`bluemap/pluginState.json`, which the copy inherits), so neither row has the map's renderer in it. `still` kept mob cap
100%, simulation 6 and view 8, with chunk-tick distance at 9; 4 of its 30 samples averaged over 50 ms. `walk` ended on
mob cap 50%, chunk-tick distance 3, simulation 4 and view 8, with 25 of 30 samples over 50 ms. So in `walk`, steps 1 and 2
of the rule below are already in the number. `still` stayed at simulation 6 because nothing moves between 40 and 50 ms,
so step 2 hasn't been tried there: a fixed lower distance is the next free test, and a bigger plan comes after that. On
2026-11-04 Reizor's Dallas page listed
3 threads and 24 GB at $67.50 a month, and 4 threads and 32 GB at $90 as sold out. **Decision (2026-11-04): launch on
this plan**, and look again if `spark tps` stays under 18 TPS on launch night.

In `walk`, data pack and other commands were 47.8% of the main thread's samples, and the main thread waited for only
5.2% of the tick. Game logic runs on that one thread, so more threads help only as far as the renderer and the garbage
collector are taking its turn, which nobody has measured. Carpet's own frames, which real players don't have, were
about 7%. Fake players also have no farms, fights or building, so read this as a number to compare releases with, not a forecast.
Real players could land on either side of it.

**3.1.1 with the map on**, 2026-11-04 at 22:14 Pacific. Not comparable with the 3.1.0 rows: `bluemap start` went in
before the script's second copy, so the copy had `render-threads-enabled: true`. The server process used about 89-99% of
the CPU, against about 51-75% in the 3.1.0 runs, and `BlueMap-RenderThread-0` shows real work only in these two profiles.
`still` had 23 of 30 samples over 50 ms and ended on mob cap 80%, chunk-tick distance 6, simulation 6 and view 8. `walk`
had 29 of 30, one 2164 ms old-generation collection, and ended on mob cap 40%, chunk-tick distance 3, simulation 4 and
view 7. Read these rows as what launch night could look like if the 4:30 PM `bluemap stop` (docs/LAUNCH.md) is missed.

**3.1.1 with the map stopped**, 2026-11-04 at 22:44 Pacific, the rows to compare with 3.1.0. The copy had
`render-threads-enabled: false`, spark's process CPU was about 59% and 71%, and no render thread appears in either profile.
So the map was most of the difference above. Against 3.1.0, `still` is 1.5 ms slower at the same 20.0 TPS, ending on
chunk-tick distance 7 instead of 9. `walk` is 2.6 ms slower at 17.8 TPS against 18.2, ending on mob cap 40% instead of 50%,
with 23 of 30 samples over 50 ms against 25. That's one run each, so it doesn't separate any cost of Mace Limiter from
ordinary variation between runs. `walk` is now just under the 18 TPS named in the decision above. That line is about
`spark tps` with real players on launch night, so this row doesn't trigger it.

**3.1.0 on the home PC.** The table above is the VPS; these are the i7-8700K with its slow disk, so compare them only
with each other. 30 fake players with a kit, standing, all 30 online, no command-limit hits:

| Build | Median tick | Worst p95 | TPS | ServerCore held | spark profile |
|---|---|---|---|---|---|
| 3.1.0's mods, no speed patches | 185.1 ms | 335.8 ms | 5.4 | mob cap 60%, simulation 5 | https://spark.lucko.me/Dzh1y2KSog |
| With the speed patches | 68.5 ms | 153.5 ms | 14.1 | mob cap 40%, simulation 4, view 7 | not captured |
| Final build: Nether mods gone, data pack in, fresh world on the launch seed | 52.5 ms | 88.9 ms | 18.0 | mob cap 40%, simulation 4, view 8 | not captured |

Those runs ended on different settings, and the last is a newer world, so not all of the gain is the patches or the
Nether mods. In the second run datapack commands were still 64% of the tick.

**What the Enchant Disabler data pack costs.** The final build again, with a throwaway datapack giving and clearing one
stone per player per second, because the pack's advancement only fires on an inventory change:

| Run | Median tick | Worst p95 | TPS |
|---|---|---|---|
| Mod and pack | 54.8 ms | 108.0 ms | 17.2 |
| Mod and pack, repeated | 54.0 ms | 86.6 ms | 17.7 |
| Mod only | 54.0 ms | 89.0 ms | 17.6 |
| Pack only | 54.1 ms | 90.6 ms | 17.0 |
| Mod and pack, all 30 holding a DnT book | 59.6 ms | 127.6 ms | 16.0 |

The repeat shows the noise, about 0.8 ms, so the pack's own cost doesn't show. The last row is the worst case: with the
mod installed the pack can't strip a book, so it checks every slot again on each change. That is about 5 ms if all 30
hold one, and event books are rare.

The worst p99 is about 6 s, and up to 13 s in these runs, one stall each autosave: the main thread writes 30 players' `.dat` files
(`PlayerList.saveAll` in a JFR recording) and this PC's disk is slow. Holding the view distance at 8 didn't remove it.
The VPS's p99s above (547 ms and 1,055 ms) may be the same thing; nobody has checked.

**Decision rule.** Under about 40 ms median at 30 players, leave it: that leaves room for spikes. Above
that, change one thing at a time, in this order, and run the test again after each:

1. **Pause BlueMap in the evening** if it shows up. It already renders on one thread
   (`render-thread-count: 1`); `bluemap stop` over RCON pauses it and `bluemap start` resumes it.
2. **Lower `simulation-distance`** in the live `server.properties` from 6 to 5, then 4, and the `max` of
   `SIMULATION_DISTANCE` in `server/config/servercore/config.yml` with it: ServerCore raises the distance back to that
   `max` once ticks recover. Players still see 8 chunks; mobs, crops and farms only run nearer. If
   `servercore_status` in `summary.json` shows lower distances than these, ServerCore's dynamic mode was already
   cutting them during the test because ticks averaged over 50 ms, so the real cost is higher than the number. It cuts
   above `target-mspt` plus 5 and raises below `target-mspt` minus 5, so at this server's 45, nothing moves between 40
   and 50 ms. That's
   from ServerCore's source (`DynamicManager`, `LinkedSetting`), not tried on this server.
3. **A plan with 4 or more threads** if it is still over 40 ms.

## DDoS protection

Today players connect straight to the VPS address (the `play.monkeysmp` A record), and that address is in
public DNS history. Whether to do more depends on what Reizor filters, so the question below goes to Reizor
support first. As of 2026-10-25 nothing has changed and DNS stays as it is.

- **Always-on filtering at Reizor's edge** that covers the game ports (TCP 25565 and UDP 24454): nothing to add
  beyond its panel firewall.
- **Only a null-route when attacked**, or no filtering: put TCPShield in front, as below.

The question for Reizor support (the owner sends it):

> Does my VPS (Dallas) have DDoS filtering at your network edge? Is it always on, or does it null-route the
> address when an attack is detected? Does it cover game traffic, TCP 25565 (Minecraft) and UDP 24454 (voice
> chat)? Is there a firewall in your panel that filters before traffic reaches the VPS? Can I get a new or
> additional IPv4 address, and at what cost? Do you notify customers when an attack is mitigated?

**The TCPShield plan** (only if the answer is weak):

1. **Tier.** Free ($0, 1 TB a month, sized for 20-30 players) covers the game only. Voice chat's UDP isn't
   proxied on Free: voice either stops working, or `voice_host` points at the VPS and publishes the address
   the proxy hides. Pro ($25 a month, 5 TB) adds Simple Voice Chat support. With Free, check the traffic after
   the first month (`vnstat` on the VPS).
2. **The real player addresses.** The Proxy Protocol Support mod (Fabric, server side only,
   added with `tools/add.py`) reads them from the proxy, so bans, LuckPerms and logs see players, not
   TCPShield. In `server/config/proxy_protocol_support.json`: `"enableProxyProtocol": true`,
   `"whitelistTCPShieldServers": true` (it fetches TCPShield's addresses itself) and
   `"directAccessIPs": ["127.0.0.1"]` (drop the default `192.168.0.0/16`), so anything else is refused.
3. **Lock the VPS to the proxy.** Docker publishes ports past ufw, so a ufw rule doesn't close 25565. Use
   Reizor's panel firewall if it has one, or the `DOCKER-USER` chain (matched on the original port, since
   Docker rewrites the destination), then save the rules with `netfilter-persistent save`:

   ```sh
   iptables -I DOCKER-USER -p tcp -m conntrack --ctorigdstport 25565 -j DROP
   for net in $(curl -fsS https://tcpshield.com/v4/); do
       iptables -I DOCKER-USER -p tcp -s "$net" -m conntrack --ctorigdstport 25565 -j RETURN
   done
   ```

4. **A new address.** The current one is already public, so the proxy only hides a new one. The map's
   `A` record names the same machine and would leak the new address too, so the map moves behind an HTTP
   proxy or off the VPS at the same time.
5. **DNS last.** Point the `_minecraft._tcp.monkeysmp` SRV record at the TCPShield address, and each join
   address's SRV record with it (docs/PROMOTION.md), as for a failover. Then check the Uptime Kuma game
   monitor still answers through it.
