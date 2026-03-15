#!/bin/bash

# CPU temperature using sensors
cpu_temp=$(sensors | grep 'Package id 0:' | awk '{print $4}' | sed 's/+//' | sed 's/\..*//')

# GPU temperature from radeon hwmon
gpu_temp_path=$(find /sys/class/drm/card*/device/hwmon/hwmon*/temp1_input 2>/dev/null | head -n 1)

if [ -f "$gpu_temp_path" ]; then
  raw_gpu_temp=$(cat "$gpu_temp_path")
  gpu_temp=$((raw_gpu_temp / 1000))
else
  gpu_temp=""
fi

output=""

if [ -n "$cpu_temp" ]; then
  output+="CPU: $cpu_temp°C"
fi

if [ -n "$gpu_temp" ]; then
  if [ -n "$output" ]; then
    output+=" "
  fi
  output+="GPU: ${gpu_temp}°C"
fi

if [ -n "$output" ]; then
  echo "[ $output ]"
else
  echo "[]"
fi
