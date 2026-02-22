#!/usr/bin/bash
exec grim -g "$(slurp)" "/home/lynch/Screenshots/screenshot-$(date +%s).png"
