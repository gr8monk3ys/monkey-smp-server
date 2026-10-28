#!/bin/sh
# The weekly update check on the live VPS (realms-updates.timer). GitHub Actions doesn't start in this
# private repo (billing), so this is what notices new builds, security fixes among them, while it can't.
# It runs tools/check_updates.py from the deployed checkout, so it compares what is live with what
# upstream has, and posts a line to Discord with the full report attached. It posts every week, so a
# silent Monday means the timer is broken. Read-only: taking an update is still `check_updates.py --apply`
# on a PC, the smoke test and a release (docs/MAINTAINING.md).
#
#   sh realms-updates.sh     check, print the report and post it
#
# Settings come from /etc/realms-deploy.env (or REALMS_DEPLOY_ENV): REPO_DIR, and the webhook
# STAFF_WEBHOOK_URL (empty = DISCORD_WEBHOOK_URL). Needs python3 (3.10 or newer) and curl.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=updates
. "$(dirname -- "$0")/lib.sh"

ENV_FILE=${REALMS_DEPLOY_ENV:-/etc/realms-deploy.env}
# shellcheck disable=SC1090
[ ! -f "$ENV_FILE" ] || . "$ENV_FILE"

REPO_DIR=${REPO_DIR:-/srv/realms/repo}
DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL:-}
STAFF_WEBHOOK_URL=${STAFF_WEBHOOK_URL:-$DISCORD_WEBHOOK_URL}

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Posts $1, with the file $2 attached when given. The messages are ours (no quotes or backslashes), so
# plain printf makes valid JSON.
post() {
    if [ -z "$STAFF_WEBHOOK_URL" ]; then
        log 'no webhook in the settings; not posting'
        return 0
    fi
    if [ $# -gt 1 ]; then
        curl -fsS -m 30 --form-string "payload_json={\"content\":\"$1\"}" -F "files[0]=@$2;type=text/markdown" \
            "$STAFF_WEBHOOK_URL" >/dev/null || log 'could not post to Discord'
    else
        printf '{"content":"%s"}' "$1" |
            curl -fsS -m 15 -H 'Content-Type: application/json' -d @- "$STAFF_WEBHOOK_URL" >/dev/null ||
            log 'could not post to Discord'
    fi
}

release=$(git -C "$REPO_DIR" describe --tags --always 2>/dev/null || echo 'the live release')
report="$work/updates-$(date +%Y-%m-%d).md"
# check_updates.py writes count=<newer builds + pin problems> to $GITHUB_OUTPUT, as it does in CI.
if ! GITHUB_OUTPUT="$work/count" python3 -B "$REPO_DIR/tools/check_updates.py" --out "$report" >"$work/out" 2>&1; then
    tail -n 30 "$work/out"
    post "Weekly update check for $release failed (tools/check_updates.py exited with an error). Check: journalctl -u realms-updates"
    exit 1
fi
cat "$report"
count=$(sed -n 's/^count=//p' "$work/count")
if [ "${count:-0}" -eq 0 ]; then
    post "Weekly update check for $release: everything is on the newest stable build."
else
    post "Weekly update check for $release: $count newer build(s) or pin problem(s), listed in the attached report. Take them with python tools/check_updates.py --apply on a PC, then the smoke test and a release (docs/MAINTAINING.md)." "$report"
fi
