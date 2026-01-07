#!/bin/bash

# Get CPU usage from /proc/stat
read cpu a b c d rest </proc/stat
prev_idle=$d
prev_total=$((a + b + c + d))

sleep 0.5

read cpu a b c d rest </proc/stat
idle=$d
total=$((a + b + c + d))

cpu_usage=$((100 * ((total - prev_total) - (idle - prev_idle)) / (total - prev_total)))

# Get RAM usage using `free`
mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
mem_available=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
mem_used=$((mem_total - mem_available))
mem_usage=$((100 * mem_used / mem_total))

echo "[ CPU: ${cpu_usage}% RAM: ${mem_usage}% ]"
