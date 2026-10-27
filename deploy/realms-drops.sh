#!/bin/sh
# Weeknight supply drops (tools/drops.py; docs/ADMIN.md, "Supply drops"): sends the output of
# `python3 tools/drops.py commands WORLD` to the server over RCON (`drops.py send`, which reads each answer
# through tools/rcon.py and says what the try's return code means; this only schedules and logs). Minecraft
# can't see claims or the wall
# clock, so this picks the spots (from the saved claims and border) and the night; the realms-drops data pack
# decides the rest (enough players online, no drop yet tonight, no event on). realms-drops.timer runs it every
# 10 minutes as the realms user. Outside drop hours (Monday to Thursday, 6 to 10 PM Pacific) there is nothing
# to send, and once tonight's drop has run the pack turns the rest away, so running it again is safe.
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

ENV_FILE=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}

# "setting NAME DEFAULT": NAME's value in the env file (the last one, quotes dropped), else DEFAULT.
setting() {
    v=''
    [ ! -r "$ENV_FILE" ] ||
        v=$(sed -n "s/^[[:space:]]*$1=//p" "$ENV_FILE" | tail -n 1 | sed -e 's/[[:space:]]*$//' -e "s/^[\"']//" -e "s/[\"']\$//")
    printf '%s' "${v:-$2}"
}
REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/realms/repo)}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/realms/TheRealms-Server)}
WORLD=$LIVE_DIR/server/world
TOOL=$REPO_DIR/tools/drops.py

UNITS='realms-drops.service realms-drops.timer'
TIMER=realms-drops.timer

log() { printf '%s [realms-drops] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

compose() { docker compose --project-directory "$LIVE_DIR/docker" -f "$LIVE_DIR/docker/compose.yaml" "$@"; }
running() { [ -n "$(compose ps -q --status running realms 2>/dev/null)" ]; }

# The commands for now, one per line: the spots, then `function realms:drops/try {night:N}`. None outside
# drop hours, or when no spot clear of every claim is left in the ring.
need_tool() {
    command -v python3 >/dev/null 2>&1 || die 'python3 is missing (deploy/upgrade-2.5.0.sh installs it)'
    [ -r "$TOOL" ] || die "$TOOL is missing: is the release with supply drops deployed?"
}
commands() {
    need_tool
    python3 -B "$TOOL" commands "$WORLD" || die 'tools/drops.py commands failed'
}

# Units whose copy in /etc/systemd/system differs from the deployed checkout's.
changed_units() {
    changed=''
    for u in $UNITS; do
        cmp -s "$REPO_DIR/deploy/$u" "/etc/systemd/system/$u" || changed="$changed $u"
    done
    printf '%s' "$changed"
}
timer_running() { systemctl is-enabled --quiet "$TIMER" 2>/dev/null && systemctl is-active --quiet "$TIMER" 2>/dev/null; }

case $MODE in
    check)
        need_tool
        python3 -B "$TOOL" spots "$WORLD" 2>&1 | while IFS= read -r l; do log "$l"; done
        out=$(commands)
        log 'commands for now:'
        [ -n "$out" ] || log '  none (outside drop hours, or no spot)'
        printf '%s\n' "$out" | while IFS= read -r c; do [ -z "$c" ] || log "  $c"; done
        changed=$(changed_units)
        if timer_running; then state=running; else state='not running'; fi
        log "timer: $TIMER $state; units to copy:${changed:- none}"
        if running; then log 'server: running'; else log 'server: not running (nothing would be sent)'; fi
        log 'check finished: nothing was changed'
        ;;
    install)
        [ "$(id -u)" = 0 ] || die 'run as root: it installs systemd units'
        for u in $UNITS; do
            [ -r "$REPO_DIR/deploy/$u" ] || die "$REPO_DIR/deploy/$u is missing: is the release with supply drops deployed?"
        done
        changed=$(changed_units)
        if [ -z "$changed" ] && timer_running; then
            log "already installed and running: $TIMER"
        else
            for u in $changed; do
                install -m 644 -o root -g root "$REPO_DIR/deploy/$u" "/etc/systemd/system/$u"
                log "installed /etc/systemd/system/$u"
            done
            [ -z "$changed" ] || systemctl daemon-reload
            systemctl enable --now "$TIMER"
            # A timer that was already running picks up a changed schedule on restart; this doesn't run its service.
            [ -z "$changed" ] || systemctl restart "$TIMER"
            log "running: $TIMER"
        fi
        systemctl list-timers --all --no-pager "$TIMER" 2>&1 | while IFS= read -r l; do log "  $l"; done
        ;;
    send)
        # Outside drop hours it prints nothing, so there is nothing worth a log line every 10 minutes.
        need_tool
        if out=$(python3 -B "$TOOL" send "$WORLD" --docker "$LIVE_DIR/docker" 2>&1); then rc=0; else rc=$?; fi
        [ -z "$out" ] || printf '%s\n' "$out" | while IFS= read -r l; do log "$l"; done
        [ "$rc" = 0 ] || die 'not every command went through (the timer tries again in 10 minutes)'
        ;;
esac
