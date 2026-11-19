# Hydrogen AI Node

An offline-first AI appliance for the RED Hydrogen One and other Android devices capable of running Termux. It treats the phone like a small Raspberry Pi: a local server, persistent storage, a browser dashboard, and an API for future hardware integrations.

**No root, bootloader unlock, or custom ROM is required.**

## Version 0.1 features

- Offline chat through a locally running llama.cpp server
- Qwen2.5 1.5B Q4_K_M as the initial small-model default
- Offline text-file summarization
- Persistent notes and tasks in SQLite
- Search across notes and tasks
- Device, storage, memory, and model status
- Mobile browser dashboard with no external assets or CDN
- Local HTTP API
- Python standard library only for the node itself

The model generates chat and summaries. Notes, tasks, search, and status are deterministic tools and do not depend on model tool-calling accuracy.

## Architecture

    Android browser
          |
          | http://127.0.0.1:8090
          v
    Hydrogen AI Node (Python)
          |-- SQLite: notes, tasks, chat history
          |-- Dashboard and local API
          |
          | http://127.0.0.1:8080/v1/chat/completions
          v
    llama-server (llama.cpp)
          |
          v
    Local GGUF model

## Requirements

- RED Hydrogen One or another ARM64 Android device
- Android 8.1 or newer is the initial target
- Termux from the official F-Droid or GitHub source
- Approximately 4 GB free storage for the model, source, build files, and temporary data
- Internet during installation only
- Charger connected during compilation and long inference sessions

Do not use an old, unmaintained Termux package. Keep the stock Android firmware for this version.

## Install on the phone

1. Install Termux from its official project source.
2. Clone this repository. Because it is currently private, authenticate with GitHub CLI or download a ZIP while signed in.
3. In Termux, enter the project directory and run:

~~~sh
bash scripts/install.sh
~~~

The installer builds a pinned llama.cpp revision in **$HOME/.hydrogen-ai-node/llama.cpp** and downloads the default model to **$HOME/.hydrogen-ai-node/models/**. It does not use or modify an existing **$HOME/llama.cpp** checkout. Compilation and the 1.1 GB model download can take a while. Every downloaded or pre-existing model must pass SHA-256 verification before installation succeeds.

## Start and stop

~~~sh
bash scripts/start.sh
~~~

Leave Termux open and visit **http://127.0.0.1:8090** in the phone browser.

To stop the managed model server:

~~~sh
bash scripts/stop.sh
~~~

The Python dashboard stops with Ctrl+C in its terminal. Android battery optimization may terminate background work; disable optimization for Termux if you deliberately want a persistent node.

## Local API

- GET /api/status
- GET, POST /api/notes
- DELETE /api/notes/ID
- GET, POST /api/tasks
- PATCH, DELETE /api/tasks/ID
- GET, POST, DELETE /api/chat
- POST /api/summarize
- GET /api/search?q=TEXT

POST and PATCH bodies use JSON. Example:

~~~sh
curl http://127.0.0.1:8090/api/status
~~~

## Data and security

The default database is at **$HOME/.hydrogen-ai-node/node.db**. Model output and node logs remain in the Termux home directory. Both services bind to **127.0.0.1**, so other devices cannot connect by default.

Do not expose port 8090 directly to the public internet. The dashboard has no authentication and neither service uses TLS. The start script generates a private random API key for the model server and stores it with owner-only permissions. LAN access, authentication, and backups should be designed before changing the bind address. When the node is bound to loopback, it rejects non-local Host headers as a DNS-rebinding safeguard. The model client accepts only plain HTTP on loopback. There is intentionally no arbitrary shell-command endpoint.

## Raspberry Pi–style roadmap

1. Authentication and explicit LAN mode
2. Local document import and retrieval search
3. Voice input/output using Android and Termux APIs
4. Camera capture with user approval
5. Scheduled jobs and explicit local automation rules
6. USB serial integration with an ESP32 or Arduino for sensors and relays
7. MQTT client for local home automation
8. Optional native Android launcher and foreground service

USB serial accessories are the recommended GPIO path. The Hydrogen One does not expose Raspberry Pi-compatible GPIO pins.

## Model expectations

A 1.5B model is useful for basic chat, rewriting, and short summaries, but it is not as capable as a modern cloud model. Larger models require more memory and will be slow on the Snapdragon 835. Expect heat and verify important answers.

The server starts with a 2,048-token context. Chat messages are limited to 3,000 characters and retained history is bounded to a 4,000-character prompt budget. Summaries accept up to 18,000 characters and process longer documents in roughly 3,000-character chunks before combining the partial summaries. A long summary requires several sequential model calls and can take minutes. These limits reduce memory pressure; they do not guarantee that Android will never terminate a busy process.

See [Evidence and safe investigation workflows](docs/EVIDENCE.md) for phone-inference sources, realistic OSINT-adjacent uses, and verification rules. See [Verification](docs/VERIFICATION.md) for the exact tested revisions, hashes, checks, and remaining device-specific unknowns.

## Development checks

~~~sh
python -m py_compile hydrogen_node.py
python -m unittest discover -s tests -v
~~~

Additional audit checks used in development are Ruff, Bandit, shell syntax validation, dashboard JavaScript parsing, and a real llama-server inference smoke test. Cloud tests do not replace an on-device test with the model server running. Model output is not evidence; verify important claims against original sources.
