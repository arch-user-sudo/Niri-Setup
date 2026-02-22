#!/bin/sh

# Your update functions here (unchanged)
# --------------------------------------

update_ram() {
    USED_RAM=$(free -h | awk '/Mem:/ {print $3}')
    STATUS_RAM=" ${USED_RAM}"
}

update_cpu() {
    CPU_IDLE=$(vmstat 1 2 | tail -1 | awk '{print $15}')
    CPU_USAGE=$((100 - CPU_IDLE))
    STATUS_CPU=" ${CPU_USAGE}%"
}

update_disk() {
    FREE_SPACE=$(df -h / | awk 'NR==2 {print $4}')
    STATUS_DISK=" ${FREE_SPACE} Free"
}

update_gpu() {
    GPU_DATA=$(radeontop -d - -l 1 2>/dev/null | grep -oP 'gpu\s+\K\d+\.\d+')
    GPU_LOAD_INT=$(printf "%.0f\n" ${GPU_DATA})
    STATUS_GPU="󰍹 ${GPU_LOAD_INT}%"
}

WEATHER_UPDATE_FREQ=1800
WEATHER_LAST_UPDATE=0

update_weather() {
    CURRENT=$(date +%s)
    if [ $((CURRENT - WEATHER_LAST_UPDATE)) -gt $WEATHER_UPDATE_FREQ ]; then
        WEATHER=$(curl -s "wttr.in/Kimberley?format=%t+%C" | tr -d '\n')
        STATUS_WEATHER="󰖐 ${WEATHER}"
        WEATHER_LAST_UPDATE=$CURRENT
    fi
}

update_time() {
    STATUS_TIME=" $(date '+%a %d %b %H:%M%p')"
}

# Start loop
while true; do
    update_ram
    update_cpu
    update_disk
    update_gpu
    update_weather
    update_time

    xsetroot -name "| ${STATUS_RAM} | ${STATUS_CPU} | ${STATUS_GPU} | ${STATUS_DISK} | ${STATUS_WEATHER} | ${STATUS_TIME}"

    sleep 5
done
