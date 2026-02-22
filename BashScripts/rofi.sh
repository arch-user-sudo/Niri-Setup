#!/bin/bash

# Check if rofi is already running
if pgrep -x rofi >/dev/null; then
    # If running, kill it
    pkill -x rofi
else
    # Otherwise, launch rofi (change mode as needed)
    rofi -show drun
fi
