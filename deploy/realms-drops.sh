#!/bin/sh
# Weeknight supply drops (tools/drops.py; docs/ADMIN.md, "Supply drops"): a timed job (deploy/lib.sh, timed_job)
# that sends `python3 tools/drops.py commands WORLD` to the server over RCON; drops.py says what the try's return
# code means. Minecraft can't see claims or the wall clock, so this picks the spots (from the saved claims and
# border) and the night; the realms-drops data pack decides the rest (enough players online, no drop yet tonight,
# no event on). realms-drops.timer runs it every 10 minutes as the realms user. Outside drop hours (Monday to
# Thursday, 6 to 10 PM Pacific) there is nothing to send, so it logs nothing and takes no lock; once tonight's
# drop has run the pack turns the rest away, so running it again is safe.
#
#   sh realms-drops.sh                  sends the commands (a server that isn't running is skipped)
#   sh realms-drops.sh --check          prints the spots and commands for now and whether the timer is installed
#                                       and running; changes nothing
#   sudo sh realms-drops.sh --install   copies realms-drops.service and realms-drops.timer from the deployed
#                                       checkout to /etc/systemd/system (only if they changed) and starts the timer
#
# Reads only REPO_DIR, LIVE_DIR and LOCK_FILE from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV), and the saved
# world's claims and border. Needs python3 3.10 or newer (deploy/upgrade-2.5.0.sh installs it).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=realms-drops
. "$(dirname -- "$0")/lib.sh"

JOB_TOOL=drops.py
JOB_WORLD=1
JOB_SHOW=spots
JOB_FOR='supply drops'
JOB_NONE='outside drop hours, or no spot'
JOB_RETRY='the timer tries again in 10 minutes'
JOB_DOWN='nothing would be sent'
timed_job "$@"
