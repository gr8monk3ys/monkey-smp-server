#!/bin/sh
# Backs up the live server folder every hour, encrypted, to a Cloudflare R2 bucket with restic
# (docs/LIVE.md, "Backups off the machine"). monkey-backup.timer runs it. It runs as root:
# /etc/monkey-backup.env holds the R2 keys and the restic password, and only root may read it.
#
#   sh monkey-backup.sh                  back up now (what the hourly timer runs)
#   sh monkey-backup.sh --init           create the restic repository in the bucket (once; safe to repeat)
#   sh monkey-backup.sh --save-on        turn saving back on if a backup was stopped before it could
#                                        (monkey-backup.service runs this after every run)
#   sh monkey-backup.sh --restic ARGS    run restic with these settings, e.g. --restic snapshots
#   sh monkey-backup.sh --restic-read snapshots|ls|restore ARGS
#                                        the same, read-only: restic --no-lock, so it writes nothing to the
#                                        repository, not even a lock; with READ_AWS_ACCESS_KEY_ID and
#                                        READ_AWS_SECRET_ACCESS_KEY set (an R2 token that can only read), the
#                                        bucket refuses writes too. The restore drill uses it.
#
# What a backup does:
#   1. waits for a deploy that is running (monkey-deploy.sh backs up and restarts the server; the
#      two must not overlap), and holds the deploy lock until saving is back on
#   2. if the server answers RCON (asked RCON_TRIES times, RCON_WAIT seconds apart, so a server that is
#      lagging or just starting gets about 2 minutes): save-off, save-all flush, so the world on disk is whole
#      and stays still. Otherwise the world on disk is backed up as it is, with a second tag that says why:
#        stopped    the container is not running: the server saved everything as it stopped, so the copy is
#                   whole
#        unflushed  the container runs but RCON doesn't answer (hung, or still starting): the files may be up
#                   to 5 minutes old (the autosave) and one may be caught mid-write. Better than no copy; a
#                   restore takes the newest snapshot without this tag when there is a choice (docs/LIVE.md)
#      After 3 runs in a row without an answer, staff get one Discord post (the server may be down).
#   3. restic backup of the live server folder (no jars, logs, libraries, BlueMap tiles or
#      session.lock, like `monkey backup`) to R2: encrypted and compressed, only changed data is sent
#   4. save-on, also when restic failed or the run is stopped
#   5. restic forget: keeps 48 hourly, 14 daily, 8 weekly and 6 monthly snapshots of each kind (whole,
#      stopped, unflushed: --group-by host,paths,tags), so a stopped or unflushed copy never takes a whole
#      one's place; once a day, prune deletes the data no snapshot needs any more
#   6. restic check --read-data-subset=5%: reads back a random 5% of the stored data and checks it
#   7. requests PING_URL (in /etc/monkey-backup.env) after a backup that worked: a dead-man's switch, such as a
#      healthchecks.io check, that raises its own alarm when the requests stop, whatever stopped them (the
#      VPS, systemd, this script). No PING_URL, no request.
#   8. posts to Discord (DISCORD_WEBHOOK_URL in /etc/monkey-deploy.env) when backups start failing
#      and when they work again, not every hour
#
# Settings come from /etc/monkey-backup.env (or MONKEY_BACKUP_ENV); see monkey-backup.env.example.
# LIVE_DIR, the deploy lock and the webhook come from /etc/monkey-deploy.env (or MONKEY_DEPLOY_ENV).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=backup
. "$(dirname -- "$0")/lib.sh"

ENV_FILE=${MONKEY_BACKUP_ENV:-/etc/monkey-backup.env}
DEPLOY_ENV=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
# The tests point these elsewhere (tests/test_backup.py).
STATE_DIR=${MONKEY_BACKUP_STATE:-/var/lib/monkey-backup}
BACKUP_LOCK=${MONKEY_BACKUP_LOCK:-/run/monkey-backup.lock}
# The longest the server may go without saving while restic reads the world. The first backup sends
# the whole world; later ones only what changed, usually in a minute or two.
BACKUP_TIMEOUT=45m
# How many times, and how many seconds apart, the server is asked whether it answers RCON.
RCON_TRIES=${RCON_TRIES:-4}
RCON_WAIT=${RCON_WAIT:-30}

mode=backup
if [ $# -gt 0 ]; then
    case "$1" in
        --init) mode=init ;;
        --save-on) mode=save-on ;;
        --restic) mode=restic ;;
        --restic-read) mode=restic-read ;;
        *) die "unknown option '$1' (use --init, --save-on, --restic ARGS or --restic-read ARGS)" ;;
    esac
    shift
    case $mode in
        restic) ;;
        restic-read)
            case "${1:-}" in
                snapshots | ls | restore) ;;
                *) die "--restic-read runs only snapshots, ls or restore, not '${1:-}'" ;;
            esac
            ;;
        *) [ $# -eq 0 ] || die "--$mode takes no arguments" ;;
    esac
fi

[ "$(id -u)" = 0 ] || die "run this as root: only root may read $ENV_FILE"
cd /

LIVE_DIR=$(setting_in "$DEPLOY_ENV" LIVE_DIR /srv/monkey/MonkeySMP-Server)
DEPLOY_LOCK=$(setting_in "$DEPLOY_ENV" LOCK_FILE /tmp/monkey-deploy.lock)
WEBHOOK=$(setting_in "$DEPLOY_ENV" DISCORD_WEBHOOK_URL)
STAFF_WEBHOOK=$(setting_in "$DEPLOY_ENV" STAFF_WEBHOOK_URL "$WEBHOOK")
# Every snapshot holds this path; restores name it (docs/LIVE.md).
SERVER=$LIVE_DIR/server

if [ "$mode" = save-on ]; then
    # Needs no settings: only whether a backup left saving off.
    [ -e "$STATE_DIR/saving-off" ] || exit 0
    log 'a backup stopped before turning saving back on: save-on'
    rcon save-on >/dev/null || die 'save-on failed: run  docker compose exec monkey monkey rcon save-on'
    rm -f "$STATE_DIR/saving-off"
    exit 0
fi

[ -f "$ENV_FILE" ] ||
    die "$ENV_FILE is missing: copy deploy/monkey-backup.env.example there and fill it in (docs/LIVE.md)"
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
RESTIC_CACHE_DIR=${RESTIC_CACHE_DIR:-/var/cache/monkey-backup}
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
if [ "$mode" = restic-read ]; then
    value=$(setting_in "$ENV_FILE" READ_AWS_ACCESS_KEY_ID)
    if [ -n "$value" ]; then
        AWS_ACCESS_KEY_ID=$value
        AWS_SECRET_ACCESS_KEY=$(setting_in "$ENV_FILE" READ_AWS_SECRET_ACCESS_KEY)
        [ -n "$AWS_SECRET_ACCESS_KEY" ] || die "READ_AWS_ACCESS_KEY_ID is set but READ_AWS_SECRET_ACCESS_KEY is empty in $ENV_FILE"
    fi
    value=''
    exec restic --no-lock "$@"
fi
PING_URL=$(setting_in "$ENV_FILE" PING_URL)

# One backup at a time. A restore (the drill, a staff restore) holds the lock too, for up to its 3-hour timeout,
# so the wait is longer than that: a slow restore delays a backup, it doesn't fail it.
exec 8>"$BACKUP_LOCK"
flock -w 11400 8 || die 'a backup or a restore has held the backup lock for over 3 hours'
mkdir -p "$STATE_DIR"

# ---------------------------------------------------------------- helpers

save_on() {
    [ -e "$STATE_DIR/saving-off" ] || return 0
    if rcon save-on >/dev/null; then
        rm -f "$STATE_DIR/saving-off"
        log 'saving is on again'
    else
        # monkey-backup.service tries again (--save-on) once this run has ended.
        log 'ERROR: save-on failed'
        return 1
    fi
}

# "ping_alive": requests PING_URL, the dead-man's switch. It never fails the backup and never prints the URL (its
# path is the check's secret: whoever has it can ping).
ping_alive() {
    [ -n "$PING_URL" ] || return 0
    case $PING_URL in
        https://*) ;;
        *) log 'WARNING: PING_URL is not an https:// URL; not pinging'; return 0 ;;
    esac
    if curl -fsS -m 10 --retry 3 -o /dev/null "$PING_URL" 2>/dev/null; then
        log 'pinged the dead-man switch (PING_URL)'
    else
        log 'WARNING: could not reach PING_URL; if that goes on, its check raises the alarm'
    fi
}

# "answers": the server answers RCON, asked up to RCON_TRIES times, RCON_WAIT seconds apart.
answers() {
    tries=1
    while ! rcon list >/dev/null; do
        [ "$tries" -lt "$RCON_TRIES" ] || return 1
        tries=$((tries + 1))
        sleep "$RCON_WAIT"
    done
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
            discord 'Monkey SMP off-site backups work again.' "$WEBHOOK"
        fi
    elif [ "$rc" != 0 ] && [ ! -e "$STATE_DIR/failing" ]; then
        touch "$STATE_DIR/failing"
        discord "Monkey SMP off-site backup FAILED: ${DIED:-see the log}. It tries again every hour. Check: journalctl -u monkey-backup" "$WEBHOOK"
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
    # monkey-deploy.sh holds its lock for a whole deploy, which backs up (its own save-off and
    # save-on) and recreates the container: wait for it, and keep it out until saving is back on.
    # (A deploy check that finds the lock taken tries again 5 minutes later.) Read-only is enough
    # for flock, and root may not open another user's file in /tmp for writing
    # (fs.protected_regular). No lock file means no deploy has run since boot.
    if [ -e "$DEPLOY_LOCK" ]; then
        deploy_lock 2700 "$DEPLOY_LOCK" || die 'a deploy has held its lock for 45 minutes'
    fi

    [ -s "$SERVER/$(setting_in "$SERVER/server.properties" level-name world)/level.dat" ] ||
        die "there is no world with a level.dat in $SERVER"
    # Until 2026-11 a server that didn't answer was skipped for the hour. Its world is still on disk, so now it is
    # backed up as it is, tagged with why it wasn't flushed first (the header, step 2).
    rm -f "$STATE_DIR/skipped"
    kind=''
    if answers; then
        rm -f "$STATE_DIR/unanswered"
        log 'save-off, save-all flush'
        touch "$STATE_DIR/saving-off"
        rcon save-off >/dev/null || die 'save-off failed'
        rcon 'save-all flush' >/dev/null || die 'save-all flush failed'
        sleep 3
    else
        # Stopped only when nothing runs and the container ended the way a stop ends (exit 0, or 130/143 after
        # SIGINT/SIGTERM), or there is none; a crash, a kill (137) or a restart loop may have cut a save short.
        if ids=$(compose ps -q --status running monkey 2>/dev/null) && [ -z "$ids" ] &&
            ended=$(compose ps -a --format '{{.State}} {{.ExitCode}}' monkey 2>/dev/null) &&
            case $ended in '' | 'exited 0' | 'exited 130' | 'exited 143') true ;; *) false ;; esac; then
            kind=stopped
            log 'the server is stopped: it saved everything as it stopped; backing up its world as it is (tag: stopped)'
        else
            kind=unflushed
            log "WARNING: the server has not answered RCON for $(((RCON_TRIES - 1) * RCON_WAIT)) seconds and may be running: backing up the world as it is on disk, without save-all flush (tag: unflushed)"
        fi
        unanswered=$(cat "$STATE_DIR/unanswered" 2>/dev/null || true)
        case "$unanswered" in '' | *[!0-9]*) unanswered=0 ;; esac
        unanswered=$((unanswered + 1))
        echo "$unanswered" >"$STATE_DIR/unanswered"
        # Once, on the third run in a row: the server may be down, and that is staff's to look at, not a failed backup.
        [ "$unanswered" -ne 3 ] ||
            discord "Monkey SMP has not answered RCON for 3 backup runs in a row ($kind). Backups go on from the disk. Check: docker compose ps, and docs/LIVE.md, \"The server is down\"" "$STAFF_WEBHOOK"
    fi

    log "sending $SERVER to R2"
    rc=0
    timeout "$BACKUP_TIMEOUT" restic backup --host "$SNAPSHOT_HOST" --tag world ${kind:+--tag "$kind"} \
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

    restic forget --quiet --host "$SNAPSHOT_HOST" --tag world --group-by host,paths,tags --keep-hourly "$KEEP_HOURLY" \
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
    log "done: the world is in R2${kind:+ (tag: $kind)}"
    ping_alive
}

case "$mode" in
    init) init_repo ;;
    backup) backup ;;
esac
