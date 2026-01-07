#!/bin/bash

# Check if Bluetooth is powered off using rfkill
if rfkill list bluetooth | grep -q "Soft blocked: yes"; then
  echo ""
  exit 0
fi

# Get any battery device starting with battery_ps_controller_battery or battery_
device_path=$(upower -e | grep -E '^/org/freedesktop/UPower/devices/battery_')

if [ -n "$device_path" ]; then
  battery=$(upower -i "$device_path" | awk '/percentage:/ {print $2}')
  echo " $battery"
else
  echo ""
fi
