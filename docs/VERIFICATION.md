# Verification and audit results

## Pinned supply-chain inputs

- llama.cpp commit: `9a080f44b503c64f66c84a6274b9d9ee5d5b09d5`
- Model: `qwen2.5-1.5b-instruct-q4_k_m.gguf`
- Model size: `1,117,320,736` bytes
- Model SHA-256: `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`
- Model source: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf

The installer verifies the model hash before moving a new download into place. A corrupt existing model is removed and downloaded again. llama.cpp and the model live under `$HOME/.hydrogen-ai-node/`; an existing `$HOME/llama.cpp` checkout is not used.

## Cloud build and integration results

The clean native build completed all **434/434** steps successfully with CMake Release, Ninja, two parallel jobs, `GGML_NATIVE=OFF`, and `LLAMA_CURL=OFF`. The downloaded model matched the expected SHA-256.

The end-to-end test used Linux x86_64 on Azure, Python 3.14.2, the compiled llama-server, the real GGUF model, and the actual Hydrogen node API:

- A direct model request without the API key returned HTTP 401.
- Authenticated chat returned HTTP 200 and a nonempty privacy answer in 3.453 seconds.
- Summarization returned HTTP 200 in 5.893 seconds and retained the meeting date, $12,000 amount, two resident concerns, and 30-day deletion term from the source text.
- An 18,001-character summary request returned HTTP 400.
- `Host: attacker.example` returned HTTP 403.
- The test processes were terminated afterward and the logs were inspected.

These timings demonstrate software integration only. They are **not** expected Hydrogen One timings.

## Static and regression checks

- Python byte-compilation passed.
- All 12 unit and HTTP regression tests passed.
- Ruff correctness checks passed.
- Bandit completed with no findings.
- All shell scripts passed `bash -n`.
- Dashboard JavaScript parsed successfully.
- `git diff --check` passed.
- The stop script rejected an unrelated process and stopped a managed test llama-server process.

The code review also confirmed parameterized SQLite queries, use of `textContent` rather than HTML injection in the dashboard, bounded request and prompt sizes, serialized model requests, loopback-only model URLs, localhost Host-header checks, and no arbitrary shell-command route.

## Remaining unverified items

No test has yet compiled or run this revision in Termux on the Hydrogen One. ARM64 compatibility, Snapdragon 835 inference speed, memory pressure, heat, battery drain, and Android background behavior remain unknown until measured on the device. This audit reduces risk but is not a guarantee of security, correctness, or hardware compatibility.

The dashboard has no authentication and neither service uses TLS, so both services must remain bound to loopback. The start script generates a random model API key, stores it with owner-only permissions, and passes it to authenticated health and inference requests. PDF/OCR, source-linked citations, voice, images, live collection, geolocation, and hardware control are not implemented.

## First on-device acceptance test

After installation, verify the exact inputs:

~~~sh
git -C "$HOME/.hydrogen-ai-node/llama.cpp" rev-parse HEAD
sha256sum "$HOME/.hydrogen-ai-node/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
~~~

The outputs must match the commit and SHA-256 above. Then run:

~~~sh
bash scripts/start.sh
~~~

Confirm that `http://127.0.0.1:8090/api/status` reports the model as online. Test one short chat, one short summary, notes, tasks, search, and history deletion. Keep the phone connected to power, watch memory and temperature, and test a sustained session before relying on it as a persistent node. If Android kills Termux, review battery optimization and reduce the context or thread count before trying a larger model.
