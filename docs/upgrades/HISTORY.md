# One-off upgrade steps already done

The live server's one-off steps for releases that are live now, moved out of docs/LIVE.md ("One-off steps when
upgrading") once they were done. They are kept as they were written, for the record and for a VPS set up again from
scratch: several of them are still the only install steps for a timer (outposts, omens, sieges, news, the website's
status). Steps still to do stay in docs/LIVE.md. Newest first, as they were there; "above" and "below" mean in this
file.

## 2.5.0: `deploy/upgrade-2.5.0.sh`

For 2.5.0, `deploy/upgrade-2.5.0.sh` did the Distant Horizons change (gone with the mod in 3.0.0) and the section below (the short rules, ServerCore
and claims) with a single restart, then the spawn claim, python3 and the two timers ("Monitoring, the daily
restart and the update check" in docs/LIVE.md). It skips whatever is already done, so it is safe to run again. Run it as root
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
line; its log is `/var/log/monkey-upgrade-2.5.0.log`. The off-site backups stay a manual step (docs/LIVE.md, "Backups off
the machine"): they need keys the owner makes.

## Monkey SMP names (2.10.0)

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

## 3.1.1: Mace Limiter

3.1.1 adds one server-only mod. Players keep the 3.1.0 pack and nothing they install changes. It adds no blocks, items
or world generation, so it stays on the world it finds.

Its settings and its count live in `world/macelimiter_maces.json`, made on the first start with a limit of 3. They belong
to the world, so a new world starts at 3 again. For another limit, `monkey rcon "macelimit set 5"`. Check with
`monkey rcon "macelimit"` and `monkey rcon "macelimit count"`.

## 3.1.0: the final mod list and the speed patches

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

## 3.0.0: Minecraft 26.2 and a new world

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

## A new world for Season I (2.8.0)

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
10. Pre-generate as on the first setup (docs/LIVE.md, "Set up (once)", step 6): `monkey rcon "chunky worldborder"`,
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

## The weekly challenges' timer (the release with the weekly challenges)

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

## The supply drops' timer (the release with supply drops)

Once that release is live, install `monkey-drops.timer` the same way (`docs/ADMIN.md`, "Supply drops"):

```sh
sh /srv/monkey/repo/deploy/monkey-drops.sh --check
sudo sh /srv/monkey/repo/deploy/monkey-drops.sh --install
```

It runs every 10 minutes as `monkey`, sends nothing outside Monday to Thursday, 6 to 10 PM Pacific, and
reads only `REPO_DIR` and `LIVE_DIR` from `/etc/monkey-deploy.env`, plus the saved claims and border from
the world. Without it there are no automatic drops; staff can still start one by hand.

## The outposts' timer (the release with outposts)

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

## The omens' timer (the release with omens)

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

## The website's status (the release with `tools/status.py`)

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

## The sieges timer (the release with outpost sieges and 7-day wars)

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

## The news timer (the release with Monkey SMP news)

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

## The spawn NPCs (the release with spawn NPCs)

The release adds the `monkey-npcs` data pack but places no one. Once it is live, an op places the Guide and
the Town Crier at spawn once, in game: `/function monkey:npcs/guide/here` and `/function monkey:npcs/crier/here`
where each should stand (docs/ADMIN.md, "Spawn NPCs"). Until then there are no NPCs at spawn. Place them again
after a release that changes their text.

## NPCs in claims (2.9.1)

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

It works like `deploy/shops-claims.sh` (docs/LIVE.md, "Shops in claims"): it warns players online (`--now` skips that), takes
the deploy lock, stops the server for about 3 minutes (the mod reads the list only on start), keeps the old file
as `openpartiesandclaims-server.toml.before-npcs` and starts the server again whatever happens; its log is
`/var/log/monkey-npc-claims.log`. It prints only the `forcedEntityProtectionExceptionList` line. If that list is
missing or spread over several lines, it changes nothing and says so: add the entries it names to it by hand
with the server stopped. Nothing to do in game: the NPCs stay where they are.

## The short rules, ServerCore and claims (the release after 2.4.2)

The release brings the short rules (`server/codeofconduct/en_us.txt`, a new file), but the live server keeps its
own copies of three files, so four settings in them stay off: the Code of Conduct (`server.properties`), ServerCore's
breeding cap and villager lobotomization (`config/servercore/config.yml`) and Open Parties and Claims' 4 chunks per
player (`config/openpartiesandclaims-server.toml`). Spawn's no-PvP claim belongs to the world, so it's made from the
console. Do this after the release is live: `ls /srv/monkey/MonkeySMP-Server/server/codeofconduct/en_us.txt` must
list the file. Then, as `monkey` (`sudo -iu monkey`):

```sh
cd /srv/monkey/MonkeySMP-Server/docker
exec 9>/tmp/monkey-deploy.lock && flock 9    # the deploy lock (docs/LIVE.md)
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
