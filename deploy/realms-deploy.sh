#!/bin/sh
# Keeps the live server on a Linux VPS in step with the repo (docs/LIVE.md). A systemd timer runs it
# every few minutes; it does nothing unless there is something new to deploy.
#
#   sh realms-deploy.sh            deploy the newest release tag (or TRACK branch) if it isn't live yet
#   sh realms-deploy.sh --now      the same, right away: ignores DEPLOY_WINDOW and skips the warning
#   sh realms-deploy.sh --status   print what is deployed and what would be
#   sh realms-deploy.sh --restart  the daily restart (realms-restart.timer): warn, restart, post a spark
#                                  health link; skipped when the server started less than
#                                  RESTART_MIN_UPTIME hours ago (a deploy already restarted it)
#
# With DEPLOY_WINDOW set (e.g. 04:00-05:00, in DEPLOY_TZ), a new release waits for that window, so a
# fix tagged in the afternoon goes live at 4 AM. The first deploy on a new machine doesn't wait.
#
# What a deploy does:
#   1. git fetch; pick the newest vX.Y.Z tag (TRACK=tags, the default) or the tip of TRACK=<branch>
#   2. if players are online, warn them in chat 5 minutes and 1 minute ahead
#   3. back up the world (realms backup, while the server runs)
#   4. copy package/ of that commit over the live release folder, keeping server/, backups/, java/,
#      the downloads and docker/.env (the same as unzipping a new release over the old one)
#   5. recreate the container: its entrypoint runs the idempotent install, then starts the server
#   6. wait for the server to answer RCON; if it doesn't, put the previous commit back the same way
#      and remember the failed one so it isn't retried every run
#   7. post the result to Discord (DISCORD_WEBHOOK_URL), saying whether players must update their pack
#
# Settings come from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV); see realms-deploy.env.example.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

ENV_FILE=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
# shellcheck disable=SC1090
[ ! -f "$ENV_FILE" ] || . "$ENV_FILE"

REPO_DIR=${REPO_DIR:-/srv/realms/repo}
LIVE_DIR=${LIVE_DIR:-/srv/realms/TheRealms-Server}
TRACK=${TRACK:-tags}
WARN_MINUTES=${WARN_MINUTES:-5}
BOOT_TIMEOUT=${BOOT_TIMEOUT:-900}
DEPLOY_WINDOW=${DEPLOY_WINDOW:-}
DEPLOY_TZ=${DEPLOY_TZ:-America/Los_Angeles}
DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL:-}
STAFF_WEBHOOK_URL=${STAFF_WEBHOOK_URL:-$DISCORD_WEBHOOK_URL}
RESTART_MIN_UPTIME=${RESTART_MIN_UPTIME:-6}
LOCK_FILE=${LOCK_FILE:-/tmp/realms-deploy.lock}

STATE="$LIVE_DIR/.deployed"
FAILED="$LIVE_DIR/.deploy-failed"
COMPOSE="docker compose --project-directory $LIVE_DIR/docker -f $LIVE_DIR/docker/compose.yaml"

log() { printf '%s [deploy] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { log "ERROR: $*"; exit 1; }

now=''
status_only=''
restart=''
for arg in "$@"; do
    case "$arg" in
        --now) now=1 ;;
        --status) status_only=1 ;;
        --restart) restart=1 ;;
        *) die "unknown option '$arg' (use --now, --status or --restart)" ;;
    esac
done

# One deploy at a time: the timer and a manual run must not overlap. The daily restart takes the same
# lock, so it never runs during a deploy (or an off-site backup, which waits for this lock too); it waits
# for one to finish, and then usually finds the server freshly started and skips.
exec 9>"$LOCK_FILE"
if [ -n "$restart" ]; then
    flock -w 1800 9 || { log 'the deploy lock was taken for 30 minutes; skipping the daily restart'; exit 0; }
else
    flock -n 9 || { log 'another deploy is running; skipping'; exit 0; }
fi

# DEPLOY_WINDOW "HH:MM-HH:MM" as two HHMM numbers; a window may cross midnight (23:00-01:00).
window_start=''
window_end=''
if [ -n "$DEPLOY_WINDOW" ]; then
    window_start=$(printf '%s' "${DEPLOY_WINDOW%%-*}" | tr -d ':')
    window_end=$(printf '%s' "${DEPLOY_WINDOW#*-}" | tr -d ':')
    for t in "$window_start" "$window_end"; do
        case "$t" in
            [01][0-9][0-5][0-9] | 2[0-3][0-5][0-9]) ;;
            *) die "DEPLOY_WINDOW '$DEPLOY_WINDOW' is not HH:MM-HH:MM (e.g. 04:00-05:00)" ;;
        esac
    done
    [ "$window_start" != "$window_end" ] || die "DEPLOY_WINDOW '$DEPLOY_WINDOW' starts and ends at the same time"
fi

clock() { TZ=$DEPLOY_TZ date +%H%M; }

# True when there is no window or the clock in DEPLOY_TZ is inside it. `[ -lt ]` reads 0400 as decimal.
in_window() {
    [ -n "$DEPLOY_WINDOW" ] || return 0
    t=$(clock)
    if [ "$window_start" -lt "$window_end" ]; then
        [ "$t" -ge "$window_start" ] && [ "$t" -lt "$window_end" ]
    else
        [ "$t" -ge "$window_start" ] || [ "$t" -lt "$window_end" ]
    fi
}

[ -d "$REPO_DIR/.git" ] || die "$REPO_DIR is not a git clone of the repo (docs/LIVE.md, step 3)"
[ -f "$LIVE_DIR/docker/compose.yaml" ] || [ ! -e "$LIVE_DIR" ] || die "$LIVE_DIR has no docker/compose.yaml"

# ---------------------------------------------------------------- helpers

# Posts $1 to the webhook $2 (default DISCORD_WEBHOOK_URL).
discord() {
    url=${2:-$DISCORD_WEBHOOK_URL}
    [ -n "$url" ] || return 0
    # The message is ours (no quotes or backslashes in it), so plain printf makes valid JSON.
    printf '{"content":"%s"}' "$1" |
        curl -fsS -m 15 -H 'Content-Type: application/json' -d @- "$url" >/dev/null ||
        log 'could not post to Discord'
}

running() { [ -n "$($COMPOSE ps -q --status running realms 2>/dev/null)" ]; }

rcon() { $COMPOSE exec -T realms realms rcon "$1" 2>/dev/null; }

players_online() {
    # "There are 3 of a max of 20 players online: ..."
    rcon list | sed -n 's/.*There are \([0-9][0-9]*\) of.*/\1/p' | head -n 1
}

# If players are online, warns them in chat WARN_MINUTES and 1 minute ahead. $1 begins the first
# message ("Server update to v2.4.1"), $2 the last ("Server update").
warn_players() {
    warn_online=$(players_online || true)
    [ "${warn_online:-0}" -gt 0 ] || return 0
    log "$warn_online player(s) online; warning them"
    rcon "say $1 in $WARN_MINUTES minutes (about 3 minutes offline)." >/dev/null || true
    [ "$WARN_MINUTES" -le 1 ] || sleep $(((WARN_MINUTES - 1) * 60))
    rcon "say $2 in 1 minute. Find a safe spot." >/dev/null || true
    sleep 60
}

# Recreates the container (its entrypoint installs, then starts) and waits for RCON to answer.
restart_and_wait() {
    $COMPOSE up -d --build --force-recreate
    waited=0
    while [ "$waited" -lt "$BOOT_TIMEOUT" ]; do
        sleep 15
        waited=$((waited + 15))
        running || return 1
        if rcon list >/dev/null; then return 0; fi
    done
    return 1
}

# Whole hours since the container started (a deploy recreates it, and so does a crash); empty if unknown.
uptime_hours() {
    id=$($COMPOSE ps -q realms 2>/dev/null) || return 0
    [ -n "$id" ] || return 0
    started=$(docker inspect -f '{{.State.StartedAt}}' "$id" 2>/dev/null) || return 0
    since=$(date -d "$started" +%s 2>/dev/null) || return 0
    echo $((($(date +%s) - since) / 3600))
}

# The link to a fresh `spark health` report (TPS, tick times, CPU, memory, GC), or nothing. spark answers
# from its own thread after the RCON reply has gone, but it also sends the link to the console, so the link
# is read from the server log.
spark_health() {
    log_file="$LIVE_DIR/server/logs/latest.log"
    seen=$(wc -l <"$log_file" 2>/dev/null || echo 0)
    rcon 'spark health upload' >/dev/null || return 0
    waited=0
    while [ "$waited" -lt 30 ]; do
        sleep 3
        waited=$((waited + 3))
        link=$(tail -n "+$((seen + 1))" "$log_file" 2>/dev/null | grep -o 'https://spark\.lucko\.me/[A-Za-z0-9]*' | tail -n 1)
        if [ -n "$link" ]; then
            echo "$link"
            return 0
        fi
    done
}

# ---------------------------------------------------------------- daily restart (--restart)

# Bounds memory creep: one restart a day, inside the deploy window but after the deploy, which already
# restarts the server when there is a release. The health report from just before the restart shows
# whether memory use keeps climbing from day to day (a leak a restart only hides).
if [ -n "$restart" ]; then
    running || { log 'the server is not running; nothing to restart'; exit 0; }
    hours=$(uptime_hours)
    if [ -n "$hours" ] && [ "$hours" -lt "$RESTART_MIN_UPTIME" ]; then
        log "the server started ${hours}h ago (a deploy or a crash restarted it); skipping the daily restart"
        exit 0
    fi
    online=$(players_online || true)
    health=$(spark_health)
    log "daily restart after ${hours:-?}h up; spark health: ${health:-no link}"
    warn_players 'Daily restart' 'Daily restart'
    if restart_and_wait; then
        log 'back up after the daily restart'
        msg="Daily restart: Monkey SMP is back up (it had been up ${hours:-?} h, ${online:-?} online)."
        [ -z "$health" ] || msg="$msg spark health just before: $health"
        discord "$msg" "$STAFF_WEBHOOK_URL"
        exit 0
    fi
    discord "Daily restart: the server did not answer within ${BOOT_TIMEOUT}s and may be DOWN. Check: journalctl -u realms-restart" "$STAFF_WEBHOOK_URL"
    die "the server did not answer within ${BOOT_TIMEOUT}s after the daily restart"
fi

# ---------------------------------------------------------------- what to deploy

git -C "$REPO_DIR" fetch --quiet --tags --prune --force origin

target_ref() {
    if [ "$TRACK" = tags ]; then
        git -C "$REPO_DIR" tag -l 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | head -n 1
    else
        echo "origin/$TRACK"
    fi
}

ref=$(target_ref)
[ -n "$ref" ] || die "no release tag (vX.Y.Z) in the repo yet"
commit=$(git -C "$REPO_DIR" rev-parse --verify "$ref^{commit}")
deployed=$(cat "$STATE" 2>/dev/null || true)
failed=$(cat "$FAILED" 2>/dev/null || true)

if [ -n "$status_only" ]; then
    echo "track:    $TRACK"
    echo "newest:   $ref ($commit)"
    echo "deployed: ${deployed:-nothing yet}"
    [ -z "$failed" ] || echo "failed:   $failed (skipped until a newer commit)"
    if [ -n "$DEPLOY_WINDOW" ]; then
        if in_window; then state='open'; else state='closed'; fi
        echo "window:   $DEPLOY_WINDOW $DEPLOY_TZ (now $(clock), $state)"
    fi
    exit 0
fi

[ "$commit" != "$deployed" ] || exit 0
if [ "$commit" = "$failed" ]; then
    log "$ref ($commit) failed to boot before; waiting for a newer commit"
    exit 0
fi
if [ -z "$now" ] && [ -n "$deployed" ] && ! in_window; then
    log "$ref is waiting for the $DEPLOY_WINDOW $DEPLOY_TZ deploy window (--now deploys it now)"
    exit 0
fi

# ---------------------------------------------------------------- deploy

# Copies package/ of commit $1 over the live folder. The excluded paths are what the server and
# installer create (the same list tools/build.py keeps out of a release) plus our state files;
# rsync --delete never removes excluded paths.
sync_package() {
    tmp=$(mktemp -d)
    git -C "$REPO_DIR" archive "$1" package | tar -x -C "$tmp"
    mkdir -p "$LIVE_DIR"
    rsync -a --delete \
        --exclude '/server/' --exclude '/java/' --exclude '/backups/' --exclude '/exports/' \
        --exclude '/downloads/' --exclude '/pwsh/' --exclude '/docker/.env' \
        --exclude '/.realms-launch' --exclude '/smoke-console.log*' \
        --exclude '/.deployed' --exclude '/.deploy-failed' \
        "$tmp/package/" "$LIVE_DIR/"
    rm -rf "$tmp"
}

label=$ref
[ "$TRACK" = tags ] || label="$TRACK@$(git -C "$REPO_DIR" rev-parse --short "$commit")"
log "deploying $label ($commit); live: ${deployed:-nothing}"

# Players need the new client pack when client/ changed (mods added, removed or updated). Every
# release bumps "versionId" in the pack index, and that alone doesn't make an old pack unable to join.
index_without_version() {
    git -C "$REPO_DIR" show "$1:client/modrinth.index.json" 2>/dev/null | grep -v '^[[:space:]]*"versionId":'
}
pack_changed=''
if [ -z "$deployed" ] ||
    ! git -C "$REPO_DIR" diff --quiet "$deployed" "$commit" -- client/ ':(exclude)client/modrinth.index.json' 2>/dev/null ||
    [ "$(index_without_version "$deployed")" != "$(index_without_version "$commit")" ]; then
    pack_changed=1
fi

if running; then
    [ -n "$now" ] || warn_players "Server update to $label" 'Server update'
    log 'backing up the world'
    $COMPOSE exec -T realms realms backup || die 'backup failed; not deploying'
fi

sync_package "$commit"
[ -f "$LIVE_DIR/docker/.env" ] ||
    die "first deploy: copy $LIVE_DIR/docker/.env.example to .env, set EULA=TRUE and OWNER, then run this again"
if restart_and_wait; then
    echo "$commit" >"$STATE"
    rm -f "$FAILED"
    # The next run uses this commit's copy of this script. git replaces files rather than writing
    # into them, so the copy running now is unaffected.
    git -C "$REPO_DIR" checkout --quiet --force --detach "$commit"
    log "live: $label"
    msg="Monkey SMP is back up on $label."
    [ -z "$pack_changed" ] || msg="$msg The mod list changed: update your modpack before joining (see the site)."
    discord "$msg"
    exit 0
fi

log "$label did not come up within ${BOOT_TIMEOUT}s"
echo "$commit" >"$FAILED"
if [ -n "$deployed" ]; then
    log "rolling back to $deployed"
    sync_package "$deployed"
    if restart_and_wait; then
        discord "Update to $label failed to start; rolled back to the previous version. The server is up."
        exit 1
    fi
fi
discord "Update to $label failed and the server is DOWN. Check: journalctl -u realms-deploy"
exit 1
