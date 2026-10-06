#!/bin/sh
# Copies the world and settings into the backups folder. Safe while the server runs.
# Linux and macOS; on Windows use "Backup World.bat". Run it as  ./backup.sh  (or  sh backup.sh).
cd "$(dirname "$0")" || exit 1
exec sh realms/realms.sh backup "$@"
