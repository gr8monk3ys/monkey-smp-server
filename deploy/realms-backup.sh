#!/bin/sh
# Backs up the live server folder every hour, encrypted, to a Cloudflare R2 bucket with restic
# (docs/LIVE.md, "Backups off the machine"). realms-backup.timer runs it. It runs as root:
# /etc/realms-backup.env holds the R2 keys and the restic password, and only root may read it.
#
#   sh realms-backup.sh                  back up now (what the hourly timer runs)
#   sh realms-backup.sh --init           create the restic repository in the bucket (once; safe to repeat)
#   sh realms-backup.sh --save-on        turn saving back on if a backup was stopped before it could
#                                        (realms-backup.service runs this after every run)
#   sh realms-backup.sh --restic ARGS    run restic with these settings, e.g. --restic snapshots
#
# What a backup does:
#   1. waits for a deploy that is running (realms-deploy.sh backs up and restarts the server; the
#      two must not overlap), and holds the deploy lock until saving is back on
#   2. if the server answers RCON: save-off, save-all flush, so the world on disk is whole and stays
#      still. A server that is stopped or still starting is skipped that hour (and reported after 3
#      in a row).
#   3. restic backup of the live server folder (no jars, logs, libraries, BlueMap tiles or
#      session.lock, like `realms backup`) to R2: encrypted and compressed, only changed data is sent
#   4. save-on, also when restic failed or the run is stopped
#   5. restic forget: keeps 48 hourly, 14 daily, 8 weekly and 6 monthly snapshots; once a day,
#      prune deletes the data no snapshot needs any more
#   6. restic check --read-data-subset=5%: reads back a random 5% of the stored data and checks it
#   7. posts to Discord (DISCORD_WEBHOOK_URL in /etc/realms-deploy.env) when backups start failing
#      and when they work again, not every hour
#
# Settings come from /etc/realms-backup.env (or REALMS_BACKUP_ENV); see realms-backup.env.example.
# LIVE_DIR, the deploy lock and the webhook come from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=backup
. "$(dirname -- "$0")/lib.sh"

ENV_FILE=${REALMS_BACKUP_ENV:-/etc/realms-backup.env}
DEPLOY_ENV=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
STATE_DIR=/var/lib/realms-backup
BACKUP_LOCK=/run/realms-backup.lock
# The longest the server may go without saving while restic reads the world. The first backup sends
# the whole world; later ones only what changed, usually in a minute or two.
BACKUP_TIMEOUT=45m

mode=backup
if [ $# -gt 0 ]; then
    case "$1" in
        --init) mode=init ;;
        --save-on) mode=save-on ;;
        --restic) mode=restic ;;
        *) die "unknown option '$1' (use --init, --save-on or --restic ARGS)" ;;
    esac
    shift
    [ "$mode" = restic ] || [ $# -eq 0 ] || die "--$mode takes no arguments"
fi

[ "$(id -u)" = 0 ] || die "run this as root: only root may read $ENV_FILE"
cd /

LIVE_DIR=$(setting_in "$DEPLOY_ENV" LIVE_DIR /srv/realms/TheRealms-Server)
DEPLOY_LOCK=$(setting_in "$DEPLOY_ENV" LOCK_FILE /tmp/realms-deploy.lock)
WEBHOOK=$(setting_in "$DEPLOY_ENV" DISCORD_WEBHOOK_URL)
# Every snapshot holds this path; restores name it (docs/LIVE.md).
SERVER=$LIVE_DIR/server

if [ "$mode" = save-on ]; then
    # Needs no settings: only whether a backup left saving off.
    [ -e "$STATE_DIR/saving-off" ] || exit 0
    log 'a backup stopped before turning saving back on: save-on'
    rcon save-on >/dev/null || die 'save-on failed: run  docker compose exec realms realms rcon save-on'
    rm -f "$STATE_DIR/saving-off"
    exit 0
fi

[ -f "$ENV_FILE" ] ||
    die "$ENV_FILE is missing: copy deploy/realms-backup.env.example there and fill it in (docs/LIVE.md)"
case "$(stat -c '%u:%a' "$ENV_FILE")" in
    0:600 | 0:400) ;;
    *) log "WARNING: other users can read $ENV_FILE; make it root-only: chown root: $ENV_FILE && chmod 600 $ENV_FILE" ;;
esac
for key in RESTIC_REPOSITORY RESTIC_PASSWORD AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do
    value=$(setting_in "$ENV_FILE" "$key")
    [ -n "$value" ] || die "$key is empty in $ENV_FILE"
    export "$key=$value"
done
value=''
AWS_DEFAULT_REGION=$(setting_in "$ENV_FILE" AWS_DEFAULT_REGION auto)
RESTIC_CACHE_DIR=${RESTIC_CACHE_DIR:-/var/cache/realms-backup}
export AWS_DEFAULT_REGION RESTIC_CACHE_DIR
KEEP_HOURLY=$(setting_in "$ENV_FILE" KEEP_HOURLY 48)
KEEP_DAILY=$(setting_in "$ENV_FILE" KEEP_DAILY 14)
KEEP_WEEKLY=$(setting_in "$ENV_FILE" KEEP_WEEKLY 8)
KEEP_MONTHLY=$(setting_in "$ENV_FILE" KEEP_MONTHLY 6)
SNAPSHOT_HOST=$(setting_in "$ENV_FILE" SNAPSHOT_HOST monkey-smp)
for n in "$KEEP_HOURLY" "$KEEP_DAILY" "$KEEP_WEEKLY" "$KEEP_MONTHLY"; do
    case "$n" in
        '' | *[!0-9]*) die "KEEP_HOURLY, KEEP_DAILY, KEEP_WEEKLY and KEEP_MONTHLY must be whole numbers, not '$n'" ;;
    esac
done

command -v restic >/dev/null || die 'restic is not installed (docs/LIVE.md, "Backups off the machine")'
[ "$mode" != restic ] || exec restic "$@"

# One backup at a time.
exec 8>"$BACKUP_LOCK"
flock -w 3600 8 || die 'another backup has been running for an hour'
mkdir -p "$STATE_DIR"

# ---------------------------------------------------------------- helpers

discord() {
    [ -n "$WEBHOOK" ] || return 0
    # Our own words, minus any quote or backslash, so plain printf makes valid JSON.
    msg=$(printf '%s' "$1" | tr -d '"\\')
    printf '{"content":"%s"}' "$msg" |
        curl -fsS -m 15 -H 'Content-Type: application/json' -d @- "$WEBHOOK" >/dev/null ||
        log 'could not post to Discord'
}

save_on() {
    [ -e "$STATE_DIR/saving-off" ] || return 0
    if rcon save-on >/dev/null; then
        rm -f "$STATE_DIR/saving-off"
        log 'saving is on again'
    else
        # realms-backup.service tries again (--save-on) once this run has ended.
        log 'ERROR: save-on failed'
        return 1
    fi
}

ok=''
on_exit() {
    rc=$?
    save_on || rc=1
    [ "$mode" = backup ] || return 0
    # Post once when backups start failing and once when they work again, not every hour.
    if [ -n "$ok" ]; then
        if [ -e "$STATE_DIR/failing" ]; then
            rm -f "$STATE_DIR/failing"
            discord 'Monkey SMP off-site backups work again.'
        fi
    elif [ "$rc" != 0 ] && [ ! -e "$STATE_DIR/failing" ]; then
        touch "$STATE_DIR/failing"
        discord "Monkey SMP off-site backup FAILED: ${DIED:-see the log}. It tries again every hour. Check: journalctl -u realms-backup"
    fi
}
trap on_exit EXIT
# systemd stops a run that overruns with SIGTERM; exit through on_exit so saving goes back on.
trap 'exit 143' TERM INT HUP

# ---------------------------------------------------------------- init

init_repo() {
    rc=0
    err=$(restic cat config 2>&1 >/dev/null) || rc=$?
    case "$rc" in
        0) log 'the restic repository already exists' ;;
        10)
            restic init
            log 'created the restic repository. Keep RESTIC_PASSWORD somewhere off this VPS too: the backups cannot be read without it.'
            ;;
        *)
            printf '%s\n' "$err" >&2
            die "restic could not open the repository (exit code $rc, message above)"
            ;;
    esac
}

# ---------------------------------------------------------------- backup

backup() {
    # realms-deploy.sh holds its lock for a whole deploy, which backs up (its own save-off and
    # save-on) and recreates the container: wait for it, and keep it out until saving is back on.
    # (A deploy check that finds the lock taken tries again 5 minutes later.) Read-only is enough
    # for flock, and root may not open another user's file in /tmp for writing
    # (fs.protected_regular). No lock file means no deploy has run since boot.
    if [ -e "$DEPLOY_LOCK" ]; then
        deploy_lock 2700 "$DEPLOY_LOCK" || die 'a deploy has held its lock for 45 minutes'
    fi

    if ! rcon list >/dev/null; then
        skipped=$(cat "$STATE_DIR/skipped" 2>/dev/null || true)
        case "$skipped" in '' | *[!0-9]*) skipped=0 ;; esac
        skipped=$((skipped + 1))
        echo "$skipped" >"$STATE_DIR/skipped"
        [ "$skipped" -lt 3 ] || die "the server has not answered RCON for $skipped hours, so nothing has been backed up"
        log 'the server is not answering (stopped or still starting): nothing new to back up this hour'
        return 0
    fi
    rm -f "$STATE_DIR/skipped"
    [ -s "$SERVER/$(setting_in "$SERVER/server.properties" level-name world)/level.dat" ] ||
        die "there is no world with a level.dat in $SERVER"

    log 'save-off, save-all flush'
    touch "$STATE_DIR/saving-off"
    rcon save-off >/dev/null || die 'save-off failed'
    rcon 'save-all flush' >/dev/null || die 'save-all flush failed'
    sleep 3

    log "sending $SERVER to R2"
    rc=0
    timeout "$BACKUP_TIMEOUT" restic backup --host "$SNAPSHOT_HOST" --tag world \
        --exclude "$SERVER/libraries" --exclude "$SERVER/versions" --exclude "$SERVER/cache" \
        --exclude "$SERVER/logs" --exclude "$SERVER/bluemap" --exclude "$SERVER/plugins/.paper-remapped" \
        --exclude "$SERVER/.fabric" --exclude '*.jar' --exclude session.lock \
        "$SERVER" || rc=$?
    save_on || die 'save-on failed after the backup'
    exec 9<&-
    case "$rc" in
        0) ;;
        # Some files could not be read, usually a mod's temporary file that went away mid-backup.
        # The snapshot has everything else.
        3) log 'WARNING: restic could not read some files (named above); the snapshot has the rest' ;;
        124) die "restic took longer than $BACKUP_TIMEOUT, so it was stopped and saving is back on" ;;
        *) die "restic could not send the backup to R2 (exit code $rc)" ;;
    esac

    restic forget --quiet --host "$SNAPSHOT_HOST" --tag world --keep-hourly "$KEEP_HOURLY" \
        --keep-daily "$KEEP_DAILY" --keep-weekly "$KEEP_WEEKLY" --keep-monthly "$KEEP_MONTHLY" ||
        die 'restic forget failed'
    if [ -z "$(find "$STATE_DIR/pruned" -mmin -1380 2>/dev/null)" ]; then
        log 'pruning: deleting data that no snapshot needs any more (once a day)'
        restic prune || die 'restic prune failed'
        touch "$STATE_DIR/pruned"
    fi

    log 'reading back 5% of the stored data (restic check --read-data-subset=5%)'
    restic check --read-data-subset=5% || die 'restic check found a problem in the repository'
    ok=1
    log 'done: the world is in R2'
}

case "$mode" in
    init) init_repo ;;
    backup) backup ;;
esac
