#!/bin/sh
# Entrypoint of Monkey SMP Docker image (see Dockerfile and compose.yaml). /monkey is the release
# folder (MonkeySMP-Server), mounted from the host.
#
#   monkey-entrypoint [server]      install or update, then run the server until docker stop (default)
#   monkey-entrypoint <command>...  any monkey.sh command, as the same user as the server
#   monkey <command>...             the same, for: docker compose exec monkey monkey backup
#
# Environment (see .env.example):
#   EULA=TRUE    agree to the Minecraft EULA; without it (and without an earlier agreement in
#                server/eula.txt) the server refuses to start
#   OWNER        Minecraft name that becomes the admin on the first install (else no admin)
#   MEMORY_GB    server memory in GB (else picked from the memory the container may use)
#   PUID, PGID   user and group to run as (else the owner of the release folder)
set -eu

ROOT=/monkey
MONKEY="$ROOT/monkey/monkey.sh"

say() { printf '[docker] %s\n' "$*"; }
die() { printf '[docker] ERROR: %s\n' "$1" >&2; exit "${2:-1}"; }

# Runs the rest of this script as the owner of the release folder, so what the server writes on a
# Linux host belongs to the host user, not root. Docker Desktop (Windows, macOS) shows a mounted
# folder as owned by root but lets any user write to it, so a plain user (1000) is used there too;
# only a folder that really belongs to root (and isn't writable by others) runs as root.
drop_privileges() {
    [ "$(id -u)" = 0 ] || return 0
    uid="${PUID:-}"
    gid="${PGID:-}"
    if [ -z "$uid" ]; then
        uid=$(stat -c %u "$ROOT")
        gid=$(stat -c %g "$ROOT")
        if [ "$uid" = 0 ] && setpriv --reuid=1000 --regid=1000 --clear-groups test -w "$ROOT" 2>/dev/null; then
            uid=1000
            gid=1000
        fi
    fi
    gid="${gid:-$uid}"
    case "$uid:$gid" in
        *[!0-9:]* | :* | *:) die "PUID and PGID must be numbers, not '$uid' and '$gid'." ;;
    esac
    [ "$uid" != 0 ] || return 0
    # Give the user a name and home for programs that look them up (Java, PowerShell). The
    # container's /etc is its own, so this never touches the host.
    getent passwd "$uid" >/dev/null || echo "monkey:x:$uid:$gid:Monkey SMP:$HOME:/bin/sh" >>/etc/passwd
    getent group "$gid" >/dev/null || echo "monkey:x:$gid:" >>/etc/group
    exec setpriv --reuid="$uid" --regid="$gid" --clear-groups -- "$0" "$@"
}

check_folder() {
    [ -f "$MONKEY" ] || die "$ROOT has no monkey/monkey.sh. compose.yaml mounts the folder above docker/ at $ROOT: run docker compose from MonkeySMP-Server/docker, inside the unzipped release."
    [ -w "$ROOT" ] || die "user $(id -u) can't write to the release folder. Give it to that user (sudo chown -R $(id -u):$(id -g) MonkeySMP-Server) or set PUID and PGID in docker/.env to its owner."
}

eula_agreed() {
    case "$(printf '%s' "${EULA:-}" | tr '[:upper:]' '[:lower:]')" in
        true | yes) return 0 ;;
    esac
    return 1
}

eula_on_file() {
    grep -qiE '^[[:space:]]*eula[[:space:]]*=[[:space:]]*true' "$ROOT/server/eula.txt" 2>/dev/null
}

# The PID of the server's java process (this container has its own process list).
java_pid() {
    for d in /proc/[0-9]*; do
        if [ "$(cat "$d/comm" 2>/dev/null)" = java ]; then
            echo "${d#/proc/}"
            return 0
        fi
    done
    return 1
}

child=''
stopping=''

# docker stop (SIGTERM, passed on by tini) or Ctrl+C: SIGTERM to java runs Minecraft's shutdown
# hook, which saves every world and stops cleanly. Before java runs (still installing), the
# installer is stopped instead; its downloads are only kept once their hash checks out.
on_stop() {
    stopping=1
    if pid=$(java_pid); then
        say 'Stopping the server; it saves the world first...'
        kill -TERM "$pid" 2>/dev/null || true
    elif [ -n "$child" ]; then
        kill -TERM "$child" 2>/dev/null || true
    fi
}

# Runs a command in the background, with the container's stdin (the server console), and waits
# for it to exit, including after a signal interrupts the wait. Returns its exit code.
run_child() {
    "$@" <&3 &
    child=$!
    rc=0
    while :; do
        wait "$child" && rc=0 || rc=$?
        kill -0 "$child" 2>/dev/null || break
    done
    child=''
    return "$rc"
}

run_server() {
    check_folder
    set -- install -NonInteractive
    if eula_agreed; then
        set -- "$@" -AcceptEula
    elif ! eula_on_file; then
        die "To run a Minecraft server you have to agree to the Minecraft EULA: https://aka.ms/MinecraftEULA
          If you agree, set EULA=TRUE in docker/.env (copy .env.example to .env first), then run
          docker compose up -d   again." 64
    fi
    if [ -n "${OWNER:-}" ]; then
        case "$OWNER" in
            *[!A-Za-z0-9_]*) die "OWNER must be a Minecraft name (letters, digits and _), not '$OWNER'." ;;
        esac
        set -- "$@" -Owner "$OWNER"
    else
        set -- "$@" -NoOwner
    fi
    memory=''
    if [ -n "${MEMORY_GB:-}" ]; then
        case "$MEMORY_GB" in
            *[!0-9]* | 0*) die "MEMORY_GB must be a whole number of gigabytes, not '$MEMORY_GB'." ;;
        esac
        memory="$MEMORY_GB"
    fi
    [ "$(id -u)" != 0 ] || say 'Running as root, because the release folder belongs to root. To run as a plain user, give the folder to one (chown -R) or set PUID/PGID.'

    # Children started with & get /dev/null as stdin unless it is passed on explicitly.
    if { true <&0; } 2>/dev/null; then exec 3<&0; else exec 3</dev/null; fi
    trap on_stop TERM INT

    say "Installing or updating Monkey SMP in the release folder (as user $(id -u))"
    rc=0
    run_child sh "$MONKEY" "$@" || rc=$?
    [ -z "$stopping" ] || exit 0
    [ "$rc" = 0 ] || die "the install failed (exit code $rc); see the messages above." "$rc"

    if [ -n "$memory" ]; then set -- start -NonInteractive -MemoryGB "$memory"; else set -- start -NonInteractive; fi
    rc=0
    run_child sh "$MONKEY" "$@" || rc=$?
    if [ -n "$stopping" ]; then
        # Java exits with 143 after a SIGTERM even when it saved and stopped cleanly.
        say 'Server stopped.'
        exit 0
    fi
    # Stopped from its console ("stop") or crashed: exit, and Docker's restart policy decides.
    exit "$rc"
}

drop_privileges "$@"
case "$(basename "$0")" in
    monkey)
        [ $# -gt 0 ] || die 'usage: monkey <command> [args], e.g.  monkey backup | monkey add-player Steve | monkey rcon "say hi" | monkey status'
        check_folder
        exec sh "$MONKEY" "$@"
        ;;
esac
if [ "${1:-server}" = server ]; then
    run_server
fi
check_folder
exec sh "$MONKEY" "$@"
