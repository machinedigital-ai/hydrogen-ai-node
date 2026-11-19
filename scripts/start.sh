#!/data/data/com.termux/files/usr/bin/bash
set -eu
umask 077
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
RUNTIME="$HOME/.hydrogen-ai-node"
LLAMA_SERVER="$RUNTIME/llama.cpp/build/bin/llama-server"
MODEL="$RUNTIME/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
KEY_FILE="$RUNTIME/llama-api-key"
mkdir -p "$RUNTIME"
if [ ! -x "$LLAMA_SERVER" ] || [ ! -s "$MODEL" ]; then
  echo "Model or llama-server missing. Run: bash scripts/install.sh" >&2
  exit 1
fi
python3 -c "import secrets,sys; from pathlib import Path; p=Path(sys.argv[1]); key=p.read_text().strip() if p.exists() else \"\"; key=key or secrets.token_hex(32); assert len(key.splitlines()) == 1; p.write_text(key+\"\\n\"); p.chmod(0o600)" "$KEY_FILE"
if ! curl -fsS -H "Authorization: Bearer $(cat "$KEY_FILE")" http://127.0.0.1:8080/health >/dev/null 2>&1; then
  nohup "$LLAMA_SERVER" -m "$MODEL" --host 127.0.0.1 --port 8080 --api-key-file "$KEY_FILE" -t 4 -c 2048 >"$RUNTIME/llama.log" 2>&1 &
  echo "$!" >"$RUNTIME/llama.pid"
fi
python3 - "$KEY_FILE" <<PY
import sys
import time
import urllib.request
from pathlib import Path
key = Path(sys.argv[1]).read_text().strip()
for _ in range(90):
    try:
        request = urllib.request.Request(
            "http://127.0.0.1:8080/health",
            headers={"Authorization": "Bearer " + key},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            if response.status == 200:
                sys.exit(0)
    except Exception:
        time.sleep(1)
raise SystemExit("Model did not become ready. Check ~/.hydrogen-ai-node/llama.log")
PY
echo "Open http://127.0.0.1:8090 in the phone browser."
cd "$ROOT"
exec python3 hydrogen_node.py --host 127.0.0.1 --port 8090 --llama-url http://127.0.0.1:8080 --llama-key-file "$KEY_FILE" --db "$RUNTIME/node.db"
