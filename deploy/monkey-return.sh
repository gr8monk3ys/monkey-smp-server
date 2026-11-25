#!/bin/sh
# The relaunch's 24-hour return (tools/timed_return.py; docs/relaunch/lifesteal.md): a timed job (deploy/lib.sh,
# timed_job) that brings an eliminated player back with 3 hearts a day after they went out. LifeStealZ keeps no
# time of elimination, so the tool notes it from LifeStealZ's player data and keeps the list in the release's
# docker folder. monkey-return.timer runs it every 10 minutes as the monkey user. Outside the relaunch's season,
# or with nobody due, it sends nothing.
#
#   sh monkey-return.sh                  notes who is out and sends the revives due (a stopped server waits)
#   sh monkey-return.sh --check          prints who is out, when each comes back, the commands for now and
#                                        whether the timer is installed and running; changes nothing
#   sudo sh monkey-return.sh --install   copies monkey-return.service and monkey-return.timer from the deployed
#                                        checkout to /etc/systemd/system (only if they changed) and starts the timer
#
# Reads only REPO_DIR, LIVE_DIR and LOCK_FILE from /etc/monkey-deploy.env (or MONKEY_DEPLOY_ENV), and
# server/plugins/LifeStealZ/userData.db. Needs python3 3.10 or newer.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=monkey-return
. "$(dirname -- "$0")/lib.sh"

JOB_TOOL=timed_return.py
JOB_WORLD=1
JOB_SHOW=waiting
JOB_FOR='the 24-hour return'
JOB_RETRY='the timer tries again in 10 minutes'
JOB_DOWN='the revives due wait for it'
timed_job "$@"
