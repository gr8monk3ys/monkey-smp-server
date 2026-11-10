#!/bin/sh
# Tells staff on Discord that a Monkey SMP unit failed. systemd starts it through monkey-alert@.service: every
# monkey-* service has OnFailure=monkey-alert@%n.service, so `monkey-alert@monkey-day.service.service` runs
#   sh monkey-alert.sh monkey-day.service
# docs/LIVE.md, "Failure alerts".
#
# The post: "Monkey SMP: UNIT failed. Check: journalctl -u UNIT", to STAFF_WEBHOOK_URL, else DISCORD_WEBHOOK_URL,
# from /etc/monkey-deploy.env (read, never sourced; the URL is never printed). No webhook: it logs and posts nothing.
#
# Repeats: at most one post per unit in 6 hours (ALERT_QUIET_HOURS). A failure inside that time is counted, not
# posted, and the next post says how many there were. A unit that retries every 10 minutes, or one that systemd
# restarts and that fails each time, so posts once, not dozens of times. systemd runs one copy of an instance at a
# time, so two failures of one unit can't race on its count.
#
# Exit 4 means "failed, and staff were already told" (a timed job that gave up, a deploy or daily restart that
# posted its own DOWN message): for those it posts nothing, so one failure is one message.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=monkey-alert
. "$(dirname -- "$0")/lib.sh"

ENV_FILE=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
STATE=${ALERT_STATE:-${STATE_DIRECTORY:-/var/lib/monkey-alert}}
QUIET_HOURS=${ALERT_QUIET_HOURS:-6}
whole_number ALERT_QUIET_HOURS "$QUIET_HOURS" hours

unit=${1:-}
case $unit in
    monkey-*.service) ;;
    *) echo "usage: sh $0 monkey-NAME.service" >&2; exit 2 ;;
esac
# A unit name only: it is a file name in STATE and goes into a Discord message.
case $unit in *[!A-Za-z0-9@._-]*) die "not a unit name: $unit" ;; esac

status=$(systemctl show -p ExecMainStatus --value "$unit" 2>/dev/null || true)
if [ "$status" = 4 ]; then
    log "$unit failed with exit 4: it told staff itself, so nothing more is posted"
    exit 0
fi

hook=$(setting STAFF_WEBHOOK_URL '')
[ -n "$hook" ] || hook=$(setting DISCORD_WEBHOOK_URL '')
if [ -z "$hook" ]; then
    log "$unit failed; no STAFF_WEBHOOK_URL or DISCORD_WEBHOOK_URL in $ENV_FILE, so nothing is posted"
    exit 0
fi

mkdir -p "$STATE"
file=$STATE/$unit
now=$(date +%s)
last=0
missed=0
[ ! -f "$file" ] || read -r last missed <"$file" || true
case $last in '' | *[!0-9]*) last=0 ;; esac
case $missed in '' | *[!0-9]*) missed=0 ;; esac

if [ $((now - last)) -lt $((QUIET_HOURS * 3600)) ]; then
    missed=$((missed + 1))
    printf '%s %s\n' "$last" "$missed" >"$file.new"
    mv -f "$file.new" "$file"
    log "$unit failed again; staff heard about it less than ${QUIET_HOURS} h ago: counted ($missed), not posted"
    exit 0
fi

msg="Monkey SMP: $unit failed. Check: journalctl -u $unit"
[ "$missed" -eq 0 ] || msg="$msg (It also failed $missed more time(s) since the last alert about it.)"
discord "$msg" "$hook"
printf '%s 0\n' "$now" >"$file.new"
mv -f "$file.new" "$file"
log "posted: $unit failed"
