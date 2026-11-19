#!/data/data/com.termux/files/usr/bin/bash
set -eu
if ! command -v pkg >/dev/null 2>&1; then
  echo "Run this installer inside Termux on Android." >&2
  exit 1
fi
pkg update -y
pkg install -y python git clang cmake ninja curl libandroid-spawn
RUNTIME="$HOME/.hydrogen-ai-node"
LLAMA_DIR="$RUNTIME/llama.cpp"
LLAMA_COMMIT="9a080f44b503c64f66c84a6274b9d9ee5d5b09d5"
mkdir -p "$LLAMA_DIR"
if [ ! -d "$LLAMA_DIR/.git" ]; then
  git -C "$LLAMA_DIR" init
  git -C "$LLAMA_DIR" remote add origin https://github.com/ggml-org/llama.cpp
fi
git -C "$LLAMA_DIR" fetch --depth 1 origin "$LLAMA_COMMIT"
git -C "$LLAMA_DIR" checkout --detach FETCH_HEAD
cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF
cmake --build "$LLAMA_DIR/build" --config Release -j 2
MODEL_DIR="$RUNTIME/models"
MODEL_FILE="$MODEL_DIR/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_SHA256="6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
mkdir -p "$MODEL_DIR"
if [ -s "$MODEL_FILE" ] && printf "%s  %s\n" "$MODEL_SHA256" "$MODEL_FILE" | sha256sum -c -; then
  echo "Existing model passed SHA-256 verification."
else
  rm -f "$MODEL_FILE" "$MODEL_FILE.download"
  curl -L --fail --retry 3 -o "$MODEL_FILE.download" "$MODEL_URL"
  printf "%s  %s\n" "$MODEL_SHA256" "$MODEL_FILE.download" | sha256sum -c -
  mv "$MODEL_FILE.download" "$MODEL_FILE"
fi
echo "Installation complete. Start the node with: bash scripts/start.sh"
