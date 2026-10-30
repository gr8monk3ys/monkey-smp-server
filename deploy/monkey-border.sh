#!/bin/sh
# Border acts (tools/border.py; docs/SEASONS.md, "The acts of a season"): a timed job (deploy/lib.sh, timed_job)
# that sends `python3 tools/border.py commands WORLD` to the server over RCON. On an act's date (the Saturday event
# slot, 6 PM Pacific) it grows the Overworld's and the Nether's (1:8) world borders, then fits the live map's
# render masks to them (tools/map_border.py), reloads BlueMap, and an hour later purges the maps it changed so
# they render again. monkey-border.timer runs it every hour as the monkey user. With nothing due it logs nothing
# and takes no lock; it reads the saved world's borders and never shrinks one, so running it again is safe.
#
#   sh monkey-border.sh                  sends the commands (a server that isn't running is skipped)
#   sh monkey-border.sh --check          prints the season's acts, the borders, the commands for now and whether
#                                        the timer is installed and running; changes nothing
#   sudo sh monkey-border.sh --install   copies monkey-border.service and monkey-border.timer from the deployed
#                                        checkout to /etc/systemd/system (only if they changed) and starts the timer
#
# Installed for Season II (docs/SEASONS.md, "Season II"). Reads only REPO_DIR, LIVE_DIR and LOCK_FILE from
# /etc/monkey-deploy.env (or MONKEY_DEPLOY_ENV), and the saved world's scores and borders; writes only the map
# configs in the server's config/bluemap. Needs python3 3.10 or newer (deploy/upgrade-2.5.0.sh installs it).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=monkey-border
. "$(dirname -- "$0")/lib.sh"

JOB_TOOL=border.py
JOB_WORLD=1
JOB_SHOW=status
JOB_FOR='border acts'
JOB_NONE='no border act due, and the map fits the border'
JOB_RETRY='the timer tries again in an hour'
JOB_DOWN='nothing would be sent'
timed_job "$@"
