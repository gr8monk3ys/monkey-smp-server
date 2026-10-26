#!/bin/sh
# Measures what the live VPS can carry (docs/LIVE.md, "Load test"): tools/loadtest.py with Carpet fake players
# and a spark profile of every thread, on a throwaway copy of the live server, on the live machine itself.
# Run it as root at a quiet time: the server is offline for about 15 minutes per scenario. Started with
# systemd-run it carries on if the SSH connection drops:
#
#   systemd-run --unit=realms-loadtest --collect -p TimeoutStopSec=20min sh /srv/realms/repo/deploy/realms-loadtest.sh
#   journalctl -fu realms-loadtest
#
# Environment (systemd-run --setenv=NAME=value):
#   SCENARIOS    "still" (default, the same test as the 8700K table in docs/ADMIN.md); "still walk" adds a
#                run with players walking through loaded terrain
#   PLAYERS      fake players (default 25)     MINUTES   minutes measured per scenario (default 5)
#   LOADTEST_PY  the loadtest.py to run (default: the deployed checkout's); it needs --spark
#   FORCE=1      run although Chunky is still pre-generating (the numbers then include it)
# Settings and webhooks come from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV).
#
# Why it is safe for the live world and for players:
#   - it holds the deploy lock, so no deploy, daily restart or off-site backup runs meanwhile
#   - the copy is made with rsync while the server runs, then again (only what changed) once the server has
#     stopped and saved; the live folder is only read
#   - Tebex is taken out of the copy: it would otherwise claim real purchases and run their commands there
#   - the copy runs in a one-off container that publishes no ports, so nobody can join it and its ports
#     (25565, RCON, BlueMap's 8100) can't clash with the live ones
#   - the live server is stopped meanwhile (the machine can't hold both heaps, and they would share the two
#     CPU threads), and started again whatever happens; then the copy is deleted
# Results stay in /root/loadtest-results/<time>/; the main numbers go to the staff webhook.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

ENV_FILE=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
# shellcheck disable=SC1090
[ ! -f "$ENV_FILE" ] || . "$ENV_FILE"

REPO_DIR=${REPO_DIR:-/srv/realms/repo}
LIVE_DIR=${LIVE_DIR:-/srv/realms/TheRealms-Server}
WARN_MINUTES=${WARN_MINUTES:-5}
BOOT_TIMEOUT=${BOOT_TIMEOUT:-900}
DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL:-}
STAFF_WEBHOOK_URL=${STAFF_WEBHOOK_URL:-$DISCORD_WEBHOOK_URL}
LOCK_FILE=${LOCK_FILE:-/tmp/realms-deploy.lock}
SCENARIOS=${SCENARIOS:-still}
PLAYERS=${PLAYERS:-25}
MINUTES=${MINUTES:-5}
LOADTEST_PY=${LOADTEST_PY:-$REPO_DIR/tools/loadtest.py}
FORCE=${FORCE:-}
COPY_DIR=${COPY_DIR:-/srv/realms-loadtest/TheRealms-Server}
RESULTS=${RESULTS:-/root/loadtest-results/$(date +%Y%m%d-%H%M)}
IMAGE=realms-loadtest
# Carpet makes the fake players; it is not part of the pack. The Fabric build for Minecraft 26.3, from Modrinth.
CARPET_URL=https://cdn.modrinth.com/data/TQTTVgYE/versions/yt9oDFOj/fabric-carpet-26.3%2Bv260915.jar
CARPET_SHA512=7a479ba69eb5049cb94365d5044bd58c9f970c50b3484861fe3675f1917f7c99c1b1f50a5e01bdd9ded940d76a995539009a3656e05be2f513f20ec14de991a7

COMPOSE="docker compose --project-directory $LIVE_DIR/docker -f $LIVE_DIR/docker/compose.yaml"

log() { printf '%s [loadtest] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { log "ERROR: $*"; exit 1; }

# Posts $1 to the webhook $2. The messages are ours (no quotes or backslashes), so printf makes valid JSON.
discord() {
    [ -n "$2" ] || return 0
    printf '{"content":"%s"}' "$1" |
        curl -fsS -m 15 -H 'Content-Type: application/json' -d @- "$2" >/dev/null ||
        log 'could not post to Discord'
}

running() { [ -n "$($COMPOSE ps -q --status running realms 2>/dev/null)" ]; }
rcon() { $COMPOSE exec -T realms realms rcon "$1" 2>/dev/null; }
players_online() { rcon list | sed -n 's/.*There are \([0-9][0-9]*\) of.*/\1/p' | head -n 1; }

wait_for_live() {
    waited=0
    while [ "$waited" -lt "$BOOT_TIMEOUT" ]; do
        sleep 15
        waited=$((waited + 15))
        if rcon list >/dev/null; then return 0; fi
    done
    return 1
}

# "field NAME FILE": a number or string from loadtest.py's summary.json.
field() { sed -n "s/.*\"$1\": \"*\([^\",]*\).*/\1/p" "$2" | head -n 1; }

# ---------------------------------------------------------------- checks (the server is still up)

[ "$(id -u)" = 0 ] || die 'run as root (it stops and starts the server and runs a container)'
for tool in docker rsync curl sha512sum flock runuser; do
    command -v "$tool" >/dev/null || die "$tool is missing"
done
cd /
[ -f "$LIVE_DIR/docker/compose.yaml" ] || die "$LIVE_DIR has no docker/compose.yaml"
# rsync --delete into the copy: it must be neither the live folder, nor inside it, nor around it.
case "$COPY_DIR" in /?*/?*) ;; *) die "COPY_DIR=$COPY_DIR is not an absolute path two folders deep" ;; esac
case "$COPY_DIR/" in "$LIVE_DIR"/*) die "COPY_DIR=$COPY_DIR is inside the live folder" ;; esac
case "$LIVE_DIR/" in "$COPY_DIR"/*) die "COPY_DIR=$COPY_DIR holds the live folder" ;; esac
[ -f "$LOADTEST_PY" ] || die "no $LOADTEST_PY"
grep -q -- '--spark' "$LOADTEST_PY" ||
    die "$LOADTEST_PY predates --spark: copy tools/loadtest.py from a newer checkout here and set LOADTEST_PY"

# One at a time with deploys, the daily restart and off-site backups. Read-only: root may not open another
# user's file in /tmp for writing (fs.protected_regular), and flock works on any open file.
[ -e "$LOCK_FILE" ] || runuser -u "$(stat -c %U "$LIVE_DIR")" -- touch "$LOCK_FILE"
exec 9<"$LOCK_FILE"
flock -w 600 9 || die 'a deploy, restart or backup has held the deploy lock for 10 minutes; try again later'

running || die 'the live server is not running; start it first'
progress=$(rcon 'chunky progress' || true)
log "chunky progress: ${progress:-no answer}"
case "$progress" in
    *%*) [ -n "$FORCE" ] || die 'Chunky is still pre-generating, which takes the same two threads: measure after it finishes, or set FORCE=1' ;;
esac
# A copy would share a database server with the live one (fake players written into the real permissions).
if grep -Eiq '^[[:space:]]*storage-method[[:space:]]*[=:][[:space:]]*"?(mysql|mariadb|postgresql|mongodb)' \
    "$LIVE_DIR/server/config/luckperms/luckperms.conf" 2>/dev/null; then
    die 'LuckPerms uses a database server, which the copy would share; not safe to copy'
fi

mem=$(sed -n 's/^[[:space:]]*MEMORY_GB[[:space:]]*=[[:space:]]*//p' "$LIVE_DIR/docker/.env" 2>/dev/null | tr -d ' "\r' | tail -n 1)
mem=${mem:-8}
# The exact check comes once the server has stopped; this one only catches a machine that can never fit it.
total_gb=$(awk '/^MemTotal:/ { print int($2 / 1048576) }' /proc/meminfo)
[ "$total_gb" -ge $((mem + 3)) ] || die "the copy needs MEMORY_GB ($mem) plus 3 GB, and this machine has $total_gb GB"

mkdir -p "${COPY_DIR%/*}"
need=$(du -skx --exclude="$LIVE_DIR/backups" --exclude="$LIVE_DIR/exports" --exclude="$LIVE_DIR/loadtest" "$LIVE_DIR" | cut -f 1)
have=$(df -Pk "${COPY_DIR%/*}" | awk 'NR == 2 { print $4 }')
[ ! -d "$COPY_DIR" ] || have=$((have + $(du -skx "$COPY_DIR" | cut -f 1)))  # an old copy is reused
[ "$have" -gt $((need + 2097152)) ] ||
    die "the copy needs $((need / 1048576)) GB plus 2 GB to spare, and the disk has $((have / 1048576)) GB free"

stopped=''
work=''
cleanup() {
    status=$?
    set +e
    trap - EXIT INT TERM HUP
    docker rm -f realms-loadtest >/dev/null 2>&1
    if [ -n "$stopped" ]; then
        [ "$status" = 0 ] || discord 'The load test stopped with an error; see journalctl -u realms-loadtest.' "$STAFF_WEBHOOK_URL"
        log 'starting the live server again'
        if $COMPOSE up -d realms && wait_for_live; then
            log 'the live server is back up'
            discord 'Monkey SMP is back up after the performance test.' "$DISCORD_WEBHOOK_URL"
        else
            log "the live server did not answer within ${BOOT_TIMEOUT}s"
            discord "After the load test the live server did not answer within ${BOOT_TIMEOUT}s and may be DOWN. Check: journalctl -u realms-loadtest" "$STAFF_WEBHOOK_URL"
            status=1
        fi
    fi
    if [ -d "$COPY_DIR/loadtest" ]; then
        mkdir -p "$RESULTS" && cp -a "$COPY_DIR/loadtest/." "$RESULTS/" && log "results: $RESULTS"
    fi
    rm -rf "$COPY_DIR"
    rmdir "${COPY_DIR%/*}" 2>/dev/null
    [ -z "$work" ] || rm -rf "$work"
    docker image rm "$IMAGE" >/dev/null 2>&1
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

work=$(mktemp -d)
log 'downloading Carpet'
curl -fsSL -m 120 -o "$work/carpet.jar" "$CARPET_URL"
printf '%s  %s\n' "$CARPET_SHA512" "$work/carpet.jar" | sha512sum -c --quiet - ||
    die 'the Carpet download does not match its hash'
cp "$LOADTEST_PY" "$work/loadtest.py"

copy() {
    nice -n 10 rsync -a --delete "$@" --exclude /backups/ --exclude /exports/ --exclude /loadtest/ \
        "$LIVE_DIR/" "$COPY_DIR/"
}
log "copying $LIVE_DIR to $COPY_DIR while the server runs"
mkdir -p "$COPY_DIR"
copy

# ---------------------------------------------------------------- downtime starts

count=0
for s in $SCENARIOS; do count=$((count + 1)); done
minutes=$((5 + 10 * count))
online=$(players_online || true)
discord "Monkey SMP goes offline for about $minutes minutes for a performance test." "$DISCORD_WEBHOOK_URL"
if [ "${online:-0}" -gt 0 ]; then
    log "$online player(s) online; warning them"
    rcon "say Performance test in $WARN_MINUTES minutes (about $minutes minutes offline)." >/dev/null || true
    [ "$WARN_MINUTES" -le 1 ] || sleep $(((WARN_MINUTES - 1) * 60))
    rcon 'say Performance test in 1 minute. Find a safe spot.' >/dev/null || true
    sleep 60
fi

stopped=1
log 'stopping the live server'
$COMPOSE stop

free_gb=$(awk '/^MemAvailable:/ { print int($2 / 1048576) }' /proc/meminfo)
[ "$free_gb" -ge $((mem + 2)) ] ||
    die "with the server stopped only $free_gb GB of memory is free; the test needs MEMORY_GB ($mem) plus 2"

log 'copying what changed since (the world, now saved)'
copy --checksum

# Tebex would claim real purchases and run their commands on the copy. Its jar and its folder (mods/tebex
# holds its config and secret key) both go.
find "$COPY_DIR/server/mods" "$COPY_DIR/server/config" -maxdepth 1 -iname '*tebex*' -exec rm -rf {} +
if find "$COPY_DIR/server/mods" "$COPY_DIR/server/config" -iname '*tebex*' | grep -q .; then
    die 'could not take Tebex out of the copy'
fi
# A pre-generation task would resume in the copy and take the CPU the test measures.
chunky="$COPY_DIR/server/config/chunky/config.json"
[ ! -f "$chunky" ] || sed -i 's/"continueOnRestart": *true/"continueOnRestart": false/' "$chunky"

log 'building the image from the copy'
docker build -q -t "$IMAGE" "$COPY_DIR/docker" >/dev/null
log "running $SCENARIOS with $PLAYERS players, ${MINUTES} min each, ${mem} GB (no ports published)"
docker run --rm --name realms-loadtest -v "$COPY_DIR:/realms" -v "$work:/lt:ro" \
    -e SCENARIOS="$SCENARIOS" -e PLAYERS="$PLAYERS" -e MINUTES="$MINUTES" -e MEMORY_GB="$mem" \
    --entrypoint sh "$IMAGE" -c '
        set -e
        apt-get update -qq
        apt-get install -y -qq --no-install-recommends python3 >/dev/null
        for s in $SCENARIOS; do
            python3 -B /lt/loadtest.py /realms --carpet /lt/carpet.jar --players "$PLAYERS" --scenario "$s" \
                --minutes "$MINUTES" --memory-gb "$MEMORY_GB" --spark --name "$s-$PLAYERS"
        done'

report=''
for s in $SCENARIOS; do
    f="$COPY_DIR/loadtest/$s-$PLAYERS/summary.json"
    [ -f "$f" ] || continue
    line="$s, $PLAYERS players: median tick $(field mspt_median "$f") ms, p95 up to $(field p95_max "$f") ms, $(field tps "$f") TPS"
    url=$(field spark_profile "$f")
    [ -z "$url" ] || line="$line, all threads $url"
    report="$report $line."
done
log "result:${report:- none}"
discord "Load test on the live VPS:${report:- no results, see journalctl -u realms-loadtest.} Decision rule: docs/LIVE.md, Load test." "$STAFF_WEBHOOK_URL"
