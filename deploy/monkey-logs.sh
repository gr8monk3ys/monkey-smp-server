#!/bin/sh
# Deletes the server's old log files, so the privacy page's "Server logs ... then they are deleted" holds. Started
# daily by monkey-logs.timer as monkey; docs/LIVE.md, "Log pruning".
#
#   sh monkey-logs.sh            deletes what is older than LOG_KEEP_DAYS
#   sh monkey-logs.sh --check    lists what it would delete, and deletes nothing
#
# What it deletes, in LIVE_DIR/server/logs only (no other folder, nothing below it, no links):
#   YYYY-MM-DD-N.log.gz   the server's daily logs, by the date in the name: older than LOG_KEEP_DAYS days
#   debug-N.log.gz        the debug logs, by when they were last written: more than LOG_KEEP_DAYS days ago
# It never touches latest.log or debug.log (the logs being written), the world, the backups or anything else.
#
# LOG_KEEP_DAYS comes from /etc/monkey-deploy.env (default 90) and is at least 14, so a typo can't empty the folder
# staff use for reports and appeals. The privacy page names no number of days; when it does, set the same here.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=monkey-logs
. "$(dirname -- "$0")/lib.sh"

ENV_FILE=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/monkey/MonkeySMP-Server)}
KEEP_DAYS=${LOG_KEEP_DAYS:-$(setting LOG_KEEP_DAYS 90)}
LOGS=$LIVE_DIR/server/logs

mode=delete
case "${1:-}" in
    '') ;;
    --check) mode=check ;;
    *) echo "usage: sh $0 [--check]" >&2; exit 2 ;;
esac
whole_number LOG_KEEP_DAYS "$KEEP_DAYS" days
[ "$KEEP_DAYS" -ge 14 ] || die "LOG_KEEP_DAYS is $KEEP_DAYS; it must be at least 14"

if [ ! -d "$LOGS" ] || [ -L "$LOGS" ]; then
    log "no logs folder at $LOGS: nothing to do"
    exit 0
fi

# The newest day that is deleted: a log named for this day or an earlier one is older than KEEP_DAYS.
cutoff=$(date -u -d "@$(($(date +%s) - (KEEP_DAYS + 1) * 86400))" +%Y-%m-%d)

old=$(
    find "$LOGS" -mindepth 1 -maxdepth 1 -type f -name '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-*.log.gz' |
        while IFS= read -r f; do
            day=${f##*/}
            day=${day%"${day#??????????}"}
            # Plain string order is date order for YYYY-MM-DD.
            if ! expr "$day" \> "$cutoff" >/dev/null; then printf '%s\n' "$f"; fi
        done
    find "$LOGS" -mindepth 1 -maxdepth 1 -type f -name 'debug-[0-9]*.log.gz' -mtime +"$KEEP_DAYS"
)

if [ -z "$old" ]; then
    log "no log in $LOGS is older than $KEEP_DAYS days"
    exit 0
fi
count=$(printf '%s\n' "$old" | wc -l | tr -d ' ')
if [ "$mode" = check ]; then
    log "$count log file(s) in $LOGS are older than $KEEP_DAYS days; a run would delete:"
    printf '%s\n' "$old" | while IFS= read -r f; do log "  ${f##*/}"; done
    exit 0
fi
printf '%s\n' "$old" | while IFS= read -r f; do rm -f -- "$f"; done
log "deleted $count log file(s) older than $KEEP_DAYS days from $LOGS (logs from $cutoff and before)"
