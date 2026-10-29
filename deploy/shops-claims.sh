#!/bin/sh
# The one-off step for shops on the live VPS (docs/LIVE.md, "Shops in claims"). The release with Universal Shops
# ships `forcedBlockProtectionExceptionList = [..., "hand$universal_shops:trade_block"]` in
# defaults/config/openpartiesandclaims-server.toml, so anyone may click a Trade Shop with an empty hand in
# someone else's claim and buy from it. This adds that entry to the live server's own copy
# (deploy/claims-exception.sh does the work). Run it as root once that release is live. Started with systemd-run
# it carries on if the SSH connection drops while the server is stopped:
#
#   systemd-run --unit=monkey-shops --collect -p TimeoutStopSec=20min sh /srv/monkey/repo/deploy/shops-claims.sh
#   journalctl -fu monkey-shops
#
#   sh shops-claims.sh --check   says whether it is still to do, and changes nothing
#   sh shops-claims.sh --now     stops the server without the warning in chat
#
# Its log is /var/log/monkey-shops-claims.log (or SHOPS_LOG).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=shops-claims
. "$(dirname -- "$0")/lib.sh"

WHAT='shops in claims'
LOG_TO=${SHOPS_LOG:-/var/log/monkey-shops-claims.log}
KEEP_AS=before-shops
KEY=forcedBlockProtectionExceptionList
ENTRIES='hand$universal_shops:trade_block'  # the same entry as defaults/config/openpartiesandclaims-server.toml
MOD='Universal Shops'
JARS='universal_shops-*.jar'
NOT_YET='the release with shops is live'
. "$(dirname -- "$0")/claims-exception.sh"
