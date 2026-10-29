#!/bin/sh
# The one-off step for the spawn NPCs on a live server installed before 2.9.1 (docs/LIVE.md, "NPCs in claims").
# defaults/config/openpartiesandclaims-server.toml ships
# `forcedEntityProtectionExceptionList = ["minecraft:minecart", "hand$easy_npc:*"]`, so anyone may right-click an
# Easy NPC (the Guide, the Town Crier) with an empty hand in any claim, spawn's server claim included. A deploy
# never overwrites the live server's own copy of that file, so this adds the entry there. Run it as root. Started
# with systemd-run it carries on if the SSH connection drops while the server is stopped:
#
#   systemd-run --unit=realms-npcs --collect -p TimeoutStopSec=20min sh /srv/realms/repo/deploy/npc-claims.sh
#   journalctl -fu realms-npcs
#
#   sh npc-claims.sh --check   says whether it is still to do, and changes nothing
#   sh npc-claims.sh --now     stops the server without the warning in chat
#
# When the list already names easy_npc: (with any prefix) it does nothing, so running it again is safe.
# Otherwise, under the deploy lock, with a warning in chat if players are online, it stops the server (Open
# Parties and Claims reads the setting only on start, and would write over a change made while it runs), copies
# the file to openpartiesandclaims-server.toml.before-npcs once, adds the entry, and starts the server again
# whatever happens. About 3 minutes offline. A list it can't edit safely (missing, or spread over several lines)
# is left for you to set by hand.
#
# It reads only LIVE_DIR, LOCK_FILE, WARN_MINUTES and BOOT_TIMEOUT from /etc/realms-deploy.env (or
# REALMS_DEPLOY_ENV), without sourcing it, so the webhooks are never read. RCON goes through the container's own
# `realms rcon`, which finds the password itself. No secret is read, printed or asked for. What it prints also
# goes to /var/log/realms-npc-claims.log (or NPCS_LOG), with the output of docker.
#
# A copy of deploy/shops-claims.sh for another key and entry: fix a bug in one, fix it in both.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=npc-claims
. "$(dirname -- "$0")/lib.sh"

case "${1:-}" in
    '') MODE=apply ;;
    --check) MODE=check ;;
    --now) MODE=now ;;
    *) echo "usage: sh $0 [--check | --now]" >&2; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || { echo 'run as root: it stops the server and edits its files as their owner' >&2; exit 1; }

ENV_FILE=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
LOG_TO=${NPCS_LOG:-/var/log/realms-npc-claims.log}

LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/realms/TheRealms-Server)}
LOCK_FILE=${LOCK_FILE:-$(setting LOCK_FILE /tmp/realms-deploy.lock)}
WARN_MINUTES=${WARN_MINUTES:-$(setting WARN_MINUTES 5)}
BOOT_TIMEOUT=${BOOT_TIMEOUT:-$(setting BOOT_TIMEOUT 900)}
whole_number WARN_MINUTES "$WARN_MINUTES" minutes
whole_number BOOT_TIMEOUT "$BOOT_TIMEOUT" seconds

SERVER_DIR=$LIVE_DIR/server
FILE=$SERVER_DIR/config/openpartiesandclaims-server.toml
BACKUP=$FILE.before-npcs
KEY=forcedEntityProtectionExceptionList
NAMESPACE='easy_npc:'
ENTRY="hand\$${NAMESPACE}*"  # the same entry as defaults/config/openpartiesandclaims-server.toml
SERVICE_USER=realms   # the owner of the deploy lock (docs/LIVE.md)

umask 022

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
    log 'waiting for the deploy lock'
    deploy_lock 1800 || die 'a deploy, restart or backup has held the deploy lock for 30 minutes; try again later'
    locked=1
}

# The lines of FILE that set KEY, as "LINE:TEXT". Only these: the rest of the file is never printed.
setting_lines() { grep -n "^[[:space:]]*$KEY[[:space:]]*=" "$FILE" || true; }

# 'done' when the list names an Easy NPC entity, 'todo' when it is a one-line list without it, 'missing' when the
# file doesn't set KEY (a newer mod renamed it) and 'by-hand' when the list is spread over several lines.
state() {
    found=$(setting_lines)
    case "$found" in
        '') echo missing ;;
        *"$NAMESPACE"*) echo 'done' ;;
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
log "started ($MODE); log: $LOG_TO"
[ -f "$LIVE_DIR/docker/compose.yaml" ] || die "$LIVE_DIR has no docker/compose.yaml (LIVE_DIR in $ENV_FILE?)"
npc=''
for jar in "$SERVER_DIR"/mods/easy_npc-*.jar; do
    [ ! -e "$jar" ] || npc=$jar
done
[ -n "$npc" ] ||
    die "Easy NPC isn't in $SERVER_DIR/mods: run this once a release with the spawn NPCs is live"
[ -f "$FILE" ] || die "no $FILE (has the server started once?)"

case "$(state)" in
    'done')
        log 'NPCs in claims: already set'
        show
        exit 0 ;;
    missing)
        die "the file has no $KEY setting, so a newer Open Parties and Claims renamed it: add \"$ENTRY\" by hand" \
            'with the server stopped (docs/LIVE.md, "NPCs in claims")' ;;
    by-hand)
        log "NPCs in claims: $KEY isn't a one-line list; add \"$ENTRY\" to it by hand, server stopped:"
        show
        exit 1 ;;
esac
log 'NPCs in claims: to do; now:'
show
if [ "$MODE" = check ]; then
    log 'check finished: one restart to do (about 3 minutes offline); nothing was changed'
    exit 0
fi

# ---------------------------------------------------------------- the change

take_lock
was_running=''
if running; then
    [ "$MODE" = now ] || warn_players 'Server restart' '' 'for a settings update (about 3 minutes offline)'
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
    log 'finished: NPCs in claims set; it takes effect when the server starts'
# Checked again with the server up: the mod writes its file back on start.
elif [ "$(state)" = 'done' ]; then
    log 'finished: NPCs in claims set'
    show
else
    log 'the mod dropped the change on start; add the entry by hand, server stopped:'
    show
    exit 1
fi
