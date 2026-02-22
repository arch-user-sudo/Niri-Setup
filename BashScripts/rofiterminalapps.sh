#!/bin/bash

# List of terminal apps
apps=("bluetuith" "nmtui" "btop" "nvim" "pulsemixer" "bash ~/screenshot.sh")

# Show Rofi in "drun" style (grid menu) using -dmenu replacement
choice=$(printf '%s\n' "${apps[@]}" | rofi -show run -dmenu -p "Terminal Apps:")

# Exit if nothing selected
[ -z "$choice" ] && exit 0

# Launch in foot
alacritty -e "$choice"
