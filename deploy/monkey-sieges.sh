#!/bin/sh
# Siege windows and the game's clock (tools/sieges.py; docs/SEASONS.md, "Siege windows"): a timed job
# (deploy/lib.sh, timed_job) that sends `python3 tools/sieges.py commands` to the server over RCON: the minute,
# the seconds until the next siege window opens and closes, and its hours. Minecraft can't see the wall clock;
# the monkey-sieges pack counts on from each run, warns, opens and closes the window on the second, and (when
# staff have switched siege windows on) opens and closes the claims. The same minute ends 7-day wars
# (tools/diplomacy.py), so the timer runs whether or not siege windows are on. monkey-sieges.timer runs it every
# 5 minutes as the monkey user; every run sends the same kind of command, so running it again is safe.
#
#   sh monkey-sieges.sh                  sends the clock (a server that isn't running is skipped)
#   sh monkey-sieges.sh --check          prints the coming windows, the command for now and whether the timer is
#                                        installed and running; changes nothing
#   sudo sh monkey-sieges.sh --install   copies monkey-sieges.service and monkey-sieges.timer from the deployed
#                                        checkout to /etc/systemd/system (only if they changed) and starts the timer
#
# Reads only REPO_DIR, LIVE_DIR and LOCK_FILE from /etc/monkey-deploy.env (or MONKEY_DEPLOY_ENV). Needs python3
# 3.10 or newer (deploy/upgrade-2.5.0.sh installs it).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=monkey-sieges
. "$(dirname -- "$0")/lib.sh"

JOB_TOOL=sieges.py
JOB_FOR='the siege windows and the clock'
JOB_SHOW=windows
JOB_RETRY='the timer tries again in 5 minutes'
JOB_DOWN='nothing would be sent'
timed_job "$@"
