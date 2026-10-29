#!/bin/sh
# Omens (tools/omens.py; docs/ADMIN.md, "Omens"): a timed job (deploy/lib.sh, timed_job) that sends
# `python3 tools/omens.py commands WORLD` to the server over RCON; omens.py says what the try's return code
# means. Minecraft can't see the wall clock, so this works out the week's evenings from the secret the
# monkey-omens data pack keeps in the saved scoreboard, and sends the evening's omens in order (with the
# Meteor's spots and the longest kill streaks); the pack decides the rest (enough players online, the season
# launched, no omen yet tonight, no event or supply drop on). monkey-omens.timer runs it every 10 minutes as
# the monkey user. Outside an evening's hours there is nothing to send, so it logs nothing and takes no lock;
# once tonight's omen has run the pack turns the rest away, so running it again is safe. --check doesn't show
# the week's plan (`python3 tools/omens.py plan WORLD` does, and spoils it).
#
#   sh monkey-omens.sh                  sends the commands (a server that isn't running is skipped)
#   sh monkey-omens.sh --check          prints the commands for now and whether the timer is installed and
#                                       running; changes nothing
#   sudo sh monkey-omens.sh --install   copies monkey-omens.service and monkey-omens.timer from the deployed
#                                       checkout to /etc/systemd/system (only if they changed) and starts the timer
#
# Reads only REPO_DIR, LIVE_DIR and LOCK_FILE from /etc/monkey-deploy.env (or MONKEY_DEPLOY_ENV), and the saved
# world's scoreboard, claims and border. Needs python3 3.10 or newer (deploy/upgrade-2.5.0.sh installs it).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=monkey-omens
. "$(dirname -- "$0")/lib.sh"

JOB_TOOL=omens.py
JOB_WORLD=1
JOB_FOR='omens'
JOB_NONE='not an omen evening now, or no omen key saved yet'
JOB_RETRY='the timer tries again in 10 minutes'
JOB_DOWN='nothing would be sent'
timed_job "$@"
