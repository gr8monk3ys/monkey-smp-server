#!/bin/sh
# Keeps the live server on a Linux VPS in step with the repo (docs/LIVE.md). A systemd timer runs it
# every few minutes; it does nothing unless there is something new to deploy.
#
#   sh realms-deploy.sh            deploy the newest release tag (or TRACK branch) if it isn't live yet
#   sh realms-deploy.sh --now      the same, without the 5-minute warning to players online
#   sh realms-deploy.sh --status   print what is deployed and what would be
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
DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL:-}
LOCK_FILE=${LOCK_FILE:-/tmp/realms-deploy.lock}

STATE="$LIVE_DIR/.deployed"
FAILED="$LIVE_DIR/.deploy-failed"
COMPOSE="docker compose --project-directory $LIVE_DIR/docker -f $LIVE_DIR/docker/compose.yaml"

log() { printf '%s [deploy] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { log "ERROR: $*"; exit 1; }

now=''
status_only=''
for arg in "$@"; do
    case "$arg" in
        --now) now=1 ;;
        --status) status_only=1 ;;
        *) die "unknown option '$arg' (use --now or --status)" ;;
    esac
done

# One deploy at a time: the timer and a manual run must not overlap.
exec 9>"$LOCK_FILE"
flock -n 9 || { log 'another deploy is running; skipping'; exit 0; }

[ -d "$REPO_DIR/.git" ] || die "$REPO_DIR is not a git clone of the repo (docs/LIVE.md, step 3)"
[ -f "$LIVE_DIR/docker/compose.yaml" ] || [ ! -e "$LIVE_DIR" ] || die "$LIVE_DIR has no docker/compose.yaml"

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
    exit 0
fi

[ "$commit" != "$deployed" ] || exit 0
if [ "$commit" = "$failed" ]; then
    log "$ref ($commit) failed to boot before; waiting for a newer commit"
    exit 0
fi

# ---------------------------------------------------------------- helpers

discord() {
    [ -n "$DISCORD_WEBHOOK_URL" ] || return 0
    # The message is ours (no quotes or backslashes in it), so plain printf makes valid JSON.
    printf '{"content":"%s"}' "$1" |
        curl -fsS -m 15 -H 'Content-Type: application/json' -d @- "$DISCORD_WEBHOOK_URL" >/dev/null ||
        log 'could not post to Discord'
}

running() { [ -n "$($COMPOSE ps -q --status running realms 2>/dev/null)" ]; }

rcon() { $COMPOSE exec -T realms realms rcon "$1" 2>/dev/null; }

players_online() {
    # "There are 3 of a max of 20 players online: ..."
    rcon list | sed -n 's/.*There are \([0-9][0-9]*\) of.*/\1/p' | head -n 1
}

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

# ---------------------------------------------------------------- deploy

label=$ref
[ "$TRACK" = tags ] || label="$TRACK@$(git -C "$REPO_DIR" rev-parse --short "$commit")"
log "deploying $label ($commit); live: ${deployed:-nothing}"

# Players need the new client pack when client/ changed (mods added, removed or updated).
pack_changed=''
if [ -z "$deployed" ] || ! git -C "$REPO_DIR" diff --quiet "$deployed" "$commit" -- client/ 2>/dev/null; then
    pack_changed=1
fi

if running; then
    online=$(players_online || true)
    if [ -z "$now" ] && [ "${online:-0}" -gt 0 ]; then
        log "$online player(s) online; warning them"
        rcon "say Server update to $label in $WARN_MINUTES minutes (about 3 minutes offline)." >/dev/null || true
        [ "$WARN_MINUTES" -le 1 ] || sleep $(((WARN_MINUTES - 1) * 60))
        rcon 'say Server update in 1 minute. Find a safe spot.' >/dev/null || true
        sleep 60
    fi
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
