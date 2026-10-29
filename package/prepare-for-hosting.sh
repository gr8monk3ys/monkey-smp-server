#!/bin/sh
# Makes a zip of the server for running it on an online host instead of this computer (see HOSTING.txt inside).
# Linux and macOS; on Windows use "Prepare for Hosting.bat". Run it as  ./prepare-for-hosting.sh  (or  sh prepare-for-hosting.sh).
cd "$(dirname "$0")" || exit 1
exec sh monkey/monkey.sh export-host "$@"
