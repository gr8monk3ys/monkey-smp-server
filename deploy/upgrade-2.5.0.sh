#!/bin/sh
# The one-off steps for 2.5.0 on the live VPS (docs/LIVE.md, "One-off steps when upgrading" and "Monitoring,
# the daily restart and the update check"). Run it as root once 2.5.0 is live, so the deployed checkout has the
# timer files and the server has the short rules. Started with systemd-run it carries on if the SSH connection
# drops while the server is stopped:
#
#   systemd-run --unit=monkey-upgrade --collect -p TimeoutStopSec=20min sh /srv/monkey/repo/deploy/upgrade-2.5.0.sh
#   journalctl -fu monkey-upgrade
#
#   sh upgrade-2.5.0.sh --check   says what is still to do, and changes nothing
#   sh upgrade-2.5.0.sh --now     stops the server without the warning in chat
#
# Each step is skipped when it is already done, so running it again is safe:
#   1. installs python3 if it is missing (the weekly update check needs 3.10 or newer)
#   2. changes the settings the live server's own copies of these files still have off, all with one stop:
#        config/DistantHorizons.toml          no server-side LODs (they carry the real ores)
#        server.properties                    enable-code-of-conduct=true (the short rules)
#        config/servercore/config.yml         the breeding cap and villager lobotomization
#        config/openpartiesandclaims-server.toml  maxPlayerClaims = 4
#      Under the deploy lock, with a warning in chat if players are online, the server stopped (the mods would
#      write over the change), a copy of each file first (DistantHorizons.toml.before-2.5.0, the others
#      *.pre-onboarding as in docs/LIVE.md), and the server started again whatever happens. About 3 minutes
#      offline.
#   3. the no-PvP server claim over the 7 x 7 chunks around spawn, through RCON with the server up
#   4. installs monkey-restart.timer and monkey-updates.timer from the deployed checkout and starts them
# The off-site backups (monkey-backup.sh) are not here: they need keys the owner makes (docs/LIVE.md).
#
# It reads only REPO_DIR, LIVE_DIR, LOCK_FILE, WARN_MINUTES and BOOT_TIMEOUT from /etc/monkey-deploy.env (or
# MONKEY_DEPLOY_ENV), without sourcing it, so the webhooks are never read. RCON goes through the container's own
# `monkey rcon`, which finds the password itself. Of server.properties it reads and prints only the
# enable-code-of-conduct line, never rcon.password. No secret is read, printed or asked for. What it prints also
# goes to /var/log/monkey-upgrade-2.5.0.log (or UPGRADE_LOG), with the output of apt-get, systemctl and docker.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=upgrade-2.5.0
. "$(dirname -- "$0")/lib.sh"

case "${1:-}" in
    '') MODE=apply ;;
    --check) MODE=check ;;
    --now) MODE=now ;;
    *) echo "usage: sh $0 [--check | --now]" >&2; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || { echo 'run as root: it installs packages and timers and stops the server' >&2; exit 1; }

ENV_FILE=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
LOG_TO=${UPGRADE_LOG:-/var/log/monkey-upgrade-2.5.0.log}

REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/monkey/repo)}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/monkey/MonkeySMP-Server)}
LOCK_FILE=${LOCK_FILE:-$(setting LOCK_FILE /tmp/monkey-deploy.lock)}
WARN_MINUTES=${WARN_MINUTES:-$(setting WARN_MINUTES 5)}
BOOT_TIMEOUT=${BOOT_TIMEOUT:-$(setting BOOT_TIMEOUT 900)}
case "$WARN_MINUTES" in '' | *[!0-9]*) WARN_MINUTES=5 ;; esac
case "$BOOT_TIMEOUT" in '' | *[!0-9]*) BOOT_TIMEOUT=900 ;; esac

SERVER_DIR=$LIVE_DIR/server
# The settings, one per line: FILE|KEY|VALUE, FILE in the server folder. KEY is NAME for a "NAME = value" line
# (TOML, server.properties) or BLOCK.NAME for "NAME: value" directly inside the YAML block BLOCK.
SETTINGS='config/DistantHorizons.toml|synchronizeOnLoad|false
config/DistantHorizons.toml|enableRealTimeUpdates|false
config/DistantHorizons.toml|generatorPlan|"DISABLED"
server.properties|enable-code-of-conduct|true
config/servercore/config.yml|lobotomize-villagers.enabled|true
config/servercore/config.yml|breeding-cap.enabled|true
config/openpartiesandclaims-server.toml|maxPlayerClaims|4'
FILES='config/DistantHorizons.toml server.properties config/servercore/config.yml config/openpartiesandclaims-server.toml'
CONDUCT=$SERVER_DIR/codeofconduct/en_us.txt  # what enable-code-of-conduct shows; 2.5.0 brings it
# docs/LIVE.md, "The short rules, ServerCore and claims": PvP off in server claims, then the server claims the
# 7 x 7 chunks around the world spawn (the console's ~ ~), skipping chunks a player already claimed.
CLAIM_COMMANDS='opac server-claims-config set claims.protection.exceptions.playersByPlayers false
oclaims server claim in minecraft:overworld ~-48 ~-48 ~48 ~48'
# Written once the claim commands went through. The claim belongs to this world: a new world needs it again
# (the admin notes in docs/RULES.md), and this file doesn't know about that.
CLAIM_MARK=${CLAIM_MARK:-/var/lib/monkey-upgrade/2.5.0-spawn-claim}
UNITS='monkey-restart.service monkey-restart.timer monkey-updates.service monkey-updates.timer'
TIMERS='monkey-restart.timer monkey-updates.timer'
SERVICE_USER=monkey  # User= in the two .service files
TAB=$(printf '\t')

umask 022

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

todo=0      # --check: steps still to do
problems=0  # steps that need a look by hand

# ---------------------------------------------------------------- checks (nothing changes yet)

for tool in docker flock runuser systemctl apt-get install awk cmp stat sed grep cut tail; do
    command -v "$tool" >/dev/null || die "$tool is missing"
done
cd /
log "started ($MODE); log: $LOG_TO"
[ -f "$LIVE_DIR/docker/compose.yaml" ] || die "$LIVE_DIR has no docker/compose.yaml (LIVE_DIR in $ENV_FILE?)"
for u in $UNITS monkey-updates.sh; do
    [ -f "$REPO_DIR/deploy/$u" ] ||
        die "$REPO_DIR/deploy has no $u: the deployed release is older than 2.5.0; run this once 2.5.0 is live"
done
[ -f "$REPO_DIR/tools/check_updates.py" ] || die "$REPO_DIR has no tools/check_updates.py"
if ! runuser -u "$SERVICE_USER" -- test -r "$ENV_FILE"; then
    log "WARNING: $SERVICE_USER can't read $ENV_FILE, which the timers' services need. As root:" \
        "chown root:$SERVICE_USER $ENV_FILE && chmod 640 $ENV_FILE"
    problems=$((problems + 1))
fi

# The deploy lock: one at a time with deploys, the daily restart and off-site backups. Read-only: root may not
# open another user's file in /tmp for writing (fs.protected_regular), and flock works on any open file.
locked=''
take_lock() {
    [ -z "$locked" ] || return 0
    log 'waiting for the deploy lock'
    deploy_lock 1800 || die 'a deploy, restart or backup has held the deploy lock for 30 minutes; try again later'
    locked=1
}

# ---------------------------------------------------------------- 1. python3

if python_ok 10; then
    log "python3: already installed ($(python3 --version 2>&1))"
elif [ "$MODE" = check ]; then
    log 'python3: to do (missing, or older than 3.10)'
    todo=$((todo + 1))
else
    log 'python3: installing'
    export DEBIAN_FRONTEND=noninteractive
    logged apt-get install -y --no-install-recommends python3 ||
        { logged apt-get update && logged apt-get install -y --no-install-recommends python3; } ||
        die "apt-get could not install python3 (see $LOG_TO)"
    python_ok 10 || die "python3 is installed but older than 3.10: $(python3 --version 2>&1)"
    log "python3: installed ($(python3 --version 2>&1))"
fi

# ---------------------------------------------------------------- 2. the settings

# "locate FILE KEY": a "LINE<tab>VALUE" line for each line of FILE that sets KEY (see SETTINGS), nothing else.
locate() {
    awk -v key="$2" '
        function indent(s) { match(s, /^[ \t]*/); return RLENGTH }
        # The value after the match just made (RSTART, RLENGTH), without a trailing comment.
        function value(s) { s = substr(s, RLENGTH + 1); sub(/^[ \t]*/, "", s); sub(/[ \t]*(#.*)?$/, "", s); return s }
        BEGIN { dot = index(key, "."); parent = substr(key, 1, dot - 1); name = substr(key, dot + 1) }
        !dot { if (match($0, "^[ \t]*" key "[ \t]*=")) print NR "\t" value($0); next }
        /^[ \t]*(#.*)?$/ { next }
        inside && indent($0) <= depth { inside = 0 }
        inside && child < 0 { child = indent($0) }
        inside && indent($0) == child && match($0, "^[ \t]*" name ":") { print NR "\t" value($0); next }
        !inside && match($0, "^[ \t]*" parent ":[ \t]*(#.*)?$") { inside = 1; depth = indent($0); child = -1 }
    ' "$1"
}

backup_of() {
    case "$1" in
        *DistantHorizons.toml) echo "$1.before-2.5.0" ;;
        *) echo "$1.pre-onboarding" ;;  # the name docs/LIVE.md uses
    esac
}

# "file_state FILE": 'done' when every setting in FILE has its value, todo when one doesn't, and "missing KEY"
# when FILE has no line for KEY (a newer mod renamed it: set it by hand). server.properties may lack the line:
# it is added.
file_state() {
    state='done'
    while IFS='|' read -r s_file key value; do
        [ "$s_file" = "$1" ] || continue
        found=$(locate "$SERVER_DIR/$1" "$key")
        if [ -z "$found" ]; then
            case "$1" in
                *.properties) state=todo; continue ;;
                *) echo "missing $key"; return 0 ;;
            esac
        fi
        if printf '%s\n' "$found" | cut -f 2 | grep -qvxF -- "$value"; then state=todo; fi
    done <<EOF
$SETTINGS
EOF
    echo "$state"
}

# Logs what FILE's settings read. Only those lines: server.properties also holds the RCON password.
file_lines() {
    while IFS='|' read -r s_file key value; do
        [ "$s_file" = "$1" ] || continue
        locate "$SERVER_DIR/$1" "$key" | while IFS="$TAB" read -r n v; do log "  $1:$n: $key = $v"; done
    done <<EOF
$SETTINGS
EOF
}

# Sets FILE's settings, as the file's owner so the file keeps its owner.
file_edit() {
    path=$SERVER_DIR/$1
    owner=$(stat -c %U "$path")
    backup=$(backup_of "$path")
    if [ -e "$backup" ]; then
        log "  keeping the earlier copy $backup"
    else
        runuser -u "$owner" -- cp -p "$path" "$backup"
        log "  copied $1 to $backup"
    fi
    while IFS='|' read -r s_file key value; do
        [ "$s_file" = "$1" ] || continue
        found=$(locate "$path" "$key")
        if [ -z "$found" ]; then  # only server.properties gets here (file_state)
            runuser -u "$owner" -- sh -c '[ -z "$(tail -c 1 "$2")" ] || echo >>"$2"; printf "%s\n" "$1" >>"$2"' \
                sh "$key=$value" "$path"
            continue
        fi
        case "$key" in
            *.*) sep=':' ;;
            *) sep='=' ;;
        esac
        for n in $(printf '%s\n' "$found" | cut -f 1); do
            runuser -u "$owner" -- sed -i "${n}s/^\([[:space:]]*${key#*.}[[:space:]]*$sep[[:space:]]*\).*/\1$value/" "$path"
        done
    done <<EOF
$SETTINGS
EOF
}

label() {
    case "$1" in
        *DistantHorizons.toml) echo 'Distant Horizons (no server-side LODs)' ;;
        server.properties) echo 'the Code of Conduct' ;;
        *servercore*) echo 'ServerCore (breeding cap, villager lobotomization)' ;;
        *) echo 'Open Parties and Claims (4 chunks per player)' ;;
    esac
}

pending=''  # the files to change
for f in $FILES; do
    if [ ! -f "$SERVER_DIR/$f" ]; then
        log "$(label "$f"): no $SERVER_DIR/$f (has the server started once with this mod?): look by hand"
        problems=$((problems + 1))
        continue
    fi
    if [ "$f" = server.properties ] && [ ! -f "$CONDUCT" ]; then
        log "$(label "$f"): not turned on, as there is no $CONDUCT to show: is 2.5.0 live?"
        problems=$((problems + 1))
        continue
    fi
    state=$(file_state "$f")
    case "$state" in
        'done')
            log "$(label "$f"): already set" ;;
        missing*)
            log "$(label "$f"): $f has no ${state#missing } setting, so a newer mod renamed it: set it by hand" \
                'with the server stopped (docs/LIVE.md, "One-off steps when upgrading")'
            problems=$((problems + 1)) ;;
        *)
            log "$(label "$f"): to do; now:"
            file_lines "$f"
            pending="$pending $f" ;;
    esac
done

if [ -z "$pending" ]; then
    :
elif [ "$MODE" = check ]; then
    log 'settings: to do (one restart, about 3 minutes offline)'
    todo=$((todo + 1))
else
    take_lock
    if running; then
        [ "$MODE" = now ] || warn_players
        stopped=1
        log 'stopping the server'
        logged compose stop monkey
    else
        log 'the server is not running: changing the files and leaving the server stopped'
    fi
    for f in $pending; do
        log "$(label "$f"): changing $f"
        file_edit "$f"
        file_lines "$f"
    done
    start_again
    # Checked again with the server up, as the mods write their files on start.
    for f in $pending; do
        if [ "$(file_state "$f")" = 'done' ]; then
            log "$(label "$f"): set"
        else
            log "$(label "$f"): the change did not take; set it by hand:"
            file_lines "$f"
            problems=$((problems + 1))
        fi
    done
fi

# ---------------------------------------------------------------- 3. the spawn claim

if [ -e "$CLAIM_MARK" ]; then
    log "spawn claim: already made ($CLAIM_MARK)"
elif [ "$MODE" = check ]; then
    log 'spawn claim: to do (two console commands with the server up; safe to repeat if it was made by hand)'
    todo=$((todo + 1))
elif ! running; then
    log 'spawn claim: the server is not running; start it and run this again'
    problems=$((problems + 1))
else
    take_lock
    failed=''
    while IFS= read -r cmd; do
        log "spawn claim: $cmd"
        if out=$(rcon "$cmd"); then
            printf '%s\n' "$out" | while IFS= read -r l; do [ -z "$l" ] || log "  $l"; done
            case "$out" in *'Unknown or incomplete command'* | *'Incorrect argument'* | *'<--[HERE]'*) failed=1 ;; esac
        else
            log '  RCON did not answer'
            failed=1
        fi
    done <<EOF
$CLAIM_COMMANDS
EOF
    if [ -n "$failed" ]; then
        log 'spawn claim: a command failed (above); run them by hand (docs/LIVE.md)'
        problems=$((problems + 1))
    else
        mkdir -p "$(dirname "$CLAIM_MARK")"
        date '+%Y-%m-%d %H:%M:%S' >"$CLAIM_MARK"
        log 'spawn claim: made (it fills in over a few seconds)'
    fi
fi
if [ -n "$locked" ]; then
    exec 9<&-  # deploys and backups may run again
    locked=''
fi

# ---------------------------------------------------------------- 4. the timers

# $UNITS is a list of unit names.
# shellcheck disable=SC2086
changed=$(changed_units $UNITS)
idle=''
for t in $TIMERS; do
    timer_running "$t" || idle="$idle $t"
done
if [ -z "$changed$idle" ]; then
    log 'timers: already installed and running'
elif [ "$MODE" = check ]; then
    log "timers: to do (copy:${changed:- none}; start:${idle:- none})"
    todo=$((todo + 1))
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
fi
# shellcheck disable=SC2086
systemctl list-timers --all --no-pager $TIMERS 2>&1 | while IFS= read -r l; do log "  $l"; done

# ---------------------------------------------------------------- done

if [ "$problems" -gt 0 ]; then
    log "finished: $problems thing(s) need a look by hand (above)"
    exit 1
elif [ "$MODE" = check ]; then
    log "check finished: $todo step(s) to do; nothing was changed"
else
    log 'finished: all steps done'
fi
