if status is-interactive
    # Commands to run in interactive sessions can go here
end

zoxide init fish | source

starship init fish | source

alias yayf='fzf --height=30%'
alias weather='curl wttr.in/Kimberley'
alias sdb1='sudo mount /dev/sdb1 ~/sdb1'
alias sdb1x='sudo umount ~/sdb1'
alias mtp='jmtpfs ~/mtp'
alias mtpx='fusermount -u ~/mtp'
alias portal='nohup /usr/lib/xdg-desktop-portal-gtk >/dev/null 2>&1 & disown'
alias polkit='nohup /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 >/dev/null 2>&1 & disown'
alias clock='tty-clock -c -D -C 7'
alias unlock='sudo sysctl kernel.unprivileged_userns_clone=1'
alias lock='sudo sysctl kernel.unprivileged_userns_clone=0'
alias ls='eza --icons'
alias fetch='fastfetch'
alias fetch2='fastfetch --logo arch'
alias matrix='cmatrix -u 8 -C white'
alias scan='clamscan -r -i'
alias optimize='sudo fstrim -v /'
alias screenshot='bash ~/BashScripts/screenshot.sh'
alias wpp='nohup python ~/BashScripts/wallpaper.py &'
alias a='~/BashScripts/fzflauncher.sh'
alias zenbrowser='nohup flatpak run app.zen_browser.zen >/dev/null 2>&1 & disown'
alias stm='nohup flatpak run com.valvesoftware.Steam >/dev/null 2>&1 & disown'
alias x='xwayland-satellite & disown'
alias p='niri --session'
alias boost1='sudo renice -n -20 -p $(pidof dwl)'
alias boost1off='sudo renice -n -0 -p $(pidof dwl)'
alias boost2='pidof Xwayland | xargs sudo renice -n -20 -p'
alias boost2off='pidof Xwayland | xargs sudo renice -n -0 -p'
alias boost3='pidof CombatMaster.x8 | xargs sudo renice -n -20 -p'
alias S='nohup bash ~/BashScripts/wbsystemstats.sh & disown'
#alias s='fish ~/togglescripts/waybar.sh'
alias s='~/BashScripts/WaybarSwitcher.sh'
fastfetch
#macchina -t Hydrogen
#pfetch

set -g fish_greeting ""

#function s
#    if pgrep -x waybar >/dev/null
#        pkill waybar
#    else
#        nohup waybar & disown
#    end
#end
function cd
    if builtin cd $argv
        ls -a
    end
end

function imgg
    set -l files (ls -1 | string match -r '.*\.(png|jpg|jpeg|webp|gif)$' | sk -m)

    if test (count $files) -gt 0
        imv-dir $files >/dev/null 2>&1 &
        disown
    end
end

function pdf
    # List all PDFs in the current directory
    set -l files (find . -maxdepth 1 -type f -iname "*.pdf" -print)

    # Open fzf with live PDF selection
    printf "%s\n" $files | sk --prompt="PDF > " \
        --bind "enter:execute-silent(nohup zathura "{}" & disown)"
end

function wp
    # List all images in the current directory
    set -l files (find . -maxdepth 1 -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.webp" -o -iname "*.gif" \) -print)

    # Open fzf with live wallpaper selection
    printf "%s\n" $files | sk --prompt="Wallpaper > " \
        --bind "enter:execute-silent(pkill -f '^wbg' >/dev/null 2>&1; nohup wbg -s "{}" &)"
end

function img
    # List all images in the current directory
    set -l files (find . -maxdepth 1 -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.webp" -o -iname "*.gif" \) -print)

    # Open fzf with live wallpaper selection
    printf "%s\n" $files | sk --prompt="View > " \
        --bind "enter:execute-silent(nohup imv-dir "{}" &)"
end

fish_config theme choose tomorrow-night

# Auto-start niri on TTY1 without checking WAYLAND/X
#if status is-login
#    if test (tty) = /dev/tty1
#        exec niri --session
#    end
#end
