#!/bin/bash

# Detect active interface
get_interface() {
  ip route get 8.8.8.8 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="dev") print $(i+1)}'
}

interface=$(get_interface)

# Exit if interface is invalid
if [[ -z "$interface" || ! -e "/sys/class/net/$interface/statistics/rx_bytes" ]]; then
  echo "No network"
  exit 1
fi

# Continuous output loop
while true; do
  rx1=$(cat /sys/class/net/$interface/statistics/rx_bytes)
  tx1=$(cat /sys/class/net/$interface/statistics/tx_bytes)
  sleep 1
  rx2=$(cat /sys/class/net/$interface/statistics/rx_bytes)
  tx2=$(cat /sys/class/net/$interface/statistics/tx_bytes)

  rx_rate=$(( (rx2 - rx1) / 1024 ))
  tx_rate=$(( (tx2 - tx1) / 1024 ))

  echo "[ ↓ ${rx_rate} KiB/s ↑ ${tx_rate} KiB/s ]"
done
