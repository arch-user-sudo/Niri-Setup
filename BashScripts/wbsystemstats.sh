#!/bin/bash

# Define the command to avoid repetition and typos
WAYBAR_CMD="waybar -c /home/lynch/.config/underbar/config.jsonc -s /home/lynch/.config/underbar/style.css"

# Check if the process is already running
if pgrep -f "$WAYBAR_CMD" >/dev/null; then
  # If it's running, kill it
  pkill -f "$WAYBAR_CMD"
else
  # If it's not running, launch it in the background
  $WAYBAR_CMD &
fi
