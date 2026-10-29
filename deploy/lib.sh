# What every deploy script shares: settings, the log, the server's container, warning players and waiting for a
# restart, Discord posts, the deploy lock, the timers and the timed jobs.
# Sourced, never run: after `set -eu`, a script sets LOG_NAME (the tag on its log lines) and
#
#   . "$(dirname -- "$0")/lib.sh"
#
# The scripts run from the deployed checkout (/srv/monkey/repo/deploy), so this is always the copy that came with
# them. monkey-deploy.sh sources it before it touches the checkout; a deploy's git checkout replaces files rather
# than writing into them, so the copy a running script loaded is unaffected.
#
# Whether the server accepted an RCON command is read in Python (tools/rcon.py): `rcon` here is for say, list and
# save-*, whose answers the scripts only log or count.
#
# Plain POSIX sh, LF line endings, plain ASCII.

# "setting_in FILE NAME [DEFAULT]": NAME's value in the KEY=value file FILE (the last one), else DEFAULT, exactly
# as written: not run through the shell, so a value may hold $, quotes, spaces or backslashes. KEY="value" and
# KEY='value' work too.
setting_in() {
    lib_v=''
    [ ! -r "$1" ] || lib_v=$(sed -n "s/^[[:space:]]*$2[[:space:]]*=[[:space:]]*//p" "$1" | tail -n 1 |
        sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/")
    printf '%s' "${lib_v:-${3:-}}"
}
# "setting NAME [DEFAULT]": the same, from ENV_FILE.
setting() { setting_in "$ENV_FILE" "$@"; }

# "log WORDS...": one line, `YYYY-MM-DD HH:MM:SS [LOG_NAME] WORDS`, on stdout and, with LOG_TO set, in that file.
log() {
    lib_line="$(date '+%Y-%m-%d %H:%M:%S') [$LOG_NAME] $*"
    [ -z "${LOG_TO:-}" ] || printf '%s\n' "$lib_line" >>"$LOG_TO"
    printf '%s\n' "$lib_line"
}
# "die WORDS...": logs `ERROR: WORDS` on stderr, so a die inside $(...) still shows, and exits 1. DIED keeps WORDS
# for an EXIT trap (monkey-backup.sh posts it).
DIED=''
die() { DIED=$*; log "ERROR: $*" >&2; exit 1; }
# "logged CMD...": runs CMD with its output going to LOG_TO only.
logged() { "$@" >>"$LOG_TO" 2>&1; }
# "log_each CMD...": runs CMD, logging each line it prints as it prints it (blank lines dropped); returns CMD's exit
# code. The code comes after a newline of its own, so output without a final newline can't swallow it.
log_each() {
    exec 3>&1
    lib_rc=$( { "$@" 2>&1 && printf '\nexit=0\n' || printf '\nexit=%s\n' "$?"; } | while IFS= read -r lib_l; do
        case $lib_l in exit=*) printf '%s' "${lib_l#exit=}" ;; '') ;; *) log "$lib_l" >&3 ;; esac
    done )
    exec 3>&-
    return "${lib_rc:-1}"
}

# "python_ok MINOR": python3 is installed and 3.MINOR or newer.
python_ok() { python3 -c "import sys; sys.exit(sys.version_info < (3, $1))" 2>/dev/null; }

# "absolute PATH": PATH, made absolute against the working directory.
absolute() { case $1 in /*) printf '%s\n' "$1" ;; *) printf '%s\n' "$PWD/$1" ;; esac; }

# The server's container, through the release's docker folder in LIVE_DIR. Run from /: docker compose stats the
# working directory, and a hand run as monkey from root's home (`runuser -u monkey -- sh ...` in /root) would
# otherwise fail every call, so `running` would say no and the deploy skip the backup. A relative LIVE_DIR is
# taken from the caller's folder, before the cd.
compose() {
    lib_live=$(absolute "$LIVE_DIR")
    (cd / && docker compose --project-directory "$lib_live/docker" -f "$lib_live/docker/compose.yaml" "$@")
}
running() { [ -n "$(compose ps -q --status running monkey 2>/dev/null)" ]; }
# "rcon CMD": the server's answer on stdout; fails when docker or RCON did. The container's own `monkey rcon`
# finds the password itself, so no secret is read here.
rcon() { compose exec -T monkey monkey rcon "$1" </dev/null 2>/dev/null; }

# "players_online": how many players are online, from `list` ("There are 3 of a max of 20 players online: ...");
# nothing when the server didn't answer.
players_online() { rcon list | sed -n 's/.*There are \([0-9][0-9]*\) of.*/\1/p' | head -n 1; }

# "whole_number NAME VALUE [UNIT]": dies unless VALUE is a whole number (0, 5, 900: no sign, no leading 0), naming
# the setting NAME, so a typo in a setting stops a script before it stops anything instead of skipping a step.
whole_number() {
    case $2 in '' | *[!0-9]* | 0?*) die "$1 must be a whole number${3:+ of $3}, not '$2'" ;; esac
}

# "warn_players FIRST [LAST [DETAIL]]": when players are online, says `FIRST in WARN_MINUTES minutes DETAIL.` in
# chat, then a minute ahead `LAST in 1 minute. Find a safe spot.`, and returns a minute after that. LAST empty or
# left out is FIRST; DETAIL is "(about 3 minutes offline)". WARN_MINUTES is 5 when unset, 0 warns nobody, and
# anything but a whole number is a die. PLAYERS_ONLINE keeps how many were online (empty when the server didn't
# answer), so a caller needs no second `list`.
warn_players() {
    lib_minutes=${WARN_MINUTES:-5}
    whole_number WARN_MINUTES "$lib_minutes" minutes
    PLAYERS_ONLINE=$(players_online || true)
    [ "$lib_minutes" -gt 0 ] && [ "${PLAYERS_ONLINE:-0}" -gt 0 ] || return 0
    log "$PLAYERS_ONLINE player(s) online; warning them $lib_minutes minutes ahead"
    rcon "say $1 in $lib_minutes minutes ${3:-(about 3 minutes offline)}." >/dev/null || true
    [ "$lib_minutes" -le 1 ] || sleep $(((lib_minutes - 1) * 60))
    rcon "say ${2:-$1} in 1 minute. Find a safe spot." >/dev/null || true
    sleep 60
}

# "wait_for_live [--while-running]": waits up to BOOT_TIMEOUT seconds (default 900) for the server to answer RCON,
# asking every 15 seconds; returns 1 when it didn't. --while-running gives up as soon as the container isn't
# running (a deploy's failed boot rolls back sooner); without it a container that crashed gets the whole time to
# come back (compose restarts it). A BOOT_TIMEOUT that isn't a whole number is a die.
wait_for_live() {
    whole_number BOOT_TIMEOUT "${BOOT_TIMEOUT:-900}" seconds
    lib_waited=0
    while [ "$lib_waited" -lt "${BOOT_TIMEOUT:-900}" ]; do
        sleep 15
        lib_waited=$((lib_waited + 15))
        [ "${1:-}" != --while-running ] || running || return 1
        if rcon list >/dev/null; then return 0; fi
    done
    return 1
}

# "discord MSG [URL [FILE]]": posts MSG to the Discord webhook URL (left out: DISCORD_WEBHOOK_URL; empty: no post),
# with FILE attached as Markdown when given. A post that fails is logged, never an error. MSG becomes a JSON string
# here: backslashes and double quotes are escaped, newlines, tabs and carriage returns become \n, \t and \r, and
# any other control character is dropped, so any text makes valid JSON.
discord() {
    if [ $# -gt 1 ]; then lib_url=$2; else lib_url=${DISCORD_WEBHOOK_URL:-}; fi
    [ -n "$lib_url" ] || return 0
    lib_tab=$(printf '\t')
    lib_cr=$(printf '\r')
    lib_json=$(printf '%s' "$1" | tr -d '\001-\010\013\014\016-\037\177' |
        sed -e 's/[\\"]/\\&/g' -e "s/$lib_tab/\\\\t/g" -e "s/$lib_cr/\\\\r/g" |
        awk 'NR > 1 { printf "%s", "\\n" } { printf "%s", $0 }')
    if [ $# -gt 2 ]; then
        curl -fsS -m 30 --form-string "payload_json={\"content\":\"$lib_json\"}" -F "files[0]=@$3;type=text/markdown" \
            "$lib_url" >/dev/null
    else
        printf '{"content":"%s"}' "$lib_json" | curl -fsS -m 15 -H 'Content-Type: application/json' -d @- "$lib_url" >/dev/null
    fi || log 'could not post to Discord'
}

# "deploy_lock SECONDS [FILE]": waits up to SECONDS (0: not at all) for the deploy lock, FILE (default LOCK_FILE,
# else /tmp/monkey-deploy.lock), and holds it on fd 9 until the script exits; returns 1 only when it wasn't free in
# time. A lock file it can't create or open is a die, so a caller's "busy, skipping" never hides it.
# Deploys, the daily restart, off-site backups, the standings and the timed jobs take it, so none of
# them runs while another restarts or saves the server. Root opens it read-only, after creating it as the live
# folder's owner (SERVICE_USER when set; root itself before there is a live folder): root may not open another
# user's file in /tmp for writing (fs.protected_regular), and flock works on any open file. Root creates it with
# noclobber (O_EXCL: never through a link someone else left at that name) and opens only a plain file.
deploy_lock() {
    lib_lock=${2:-${LOCK_FILE:-/tmp/monkey-deploy.lock}}
    # `command exec`: a failed redirection returns here instead of ending the script on the shell's own error.
    if [ "$(id -u)" = 0 ]; then
        if [ ! -e "$lib_lock" ] && [ ! -L "$lib_lock" ]; then
            lib_owner=${SERVICE_USER:-$(stat -c %U "$LIVE_DIR" 2>/dev/null || :)}
            if [ -n "$lib_owner" ]; then
                runuser -u "$lib_owner" -- touch "$lib_lock"
            else
                (set -C; : >"$lib_lock")
            fi || die "could not create the deploy lock $lib_lock"
        fi
        [ -f "$lib_lock" ] && [ ! -L "$lib_lock" ] || die "the deploy lock $lib_lock is not a plain file"
        command exec 9<"$lib_lock" || die "could not open the deploy lock $lib_lock"
    else
        command exec 9>>"$lib_lock" || die "could not open the deploy lock $lib_lock"
    fi
    if [ "$1" = 0 ]; then flock -n 9; else flock -w "$1" 9; fi
}

# "changed_units UNIT...": the units whose copy in /etc/systemd/system differs from the deployed checkout's.
changed_units() {
    lib_changed=''
    for lib_u in "$@"; do
        cmp -s "$REPO_DIR/deploy/$lib_u" "/etc/systemd/system/$lib_u" || lib_changed="$lib_changed $lib_u"
    done
    printf '%s' "$lib_changed"
}
# "timer_running TIMER": enabled and active.
timer_running() { systemctl is-enabled --quiet "$1" 2>/dev/null && systemctl is-active --quiet "$1" 2>/dev/null; }
# "timer_state TIMER UNIT...": the --check line, `timer: TIMER running; units to copy: ...`.
timer_state() {
    lib_timer=$1
    shift
    lib_changed=$(changed_units "$@")
    if timer_running "$lib_timer"; then lib_state=running; else lib_state='not running'; fi
    log "timer: $lib_timer $lib_state; units to copy:${lib_changed:- none}"
}
# "install_timer TIMER UNIT...": copies the units that changed to /etc/systemd/system and starts TIMER, as root.
install_timer() {
    lib_timer=$1
    shift
    lib_changed=$(changed_units "$@")
    if [ -z "$lib_changed" ] && timer_running "$lib_timer"; then
        log "already installed and running: $lib_timer"
    else
        for lib_u in $lib_changed; do
            install -m 644 -o root -g root "$REPO_DIR/deploy/$lib_u" "/etc/systemd/system/$lib_u"
            log "installed /etc/systemd/system/$lib_u"
        done
        [ -z "$lib_changed" ] || systemctl daemon-reload
        systemctl enable --now "$lib_timer"
        # A timer that was already running picks up a changed schedule on restart; this doesn't run its service.
        [ -z "$lib_changed" ] || systemctl restart "$lib_timer"
        log "running: $lib_timer"
    fi
    systemctl list-timers --all --no-pager "$lib_timer" 2>&1 | while IFS= read -r lib_l; do log "  $lib_l"; done
}

# ---------------------------------------------------------------- timed jobs (GLOSSARY.md, "Timed job")

# "timed_job [--check | --install]": a timed job's whole script, run as its last line. The job is named by
# LOG_NAME: its units are LOG_NAME.service and LOG_NAME.timer. Before it, the script sets
#   JOB_TOOL    its tool in tools/ (challenges.py): `commands [WORLD]` prints the RCON commands for now, one per
#               line, and `send [WORLD] --docker DIR` sends them through tools/rcon.py, exiting 1 when one wasn't
#               accepted, 3 when the server isn't running and the job must run (rcon.NOT_RUNNING), and 4 when it
#               gave up (rcon.GAVE_UP)
#   JOB_FOR     what the release brought it, for "is the release with JOB_FOR deployed?"
#   JOB_RETRY   when it runs again after a failure, for the errors ("the next hour tries again")
#   JOB_DOWN    what a stopped server means, for --check's "server: not running (JOB_DOWN)"
# and optionally JOB_WORLD=1 (the tool takes the saved world first), JOB_SHOW (a tool subcommand whose output
# --check logs first: drops' spots) and JOB_NONE (why there may be no commands, for --check; with it, sending
# asks for the commands first, and none means nothing is logged and no lock is taken).
#
# With no option it waits up to 30 minutes for the deploy lock, so it never lands while a deploy, the daily
# restart or an off-site backup has the server stopped or not saving, sends, and logs each line the tool prints;
# any failure is an error, so systemd's retry or the next run tries again. A tool that gave up posts a staff
# alert and returns 4 (monkey-day.service's RestartPreventExitStatus), so the next timer run starts afresh.
# --check prints the commands for now, the timer's state and whether the server is running, and changes
# nothing. --install (root) copies the units from the deployed checkout to /etc/systemd/system (only those that
# changed) and starts the timer.
#
# It reads only REPO_DIR, LIVE_DIR and LOCK_FILE from /etc/monkey-deploy.env (or MONKEY_DEPLOY_ENV), without
# sourcing it; the staff webhook (STAFF_WEBHOOK_URL, else DISCORD_WEBHOOK_URL) only to post that a job gave up.
# No secret is printed or asked for.
timed_job() {
    case "${1:-}" in
        '') lib_mode=send ;;
        --check) lib_mode=check ;;
        --install) lib_mode=install ;;
        *) echo "usage: sh $0 [--check | --install]" >&2; return 2 ;;
    esac
    ENV_FILE=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
    REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/monkey/repo)}
    LOCK_FILE=${LOCK_FILE:-$(setting LOCK_FILE /tmp/monkey-deploy.lock)}
    LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/monkey/MonkeySMP-Server)}
    lib_units="$LOG_NAME.service $LOG_NAME.timer"
    if [ "$lib_mode" = install ]; then
        [ "$(id -u)" = 0 ] || die 'run as root: it installs systemd units'
        for lib_u in $lib_units; do
            [ -r "$REPO_DIR/deploy/$lib_u" ] || die "$REPO_DIR/deploy/$lib_u is missing: is the release with $JOB_FOR deployed?"
        done
        install_timer "$LOG_NAME.timer" $lib_units
        return 0
    fi

    lib_tool=$REPO_DIR/tools/$JOB_TOOL
    command -v python3 >/dev/null 2>&1 || die 'python3 is missing (deploy/upgrade-2.5.0.sh installs it)'
    [ -r "$lib_tool" ] || die "$lib_tool is missing: is the release with $JOB_FOR deployed?"
    # The tool's arguments before its options: the world, for a job that reads it.
    if [ -n "${JOB_WORLD:-}" ]; then set -- "$LIVE_DIR/server/world"; else set --; fi
    if [ "$lib_mode" = check ] && [ -n "${JOB_SHOW:-}" ]; then
        python3 -B "$lib_tool" "$JOB_SHOW" "$@" 2>&1 | while IFS= read -r lib_l; do log "$lib_l"; done
    fi
    if [ "$lib_mode" = check ] || [ -n "${JOB_NONE:-}" ]; then
        lib_out=$(python3 -B "$lib_tool" commands "$@") || die "tools/$JOB_TOOL commands failed"
    fi

    if [ "$lib_mode" = send ]; then
        [ -z "${JOB_NONE:-}" ] || [ -n "$lib_out" ] || return 0
        deploy_lock 1800 || die "the deploy lock was taken for 30 minutes ($JOB_RETRY)"
        lib_sent=0
        log_each python3 -B -u "$lib_tool" send "$@" --docker "$LIVE_DIR/docker" || lib_sent=$?
        case $lib_sent in
            0) return 0 ;;
            3) die "the server isn't running ($JOB_RETRY)" ;;
            4) ;;
            *) die "not every command went through ($JOB_RETRY)" ;;
        esac
        lib_staff=${STAFF_WEBHOOK_URL:-$(setting STAFF_WEBHOOK_URL)}
        lib_staff=${lib_staff:-${DISCORD_WEBHOOK_URL:-$(setting DISCORD_WEBHOOK_URL)}}
        [ -n "$lib_staff" ] || log 'no webhook in the settings; not posting'
        discord "Monkey SMP: $LOG_NAME gave up on $JOB_FOR after retrying. Check: journalctl -u $LOG_NAME" "$lib_staff"
        log "gave up; the timer's next run starts afresh"
        return 4
    fi
    log 'commands for now:'
    [ -n "$lib_out" ] || log "  none${JOB_NONE:+ ($JOB_NONE)}"
    printf '%s\n' "$lib_out" | while IFS= read -r lib_l; do [ -z "$lib_l" ] || log "  $lib_l"; done
    timer_state "$LOG_NAME.timer" $lib_units
    python3 -B "$REPO_DIR/tools/rcon.py" running --docker "$LIVE_DIR/docker" && lib_up=0 || lib_up=$?
    case $lib_up in
        0) log 'server: running' ;;
        1) log "server: not running ($JOB_DOWN)" ;;
        *) log "server: can't tell (docker failed; see above)" ;;
    esac
    log 'check finished: nothing was changed'
}
