# Runbook: when something breaks on the live server

One page for the VPS at 3 AM. Each part goes symptom, check, fix, who to tell, and links the long docs
([LIVE.md](LIVE.md), [ADMIN.md](ADMIN.md)) for the detail. Stop at the first check that explains it.

On the VPS over SSH, as `monkey` (`sudo -iu monkey`) unless a line says root (`sudo`), in
`/srv/monkey/MonkeySMP-Server/docker`. `monkey rcon "..."` is short for `docker compose exec monkey monkey rcon "..."`.
Only one copy of the world may run at a time, so never start the home PC while the VPS might be running.

**Who to tell, every time:** players get one line in the public Discord channel (what is down, since when, when you
will look again); staff get what you did in the staff channel. Root-only steps (backups, restores, `install-root.sh`)
are the owner's: wake one only when the world is at risk.

## Where the logs are

| What | Command |
|---|---|
| The game | `docker compose logs --tail 200 monkey`; files in `../server/logs/latest.log` and `../server/crash-reports/` |
| Deploys and rollbacks | `journalctl -u monkey-deploy -n 100` |
| Daily restart | `journalctl -u monkey-restart -n 50` |
| Off-site backup, restore drill (root) | `journalctl -u monkey-backup -n 50`, `journalctl -u monkey-restore-drill -n 40` |
| Staff page | `journalctl -u monkey-staff -u monkey-panel -n 50` |
| Standings, day, timed jobs | `journalctl -u monkey-standings -u monkey-standings-board -n 50`, `journalctl -u monkey-day` |
| What failed, what runs now | `systemctl --failed`, `systemctl list-units 'monkey-*' --state=activating`, `journalctl -u 'monkey-alert@*' -n 20` |

A failure alert in the staff channel names the unit and the `journalctl` line to read
([LIVE.md, "Monitoring"](LIVE.md#monitoring-the-daily-restart-and-the-update-check)).

## Server down or won't start

- **Symptom:** players can't join; Uptime Kuma posts in Discord; the staff page says Offline.
- **Check:** `docker compose ps`. `Up` but nobody can join: DNS and firewall, step 5 of
  [LIVE.md, "The server is down"](LIVE.md#the-server-is-down). Then `sh /srv/monkey/repo/deploy/monkey-deploy.sh --status`
  and the `activating` list above: a deploy, the daily restart or a backup can hold it down for up to 15 minutes.
  Wait for it; don't start the server by hand meanwhile. Then `docker compose logs --tail 200 monkey`:
  `OutOfMemoryError` or exit code 137 is memory (`free -g`, `MEMORY_GB` in `.env`); a mod error at start is a bad
  release (below); `No space left on device` is the disk (below).
- **Fix:** `docker compose up -d`, `docker compose logs -f monkey` until `Done`, then `monkey rcon list`.
  The machine itself gone for hours: [LIVE.md, "Fallback: home PC on playit.gg"](LIVE.md#fallback-home-pc-on-playitgg).
- **Tell:** players when it is down and when it is back; afterwards check the backups ran
  (`sudo journalctl -u monkey-backup -n 20`) and put one line on the cause in the staff channel.

## Lag

- **Symptom:** rubber-banding, slow blocks; the staff page says Slow, or a health alert says lag.
- **Check:** `monkey rcon "spark tps"` (tick time under 50 ms keeps 20 TPS), `monkey rcon "spark health"`,
  `free -g`, and the staff page's "What it probably is". A running pre-generation: `monkey rcon "chunky progress"`.
- **Fix:** find the cause with `monkey rcon "spark profiler start"`, a few minutes later
  `monkey rcon "spark profiler stop"`, and open the link (or Server > "Find what causes lag" on the staff page).
  Pre-generation in play hours: `monkey rcon "chunky pause"`. Memory climbing for days: restart now, with warnings,
  `RESTART_MIN_UPTIME=0 sh /srv/monkey/repo/deploy/monkey-deploy.sh --restart`. Detail: ADMIN.md,
  ["Before a big group joins"](ADMIN.md#before-a-big-group-joins).
- **Tell:** the staff channel, with the spark link.

## Disk full

- **Symptom:** `No space left on device` in the log; a health alert for disk; backups fail.
- **Check:** `df -h /srv`, then `du -sh ../server/world ../backups` and `ls -lh ../server/world/ledger.sqlite*`.
  Ledger's history (`world/ledger.sqlite`) grew about 8 GB a day before 3.5.0; it should be flat now.
- **Fix:** delete old folders in `../backups/` (a deploy keeps the newest 3; R2 has the history), never `server/`.
  Then the leftovers: `ledger.sqlite.before-prune` (once `ledger search` works in game), `world.before-restore`
  and `/srv/monkey/restore` after a restore, a kept drill folder in `/var/tmp/monkey-drill.*`.
  A big `ledger.sqlite`: run `tools/ledger_prune.py` twice, server up then stopped, exactly as in
  [LIVE.md, "Ledger's history"](LIVE.md#ledgers-history-the-release-with-the-charged-cube-patch) (root's copies first).
  Old logs: `sh /srv/monkey/repo/deploy/monkey-logs.sh --check` lists what the daily prune deletes.
- **Tell:** the staff channel; the owner if the world itself is what filled it.

## Restore from backup

- **Symptom:** the world is broken or a mistake needs undoing (a grief rollback is Ledger's job, not this).
- **Check** (root): `sudo sh /opt/monkey/deploy/monkey-backup.sh --restic snapshots`. Pick the newest snapshot
  not tagged `unflushed`. A deploy's own copy (the newest folders in `../backups/`) needs no download.
- **Fix** (root), as in [LIVE.md, "Restore"](LIVE.md#restore); only the world goes back:

  ```sh
  sh /opt/monkey/deploy/monkey-backup.sh --restic restore latest:/srv/monkey/MonkeySMP-Server/server --target /srv/monkey/restore
  cd /srv/monkey/MonkeySMP-Server/docker && docker compose stop
  mv ../server/world ../server/world.before-restore && mv /srv/monkey/restore/world ../server/world
  chown -R monkey: ../server/world && docker compose up -d
  ```

  `<ID>:` in place of `latest:` takes an older snapshot. To prove backups read back without touching the live
  server: `sudo systemctl start monkey-restore-drill` ([the drill](LIVE.md#the-restore-drill-on-the-vps)).
- **Tell:** players how much time was lost; the owner before you start.

## Roll back a bad release

- **Symptom:** a deploy went live (4-5 AM Pacific) and the server won't start, or it starts and something is broken.
- **Check:** `sh /srv/monkey/repo/deploy/monkey-deploy.sh --status` (`deployed:`, `failed:`, `pinned:`) and
  `journalctl -u monkey-deploy -n 100`.
- **Fix:** a release that doesn't answer within `BOOT_TIMEOUT` (15 minutes) is rolled back by the deploy itself: it
  puts the previous release back, posts to Discord and writes the commit to `/srv/monkey/MonkeySMP-Server/.deploy-failed`,
  so it isn't retried until a newer commit. To retry once fixed: delete `.deploy-failed` and run
  `sh /srv/monkey/repo/deploy/monkey-deploy.sh --now`. A release that starts but is broken:
  `sh /srv/monkey/repo/deploy/monkey-deploy.sh --tag=vX.Y.Z` with the last good tag deploys it now (it still warns
  players) and pins it; `--tag=` with the newest tag unpins once a fix is out. Only the files go back, not the world:
  never go back across a Minecraft version or a world reset. The world from before the update is the newest folder in
  `../backups/`. If the release changed the players' pack, players who updated may need the old one again.
- **Tell:** players (which pack to use); the staff channel; whoever tagged the release.

## Staff page down

- **Symptom:** `https://staff.monkeysmp.lscaturchio.xyz` doesn't load, logs in to errors, or says "No reading yet".
  The game is unaffected; this can wait for daylight.
- **Check:** `curl -sI https://staff.monkeysmp.lscaturchio.xyz | head -1` (a 401 means Caddy and the password check
  are up), `systemctl status caddy monkey-panel`, `systemctl list-timers monkey-staff.timer`,
  `sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --check`, and the staff page's journal above.
- **Fix:** controls failing: `sudo systemctl restart monkey-panel`. Status stale: `sudo systemctl start monkey-staff`.
  After a release that changed its units or `Caddyfile.staff`: `sudo sh /srv/monkey/repo/deploy/monkey-staff.sh --install`.
  Detail: [LIVE.md, "The staff page"](LIVE.md#the-staff-page).
- **Tell:** the staff channel, so nobody waits on the page for a ban or a restart (the console works without it).
