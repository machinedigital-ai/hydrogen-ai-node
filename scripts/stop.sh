#!/data/data/com.termux/files/usr/bin/bash
set -eu
PID_FILE="$HOME/.hydrogen-ai-node/llama.pid"
if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE")"
  CMDLINE="$(tr '\0' ' ' <"/proc/$PID/cmdline" 2>/dev/null || true)"
  if kill -0 "$PID" 2>/dev/null; then
    case "$CMDLINE" in
      *llama-server*)
        kill "$PID"
        echo "Stopped llama-server ($PID)."
        ;;
      *)
        echo "Refusing to stop PID $PID: it is not a llama-server process." >&2
        exit 1
        ;;
    esac
  fi
  rm -f "$PID_FILE"
else
  echo "No managed llama-server PID was found."
fi
