#!/bin/sh
# Backs up the live world every hour and copies it off the VPS, encrypted, to a Cloudflare R2 bucket
# with restic (docs/LIVE.md, "Backups off the machine"). realms-backup.timer runs it every hour and
# realms-restore-test.timer once a month with --restore-test. It runs as root: /etc/realms-backup.env
# holds the R2 keys and the restic password, and only root may read it.
#
#   sh realms-backup.sh                  back up now (what the hourly timer runs)
#   sh realms-backup.sh --init           create the restic repository in the bucket (once; safe to repeat)
#   sh realms-backup.sh --restore-test   restore the newest snapshot to a temporary folder and check it
#   sh realms-backup.sh --restic ARGS    run restic with these settings, e.g. --restic snapshots
#
# What a backup does:
#   1. waits for a deploy that is running (realms-deploy.sh backs up and restarts the server; the
#      two must not overlap)
#   2. if the server answers RCON, runs `realms backup` in the container: save-off, save-all flush,
#      copy the world, configs and mod data to backups/<time> (no jars, logs, libraries, BlueMap
#      tiles or session.lock), save-on; the newest 14 stay. A server that is stopped or still
#      starting has nothing new to save, so that hour is skipped (and reported after 3 in a row).
#   3. hard-links that folder to /srv/realms/offsite/server, so every snapshot has the same path:
#      restic then skips files that haven't changed, and forget sees one series of snapshots
#   4. restic backup to R2 (encrypted and compressed; only changed data is sent), tagged world
#   5. restic forget: keeps 48 hourly, 14 daily and 8 weekly snapshots; once a day, prune deletes
#      the data no snapshot needs any more
#   6. posts to Discord (DISCORD_WEBHOOK_URL in /etc/realms-deploy.env) when backups start failing
#      and when they work again, not every hour
#
# A restore test restores the newest snapshot to a temporary folder, checks that level.dat is a
# whole gzip file and that the region files are there and whole, and posts the result to Discord.
#
# Settings come from /etc/realms-backup.env (or REALMS_BACKUP_ENV); see realms-backup.env.example.
# LIVE_DIR, the deploy lock and the webhook come from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

ENV_FILE=${REALMS_BACKUP_ENV:-/etc/realms-backup.env}
DEPLOY_ENV=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
# Every snapshot holds this path: restores name it (docs/LIVE.md). It must be on the same disk as
# backups/ for the hard links.
STAGE=/srv/realms/offsite/server
STATE_DIR=/var/lib/realms-backup
LOCK_FILE=/run/realms-backup.lock

log() { printf '%s [backup] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
reason=''
die() { reason=$*; log "ERROR: $*"; exit 1; }

# The value of $2 in the KEY=value file $1 (else $3), exactly as written: not run through the shell,
# so a password may hold $, quotes, spaces or backslashes. KEY="value" and KEY='value' work too.
setting() {
    v=''
    [ ! -r "$1" ] || v=$(sed -n "s/^[[:space:]]*$2[[:space:]]*=[[:space:]]*//p" "$1" | tail -n 1 |
        sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/")
    printf '%s' "${v:-${3:-}}"
}

mode=backup
if [ $# -gt 0 ]; then
    case "$1" in
        --init) mode=init ;;
        --restore-test) mode=restore-test ;;
        --restic) mode=restic ;;
        *) die "unknown option '$1' (use --init, --restore-test or --restic ARGS)" ;;
    esac
    shift
    [ "$mode" = restic ] || [ $# -eq 0 ] || die "--$mode takes no arguments"
fi

[ "$(id -u)" = 0 ] || die "run this as root: only root may read $ENV_FILE"
cd /
[ -f "$ENV_FILE" ] ||
    die "$ENV_FILE is missing: copy deploy/realms-backup.env.example there and fill it in (docs/LIVE.md)"
case "$(stat -c '%u:%a' "$ENV_FILE")" in
    0:600 | 0:400) ;;
    *) log "WARNING: other users can read $ENV_FILE; make it root-only: chown root: $ENV_FILE && chmod 600 $ENV_FILE" ;;
esac
for key in RESTIC_REPOSITORY RESTIC_PASSWORD AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do
    value=$(setting "$ENV_FILE" "$key")
    [ -n "$value" ] || die "$key is empty in $ENV_FILE"
    export "$key=$value"
done
value=''
AWS_DEFAULT_REGION=$(setting "$ENV_FILE" AWS_DEFAULT_REGION auto)
RESTIC_CACHE_DIR=${RESTIC_CACHE_DIR:-/var/cache/realms-backup}
export AWS_DEFAULT_REGION RESTIC_CACHE_DIR
KEEP_HOURLY=$(setting "$ENV_FILE" KEEP_HOURLY 48)
KEEP_DAILY=$(setting "$ENV_FILE" KEEP_DAILY 14)
KEEP_WEEKLY=$(setting "$ENV_FILE" KEEP_WEEKLY 8)
SNAPSHOT_HOST=$(setting "$ENV_FILE" SNAPSHOT_HOST monkey-smp)
for n in "$KEEP_HOURLY" "$KEEP_DAILY" "$KEEP_WEEKLY"; do
    case "$n" in
        '' | *[!0-9]*) die "KEEP_HOURLY, KEEP_DAILY and KEEP_WEEKLY must be whole numbers, not '$n'" ;;
    esac
done

LIVE_DIR=$(setting "$DEPLOY_ENV" LIVE_DIR /srv/realms/TheRealms-Server)
DEPLOY_LOCK=$(setting "$DEPLOY_ENV" LOCK_FILE /tmp/realms-deploy.lock)
WEBHOOK=$(setting "$DEPLOY_ENV" DISCORD_WEBHOOK_URL)
BACKUPS=$LIVE_DIR/backups
COMPOSE="docker compose --project-directory $LIVE_DIR/docker -f $LIVE_DIR/docker/compose.yaml"

command -v restic >/dev/null || die 'restic is not installed (docs/LIVE.md, "Backups off the machine")'
[ "$mode" != restic ] || exec restic "$@"

# One backup or restore test at a time.
exec 8>"$LOCK_FILE"
flock -w 3600 8 || die 'another backup or restore test has been running for an hour'
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

# The number of region files in folder $1 (0 if it doesn't exist).
regions() { find "$1" -maxdepth 1 -type f -name 'r.*.mca' 2>/dev/null | wc -l | tr -d ' '; }

level_name() { setting "$LIVE_DIR/server/server.properties" level-name world; }

uploaded=''
tmp=''
on_exit() {
    rc=$?
    rm -rf "$STAGE"
    [ -z "$tmp" ] || rm -rf "$tmp"
    case "$mode" in
        backup)
            # Post once when backups start failing and once when they work again, not every hour.
            if [ -n "$uploaded" ]; then
                if [ -e "$STATE_DIR/failing" ]; then
                    rm -f "$STATE_DIR/failing"
                    discord 'Monkey SMP off-site backups work again.'
                fi
            elif [ "$rc" != 0 ] && [ ! -e "$STATE_DIR/failing" ]; then
                touch "$STATE_DIR/failing"
                discord "Monkey SMP off-site backup FAILED: ${reason:-see the log}. It tries again every hour. Check: journalctl -u realms-backup"
            fi
            ;;
        restore-test)
            [ "$rc" = 0 ] ||
                discord "Monkey SMP backup restore test FAILED: ${reason:-see the log}. Check: journalctl -u realms-restore-test"
            ;;
    esac
}
trap on_exit EXIT
# systemd stops a run that overruns with SIGTERM; exit through on_exit so it still reports.
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
    # realms-deploy.sh holds its lock for a whole deploy, which backs up and recreates the container:
    # wait for it, so a deploy never restarts the server halfway through this copy. (A deploy check
    # that finds the lock taken tries again 5 minutes later.) Read-only is enough for flock, and root
    # may not open another user's file in /tmp for writing (fs.protected_regular). No lock file means
    # no deploy has run since boot.
    if [ -e "$DEPLOY_LOCK" ]; then
        exec 9<"$DEPLOY_LOCK"
        flock -w 2700 9 || die 'a deploy has held its lock for 45 minutes'
    fi

    if ! $COMPOSE exec -T realms realms rcon list >/dev/null 2>&1; then
        skipped=$(cat "$STATE_DIR/skipped" 2>/dev/null || true)
        case "$skipped" in '' | *[!0-9]*) skipped=0 ;; esac
        skipped=$((skipped + 1))
        echo "$skipped" >"$STATE_DIR/skipped"
        [ "$skipped" -lt 3 ] || die "the server has not answered RCON for $skipped hours, so nothing has been backed up"
        log 'the server is not answering (stopped or still starting): nothing new to back up this hour'
        return 0
    fi
    rm -f "$STATE_DIR/skipped"

    before=$(ls -1 "$BACKUPS" 2>/dev/null || true)
    log 'backing up the world (realms backup)'
    $COMPOSE exec -T realms realms backup || die 'realms backup failed'
    exec 9<&-
    # The folder it just made: names are times, but comparing the lists also works on the night the
    # clocks go back.
    new=$(ls -1 "$BACKUPS" | grep -vxF -e "$before" | sort | tail -n 1 || true)
    [ -n "$new" ] || die "realms backup made no new folder in $BACKUPS"
    level=$(level_name)
    [ -s "$BACKUPS/$new/$level/level.dat" ] || die "the new backup $new has no $level/level.dat"

    rm -rf "$STAGE"
    mkdir -p "${STAGE%/*}"
    cp -al "$BACKUPS/$new" "$STAGE" ||
        die "could not hard-link $BACKUPS/$new to $STAGE (they must be on the same disk)"
    log "sending $new to R2"
    # The copy has new inodes every hour, so compare files by size and modification time only.
    restic backup --host "$SNAPSHOT_HOST" --tag world --ignore-inode --ignore-ctime "$STAGE" ||
        die "restic could not send $new to R2"
    uploaded=1

    restic forget --quiet --host "$SNAPSHOT_HOST" --tag world \
        --keep-hourly "$KEEP_HOURLY" --keep-daily "$KEEP_DAILY" --keep-weekly "$KEEP_WEEKLY" ||
        die 'restic forget failed'
    if [ -z "$(find "$STATE_DIR/pruned" -mmin -1380 2>/dev/null)" ]; then
        log 'pruning: deleting data that no snapshot needs any more (once a day)'
        restic prune || die 'restic prune failed'
        touch "$STATE_DIR/pruned"
    fi
    log "done: $new is in R2"
}

# ---------------------------------------------------------------- restore test

restore_test() {
    log 'checking the repository (restic check)'
    restic check || die 'restic check found a problem in the repository'
    json=$(restic snapshots latest --host "$SNAPSHOT_HOST" --tag world --json) ||
        die 'restic could not list the snapshots'
    id=$(printf '%s' "$json" | sed -n 's/.*"short_id":"\([0-9a-f]*\)".*/\1/p')
    when=$(printf '%s' "$json" | sed -n 's/.*"time":"\([0-9-]*\)T\([0-9][0-9]:[0-9][0-9]\).*/\1 \2/p')
    [ -n "$id" ] || die 'there is no snapshot in the repository yet'

    tmp=$(mktemp -d "${TMPDIR:-/var/tmp}/realms-restore-test.XXXXXX")
    log "restoring snapshot $id ($when) to $tmp"
    restic restore "$id:$STAGE" --target "$tmp" || die "restic could not restore snapshot $id"

    level=$(level_name)
    world=$tmp/$level
    dims=$world/dimensions/minecraft
    [ -s "$world/level.dat" ] || die "snapshot $id has no $level/level.dat"
    gzip -t "$world/level.dat" 2>/dev/null || die "$level/level.dat in snapshot $id is not a whole gzip file"
    over=$(regions "$dims/overworld/region")
    nether=$(regions "$dims/the_nether/region")
    end=$(regions "$dims/the_end/region")
    [ "$over" -gt 0 ] || die "snapshot $id has no region files in $level/dimensions/minecraft/overworld/region"
    # A region file is whole 4 KiB sectors, starting with an 8 KiB header unless it is empty.
    bad=$(find "$world" -path '*/region/*.mca' -type f -printf '%s\n' |
        awk '$1 % 4096 || ($1 && $1 < 8192) { n++ } END { print n + 0 }')
    [ "$bad" = 0 ] || die "region files cut short in snapshot $id: $bad"

    live=$(regions "$LIVE_DIR/server/$level/dimensions/minecraft/overworld/region")
    mb=$(du -sm "$tmp" | cut -f1)
    msg="Monkey SMP backup restore test passed: snapshot $id ($when), $mb MB, level.dat OK, region files: overworld $over (live world $live), nether $nether, end $end."
    log "$msg"
    discord "$msg"
}

case "$mode" in
    init) init_repo ;;
    backup) backup ;;
    restore-test) restore_test ;;
esac
