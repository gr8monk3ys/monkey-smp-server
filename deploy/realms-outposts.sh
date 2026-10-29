#!/bin/sh
# Outposts (tools/outposts.py; docs/ADMIN.md, "Outposts"): a timed job (deploy/lib.sh, timed_job) that sends
# `python3 tools/outposts.py commands WORLD` to the server over RCON; outposts.py says what the survey's return code
# means. Minecraft can't see claims, so this picks the outposts' spots (from the saved claims and border) after the
# launch and after each border act, moves one a claim has come too close to, and keeps the live map's marker set
# in step; the realms-outposts data pack checks the ground and runs the captures. realms-outposts.timer runs it
# every hour as the realms user. With nothing to place or move it logs nothing and takes no lock; the pack turns a
# second survey for the same border away, so running it again is safe.
#
#   sh realms-outposts.sh                  sends the commands (a server that isn't running is skipped)
#   sh realms-outposts.sh --check          prints the outposts, the commands for now and whether the timer is
#                                          installed and running; changes nothing
#   sudo sh realms-outposts.sh --install   copies realms-outposts.service and realms-outposts.timer from the deployed
#                                          checkout to /etc/systemd/system (only if they changed) and starts the timer
#
# Reads only REPO_DIR, LIVE_DIR and LOCK_FILE from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV), and the saved
# world's claims, border, scores and storage. Needs python3 3.10 or newer (deploy/upgrade-2.5.0.sh installs it).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=realms-outposts
. "$(dirname -- "$0")/lib.sh"

JOB_TOOL=outposts.py
JOB_WORLD=1
JOB_SHOW=status
JOB_FOR='outposts'
JOB_NONE='before the launch, or nothing to place or move'
JOB_RETRY='the timer tries again in an hour'
JOB_DOWN='nothing would be sent'
timed_job "$@"
