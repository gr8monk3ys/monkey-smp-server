#!/bin/sh
# The one-off step for the spawn NPCs on a live server installed before 2.9.1 (docs/LIVE.md, "NPCs in claims").
# defaults/config/openpartiesandclaims-server.toml ships `forcedEntityProtectionExceptionList = ["minecraft:minecart",
# "hand$easy_npc:humanoid", "hand$easy_npc:humanoid_slim"]`, so anyone may right-click an Easy NPC (the Guide, the
# Town Crier) with an empty hand in any claim, spawn's server claim included. This adds those entries to the live
# server's own copy (deploy/claims-exception.sh does the work). Run it as root. Started with systemd-run it carries
# on if the SSH connection drops while the server is stopped:
#
#   systemd-run --unit=realms-npcs --collect -p TimeoutStopSec=20min sh /srv/realms/repo/deploy/npc-claims.sh
#   journalctl -fu realms-npcs
#
#   sh npc-claims.sh --check   says whether it is still to do, and changes nothing
#   sh npc-claims.sh --now     stops the server without the warning in chat
#
# Its log is /var/log/realms-npc-claims.log (or NPCS_LOG).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=npc-claims
. "$(dirname -- "$0")/lib.sh"

WHAT='NPCs in claims'
LOG_TO=${NPCS_LOG:-/var/log/realms-npc-claims.log}
KEEP_AS=before-npcs
KEY=forcedEntityProtectionExceptionList
# The same entries as defaults/config/openpartiesandclaims-server.toml.
ENTRIES='hand$easy_npc:humanoid hand$easy_npc:humanoid_slim'
MOD='Easy NPC'
JARS='easy_npc-*.jar'
NOT_YET='a release with the spawn NPCs is live'
. "$(dirname -- "$0")/claims-exception.sh"
