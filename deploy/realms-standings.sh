#!/bin/sh
# Weekly faction standings on the live VPS (tools/standings.py; docs/SEASONS.md, "Weekly standings").
#
#   sh realms-standings.sh close   ends the week: its final table goes on the in-game board, in chat and in
#                                  Discord, and a new week starts (realms-standings.timer, Sundays 7 PM Pacific)
#   sh realms-standings.sh board   this week so far on the in-game board (realms-standings-board.timer, hourly)
#   sh realms-standings.sh show    prints this week so far; changes nothing
#
# Run it as realms (the services do), so the files it keeps stay realms's and the deploy lock stays usable:
#   sudo -u realms sh /srv/realms/repo/deploy/realms-standings.sh show
#
# close and board take the deploy lock, so they never run during a deploy, the daily restart or an off-site
# backup: close waits up to 30 minutes for it, board skips the hour. Reads the saved world (the server saves
# every 5 minutes) and writes the board through the container's own `realms rcon`.
#
# Settings come from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV): REPO_DIR, LIVE_DIR, LOCK_FILE,
# STANDINGS_DIR (default /srv/realms/standings) and the webhook STANDINGS_WEBHOOK_URL (empty =
# DISCORD_WEBHOOK_URL). The webhook goes to the tool in its environment and is never printed. Needs python3
# (3.11 or newer).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

case "${1:-}" in
    close | board | show) MODE=$1 ;;
    *) echo "usage: sh $0 close | board | show" >&2; exit 2 ;;
esac

ENV_FILE=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
# shellcheck disable=SC1090
[ ! -f "$ENV_FILE" ] || . "$ENV_FILE"

REPO_DIR=${REPO_DIR:-/srv/realms/repo}
LIVE_DIR=${LIVE_DIR:-/srv/realms/TheRealms-Server}
LOCK_FILE=${LOCK_FILE:-/tmp/realms-deploy.lock}
STANDINGS_DIR=${STANDINGS_DIR:-/srv/realms/standings}
DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL:-}
STANDINGS_WEBHOOK_URL=${STANDINGS_WEBHOOK_URL:-$DISCORD_WEBHOOK_URL}
export STANDINGS_WEBHOOK_URL

log() { printf '%s [standings] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

WORLD=$LIVE_DIR/server/world
TOOL=$REPO_DIR/tools/standings.py
[ -f "$TOOL" ] || { log "no $TOOL: is a release with the standings live?"; exit 1; }

if [ "$MODE" = show ]; then
    exec python3 -B "$TOOL" show "$WORLD" --state "$STANDINGS_DIR"
fi

# Root would make files realms can't change, and a lock file realms-deploy.sh can't open (fs.protected_regular).
[ "$(id -u)" != 0 ] || { echo "run it as realms: sudo -u realms sh $0 $MODE" >&2; exit 1; }

exec 9>>"$LOCK_FILE"
if [ "$MODE" = close ]; then
    flock -w 1800 9 || { log 'the deploy lock was taken for 30 minutes; trying again later'; exit 1; }
else
    flock -w 60 9 || { log 'a deploy, restart or backup is running; skipping this update'; exit 0; }
fi

mkdir -p "$STANDINGS_DIR"
python3 -B "$TOOL" "$MODE" "$WORLD" --state "$STANDINGS_DIR" --docker "$LIVE_DIR/docker"
