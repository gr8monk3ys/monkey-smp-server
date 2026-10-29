# The body of the one-off "X in claims" steps (deploy/npc-claims.sh, deploy/shops-claims.sh): adds entries to one of
# Open Parties and Claims' exception lists in the live server's own openpartiesandclaims-server.toml, which a deploy
# never overwrites. Sourced, never run: after `set -eu`, LOG_NAME and lib.sh, the script sets
#
#   WHAT       what its log lines call the step ("NPCs in claims"), also the docs/LIVE.md section
#   LOG_TO     its log file
#   KEEP_AS    the suffix of the copy of the file kept before the change (before-npcs)
#   KEY        the list's setting, e.g. forcedEntityProtectionExceptionList
#   ENTRIES    the entries, as in defaults/config/openpartiesandclaims-server.toml, separated by spaces (no
#              spaces, quotes or wildcards in one)
#   MOD, JARS  the mod the entries are for, and a glob of its jar in server/mods
#   NOT_YET    when to run it, for when the jar isn't there yet ("a release with the spawn NPCs is live")
#
# then sources this. When the list holds every entry it does nothing, so running it again is safe. Otherwise,
# under the deploy lock, with a warning in chat if players are online, it stops the server (the mod reads the
# setting only on start, and would write over a change made while it runs), copies the file to KEEP_AS once, adds
# the missing entries, and starts the server again whatever happens. About 3 minutes offline. A list it can't edit
# safely (missing, or spread over several lines) is left for you to set by hand.
#
# It reads only LIVE_DIR, LOCK_FILE, WARN_MINUTES and BOOT_TIMEOUT from /etc/monkey-deploy.env (or
# MONKEY_DEPLOY_ENV), without sourcing it, so the webhooks are never read. RCON goes through the container's own
# `monkey rcon`, which finds the password itself. No secret is read, printed or asked for. What it prints also
# goes to LOG_TO, with the output of docker.
#
# Plain POSIX sh, LF line endings, plain ASCII.

case "${1:-}" in
    '') MODE=apply ;;
    --check) MODE=check ;;
    --now) MODE=now ;;
    *) echo "usage: sh $0 [--check | --now]" >&2; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || { echo 'run as root: it stops the server and edits its files as their owner' >&2; exit 1; }

ENV_FILE=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}

LIVE_DIR=$(absolute "${LIVE_DIR:-$(setting LIVE_DIR /srv/monkey/MonkeySMP-Server)}")
LOCK_FILE=${LOCK_FILE:-$(setting LOCK_FILE /tmp/monkey-deploy.lock)}
WARN_MINUTES=${WARN_MINUTES:-$(setting WARN_MINUTES 5)}
BOOT_TIMEOUT=${BOOT_TIMEOUT:-$(setting BOOT_TIMEOUT 900)}
whole_number WARN_MINUTES "$WARN_MINUTES" minutes
whole_number BOOT_TIMEOUT "$BOOT_TIMEOUT" seconds

SERVER_DIR=$LIVE_DIR/server
FILE=$SERVER_DIR/config/openpartiesandclaims-server.toml
BACKUP=$FILE.$KEEP_AS
SERVICE_USER=monkey   # the owner of the deploy lock (docs/LIVE.md)

umask 022

# Starts the server again if this script stopped it. Also the exit trap, so an error, Ctrl+C, a dropped SSH
# connection or `systemctl stop` never leaves it down.
stopped=''
start_again() {
    [ -n "$stopped" ] || return 0
    stopped=''
    log 'starting the server again'
    if logged compose up -d monkey && wait_for_live; then
        log 'the server is back up'
    else
        log "ERROR: the server did not answer within ${BOOT_TIMEOUT}s: look at docker compose logs monkey"
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

# The entries the list doesn't hold yet, each quoted and followed by ", ". Only the exact entry counts: another
# prefix (`break$`) or a narrower id leaves it to do.
missing() {
    found=$(setting_lines)
    for entry in $ENTRIES; do
        case "$found" in *"\"$entry\""*) ;; *) printf '"%s", ' "$entry" ;; esac
    done
}

# 'done' when the list holds every entry, 'todo' when it is a one-line list missing some, 'missing' when the file
# doesn't set KEY (a newer mod renamed it) and 'by-hand' when the list is spread over several lines.
state() {
    found=$(setting_lines)
    if [ -z "$found" ]; then
        echo missing
    elif [ -z "$(missing)" ]; then
        echo 'done'
    elif [ "$(printf '%s\n' "$found" | wc -l)" -eq 1 ] &&
        printf '%s\n' "$found" | grep -q '=[[:space:]]*\[.*][[:space:]]*$'; then
        echo todo
    else
        echo by-hand
    fi
}

show() { setting_lines | while IFS= read -r l; do log "  ${FILE#"$SERVER_DIR"/}:$l"; done; }

# Adds the missing entries at the end of the one-line list, as the file's owner so the file keeps its owner and
# mode.
edit() {
    owner=$(stat -c %U "$FILE")
    if [ -e "$BACKUP" ]; then
        log "keeping the earlier copy $BACKUP"
    else
        runuser -u "$owner" -- cp -p "$FILE" "$BACKUP"
        log "copied the file to $BACKUP"
    fi
    add=$(missing)
    tmp=$(mktemp)
    awk -v key="$KEY" -v add="${add%, }" '
        !done && match($0, "^[ \t]*" key "[ \t]*=") && match($0, /][ \t]*$/) {
            head = substr($0, 1, RSTART - 1); tail = substr($0, RSTART)
            sep = (head ~ /\[[ \t]*$/) ? "" : ", "
            print head sep add tail; done = 1; next
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
jar=''
for found_jar in "$SERVER_DIR"/mods/$JARS; do
    [ ! -e "$found_jar" ] || jar=$found_jar
done
[ -n "$jar" ] || die "$MOD isn't in $SERVER_DIR/mods: run this once $NOT_YET"
[ -f "$FILE" ] || die "no $FILE (has the server started once?)"

case "$(state)" in
    'done')
        log "$WHAT: already set"
        show
        exit 0 ;;
    missing)
        add=$(missing)
        die "the file has no $KEY setting, so a newer Open Parties and Claims renamed it: add ${add%, } to it by" \
            "hand with the server stopped (docs/LIVE.md, \"$WHAT\")" ;;
    by-hand)
        add=$(missing)
        log "$WHAT: $KEY isn't a one-line list; add ${add%, } to it by hand, server stopped:"
        show
        exit 1 ;;
esac
log "$WHAT: to do; now:"
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
    logged compose stop monkey
else
    log 'the server is not running: changing the file and leaving the server stopped'
fi
edit
show
[ "$(state)" = 'done' ] || die 'the change did not take (above); add the entries by hand, server stopped'
start_again
exec 9<&-  # deploys and backups may run again
locked=''

if [ -z "$was_running" ]; then
    log "finished: $WHAT set; it takes effect when the server starts"
# Checked again with the server up: the mod writes its file back on start.
elif [ "$(state)" = 'done' ]; then
    log "finished: $WHAT set"
    show
else
    log 'the mod dropped the change on start; add the entries by hand, server stopped:'
    show
    exit 1
fi
