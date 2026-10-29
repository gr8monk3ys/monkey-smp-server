# The live server (monkeysmp.lscaturchio.xyz)

How the paid, always-on copy of Monkey SMP runs: one Linux VPS running the Docker setup from the release,
kept in step with this repo by `deploy/realms-deploy.sh`, with a home PC on playit.gg as the fallback.
The business side (prices, costs, referrals) is in the plan linked from the PR that added this file; the
public site is `site/`.

```
players --> monkeysmp.lscaturchio.xyz (SRV record) --> play.monkeysmp.lscaturchio.xyz (A) --> VPS :25565
                                                     \-> failover: SRV target swapped to the playit.gg address
browsers --> https://map.monkeysmp.lscaturchio.xyz (A) --> VPS: Caddy :443 --> BlueMap 127.0.0.1:8100
repo (tag vX.Y.Z) <-- git fetch every 5 min -- VPS: realms-deploy.timer --> docker compose (the release's docker/)
```

## Why releases, not every push

A deploy restarts the server, and when `client/` changed every player has to update their pack before they
can join again. A release tag is the point where both exist: the release workflow publishes the matching
`.mrpack`. So the VPS follows the newest `vX.Y.Z` tag. To make any merge to `main` go live instead, set
`TRACK=main` in `/etc/realms-deploy.env`. GitHub Actions doesn't start in this private repo right now
(billing), and the VPS pulls rather than being pushed to, so nothing here depends on Actions or on an
SSH key into the server.

## The machine

One fast core matters more than anything else (docs/ADMIN.md, "How many players"): a current Ryzen
(7000/9000 series) at about 5 GHz runs about 25 players at 20 TPS; an old Xeon runs fewer than a 2017
desktop. Pick a VPS or dedicated server that names the CPU model, with 16 GB of RAM, NVMe and a US West or
central location (the group plays evenings Pacific). Debian 12 or Ubuntu 24.04.

Running now (since October 2026): a Reizor Hosting "Ryzen 9 9950X VPS 16GB" in Dallas (2 dedicated threads,
16 GB, 200 GB NVMe, $45 a month), Debian 12, set up with the steps below.

## Set up (once)

1. **User and Docker.** As root: install Docker Engine with the compose plugin, `git`, `rsync` and `curl`;
   `adduser --disabled-password realms`; `usermod -aG docker realms`; `mkdir -p /srv/realms && chown realms: /srv/realms`.
2. **Firewall.** Open 25565/tcp (game), 24454/udp (voice chat), and 80/tcp, 443/tcp and 443/udp for Caddy,
   which serves the live map over HTTPS (step 9). Don't open 8100: BlueMap is published on 127.0.0.1 only
   (`MAP_PORT` in step 5), because ports Docker publishes skip ufw's rules, so ufw alone could not keep it
   private. Keep SSH key-only. RCON (25575) stays unpublished (compose.yaml).
3. **Clone with a read-only deploy key.** As `realms`: `ssh-keygen -t ed25519 -f ~/.ssh/realms_deploy -N ''`,
   add the `.pub` file as a read-only deploy key in the repo settings on GitHub, then trust GitHub's host
   key as GitHub publishes it (fingerprint `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU` in its docs)
   rather than whatever key the network answers with, and clone:
   ```sh
   printf 'Host github.com\n  IdentityFile ~/.ssh/realms_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config
   echo 'github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl' >> ~/.ssh/known_hosts
   git clone git@github.com:gr8monk3ys/monkey-smp-server.git /srv/realms/repo
   ```
4. **Settings.** Back on your admin account (`realms` has no sudo): `sudo cp /srv/realms/repo/deploy/realms-deploy.env.example /etc/realms-deploy.env`, edit
   it (the Discord webhook is optional; `DEPLOY_WINDOW` is when updates may go live), then
   `sudo chown root:realms /etc/realms-deploy.env && sudo chmod 640 /etc/realms-deploy.env` (the deploy
   service runs as `realms`, so it has to be able to read the file).
5. **First deploy.** As `realms` (`sudo -iu realms`): `sh /srv/realms/repo/deploy/realms-deploy.sh` copies the release folder to
   `/srv/realms/TheRealms-Server` and stops, asking for `docker/.env`: copy `.env.example` to `.env`
   there, set `EULA=TRUE`, `OWNER=<your Minecraft name>`, `MEMORY_GB=10`, `TZ=America/Los_Angeles` and
   `MAP_PORT=127.0.0.1:8100` (the map is reached through Caddy, step 9).
   To keep an existing world, copy its `server` folder into `/srv/realms/TheRealms-Server/` now. Run the
   script again: it downloads about 500 MB, starts the server and records the deployed commit.
6. **Pre-generate the world** before anyone joins: exploring new land costs far more tick time than
   anything else. Leave the border alone: the `realms-rules` pack sets Season I's starting border (2500
   wide, 312.5 in the Nether, centred on spawn) and the border acts in docs/SEASONS.md grow it by hand.
   Generate out to the season's largest border (6000) plus the view distance. In the console:
   `chunky worldborder` (centres Chunky on the border, not on 0,0), `chunky radius 3200` and `chunky start`
   (hours). The Nether is 1/8 the size: `chunky world minecraft:the_nether`, `chunky worldborder`,
   `chunky radius 500` and `chunky start`. It carries on after a restart because the default
   `config/chunky/config.json` sets `continueOnRestart`; on a server set up before that, set it to `true`
   in that file once and run `chunky continue`.
7. **Timers.** `sudo cp /srv/realms/repo/deploy/realms-deploy.{service,timer} /etc/systemd/system/`,
   `sudo systemctl daemon-reload && sudo systemctl enable --now realms-deploy.timer`. Then
   `sudo sh /srv/realms/repo/deploy/realms-day.sh --install` for the day timer, which counts "days played" for
   the wardrobe (docs/RETENTION.md) at midnight UTC (`--check` shows what it sends and whether it runs). Then
   `sudo sh /srv/realms/repo/deploy/realms-week.sh --install` for the week timer: every hour it tells the
   server which weekly challenge week it is and keeps Season I's launch weekend on the wall clock
   (docs/ADMIN.md, "Weekly challenges"). `sh /srv/realms/repo/deploy/realms-week.sh --check` shows what it
   sends and whether it runs. Then `sudo sh /srv/realms/repo/deploy/realms-drops.sh --install` for the
   weeknight supply drops (docs/ADMIN.md, "Supply drops"), and place the spawn NPCs once the server is up
   (docs/ADMIN.md, "Spawn NPCs").
8. **DNS** (Cloudflare, which holds the lscaturchio.xyz zone): an `A` record `play.monkeysmp` to the VPS
   address with the proxy off ("DNS only": Cloudflare's proxy carries only web traffic), and an `SRV` record `_minecraft._tcp.monkeysmp` with priority 0, weight 5, port 25565, target
   `play.monkeysmp.lscaturchio.xyz`, TTL 60. Players then type `monkeysmp.lscaturchio.xyz` with no
   port, while the same name serves the website. Voice chat finds the server by itself. For the map, an `A`
   record `map.monkeysmp` to the same address, also "DNS only": Caddy gets the certificate itself. The zone has
   a wildcard record that sends any other name to Vercel, so without its own record the map name lands there.
9. **The live map over HTTPS** (after step 8, so Let's Encrypt can reach the VPS by name). As root, install
   Caddy from its apt repository (https://caddyserver.com/docs/install), put this in `/etc/caddy/Caddyfile`
   and run `systemctl reload caddy`:
   ```
   map.monkeysmp.lscaturchio.xyz {
   	encode zstd gzip
   	reverse_proxy 127.0.0.1:8100
   }
   ```
   Caddy gets and renews the certificate and redirects `http://` to `https://`. The site's `MAP_URL` links
   there. Then fit the map to the border (docs/ADMIN.md, "The live map"): before the first fit the map
   shows everything Chunky generated, which is land the border acts haven't opened yet.
   Caddy rather than Cloudflare's proxy: the proxy would hide the address, but the game's own record shows
   it anyway, and it would need an Origin Rule for port 8100 plus a firewall list of Cloudflare's address
   ranges kept up to date by hand.
10. **Off-site backups**: see "Set up the off-site copy" under "Backups off the machine" below.

## Day to day

| Do this | How (on the VPS, as `realms`) |
|---|---|
| Ship a change | merge to `main`, then tag a release as in docs/MAINTAINING.md. In the next deploy window (`DEPLOY_WINDOW`, 4-5 AM Pacific in the example settings) the VPS warns anyone online, backs up, updates and restarts |
| Ship it right now | `sh /srv/realms/repo/deploy/realms-deploy.sh --now` (ignores the window and skips the warning) |
| When will it go live? | `sh /srv/realms/repo/deploy/realms-deploy.sh --status`: the newest tag, what is live, and whether the window is open |
| What is live? | `sh /srv/realms/repo/deploy/realms-deploy.sh --status` |
| Deploy log | `journalctl -u realms-deploy -n 100` |
| Console | `cd /srv/realms/TheRealms-Server/docker && docker compose attach realms` (leave with Ctrl+P, Ctrl+Q) |
| A command | `docker compose exec realms realms rcon "say hi"` |
| Let a player in by hand | `docker compose exec realms realms add-player NAME` |
| Grow the border (a border act) | `docker compose exec realms realms rcon "worldborder set 4000 600"` and `... "execute in minecraft:the_nether run worldborder set 500 600"`, then fit the map to it: docs/ADMIN.md, "The live map" |
| Store or staff grants (wardrobe) | `docker compose exec realms realms rcon "scoreboard players set NAME rw.tier 2"`; the full list is in docs/RETENTION.md |
| Retention numbers | `python3 /srv/realms/repo/tools/retention.py /srv/realms/TheRealms-Server/server/logs` |
| Joins per join address | `python3 /srv/realms/repo/tools/join_addresses.py /srv/realms/TheRealms-Server/server/logs` (docs/PROMOTION.md) |
| This week's standings so far | `sh /srv/realms/repo/deploy/realms-standings.sh show` (changes nothing); log: `journalctl -u realms-standings -u realms-standings-board -n 50` |
| The Sunday recap, as it would post now | `sh /srv/realms/repo/deploy/realms-standings.sh preview` (changes nothing) |
| Backup log (as root) | `journalctl -u realms-backup -n 50` |
| Off-site snapshots (as root) | `sh /srv/realms/repo/deploy/realms-backup.sh --restic snapshots` |

If a new release doesn't answer within `BOOT_TIMEOUT`, the script puts the previous release back, restarts
it, posts to Discord, and skips the failed commit until a newer one appears. The world backup it took
before the update is the newest folder in `backups/`.

## One-off steps when upgrading

A deploy never overwrites files in `server/`, and a new default config only reaches a server that doesn't have
that file yet. When a release changes a default the live server already has, its steps are here. They work
before or after the release goes live.

For 2.5.0, `deploy/upgrade-2.5.0.sh` does the two sections below (Distant Horizons; the short rules, ServerCore
and claims) with a single restart, then the spawn claim, python3 and the two timers ("Monitoring, the daily
restart and the update check"). It skips whatever is already done, so it is safe to run again. Run it as root
once 2.5.0 is live, `--check` first (it says what is left and changes nothing). Under `systemd-run` it carries on
if SSH drops while the server is stopped:

```sh
sudo sh /srv/realms/repo/deploy/upgrade-2.5.0.sh --check
sudo systemd-run --unit=realms-upgrade --collect -p TimeoutStopSec=20min sh /srv/realms/repo/deploy/upgrade-2.5.0.sh
journalctl -fu realms-upgrade
```

It warns players online `WARN_MINUTES` (5) and 1 minute ahead (`--now` skips that), stops the server for about
3 minutes, keeps the old files (`DistantHorizons.toml.before-2.5.0`, the others `.pre-onboarding`) and starts the
server again whatever happens. A setting it can't find (a mod renamed it) is left for you, with the rest done.
It reads no secrets from `/etc/realms-deploy.env` and of `server.properties` only the `enable-code-of-conduct`
line; its log is `/var/log/realms-upgrade-2.5.0.log`. The off-site backups stay a manual step ("Backups off the
machine"): they need keys the owner makes.

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

As `realms` (`sudo -iu realms`), in `/srv/realms/TheRealms-Server/docker` (`realms rcon` is short for
`docker compose exec realms realms rcon`), and the two `systemctl` lines on your admin account:

1. Let 2.8.0 deploy as usual. The deploy backs the world up first, so the newest folder in `../backups/` from
   before the update is the old world as 2.7.0 left it. Keep it out of the rotation:
   `mkdir -p /srv/realms/seasons/pre-season && cp -a ../backups/<that folder> /srv/realms/seasons/pre-season/backup-2.7`.
   The off-site backups copy `backups/` only, so add `/srv/realms/seasons` to that job or keep a copy by hand.
2. Pause deploys: `sudo systemctl stop realms-deploy.timer`.
3. Warn and stop: `realms rcon "say The server restarts in 1 minute for the new world."`, wait a minute,
   `docker compose stop`.
4. Move the old world aside (keep it): `mv ../server/world /srv/realms/seasons/pre-season/world`. Then put
   2.8.0's short rules in place (they quote rules 44 to 46, and the server keeps its own copy, so an update
   doesn't replace it): `cp ../realms/defaults/codeofconduct/en_us.txt ../server/codeofconduct/en_us.txt`.
   Everyone accepts them on their first join.
5. Carry the wardrobe over, before the first start:

   ```sh
   python3 /srv/realms/repo/tools/season.py carry /srv/realms/seasons/pre-season/world \
       --into /srv/realms/TheRealms-Server/server/world --season 1
   ```

   `--season 1`: it's still Season I, so everyone who plays stays a founder and Founder's Circlet still opens
   at launch.
6. Keep the seed: `level-seed` in `../server/server.properties` stays, so the land is the same, now with the
   new structures. A new seed is the owners' call; it stays as secret as the old one (docs/ADMIN.md, "World
   generation").
7. Start: `docker compose up -d`. The installer adds the data packs, the rules pack sets the starting border
   (2500 wide, 312.5 in the Nether) and keeps the End closed, and the console says "Carried N players' wardrobe
   scores and K teams into season 1."
8. Check:

   ```sh
   realms rcon "scoreboard players get #carried rw.day"     # 1
   realms rcon "scoreboard players get #season rw.day"      # 1
   realms rcon "scoreboard players get NAME rw.tier"        # a supporter: the same as in the old world
   realms rcon "gamerule keep_inventory"                    # false
   realms rcon "worldborder get"                            # 2500
   grep -o 'nova_structures:' ../server/config/enchantmentdisabler/config.toml | wc -l   # 17 (rule B18)
   grep -E '^(reset_time_value|reset_time_unit|only_reset_when_empty)=' ../server/lootrestock.properties   # 7, days, true
   ```

   The last two are the new 2.8.0 configs, copied because the live server didn't have them (docs/ADMIN.md,
   "Mod settings").
9. The no-PvP spawn claim, as in docs/RULES.md (rule 26):
   `realms rcon "opac server-claims-config set claims.protection.exceptions.playersByPlayers false"`, then
   `realms rcon "oclaims server claim in minecraft:overworld ~-48 ~-48 ~48 ~48"`.
10. Pre-generate as on the first setup (step 6 above): `realms rcon "chunky worldborder"`,
    `realms rcon "chunky radius 3200"`, `realms rcon "chunky start"`; the Nether with
    `realms rcon "chunky world minecraft:the_nether"`, `"chunky worldborder"`, `"chunky radius 500"`,
    `"chunky start"`. The End has no border, so give it a centre:
    `realms rcon "chunky world minecraft:the_end"`, `"chunky center 0 0"`, `"chunky radius 2000"`,
    `"chunky start"` (on a test server, End cities and Qrafty's villages were 400 to 2000 blocks out).
    `realms rcon "chunky progress"` shows how far it is.
11. Clear the old world off the live map: `realms rcon "bluemap purge world"`, and the same for
    `world_the_nether` and `world_the_end` (if one says "BlueMap is still loading", run it again a few
    seconds later). The map's border masks are config, not world: they still fit Season I's start.
12. In game, as an op at spawn: `/function realms:npcs/guide/here` and `/function realms:npcs/crier/here` where
    each should stand, and `/function realms:standings/place` for the board (docs/ADMIN.md, "Spawn NPCs" and
    "Weekly standings and bounties").
13. Turn deploys back on: `sudo systemctl start realms-deploy.timer` (unless the launch freeze has started:
    docs/LAUNCH.md).

The week, day, drops and standings timers need nothing: they find the world by its path and talk over RCON,
so a run during the switch just fails and the next one works. Within the hour `realms-week.timer` tells the new
world the challenge week. The launch itself is unchanged: `function realms:rules/launch` at 5 PM on the day.
The old world stays in `/srv/realms/seasons/pre-season/`: to go back to it, stop the server, move the new
`world` aside and move the old one back (`backup-2.7` is the same world before 2.8.0 touched it).

### The weekly challenges' timer (the release with the weekly challenges)

Once that release is live, install `realms-week.timer` from the deployed checkout. It is safe to run again
(it copies only units that changed), and `--check` says what it would send and changes nothing:

```sh
sh /srv/realms/repo/deploy/realms-week.sh --check
sudo sh /srv/realms/repo/deploy/realms-week.sh --install
```

Do it before the launch (Saturday 31 October 2026, 5 PM Pacific): without the timer the challenge week never
turns over, and the launch weekend's window ends on game time alone, which stops while the server is empty.
It needs python3 3.10 or newer (`deploy/upgrade-2.5.0.sh` installs it) and reads only `REPO_DIR` and
`LIVE_DIR` from `/etc/realms-deploy.env`.

### The supply drops' timer (the release with supply drops)

Once that release is live, install `realms-drops.timer` the same way (`docs/ADMIN.md`, "Supply drops"):

```sh
sh /srv/realms/repo/deploy/realms-drops.sh --check
sudo sh /srv/realms/repo/deploy/realms-drops.sh --install
```

It runs every 10 minutes as `realms`, sends nothing outside Monday to Thursday, 6 to 10 PM Pacific, and
reads only `REPO_DIR` and `LIVE_DIR` from `/etc/realms-deploy.env`, plus the saved claims and border from
the world. Without it there are no automatic drops; staff can still start one by hand.

### The outposts' timer (the release with outposts)

Once that release is live, install `realms-outposts.timer` the same way (`docs/ADMIN.md`, "Outposts"):

```sh
sh /srv/realms/repo/deploy/realms-outposts.sh --check
sudo sh /srv/realms/repo/deploy/realms-outposts.sh --install
```

It runs every hour at 45 past as `realms`, sends nothing before the launch or when every outpost has its
spot, and reads only `REPO_DIR` and `LIVE_DIR` from `/etc/realms-deploy.env`, plus the saved claims, border,
scores and storage from the world. It also writes the "Outposts" marker set into the Overworld map's config
under `server/config/bluemap/maps/` and sends `bluemap reload` when that changed. Without the timer there
are no outposts: the pack waits for spots.

### The omens' timer (the release with omens)

Once that release is live, install `realms-omens.timer` the same way (`docs/ADMIN.md`, "Omens"):

```sh
sh /srv/realms/repo/deploy/realms-omens.sh --check
sudo sh /srv/realms/repo/deploy/realms-omens.sh --install
```

It runs every 10 minutes (5 minutes after the drops' timer) as `realms`, sends nothing outside an omen
evening (two weekday evenings a week, from a start between 6:00 and 8:50 PM until 10 PM Pacific), and reads
only `REPO_DIR` and `LIVE_DIR` from `/etc/realms-deploy.env`, plus the saved scoreboard, claims and border
from the world. `--check` doesn't show the week's plan. Without the timer there are no automatic omens;
staff can still start one by hand.

### The news timer (the release with Monkey SMP news)

Monkey SMP news posts one plain line to the public channel for a rare first, the first finish of a rare
challenge or a new faction (`docs/ADMIN.md`, "Monkey SMP news"). Once that release is live:

1. In Discord, open the channel (#monkey-smp) > Edit Channel > Integrations > Webhooks > New Webhook, name it
   Monkey SMP, and Copy Webhook URL. It may be the standings' webhook if that already posts there.
2. Put it in the settings file, which stays root:realms, mode 640 (`sudo nano /etc/realms-deploy.env`):
   `NEWS_WEBHOOK_URL=https://discord.com/api/webhooks/...`. Nowhere else: never in git, a ticket or chat.
3. Install the timer and look at what it would post:

```sh
sudo sh /srv/realms/repo/deploy/realms-news.sh --install
sh /srv/realms/repo/deploy/realms-news.sh --check
```

It runs every 10 minutes (2 minutes past, clear of the drops and omens) as `realms`, reads `REPO_DIR`,
`LIVE_DIR`, `LOCK_FILE`, `NEWS_DIR` (default `/srv/realms/news`) and `NEWS_WEBHOOK_URL` from
`/etc/realms-deploy.env`, and only the saved world (no RCON). `--check` says whether the webhook is set, never
its value. Install it, webhook set, before the launch, so launch night posts: nothing posts before
`realms:rules/launch`, and the runs before it are what date the launch (no calendar date is used). A season
whose first launched run had no run in the 3 hours before it (the webhook added mid-season), or a gap of more
than 3 hours between runs (the webhook emptied for a while, the VPS down), keeps what turned up meanwhile as
baseline and posts only what is new after it. To stop it, empty `NEWS_WEBHOOK_URL` (or
`sudo systemctl disable --now realms-news.timer`). A new season needs nothing as long as the webhook stays set
across it: a new world is a new `season-<n>.json` in `NEWS_DIR`, so every first is news again.

### The day timer as a job (the release with `deploy/realms-day.sh`)

The week, drops, omens and day timers are timed jobs (GLOSSARY.md): one runner in `deploy/lib.sh` takes the deploy
lock and reads each answer for a refusal. Before this release `realms-day.service` ran `docker compose ... rcon`
itself, without either. It now sends `function realms:wardrobe/day_once {stamp:YYYYMMDD}`, the UTC date, and the
wardrobe pack starts one day per date, so a retry after a run that reached the server never counts a second day.
Once the release is live (its wardrobe pack has `day_once`), replace the unit from the deployed checkout (it
copies only the units that changed, and restarting the timer doesn't start a new day):

```sh
sh /srv/realms/repo/deploy/realms-day.sh --check
sudo sh /srv/realms/repo/deploy/realms-day.sh --install
```

Until then the old unit keeps working: it runs `function realms:wardrobe/day`, which the release keeps (staff can
run it for an extra day). Like the old one, the new one tries again every 10 minutes while the server is down; it
now also does when the server turns the command down (say, the wardrobe pack is off). It gives up after 6 hours
of tries: it posts to the staff channel and stops, and the next midnight's run starts afresh. `journalctl -u
realms-day` shows each try; to start the given-up day later, run `sh /srv/realms/repo/deploy/realms-day.sh` as
`realms` (by hand it has no limit, and a date already started is left alone).

### The spawn NPCs (the release with spawn NPCs)

The release adds the `realms-npcs` data pack but places no one. Once it is live, an op places the Guide and
the Town Crier at spawn once, in game: `/function realms:npcs/guide/here` and `/function realms:npcs/crier/here`
where each should stand (docs/ADMIN.md, "Spawn NPCs"). Until then there are no NPCs at spawn. Place them again
after a release that changes their text.

### Distant Horizons stops sending its own LODs (the release after 2.4.2)

The live `DistantHorizons.toml` was written by Distant Horizons on the first start, with server-side LODs on,
and those carry the real ores ("Distant Horizons and x-ray" in docs/ADMIN.md). Turn them off with the server
stopped, so Distant Horizons can't write over the change. As `realms` (`sudo -iu realms`):

```sh
cd /srv/realms/TheRealms-Server/docker
exec 9>/tmp/realms-deploy.lock && flock 9    # the deploy lock (LOCK_FILE in /etc/realms-deploy.env): no deploy or backup starts meanwhile
docker compose stop realms
f=/srv/realms/TheRealms-Server/server/config/DistantHorizons.toml
cp "$f" "$f.bak"
sed -i -e 's/^\([[:space:]]*synchronizeOnLoad[[:space:]]*=\).*/\1 false/' \
       -e 's/^\([[:space:]]*enableRealTimeUpdates[[:space:]]*=\).*/\1 false/' \
       -e 's/^\([[:space:]]*generatorPlan[[:space:]]*=\).*/\1 "DISABLED"/' "$f"
grep -nE '^[[:space:]]*(synchronizeOnLoad|enableRealTimeUpdates|generatorPlan)[[:space:]]*=' "$f"
docker compose start realms
exec 9>&-                                    # let deploys and backups run again
```

The `grep` must print three lines ending in `false`, `false` and `"DISABLED"`. If it prints fewer, a newer
Distant Horizons has renamed a key: find it in the file (its comments say what each setting does) and set it
by hand, with the server stopped again. LODs players already received before the change stay on their
computers; from now on they only get LODs of land they walk past.

### The short rules, ServerCore and claims (the release after 2.4.2)

The release brings the short rules (`server/codeofconduct/en_us.txt`, a new file), but the live server keeps its
own copies of three files, so four settings in them stay off: the Code of Conduct (`server.properties`), ServerCore's
breeding cap and villager lobotomization (`config/servercore/config.yml`) and Open Parties and Claims' 4 chunks per
player (`config/openpartiesandclaims-server.toml`). Spawn's no-PvP claim belongs to the world, so it's made from the
console. Do this after the release is live: `ls /srv/realms/TheRealms-Server/server/codeofconduct/en_us.txt` must
list the file. Then, as `realms` (`sudo -iu realms`):

```sh
cd /srv/realms/TheRealms-Server/docker
exec 9>/tmp/realms-deploy.lock && flock 9    # the deploy lock, as above
S=/srv/realms/TheRealms-Server/server
P=$S/server.properties C=$S/config/servercore/config.yml O=$S/config/openpartiesandclaims-server.toml
docker compose exec -T realms realms rcon "say The server restarts in 1 minute for a settings update." && sleep 60
docker compose stop realms
for f in "$P" "$C" "$O"; do [ -e "$f.pre-onboarding" ] || cp -p "$f" "$f.pre-onboarding"; done   # once
grep -q '^enable-code-of-conduct=' "$P" || echo 'enable-code-of-conduct=true' >> "$P"
sed -i 's/^enable-code-of-conduct=.*/enable-code-of-conduct=true/' "$P"
awk '$1 == "lobotomize-villagers:" || $1 == "breeding-cap:" { f = 1; print; next }
     f && $1 == "enabled:" { sub(/enabled:.*/, "enabled: true"); f = 0 } { print }' "$C" > "$C.new"
cat "$C.new" > "$C" && rm "$C.new"
sed -i 's/^\([[:space:]]*maxPlayerClaims[[:space:]]*=\).*/\1 4/' "$O"
grep -h -E '^enable-code-of-conduct=|^[[:space:]]*maxPlayerClaims[[:space:]]*=' "$P" "$O"
grep -A2 -E '^[[:space:]]*(lobotomize-villagers|breeding-cap):' "$C" | grep 'enabled:'
docker compose start realms
until docker compose exec -T realms realms rcon list >/dev/null 2>&1; do sleep 10; done
docker compose exec -T realms realms rcon "opac server-claims-config set claims.protection.exceptions.playersByPlayers false"
docker compose exec -T realms realms rcon "oclaims server claim in minecraft:overworld ~-48 ~-48 ~48 ~48"
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
sudo sh /srv/realms/repo/deploy/shops-claims.sh --check
sudo systemd-run --unit=realms-shops --collect -p TimeoutStopSec=20min sh /srv/realms/repo/deploy/shops-claims.sh
journalctl -fu realms-shops
```

Like `upgrade-2.5.0.sh` it warns players online (`--now` skips that), takes the deploy lock, stops the server for
about 3 minutes, keeps the old file as `openpartiesandclaims-server.toml.before-shops`, and starts the server
again whatever happens; its log is `/var/log/realms-shops-claims.log`. It prints only the
`forcedBlockProtectionExceptionList` line. If that list is missing or spread over several lines, it changes
nothing and says so: add the entry by hand with the server stopped, as in the section above.

## Backups off the machine

`backups/` is on the same disk as the world, so a dead disk or a lost VPS takes both. So every hour the VPS
also sends the live server folder, encrypted, to a Cloudflare R2 bucket with [restic](https://restic.net).
`realms-backup.timer` runs `deploy/realms-backup.sh` on the hour:

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

When backups fail, or the server hasn't answered for 3 hours, it posts to the Discord webhook in
`/etc/realms-deploy.env`, once, and again when they work. A deploy still backs up into `backups/` before it
updates, and keeps the newest 3 there (`KEEP_BACKUPS` in `/etc/realms-deploy.env`): R2 holds the history.

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
   `/etc/realms-backup.env` with it, leaving the bucket unreadable. Lost R2 keys can be made again; a lost
   password can't.
3. **restic and the settings**, on the VPS as root. restic 0.19.1 from its release (Debian 12's package is
   0.14, too old for the restore commands below; `apt install bzip2` if `bunzip2` is missing):
   ```sh
   curl -fsSLO https://github.com/restic/restic/releases/download/v0.19.1/restic_0.19.1_linux_amd64.bz2
   echo 'f415415624dcc452f2a02b8c33641791a8c6d6d3b65bbb3543fcf9a25151585c  restic_0.19.1_linux_amd64.bz2' | sha256sum -c
   bunzip2 restic_0.19.1_linux_amd64.bz2 && install -m 755 restic_0.19.1_linux_amd64 /usr/local/bin/restic
   install -m 600 -o root -g root /srv/realms/repo/deploy/realms-backup.env.example /etc/realms-backup.env
   nano /etc/realms-backup.env
   ```
   Type the address (as `s3:https://...`), the two keys and the password into the file. It stays root-only:
   never copy the values into the repo or a chat.
4. **The unit, the first backup and the timer:**
   ```sh
   cp /srv/realms/repo/deploy/realms-backup.{service,timer} /etc/systemd/system/ && systemctl daemon-reload
   sh /srv/realms/repo/deploy/realms-backup.sh --init
   systemctl start realms-backup
   systemctl enable --now realms-backup.timer
   ```
   `--init` creates the repository in the bucket. The first backup sends the whole server folder, so the
   server doesn't save until it is done (players can keep playing); later ones send only the changes.
   `/srv/realms/repo` is checked out at the live release, so these files arrive with the first release that
   has them (or `git checkout --detach origin/main` there as `realms`: the deploy script decides what is
   live from its own record, not from that checkout).
5. **Put the monthly restore drill (below) in your calendar.**

The VPS's token can delete (pruning needs to), so the bucket doesn't guard against someone who takes over the
VPS. For that, now and then copy a drill's restored `server` folder (below) to a disk at home before
deleting it.

### Restore

Every snapshot holds the server folder at its path on the VPS, `/srv/realms/TheRealms-Server/server`.
Restoring `latest:/srv/realms/TheRealms-Server/server` gives the newest one; `--restic snapshots` lists the
others by ID and time, and `<ID>:/srv/realms/TheRealms-Server/server` restores one of them. On the VPS the
script reads the keys from the settings file, so none go on the command line.

**On the VPS** (the world broke, or a mistake needs undoing), as root:

```sh
sh /srv/realms/repo/deploy/realms-backup.sh --restic restore latest:/srv/realms/TheRealms-Server/server --target /srv/realms/restore
cd /srv/realms/TheRealms-Server/docker && docker compose stop
mv ../server/world ../server/world.before-restore && mv /srv/realms/restore/world ../server/world
chown -R realms: ../server/world && docker compose up -d
```

Only the world goes back. The whitelist, bans, LuckPerms and the mods stay as they are, so nobody who paid
since then loses access. The last 3 deploys' backups are also in `backups/`, with no download: move
`../backups/<time>/world` in instead. Delete `world.before-restore` and `/srv/realms/restore` once the server
is fine.

**On a new VPS**: set it up as in "Set up (once)" above. In step 5, before running the deploy script the
second time, do steps 2 and 3 of the off-site setup with the values from your password manager, then
`sh /srv/realms/repo/deploy/realms-backup.sh --restic restore latest:/srv/realms/TheRealms-Server/server --target /srv/realms/TheRealms-Server/server`
and `chown -R realms: /srv/realms/TheRealms-Server/server`. Then run the deploy script, download the Tebex
jar into `server/mods` again (backups leave jars out; see "Payments and Discord"), and finish with step 4
of the off-site setup. The new VPS carries on the same series of snapshots.

### Monthly restore drill (home PC)

Once a month, restore the newest snapshot onto the home PC and start it there. It proves the backups can be
read and the world loads, and it rehearses the playit.gg fallback below, which starts the same way.

1. **Make room.** Stop any other Minecraft server on the PC first, test servers included: two servers fight
   over BlueMap's port 8100, and the one that loses shuts down. Check that about 12 GB of memory is free.
2. **The release.** Download the zip of the release that is live (`realms-deploy.sh --status` on the VPS)
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
   C:\Tools\restic\restic.exe snapshots --latest 1
   C:\Tools\restic\restic.exe restore latest:/srv/realms/TheRealms-Server/server --target server
   ```
   The newest snapshot should be from the last hour or two.
5. **Start it** with `Start Server.bat`. Backups leave the jars out, so the first start downloads Java,
   Fabric and the mods (about 500 MB), then loads the restored world. Leave the Tebex jar out on a drill:
   with it, this copy would carry out store purchases meant for the VPS.
6. **Join it** through playit.gg: start the agent and join its tunnel address (not `monkeysmp.lscaturchio.xyz`:
   DNS stays on the VPS during a drill). Your base should be there as it was at the snapshot's time.
7. **Stop it and delete the folder.** It is a copy: nothing done on it counts. Note the date and what
   failed, if anything; a failed drill is the cheap time to find out.

## Fallback: home PC on playit.gg

When the VPS or its provider is down for longer than a restart:

1. On the home PC, do steps 1 to 5 of the restore drill above, in a folder you keep, and put the Tebex jar
   into `server\mods` this time (see "Payments and Discord").
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
  reverse on expiry, is in docs/RETENTION.md). The monthly pass renews until the buyer cancels it from
  Tebex's payment history page; after 3 failed renewals it expires and the expiry commands run. Tebex's
  Fabric mod (2.4.6) is built for 26.2 but loads on 26.3 (checked on the live server, October 2026). It sits
  in `server/mods` as an extra jar, which deploys and the installer leave alone. Backups leave every jar
  out, so after restoring one (or on the fallback below) download it again:
  `https://cdn.modrinth.com/data/nRA0jiJt/versions/qg7SxggJ/tebex-fabric-26.2-2.4.6-0096441.jar`. Once
  there is a 26.3 build it can go into the manifest with `tools/add.py`, and then it comes back by itself.
- **Discord**: Tebex's Discord integration gives buyers the paid role. The forum, announcements, ban
  appeals and the `realms` bridge live in the Discord server repo (gr8monk3ys/discord-server). The bridge
  talks RCON, which is plain text: reach the VPS over Tailscale or WireGuard, never by publishing 25575.

### The store (set up once, before the first sale)

Status (2026-10-28): the Tebex project "Monkey SMP" is set up and connected to the live server. Delivery
(`tebex secret` in the console), the Server Pass package, the support contact, the payout wallet and the
storefront are all done. It went to Tebex for review on 2026-10-27, which Tebex says takes up to 2 working days.
Until it is approved, checkout takes only test payments and the public store address isn't known.
`monkeysmp.tebex.io` belongs to another server, so read the address off the Tebex panel once the store is live.
Then make a test purchase, check that the buyer is on the whitelist (the server log shows Tebex's command), and
only after that fill in `STORE_URL` (below). If Tebex's review asked for package changes, check the prices
and terms against the table below before the first real sale.

Tebex can't change the price of a subscription already sold, so set these before the store link goes on
the site (the reasons are in docs/adr/0008-pass-prices-settled-before-the-first-sale.md):

| Package | Price | Charged | Commands (docs/RETENTION.md) |
| --- | --- | --- | --- |
| Server Pass | $5 | monthly subscription | whitelist, `rw.months 1` on renewal |
| Server Pass, 3 months | $14 | once; Remove After 90 days | whitelist, `rw.months 3` |
| Ember, Banner, Crown | $3, $7, $15 | monthly subscription | `rw.tier`, `tier_*` team |

- **No priority or reserved slots, and no coupons for single people.** Mojang's rules ask for one price
  for access; a sale has to be open to everyone.
- **Free trial on the monthly pass: 7 days.** Tebex added native trials for subscription packages (1, 3,
  7, 10, 14 or 30 days; Packages > the package > Trials). It takes card details at checkout and charges
  when the trial ends; a trial on the package is the same for every buyer, so it stays within the
  one-price rule. Seven days always includes a Saturday event (docs/SEASONS.md). Tebex's docs don't say
  which commands run when a trial starts or is cancelled, so test once with a real purchase before
  switching it on for everyone: the whitelist command has to run when the trial starts, the removal when
  it is cancelled, and `rw.months` mustn't count the trial's first charge twice. If the whitelist waits for
  the first charge, leave trials off and run open-house evenings instead: the whitelist off for one
  announced evening a month with staff online, listed in docs/SEASONS.md and on the site. Once trials are
  on, add this to the site's FAQ (`site/index.html`), under "Refunds?":
  "**Can I try it first?** Yes: the monthly pass starts with 7 free days. Tebex asks for a card and charges
  the first month when the 7 days end, unless you cancel before then on its payment history page."
- **Creator codes** (Creator Codes in the Tebex panel): a 20% revenue share, no customer discount, limited
  to the 3-month pass if Tebex offers that. Tebex pays a code's share only on a subscription's first
  payment, takes 1% more on payments made with a code, and settles the creator's Tebex Wallet after 30
  working days. The public terms are `site/creators.html`; finding creators is in docs/PROMOTION.md.
- **The site.** Put the webstore's address in `STORE_URL` in `site/config.js` and run
  `python tools/site_links.py`, which writes it into the pages. Do it only once a test purchase has
  whitelisted someone: while `STORE_URL` is empty the pages say passes are arranged in the Discord and
  staff whitelist buyers by hand, and setting it switches them to the store's wording ("on the whitelist
  within a minute or two"), marked `data-store="open"` and `"soon"` in the HTML.

## Monitoring, the daily restart and the update check

| What | Runs on | Does |
|---|---|---|
| Uptime Kuma | the home PC (fleet repo, `services/uptime-kuma.md`) | every minute: a Minecraft status ping to `monkeysmp.lscaturchio.xyz` (through the SRV record, as players connect) and an HTTP check of the live map; alerts in a Discord channel; quiet 4-5 AM Pacific, when deploys and the daily restart happen |
| `realms-restart.timer` | the VPS | restarts the server at 4:30 AM Pacific and posts a spark health link |
| `realms-updates.timer` | the VPS | Mondays at 10 AM Pacific: lists newer builds of what the live release pins |
| `realms-standings.timer` | the VPS | Sundays at 7 PM Pacific: closes the week's faction standings and posts them (below) |
| `realms-standings-board.timer` | the VPS | every hour at :20: puts this week so far on the in-game board |
| `realms-news.timer` | the VPS | every 10 minutes: Monkey SMP news to the public channel, a few lines a week ("The news timer") |

Uptime Kuma runs on the home PC because a monitor on the VPS goes down with the VPS, and the home PC is on all
the time anyway. The update check runs on the VPS rather than the home PC: it uses the webhook that is already
in `/etc/realms-deploy.env` (no second copy of it), and it checks the release that is actually live.

Install the two timers once the release after 2.4.1 is live (they run from the deployed checkout):

```sh
sudo apt-get install -y python3    # the update check runs tools/check_updates.py (3.10 or newer)
sudo cp /srv/realms/repo/deploy/realms-{restart,updates}.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now realms-restart.timer realms-updates.timer
```

Both post to `STAFF_WEBHOOK_URL` in `/etc/realms-deploy.env` when it is set (a staff-only channel), and to
`DISCORD_WEBHOOK_URL` otherwise.

**The daily restart** keeps memory from creeping up over days of uptime (Distant Horizons, BlueMap and mod
caches). It runs inside the deploy window but after the deploy check: when a release went live that morning,
the server is younger than `RESTART_MIN_UPTIME` hours (6) and the restart skips. It waits up to 30 minutes for
the deploy lock, so it never overlaps a deploy or an off-site backup. It warns anyone online 5 minutes and 1
minute ahead, like a deploy, takes `spark health` just before stopping, and posts "back up (had been up N h)"
with that link. If memory use in those reports keeps climbing from day to day, something leaks and the
restart only hides it. Log: `journalctl -u realms-restart -n 50`. To restart now as the timer would, as
`realms`: `RESTART_MIN_UPTIME=0 sh /srv/realms/repo/deploy/realms-deploy.sh --restart`.

**The weekly update check** runs `tools/check_updates.py` against the live release, since the GitHub Actions
check can't run in this private repo. It posts every Monday, with the report attached when there is anything
newer, so a Monday without a post means the timer is broken. It changes nothing: taking an update is still
`check_updates.py --apply` on a PC, the smoke test and a release (docs/MAINTAINING.md). Run it now with
`sudo systemctl start realms-updates`; log: `journalctl -u realms-updates`.

**The weekly standings** (docs/SEASONS.md, "Weekly standings") run `tools/standings.py` from the deployed
checkout, through `deploy/realms-standings.sh`, as `realms`. They read the world's saved files (parties,
claims, scoreboard) and send only the board's text to the game, over RCON through the container. Set them up
once a release with them is live and the server has started on it, as root, `--check` first:

```sh
sudo sh /srv/realms/repo/deploy/install-standings.sh --check
sudo sh /srv/realms/repo/deploy/install-standings.sh
```

It skips whatever is already done: python3 (3.11 or newer), a check that the `realms-standings` data pack is
on, the folder the weeks are kept in (`STANDINGS_DIR`, default `/srv/realms/standings`), the first week's
snapshot, and the two timers. Two things stay by hand:

- The channel: `STANDINGS_WEBHOOK_URL` in `/etc/realms-deploy.env`, a public channel such as `#monkey-smp`.
  Empty, the post goes to `DISCORD_WEBHOOK_URL`. The webhook is never printed or logged.
- The board: an op stands at spawn and runs `/function realms:standings/place` (docs/ADMIN.md).

On Sunday at 7 PM Pacific the timer closes the week: it keeps the final table in
`STANDINGS_DIR/weeks/<date>.json`, starts the next week from a new snapshot, puts both on the board, announces
it in chat and posts it to Discord as the Sunday recap ("Monkey SMP Weekly": the table and a few lines on the
week, worked out at the close and kept in the same file). Before the launch (`function realms:rules/launch`
sets `#launched rw.day`) it keeps the week but posts nothing. It waits up to 30 minutes for the deploy lock, so it never runs during a
deploy, the daily restart or an off-site backup. If the board or Discord fails, the service fails and systemd
tries again every 10 minutes for 2 hours; a retry finishes what is left and never closes the week twice (a
week closes only when it is at least 3 days old). The hourly board update skips its turn when the lock is
busy. To run the Sunday job now (it still closes only a week at least 3 days old):
`sudo systemctl start realms-standings`; log: `journalctl -u realms-standings -n 50`.

## Load test

The player table in docs/ADMIN.md was measured on an i7-8700K with nothing else running. The VPS core is
faster, but it has only two threads, shared by the game thread, C2ME's chunk workers, Distant Horizons'
LOD builders, BlueMap's renderer and the garbage collector, so its number has to be measured on the VPS.
`deploy/realms-loadtest.sh` runs `tools/loadtest.py` there: 25 Carpet fake players standing spread out in
generated terrain (the same test as the table), 5 minutes measured, with a spark profile of every thread.

Run it as root at a quiet time, after Chunky has finished pre-generating (it refuses before that; `FORCE=1`
overrides) and not around midnight UTC (realms-day.timer). The server is offline for about 15 minutes: the
script says so on Discord and warns anyone online. Started with `systemd-run`, it carries on if SSH drops:

```sh
systemd-run --unit=realms-loadtest --collect -p TimeoutStopSec=20min sh /srv/realms/repo/deploy/realms-loadtest.sh
journalctl -fu realms-loadtest
```

Before a release ships the script, copy `deploy/realms-loadtest.sh`, `deploy/lib.sh` (it sources it from its own folder) and `tools/loadtest.py` to `/root/` and
run `systemd-run --unit=realms-loadtest --collect -p TimeoutStopSec=20min --setenv=LOADTEST_PY=/root/loadtest.py sh /root/realms-loadtest.sh`.

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

The first run, on 2026-10-25 at 22:30 Pacific. One fake player (Load08) didn't join, so it ran with 24. The
median sample stayed at 13-31 ms: about 30 ms for a minute or two, then about 15 ms. No 10-second sample
averaged over 50 ms. The worst p95 was 74 ms and the worst p99 105 ms, with two "can't keep up" warnings.
ServerCore kept the full distances (simulation 6, view 8), so the numbers aren't flattered. **Decision:
leave it.** The run's `summary.json` and staff post hold a docs link that spark printed while stopping;
`tools/loadtest.py` now skips those. The profile link above came from the run's `server.log`.

**Decision rule.** Under about 40 ms median at 25 players, leave it: that leaves room for spikes. Above
that, change one thing at a time, in this order, and run the test again after each:

1. **Cap Distant Horizons** if its threads show up in the spark profile. In `server/config/DistantHorizons.toml`:
   `numberOfThreads = 1` and `threadRunTimeRatio = "0.5"` under `[common.multiThreading]`, and a smaller
   `maxGenerationRequestDistance` (4096 now) under `[server]`.
2. **Pause BlueMap in the evening** if it shows up. It already renders on one thread
   (`render-thread-count: 1`); `bluemap stop` over RCON pauses it and `bluemap start` resumes it.
3. **Lower `simulation-distance`** in the live `server.properties` from 6 to 5, then 4. Players still see 8
   chunks; mobs, crops and farms only run nearer. If `servercore_status` in `summary.json` shows lower
   distances than these, ServerCore's dynamic mode was already cutting them during the test because ticks
   were over 45 ms, so the real cost is higher than the number.
4. **A plan with 4 or more threads** if it is still over 40 ms.

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
2. **The real player addresses.** The Proxy Protocol Support mod (Fabric, server side only, 1.2.1 for 26.3,
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
