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
7. **Timers.** `sudo cp /srv/realms/repo/deploy/realms-{deploy,day}.{service,timer} /etc/systemd/system/`,
   `sudo systemctl daemon-reload && sudo systemctl enable --now realms-deploy.timer realms-day.timer`.
   The day timer counts "days played" for the wardrobe (docs/RETENTION.md) at midnight UTC.
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

1. On the home PC, unzip the same release, put the newest off-machine backup in as `server`, put the
   Tebex jar back in `server\mods` (backups leave jars out; see "Payments" below), and start it with
   `Start Server.bat`.
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
  in `server/mods` as an extra jar, which deploys and the installer leave alone. Backups leave every jar
  out, so after restoring one (or on the fallback below) download it again:
  `https://cdn.modrinth.com/data/nRA0jiJt/versions/qg7SxggJ/tebex-fabric-26.2-2.4.6-0096441.jar`. Once
  there is a 26.3 build it can go into the manifest with `tools/add.py`, and then it comes back by itself.
- **Discord**: Tebex's Discord integration gives buyers the paid role. The forum, announcements, ban
  appeals and the `realms` bridge live in the Discord server repo (gr8monk3ys/discord-server). The bridge
  talks RCON, which is plain text: reach the VPS over Tailscale or WireGuard, never by publishing 25575.

### The store (set up once, before the first sale)

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
  `python tools/site_links.py`, which writes it into the pages.
