#!/bin/sh
# The staff page's backup helper: does the three things the page may ask of root, and nothing else. The page
# (tools/staff_panel.py, as the monkey user) can't read the backup keys, so it never runs restic: it writes a request
# file to STAFF_DIR/requests, monkey-staff-helper.path sees it and starts monkey-staff-helper.service, which runs this.
# docs/LIVE.md, "The staff page", "Backups from the page".
#
#   backup-now       systemctl start monkey-backup.service (the hourly backup, now)
#   list-snapshots   restic snapshots --json --tag world, cut down by tools/staff_apex.py to id, time, tags and size
#   restore          puts one snapshot's world back: restores it beside the live world while the server runs, then
#                    under the deploy lock warns players, stops the server, moves the live world to
#                    LIVE_DIR/backups/before-restore-TIME/, moves the snapshot's world in and starts the server
#
# A request is read as data, never run: only `action=` with one of the three words above and `snapshot=` with 8 to 64
# hex digits are taken from it, anything else in it is ignored, and nothing from it reaches a shell or a log but those.
# A request that isn't a plain file, or whose name isn't one the page writes, is deleted unread. What happened goes to
# RESULTS/ID.json (root's folder: the page only reads it), in the script's own words.
#
#   sh monkey-staff-helper.sh     handle every request waiting (what the service runs)
#
# Install with  sudo sh monkey-staff.sh --install-helper  (an owner's step: it adds a root service).
# Reads REPO_DIR, LIVE_DIR, STAFF_DIR and LOCK_FILE from /etc/monkey-deploy.env (or MONKEY_DEPLOY_ENV); HELPER_RESULTS
# and HELPER_LOCK_WAIT are for the tests.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=staff-helper
. "$(dirname -- "$0")/lib.sh"

ENV_FILE=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/monkey/repo)}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/monkey/MonkeySMP-Server)}
STAFF_DIR=${STAFF_DIR:-$(setting STAFF_DIR /srv/monkey/staff)}
LOCK_FILE=${LOCK_FILE:-$(setting LOCK_FILE /tmp/monkey-deploy.lock)}
REQUESTS=$STAFF_DIR/requests
RESULTS=${HELPER_RESULTS:-/var/lib/monkey-staff-helper/results}
LOCK_WAIT=${HELPER_LOCK_WAIT:-1800}
BACKUP=$REPO_DIR/deploy/monkey-backup.sh
KEEP_RESULTS=50

[ "$(id -u)" = 0 ] || die 'run as root (monkey-staff-helper.service does)'
cd /
umask 022
mkdir -p "$RESULTS"
chmod 755 "$RESULTS"

# "result ID ACTION STATE MESSAGE [SNAPSHOTS]": RESULTS/ID.json, written whole (a temp file, then mv). MESSAGE is this
# script's own words, quotes, backslashes and control characters dropped; SNAPSHOTS is JSON from tools/staff_apex.py.
result() {
    r_msg=$(printf '%s' "$4" | tr -d '"\\\001-\037\177')
    r_tmp=$(mktemp "$RESULTS/.result.XXXXXX")
    printf '{"id":"%s","action":"%s","state":"%s","time":"%s","message":"%s"%s}\n' "$1" "$2" "$3" \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$r_msg" "${5:+,\"snapshots\":$5}" >"$r_tmp"
    chmod 644 "$r_tmp"
    mv -f "$r_tmp" "$RESULTS/$1.json"
}

do_backup() {
    if systemctl start --no-block monkey-backup.service; then
        log "started monkey-backup.service (asked by $user)"
        result "$1" backup-now done 'The off-site backup started. Last backup shows it when it is done (a few minutes).'
    else
        log 'systemctl could not start monkey-backup.service'
        result "$1" backup-now failed 'systemctl could not start monkey-backup.service: see journalctl -u monkey-staff-helper.'
    fi
}

do_list() {
    result "$1" list-snapshots running 'Asking R2 for the snapshot list.'
    l_out=$(mktemp)
    # The pipe's status is python's: a restic that failed leaves it no JSON, and it fails too.
    if timeout 600 sh "$BACKUP" --restic snapshots --json --tag world 2>/dev/null |
        python3 -B -I "$REPO_DIR/tools/staff_apex.py" snapshots >"$l_out" 2>/dev/null; then
        log "listed the snapshots (asked by $user)"
        result "$1" list-snapshots done 'The snapshot list from R2.' "$(cat "$l_out")"
    else
        log 'listing the snapshots failed'
        result "$1" list-snapshots failed 'restic could not list the snapshots: see journalctl -u monkey-staff-helper.'
    fi
    rm -f "$l_out"
}

# "restore_failed ID WORDS": the result, the staging folder gone, the lock let go.
restore_failed() {
    log "restore failed: $2"
    result "$1" restore failed "$2"
    [ -z "${stage:-}" ] || rm -rf "$stage"
    stage=''
    exec 9<&- 2>/dev/null || :
}

do_restore() {
    r_id=$1
    r_snap=$2
    stage=''
    case $r_snap in
        '' | *[!0-9a-f]*) result "$r_id" restore refused 'The snapshot ID is not hex.'; return 0 ;;
    esac
    if [ ${#r_snap} -lt 8 ] || [ ${#r_snap} -gt 64 ]; then
        result "$r_id" restore refused 'A snapshot ID is 8 to 64 hex digits.'
        return 0
    fi
    short=$(printf '%s' "$r_snap" | cut -c1-8)
    server=$LIVE_DIR/server
    level=$(setting_in "$server/server.properties" level-name world)
    case $level in
        '' | .* | *[!A-Za-z0-9_.-]*) result "$r_id" restore refused 'The world name in server.properties is not a plain folder name.'; return 0 ;;
    esac
    world=$server/$level
    if [ ! -f "$world/level.dat" ]; then
        result "$r_id" restore refused "There is no live world ($level) to replace."
        return 0
    fi
    owner=$(stat -c %U "$LIVE_DIR")

    log "restoring snapshot $short (asked by $user)"
    result "$r_id" restore running "Restoring snapshot $short beside the live world. The server keeps running for now."
    # Beside the world, on the same disk, so the swap is a rename; the server is still up while restic downloads.
    stage=$(mktemp -d "$LIVE_DIR/.restore.XXXXXX") || { restore_failed "$r_id" 'Could not make a folder beside the world.'; return 0; }
    if ! timeout 3h sh "$BACKUP" --restic restore "$r_snap:$server/$level" --target "$stage/world"; then
        restore_failed "$r_id" "restic could not restore snapshot $short: see journalctl -u monkey-staff-helper."
        return 0
    fi
    if [ ! -f "$stage/world/level.dat" ]; then
        restore_failed "$r_id" "Snapshot $short has no $level/level.dat: nothing was changed."
        return 0
    fi
    chown -R "$owner:" "$stage/world" || { restore_failed "$r_id" 'Could not give the restored world to the server user.'; return 0; }

    if ! deploy_lock "$LOCK_WAIT" "$LOCK_FILE"; then
        restore_failed "$r_id" 'A deploy, restart or backup held the deploy lock for 30 minutes: nothing was changed.'
        return 0
    fi
    was_running=''
    if running; then
        was_running=1
        if [ "$(players_online || echo 0)" -gt 0 ] 2>/dev/null; then
            rcon 'say World restore: the server stops in 1 minute and is back in a few. Find a safe spot.' >/dev/null || :
            sleep 60
        fi
        log 'stopping the server'
        if ! compose stop monkey; then
            restore_failed "$r_id" 'docker could not stop the server: nothing was changed.'
            compose up -d --no-build monkey || :
            return 0
        fi
    fi
    keep=$LIVE_DIR/backups/before-restore-$(date -u +%Y%m%dT%H%M%SZ)
    if ! { mkdir -p "$keep" && chown "$owner:" "$LIVE_DIR/backups" "$keep" && mv "$world" "$keep/$level"; }; then
        [ -z "$was_running" ] || compose up -d --no-build monkey || :
        restore_failed "$r_id" 'Could not move the live world aside: nothing was changed.'
        return 0
    fi
    if ! mv "$stage/world" "$world"; then
        mv "$keep/$level" "$world" || :
        [ -z "$was_running" ] || compose up -d --no-build monkey || :
        restore_failed "$r_id" 'Could not move the restored world in: the live world is back as it was.'
        return 0
    fi
    rm -rf "$stage"
    stage=''
    log "snapshot $short is the world now; the old one is in $keep"
    aside="the old world is in backups/${keep##*/}"
    if [ -z "$was_running" ]; then
        result "$r_id" restore done "Snapshot $short is the world now ($aside). The server was stopped and still is."
    elif ! compose up -d --no-build monkey; then
        result "$r_id" restore failed "Snapshot $short is the world now ($aside), but docker could not start the server."
    elif wait_for_live; then
        result "$r_id" restore done "Snapshot $short is the world now and the server is back up ($aside)."
    else
        result "$r_id" restore failed "Snapshot $short is the world now ($aside), but the server did not answer within 15 minutes."
    fi
    exec 9<&-
}

# A result still marked running is from a run that was stopped: only one runs at a time (a oneshot service).
for old in "$RESULTS"/*.json; do
    [ -f "$old" ] || continue
    if grep -q '"state":"running"' "$old"; then
        sed 's/"state":"running"/"state":"stopped"/' "$old" >"$old.tmp" && mv -f "$old.tmp" "$old"
    fi
done

for req in "$REQUESTS"/*.req; do
    [ -e "$req" ] || [ -L "$req" ] || continue
    name=${req##*/}
    id=${name%.req}
    if [ -L "$req" ] || [ ! -f "$req" ]; then
        rm -f "$req"
        log 'deleted a request that is not a plain file'
        continue
    fi
    case $id in
        [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z-[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;;
        *)
            rm -f "$req"
            log 'deleted a request whose name the page does not write'
            continue
            ;;
    esac
    body=$(timeout 5 head -c 2048 "$req" 2>/dev/null || :)
    rm -f "$req"
    action=$(printf '%s\n' "$body" | sed -n 's/^action=\([a-z-]*\)$/\1/p' | head -n 1)
    snapshot=$(printf '%s\n' "$body" | sed -n 's/^snapshot=\([0-9a-f]*\)$/\1/p' | head -n 1)
    user=$(printf '%s\n' "$body" | sed -n 's/^user=\([A-Za-z0-9_-]\{1,64\}\)$/\1/p' | head -n 1)
    user=${user:-unknown}
    body=''
    case $action in
        backup-now) do_backup "$id" || : ;;
        list-snapshots) do_list "$id" || : ;;
        restore) do_restore "$id" "$snapshot" || : ;;
        *)
            log 'refused a request: not an action the helper runs'
            result "$id" unknown refused 'Not an action the helper runs.'
            ;;
    esac
done

# The newest KEEP_RESULTS results; the names start with the time, so they sort by it.
ls -1 "$RESULTS" | grep '\.json$' | sort -r | tail -n +$((KEEP_RESULTS + 1)) | while IFS= read -r old; do
    rm -f "$RESULTS/$old"
done
