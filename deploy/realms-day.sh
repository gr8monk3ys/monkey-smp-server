#!/bin/sh
# Starts a new day for the wardrobe's "days played" count (tools/wardrobe.py; docs/RETENTION.md): a timed job
# (deploy/lib.sh, timed_job) that sends `function realms:wardrobe/day_once {stamp:YYYYMMDD}` (`python3
# tools/wardrobe.py commands`), today's UTC date, to the server over RCON. realms-day.timer runs it at midnight
# UTC as the realms user. The data pack starts one day per date, so running it again the same date does nothing.
# A missed day is never caught up, so unlike the week a server that isn't running is a failure: realms-day.service
# then tries again every 10 minutes, for up to 6 hours (tools/wardrobe.py, GIVE_UP), and then posts a staff
# alert and stops (exit 4). Run by hand, it has no such limit: that is how staff start a day that was given up.
#
#   sh realms-day.sh                  sends the command (fails when the server isn't running)
#   sh realms-day.sh --check          prints the command and whether the timer is installed and running;
#                                     changes nothing
#   sudo sh realms-day.sh --install   copies realms-day.service and realms-day.timer from the deployed checkout
#                                     to /etc/systemd/system (only if they changed) and starts the timer
#
# Reads only REPO_DIR, LIVE_DIR and LOCK_FILE from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV), and the staff
# webhook when it gives up. Needs python3
# 3.10 or newer (deploy/upgrade-2.5.0.sh installs it).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=realms-day
. "$(dirname -- "$0")/lib.sh"

JOB_TOOL=wardrobe.py
JOB_FOR="the wardrobe's day job"
JOB_RETRY='realms-day.service tries again in 10 minutes'
JOB_DOWN='a run would fail, and realms-day.service would try again every 10 minutes until it answers'
timed_job "$@"
