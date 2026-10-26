#!/bin/sh
# The one-off step for shops on the live VPS (docs/LIVE.md, "Shops in claims"). The release with Universal Shops
# ships `forcedBlockProtectionExceptionList = [..., "hand$universal_shops:trade_block"]` in
# defaults/config/openpartiesandclaims-server.toml, so anyone may click a Trade Shop with an empty hand in
# someone else's claim and buy from it. A deploy never overwrites the live server's own copy of that file, so
# this adds the entry there. Run it as root once that release is live. Started with systemd-run it carries on if
# the SSH connection drops while the server is stopped:
#
#   systemd-run --unit=realms-shops --collect -p TimeoutStopSec=20min sh /srv/realms/repo/deploy/shops-claims.sh
#   journalctl -fu realms-shops
#
#   sh shops-claims.sh --check   says whether it is still to do, and changes nothing
#   sh shops-claims.sh --now     stops the server without the warning in chat
#
# When the list already names universal_shops:trade_block (with any prefix) it does nothing, so running it again
# is safe. Otherwise, under the deploy lock, with a warning in chat if players are online, it stops the server
# (Open Parties and Claims reads the setting only on start, and would write over a change made while it runs),
# copies the file to openpartiesandclaims-server.toml.before-shops once, adds the entry, and starts the server
# again whatever happens. About 3 minutes offline. A list it can't edit safely (missing, or spread over several
# lines) is left for you to set by hand.
#
# It reads only LIVE_DIR, LOCK_FILE, WARN_MINUTES and BOOT_TIMEOUT from /etc/realms-deploy.env (or
# REALMS_DEPLOY_ENV), without sourcing it, so the webhooks are never read. RCON goes through the container's own
# `realms rcon`, which finds the password itself. No secret is read, printed or asked for. What it prints also
# goes to /var/log/realms-shops-claims.log (or SHOPS_LOG), with the output of docker.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

case "${1:-}" in
    '') MODE=apply ;;
    --check) MODE=check ;;
    --now) MODE=now ;;
    *) echo "usage: sh $0 [--check | --now]" >&2; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || { echo 'run as root: it stops the server and edits its files as their owner' >&2; exit 1; }

ENV_FILE=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
LOG=${SHOPS_LOG:-/var/log/realms-shops-claims.log}

# "setting NAME DEFAULT": NAME's value in the env file (the last one, quotes dropped), else DEFAULT.
setting() {
    v=''
    [ ! -r "$ENV_FILE" ] ||
        v=$(sed -n "s/^[[:space:]]*$1=//p" "$ENV_FILE" | tail -n 1 | sed -e 's/[[:space:]]*$//' -e "s/^[\"']//" -e "s/[\"']\$//")
    printf '%s' "${v:-$2}"
}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/realms/TheRealms-Server)}
LOCK_FILE=${LOCK_FILE:-$(setting LOCK_FILE /tmp/realms-deploy.lock)}
WARN_MINUTES=${WARN_MINUTES:-$(setting WARN_MINUTES 5)}
BOOT_TIMEOUT=${BOOT_TIMEOUT:-$(setting BOOT_TIMEOUT 900)}
case "$WARN_MINUTES" in '' | *[!0-9]*) WARN_MINUTES=5 ;; esac
case "$BOOT_TIMEOUT" in '' | *[!0-9]*) BOOT_TIMEOUT=900 ;; esac

SERVER_DIR=$LIVE_DIR/server
FILE=$SERVER_DIR/config/openpartiesandclaims-server.toml
BACKUP=$FILE.before-shops
KEY=forcedBlockProtectionExceptionList
BLOCK='universal_shops:trade_block'
ENTRY="hand\$$BLOCK"  # the same entry as defaults/config/openpartiesandclaims-server.toml
SERVICE_USER=realms   # the owner of the deploy lock (docs/LIVE.md)

umask 022
log() {
    line="$(date '+%Y-%m-%d %H:%M:%S') [shops-claims] $*"
    printf '%s\n' "$line" >>"$LOG"
    printf '%s\n' "$line"
}
die() { log "ERROR: $*"; exit 1; }
# Runs a command with its output in the log file only.
logged() { "$@" >>"$LOG" 2>&1; }

compose() { docker compose --project-directory "$LIVE_DIR/docker" -f "$LIVE_DIR/docker/compose.yaml" "$@"; }
running() { [ -n "$(compose ps -q --status running realms 2>/dev/null)" ]; }
rcon() { compose exec -T realms realms rcon "$1" </dev/null 2>/dev/null; }

wait_for_live() {
    waited=0
    while [ "$waited" -lt "$BOOT_TIMEOUT" ]; do
        sleep 15
        waited=$((waited + 15))
        if rcon list >/dev/null; then return 0; fi
    done
    return 1
}

# If players are online, warns them in chat WARN_MINUTES and 1 minute ahead.
warn_players() {
    [ "$WARN_MINUTES" -gt 0 ] || return 0
    online=$(rcon list | sed -n 's/.*There are \([0-9][0-9]*\) of.*/\1/p' | head -n 1)
    [ "${online:-0}" -gt 0 ] || return 0
    log "$online player(s) online; warning them $WARN_MINUTES minutes ahead"
    rcon "say Server restart in $WARN_MINUTES minutes for a settings update (about 3 minutes offline)." >/dev/null || true
    [ "$WARN_MINUTES" -le 1 ] || sleep $(((WARN_MINUTES - 1) * 60))
    rcon 'say Server restart in 1 minute. Find a safe spot.' >/dev/null || true
    sleep 60
}

# Starts the server again if this script stopped it. Also the exit trap, so an error, Ctrl+C, a dropped SSH
# connection or `systemctl stop` never leaves it down.
stopped=''
start_again() {
    [ -n "$stopped" ] || return 0
    stopped=''
    log 'starting the server again'
    if logged compose up -d realms && wait_for_live; then
        log 'the server is back up'
    else
        log "ERROR: the server did not answer within ${BOOT_TIMEOUT}s: look at docker compose logs realms"
        return 1
    fi
}
cleanup() {
    status=$?
    set +e
    trap - EXIT INT TERM HUP
    start_again || status=1
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

# The deploy lock: one at a time with deploys, the daily restart and off-site backups. Read-only: root may not
# open another user's file in /tmp for writing (fs.protected_regular), and flock works on any open file.
locked=''
take_lock() {
    [ -z "$locked" ] || return 0
    [ -e "$LOCK_FILE" ] || runuser -u "$SERVICE_USER" -- touch "$LOCK_FILE"
    exec 9<"$LOCK_FILE"
    log 'waiting for the deploy lock'
    flock -w 1800 9 || die 'a deploy, restart or backup has held the deploy lock for 30 minutes; try again later'
    locked=1
}

# The lines of FILE that set KEY, as "LINE:TEXT". Only these: the rest of the file is never printed.
setting_lines() { grep -n "^[[:space:]]*$KEY[[:space:]]*=" "$FILE" || true; }

# 'done' when the list names the shop block, 'todo' when it is a one-line list without it, 'missing' when the
# file doesn't set KEY (a newer mod renamed it) and 'by-hand' when the list is spread over several lines.
state() {
    found=$(setting_lines)
    case "$found" in
        '') echo missing ;;
        *"$BLOCK"*) echo 'done' ;;
        *)
            if [ "$(printf '%s\n' "$found" | wc -l)" -eq 1 ] &&
                printf '%s\n' "$found" | grep -q '=[[:space:]]*\[.*][[:space:]]*$'; then
                echo todo
            else
                echo by-hand
            fi ;;
    esac
}

show() { setting_lines | while IFS= read -r l; do log "  ${FILE#"$SERVER_DIR"/}:$l"; done; }

# Adds ENTRY at the end of the one-line list, as the file's owner so the file keeps its owner and mode.
edit() {
    owner=$(stat -c %U "$FILE")
    if [ -e "$BACKUP" ]; then
        log "keeping the earlier copy $BACKUP"
    else
        runuser -u "$owner" -- cp -p "$FILE" "$BACKUP"
        log "copied the file to $BACKUP"
    fi
    tmp=$(mktemp)
    awk -v key="$KEY" -v entry="$ENTRY" '
        !done && match($0, "^[ \t]*" key "[ \t]*=") && match($0, /][ \t]*$/) {
            head = substr($0, 1, RSTART - 1); tail = substr($0, RSTART)
            sep = (head ~ /\[[ \t]*$/) ? "" : ", "
            print head sep "\"" entry "\"" tail; done = 1; next
        }
        { print }
    ' "$FILE" >"$tmp"
    chmod 644 "$tmp"
    # shellcheck disable=SC2016  # $1 and $2 belong to the inner sh
    runuser -u "$owner" -- sh -c 'cat "$1" >"$2"' sh "$tmp" "$FILE"
    rm -f "$tmp"
}

# ---------------------------------------------------------------- checks (nothing changes yet)

for tool in docker flock runuser awk grep sed stat tail wc mktemp chmod; do
    command -v "$tool" >/dev/null || die "$tool is missing"
done
cd /
log "started ($MODE); log: $LOG"
[ -f "$LIVE_DIR/docker/compose.yaml" ] || die "$LIVE_DIR has no docker/compose.yaml (LIVE_DIR in $ENV_FILE?)"
shops=''
for jar in "$SERVER_DIR"/mods/universal_shops-*.jar; do
    [ ! -e "$jar" ] || shops=$jar
done
[ -n "$shops" ] ||
    die "Universal Shops isn't in $SERVER_DIR/mods: run this once the release with shops is live"
[ -f "$FILE" ] || die "no $FILE (has the server started once?)"

case "$(state)" in
    'done')
        log 'shops in claims: already set'
        show
        exit 0 ;;
    missing)
        die "the file has no $KEY setting, so a newer Open Parties and Claims renamed it: add \"$ENTRY\" by hand" \
            'with the server stopped (docs/LIVE.md, "Shops in claims")' ;;
    by-hand)
        log "shops in claims: $KEY isn't a one-line list; add \"$ENTRY\" to it by hand, server stopped:"
        show
        exit 1 ;;
esac
log 'shops in claims: to do; now:'
show
if [ "$MODE" = check ]; then
    log 'check finished: one restart to do (about 3 minutes offline); nothing was changed'
    exit 0
fi

# ---------------------------------------------------------------- the change

take_lock
was_running=''
if running; then
    [ "$MODE" = now ] || warn_players
    was_running=1
    stopped=1
    log 'stopping the server'
    logged compose stop realms
else
    log 'the server is not running: changing the file and leaving the server stopped'
fi
edit
show
[ "$(state)" = 'done' ] || die 'the change did not take (above); add the entry by hand, server stopped'
start_again
exec 9<&-  # deploys and backups may run again
locked=''

if [ -z "$was_running" ]; then
    log 'finished: shops in claims set; it takes effect when the server starts'
# Checked again with the server up: the mod writes its file back on start.
elif [ "$(state)" = 'done' ]; then
    log 'finished: shops in claims set'
    show
else
    log 'the mod dropped the change on start; add the entry by hand, server stopped:'
    show
    exit 1
fi
