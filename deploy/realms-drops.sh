#!/bin/sh
# Weeknight supply drops (tools/drops.py; docs/ADMIN.md, "Supply drops"): sends the output of
# `python3 tools/drops.py commands WORLD` to the server over RCON (`drops.py send`, which reads each answer
# through tools/rcon.py and says what the try's return code means; this only schedules and logs). Minecraft
# can't see claims or the wall
# clock, so this picks the spots (from the saved claims and border) and the night; the realms-drops data pack
# decides the rest (enough players online, no drop yet tonight, no event on). realms-drops.timer runs it every
# 10 minutes as the realms user. Outside drop hours (Monday to Thursday, 6 to 10 PM Pacific) there is nothing
# to send, and once tonight's drop has run the pack turns the rest away, so running it again is safe.
# Sending waits up to 30 minutes for the deploy lock (deploy/lib.sh), so it never lands while a deploy, the
# daily restart or an off-site backup has the server stopped or not saving.
#
#   sh realms-drops.sh                  sends the commands (a server that isn't running is skipped)
#   sh realms-drops.sh --check          prints the spots and commands for now and whether the timer is installed
#                                       and running; changes nothing
#   sudo sh realms-drops.sh --install   copies realms-drops.service and realms-drops.timer from the deployed
#                                       checkout to /etc/systemd/system (only if they changed) and starts the timer
#
# It reads only REPO_DIR and LIVE_DIR from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV), without sourcing it,
# so the webhooks are never read. It reads the saved world (claims and the border) and nothing else from it.
# RCON goes through the container's own `realms rcon`, which finds the password itself. No secret is read,
# printed or asked for. Needs python3 3.10 or newer (deploy/upgrade-2.5.0.sh installs it).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

case "${1:-}" in
    '') MODE=send ;;
    --check) MODE=check ;;
    --install) MODE=install ;;
    *) echo "usage: sh $0 [--check | --install]" >&2; exit 2 ;;
esac

LOG_NAME=realms-drops
. "$(dirname -- "$0")/lib.sh"

ENV_FILE=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/realms/repo)}
LOCK_FILE=${LOCK_FILE:-$(setting LOCK_FILE /tmp/realms-deploy.lock)}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/realms/TheRealms-Server)}
WORLD=$LIVE_DIR/server/world
TOOL=$REPO_DIR/tools/drops.py

UNITS='realms-drops.service realms-drops.timer'
TIMER=realms-drops.timer

# The commands for now, one per line: the spots, then `function realms:drops/try {night:N}`. None outside
# drop hours, or when no spot clear of every claim is left in the ring.
need_tool() {
    command -v python3 >/dev/null 2>&1 || die 'python3 is missing (deploy/upgrade-2.5.0.sh installs it)'
    [ -r "$TOOL" ] || die "$TOOL is missing: is the release with supply drops deployed?"
}
commands() {
    python3 -B "$TOOL" commands "$WORLD" || die 'tools/drops.py commands failed'
}

case $MODE in
    check)
        need_tool
        python3 -B "$TOOL" spots "$WORLD" 2>&1 | while IFS= read -r l; do log "$l"; done
        out=$(commands)
        log 'commands for now:'
        [ -n "$out" ] || log '  none (outside drop hours, or no spot)'
        printf '%s\n' "$out" | while IFS= read -r c; do [ -z "$c" ] || log "  $c"; done
        timer_state "$TIMER" $UNITS
        python3 -B "$REPO_DIR/tools/rcon.py" running --docker "$LIVE_DIR/docker" && up=0 || up=$?
        case $up in
            0) log 'server: running' ;;
            1) log 'server: not running (nothing would be sent)' ;;
            *) log "server: can't tell (docker failed; see above)" ;;
        esac
        log 'check finished: nothing was changed'
        ;;
    install)
        [ "$(id -u)" = 0 ] || die 'run as root: it installs systemd units'
        for u in $UNITS; do
            [ -r "$REPO_DIR/deploy/$u" ] || die "$REPO_DIR/deploy/$u is missing: is the release with supply drops deployed?"
        done
        install_timer "$TIMER" $UNITS
        ;;
    send)
        # Outside drop hours there is nothing to send: no log line every 10 minutes, and no deploy lock taken.
        need_tool
        out=$(commands)
        [ -n "$out" ] || exit 0
        deploy_lock 1800 || die "the deploy lock was taken for 30 minutes (the timer tries again in 10 minutes)"
        log_each python3 -B -u "$TOOL" send "$WORLD" --docker "$LIVE_DIR/docker" ||
            die 'not every command went through (the timer tries again in 10 minutes)'
        ;;
esac
