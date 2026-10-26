#!/bin/sh
# The one-off steps for 2.5.0 on the live VPS (docs/LIVE.md, "One-off steps when upgrading" and "Monitoring,
# the daily restart and the update check"). Run it as root once 2.5.0 is live, so the deployed checkout has the
# timer files. Started with systemd-run it carries on if the SSH connection drops while the server is stopped:
#
#   systemd-run --unit=realms-upgrade --collect -p TimeoutStopSec=20min sh /srv/realms/repo/deploy/upgrade-2.5.0.sh
#   journalctl -fu realms-upgrade
#
#   sh upgrade-2.5.0.sh --check   says what is still to do, and changes nothing
#   sh upgrade-2.5.0.sh --now     stops the server without the warning in chat
#
# Each step is skipped when it is already done, so running it again is safe:
#   1. installs python3 if it is missing (the weekly update check needs 3.10 or newer)
#   2. turns off Distant Horizons' server-side LODs, which carry the real ores, in DistantHorizons.toml: under
#      the deploy lock, with a warning in chat if players are online, the server stopped (Distant Horizons
#      would write over the change), a copy of the file first (DistantHorizons.toml.before-2.5.0), and the
#      server started again whatever happens. About 3 minutes offline.
#   3. installs realms-restart.timer and realms-updates.timer from the deployed checkout and starts them
# The off-site backups (realms-backup.sh) are not here: they need keys the owner makes (docs/LIVE.md).
#
# It reads only REPO_DIR, LIVE_DIR, LOCK_FILE, WARN_MINUTES and BOOT_TIMEOUT from /etc/realms-deploy.env (or
# REALMS_DEPLOY_ENV), without sourcing it, so the webhooks are never read. RCON goes through the container's own
# `realms rcon`, which finds the password itself. No secret is read, printed or asked for. What it prints also
# goes to /var/log/realms-upgrade-2.5.0.log (or UPGRADE_LOG), with the output of apt-get, systemctl and docker.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

case "${1:-}" in
    '') MODE=apply ;;
    --check) MODE=check ;;
    --now) MODE=now ;;
    *) echo "usage: sh $0 [--check | --now]" >&2; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || { echo 'run as root: it installs packages and timers and stops the server' >&2; exit 1; }

ENV_FILE=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
LOG=${UPGRADE_LOG:-/var/log/realms-upgrade-2.5.0.log}

# "setting NAME DEFAULT": NAME's value in the env file (the last one, quotes dropped), else DEFAULT.
setting() {
    v=''
    [ ! -r "$ENV_FILE" ] ||
        v=$(sed -n "s/^[[:space:]]*$1=//p" "$ENV_FILE" | tail -n 1 | sed -e 's/[[:space:]]*$//' -e "s/^[\"']//" -e "s/[\"']\$//")
    printf '%s' "${v:-$2}"
}
REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/realms/repo)}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/realms/TheRealms-Server)}
LOCK_FILE=${LOCK_FILE:-$(setting LOCK_FILE /tmp/realms-deploy.lock)}
WARN_MINUTES=${WARN_MINUTES:-$(setting WARN_MINUTES 5)}
BOOT_TIMEOUT=${BOOT_TIMEOUT:-$(setting BOOT_TIMEOUT 900)}
case "$WARN_MINUTES" in '' | *[!0-9]*) WARN_MINUTES=5 ;; esac
case "$BOOT_TIMEOUT" in '' | *[!0-9]*) BOOT_TIMEOUT=900 ;; esac

DH_FILE=$LIVE_DIR/server/config/DistantHorizons.toml
DH_BACKUP=$DH_FILE.before-2.5.0
# The settings that send Distant Horizons' LODs (and the ores in them) to players, and the value each needs.
DH_SETTINGS='synchronizeOnLoad=false enableRealTimeUpdates=false generatorPlan="DISABLED"'
UNITS='realms-restart.service realms-restart.timer realms-updates.service realms-updates.timer'
TIMERS='realms-restart.timer realms-updates.timer'
SERVICE_USER=realms  # User= in the two .service files

umask 022
log() {
    line="$(date '+%Y-%m-%d %H:%M:%S') [upgrade-2.5.0] $*"
    printf '%s\n' "$line" >>"$LOG"
    printf '%s\n' "$line"
}
die() { log "ERROR: $*"; exit 1; }
# Runs a command with its output in the log file only.
logged() { "$@" >>"$LOG" 2>&1; }

compose() { docker compose --project-directory "$LIVE_DIR/docker" -f "$LIVE_DIR/docker/compose.yaml" "$@"; }
running() { [ -n "$(compose ps -q --status running realms 2>/dev/null)" ]; }
rcon() { compose exec -T realms realms rcon "$1" 2>/dev/null; }

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
    rcon "say Server restart in $WARN_MINUTES minutes (about 3 minutes offline)." >/dev/null || true
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

todo=0      # --check: steps still to do
problems=0  # steps that need a look by hand

# ---------------------------------------------------------------- checks (nothing changes yet)

for tool in docker flock runuser systemctl apt-get install cmp stat sed grep; do
    command -v "$tool" >/dev/null || die "$tool is missing"
done
cd /
log "started ($MODE); log: $LOG"
[ -f "$LIVE_DIR/docker/compose.yaml" ] || die "$LIVE_DIR has no docker/compose.yaml (LIVE_DIR in $ENV_FILE?)"
for u in $UNITS realms-updates.sh; do
    [ -f "$REPO_DIR/deploy/$u" ] ||
        die "$REPO_DIR/deploy has no $u: the deployed release is older than 2.5.0; run this once 2.5.0 is live"
done
[ -f "$REPO_DIR/tools/check_updates.py" ] || die "$REPO_DIR has no tools/check_updates.py"
if ! runuser -u "$SERVICE_USER" -- test -r "$ENV_FILE"; then
    log "WARNING: $SERVICE_USER can't read $ENV_FILE, which the timers' services need. As root:" \
        "chown root:$SERVICE_USER $ENV_FILE && chmod 640 $ENV_FILE"
    problems=$((problems + 1))
fi

# ---------------------------------------------------------------- 1. python3

python_ok() { python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; }
if python_ok; then
    log "python3: already installed ($(python3 --version 2>&1))"
elif [ "$MODE" = check ]; then
    log 'python3: to do (missing, or older than 3.10)'
    todo=$((todo + 1))
else
    log 'python3: installing'
    export DEBIAN_FRONTEND=noninteractive
    logged apt-get install -y --no-install-recommends python3 ||
        { logged apt-get update && logged apt-get install -y --no-install-recommends python3; } ||
        die "apt-get could not install python3 (see $LOG)"
    python_ok || die "python3 is installed but older than 3.10: $(python3 --version 2>&1)"
    log "python3: installed ($(python3 --version 2>&1))"
fi

# ---------------------------------------------------------------- 2. Distant Horizons

# "done" when every line that sets one of DH_SETTINGS has its value, "todo" when one doesn't, and "missing
# NAME" when the file has no line for NAME (a newer Distant Horizons renamed it: set it by hand).
dh_state() {
    state='done'
    for kv in $DH_SETTINGS; do
        key=${kv%%=*}
        all=$(grep -cE "^[[:space:]]*${key}[[:space:]]*=" "$DH_FILE" || true)
        good=$(grep -cE "^[[:space:]]*${key}[[:space:]]*=[[:space:]]*${kv#*=}[[:space:]]*(#.*)?\$" "$DH_FILE" || true)
        if [ "$all" -eq 0 ]; then
            echo "missing $key"
            return 0
        fi
        [ "$good" = "$all" ] || state=todo
    done
    echo "$state"
}

# The same edit as docs/LIVE.md, made by the file's owner so the file keeps its owner.
dh_edit() {
    set --
    for kv in $DH_SETTINGS; do
        set -- "$@" -e "s/^\([[:space:]]*${kv%%=*}[[:space:]]*=\).*/\1 ${kv#*=}/"
    done
    runuser -u "$owner" -- sed -i "$@" "$DH_FILE"
}

dh_lines() {
    keys=$(for kv in $DH_SETTINGS; do printf '%s|' "${kv%%=*}"; done)
    grep -nE "^[[:space:]]*(${keys%|})[[:space:]]*=" "$DH_FILE" | while IFS= read -r l; do log "  $l"; done
}

if [ ! -f "$DH_FILE" ]; then
    log "Distant Horizons: no $DH_FILE (has the server started once with Distant Horizons?): look by hand"
    problems=$((problems + 1))
else
    state=$(dh_state)
    case "$state" in
        'done')
            log 'Distant Horizons: server-side LODs already off' ;;
        missing*)
            log "Distant Horizons: $DH_FILE has no ${state#missing } setting, so a newer Distant Horizons renamed" \
                'it: set it by hand with the server stopped (docs/LIVE.md, "One-off steps when upgrading")'
            problems=$((problems + 1)) ;;
        *)
            if [ "$MODE" = check ]; then
                log 'Distant Horizons: to do (server-side LODs are on; needs about 3 minutes offline):'
                dh_lines
                todo=$((todo + 1))
            else
                owner=$(stat -c %U "$DH_FILE")
                # One at a time with deploys, the daily restart and off-site backups. Read-only: root may not
                # open another user's file in /tmp for writing (fs.protected_regular), and flock works on any
                # open file.
                [ -e "$LOCK_FILE" ] || runuser -u "$owner" -- touch "$LOCK_FILE"
                exec 9<"$LOCK_FILE"
                log 'Distant Horizons: waiting for the deploy lock'
                flock -w 1800 9 || die 'a deploy, restart or backup has held the deploy lock for 30 minutes; try again later'
                if running; then
                    [ "$MODE" = now ] || warn_players
                    stopped=1
                    log 'stopping the server'
                    logged compose stop realms
                else
                    log 'the server is not running: changing the file and leaving the server stopped'
                fi
                if [ -e "$DH_BACKUP" ]; then
                    log "keeping the earlier copy $DH_BACKUP"
                else
                    runuser -u "$owner" -- cp -p "$DH_FILE" "$DH_BACKUP"
                    log "copied the file to $DH_BACKUP"
                fi
                dh_edit
                log 'Distant Horizons: the settings now read:'
                dh_lines
                state=$(dh_state)
                if [ "$state" = 'done' ]; then
                    log 'Distant Horizons: server-side LODs off'
                else
                    log "Distant Horizons: the change did not take ($state): set the settings by hand"
                    problems=$((problems + 1))
                fi
                start_again
                exec 9<&-  # deploys and backups may run again
            fi ;;
    esac
fi

# ---------------------------------------------------------------- 3. the timers

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
