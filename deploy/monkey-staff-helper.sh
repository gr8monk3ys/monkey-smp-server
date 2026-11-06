#!/bin/sh
# The staff page's root helper: does the few things the page may ask of root, and nothing else. The page
# (tools/staff_panel.py, as the monkey user) can't read the backup keys or replace the world while the server runs, so
# it writes a request file to STAFF_DIR/requests; monkey-staff-helper.path sees it and starts
# monkey-staff-helper.service, which runs this. docs/LIVE.md, "The staff page", "Backups from the page".
#
#   backup-now       systemctl start monkey-backup.service (the hourly backup, now)
#   list-snapshots   restic snapshots --json --tag world, cut down by tools/staff_apex.py to id, time, tags and size
#   restore          puts one snapshot's world back: restores it beside the live world while the server runs, then
#                    under the deploy lock warns players, stops the server, moves the live world to
#                    LIVE_DIR/backups/before-restore-TIME/, moves the snapshot's world in and starts the server
#   deploy           runs deploy/monkey-deploy.sh --tag=TAG as the checkout's owner: that release, pinned (it backs the
#                    world up, warns players and rolls back a release that doesn't start, as every deploy does)
#   reset            under the deploy lock warns players, stops the server, moves the world folders to
#                    LIVE_DIR/backups/before-reset-TIME/ with a copy of server.properties, sets a new level-seed if
#                    the request has one, and starts the server, which makes a new world
#   world-upload     unpacks STAFF_DIR/uploads/ID.zip beside the live world (tools/staff_host.py, as the server's
#                    user, checks it all again), then swaps it in like a restore (backups/before-upload-TIME/)
#
# A request is read as data, never run: only `action=` with one of the words above, `snapshot=` with 8 to 64 hex
# digits, `tag=` vX.Y.Z, `seed=` letters, digits and _ (and a leading -) and `upload=` an upload's id are taken from
# it, anything else in it is ignored, and nothing from it reaches a shell or a log but those. A new seed never reaches
# a log or a result: they say "seed changed". A request that isn't a plain file, or whose name isn't one the page
# writes, is deleted unread. What happened goes to RESULTS/ID.json (root's folder: the page only reads it), in the
# script's own words.
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

# ---------------------------------------------------------------- what the world jobs share

# "job_failed ID ACTION WORDS": the result, the staging folder gone, the lock let go.
job_failed() {
    log "$2 failed: $3"
    result "$1" "$2" failed "$3"
    [ -z "${stage:-}" ] || rm -rf "$stage"
    stage=''
    exec 9<&- 2>/dev/null || :
}

# "live_world ID ACTION": sets server, level, world and owner (the live folder's user), or writes a refusal and
# returns 1 when the world's name in server.properties isn't a plain folder name.
live_world() {
    server=$LIVE_DIR/server
    level=$(setting_in "$server/server.properties" level-name world)
    case $level in
        '' | .* | *[!A-Za-z0-9_.-]*)
            result "$1" "$2" refused 'The world name in server.properties is not a plain folder name.'
            return 1
            ;;
    esac
    world=$server/$level
    owner=$(stat -c %U "$LIVE_DIR")
}

# "as_owner CMD...": CMD as the live folder's user. Everything under LIVE_DIR is that user's to change, links
# included, so root never makes, moves, reads or writes a file there itself: it would follow a link anywhere.
as_owner() {
    runuser -u "$owner" -- "$@"
}

# "stop_for ID ACTION WORDS": takes the deploy lock, warns players a minute ahead ("WORDS: the server stops...") and
# stops the server; sets was_running. Returns 1, after a failed result, when the lock or docker said no.
stop_for() {
    if ! deploy_lock "$LOCK_WAIT" "$LOCK_FILE"; then
        job_failed "$1" "$2" 'A deploy, restart or backup held the deploy lock for 30 minutes: nothing was changed.'
        return 1
    fi
    was_running=''
    running || return 0
    was_running=1
    if [ "$(players_online || echo 0)" -gt 0 ] 2>/dev/null; then
        rcon "say $3: the server stops in 1 minute and is back in a few. Find a safe spot." >/dev/null || :
        sleep 60
    fi
    log 'stopping the server'
    if ! compose stop monkey; then
        compose up -d --no-build monkey || :
        job_failed "$1" "$2" 'docker could not stop the server: nothing was changed.'
        return 1
    fi
}

# "swap_in ID ACTION NEW KEEP": moves the live world (if there is one) to LIVE_DIR/backups/KEEP-TIME/ and NEW in its
# place; sets keep and aside. Puts everything back and returns 1, after a failed result, when a move fails.
swap_in() {
    keep=$LIVE_DIR/backups/$4-$(date -u +%Y%m%dT%H%M%SZ)
    if ! { as_owner mkdir -p "$keep" &&
        { [ ! -e "$world" ] || as_owner mv "$world" "$keep/$level"; }; }; then
        [ -z "$was_running" ] || compose up -d --no-build monkey || :
        job_failed "$1" "$2" 'Could not move the live world aside: nothing was changed.'
        return 1
    fi
    if ! as_owner mv "$3" "$world"; then
        [ ! -e "$keep/$level" ] || as_owner mv "$keep/$level" "$world" || :
        [ -z "$was_running" ] || compose up -d --no-build monkey || :
        job_failed "$1" "$2" 'Could not move the new world in: the live world is back as it was.'
        return 1
    fi
    aside="the old world is in backups/${keep##*/}"
}

# "start_after ID ACTION WHAT ASIDE": starts the server again if it was running, writes the result, lets go of the lock.
start_after() {
    if [ -z "$was_running" ]; then
        result "$1" "$2" done "$3 ($4). The server was stopped and still is."
    elif ! compose up -d --no-build monkey; then
        result "$1" "$2" failed "$3 ($4), but docker could not start the server."
    elif wait_for_live; then
        result "$1" "$2" done "$3 and the server is back up ($4)."
    else
        result "$1" "$2" failed "$3 ($4), but the server did not answer within 15 minutes."
    fi
    exec 9<&-
}

# ---------------------------------------------------------------- restore

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
    live_world "$r_id" restore || return 0
    if [ ! -f "$world/level.dat" ]; then
        result "$r_id" restore refused "There is no live world ($level) to replace."
        return 0
    fi

    log "restoring snapshot $short (asked by $user)"
    result "$r_id" restore running "Restoring snapshot $short beside the live world. The server keeps running for now."
    # Beside the world, on the same disk, so the swap is a rename; the server is still up while restic downloads.
    stage=$(mktemp -d "$LIVE_DIR/.restore.XXXXXX") || { job_failed "$r_id" restore 'Could not make a folder beside the world.'; return 0; }
    if ! timeout 3h sh "$BACKUP" --restic restore "$r_snap:$server/$level" --target "$stage/world"; then
        job_failed "$r_id" restore "restic could not restore snapshot $short: see journalctl -u monkey-staff-helper."
        return 0
    fi
    if [ ! -f "$stage/world/level.dat" ]; then
        job_failed "$r_id" restore "Snapshot $short has no $level/level.dat: nothing was changed."
        return 0
    fi
    # Only now the server user's: while restic wrote as root, nobody else could put a link in the folder.
    chown -R "$owner:" "$stage/world" && chown "$owner:" "$stage" ||
        { job_failed "$r_id" restore 'Could not give the restored world to the server user.'; return 0; }

    stop_for "$r_id" restore 'World restore' || return 0
    swap_in "$r_id" restore "$stage/world" before-restore || return 0
    rm -rf "$stage"
    stage=''
    log "snapshot $short is the world now; the old one is in $keep"
    start_after "$r_id" restore "Snapshot $short is the world now" "$aside"
}

# ---------------------------------------------------------------- version switch

do_deploy() {
    d_id=$1
    d_tag=$2
    case $d_tag in
        v[0-9]*.[0-9]*.[0-9]*) ;;
        *) result "$d_id" deploy refused 'Not a release tag (vX.Y.Z).'; return 0 ;;
    esac
    case ${d_tag#v} in
        *[!0-9.]* | *..* | .* | *.) result "$d_id" deploy refused 'Not a release tag (vX.Y.Z).'; return 0 ;;
    esac
    # git as the checkout's owner: root's git refuses a checkout it doesn't own.
    as=$(stat -c %U "$REPO_DIR")
    if ! runuser -u "$as" -- git -C "$REPO_DIR" rev-parse --verify --quiet "refs/tags/$d_tag^{commit}" >/dev/null 2>&1; then
        result "$d_id" deploy refused "$d_tag is not a tag in the repo checkout."
        return 0
    fi
    log "deploying $d_tag (asked by $user)"
    result "$d_id" deploy running "Deploying $d_tag: a 5-minute warning if players are on, a backup, then a restart."
    if runuser -u "$as" -- sh "$REPO_DIR/deploy/monkey-deploy.sh" --tag="$d_tag"; then
        log "deployed $d_tag"
        result "$d_id" deploy done "$d_tag is the live version (pinned until someone picks the newest release)."
    else
        log "deploying $d_tag failed"
        result "$d_id" deploy failed "The deploy of $d_tag failed; a release that doesn't start is rolled back. See journalctl -u monkey-staff-helper."
    fi
}

# ---------------------------------------------------------------- world reset

do_reset() {
    s_id=$1
    s_seed=$2
    stage=''
    if [ -n "$s_seed" ]; then
        case ${s_seed#-} in
            '' | *[!A-Za-z0-9_]*) result "$s_id" reset refused 'The seed has characters a seed here may not have.'; return 0 ;;
        esac
        if [ ${#s_seed} -gt 65 ]; then
            result "$s_id" reset refused 'The seed is too long.'
            return 0
        fi
    fi
    live_world "$s_id" reset || return 0
    props=$server/server.properties
    # Never the seed itself, in the log or the result.
    if [ -n "$s_seed" ]; then s_words='seed changed'; else s_words='same seed'; fi
    log "resetting the world (asked by $user, $s_words)"
    result "$s_id" reset running 'Resetting the world: it is moved aside, not deleted.'

    stop_for "$s_id" reset 'World reset' || return 0
    keep=$LIVE_DIR/backups/before-reset-$(date -u +%Y%m%dT%H%M%SZ)
    if ! { as_owner mkdir -p "$keep" && as_owner cp -p "$props" "$keep/server.properties"; }; then
        [ -z "$was_running" ] || compose up -d --no-build monkey || :
        job_failed "$s_id" reset 'Could not make the folder the old world goes to: nothing was changed.'
        return 0
    fi
    moved=''
    for d in "$level" "${level}_nether" "${level}_the_end"; do
        [ -e "$server/$d" ] || continue
        if ! as_owner mv "$server/$d" "$keep/$d"; then
            for m in $moved; do as_owner mv "$keep/$m" "$server/$m" || :; done
            [ -z "$was_running" ] || compose up -d --no-build monkey || :
            job_failed "$s_id" reset 'Could not move the world aside: it is back as it was.'
            return 0
        fi
        moved="$moved $d"
    done
    what='The world is reset: the server makes a new one as it starts'
    if [ -n "$s_seed" ]; then
        # Written over the file in place, so its owner and mode (it holds the RCON password) stay as they were.
        p_tmp=$(mktemp)
        as_owner cat "$props" >"$p_tmp"
        if grep -q '^level-seed=' "$p_tmp"; then
            sed -i "s/^level-seed=.*/level-seed=$s_seed/" "$p_tmp"
        else
            printf 'level-seed=%s\n' "$s_seed" >>"$p_tmp"
        fi
        as_owner sh -c 'cat >"$1"' sh "$props" <"$p_tmp"
        rm -f "$p_tmp"
        what="$what, seed changed"
    fi
    s_seed=''
    log "the world is reset; the old one is in $keep"
    start_after "$s_id" reset "$what" "the old world and server.properties are in backups/${keep##*/}"
}

# ---------------------------------------------------------------- world upload

do_upload() {
    u_id=$1
    u_up=$2
    stage=''
    case $u_up in
        [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z-[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;;
        *) result "$u_id" world-upload refused 'That is not an upload this page made.'; return 0 ;;
    esac
    zip=$STAFF_DIR/uploads/$u_up.zip
    if [ -L "$zip" ] || [ ! -f "$zip" ]; then
        result "$u_id" world-upload refused 'That upload is not there any more: upload the world again.'
        return 0
    fi
    live_world "$u_id" world-upload || return 0
    log "unpacking an uploaded world (asked by $user)"
    result "$u_id" world-upload running 'Unpacking the uploaded world beside the live one. The server keeps running for now.'
    stage=$(mktemp -d "$LIVE_DIR/.upload.XXXXXX") || { job_failed "$u_id" world-upload 'Could not make a folder beside the world.'; return 0; }
    chown "$owner:" "$stage"
    u_err=$(mktemp)
    # As the server's user, not root: the zip is the page's file, and what it unpacks belongs to the server.
    if ! runuser -u "$owner" -- python3 -B -I "$REPO_DIR/tools/staff_host.py" unzip-world "$zip" "$stage" 2>"$u_err"; then
        u_why=$(tail -n 1 "$u_err" | sed 's/^staff_host: //' | cut -c1-200)
        rm -f "$u_err"
        job_failed "$u_id" world-upload "The upload was not swapped in: ${u_why:-it could not be unpacked}"
        return 0
    fi
    rm -f "$u_err"
    if [ ! -f "$stage/world/level.dat" ]; then
        job_failed "$u_id" world-upload 'The unpacked upload has no level.dat: nothing was changed.'
        return 0
    fi

    stop_for "$u_id" world-upload 'World upload' || return 0
    swap_in "$u_id" world-upload "$stage/world" before-upload || return 0
    rm -rf "$stage"
    stage=''
    rm -f "$zip"
    log "the uploaded world is live; the old one is in $keep"
    start_after "$u_id" world-upload 'The uploaded world is the world now' "$aside"
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
    tag=$(printf '%s\n' "$body" | sed -n 's/^tag=\(v[0-9]\{1,4\}\.[0-9]\{1,4\}\.[0-9]\{1,4\}\)$/\1/p' | head -n 1)
    seed=$(printf '%s\n' "$body" | sed -n 's/^seed=\(-\{0,1\}[A-Za-z0-9_]\{1,64\}\)$/\1/p' | head -n 1)
    upload=$(printf '%s\n' "$body" | sed -n 's/^upload=\([0-9]\{8\}T[0-9]\{6\}Z-[0-9a-f]\{8\}\)$/\1/p' | head -n 1)
    # A seed line that doesn't pass is refused (do_reset refuses the !), never read as "keep the seed".
    seed_bad=''
    if [ -z "$seed" ] && printf '%s\n' "$body" | grep -q '^seed='; then seed_bad=1; fi
    user=${user:-unknown}
    body=''
    case $action in
        backup-now) do_backup "$id" || : ;;
        list-snapshots) do_list "$id" || : ;;
        restore) do_restore "$id" "$snapshot" || : ;;
        deploy) do_deploy "$id" "$tag" || : ;;
        reset) do_reset "$id" "${seed_bad:+!}$seed" || : ;;
        world-upload) do_upload "$id" "$upload" || : ;;
        *)
            log 'refused a request: not an action the helper runs'
            result "$id" unknown refused 'Not an action the helper runs.'
            ;;
    esac
    seed=''
done

# The newest KEEP_RESULTS results; the names start with the time, so they sort by it.
ls -1 "$RESULTS" | grep '\.json$' | sort -r | tail -n +$((KEEP_RESULTS + 1)) | while IFS= read -r old; do
    rm -f "$RESULTS/$old"
done
