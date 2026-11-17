#!/data/data/com.termux/files/usr/bin/bash
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
RUNTIME="$HOME/.hydrogen-ai-node"
LLAMA_SERVER="$HOME/llama.cpp/build/bin/llama-server"
MODEL="$HOME/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
mkdir -p "$RUNTIME"

if [ ! -x "$LLAMA_SERVER" ] || [ ! -s "$MODEL" ]; then
  echo "Model or llama-server missing. Run: bash scripts/install.sh" >&2
  exit 1
fi

if ! curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
  nohup "$LLAMA_SERVER" -m "$MODEL" --host 127.0.0.1 --port 8080 -t 4 -c 2048 >"$RUNTIME/llama.log" 2>&1 &
  echo "$!" >"$RUNTIME/llama.pid"
fi

python3 - <<'PY'
import sys
import time
import urllib.request
for _ in range(90):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2) as response:
            if response.status == 200:
                sys.exit(0)
    except Exception:
        time.sleep(1)
raise SystemExit("Model did not become ready. Check ~/.hydrogen-ai-node/llama.log")
PY

echo "Open http://127.0.0.1:8090 in this phone's browser."
cd "$ROOT"
exec python3 hydrogen_node.py --host 127.0.0.1 --port 8090 --llama-url http://127.0.0.1:8080 --db "$RUNTIME/node.db"
