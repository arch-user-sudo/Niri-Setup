#!/usr/bin/env bash
# File: weather.sh
# Make sure to chmod +x weather.sh

# Your location, can be a city name or coordinates
LOCATION="Kimberley"

# Fetch weather from wttr.in (quiet output, 1 line, no ANSI colors)
WEATHER=$(curl -s "https://wttr.in/$LOCATION?format=%c+%t")

# Output for Waybar
echo "$WEATHER"
