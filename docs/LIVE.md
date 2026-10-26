# The live server (monkeysmp.lscaturchio.xyz)

How the paid, always-on copy of Monkey SMP runs: one Linux VPS running the Docker setup from the release,
kept in step with this repo by `deploy/realms-deploy.sh`, with a home PC on playit.gg as the fallback.
The business side (prices, costs, referrals) is in the plan linked from the PR that added this file; the
public site is `site/`.

```
players --> monkeysmp.lscaturchio.xyz (SRV record) --> play.monkeysmp.lscaturchio.xyz (A) --> VPS :25565
                                                     \-> failover: SRV target swapped to the playit.gg address
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

## Set up (once)

1. **User and Docker.** As root: install Docker Engine with the compose plugin, `git`, `rsync` and `curl`;
   `adduser --disabled-password realms`; `usermod -aG docker realms`; `mkdir -p /srv/realms && chown realms: /srv/realms`.
2. **Firewall.** Open 25565/tcp (game) and 24454/udp (voice chat). Open 8100/tcp only if the live map
   should be public. Keep SSH key-only. RCON (25575) stays unpublished (compose.yaml).
3. **Clone with a read-only deploy key.** As `realms`: `ssh-keygen -t ed25519 -f ~/.ssh/realms_deploy -N ''`,
   add the `.pub` file as a read-only deploy key in the repo settings on GitHub, then
   ```sh
   printf 'Host github.com\n  IdentityFile ~/.ssh/realms_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config
   git clone git@github.com:gr8monk3ys/monkey-smp-server.git /srv/realms/repo
   ```
4. **Settings.** `sudo cp /srv/realms/repo/deploy/realms-deploy.env.example /etc/realms-deploy.env`, edit
   it (the Discord webhook is optional; `DEPLOY_WINDOW` is when updates may go live), `sudo chmod 600 /etc/realms-deploy.env`.
5. **First deploy.** `sh /srv/realms/repo/deploy/realms-deploy.sh` copies the release folder to
   `/srv/realms/TheRealms-Server` and stops, asking for `docker/.env`: copy `.env.example` to `.env`
   there, set `EULA=TRUE`, `OWNER=<your Minecraft name>`, `MEMORY_GB=10` and `TZ=America/Los_Angeles`.
   To keep an existing world, copy its `server` folder into `/srv/realms/TheRealms-Server/` now. Run the
   script again: it downloads about 500 MB, starts the server and records the deployed commit.
6. **Pre-generate the world** before anyone joins: exploring new land costs far more tick time than
   anything else. In the console: `worldborder set 12000`, then `chunky radius 6000` and `chunky start`
   (hours; it carries on after a restart). Do the Nether at a smaller radius the same way.
7. **Timers.** `sudo cp /srv/realms/repo/deploy/realms-{deploy,day}.{service,timer} /etc/systemd/system/`,
   `sudo systemctl daemon-reload && sudo systemctl enable --now realms-deploy.timer realms-day.timer`.
   The day timer counts "days played" for the wardrobe (docs/RETENTION.md) at midnight UTC.
8. **DNS** (Vercel, which holds the lscaturchio.xyz zone): an `A` record `play.monkeysmp` to the VPS
   address, and an `SRV` record `_minecraft._tcp.monkeysmp` with priority 0, weight 5, port 25565, target
   `play.monkeysmp.lscaturchio.xyz`, TTL 60. Players then type `monkeysmp.lscaturchio.xyz` with no
   port, while the same name serves the website. Voice chat finds the server by itself.
9. **Off-site backups**: see "Set up the off-site copy" under "Backups off the machine" below.

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
| Store or staff grants (wardrobe) | `docker compose exec realms realms rcon "scoreboard players set NAME rw.tier 2"`; the full list is in docs/RETENTION.md |
| Retention numbers | `python3 /srv/realms/repo/tools/retention.py /srv/realms/TheRealms-Server/server/logs` |
| Backup log (as root) | `journalctl -u realms-backup -n 50`; the monthly test: `journalctl -u realms-restore-test` |
| Off-site snapshots (as root) | `sh /srv/realms/repo/deploy/realms-backup.sh --restic snapshots` |

If a new release doesn't answer within `BOOT_TIMEOUT`, the script puts the previous release back, restarts
it, posts to Discord, and skips the failed commit until a newer one appears. The world backup it took
before the update is the newest folder in `backups/` from the deploy's time (the deploy log names it;
hourly backups land there too).

## Backups off the machine

`backups/` is on the same disk as the world, so a dead disk or a lost VPS takes both. So every hour the VPS
also sends the world, encrypted, to a Cloudflare R2 bucket with [restic](https://restic.net):

- **`realms-backup.timer`** runs `deploy/realms-backup.sh` on the hour. If the server answers, it runs
  `realms backup` in the container, the same backup a deploy takes: `save-off`, `save-all flush`, a copy of the
  world, configs and mod data to `backups/<time>` (no jars, logs, libraries, BlueMap tiles or `session.lock`),
  `save-on`; the newest 14 stay. restic then sends that copy to R2, where only what changed since the last
  hour is new. R2 keeps the last 48 hours, then one snapshot a day for 14 days, then one a week for 8 weeks
  (`KEEP_*` in the settings); old data is pruned once a day. A backup waits for a running deploy; a deploy
  check that comes during the minute of the local copy logs "another deploy is running" and goes ahead 5
  minutes later. When backups fail, or the server hasn't answered for 3 hours, it posts to the Discord
  webhook in `/etc/realms-deploy.env`, once, and again when they work.
- **`realms-restore-test.timer`** restores the newest snapshot to a temporary folder on the 1st of each month
  (3:30 AM Pacific), checks that `level.dat` and the region files are there and whole, and posts the result.

**Cost.** R2's free tier (October 2026) is 10 GB-month of storage, 1 million writes and 10 million reads a
month, with free downloads and no minimum storage time. restic keeps each piece of data once, so the bucket
holds about one copy of the world plus 8 weeks of changes: free while that stays under 10 GB, then $0.015 per
GB-month (20 GB is $0.15 a month). The hourly runs make far fewer writes than the free million.
`--restic stats --mode raw-data` (below) shows what the bucket holds.

### Set up the off-site copy (once)

1. **Bucket and key**, in the Cloudflare dashboard (Cloudflare asks for a card to turn R2 on, even within the
   free tier): R2 > Create bucket, e.g. `monkey-smp-backups`. Its Settings page shows the S3 API address,
   `https://<ACCOUNT_ID>.r2.cloudflarestorage.com/monkey-smp-backups`. Then R2 > Manage API tokens > Create
   API token with **Object Read & Write** on that bucket only, and copy its Access Key ID and Secret Access
   Key (shown once).
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
4. **Units, the first backup and a first test restore:**
   ```sh
   cp /srv/realms/repo/deploy/realms-{backup,restore-test}.{service,timer} /etc/systemd/system/ && systemctl daemon-reload
   sh /srv/realms/repo/deploy/realms-backup.sh --init
   systemctl start realms-backup
   systemctl start realms-restore-test
   systemctl enable --now realms-backup.timer realms-restore-test.timer
   ```
   `--init` creates the repository in the bucket; the first backup sends the whole world, later ones only the
   changes. `/srv/realms/repo` is checked out at the live release, so these files arrive with the first
   release that has them (or `git checkout --detach origin/main` there as `realms`: the deploy script decides
   what is live from its own record, not from that checkout).

The VPS's token can delete (pruning needs to), so the bucket doesn't guard against someone who takes over the
VPS; for that, also keep a copy at home now and then (the restore below, on the home PC).

### Restore

Every snapshot holds the server folder at the same path, `/srv/realms/offsite/server` (the hourly copy is
hard-linked there before it goes up). Restoring `latest:/srv/realms/offsite/server` gives the newest one;
`--restic snapshots` lists the others by ID and time, and `<ID>:/srv/realms/offsite/server` restores one of
them. The script reads the keys from the settings file, so none go on the command line.

**On the VPS** (the world broke, or a mistake needs undoing), as root:

```sh
sh /srv/realms/repo/deploy/realms-backup.sh --restic restore latest:/srv/realms/offsite/server --target /srv/realms/restore
cd /srv/realms/TheRealms-Server/docker && docker compose stop
mv ../server/world ../server/world.before-restore && mv /srv/realms/restore/world ../server/world
chown -R realms: ../server/world && docker compose up -d
```

Only the world goes back. The whitelist, bans, LuckPerms and the mods stay as they are, so nobody who paid
since then loses access. The last 14 hours are also in `backups/`, with no download: move
`../backups/<time>/world` in instead. Delete `world.before-restore` and `/srv/realms/restore` once the server
is fine.

**On a new VPS**: set it up as in "Set up (once)" above. In step 5, before running the deploy script the
second time, do steps 2 and 3 of the off-site setup with the values from your password manager, then
`sh /srv/realms/repo/deploy/realms-backup.sh --restic restore latest:/srv/realms/offsite/server --target /srv/realms/TheRealms-Server/server`
and `chown -R realms: /srv/realms/TheRealms-Server/server`. Then run the deploy script, download the Tebex
jar into `server/mods` again (backups leave jars out; see "Payments and Discord"), and finish with step 4
of the off-site setup. The new VPS carries on the same series of snapshots.

**On the home PC** (Windows, for the fallback below): get `restic_0.19.1_windows_amd64.zip` from
https://github.com/restic/restic/releases and put `restic.exe` in the unzipped release folder. A second R2
token with Object Read only is enough here. In PowerShell, in that folder (the secret is typed hidden and
stays out of the history):

```powershell
$env:RESTIC_REPOSITORY = 's3:https://<ACCOUNT_ID>.r2.cloudflarestorage.com/monkey-smp-backups'
$env:AWS_DEFAULT_REGION = 'auto'
$env:AWS_ACCESS_KEY_ID = '<Access Key ID>'
$env:AWS_SECRET_ACCESS_KEY = [Net.NetworkCredential]::new('', (Read-Host -AsSecureString 'Secret Access Key')).Password
.\restic.exe restore latest:/srv/realms/offsite/server --target server
```

restic asks for the password itself. The result is the `server` folder; put the Tebex jar back into
`server\mods`.

## Fallback: home PC on playit.gg

When the VPS or its provider is down for longer than a restart:

(The newest off-machine backup is the R2 copy: see "On the home PC" under "Restore" above.)

1. On the home PC, unzip the same release, put the newest off-machine backup in as `server`, and start
   it with `Start Server.bat`.
2. Start the playit.gg agent (set up once, as in `READ ME FIRST.txt`). Its tunnel address and port stay
   the same between runs; a premium playit.gg account adds a UDP tunnel for voice chat.
3. In Vercel DNS, point the `_minecraft._tcp.monkeysmp` SRV record at the playit address and port.
   With TTL 60, players reconnect to the same name within minutes.
4. When the VPS is back, stop the home server, copy its `server` folder back to the VPS, swap the SRV
   record back, and start the VPS.

Only one copy may run the world at a time: two live copies split the world into two histories.

## Payments and Discord

- **Tebex** sells the pass and the supporter tiers, collects sales tax as the merchant of record, and runs
  commands on the server after a purchase: `whitelist add {username}` for the pass, and LuckPerms
  `lp user {username} parent add <tier>` for supporter tiers (with the reverse on expiry). Its Fabric mod
  goes into `server/mods` as an extra jar (the installer leaves jars it doesn't manage alone), or into the
  manifest with `tools/add.py` once there is a build for this Minecraft version.
- **Discord**: Tebex's Discord integration gives buyers the paid role. The forum, announcements, ban
  appeals and the `realms` bridge live in the Discord server repo (gr8monk3ys/discord-server). The bridge
  talks RCON, which is plain text: reach the VPS over Tailscale or WireGuard, never by publishing 25575.
