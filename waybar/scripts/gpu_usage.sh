#!/bin/bash

output=$(radeontop -d - -i 1 -l 1 2>/dev/null)
line=$(echo "$output" | tail -n1)

gpu_usage=$(echo "$line" | grep -oP 'gpu \K[0-9]+(\.[0-9]+)?')
vram_usage=$(echo "$line" | grep -oP 'vram \K[0-9]+(\.[0-9]+)?')

gpu_usage=${gpu_usage:---}
vram_usage=${vram_usage:---}

echo "GPU: ${gpu_usage}% VRAM: ${vram_usage}%"

