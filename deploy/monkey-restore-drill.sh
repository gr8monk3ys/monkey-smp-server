#!/bin/sh
# The restore drill: proves the off-site backups can bring the server back (docs/LIVE.md, "Restore drill").
#
#   sh monkey-restore-drill.sh          as root; monkey-restore-drill.service runs it (by hand, or monthly once
#                                       its timer is on). Takes 10 to 30 minutes.
#
# What it does:
#   1. checks there is room: free disk in DRILL_ROOT (/var/tmp) for a second copy of the server, and free memory for
#      a second server (DRILL_MEMORY_GB, default 2, plus 1 GB)
#   2. picks the newest snapshot in R2 that is not tagged unflushed (tools/restore_drill.py) and restores it into a
#      new scratch folder, DRILL_ROOT/monkey-drill.XXXXXX, through `monkey-backup.sh --restic-read`: restic
#      --no-lock, which writes nothing to the repository (with READ_AWS_ACCESS_KEY_ID set, the token can't either)
#   3. checks the restored world: level.dat reads and has a game time, and there are region files
#   4. copies in, read-only from the live folder, what a snapshot leaves out on purpose: the release (monkey/,
#      docker/ without .env, java/, pwsh/) and the server's jars, libraries and install state
#   5. boots it in its own container from the live server's image (DRILL_IMAGE, default monkey-smp-monkey) with no
#      network at all (--network none: no ports, no Discord bot, no store, nothing reaches or leaves it), one CPU,
#      low CPU priority, and a memory cap, as user 61000, which owns nothing else
#   6. waits up to DRILL_TIMEOUT seconds (900) for RCON to answer, then asks `time query gametime`: a pass is a
#      server that answers with a game time at least the restored level.dat's
#   7. stops and removes the container and deletes the scratch folder (DRILL_KEEP=1 keeps the folder to look at),
#      whatever happened
#   8. logs and posts the result to the staff channel (STAFF_WEBHOOK_URL, else DISCORD_WEBHOOK_URL), and keeps the
#      last pass in /var/lib/monkey-restore-drill/last-pass. Exit 0 pass, 1 fail.
#
# What it never does: write to the live folder (it only reads from it, and refuses a scratch folder inside it or
# around it), write to the restic repository, touch the live container, or publish a port. It holds the backup lock
# while it restores, so an hourly backup's prune can't remove data mid-restore; that backup waits, then runs.
#
# Its limit: the drill server starts offline. If the install wants to download something the live folder doesn't
# have, the boot fails with a download error while the world checks (step 3) passed: the log says which.
#
# Settings: LIVE_DIR and the webhooks from /etc/monkey-deploy.env, SNAPSHOT_HOST from /etc/monkey-backup.env (both
# read, never sourced). Installed root-owned in /opt/monkey/deploy by deploy/install-root.sh, next to the
# monkey-backup.sh, lib.sh and tools/ it uses.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=restore-drill
. "$(dirname -- "$0")/lib.sh"

HERE=$(cd "$(dirname -- "$0")" && pwd)
DEPLOY_ENV=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
BACKUP_ENV=${MONKEY_BACKUP_ENV:-/etc/monkey-backup.env}
# The tests point these elsewhere (tests/test_restore_drill.py).
BACKUP=${DRILL_BACKUP:-$HERE/monkey-backup.sh}
TOOLS=${DRILL_TOOLS:-$HERE/../tools}
SCRATCH_ROOT=${DRILL_ROOT:-/var/tmp}
STATE_DIR=${DRILL_STATE:-/var/lib/monkey-restore-drill}
BACKUP_LOCK=${MONKEY_BACKUP_LOCK:-/run/monkey-backup.lock}
MEMINFO=${DRILL_MEMINFO:-/proc/meminfo}
IMAGE=${DRILL_IMAGE:-monkey-smp-monkey}
MEMORY_GB=${DRILL_MEMORY_GB:-2}
TIMEOUT=${DRILL_TIMEOUT:-900}
KEEP=${DRILL_KEEP:-}
DRILL_UID=61000

[ $# -eq 0 ] || { echo "usage: sh $0   (as root; DRILL_KEEP=1 keeps the scratch folder)" >&2; exit 2; }
whole_number DRILL_MEMORY_GB "$MEMORY_GB" GB
whole_number DRILL_TIMEOUT "$TIMEOUT" seconds
[ "$MEMORY_GB" -ge 1 ] || die 'DRILL_MEMORY_GB must be at least 1'
[ "$(id -u)" = 0 ] || die 'run this as root: it reads the restic settings and runs docker'
cd /

LIVE_DIR=$(setting_in "$DEPLOY_ENV" LIVE_DIR /srv/monkey/MonkeySMP-Server)
WEBHOOK=$(setting_in "$DEPLOY_ENV" STAFF_WEBHOOK_URL "$(setting_in "$DEPLOY_ENV" DISCORD_WEBHOOK_URL)")
HOST=$(setting_in "$BACKUP_ENV" SNAPSHOT_HOST monkey-smp)
SERVER=$LIVE_DIR/server
live_real=$(realpath -e "$LIVE_DIR" 2>/dev/null) || die "there is no live folder at $LIVE_DIR"
[ -d "$SERVER" ] || die "there is no server folder in $LIVE_DIR"
[ -f "$BACKUP" ] || die "$BACKUP is missing"
[ -f "$TOOLS/restore_drill.py" ] && [ -f "$TOOLS/nbt.py" ] || die "$TOOLS has no restore_drill.py and nbt.py"
python_ok 10 || die 'needs python3 3.10 or newer'

# ---------------------------------------------------------------- the result, whatever happens

scratch=''
name="monkey-drill-$(date +%Y%m%d-%H%M%S)"
started=$(date +%s)
snapshot=''
verdict=''
mkdir -p "$STATE_DIR"

# "fail WORDS": the drill failed; the EXIT trap cleans up and reports.
fail() { verdict="FAILED: $*"; log "FAILED: $*"; exit 1; }

on_exit() {
    rc=$?
    [ -n "$verdict" ] || verdict="FAILED: ${DIED:-stopped before it finished (exit $rc)}"
    if docker inspect "$name" >/dev/null 2>&1; then
        docker rm -f "$name" >/dev/null 2>&1 || log "WARNING: could not remove the container $name: docker rm -f $name"
    fi
    if [ -n "$scratch" ]; then
        if [ -n "$KEEP" ]; then
            log "kept the scratch folder $scratch (DRILL_KEEP); delete it when done: rm -rf $scratch"
        else
            case $scratch in
                "$SCRATCH_ROOT"/monkey-drill.*) rm -rf -- "$scratch" && log "deleted the scratch folder $scratch" ;;
            esac
        fi
    fi
    minutes=$((($(date +%s) - started + 59) / 60))
    msg="Monkey SMP restore drill $verdict${snapshot:+ Snapshot: $snapshot.} Took $minutes min."
    case $verdict in
        PASSED*) printf '%s\n' "$(date -u +%Y-%m-%dT%H:%MZ) $msg" >"$STATE_DIR/last-pass" ;;
        *) msg="$msg Check: journalctl -u monkey-restore-drill" ;;
    esac
    log "$msg"
    discord "$msg" "$WEBHOOK"
}
trap on_exit EXIT
trap 'exit 143' TERM INT HUP

# ---------------------------------------------------------------- 1. room

root_real=$(realpath -e "$SCRATCH_ROOT" 2>/dev/null) || fail "there is no folder $SCRATCH_ROOT (DRILL_ROOT)"
case "$root_real/" in "$live_real/"*) fail "DRILL_ROOT $SCRATCH_ROOT is inside the live folder" ;; esac

server_kb=$(du -sk --exclude=bluemap --exclude=logs "$SERVER" 2>/dev/null | cut -f1)
release_kb=$(du -sck "$LIVE_DIR/java" "$LIVE_DIR/pwsh" "$LIVE_DIR/monkey" 2>/dev/null | tail -n 1 | cut -f1)
need_kb=$((${server_kb:-0} + ${release_kb:-0} + 1048576))
free_kb=$(df -Pk "$SCRATCH_ROOT" | awk 'NR == 2 { print $4 }')
[ "${free_kb:-0}" -gt "$need_kb" ] ||
    fail "not enough disk in $SCRATCH_ROOT: $((${free_kb:-0} / 1024)) MB free, $((need_kb / 1024)) MB needed"
mem_kb=$(awk '/^MemAvailable:/ { print $2 }' "$MEMINFO" 2>/dev/null || :)
[ "${mem_kb:-0}" -gt $(((MEMORY_GB + 1) * 1048576)) ] ||
    fail "not enough free memory for a second server: $((${mem_kb:-0} / 1024)) MB available, $(((MEMORY_GB + 1) * 1024)) MB needed (DRILL_MEMORY_GB=$MEMORY_GB)"
docker image inspect "$IMAGE" >/dev/null 2>&1 ||
    fail "there is no docker image $IMAGE (the live server's image; DRILL_IMAGE names another)"

scratch=$(mktemp -d "$SCRATCH_ROOT/monkey-drill.XXXXXX")
scratch_real=$(realpath -e "$scratch")
case "$scratch_real/" in "$live_real/"*) fail "the scratch folder $scratch is inside the live folder" ;; esac
chmod 700 "$scratch"

# ---------------------------------------------------------------- 2. restore

exec 8>>"$BACKUP_LOCK"
flock -w 3600 8 || fail 'a backup has held the backup lock for an hour'
list=$(timeout 600 sh "$BACKUP" --restic-read snapshots --json --tag world --host "$HOST") ||
    fail 'restic could not list the snapshots'
picked=$(printf '%s' "$list" | python3 -B -I "$TOOLS/restore_drill.py" pick) || fail 'no snapshot to restore'
set -- $picked
snapshot="${1%"${1#????????}"} from $2, $3 h old"
log "restoring snapshot $snapshot into $scratch"
timeout 3h sh "$BACKUP" --restic-read restore "$1" --target "$scratch/restored" || fail 'restic restore failed'
exec 8>&-
[ -d "$scratch/restored$SERVER" ] || fail "the snapshot holds no $SERVER"
mv "$scratch/restored$SERVER" "$scratch/server"
rm -rf -- "$scratch/restored"

# ---------------------------------------------------------------- 3. the world on disk

world=$(setting_in "$scratch/server/server.properties" level-name world)
level_time=$(python3 -B -I "$TOOLS/restore_drill.py" level-time "$scratch/server/$world/level.dat") ||
    fail "the restored world's level.dat can't be read"
regions=$(find "$scratch/server/$world/region" -name '*.mca' -size +0 2>/dev/null | wc -l)
[ "$regions" -gt 0 ] || fail "the restored world has no region files"
log "the world on disk: level.dat reads (game time $level_time), $regions region files"

# ---------------------------------------------------------------- 4. what a snapshot leaves out

for d in monkey docker java pwsh; do
    [ ! -d "$LIVE_DIR/$d" ] || cp -a "$LIVE_DIR/$d" "$scratch/"
done
rm -f "$scratch/docker/.env"
for d in libraries versions .fabric; do
    [ ! -d "$SERVER/$d" ] || cp -a "$SERVER/$d" "$scratch/server/"
done
rsync -a -m --exclude='/bluemap/' --exclude='/logs/' --exclude='/libraries/' --exclude='/versions/' \
    --exclude='/.fabric/' --include='*/' --include='*.jar' --exclude='*' "$SERVER/" "$scratch/server/"
[ ! -f "$SERVER/.monkey-state.json" ] || cp -p "$SERVER/.monkey-state.json" "$scratch/server/"
chown -R "$DRILL_UID:$DRILL_UID" "$scratch"

# ---------------------------------------------------------------- 5. and 6. boot it, offline

log "booting it offline in the container $name ($IMAGE, ${MEMORY_GB} GB, up to ${TIMEOUT}s)"
docker run -dit --name "$name" --label monkey-restore-drill=1 --network none \
    --memory "$((MEMORY_GB + 1))g" --cpus 1 --cpu-shares 256 --security-opt no-new-privileges:true \
    -e EULA=TRUE -e MEMORY_GB="$MEMORY_GB" -e PUID="$DRILL_UID" -e PGID="$DRILL_UID" -e TZ=UTC \
    -v "$scratch:/monkey" "$IMAGE" >/dev/null || fail 'docker could not start the drill container'
waited=0
up=''
while [ "$waited" -lt "$TIMEOUT" ]; do
    if docker exec "$name" monkey rcon list >/dev/null 2>&1; then
        up=1
        break
    fi
    [ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null)" = true ] || break
    sleep 15
    waited=$((waited + 15))
done
if [ -z "$up" ]; then
    log "the drill server's last log lines:"
    docker logs --tail 40 "$name" 2>&1 | while IFS= read -r line; do log "  $line"; done
    fail "the restored server did not answer RCON within ${TIMEOUT}s (the world on disk read fine)"
fi
said=$(docker exec "$name" monkey rcon 'time query gametime' 2>/dev/null || :)
game_time=$(printf '%s' "$said" | sed -n 's/.*[Tt]he time is \([0-9][0-9]*\).*/\1/p' | head -n 1)
[ -n "$game_time" ] || fail "the restored server answered, but not with its game time"
[ "$game_time" -ge "$level_time" ] ||
    fail "the restored server's game time ($game_time) is behind its level.dat's ($level_time)"
log "the restored server answers: game time $game_time (level.dat: $level_time)"

# ---------------------------------------------------------------- 7. stop it (the EXIT trap removes it all)

docker stop -t 120 "$name" >/dev/null 2>&1 || log "WARNING: docker stop $name failed; the cleanup removes it"
verdict="PASSED: restored and booted in $((waited / 60 + 1)) min, world time $game_time, $regions region files."
exit 0
