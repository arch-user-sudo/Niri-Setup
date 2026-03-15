#!/bin/bash

# Path to your Python script
SCRIPT="/home/lynch/.config/eww/newsub20222.py"

# Optional: name for identifying the process
PROCESS_NAME=$(basename "$SCRIPT")

# Check if it's already running
PID=$(pgrep -f "$SCRIPT")

if [ -z "$PID" ]; then
    echo "Starting $PROCESS_NAME..."
    python3 "$SCRIPT" &
    echo "$PROCESS_NAME started with PID $!"
else
    echo "Stopping $PROCESS_NAME (PID: $PID)..."
    kill "$PID"
    echo "$PROCESS_NAME stopped."
fi
