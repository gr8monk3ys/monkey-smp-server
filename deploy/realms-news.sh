#!/bin/sh
# Monkey SMP news on the live VPS (tools/news.py; docs/ADMIN.md, "Monkey SMP news"): one plain line in the
# public Discord channel when something notable happens (a Server First such as the Ender Dragon, the first
# finish of a rare challenge, a new faction), a few a week at most. realms-news.timer runs it every 10 minutes
# as the realms user. It reads only the saved world (the server saves every 5 minutes): no RCON, nothing sent to
# the server, no log read.
#
#   sh realms-news.sh                  posts what is due (realms-news.timer)
#   sh realms-news.sh --check          prints what the next run would post and what waits, whether the webhook is
#                                      set (never its value) and whether the timer is installed and running;
#                                      changes nothing
#   sudo sh realms-news.sh --install   makes NEWS_DIR (owned by the live folder's owner, realms), copies
#                                      realms-news.service and realms-news.timer from the deployed checkout to
#                                      /etc/systemd/system (only if they changed) and starts the timer
#
# Reads REPO_DIR, LIVE_DIR, LOCK_FILE, NEWS_DIR (default /srv/realms/news, one season-<n>.json per season) and
# the webhook NEWS_WEBHOOK_URL from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV), without sourcing it. The
# webhook goes to the tool in its environment and is never printed; with none set nothing runs, so turning it
# on mid-season is a late start (tools/news.py keeps what is already in the world as baseline). Posting skips
# the run while a deploy, the daily restart or a backup holds the deploy lock. Needs python3 3.11 or newer.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=realms-news
. "$(dirname -- "$0")/lib.sh"

case "${1:-}" in
    '') MODE=post ;;
    --check) MODE=check ;;
    --install) MODE=install ;;
    *) echo "usage: sh $0 [--check | --install]" >&2; exit 2 ;;
esac

ENV_FILE=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/realms/repo)}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/realms/TheRealms-Server)}
LOCK_FILE=${LOCK_FILE:-$(setting LOCK_FILE /tmp/realms-deploy.lock)}
NEWS_DIR=${NEWS_DIR:-$(setting NEWS_DIR /srv/realms/news)}
UNITS='realms-news.service realms-news.timer'

if [ "$MODE" = install ]; then
    [ "$(id -u)" = 0 ] || die 'run as root: it installs systemd units'
    for u in $UNITS; do
        [ -r "$REPO_DIR/deploy/$u" ] || die "$REPO_DIR/deploy/$u is missing: is the release with the news deployed?"
    done
    owner=$(stat -c %U "$LIVE_DIR" 2>/dev/null) || die "no live folder at $LIVE_DIR"
    install -d -m 755 -o "$owner" -g "$owner" "$NEWS_DIR"
    log "news folder: $NEWS_DIR (owned by $owner)"
    # shellcheck disable=SC2086
    install_timer realms-news.timer $UNITS
    exit 0
fi

TOOL=$REPO_DIR/tools/news.py
WORLD=$LIVE_DIR/server/world
command -v python3 >/dev/null 2>&1 || die 'python3 is missing (deploy/install-standings.sh installs it)'
python_ok 11 || die "python3 is older than 3.11 (party names are TOML): $(python3 --version 2>&1)"
[ -r "$TOOL" ] || die "$TOOL is missing: is the release with the news deployed?"
NEWS_WEBHOOK_URL=${NEWS_WEBHOOK_URL:-$(setting NEWS_WEBHOOK_URL)}

if [ "$MODE" = check ]; then
    if [ -n "$NEWS_WEBHOOK_URL" ]; then log 'webhook: set'; else log 'webhook: not set (NEWS_WEBHOOK_URL): nothing posts'; fi
    rc=0
    log_each python3 -B "$TOOL" preview "$WORLD" --state "$NEWS_DIR" || rc=$?
    # shellcheck disable=SC2086
    timer_state realms-news.timer $UNITS
    [ "$rc" = 0 ] || log "the preview failed (exit $rc): a source couldn't be read, see above"
    log 'check finished: nothing was changed'
    exit "$rc"
fi

# Root would make a news file realms can't change, and a lock file realms-deploy.sh can't open.
[ "$(id -u)" != 0 ] || { echo "run it as realms: sudo -u realms sh $0" >&2; exit 1; }
[ -n "$NEWS_WEBHOOK_URL" ] || { log 'no NEWS_WEBHOOK_URL in the settings; not posting'; exit 0; }
deploy_lock 60 || { log 'a deploy, restart or backup is running; skipping this run'; exit 0; }
mkdir -p "$NEWS_DIR"
export NEWS_WEBHOOK_URL
log_each python3 -B -u "$TOOL" post "$WORLD" --state "$NEWS_DIR"
