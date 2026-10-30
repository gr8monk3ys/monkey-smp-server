#!/bin/sh
# Writes the server's public status for the website (tools/status.py): online or not, how many are playing (a
# count, never names), the season's next event and the border. Caddy serves the file next to the live map as
# https://map.monkeysmp.lscaturchio.xyz/status.json (deploy/Caddyfile), so no new port opens.
# monkey-status.timer runs it every 2 minutes as the monkey user.
#
#   sh monkey-status.sh                  writes STATUS_DIR/status.json (a server that isn't running is written
#                                        as offline: that is the status)
#   sh monkey-status.sh --check          prints the status for now and whether the timer is installed and
#                                        running; changes nothing
#   sudo sh monkey-status.sh --install   makes STATUS_DIR (the monkey user's, readable by Caddy), copies
#                                        monkey-status.service and monkey-status.timer from the deployed checkout to
#                                        /etc/systemd/system (only if they changed) and starts the timer
#
# It only reads: the saved world's border and `list` over RCON (the container's own `monkey rcon`, so no secret
# is read here). No deploy lock: during a deploy or the daily restart the status simply says offline.
# Reads only REPO_DIR, LIVE_DIR and STATUS_DIR (default /srv/monkey/status) from /etc/monkey-deploy.env (or
# MONKEY_DEPLOY_ENV). Needs python3 3.10 or newer.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=monkey-status
. "$(dirname -- "$0")/lib.sh"

case "${1:-}" in
    '') MODE=write ;;
    --check) MODE=check ;;
    --install) MODE=install ;;
    *) echo "usage: sh $0 [--check | --install]" >&2; exit 2 ;;
esac

ENV_FILE=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/monkey/repo)}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/monkey/MonkeySMP-Server)}
STATUS_DIR=${STATUS_DIR:-$(setting STATUS_DIR /srv/monkey/status)}
UNITS='monkey-status.service monkey-status.timer'

if [ "$MODE" = install ]; then
    [ "$(id -u)" = 0 ] || die 'run as root: it installs systemd units'
    for unit in $UNITS; do
        [ -r "$REPO_DIR/deploy/$unit" ] || die "$REPO_DIR/deploy/$unit is missing: is the release with the status deployed?"
    done
    install -d -m 755 -o monkey -g monkey "$STATUS_DIR"
    log "status folder: $STATUS_DIR"
    install_timer monkey-status.timer $UNITS
    exit 0
fi

TOOL=$REPO_DIR/tools/status.py
command -v python3 >/dev/null 2>&1 || die 'python3 is missing (deploy/upgrade-2.5.0.sh installs it)'
python_ok 10 || die 'python3 is older than 3.10'
[ -r "$TOOL" ] || die "$TOOL is missing: is the release with the status deployed?"
WORLD=$LIVE_DIR/server/world

if [ "$MODE" = check ]; then
    log 'status for now:'
    python3 -B "$TOOL" show "$WORLD" --docker "$LIVE_DIR/docker" | while IFS= read -r line; do log "  $line"; done
    timer_state monkey-status.timer $UNITS
    log 'check finished: nothing was changed'
    exit 0
fi

# Root would leave a file the monkey user's next run can't replace.
[ "$(id -u)" != 0 ] || { echo "run it as monkey: sudo -u monkey sh $0" >&2; exit 1; }
[ -d "$STATUS_DIR" ] || die "no $STATUS_DIR: run sudo sh $0 --install"
python3 -B "$TOOL" write "$WORLD" --docker "$LIVE_DIR/docker" --out "$STATUS_DIR/status.json"
