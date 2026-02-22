#!/usr/bin/env bash

DIRS="
/usr/share/applications
$HOME/.local/share/applications
/var/lib/flatpak/exports/share/applications
$HOME/.local/share/flatpak/exports/share/applications
"

apps=$(
  find $DIRS -name '*.desktop' 2>/dev/null | while read -r file; do
    name=$(grep -m1 '^Name=' "$file" | cut -d= -f2-)
    nodisplay=$(grep -m1 '^NoDisplay=true' "$file")
    terminal=$(grep -m1 '^Terminal=true' "$file")

    [ -z "$name" ] && continue
    [ -n "$nodisplay" ] && continue
    [ -n "$terminal" ] && continue

    id=$(basename "$file" .desktop)

    # Mark Flatpak apps visibly
    if grep -q '^X-Flatpak=' "$file" || echo "$file" | grep -q '/flatpak/exports/'; then
      printf '%s [flatpak] | %s\n' "$name" "$id"
    else
      printf '%s | %s\n' "$name" "$id"
    fi
  done
)

choice=$(printf '%s\n' "$apps" | sort -u | fzf --prompt="apps> ")
[ -z "$choice" ] && exit 0

id=$(printf '%s' "$choice" | sed 's/.* | //')

# Try Flatpak first
if flatpak info "$id" >/dev/null 2>&1; then
  setsid -f flatpak run "$id" >/dev/null 2>&1
else
  setsid -f gtk-launch "$id" >/dev/null 2>&1
fi
