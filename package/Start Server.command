#!/bin/sh
# macOS: double-click in Finder to start Monkey SMP in a Terminal window (the same as ./start.sh).
cd "$(dirname "$0")" || exit 1
exec sh ./start.sh
