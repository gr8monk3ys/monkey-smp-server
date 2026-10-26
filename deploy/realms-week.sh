#!/bin/sh
# Keeps the weekly challenges and Season I's launch weekend on the wall clock (tools/challenges.py): sends the
# output of `python3 tools/challenges.py commands` to the server over RCON. Minecraft has no wall clock, so this
# is how the server learns that a new week started (Monday, 12 AM Pacific) and when the launch weekend ends.
# realms-week.timer runs it every hour as the realms user. Both commands do nothing when nothing changed, so
# running it again, or by hand, is safe.
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

UNITS='realms-week.service realms-week.timer'
TIMER=realms-week.timer

log() { printf '%s [realms-week] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

compose() { docker compose --project-directory "$LIVE_DIR/docker" -f "$LIVE_DIR/docker/compose.yaml" "$@"; }
running() { [ -n "$(compose ps -q --status running realms 2>/dev/null)" ]; }
rcon() { compose exec -T realms realms rcon "$1" </dev/null 2>/dev/null; }

# The commands for now, one per line: `function realms:challenges/sync {week:N}`, and during and just after
# the launch weekend `function realms:wardrobe/founder/sync {seconds:N}`.
commands() {
    command -v python3 >/dev/null 2>&1 || die 'python3 is missing (deploy/upgrade-2.5.0.sh installs it)'
    [ -r "$REPO_DIR/tools/challenges.py" ] || die "$REPO_DIR/tools/challenges.py is missing: is the release with the weekly challenges deployed?"
    python3 -B "$REPO_DIR/tools/challenges.py" commands || die 'tools/challenges.py commands failed'
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
        out=$(commands)
        log 'commands for now:'
        printf '%s\n' "$out" | while IFS= read -r c; do log "  $c"; done
        changed=$(changed_units)
        if timer_running; then state=running; else state='not running'; fi
        log "timer: $TIMER $state; units to copy:${changed:- none}"
        if running; then log 'server: running'; else log 'server: not running (nothing would be sent this hour)'; fi
        log 'check finished: nothing was changed'
        ;;
    install)
        [ "$(id -u)" = 0 ] || die 'run as root: it installs systemd units'
        for u in $UNITS; do
            [ -r "$REPO_DIR/deploy/$u" ] || die "$REPO_DIR/deploy/$u is missing: is the release with the weekly challenges deployed?"
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
        out=$(commands)
        if ! running; then
            log 'server not running: nothing sent (the next hour catches up)'
            exit 0
        fi
        failed=0
        set -f  # the commands hold braces: no globbing while they are split into lines
        old_ifs=$IFS
        IFS='
'
        for c in $out; do
            IFS=$old_ifs
            if reply=$(rcon "$c"); then
                log "$c: ${reply:-ok}"
            else
                log "RCON failed: $c"
                failed=1
            fi
        done
        IFS=$old_ifs
        set +f
        [ "$failed" = 0 ] || die 'not every command went through (the next hour tries again)'
        ;;
esac
