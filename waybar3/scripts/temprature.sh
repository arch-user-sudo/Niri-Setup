#!/bin/bash

cpu_temp=$(sensors | grep 'Package id 0:' | awk '{print $4}' | sed 's/+//' | sed 's/\..*//')
gpu_temp=$(sensors | grep 'amdgpu-pci-0100' -A 3 | grep 'edge:' | awk '{print $2}' | sed 's/+//' | sed 's/\..*//')

output=""

if  [ -n "$cpu_temp" ]; then
  output+="CPU: $cpu_temp°C"
fi

if [ -n "$gpu_temp" ]; then
  if [ -n "$output" ]; then
    output+=" "
  fi
  output+="GPU: $gpu_temp°C"
fi

if [ -n "$output" ]; then
  echo "[ $output ]"
else
  echo "[]"
fi
