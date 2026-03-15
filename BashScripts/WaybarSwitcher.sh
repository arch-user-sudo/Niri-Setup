#!/usr/bin/env bash

set -euo pipefail

# Find waybar* directories in ~/.config
mapfile -t waybar_dirs < <(find "$HOME/.config" -maxdepth 1 -type d -name 'waybar*' -printf '%f\n' | sort)

if [ "${#waybar_dirs[@]}" -eq 0 ]; then
  echo "No waybar* folders found in ~/.config"
  exit 1
fi

selected=$(printf "%s\n" "${waybar_dirs[@]}" | sk --prompt="Select Waybar config: ")

if [ -z "$selected" ]; then
  echo "No selection made."
  exit 0
fi

config="$HOME/.config/$selected/config.jsonc"
style="$HOME/.config/$selected/style.css"

if [ ! -f "$config" ]; then
  echo "Missing: $config"
  exit 1
fi

if [ ! -f "$style" ]; then
  echo "Missing: $style"
  exit 1
fi

pkill waybar || true
sleep 0.2

nohup waybar -c "$config" -s "$style" &
disown
