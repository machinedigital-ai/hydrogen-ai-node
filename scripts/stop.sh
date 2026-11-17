#!/data/data/com.termux/files/usr/bin/bash
set -eu
PID_FILE="$HOME/.hydrogen-ai-node/llama.pid"
if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "Stopped llama-server ($PID)."
  fi
  rm -f "$PID_FILE"
else
  echo "No managed llama-server PID was found."
fi
