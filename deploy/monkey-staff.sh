#!/bin/sh
# The staff page: a private look at how the server is doing, and its controls, for the people who run it. Writes its
# status file (tools/staff_status.py), which monkey-staff.timer does every 2 minutes as the monkey user, and sets up
# the password-protected site Caddy serves it from (deploy/Caddyfile.staff) and the controls behind it
# (tools/staff_panel.py, monkey-panel.service). docs/LIVE.md, "The staff page".
#
#   sh monkey-staff.sh                        writes STAFF_DIR/staff.json
#   sh monkey-staff.sh --check                prints what the file would say, whether the timer and the controls
#                                             run, and (as root) who can log in and whether the site refuses a visit
#                                             with no password; changes nothing
#   sudo sh monkey-staff.sh --login NAME      adds NAME, or gives NAME a new password. Prints the password once:
#                                             it is random, and only its hash is kept (/etc/caddy/staff-logins)
#   sudo sh monkey-staff.sh --remove-login NAME
#   sudo sh monkey-staff.sh --install         makes STAFF_DIR, adds the site to Caddy, starts the timer and the
#                                             controls. Needs a login first and the site's DNS record, and takes the
#                                             site back out if a visit with no password gets in
#   sudo sh monkey-staff.sh --install-helper  the owner's step: installs the backup helper (monkey-staff-helper.path
#                                             and .service, root), so the page can start a backup, list the snapshots
#                                             and (owners) restore one. Only with STAFF_DIR /srv/monkey/staff
#   sudo sh monkey-staff.sh --add-sftp-user NAME KEYFILE | --remove-sftp-user NAME
#                                             the owner's step: an SFTP-only login to the server folder (monkey-sftp.sh)
#
# The page's own login page (tools/staff_auth.py, deploy/Caddyfile.staff-login), in place of the browser's password box:
#
#   sudo sh monkey-staff.sh --add-user NAME ROLE [EMAIL]   a login (moderator, admin or owner); prints a one-time
#                                             set-password link, good for 24 hours, to pass on privately
#   sudo sh monkey-staff.sh --reset-link NAME  prints a one-time link to set a new password, for the owner to hand over
#   sudo sh monkey-staff.sh --use-new-login   switches Caddy to the login page: needs an owner with a password, checks
#                                             the config, and switches back if a visit with no session gets in
#   sudo sh monkey-staff.sh --use-basic-auth  switches back to the password box (the rollback); --login still works
#                                             for it all along
#
# The status job only reads: `tick query` and `list` through the container's own `monkey rcon`, and the server's log
# and crash reports, which tools/staff_status.py filters. No deploy lock: during a deploy or the daily restart the page
# simply says the server is offline. The changes the page can make (console commands, the server's config files,
# restart and stop) all go through the controls, monkey-panel.service, which listens on 127.0.0.1 only, is reached only
# through the password, keeps every file it replaces, and says itself what it refuses (tools/staff_panel.py). This
# script only installs and checks it. The passwords are never on a command line, in the repo or in a log.
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
ROLE=''
EMAIL=''
case "${1:-}" in
    '') MODE=write ;;
    --check) MODE=check ;;
    --install) MODE=install ;;
    --use-new-login) MODE=use-new-login ;;
    --use-basic-auth) MODE=use-basic-auth ;;
    --add-user | --reset-link)
        MODE=${1#--}
        NAME=${2:-}
        ROLE=${3:-}
        EMAIL=${4:-}
        case $NAME in
            '' | *[!a-z0-9_]*) echo "usage: sudo sh $0 $1 NAME$([ "$1" = --reset-link ] || echo ' ROLE [EMAIL]') (small letters, digits and _)" >&2; exit 2 ;;
        esac
        if [ "$MODE" = add-user ]; then
            case $ROLE in moderator | admin | owner) ;; *) echo "usage: sudo sh $0 --add-user NAME moderator|admin|owner [EMAIL]" >&2; exit 2 ;; esac
            case $EMAIL in *[!A-Za-z0-9.@_+-]*) echo "that email has a character this script doesn't take" >&2; exit 2 ;; esac
        fi
        ;;
    --install-helper) MODE=install-helper ;;
    --add-sftp-user | --remove-sftp-user) exec sh "$(dirname -- "$0")/monkey-sftp.sh" "$@" ;;
    --login | --remove-login)
        MODE=${1#--}
        NAME=${2:-}
        case $NAME in
            '' | *[!A-Za-z0-9_-]*) echo "usage: sudo sh $0 $1 NAME (letters, digits, - and _)" >&2; exit 2 ;;
        esac
        ;;
    *) echo "usage: sh $0 [--check | --install | --install-helper | --login NAME | --remove-login NAME | --add-user NAME ROLE [EMAIL] | --reset-link NAME | --use-new-login | --use-basic-auth | --add-sftp-user NAME KEYFILE | --remove-sftp-user NAME]" >&2; exit 2 ;;
esac

ENV_FILE=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/monkey/repo)}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/monkey/MonkeySMP-Server)}
STAFF_DIR=${STAFF_DIR:-$(setting STAFF_DIR /srv/monkey/staff)}
CADDY_DIR=${CADDY_DIR:-/etc/caddy}
UNITS='monkey-staff.service monkey-staff.timer'
PANEL=monkey-panel.service
HELPER_UNITS='monkey-staff-helper.path monkey-staff-helper.service'
HOST=staff.monkeysmp.lscaturchio.xyz
LOGINS=$CADDY_DIR/staff-logins
SITE=$CADDY_DIR/staff.caddy
MAIN=$CADDY_DIR/Caddyfile
IMPORT='import /etc/caddy/staff*.caddy'

# Whether Caddy would take the config, and that it can read the logins as its own user (the password box only).
caddy_ok() {
    if ! is_new_login; then runuser -u caddy -- test -r "$LOGINS" 2>/dev/null || return 1; fi
    caddy validate --config "$MAIN" --adapter caddyfile >/dev/null 2>&1
}
# Whether the site in Caddy is the login page (deploy/Caddyfile.staff-login) rather than the password box.
is_new_login() { [ -e "$SITE" ] && grep -q 'forward_auth' "$SITE"; }
# What a visit with no password or session must get, page and status file: 401 twice for the password box; for the
# login page, a redirect to it (302) and 401.
gate_want() { if is_new_login; then echo '302 401'; else echo '401 401'; fi; }
# "auth_tool ARGS...": tools/staff_auth.py as the monkey user, whose store it is.
auth_tool() { runuser -u monkey -- env STAFF_DIR="$STAFF_DIR" python3 -B "$REPO_DIR/tools/staff_auth.py" "$@"; }
# What a visit with no password gets: 401, or 000 when there is no answer (usually no certificate yet: it is asked
# for only once the DNS record exists). Local, so it doesn't depend on the DNS record, and -k since it tests the
# password rather than the certificate.
no_password() {
    curl -ks -m 10 -o /dev/null -w '%{http_code}' --resolve "$HOST:443:127.0.0.1" "https://$HOST$1" 2>/dev/null || true
}
# What the controls answer on this machine with no login name: 403 is right (it is up, and refuses a nameless
# request), 000 is no answer.
panel_answer() {
    curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8130/api/power 2>/dev/null || true
}
# "install_panel": copies monkey-panel.service when it changed and starts it, as root, restarting it so that it runs
# the checkout's tools/staff_panel.py (a deploy updates the file, not the running copy). A restart of the controls
# leaves a server restart they started running (KillMode=process).
install_panel() {
    panel_changed=$(changed_units "$PANEL")
    if [ -n "$panel_changed" ]; then
        install -m 644 -o root -g root "$REPO_DIR/deploy/$PANEL" "/etc/systemd/system/$PANEL"
        log "installed /etc/systemd/system/$PANEL"
        systemctl daemon-reload
    fi
    systemctl enable --now monkey-panel.service
    systemctl restart monkey-panel.service
    log "running: $PANEL"
}

# How many logins there are; nothing when the file can't be read.
logins_count() { [ -r "$LOGINS" ] && grep -c '^[A-Za-z0-9_-]* ' "$LOGINS" || true; }

# The first thing Caddy's own user can't read of what the site serves, if any: a visit with the password would fail
# while one without it still gets its 401.
caddy_cannot_read() {
    for wanted in "$REPO_DIR/deploy/staff/index.html" "$REPO_DIR/site/public/fonts" "$STAFF_DIR" "$STAFF_DIR/staff.json"; do
        [ "$wanted" != "$STAFF_DIR/staff.json" ] || [ -e "$wanted" ] || continue
        runuser -u caddy -- test -r "$wanted" 2>/dev/null || { echo "$wanted"; return 0; }
    done
}

# "gate_or_remove": takes the site back out of Caddy if a visit with no password gets anything but a 401. Retries
# while there is no answer (the first certificate takes a moment).
gate_or_remove() {
    gate_tries=0
    while :; do
        gate_page=$(no_password /)
        gate_data=$(no_password /staff.json)
        { [ "$gate_page" = 000 ] || [ "$gate_data" = 000 ]; } && [ "$gate_tries" -lt 12 ] || break
        gate_tries=$((gate_tries + 1))
        sleep 5
    done
    case "$gate_page $gate_data" in
        "$(gate_want)")
            if is_new_login; then
                log 'a visit with no session goes to the login page (302) and the status file is refused (401)'
            else
                log 'a visit with no password is refused (401)'
            fi
            ;;
        '000 000')
            log 'no answer from the site yet: is the DNS record set? Caddy asks for the certificate once it is.'
            log "the password is in place; run sudo sh $0 --check once it answers"
            ;;
        *)
            # A switch between the two puts the one that was there back; an install takes the site out.
            if [ -n "${GATE_BACKUP:-}" ] && [ -e "$GATE_BACKUP" ]; then
                cp -p "$GATE_BACKUP" "$SITE"
                systemctl reload caddy
                die "a visit with no password or session got $gate_page and $gate_data: the login is as it was"
            fi
            rm -f "$SITE"
            systemctl reload caddy
            die "a visit with no password got $gate_page and $gate_data, not 401: the site is out of Caddy again"
            ;;
    esac
}

case $MODE in
    login | remove-login | install | use-new-login | use-basic-auth)
        [ "$(id -u)" = 0 ] || die 'run as root: it changes Caddy'
        command -v caddy >/dev/null 2>&1 || die 'caddy is missing (docs/LIVE.md, step 9)'
        command -v python3 >/dev/null 2>&1 || die 'python3 is missing (deploy/upgrade-2.5.0.sh installs it)'
        ;;
    add-user | reset-link)
        [ "$(id -u)" = 0 ] || die "run as root (sudo sh $0): it runs the login tool as monkey, whose store it is"
        command -v python3 >/dev/null 2>&1 || die 'python3 is missing (deploy/upgrade-2.5.0.sh installs it)'
        [ -r "$REPO_DIR/tools/staff_auth.py" ] || die "$REPO_DIR/tools/staff_auth.py is missing: is the release with the login page deployed?"
        [ -d "$STAFF_DIR" ] || install -d -m 755 -o monkey -g monkey "$STAFF_DIR"
        # The link is printed by the tool itself, once, and goes nowhere else: not through log.
        if [ "$MODE" = add-user ]; then
            if [ -n "$EMAIL" ]; then auth_tool add-user "$NAME" "$ROLE" --email "$EMAIL"; else auth_tool add-user "$NAME" "$ROLE"; fi
        else
            auth_tool reset-link "$NAME"
        fi
        exit $?
        ;;
esac

# "switch_site FILE": puts deploy/FILE in as the staff site, keeping the one that was there: Caddy must take it and
# a visit with no password or session must still be turned away, or the old one comes back.
switch_site() {
    [ -e "$SITE" ] || die "the staff page isn't in Caddy yet: run sudo sh $0 --install first"
    [ -r "$REPO_DIR/deploy/$1" ] || die "$REPO_DIR/deploy/$1 is missing: is the release with the login page deployed?"
    SWITCH_DIR=$(mktemp -d "$CADDY_DIR/.staff-switch.XXXXXX")
    trap 'rm -rf "$SWITCH_DIR"' EXIT
    cp -p "$SITE" "$SWITCH_DIR/staff.caddy"
    install -m 644 -o root -g root "$REPO_DIR/deploy/$1" "$SITE"
    if ! caddy_ok; then
        cp -p "$SWITCH_DIR/staff.caddy" "$SITE"
        die "caddy refused deploy/$1: the login is as it was. Try: caddy validate --config /etc/caddy/Caddyfile"
    fi
    systemctl reload caddy
    GATE_BACKUP=$SWITCH_DIR/staff.caddy
    gate_or_remove
}

if [ "$MODE" = use-new-login ]; then
    [ "$(panel_answer)" = 403 ] || die "the controls don't answer on 127.0.0.1:8130 (sudo systemctl status monkey-panel): they hold the login"
    READY=$(auth_tool ready 2>&1) || die "no owner can log in yet ($READY): run sudo sh $0 --add-user NAME owner EMAIL and set its password first"
    log "logins: $READY"
    switch_site Caddyfile.staff-login
    log "the staff page now has its own login page: https://$HOST/login (to go back: sudo sh $0 --use-basic-auth)"
    exit 0
fi

if [ "$MODE" = use-basic-auth ]; then
    [ "$(logins_count)" -gt 0 ] 2>/dev/null || die "no password-box logins: run sudo sh $0 --login NAME first"
    switch_site Caddyfile.staff
    log "the staff page asks for the browser password again (logins: $(logins_count))"
    exit 0
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

if [ "$MODE" = install-helper ]; then
    [ "$(id -u)" = 0 ] || die 'run as root: it installs a root service'
    # The path unit watches /srv/monkey/staff/requests: another STAFF_DIR would never be seen.
    watched=${HELPER_WATCHED:-/srv/monkey/staff}   # (another only for the tests)
    unit_dir=${UNIT_DIR:-/etc/systemd/system}
    [ "$STAFF_DIR" = "$watched" ] || die "the helper watches $watched/requests, and STAFF_DIR is $STAFF_DIR"
    # Root runs only root's copies, and takes the units from root's own clone, never from the checkout monkey can
    # write (docs/LIVE.md, "Root's own copies").
    root_dest=${ROOT_DEST:-/opt/monkey}
    root_src=${ROOT_SRC:-/opt/monkey/src}
    for f in deploy/monkey-staff-helper.sh deploy/monkey-backup.sh deploy/lib.sh tools/staff_apex.py; do
        [ -r "$root_dest/$f" ] || die "$root_dest/$f is missing: install root's copies first (sudo sh $root_dest/deploy/install-root.sh, or the first time docs/LIVE.md, \"Root's own copies\")"
    done
    for unit in $HELPER_UNITS; do
        [ -r "$root_src/deploy/$unit" ] || die "$root_src/deploy/$unit is missing: install root's copies first (docs/LIVE.md, \"Root's own copies\")"
    done
    [ -d "$STAFF_DIR" ] || die "no $STAFF_DIR: run sudo sh $0 --install first"
    # The page (monkey) writes requests here; root reads them. Nobody else may look.
    install -d -m 770 -o monkey -g monkey "$STAFF_DIR/requests"
    log "requests folder: $STAFF_DIR/requests"
    helper_changed=''
    for unit in $HELPER_UNITS; do
        cmp -s "$root_src/deploy/$unit" "$unit_dir/$unit" || helper_changed="$helper_changed $unit"
    done
    for unit in $helper_changed; do
        install -m 644 -o root -g root "$root_src/deploy/$unit" "$unit_dir/$unit"
        log "installed $unit_dir/$unit"
    done
    [ -z "$helper_changed" ] || systemctl daemon-reload
    systemctl enable --now monkey-staff-helper.path
    [ -z "$helper_changed" ] || systemctl restart monkey-staff-helper.path
    log 'running: monkey-staff-helper.path (the page can now start a backup, list snapshots and restore one)'
    exit 0
fi

if [ "$MODE" = install ]; then
    command -v curl >/dev/null 2>&1 || die 'curl is missing'
    for unit in $UNITS $PANEL Caddyfile.staff staff/index.html; do
        [ -r "$REPO_DIR/deploy/$unit" ] || die "$REPO_DIR/deploy/$unit is missing: is the release with the staff page deployed?"
    done
    [ -r "$REPO_DIR/tools/staff_panel.py" ] || die "$REPO_DIR/tools/staff_panel.py is missing: is the release with the staff page controls deployed?"
    # Whichever login the site has now stays: the login page once --use-new-login switched to it, else the password box.
    if is_new_login; then SITE_FILE=Caddyfile.staff-login; else SITE_FILE=Caddyfile.staff; fi
    [ "$SITE_FILE" = Caddyfile.staff-login ] || [ "$(logins_count)" -gt 0 ] 2>/dev/null || die "no logins yet: run sudo sh $0 --login NAME first, so the site never opens without a password"
    install -d -m 755 -o monkey -g monkey "$STAFF_DIR"
    log "status folder: $STAFF_DIR"
    UNREADABLE=$(caddy_cannot_read)
    [ -z "$UNREADABLE" ] || die "the caddy user can't read $UNREADABLE: nothing was added to Caddy"

    BACKUP=$(mktemp -d "$CADDY_DIR/.staff-backup.XXXXXX")
    trap 'rm -rf "$BACKUP"' EXIT
    cp -p "$MAIN" "$BACKUP/Caddyfile"
    [ ! -e "$SITE" ] || cp -p "$SITE" "$BACKUP/staff.caddy"
    install -m 644 -o root -g root "$REPO_DIR/deploy/$SITE_FILE" "$SITE"
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
    install_timer monkey-staff.timer $UNITS
    install_panel
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
    if systemctl is-active --quiet "$PANEL" 2>/dev/null; then PANEL_STATE=running; else PANEL_STATE='not running'; fi
    PANEL_CHANGED=$(changed_units "$PANEL")
    log "controls: $PANEL $PANEL_STATE; unit to copy:${PANEL_CHANGED:- none}"
    log "the controls answer a request with no login: $(panel_answer) (403 is right; 000 is no answer)"
    if systemctl is-active --quiet monkey-staff-helper.path 2>/dev/null; then HELPER_STATE=running; else HELPER_STATE="not installed (sudo sh $0 --install-helper)"; fi
    HELPER_CHANGED=$(changed_units $HELPER_UNITS)
    log "backup helper: monkey-staff-helper.path $HELPER_STATE; units to copy:${HELPER_CHANGED:- none}"
    if [ "$(id -u)" = 0 ]; then
        log "logins:$(sed -n 's/^\([A-Za-z0-9_-]*\) .*/ \1/p' "$LOGINS" 2>/dev/null | tr -d '\n')"
        if [ -r "$REPO_DIR/tools/staff_auth.py" ]; then
            log "login page logins: $(auth_tool ready 2>&1 | tail -n 1)"
        fi
        if is_new_login; then
            log 'login: the page'"'"'s own login page (deploy/Caddyfile.staff-login); back: --use-basic-auth'
        elif [ -e "$SITE" ]; then
            log 'login: the browser'"'"'s password box (deploy/Caddyfile.staff); to switch: --use-new-login'
        fi
        if [ -e "$SITE" ]; then
            log "a visit with no password gets: $(no_password /) ($(gate_want | cut -d ' ' -f 1) is right; 000 is no answer yet)"
            UNREADABLE=$(caddy_cannot_read)
            if [ -n "$UNREADABLE" ]; then
                log "PROBLEM: the caddy user can't read $UNREADABLE, so a visit with the password fails"
            else
                log 'the caddy user can read the page and the status file'
            fi
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
