#!/bin/sh
# Keeps the weekly challenges and Season I's launch weekend on the wall clock (tools/challenges.py): sends the
# output of `python3 tools/challenges.py commands` to the server over RCON (`challenges.py send`, which reads each
# answer through tools/rcon.py; this only schedules and logs). Minecraft has no wall clock, so this
# is how the server learns that a new week started (Monday, 12 AM Pacific) and when the launch weekend ends.
# realms-week.timer runs it every hour as the realms user. Both commands do nothing when nothing changed, so
# running it again, or by hand, is safe.
# Sending waits up to 30 minutes for the deploy lock (deploy/lib.sh), so it never lands while a deploy, the
# daily restart or an off-site backup has the server stopped or not saving.
#
#   sh realms-week.sh                  sends the commands (a server that isn't running is skipped: the week is
#                                      a score in the world, so the next hour catches up)
#   sh realms-week.sh --check          prints the commands for now and whether the timer is installed and
#                                      running; changes nothing
#   sudo sh realms-week.sh --install   copies realms-week.service and realms-week.timer from the deployed
#                                      checkout to /etc/systemd/system (only if they changed) and starts the timer
#
# It reads only REPO_DIR and LIVE_DIR from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV), without sourcing it,
# so the webhooks are never read. RCON goes through the container's own `realms rcon`, which finds the password
# itself. No secret is read, printed or asked for. Needs python3 3.10 or newer (deploy/upgrade-2.5.0.sh
# installs it).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

case "${1:-}" in
    '') MODE=send ;;
    --check) MODE=check ;;
    --install) MODE=install ;;
    *) echo "usage: sh $0 [--check | --install]" >&2; exit 2 ;;
esac

LOG_NAME=realms-week
. "$(dirname -- "$0")/lib.sh"
die() { DIED=$*; log "ERROR: $*" >&2; exit 1; }

ENV_FILE=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/realms/repo)}
LOCK_FILE=${LOCK_FILE:-$(setting LOCK_FILE /tmp/realms-deploy.lock)}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/realms/TheRealms-Server)}

UNITS='realms-week.service realms-week.timer'
TIMER=realms-week.timer

TOOL=$REPO_DIR/tools/challenges.py
need_tool() {
    command -v python3 >/dev/null 2>&1 || die 'python3 is missing (deploy/upgrade-2.5.0.sh installs it)'
    [ -r "$TOOL" ] || die "$TOOL is missing: is the release with the weekly challenges deployed?"
}

# The commands for now, one per line: `function realms:challenges/sync {week:N}`, and during and just after
# the launch weekend `function realms:wardrobe/founder/sync {seconds:N}`.
commands() {
    python3 -B "$TOOL" commands || die 'tools/challenges.py commands failed'
}

case $MODE in
    check)
        need_tool
        out=$(commands)
        log 'commands for now:'
        printf '%s\n' "$out" | while IFS= read -r c; do log "  $c"; done
        timer_state "$TIMER" $UNITS
        python3 -B "$REPO_DIR/tools/rcon.py" running --docker "$LIVE_DIR/docker" && up=0 || up=$?
        case $up in
            0) log 'server: running' ;;
            1) log 'server: not running (nothing would be sent this hour)' ;;
            *) log "server: can't tell (docker failed; see above)" ;;
        esac
        log 'check finished: nothing was changed'
        ;;
    install)
        [ "$(id -u)" = 0 ] || die 'run as root: it installs systemd units'
        for u in $UNITS; do
            [ -r "$REPO_DIR/deploy/$u" ] || die "$REPO_DIR/deploy/$u is missing: is the release with the weekly challenges deployed?"
        done
        install_timer "$TIMER" $UNITS
        ;;
    send)
        need_tool
        deploy_lock 1800 || die "the deploy lock was taken for 30 minutes (the next hour tries again)"
        log_each python3 -B -u "$TOOL" send --docker "$LIVE_DIR/docker" ||
            die 'not every command went through (the next hour tries again)'
        ;;
esac
