#!/bin/sh
# Safely stops The Realms (saves the world first).
# Linux and macOS; on Windows use "Stop Server.bat". Run it as  ./stop.sh  (or  sh stop.sh).
cd "$(dirname "$0")" || exit 1
exec sh realms/realms.sh stop "$@"
