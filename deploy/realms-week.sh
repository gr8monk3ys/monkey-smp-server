#!/bin/sh
# Keeps the weekly challenges and Season I's launch weekend on the wall clock (tools/challenges.py): a timed job
# (deploy/lib.sh, timed_job) that sends `python3 tools/challenges.py commands` to the server over RCON. Minecraft
# has no wall clock, so this is how the server learns that a new week started (Monday, 12 AM Pacific) and when the
# launch weekend ends. realms-week.timer runs it every hour as the realms user. Both commands do nothing when
# nothing changed, so running it again, or by hand, is safe.
#
#   sh realms-week.sh                  sends the commands (a server that isn't running is skipped: the week is
#                                      a score in the world, so the next hour catches up)
#   sh realms-week.sh --check          prints the commands for now and whether the timer is installed and
#                                      running; changes nothing
#   sudo sh realms-week.sh --install   copies realms-week.service and realms-week.timer from the deployed
#                                      checkout to /etc/systemd/system (only if they changed) and starts the timer
#
# Reads only REPO_DIR, LIVE_DIR and LOCK_FILE from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV). Needs python3
# 3.10 or newer (deploy/upgrade-2.5.0.sh installs it).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=realms-week
. "$(dirname -- "$0")/lib.sh"

JOB_TOOL=challenges.py
JOB_FOR='the weekly challenges'
JOB_RETRY='the next hour tries again'
JOB_DOWN='nothing would be sent this hour'
timed_job "$@"
