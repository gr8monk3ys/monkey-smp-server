#!/usr/bin/env bash
# Boots the server zip's Docker setup (MonkeySMP-Server/docker) the way a VPS owner would:
# unzip, set EULA in docker/.env, docker compose up -d, wait for "Done", run a console command,
# docker compose stop, and check it ran as the folder's owner and saved the world on the way down.
#
#   tests/docker-smoke.sh dist/MonkeySMP-Server-2.3.0.zip [work-dir]
#   MEMORY_GB=4 TIMEOUT_MINUTES=30 tests/docker-smoke.sh ...
#   GAME_PORT=35565 VOICE_PORT=34454 MAP_PORT=38100 tests/docker-smoke.sh ...   (a server already on 25565)
#
# Leaves the unzipped folder (with server/logs and compose.log) in work-dir; removes the container,
# network and image it built. COMPOSE_PROJECT_NAME picks the compose project (default monkey-docker-smoke).
set -euo pipefail

zip="$1"
work="${2:-$(mktemp -d)}"
timeout_min="${TIMEOUT_MINUTES:-30}"
memory="${MEMORY_GB:-4}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-monkey-docker-smoke}"

mkdir -p "$work"
unzip -q -o "$zip" -d "$work"
root="$work/MonkeySMP-Server"
[ -d "$root/docker" ] || { echo "no MonkeySMP-Server/docker folder in $zip"; exit 1; }
cd "$root/docker"
for f in compose.yaml Dockerfile entrypoint.sh .env.example; do
    [ -f "$f" ] || { echo "docker/$f is missing from the zip"; exit 1; }
done
log="$root/server/logs/latest.log"

cleanup() { docker compose down --rmi local --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

fail=0
docker compose build --quiet

echo "--- without EULA=TRUE it must refuse to start (and install nothing)"
set +e
refusal=$(docker compose run --rm -T -e EULA= monkey 2>&1)
code=$?
set -e
if [ "$code" -eq 0 ] || ! grep -q 'aka.ms/MinecraftEULA' <<<"$refusal"; then
    echo "$refusal"; echo "started without agreeing to the EULA (exit $code)"; fail=1
fi
[ ! -e "$root/server" ] || { echo "the refused start still created server/"; fail=1; }

echo "--- .env from .env.example: EULA=TRUE, MEMORY_GB=$memory"
sed -e 's/^EULA=.*/EULA=TRUE/' -e "s/^MEMORY_GB=.*/MEMORY_GB=$memory/" .env.example > .env
if ! grep -qx 'EULA=TRUE' .env || ! grep -qx "MEMORY_GB=$memory" .env; then
    echo ".env.example has no EULA= or MEMORY_GB= line"; exit 1
fi

docker compose up -d
cid=$(docker compose ps -aq monkey)
deadline=$(( $(date +%s) + timeout_min * 60 ))
reached=no
while [ "$(date +%s)" -lt "$deadline" ]; do
    if [ -f "$log" ] && grep -q 'Done (' "$log"; then reached=yes; break; fi
    state=$(docker inspect -f '{{.State.Status}} {{.RestartCount}}' "$cid")
    if [ "$state" != "running 0" ]; then echo "the container stopped or restarted ($state)"; break; fi
    sleep 10
done

if [ "$reached" = yes ]; then
    echo "--- started: $(grep -m1 'Done (' "$log")"
    # The exec helper runs monkey.sh in the running container, as the server's user, over RCON.
    if ! reply=$(docker compose exec -T monkey monkey rcon list 2>&1) || ! grep -q 'players online' <<<"$reply"; then
        echo "$reply"; echo "rcon through 'docker compose exec monkey monkey' failed"; fail=1
    fi
    # The server must run as the release folder's owner (a plain user on Docker Desktop), never as
    # root for a host user's folder, so its files stay the host user's.
    java_uid=$(docker compose exec -T monkey sh -c \
        'for p in /proc/[0-9]*; do [ "$(cat $p/comm 2>/dev/null)" = java ] && stat -c %u "$p"; done; true' | tr -d '\r')
    echo "--- java runs as uid ${java_uid:-?}"
    if [ "$(id -u)" != 0 ] && [ "${java_uid:-0}" = 0 ]; then echo "java runs as root"; fail=1; fi
    if [ "$(stat -c %u "$log")" != "$(stat -c %u "$root")" ]; then
        echo "server files belong to uid $(stat -c %u "$log"), the release folder to $(stat -c %u "$root")"; fail=1
    fi
fi

# What a host does to stop it: SIGTERM, which the entrypoint turns into a saving shutdown.
started=$(date +%s)
docker compose stop
took=$(( $(date +%s) - started ))
exit_code=$(docker inspect -f '{{.State.ExitCode}}' "$cid")
docker compose logs --no-color monkey > "$root/compose.log" 2>&1 || true
echo "--- stopped in ${took}s, exit code $exit_code"

[ "$reached" = yes ] || { echo "the server never printed Done"; fail=1; }
[ "$exit_code" = 0 ] || { echo "the container exited with $exit_code, not 0 (137 = killed before it finished saving)"; fail=1; }
if grep -nE 'Incompatible mods|Mixin apply.*failed|Exception in server tick loop|---- Minecraft Crash Report' "$root/compose.log" "$log" 2>/dev/null; then
    echo "errors in the server log"; fail=1
fi
if [ "$reached" = yes ] && ! grep -qE 'All dimensions are saved|Saving worlds' "$log"; then
    echo "no clean shutdown in server/logs/latest.log"; fail=1
fi
grep -hE 'Loading [0-9]+ mods|Done \(' "$root/compose.log" | head -n 3 || true
if [ "$fail" -eq 0 ]; then
    echo "DOCKER SMOKE TEST PASSED"
else
    tail -n 60 "$root/compose.log"; echo "DOCKER SMOKE TEST FAILED"; exit 1
fi
