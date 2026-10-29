#!/bin/sh
# Starts Monkey SMP. The first time, it downloads everything and asks two questions.
# Linux and macOS; on Windows use "Start Server.bat". Run it as  ./start.sh  (or  sh start.sh).
cd "$(dirname "$0")" || exit 1
exec sh monkey/monkey.sh start "$@"
