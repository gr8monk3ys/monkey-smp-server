#!/usr/bin/env bash
# Boots an exported hosting bundle (realms.ps1 export-host) the way a VPS would, with docker compose,
# then checks it reached "Done", loaded cleanly and shut down cleanly.
#
#   tests/hosting-smoke.sh exports/TheRealms-2.0.0-hosting.zip [work-dir]
#   MEMORY_GB=4 TIMEOUT_MINUTES=25 tests/hosting-smoke.sh ...
set -euo pipefail

zip="$1"
work="${2:-$(mktemp -d)}"
timeout_min="${TIMEOUT_MINUTES:-25}"
export MEMORY_GB="${MEMORY_GB:-4}"

mkdir -p "$work"
unzip -q -o "$zip" -d "$work"
dir=$(find "$work" -mindepth 1 -maxdepth 1 -type d -name 'TheRealms-*-hosting' | head -n 1)
[ -n "$dir" ] || { echo "no TheRealms-*-hosting folder in $zip"; exit 1; }
cd "$dir"
[ -x start.sh ] || { echo "start.sh lost its executable bit"; exit 1; }

docker compose up -d
deadline=$(( $(date +%s) + timeout_min * 60 ))
reached=no
while [ "$(date +%s)" -lt "$deadline" ]; do
    if docker compose logs --no-color realms 2>&1 | grep -q 'Done ('; then reached=yes; break; fi
    if ! docker compose ps --status running --services | grep -qx realms; then echo "container exited early"; break; fi
    sleep 10
done

# "stop" sends SIGTERM; Minecraft saves the world and shuts down on it.
docker compose stop -t 180 || true
docker compose logs --no-color realms > compose.log 2>&1 || true
docker compose down || true

fail=0
[ "$reached" = yes ] || { echo "the server never printed Done"; fail=1; }
if grep -nE 'Incompatible mods|Mixin apply.*failed|Exception in server tick loop|---- Minecraft Crash Report' compose.log; then
    echo "errors in the server log"; fail=1
fi
if [ "$reached" = yes ] && ! grep -qE 'All dimensions are saved|Saving worlds' compose.log; then
    echo "no clean shutdown in the log"; fail=1
fi
grep -E 'Loading [0-9]+ mods|Done \(' compose.log | head -n 3 || true
if [ "$fail" -eq 0 ]; then echo "HOSTING SMOKE TEST PASSED"; else tail -n 60 compose.log; echo "HOSTING SMOKE TEST FAILED"; exit 1; fi
