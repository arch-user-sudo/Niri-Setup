#!/bin/bash

# Command to run
CMD="foot -e pulsemixer"

# Check if the command is already running
if pgrep -f "$CMD" >/dev/null; then
    # If running, kill it
    pkill -f "$CMD"
else
    # Otherwise, launch it
    $CMD &
fi
