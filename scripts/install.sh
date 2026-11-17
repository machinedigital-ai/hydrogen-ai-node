#!/data/data/com.termux/files/usr/bin/bash
set -eu

if ! command -v pkg >/dev/null 2>&1; then
  echo "Run this installer inside Termux on Android." >&2
  exit 1
fi

pkg update -y
pkg install -y python git clang cmake ninja curl

LLAMA_DIR="$HOME/llama.cpp"
if [ ! -d "$LLAMA_DIR/.git" ]; then
  git clone --depth 1 https://github.com/ggml-org/llama.cpp "$LLAMA_DIR"
else
  git -C "$LLAMA_DIR" pull --ff-only
fi

cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF
cmake --build "$LLAMA_DIR/build" --config Release -j 4

MODEL_DIR="$HOME/models"
MODEL_FILE="$MODEL_DIR/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
mkdir -p "$MODEL_DIR" "$HOME/.hydrogen-ai-node"
if [ ! -s "$MODEL_FILE" ]; then
  curl -L --fail --retry 3 -o "$MODEL_FILE.download" "$MODEL_URL"
  mv "$MODEL_FILE.download" "$MODEL_FILE"
fi

echo "Installation complete. Start the node with: bash scripts/start.sh"
