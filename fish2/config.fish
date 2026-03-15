# Aliases
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
alias ls='exa --icons'
alias fetch='fastfetch'
alias fetch2='fastfetch --logo arch'
alias matrix='cmatrix -u 8 -C white'
alias scan='clamscan -r -i'
alias optimize='sudo fstrim -v /'
alias dwll='slstatus -s | dwl'
alias qute='nohup firejail qutebrowser &'
alias screenshot='bash ~/screenshot.sh'
alias wp='nohup python ~/wallpaper.py &'
alias launch='bash ~/fzflauncher.sh'

set -g fish_greeting "Hi Kearan"

fastfetch
# FUNCTIONS

function cd
    if builtin cd $argv
        ls -a
    end
end

set -U fish_color_user yellow
set -U fish_color_cwd yellow
set -x LS_COLORS "ex=38;5;33:ln=38;5;37:so=38;5;213:pi=38;5;220:di=38;5;147:*.txt=38;5;15:*.md=38;5;207:*.sh=38;5;82:*.py=38;5;75:*.json=38;5;214:*.yml=38;5;159:"

set -x GSK_RENDERER ngl
function fish_prompt
    # Keep everything else as is
    echo -n " >   "
end

zoxide init fish | source

starship init fish | source

# Disable Client-Side Decorations (CSD) for GTK and Qt
set -gx GTK_CSD 0
set -gx QT_WAYLAND_DISABLE_WINDOWDECORATION 1

#export vblank_mode=1

# opencode
fish_add_path /home/lynch/.opencode/bin
export XDG_DATA_DIRS="$XDG_DATA_DIRS:/var/lib/flatpak/exports/share:$HOME/.local/share/flatpak/exports/share"
