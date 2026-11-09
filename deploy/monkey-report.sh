#!/bin/sh
# The staff page's weekly rule check (tools/staff_report.py): per player, which of the server's rules the logs show
# they broke that week, for the Reports tab. monkey-report.timer runs it early every Monday, Pacific, as the monkey
# user, at the lowest CPU and disk priority (monkey-report.service). It only reads the live server's files: Ledger's
# database (read-only), the players' stats, the parties and the game's logs. It never punishes, messages a player or
# rolls anything back. docs/LIVE.md, "The staff page".
#
#   sh monkey-report.sh                  writes STAFF_DIR/reports/WEEK.json for last week; a week already written is
#                                        skipped, so running it again, or by hand, is safe
#   sh monkey-report.sh --check          prints the week so far (changes nothing) and whether the timer is installed
#                                        and running
#   sudo sh monkey-report.sh --install   copies monkey-report.service and monkey-report.timer from the deployed
#                                        checkout to /etc/systemd/system (only if they changed) and starts the timer
#
# Reads only REPO_DIR, LIVE_DIR and STAFF_DIR (default /srv/monkey/staff) from /etc/monkey-deploy.env (or
# MONKEY_DEPLOY_ENV). Needs python3 3.10 or newer (deploy/upgrade-2.5.0.sh installs it).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=monkey-report
. "$(dirname -- "$0")/lib.sh"

case "${1:-}" in
    '') MODE=write ;;
    --check) MODE=check ;;
    --install) MODE=install ;;
    *) echo "usage: sh $0 [--check | --install]" >&2; exit 2 ;;
esac

ENV_FILE=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/monkey/repo)}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/monkey/MonkeySMP-Server)}
STAFF_DIR=${STAFF_DIR:-$(setting STAFF_DIR /srv/monkey/staff)}
UNITS='monkey-report.service monkey-report.timer'
TOOL=$REPO_DIR/tools/staff_report.py

if [ "$MODE" = install ]; then
    [ "$(id -u)" = 0 ] || die 'run as root: it installs a systemd timer'
    for unit in $UNITS; do
        [ -r "$REPO_DIR/deploy/$unit" ] || die "$REPO_DIR/deploy/$unit is missing: is the release with the weekly rule check deployed?"
    done
    [ -d "$STAFF_DIR" ] || die "no $STAFF_DIR: set up the staff page first (sudo sh $REPO_DIR/deploy/monkey-staff.sh --install)"
    install -d -m 755 -o monkey -g monkey "$STAFF_DIR/reports"
    log "reports folder: $STAFF_DIR/reports"
    install_timer monkey-report.timer $UNITS
    exit 0
fi

command -v python3 >/dev/null 2>&1 || die 'python3 is missing (deploy/upgrade-2.5.0.sh installs it)'
python_ok 10 || die 'python3 is older than 3.10'
[ -r "$TOOL" ] || die "$TOOL is missing: is the release with the weekly rule check deployed?"

if [ "$MODE" = check ]; then
    log 'the week so far (nothing is written):'
    log_each python3 -B "$TOOL" show "$LIVE_DIR" --reports "$STAFF_DIR/reports"   # its exit code is kept
    timer_state monkey-report.timer $UNITS
    log 'check finished: nothing was changed'
    exit 0
fi

# Root would leave files the monkey user's next run, and the staff page, can't replace.
[ "$(id -u)" != 0 ] || { echo "run it as monkey: sudo -u monkey sh $0" >&2; exit 1; }
[ -d "$STAFF_DIR/reports" ] || die "no $STAFF_DIR/reports: run sudo sh $0 --install"
log_each python3 -B "$TOOL" write "$LIVE_DIR" --out "$STAFF_DIR/reports"   # a failed run fails the unit
