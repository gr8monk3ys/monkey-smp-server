#!/bin/sh
# The one-off steps for the weekly faction standings on the live VPS (docs/LIVE.md, "Monitoring, the daily
# restart and the update check"; docs/SEASONS.md, "Weekly standings"). Run it as root once a release with the
# standings is live and the server has started on it (the start puts the realms-standings data pack in the
# world):
#
#   sudo sh /srv/realms/repo/deploy/install-standings.sh --check   says what is still to do, and changes nothing
#   sudo sh /srv/realms/repo/deploy/install-standings.sh           does it
#
# Each step is skipped when it is already done, so running it again is safe:
#   1. installs python3 if it is missing (tools/standings.py needs 3.11 or newer, for tomllib)
#   2. checks the realms-standings data pack is in the world and turned on (it counts the week's PvP kills)
#   3. makes the folder the standings keep their weeks in (STANDINGS_DIR, default /srv/realms/standings), as realms
#   4. starts the first week: a snapshot of every player's kills and bounties so far, as realms
#   5. installs realms-standings.timer (Sundays 7 PM Pacific) and realms-standings-board.timer (hourly) from the
#      deployed checkout and starts them, then puts this week so far on the in-game board once
# Two steps stay by hand: the webhook (STANDINGS_WEBHOOK_URL in /etc/realms-deploy.env; empty = the
# DISCORD_WEBHOOK_URL channel), and the board at spawn, which staff place in game with
# /function realms:standings/place (docs/ADMIN.md).
#
# It reads only REPO_DIR, LIVE_DIR and STANDINGS_DIR from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV), without
# sourcing it, so the webhooks are never read. RCON goes through the container's own `realms rcon`, which finds
# the password itself. No secret is read, printed or asked for. What it prints also goes to
# /var/log/realms-install-standings.log (or INSTALL_LOG), with the output of apt-get and systemctl.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=install-standings
. "$(dirname -- "$0")/lib.sh"

case "${1:-}" in
    '') MODE=apply ;;
    --check) MODE=check ;;
    *) echo "usage: sh $0 [--check]" >&2; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || { echo 'run as root: it installs packages and timers' >&2; exit 1; }

ENV_FILE=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
LOG_TO=${INSTALL_LOG:-/var/log/realms-install-standings.log}

REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/realms/repo)}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/realms/TheRealms-Server)}
STANDINGS_DIR=${STANDINGS_DIR:-$(setting STANDINGS_DIR /srv/realms/standings)}

WORLD=$LIVE_DIR/server/world
PACK=realms-standings
UNITS='realms-standings.service realms-standings.timer realms-standings-board.service realms-standings-board.timer'
TIMERS='realms-standings.timer realms-standings-board.timer'
SERVICE_USER=realms  # User= in the two .service files

umask 022

todo=0      # --check: steps still to do
problems=0  # steps that need a look by hand

# ---------------------------------------------------------------- checks (nothing changes yet)

for tool in docker runuser systemctl apt-get install cmp stat sed tail; do
    command -v "$tool" >/dev/null || die "$tool is missing"
done
cd /
log "started ($MODE); log: $LOG_TO"
[ -f "$LIVE_DIR/docker/compose.yaml" ] || die "$LIVE_DIR has no docker/compose.yaml (LIVE_DIR in $ENV_FILE?)"
for f in tools/standings.py deploy/realms-standings.sh; do
    [ -f "$REPO_DIR/$f" ] || die "$REPO_DIR has no $f: the deployed release has no standings yet; run this once it does"
done
for u in $UNITS; do
    [ -f "$REPO_DIR/deploy/$u" ] || die "$REPO_DIR/deploy has no $u: the deployed release has no standings yet"
done
if ! runuser -u "$SERVICE_USER" -- test -r "$ENV_FILE"; then
    log "WARNING: $SERVICE_USER can't read $ENV_FILE, which the timers' services need. As root:" \
        "chown root:$SERVICE_USER $ENV_FILE && chmod 640 $ENV_FILE"
    problems=$((problems + 1))
fi

# ---------------------------------------------------------------- 1. python3

if python_ok 11; then
    log "python3: already installed ($(python3 --version 2>&1))"
elif [ "$MODE" = check ]; then
    log 'python3: to do (missing, or older than 3.11)'
    todo=$((todo + 1))
else
    log 'python3: installing'
    export DEBIAN_FRONTEND=noninteractive
    logged apt-get install -y --no-install-recommends python3 ||
        { logged apt-get update && logged apt-get install -y --no-install-recommends python3; } ||
        die "apt-get could not install python3 (see $LOG_TO)"
    python_ok 11 || die "python3 is installed but older than 3.11: $(python3 --version 2>&1). Debian 12 or newer has 3.11."
    log "python3: installed ($(python3 --version 2>&1))"
fi

# ---------------------------------------------------------------- 2. the data pack

pack_ok=''
if [ ! -f "$WORLD/datapacks/$PACK/pack.mcmeta" ]; then
    log "data pack: not in $WORLD/datapacks yet. Restart the server once on a release that has it" \
        "(runuser -u $SERVICE_USER -- env RESTART_MIN_UPTIME=0 sh $REPO_DIR/deploy/realms-deploy.sh --restart), then run this again"
    problems=$((problems + 1))
elif ! running; then
    log 'data pack: in the world, but the server is not running, so whether it is on is unknown; start it and run this again'
    problems=$((problems + 1))
elif ! enabled=$(rcon 'datapack list enabled'); then
    log 'data pack: RCON did not answer; run this again once the server is up'
    problems=$((problems + 1))
else
    # Only a positive answer counts: an empty or error reply must not read as "on".
    case "$enabled" in
        *"file/$PACK"*)
            log 'data pack: in the world and on'
            pack_ok=1 ;;
        *)
            log "data pack: in the world but not on; turn it on with: realms rcon 'datapack enable \"file/$PACK\"'"
            problems=$((problems + 1)) ;;
    esac
fi

# ---------------------------------------------------------------- 3. the folder

if [ -d "$STANDINGS_DIR" ] && [ "$(stat -c %U "$STANDINGS_DIR")" = "$SERVICE_USER" ]; then
    log "folder: already made ($STANDINGS_DIR)"
elif [ "$MODE" = check ]; then
    log "folder: to do ($STANDINGS_DIR, owned by $SERVICE_USER)"
    todo=$((todo + 1))
elif [ -d "$STANDINGS_DIR" ]; then
    chown "$SERVICE_USER:$SERVICE_USER" "$STANDINGS_DIR"
    log "folder: $STANDINGS_DIR now belongs to $SERVICE_USER"
else
    install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 755 "$STANDINGS_DIR"
    log "folder: made $STANDINGS_DIR"
fi

# ---------------------------------------------------------------- 4. the first week

if [ -f "$STANDINGS_DIR/week.json" ]; then
    log "first week: already started ($STANDINGS_DIR/week.json)"
elif [ "$MODE" = check ]; then
    log 'first week: to do (a snapshot of the kills and bounties so far, from the saved world)'
    todo=$((todo + 1))
elif [ -z "$pack_ok" ]; then
    log 'first week: waiting for the data pack (step 2), so the week counts its kills'
    problems=$((problems + 1))
elif runuser -u "$SERVICE_USER" -- python3 -B "$REPO_DIR/tools/standings.py" start "$WORLD" --state "$STANDINGS_DIR" \
        >>"$LOG_TO" 2>&1; then
    log 'first week: started'
else
    log "first week: tools/standings.py start failed (see $LOG_TO)"
    problems=$((problems + 1))
fi

# ---------------------------------------------------------------- 5. the timers

changed=''
for u in $UNITS; do
    cmp -s "$REPO_DIR/deploy/$u" "/etc/systemd/system/$u" || changed="$changed $u"
done
idle=''
for t in $TIMERS; do
    { systemctl is-enabled --quiet "$t" && systemctl is-active --quiet "$t"; } 2>/dev/null || idle="$idle $t"
done
if [ -z "$changed$idle" ]; then
    log 'timers: already installed and running'
elif [ "$MODE" = check ]; then
    log "timers: to do (copy:${changed:- none}; start:${idle:- none})"
    todo=$((todo + 1))
elif [ ! -f "$STANDINGS_DIR/week.json" ]; then
    log 'timers: waiting for the first week (step 4)'
    problems=$((problems + 1))
else
    for u in $changed; do
        install -m 644 -o root -g root "$REPO_DIR/deploy/$u" "/etc/systemd/system/$u"
        log "timers: installed /etc/systemd/system/$u"
    done
    if [ -n "$changed" ]; then
        logged systemctl daemon-reload
    fi
    # $TIMERS is two unit names.
    # shellcheck disable=SC2086
    logged systemctl enable --now $TIMERS
    # A timer that was already running picks up a changed schedule on restart; this doesn't run its service.
    # shellcheck disable=SC2086
    [ -z "$changed" ] || logged systemctl restart $TIMERS
    log 'timers: running'
    if logged systemctl start realms-standings-board.service; then
        log 'board: this week so far is on the in-game board'
    else
        log 'board: the first update failed: journalctl -u realms-standings-board'
        problems=$((problems + 1))
    fi
fi
# shellcheck disable=SC2086
systemctl list-timers --all --no-pager $TIMERS 2>&1 | while IFS= read -r l; do log "  $l"; done

# ---------------------------------------------------------------- done

log "by hand, if not done yet: STANDINGS_WEBHOOK_URL in $ENV_FILE for the Sunday post (empty = the" \
    'DISCORD_WEBHOOK_URL channel), and the board at spawn: stand there and run /function realms:standings/place'
if [ "$problems" -gt 0 ]; then
    log "finished: $problems thing(s) need a look by hand (above)"
    exit 1
elif [ "$MODE" = check ]; then
    log "check finished: $todo step(s) to do; nothing was changed"
else
    log 'finished: all steps done'
fi
