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

Running now (since October 2026): a Reizor Hosting "Ryzen 9 9950X VPS 16GB" in Dallas (2 dedicated threads,
16 GB, 200 GB NVMe, $45 a month), Debian 12, set up with the steps below.

## Set up (once)

1. **User and Docker.** As root: install Docker Engine with the compose plugin, `git`, `rsync` and `curl`;
   `adduser --disabled-password realms`; `usermod -aG docker realms`; `mkdir -p /srv/realms && chown realms: /srv/realms`.
2. **Firewall.** Open 25565/tcp (game) and 24454/udp (voice chat). Open 8100/tcp only if the live map
   should be public. Keep SSH key-only. RCON (25575) stays unpublished (compose.yaml).
3. **Clone with a read-only deploy key.** As `realms`: `ssh-keygen -t ed25519 -f ~/.ssh/realms_deploy -N ''`,
   add the `.pub` file as a read-only deploy key in the repo settings on GitHub, then
   ```sh
   printf 'Host github.com\n  IdentityFile ~/.ssh/realms_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config
   ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts
   git clone git@github.com:gr8monk3ys/monkey-smp-server.git /srv/realms/repo
   ```
4. **Settings.** `sudo cp /srv/realms/repo/deploy/realms-deploy.env.example /etc/realms-deploy.env`, edit
   it (the Discord webhook is optional; `DEPLOY_WINDOW` is when updates may go live), then
   `sudo chown root:realms /etc/realms-deploy.env && sudo chmod 640 /etc/realms-deploy.env` (the deploy
   service runs as `realms`, so it has to be able to read the file).
5. **First deploy.** `sh /srv/realms/repo/deploy/realms-deploy.sh` copies the release folder to
   `/srv/realms/TheRealms-Server` and stops, asking for `docker/.env`: copy `.env.example` to `.env`
   there, set `EULA=TRUE`, `OWNER=<your Minecraft name>`, `MEMORY_GB=10` and `TZ=America/Los_Angeles`.
   To keep an existing world, copy its `server` folder into `/srv/realms/TheRealms-Server/` now. Run the
   script again: it downloads about 500 MB, starts the server and records the deployed commit.
6. **Pre-generate the world** before anyone joins: exploring new land costs far more tick time than
   anything else. In the console: `worldborder set 12000`, then `chunky radius 6000` and `chunky start`
   (hours; it carries on after a restart because the default `config/chunky/config.json` sets
   `continueOnRestart`; on a server set up before that, run `chunky continue` after a restart). The Nether is 1/8 the size:
   `execute in minecraft:the_nether run worldborder set 1500`, then `chunky world minecraft:the_nether`,
   `chunky radius 750` and `chunky start`.
7. **Timers.** `sudo cp /srv/realms/repo/deploy/realms-{deploy,day}.{service,timer} /etc/systemd/system/`,
   `sudo systemctl daemon-reload && sudo systemctl enable --now realms-deploy.timer realms-day.timer`.
   The day timer counts "days played" for the wardrobe (docs/RETENTION.md) at midnight UTC.
8. **DNS** (Cloudflare, which holds the lscaturchio.xyz zone): an `A` record `play.monkeysmp` to the VPS
   address with the proxy off ("DNS only": Cloudflare's proxy carries only web traffic), and an `SRV` record `_minecraft._tcp.monkeysmp` with priority 0, weight 5, port 25565, target
   `play.monkeysmp.lscaturchio.xyz`, TTL 60. Players then type `monkeysmp.lscaturchio.xyz` with no
   port, while the same name serves the website. Voice chat finds the server by itself.

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

If a new release doesn't answer within `BOOT_TIMEOUT`, the script puts the previous release back, restarts
it, posts to Discord, and skips the failed commit until a newer one appears. The world backup it took
before the update is the newest folder in `backups/`.

## Backups off the machine

`backups/` lives on the same disk as the world. Copy it somewhere else nightly, e.g. with restic to a
Backblaze B2 or Cloudflare R2 bucket (both cost about nothing at this size):
`0 7 * * * restic -r s3:<bucket-url>/realms backup /srv/realms/TheRealms-Server/backups --keep-daily 14`.
That copy is also what the fallback below starts from.

## Fallback: home PC on playit.gg

When the VPS or its provider is down for longer than a restart:

1. On the home PC, unzip the same release, put the newest off-machine backup in as `server`, and start
   it with `Start Server.bat`.
2. Start the playit.gg agent (set up once, as in `READ ME FIRST.txt`). Its tunnel address and port stay
   the same between runs; a premium playit.gg account adds a UDP tunnel for voice chat.
3. In Cloudflare DNS, point the `_minecraft._tcp.monkeysmp` SRV record at the playit address and port.
   With TTL 60, players reconnect to the same name within minutes.
4. When the VPS is back, stop the home server, copy its `server` folder back to the VPS, swap the SRV
   record back, and start the VPS.

Only one copy may run the world at a time: two live copies split the world into two histories.

## Payments and Discord

- **Tebex** sells the pass and the supporter tiers, collects sales tax as the merchant of record, and runs
  commands on the server after a purchase: `whitelist add {username}` for the pass (`whitelist remove` when
  it ends), and the wardrobe scoreboard and team commands for supporter tiers (the full list, with the
  reverse on expiry, is in docs/RETENTION.md). The monthly pass renews until the buyer cancels it from
  Tebex's payment history page; after 3 failed renewals it expires and the expiry commands run. Tebex's
  Fabric mod (2.4.6) is built for 26.2 but loads on 26.3 (checked on the live server, October 2026). It sits
  in `server/mods` as an extra jar, which deploys and the installer leave alone; once there is a 26.3
  build it can go into the manifest with `tools/add.py`.
- **Discord**: Tebex's Discord integration gives buyers the paid role. The forum, announcements, ban
  appeals and the `realms` bridge live in the Discord server repo (gr8monk3ys/discord-server). The bridge
  talks RCON, which is plain text: reach the VPS over Tailscale or WireGuard, never by publishing 25575.
