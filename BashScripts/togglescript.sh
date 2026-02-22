#!/usr/local/bin/fish

fd . ~/togglescripts/ --type f | grep .sh | fzf | xargs -r fish
