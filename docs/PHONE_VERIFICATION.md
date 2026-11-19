# RED Hydrogen One verification

Prepared 2026-11-19 against `main` commit `af3c85aafb7f543321e1dee9d46cf93f98045f69`.
**Phone execution, installation, real inference, and sustained stability remain unverified.**
GitHub run [44190069246](https://github.com/machinedigital-ai/hydrogen-ai-node/actions/runs/44190069246)
finished successfully on November 17. Its Ubuntu/Python checks do not run Android,
compile llama.cpp, download a model, or exercise a phone. Google sign-in activity is
not installation or inference evidence.

## What the repository establishes

| Evidence | Established by inspection | Requires this phone |
| --- | --- | --- |
| `tests/test_node.py` | Validation, SQLite methods, search, task state, history ordering/clearing | Filesystem permissions, process restart survival |
| `tests/test_http.py` | HTTP workflow with a successful fake backend, media type rejection, unknown route | Actual llama.cpp responses and resource costs |
| `scripts/install.sh` | Termux package commands, unpinned llama.cpp clone/update, CMake build, default GGUF download | Package availability, compilation, complete model download |
| `scripts/start.sh` | Requests `127.0.0.1:8080` and `127.0.0.1:8090`, 4 threads, context 2048 | Successful launch, observed listeners, responsiveness |
| `hydrogen_node.py` / dashboard | Local SQLite, HTTP routes, local model URL, bundled browser assets | Browser compatibility, model quality, screen-off survival |
| New smoke harness tests | Orchestration, restart/error paths with a fake model, occupied-port refusal, cleanup, data isolation | All real inference and hardware claims |

The node uses the Python standard library. Its `LlamaClient` timeout is **180
seconds**. Chat requests allow up to 384 generated tokens and summaries 420.
Small prompts reduce load, but the smoke harness cannot override those caps
without changing the application. The harness HTTP timeout defaults to 210 seconds.

## Safety and scope

`scripts/smoke_test.py` is executable in Termux; invoke it with `python3` for
portability. `preflight` inspects prerequisites and creates a small evidence
directory. `run` starts real services and writes **only its own new database** at:

```text
$HOME/.hydrogen-ai-node/smoke/<UTC timestamp>-<random suffix>/smoke.db
```

It never opens the production `~/.hydrogen-ai-node/node.db`, invokes the
installer, downloads anything, changes radios/settings, clears user history, or
uses `stop.sh`/`pkill`. It refuses occupied ports rather than attaching to or
stopping an existing service. It stops only its own `Popen` children and retains
the database, responses, and logs. Ctrl+C/SIGTERM also trigger cleanup. Force
stopping Termux or powering off Android can bypass cleanup; never trust a stale
PID as proof of process ownership.

Both services are explicitly bound to `127.0.0.1`. Do not add `0.0.0.0`, LAN
binding, port forwarding, tunnels, or router rules. Localhost is not authentication
against other software on the phone. Use synthetic prompts during verification.
The harness removes proxy variables only from its child environments and sets a
loopback proxy bypass; it does not change your shell or saved configuration.

The script checks `/proc/net/tcp` and `tcp6` when readable. Android may hide
listener/process/sensor data; missing visibility is a warning and must not be
reported as proof of isolation or a zero reading.

## 1. Prepare while online

Use Termux from [its official F-Droid or GitHub sources](https://github.com/termux/termux-app#installation).
The repository targets ARM64 Android 8.1/API 27 or newer. Confirm the actual
firmware and app version rather than assuming stock specifications. Keep the
project, binary, and model under Termux home, not shared `/sdcard` storage.

Bootstrap Python and clone the private repository with your configured GitHub
credentials. Never place a token in a URL, command log, screenshot, or this report.
If Git credentials are not configured, download the branch ZIP while signed in
and extract it into Termux home instead.

```sh
pkg update
pkg install -y python git curl
cd "$HOME"
git clone https://github.com/machinedigital-ai/hydrogen-ai-node.git
cd "$HOME/hydrogen-ai-node"
```

For an existing checkout, enter it instead of cloning again. Fetch and select the
smoke-test branch named in the accompanying pull request before using these files.
Do not discard local edits to switch branches.

```sh
git status --short
git fetch origin codex/hydrogen-phone-smoke-test
git switch --track origin/codex/hydrogen-phone-smoke-test
git rev-parse HEAD
getprop ro.product.manufacturer
getprop ro.product.model
getprop ro.build.version.release
getprop ro.build.version.sdk
getprop ro.product.cpu.abilist
uname -m
python3 --version
df -h "$HOME"
command -v termux-info >/dev/null && termux-info
python3 scripts/smoke_test.py preflight
```

If the branch already exists locally, use `git switch codex/hydrogen-phone-smoke-test`
instead of `git switch --track`. Stop and preserve changes if Git reports conflicts.

Expected: the model/phone identity matches the RED device, API >=27, `aarch64`,
working Python >=3.9, and sufficient storage. The README budgets approximately
4 GB free **before** source/build/model installation. Missing compiler/model
checks before installation are expected failures, not a hardware incompatibility
finding. Save the printed evidence directory and Termux version output.

If the binary/model are absent, plug in the phone, keep it ventilated, and run
the existing installer while online. This command installs packages, updates
llama.cpp, builds it, and downloads a model; **the smoke script does none of this**.
Skip it when the installed artifacts are already usable, because rerunning it
updates an unpinned dependency.

```sh
set -o pipefail
bash scripts/install.sh 2>&1 | tee "$HOME/hydrogen-install-$(date -u +%Y%m%dT%H%M%SZ).log"
```

Expected: exit 0 and `Installation complete`. A healthy executable and a complete
model still need the following checks; an installer message alone is insufficient.

```sh
"$HOME/llama.cpp/build/bin/llama-server" --version
git -C "$HOME/llama.cpp" rev-parse HEAD
ls -lh "$HOME/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
python3 scripts/smoke_test.py preflight --expected-sha256 6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e
```

The digest above was read from [Qwen's exact GGUF file metadata](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/blob/main/qwen2.5-1.5b-instruct-q4_k_m.gguf)
on November 19, 2026. Compare against that publisher page while online if it has
changed. Use the SHA256 value, not the Xet hash. File size is approximately 1.1 GB;
size and a `GGUF` header alone cannot establish integrity. The command hashes the
local file and fails on a digest mismatch. It makes no network request.

Expected after installation: executable version exits 0, GGUF and SHA256 checks
pass, runtime files exist, and ports are free. `installation_ready` in
`report.json` records whether all listed installer tools and artifacts were found.
The harness does not attempt a full compiler build during preflight.

Optional instrumentation: install the **Termux:API companion Android app from the
same source as Termux**, then its command package. The command package alone is
insufficient. Do this before going offline.

```sh
pkg install -y termux-api
timeout 5 termux-battery-status
```

Expected: JSON including percentage, charging status, and battery temperature when
supported. If it times out or is denied, proceed with manual Android battery
readings and mark automated sensor evidence unavailable. No root is needed.

## 2. Clear the test ports without disrupting other work

The harness requires **8080 and 8090 free**. If the production node is running,
finish any request, press Ctrl+C in its dashboard terminal, then stop the model
from that same known installation:

```sh
bash scripts/stop.sh
```

Only use that command when you know the PID file belongs to the current model.
The existing stop script trusts a PID file and does not check command identity.
For unknown processes or a stale PID file, inspect Termux sessions and stop the
correct foreground process yourself. Do not use `killall` or blindly kill a PID.
Rerun `preflight`; occupied-port failure is intentional and leaves that service alone.

## 3. Run the installed-stack test offline

Let the phone cool after compilation. Record initial battery percentage,
temperature (if available), charger state, screen brightness, case, and room
conditions. For a battery comparison use an unplugged phone with enough charge
for the test; charging makes drain and heat readings difficult to interpret.

On Android enable airplane mode, then explicitly disable Wi-Fi and mobile data.
Airplane mode can leave Wi-Fi enabled. Capture Quick Settings and device identity
(omit serial/IMEI/account information). Keep those states unchanged for this run.
The `--offline-confirmed` flag records **your attestation**, not independent radio
verification. The harness uses only literal loopback HTTP, but that alone cannot
prove every radio or third-party process is offline.

```sh
cd "$HOME/hydrogen-ai-node"
python3 scripts/smoke_test.py run --offline-confirmed --expected-sha256 6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e --observe-seconds 300
```

Expected: progressive `[PASS]` results and a printed evidence directory. Allow
several minutes for cold loading and generation. The default model load timeout is
300 seconds; each node inference has its own 180-second application limit. The
script waits five minutes at the end for browser inspection, then stops its own
two services. Start a screen recording before running if practical.

| Stage | Expected result | Evidence |
| --- | --- | --- |
| Cold model load | Child remains alive; `/health` becomes HTTP 200 | `llama.log`, exact argv/PID in `report.json` |
| Direct model call | HTTP 200 and nonempty generated text, 32-token cap | `responses.direct_model`, elapsed wall time |
| Dashboard | `/` HTTP 200; status says node/model online | `dashboard.log`, status response |
| Loopback | Observed listeners only at `127.0.0.1:8080/8090`; no wildcard | Listener evidence in report, subject to Android visibility |
| Chat | HTTP 200, nonempty answer to two plus two | Response and latency; manually confirm answer is four |
| Summary | HTTP 200, nonempty response | Manually confirm Tuesday, six people, $120, no selected venue; no invented details |
| Restart persistence | Exact note/history retained, task still complete, SQLite quick_check `ok` | Before/after responses and retained `smoke.db` |
| Invalid requests | Malformed JSON/media type/blank chat: 400; unknown route: 404 | Error responses; the node stays available |
| Model outage | Model offline; chat and summary return JSON 503; notes remain readable | Stopped-model responses |
| Model recovery | Restarted real model loads; node chat works again | Second startup in `llama.log`, recovered response |
| Resources | Samples across baseline, loading, inference, restart and idle | `telemetry.jsonl`, resource summary; unavailable fields remain null |

The deliberate failed chat leaves one user message in the test DB because the
current application writes the prompt before calling the model. It should not
create an assistant reply on failure. This is recorded as existing behavior.

During the printed browser window open **http://127.0.0.1:8090** in this phone's
browser. Confirm Chat, Notes, Tasks, Tools, and System render without an internet
connection. Check the existing generated replies and completed task. In Tools,
paste the short workshop text above and summarize; search the timestamp marker
shown in Notes. Add only synthetic data to this isolated instance. Browser edits
after the automated restart checks do not invalidate their earlier comparison.
Capture results and visible radio state in the same recording when possible.

Optional direct observations in a second Termux session while the script is active:

```sh
curl --noproxy '*' --max-time 5 -i http://127.0.0.1:8080/health
curl --noproxy '*' --max-time 5 -i http://127.0.0.1:8090/api/status
command -v ss >/dev/null && ss -ltn
```

Health should be 200 outside the deliberate outage. Look for `127.0.0.1:8080`
and `127.0.0.1:8090`, never `0.0.0.0`, `*`, or `::` on those ports. If Android
blocks both `/proc/net` and `ss`, record the restriction: requested localhost
binding is visible in argv, while actual listener verification remains incomplete.
Do not enable LAN access to work around it.

## 4. Record memory, battery, and temperature honestly

The sampler records system MemAvailable/SwapFree, per-process VmRSS/VmHWM/VmSwap,
readable battery sysfs values, Termux:API battery JSON, and raw thermal zones.
It deliberately avoids guessing the units of vendor thermal readings. RSS includes
shared/mapped pages and is not proportional memory; summing it can double-count.
Ten-second sampling may miss peaks. The direct model response may include server
timings; node endpoints expose only end-to-end wall time, not a reliable tokens/s
measurement. Keep raw evidence rather than inventing throughput.

For a somewhat longer observation, let the phone cool, keep the same conditions,
and run:

```sh
python3 scripts/smoke_test.py run --offline-confirmed --repeat 3 --observe-seconds 600
```

This sends three short node chats plus the direct call, summary, and recovery
call, followed by **ten minutes idle**. It is not ten minutes of continuous model
load. Compare loading/inference samples with idle and repeat separately if a
steady-load characterization is needed. Do not infer hours of battery life from
this run or treat a short pass as sustained stability.

Record start/end battery percentage and elapsed minutes, charger state, maximum
known battery temperature, lowest MemAvailable, peak sampled model/dashboard RSS,
generation latencies, crashes, and any visible slowing. A small or zero percentage
change is inconclusive because battery percentages are coarse. Temperature from
the battery is not CPU die temperature. Missing sensors stay unavailable.

Stop with Ctrl+C if Android warns about heat, the phone becomes uncomfortable, or
responses degrade sharply. The script also stops when a readable Termux battery
temperature reaches 45 C, a conservative test bound rather than a validated RED
hardware limit. It checks this between/blocking operations; it cannot guarantee
an immediate stop during a model call. With no sensor access the operator must
watch the device. Never disable thermal protection.

For background behavior, repeat the smoke run with a 300-second browser window,
lock the screen for roughly two minutes during that window, unlock and reload the
dashboard, then let the run finish. Capture whether services survived. Test first
with normal settings; if necessary repeat after explicitly exempting Termux from
battery optimization and document that setting. A wake lock changes the conditions
and does not guarantee Android will preserve the process.

## 5. Separately verify the normal startup script

The automated harness launches the same installed binary and dashboard with an
isolated DB. It does **not** execute `start.sh`, so its success cannot certify the
production launcher. After the harness exits and while still offline:

```sh
cd "$HOME/hydrogen-ai-node"
bash scripts/start.sh
```

Expected: model loads within the launcher's approximately 90 polling attempts
(wall time can be longer due to health request timeouts), dashboard URL prints,
browser loads. In a second session:

```sh
curl --noproxy '*' --max-time 5 http://127.0.0.1:8090/api/status
```

Expected: `node: online`, `model: online`. Refresh the browser offline. This normal
launch opens/initializes the real DB; do not clear history or submit synthetic
prompts here unless you want them saved. Record a separate result for the launcher.
To stop, Ctrl+C in its terminal, then `bash scripts/stop.sh` only while its current
model PID ownership is known. The smoke evidence DB remains available for inspection.

## Troubleshooting

| Symptom | Likely cause / precise next step |
| --- | --- |
| `python3`/`pkg` missing | Use the official Termux app, not an Android shell or shared-storage executable. Bootstrap with `pkg install -y python git curl` while online. |
| Package mirror/SSL errors | Check phone date/time, internet and free space; use `termux-change-repo` to choose a working official mirror, then `pkg update`. Do not bypass TLS validation. |
| GitHub 401/404 or password prompt | The repo is private. Configure your existing credential method or use a signed-in ZIP download. Do not publish the repo or paste credentials into logs. |
| No space / compiler killed / signal 9 | Inspect `df -h "$HOME"` and `/proc/meminfo` if readable. Close other apps, cool the device, and build only the needed target with one job using the commands below. Signal 9 alone does not prove OOM. |
| Missing `llama-server` target/path | Installer follows unpinned upstream. Inspect the recorded llama commit, CMake target list, and upstream docs. An upstream rename or changed dependency is an installation failure; do not substitute an unrelated binary and claim pass. |
| `CANNOT LINK EXECUTABLE` or missing libraries | Run the binary inside Termux; use a build made there for this ABI. Preserve stderr/version and rebuild in a separate directory. NDK/system binaries and Termux packages have different linking assumptions. |
| `Illegal instruction` | Binary may target newer ARM instructions. Rebuild on this phone with the conservative CPU flags below; do not copy a modern-phone binary or add armv8.2/fp16/dotprod flags blindly. |
| GGUF magic or hash fails / unexpected EOF | Preserve the suspect file and partial download. Redownload to a different name, verify SHA256, then use `--model` to test that file. The installer skips any existing nonempty model, including a corrupt one. |
| Health remains 503/loading | Read the evidence `llama.log`; check model size/hash, context allocation, available memory, and child exit. Try a cool phone with fewer threads/context and a longer load timeout. |
| Direct generation succeeds, node call 503/times out | Node timeout is fixed at 180 seconds. Keep prompts short; reduce resource pressure. Raising only the harness timeout cannot raise the node timeout. Preserve both response and model log. |
| Dashboard fails to bind | A listener already owns 8090. Find its Termux session; leave it alone until ownership is clear. The harness refuses both occupied ports by design. |
| Empty/gibberish response or wrong summary | Record exact text, model hash, build, and template-related model log lines. HTTP 200 is transport success, not answer correctness. Mark semantic verification failed. |
| SQLite locked/readonly | Keep test data under Termux home with free disk space. Do not run concurrent tests against one DB. Do not delete `node.db`, WAL, or SHM to repair a lock. New smoke runs always use a fresh DB. |
| Browser blank, tabs/buttons fail | Record Android/browser versions and a screenshot. Try an up-to-date compatible browser. The current UI uses modern DOM/JS APIs; HTTP availability alone cannot prove UI compatibility on an old browser. |
| Sensor permission denied or API hangs | Verify matching-source Termux:API app plus package. Use the 5-second timeout command. Record manual readings and leave unavailable fields null; no root workaround is required. |
| Works foreground, dies screen-off | Record timing and settings, then repeat with Termux battery optimization exemption if desired. Distinguish Android lifecycle termination from inference failure. |

Lower-memory rebuild without deleting the existing build:

```sh
cmake -S "$HOME/llama.cpp" -B "$HOME/llama.cpp/build-smoke" -G Ninja -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF -DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8-a -DGGML_OPENMP=OFF -DGGML_LLAMAFILE=OFF
cmake --build "$HOME/llama.cpp/build-smoke" --target llama-server -j 1
"$HOME/llama.cpp/build-smoke/bin/llama-server" --version
python3 scripts/smoke_test.py run --offline-confirmed --llama-server "$HOME/llama.cpp/build-smoke/bin/llama-server" --threads 2 --context 1024 --load-timeout 600
```

Build while online if dependencies are needed; then disable radios again before
the final command. These flags are a fallback to investigate, not a demonstrated
Hydrogen One fix. Upstream option compatibility must be checked against the
recorded revision. `start.sh` will still use `build/bin/llama-server` and context
2048; success with these overrides does not validate its default configuration.
Stop if configure or build fails; do not run a stale binary. Keep both command
outputs with the original installer log. Add `--expected-sha256` from the verified
model metadata to the fallback smoke command as in the main procedure.

Preserve a bad/partial model and download a separate candidate while online:

```sh
mkdir -p "$HOME/models"
hydrogen_model_dir=$(mktemp -d "$HOME/models/verify-XXXXXX")
curl -L --fail --retry 3 -o "$hydrogen_model_dir/qwen.gguf.download" https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf
printf '%s  %s\n' '6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e' "$hydrogen_model_dir/qwen.gguf.download" | sha256sum -c - && mv "$hydrogen_model_dir/qwen.gguf.download" "$hydrogen_model_dir/qwen.gguf"
```

Expected: checksum `OK` before rename. Stop on curl or checksum failure; preserve
the candidate for diagnosis. After verifying the publisher digest, disable radios
and run the harness with `--model "$hydrogen_model_dir/qwen.gguf"` and the same
`--expected-sha256`. If using a new Termux session, first set `hydrogen_model_dir`
to that exact candidate directory. No original model is removed or replaced.

## Evidence and acceptance record

Each evidence directory contains `report.json`, `telemetry.jsonl`, `llama.log`,
`dashboard.log`, and (after the stack starts) `smoke.db` with its WAL/SHM if present.
Keep the whole directory together; do not copy a live SQLite file alone. After
the script exits, inspect its printed report path. It includes exact commands,
source hashes, Git revisions, responses, elapsed times, sensor visibility, and
process exits. Exit 0 means automated checks completed; exit 1 means failure or
incomplete execution; argument errors return 2. Warnings still require review.

`hardware_verified` intentionally remains **false** in every generated report,
including a successful phone run. Keep a separate reviewed acceptance record:

```text
Device model / Android / Termux / browser:
Node commit and source hashes / llama.cpp commit / model SHA256:
Evidence directory / UTC start-end:
Airplane mode / Wi-Fi off / mobile data off evidence:
Default configuration or overrides:
Install: PASS / FAIL / NOT RUN
Model load and real generation: PASS / FAIL / NOT RUN
Offline chat and factual summary: PASS / FAIL / NOT RUN
SQLite restart persistence and outage recovery: PASS / FAIL / NOT RUN
Browser UI and normal start.sh: PASS / FAIL / NOT RUN
Observed localhost listeners: PASS / FAIL / UNAVAILABLE
Memory min available / peak sampled RSS / sensor limitations:
Battery start-end and minutes / charger state:
Temperature source, initial-max / heat or latency changes:
Screen-off survival and duration / battery optimization setting:
Reviewer / review date / unresolved items:
```

Call it a **verified phone smoke pass** only after the device identity, offline
evidence, real answers, restart/error results, UI, default launcher, and listener
observations have been reviewed. If listener visibility or sensors are unavailable,
say exactly which evidence is missing. A finite smoke pass still does not prove
all-day reliability, privacy against other apps, or production readiness.

## Upstream references

- [Termux installation and plugin compatibility](https://github.com/termux/termux-app#installation): official sources and matching signatures for companion apps.
- [Termux:API](https://github.com/termux/termux-api): companion-app requirements.
- [llama.cpp Android instructions](https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md): Termux builds, private-home model location, and context-related memory pressure.
- [llama.cpp build options](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md): check against the exact installed revision.
- [Qwen model file metadata](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/blob/main/qwen2.5-1.5b-instruct-q4_k_m.gguf): model identity, size, and SHA256.

## Development validation only

```sh
python3 -m py_compile hydrogen_node.py scripts/smoke_test.py
python3 -m unittest discover -s tests -v
```

The new tests launch the real Python dashboard with a **fake model backend** on
temporary loopback ports and a temporary home. They exercise restarts, 503/recovery,
occupied-port refusal, child cleanup, retained evidence, sensor restrictions, and
preservation of a production-DB sentinel. `--development-only` bypasses the Android
gate for harness debugging; it cannot validate the RED device or offline inference.
