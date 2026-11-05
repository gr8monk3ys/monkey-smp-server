#!/bin/sh
# The staff page: a private, read-only look at how the server is doing, for the people who run it. Writes its status
# file (tools/staff_status.py), which monkey-staff.timer does every 2 minutes as the monkey user, and sets up the
# password-protected site Caddy serves it from (deploy/Caddyfile.staff). docs/LIVE.md, "The staff page".
#
#   sh monkey-staff.sh                        writes STAFF_DIR/staff.json
#   sh monkey-staff.sh --check                prints what the file would say, whether the timer runs, and (as root)
#                                             who can log in and whether the site refuses a visit with no password;
#                                             changes nothing
#   sudo sh monkey-staff.sh --login NAME      adds NAME, or gives NAME a new password. Prints the password once:
#                                             it is random, and only its hash is kept (/etc/caddy/staff-logins)
#   sudo sh monkey-staff.sh --remove-login NAME
#   sudo sh monkey-staff.sh --install         makes STAFF_DIR, starts the timer and adds the site to Caddy. Needs a
#                                             login first and the site's DNS record, and takes the site back out if a
#                                             visit with no password gets in
#
# The page has no way to change anything, and the status job only reads: `tick query` and `list` through the
# container's own `monkey rcon`, and the server's log and crash reports, which tools/staff_status.py filters. No deploy
# lock: during a deploy or the daily restart the page simply says the server is offline. The passwords are never on a
# command line, in the repo or in a log.
#
# The hash cost is 8, not Caddy's default of 14: the machine has two threads and the game needs them, and at 14 one
# check took about 600 ms of the VPS's CPU. A long random password doesn't need the slow hash to resist guessing.
#
# Reads only REPO_DIR, LIVE_DIR and STAFF_DIR (default /srv/monkey/staff) from /etc/monkey-deploy.env (or
# MONKEY_DEPLOY_ENV). CADDY_DIR is for the tests. Needs python3 3.10 or newer, and for setting up the site caddy and curl.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=monkey-staff
. "$(dirname -- "$0")/lib.sh"

NAME=''
case "${1:-}" in
    '') MODE=write ;;
    --check) MODE=check ;;
    --install) MODE=install ;;
    --login | --remove-login)
        MODE=${1#--}
        NAME=${2:-}
        case $NAME in
            '' | *[!A-Za-z0-9_-]*) echo "usage: sudo sh $0 $1 NAME (letters, digits, - and _)" >&2; exit 2 ;;
        esac
        ;;
    *) echo "usage: sh $0 [--check | --install | --login NAME | --remove-login NAME]" >&2; exit 2 ;;
esac

ENV_FILE=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/monkey/repo)}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/monkey/MonkeySMP-Server)}
STAFF_DIR=${STAFF_DIR:-$(setting STAFF_DIR /srv/monkey/staff)}
CADDY_DIR=${CADDY_DIR:-/etc/caddy}
UNITS='monkey-staff.service monkey-staff.timer'
HOST=staff.monkeysmp.lscaturchio.xyz
LOGINS=$CADDY_DIR/staff-logins
SITE=$CADDY_DIR/staff.caddy
MAIN=$CADDY_DIR/Caddyfile
IMPORT='import /etc/caddy/staff.caddy*'

# Whether Caddy would take the config, and that it can read the logins as its own user.
caddy_ok() {
    runuser -u caddy -- test -r "$LOGINS" 2>/dev/null || return 1
    caddy validate --config "$MAIN" --adapter caddyfile >/dev/null 2>&1
}
# What a visit with no password gets: 401, or 000 when there is no answer (usually no certificate yet: it is asked
# for only once the DNS record exists). Local, so it doesn't depend on the DNS record, and -k since it tests the
# password rather than the certificate.
no_password() {
    curl -ks -m 10 -o /dev/null -w '%{http_code}' --resolve "$HOST:443:127.0.0.1" "https://$HOST$1" 2>/dev/null || true
}
# How many logins there are; nothing when the file can't be read.
logins_count() { [ -r "$LOGINS" ] && grep -c '^[A-Za-z0-9_-]* ' "$LOGINS" || true; }

# "gate_or_remove": takes the site back out of Caddy if a visit with no password gets anything but a 401. Retries
# while there is no answer (the first certificate takes a moment).
gate_or_remove() {
    gate_tries=0
    while :; do
        gate_page=$(no_password /)
        gate_data=$(no_password /staff.json)
        [ "$gate_page" = 000 ] && [ "$gate_tries" -lt 12 ] || break
        gate_tries=$((gate_tries + 1))
        sleep 5
    done
    case "$gate_page $gate_data" in
        '401 401') log 'a visit with no password is refused (401)' ;;
        '000 000')
            log 'no answer from the site yet: is the DNS record set? Caddy asks for the certificate once it is.'
            log "the password is in place; run sudo sh $0 --check once it answers"
            ;;
        *)
            rm -f "$SITE"
            systemctl reload caddy
            die "a visit with no password got $gate_page and $gate_data, not 401: the site is out of Caddy again"
            ;;
    esac
}

if [ "$MODE" = login ] || [ "$MODE" = remove-login ] || [ "$MODE" = install ]; then
    [ "$(id -u)" = 0 ] || die 'run as root: it changes Caddy'
    command -v caddy >/dev/null 2>&1 || die 'caddy is missing (docs/LIVE.md, step 9)'
    command -v python3 >/dev/null 2>&1 || die 'python3 is missing (deploy/upgrade-2.5.0.sh installs it)'
fi

if [ "$MODE" = login ] || [ "$MODE" = remove-login ]; then
    umask 077
    NEW=$(mktemp "$CADDY_DIR/.staff-logins.XXXXXX")
    OLD=$(mktemp "$CADDY_DIR/.staff-logins-old.XXXXXX")
    trap 'rm -f "$NEW" "$OLD"' EXIT
    [ ! -r "$LOGINS" ] || cp -p "$LOGINS" "$OLD"
    [ ! -r "$LOGINS" ] || grep -v "^$NAME " "$LOGINS" >"$NEW" || true
    PASSWORD=''
    if [ "$MODE" = login ]; then
        PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')
        # On stdin, with its newline: caddy reads one line, and an argument would show in `ps`.
        HASH=$(printf '%s\n' "$PASSWORD" | caddy hash-password --algorithm bcrypt --bcrypt-cost 8)
        case $HASH in '$2'*) ;; *) die 'caddy did not give a bcrypt hash' ;; esac
        printf '%s %s\n' "$NAME" "$HASH" >>"$NEW"
    else
        grep -q "^$NAME " "$OLD" || die "no login called $NAME"
        # An empty list would leave a site nobody can open, or worse: stop the site instead.
        [ -s "$NEW" ] || [ ! -e "$SITE" ] || die "$NAME is the last login: to close the page, see docs/LIVE.md, \"The staff page\""
    fi
    install -m 640 -o root -g caddy "$NEW" "$LOGINS"
    if [ -e "$SITE" ]; then
        if ! caddy_ok; then
            if [ -s "$OLD" ]; then install -m 640 -o root -g caddy "$OLD" "$LOGINS"; else rm -f "$LOGINS"; fi
            die 'caddy refused the new logins: they are as they were'
        fi
        systemctl reload caddy
    fi
    if [ "$MODE" = login ]; then
        # Not through log: this is the only copy, and it belongs in a password manager, not in a log.
        printf '\nLogin for %s, shown only this once:\n\n  page:     https://%s\n  name:     %s\n  password: %s\n\n' \
            "$NAME" "$HOST" "$NAME" "$PASSWORD"
    else
        log "removed the login $NAME"
    fi
    exit 0
fi

if [ "$MODE" = install ]; then
    command -v curl >/dev/null 2>&1 || die 'curl is missing'
    for unit in $UNITS Caddyfile.staff staff/index.html; do
        [ -r "$REPO_DIR/deploy/$unit" ] || die "$REPO_DIR/deploy/$unit is missing: is the release with the staff page deployed?"
    done
    [ "$(logins_count)" -gt 0 ] 2>/dev/null || die "no logins yet: run sudo sh $0 --login NAME first, so the site never opens without a password"
    install -d -m 755 -o monkey -g monkey "$STAFF_DIR"
    log "status folder: $STAFF_DIR"
    install_timer monkey-staff.timer $UNITS

    BACKUP=$(mktemp -d "$CADDY_DIR/.staff-backup.XXXXXX")
    trap 'rm -rf "$BACKUP"' EXIT
    cp -p "$MAIN" "$BACKUP/Caddyfile"
    [ ! -e "$SITE" ] || cp -p "$SITE" "$BACKUP/staff.caddy"
    install -m 644 -o root -g root "$REPO_DIR/deploy/Caddyfile.staff" "$SITE"
    # Added by hand to the live file rather than copying the repo's over it, which would lose anything changed there.
    grep -qxF "$IMPORT" "$MAIN" || printf '\n# The staff page, if it is set up (deploy/monkey-staff.sh).\n%s\n' "$IMPORT" >>"$MAIN"
    if ! caddy_ok; then
        cp -p "$BACKUP/Caddyfile" "$MAIN"
        if [ -e "$BACKUP/staff.caddy" ]; then cp -p "$BACKUP/staff.caddy" "$SITE"; else rm -f "$SITE"; fi
        die 'caddy refused the config: it is as it was. Try: caddy validate --config /etc/caddy/Caddyfile'
    fi
    systemctl reload caddy
    log "site: https://$HOST"
    gate_or_remove
    log "logins: $(logins_count)"
    exit 0
fi

TOOL=$REPO_DIR/tools/staff_status.py
command -v python3 >/dev/null 2>&1 || die 'python3 is missing (deploy/upgrade-2.5.0.sh installs it)'
python_ok 10 || die 'python3 is older than 3.10'
[ -r "$TOOL" ] || die "$TOOL is missing: is the release with the staff page deployed?"

if [ "$MODE" = check ]; then
    log 'status for now:'
    python3 -B "$TOOL" show "$LIVE_DIR" | while IFS= read -r line; do log "  $line"; done
    timer_state monkey-staff.timer $UNITS
    if [ "$(id -u)" = 0 ]; then
        log "logins:$(sed -n 's/^\([A-Za-z0-9_-]*\) .*/ \1/p' "$LOGINS" 2>/dev/null | tr -d '\n')"
        if [ -e "$SITE" ]; then
            log "a visit with no password gets: $(no_password /) (401 is right; 000 is no answer yet)"
        else
            log "site: not added to Caddy yet (sudo sh $0 --install)"
        fi
    fi
    log 'check finished: nothing was changed'
    exit 0
fi

# Root would leave a file the monkey user's next run can't replace.
[ "$(id -u)" != 0 ] || { echo "run it as monkey: sudo -u monkey sh $0" >&2; exit 1; }
[ -d "$STAFF_DIR" ] || die "no $STAFF_DIR: run sudo sh $0 --install"
python3 -B "$TOOL" write "$LIVE_DIR" --out "$STAFF_DIR/staff.json"
