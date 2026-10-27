# What every deploy script shares: settings, the log, the server's container, the deploy lock and the timers.
# Sourced, never run: after `set -eu`, a script sets LOG_NAME (the tag on its log lines) and
#
#   . "$(dirname -- "$0")/lib.sh"
#
# The scripts run from the deployed checkout (/srv/realms/repo/deploy), so this is always the copy that came with
# them. realms-deploy.sh sources it before it touches the checkout; a deploy's git checkout replaces files rather
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
# for an EXIT trap (realms-backup.sh posts it).
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

# The server's container, through the release's docker folder in LIVE_DIR.
compose() { docker compose --project-directory "$LIVE_DIR/docker" -f "$LIVE_DIR/docker/compose.yaml" "$@"; }
running() { [ -n "$(compose ps -q --status running realms 2>/dev/null)" ]; }
# "rcon CMD": the server's answer on stdout; fails when docker or RCON did. The container's own `realms rcon`
# finds the password itself, so no secret is read here.
rcon() { compose exec -T realms realms rcon "$1" </dev/null 2>/dev/null; }

# "deploy_lock SECONDS [FILE]": waits up to SECONDS (0: not at all) for the deploy lock, FILE (default LOCK_FILE,
# else /tmp/realms-deploy.lock), and holds it on fd 9 until the script exits; returns 1 only when it wasn't free in
# time. A lock file it can't create or open is a die, so a caller's "busy, skipping" never hides it.
# Deploys, the daily restart, off-site backups, the standings and the week and drops timers take it, so none of
# them runs while another restarts or saves the server. Root opens it read-only, after creating it as the live
# folder's owner (SERVICE_USER when set; root itself before there is a live folder): root may not open another
# user's file in /tmp for writing (fs.protected_regular), and flock works on any open file. Root creates it with
# noclobber (O_EXCL: never through a link someone else left at that name) and opens only a plain file.
deploy_lock() {
    lib_lock=${2:-${LOCK_FILE:-/tmp/realms-deploy.lock}}
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
