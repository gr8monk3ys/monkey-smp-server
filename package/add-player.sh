#!/bin/sh
# Lets a friend join (adds their Minecraft name to the whitelist):  ./add-player.sh Steve
# Without a name it asks for one. Linux and macOS; on Windows use "Add Player.bat".
cd "$(dirname "$0")" || exit 1
exec sh monkey/monkey.sh add-player "$@"
