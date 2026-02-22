SCRIPT="/home/lynch/BashScripts/newsub20226(gtk).py"
PIDFILE="/tmp/$(basename "$SCRIPT").pid"

if [ ! -f "$PIDFILE" ] || ! kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Starting $(basename "$SCRIPT")..."
  python3 "$SCRIPT" &
  echo $! >"$PIDFILE"
else
  PID=$(cat "$PIDFILE")
  echo "Stopping process $PID..."
  kill "$PID"
  rm "$PIDFILE"
fi
