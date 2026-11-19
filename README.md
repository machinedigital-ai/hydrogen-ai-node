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

The installer builds llama.cpp and downloads the default model. Compilation and the model download can take a while.

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

Do not expose port 8090 directly to the public internet. This first version has no authentication or TLS. LAN access, authentication, and backups should be designed before changing the bind address. There is intentionally no arbitrary shell-command endpoint.

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

A 1.5B model is useful for basic chat, rewriting, and short summaries, but it is not as capable as a modern cloud model. Larger models require more memory and will be slow on the Snapdragon 835. Keep context small, expect heat, and verify important answers.

## Development checks

~~~sh
python -m py_compile hydrogen_node.py
python -m unittest discover -s tests -v
~~~

The automated tests validate storage and input handling; actual inference must be tested on the phone with the model server running.

## Phone verification

Use the [RED Hydrogen One verification procedure](docs/PHONE_VERIFICATION.md) for
installation checks, an isolated installed-stack smoke test, offline/browser
evidence, resource observations, and troubleshooting. It distinguishes repository
checks from results that require the physical phone.

~~~sh
python3 scripts/smoke_test.py preflight
# After installation, with airplane mode enabled and Wi-Fi/mobile data disabled:
python3 scripts/smoke_test.py run --offline-confirmed
~~~

The test refuses occupied ports, binds both services to localhost, creates a fresh
test database, and stops only processes it starts. It preserves evidence without
touching existing notes or chat. A passing automated run still requires the manual
checks in the procedure; physical RED Hydrogen One inference remains unverified
until that evidence is reviewed.
