#!/usr/bin/env bash

SCRIPT="$HOME/BashScripts/wallpaper.py"

# Check if the script is already running
if pgrep -f "python.*$SCRIPT" >/dev/null; then
  # Kill it if running
  pkill -f "python.*$SCRIPT"
else
  # Start it if not running
  python "$SCRIPT" &
  disown
fi
