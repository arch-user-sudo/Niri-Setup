#!/usr/local/bin/fish

# Application launcher using skim (sk) and fish shell
# Properly handles desktop entries without confusing native vs flatpak

# Function to launch a desktop file properly
function launch_desktop_entry
    set desktop_file $argv[1]
    
    # Get the full path to the desktop file
    set full_path (realpath "$desktop_file" 2>/dev/null)
    if test -z "$full_path"
        set full_path "$desktop_file"
    end
    
    # Use gtk-launch with the full desktop file path
    setsid -f gtk-launch (basename "$full_path" .desktop) >/dev/null 2>&1 &
end

# Scan existing directories and find desktop files
set existing_dirs
for dir in /usr/share/applications "$HOME/.local/share/applications" /var/lib/flatpak/exports/share/applications "$HOME/.local/share/flatpak/exports/share/applications"
    if test -d "$dir"
        set existing_dirs $existing_dirs "$dir"
    end
end

# Find and process desktop entries
find $existing_dirs -name '*.desktop' 2>/dev/null | while read desktop_file
    # Skip if NoDisplay=true
    if grep -q '^NoDisplay=true' "$desktop_file" 2>/dev/null
        continue
    end
    
    # Get the Name field
    set name (grep -m1 '^Name=' "$desktop_file" 2>/dev/null | cut -d= -f2-)
    if test -z "$name"
        continue
    end
    
    # Skip terminal apps (optional)
    if grep -q '^Terminal=true' "$desktop_file" 2>/dev/null
        continue
    end
    
    echo "$name | $desktop_file"
end | sort -u | sk --prompt="apps> " | read choice

if test -z "$choice"
    exit 0
end

# Extract the full desktop file path
set desktop_file (echo "$choice" | sed 's/.* | //')

# Launch the specific desktop file
if test -f "$desktop_file"
    launch_desktop_entry "$desktop_file"
else
    echo "Desktop file not found: $desktop_file" >&2
    exit 1
end