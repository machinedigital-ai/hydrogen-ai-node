#!/data/data/com.termux/files/usr/bin/python3
"""Opt-in, localhost-only installed-stack checks. Never uses the production DB.

Run with python3 for portability. See docs/PHONE_VERIFICATION.md before running.
No packages, models, settings, wake locks, or network interfaces are changed.
"""

import argparse
import hashlib
import http.client
import json
import os
import platform
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_NAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
PROMPT = "Reply in one short sentence: what is two plus two?"
DOCUMENT = (
    "The workshop is on Tuesday. Six people will attend. "
    "The budget is 120 dollars. No venue has been selected."
)


class CheckFailed(Exception):
    pass


def command(argv, timeout=10):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {"exit": result.returncode, "output": (result.stdout + result.stderr).strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"exit": None, "error": str(error)}


def read_text(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def mem_fields(path, names):
    raw = read_text(path)
    if raw is None:
        return None
    fields = {}
    for line in raw.splitlines():
        parts = line.split()
        if parts and parts[0].rstrip(":") in names:
            try:
                fields[parts[0].rstrip(":")] = int(parts[1]) * 1024
            except (ValueError, IndexError):
                pass
    return fields or None


def listeners(ports):
    """Read-only best effort. Android may forbid both proc and netlink access."""
    rows, readable = [], []
    for name, family in (("tcp", socket.AF_INET), ("tcp6", socket.AF_INET6)):
        raw = read_text("/proc/net/" + name)
        if raw is None:
            continue
        readable.append(name)
        for line in raw.splitlines()[1:]:
            fields = line.split()
            if len(fields) < 4 or fields[3] != "0A":
                continue
            address, port = fields[1].split(":")
            if int(port, 16) not in ports:
                continue
            packed = bytes.fromhex(address)
            packed = b"".join(packed[i:i + 4][::-1] for i in range(0, len(packed), 4))
            rows.append({"host": socket.inet_ntop(family, packed), "port": int(port, 16)})
    return {"readable_tables": readable, "listeners": rows}


class SmokeTest:
    def __init__(self, args):
        self.args = args
        parent = Path.home() / ".hydrogen-ai-node" / "smoke"
        parent.mkdir(parents=True, exist_ok=True)
        self.directory = parent / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
        self.directory.mkdir(mode=0o700)
        self.db = self.directory / "smoke.db"
        self.model = Path(args.model).expanduser().resolve()
        self.binary = Path(args.llama_server).expanduser().resolve()
        self.children = {}
        self.logs = []
        self.samples = []
        self.phase = "preflight"
        self.stopping = threading.Event()
        self.thermal_stop = threading.Event()
        self.sampler = None
        self.model_port, self.node_port = 8080, 8090
        self.report = {
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "mode": args.mode,
            "development_only": args.development_only,
            "offline_operator_attested": args.offline_confirmed,
            "hardware_verified": False,
            "completed": False,
            "checks": [],
            "commands": [],
            "manual_remaining": [
                "Verify RED Hydrogen One identity and radios off with screenshots/video.",
                "Check generated answers for correctness; nonempty text alone is insufficient.",
                "Exercise the browser UI and the production start.sh flow separately.",
                "Review listener evidence, missing telemetry, heat, and Android background survival.",
            ],
        }
        print("Evidence directory: " + str(self.directory), flush=True)

    def save(self):
        (self.directory / "report.json").write_text(json.dumps(self.report, indent=2) + "\n")

    def record(self, name, state, detail):
        self.report["checks"].append({"name": name, "state": state, "detail": detail})
        print("[" + state + "] " + name + ": " + str(detail), flush=True)
        self.save()

    def require(self, name, condition, detail):
        self.record(name, "PASS" if condition else "FAIL", detail)
        if not condition:
            raise CheckFailed(name)

    def preflight(self):
        props = {}
        for key in ("ro.product.manufacturer", "ro.product.model", "ro.build.version.release",
                    "ro.build.version.sdk", "ro.product.cpu.abilist"):
            props[key] = command(["getprop", key]).get("output") if shutil.which("getprop") else None
        self.report["device"] = {"properties": props, "machine": platform.machine(), "python": sys.version}
        sdk = props["ro.build.version.sdk"] or "0"
        target = shutil.which("pkg") is not None and sdk.isdigit() and int(sdk) >= 27 and platform.machine() == "aarch64"
        self.require("Android ARM64 Termux target", target or self.args.development_only,
                     "Android API >=27, aarch64, pkg required; development bypass=" + str(self.args.development_only))
        self.require("Python version", sys.version_info >= (3, 9), platform.python_version())
        tools = {name: shutil.which(name) for name in ("bash", "python3", "git", "clang", "cmake", "ninja", "curl")}
        self.report["prerequisites"] = tools
        missing = [name for name, path in tools.items() if path is None]
        self.record("Installer tools", "WARN" if missing else "PASS", "missing=" + str(missing))
        self.require("Repository files", all((ROOT / p).is_file() for p in
                     ("hydrogen_node.py", "static/index.html", "scripts/install.sh", "scripts/start.sh")), str(ROOT))
        self.report["repository"] = command(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
        self.report["working_tree"] = command(["git", "-C", str(ROOT), "status", "--porcelain"])
        self.report["source_sha256"] = {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in ("hydrogen_node.py", "static/index.html", "scripts/start.sh", "scripts/smoke_test.py")
        }
        disk = shutil.disk_usage(Path.home())
        self.report["free_storage_bytes"] = disk.free
        self.record("Installation space", "PASS" if disk.free >= 4 * 1024**3 else "WARN",
                    str(round(disk.free / 1024**3, 2)) + " GiB free; README planning allowance is about 4 GB before install")
        binary_ok = self.binary.is_file() and os.access(self.binary, os.X_OK)
        self.record("llama-server installed", "PASS" if binary_ok else "FAIL", str(self.binary))
        if binary_ok:
            version = command([str(self.binary), "--version"], timeout=30)
            self.report["llama_version"] = version
            self.record("llama-server executable", "PASS" if version["exit"] == 0 else "FAIL", version)
        self.report["llama_commit"] = command(["git", "-C", str(self.binary.parent.parent.parent), "rev-parse", "HEAD"])
        model_ok = False
        if self.model.is_file():
            with self.model.open("rb") as source:
                magic = source.read(4)
            self.report["model"] = {"path": str(self.model), "bytes": self.model.stat().st_size, "magic_hex": magic.hex()}
            model_ok = magic == b"GGUF"
            self.record("Model GGUF header", "PASS" if model_ok else "FAIL", self.report["model"])
            if self.args.hash_model or self.args.expected_sha256:
                digest = hashlib.sha256()
                with self.model.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                self.report["model"]["sha256"] = digest.hexdigest()
                if self.args.expected_sha256:
                    matches = digest.hexdigest() == self.args.expected_sha256.lower()
                    self.record("Model publisher SHA256", "PASS" if matches else "FAIL", digest.hexdigest())
                    model_ok = model_ok and matches
            if not self.args.expected_sha256:
                self.record("Model integrity scope", "WARN", "GGUF header/size are not an integrity check; compare SHA256 to the publisher before inference")
        else:
            self.record("Model installed", "FAIL", str(self.model) + " missing; no download performed")
        self.report["memory_before"] = mem_fields("/proc/meminfo", {"MemTotal", "MemAvailable", "SwapFree"})
        for port in (self.model_port, self.node_port):
            with socket.socket() as probe:
                try:
                    probe.bind(("127.0.0.1", port))
                    free = True
                except OSError:
                    free = False
            self.require("Port " + str(port) + " available", free, "Occupied ports are never reused or stopped")
        self.report["installation_ready"] = binary_ok and model_ok and not missing and self.report.get("llama_version", {}).get("exit") == 0
        if self.args.mode == "run":
            self.require("Installed runtime ready", binary_ok and model_ok and self.report.get("llama_version", {}).get("exit") == 0,
                         "Build/download first; model identity and integrity still require the publisher comparison")
            self.require("Runtime disk headroom", disk.free >= 256 * 1024**2, "At least 256 MiB free for test DB/logs; this is a guard, not a measured device requirement")

    def request(self, port, method, path, payload=None, raw=None, content_type="application/json", timeout=None):
        # http.client connects directly to literal loopback; HTTP_PROXY is never consulted.
        body = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout or self.args.request_timeout)
        started = time.monotonic()
        try:
            connection.request(method, path, body=body, headers={"Content-Type": content_type} if body is not None else {})
            response = connection.getresponse()
            data = response.read()
            kind = response.getheader("Content-Type", "")
            value = json.loads(data) if kind.startswith("application/json") else data.decode("utf-8", "replace")
            return {"status": response.status, "seconds": round(time.monotonic() - started, 3), "body": value}
        finally:
            connection.close()

    def api(self, label, method, path, payload=None, expected=200, **kwargs):
        self.check_temperature()
        result = self.request(self.node_port, method, path, payload, **kwargs)
        self.report.setdefault("responses", {})[label] = result
        self.require(label, result["status"] == expected, "HTTP " + str(result["status"]) + " in " + str(result["seconds"]) + "s")
        return result["body"]

    def start(self, name, argv, path, port):
        self.check_temperature()
        log = path.open("ab")
        self.logs.append(log)
        child_env = os.environ.copy()
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            child_env.pop(key, None)
        child_env["NO_PROXY"] = child_env["no_proxy"] = "127.0.0.1,localhost,::1"
        process = subprocess.Popen(argv, cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, env=child_env)
        self.children[name] = process
        self.report["commands"].append({"name": name, "pid": process.pid, "argv": argv, "log": str(path)})
        self.save()
        deadline = time.monotonic() + self.args.load_timeout
        while time.monotonic() < deadline:
            self.check_temperature()
            if process.poll() is not None:
                raise CheckFailed(name + " exited with " + str(process.returncode) + "; inspect " + str(path))
            try:
                result = self.request(port, "GET", "/health" if name == "llama" else "/", timeout=2)
                if result["status"] == 200:
                    self.require(name + " ready", process.poll() is None, str(path))
                    return
            except (OSError, ValueError, http.client.HTTPException):
                pass
            self.stopping.wait(1)
        raise CheckFailed(name + " readiness timeout; inspect " + str(path))

    def start_model(self):
        self.phase = "model_loading"
        self.start("llama", [str(self.binary), "-m", str(self.model), "--host", "127.0.0.1", "--port", str(self.model_port),
                            "-t", str(self.args.threads), "-c", str(self.args.context)], self.directory / "llama.log", self.model_port)

    def start_dashboard(self):
        self.start("dashboard", [sys.executable, str(ROOT / "hydrogen_node.py"), "--host", "127.0.0.1", "--port", str(self.node_port),
                                "--llama-url", "http://127.0.0.1:" + str(self.model_port), "--db", str(self.db)],
                   self.directory / "dashboard.log", self.node_port)

    def stop(self, name):
        process = self.children.get(name)
        if process is None:
            return
        if process.poll() is None:
            # Popen ownership, never a shared PID file, pkill, stop.sh, or an unrelated service.
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                self.record(name + " shutdown", "WARN", "Owned child needed SIGKILL; SQLite recovery is checked after restart")
        self.report.setdefault("process_exits", []).append({"name": name, "pid": process.pid, "exit": process.returncode})
        del self.children[name]

    def snapshot(self):
        battery = {key: read_text("/sys/class/power_supply/battery/" + key) for key in ("capacity", "temp", "status")}
        api = None
        if shutil.which("termux-battery-status"):
            response = command(["termux-battery-status"], timeout=3)
            if response["exit"] == 0:
                try:
                    api = json.loads(response["output"])
                except ValueError:
                    pass
        zones = {}
        for zone in Path("/sys/class/thermal").glob("thermal_zone*"):
            raw = read_text(zone / "temp")
            if raw is not None:
                zones[zone.name] = {"type": read_text(zone / "type"), "raw_temp": raw}
        sample = {
            "utc": datetime.now(timezone.utc).isoformat(), "monotonic": time.monotonic(), "phase": self.phase,
            "memory_bytes": mem_fields("/proc/meminfo", {"MemTotal", "MemAvailable", "SwapFree"}),
            "process_bytes": {name: mem_fields("/proc/" + str(p.pid) + "/status", {"VmRSS", "VmHWM", "VmSwap"})
                              for name, p in list(self.children.items()) if p.poll() is None},
            "battery_sysfs_raw": battery, "battery_termux_api": api, "thermal_sysfs_raw": zones,
        }
        self.samples.append(sample)
        with (self.directory / "telemetry.jsonl").open("a") as target:
            target.write(json.dumps(sample) + "\n")
        temperature = api.get("temperature") if isinstance(api, dict) else None
        if isinstance(temperature, (int, float)) and temperature >= 45:
            self.thermal_stop.set()

    def check_temperature(self):
        if self.thermal_stop.is_set():
            raise CheckFailed("Battery API reports >=45 C; conservative test stop, cool the phone before retrying")

    def sample_loop(self):
        while not self.stopping.wait(self.args.sample_seconds):
            try:
                self.snapshot()
            except Exception as error:
                # Record an instrumentation failure; do not make it look like zero heat/memory use.
                with (self.directory / "telemetry-errors.txt").open("a") as target:
                    target.write(repr(error) + "\n")

    def check_bindings(self):
        evidence = listeners({self.model_port, self.node_port})
        self.report["listener_evidence"] = evidence
        rows = evidence["listeners"]
        unsafe = [row for row in rows if row["host"] not in ("127.0.0.1", "::1")]
        self.require("No observed non-loopback listener", not unsafe, evidence)
        complete = len(evidence["readable_tables"]) == 2 and {row["port"] for row in rows} == {self.model_port, self.node_port}
        self.record("Listener visibility", "PASS" if complete else "WARN",
                    "Observed both tables/ports" if complete else "Android restricted or incomplete visibility; argv proves requested bind only, manual verification remains")

    def run_stack(self):
        self.phase = "baseline"
        self.snapshot()
        self.sampler = threading.Thread(target=self.sample_loop, daemon=True)
        self.sampler.start()
        self.start_model()
        self.phase = "direct_inference"
        result = self.request(self.model_port, "POST", "/v1/chat/completions", {
            "model": "local", "messages": [{"role": "user", "content": PROMPT}],
            "stream": False, "max_tokens": 32, "temperature": 0,
        })
        self.report.setdefault("responses", {})["direct_model"] = result
        content = result["body"].get("choices", [{}])[0].get("message", {}).get("content", "") if isinstance(result["body"], dict) else ""
        self.require("Real model API generated text", result["status"] == 200 and isinstance(content, str) and bool(content.strip()), result)
        self.start_dashboard()
        self.check_bindings()
        self.phase = "dashboard_api"
        status = self.api("Model visible to node", "GET", "/api/status")
        self.require("Model online", status.get("model") == "online", status)
        for label, kwargs in (
            ("Reject malformed JSON", {"raw": b"{", "expected": 400}),
            ("Reject wrong media type", {"raw": b"x", "content_type": "text/plain", "expected": 400}),
            ("Reject blank chat", {"payload": {"message": " "}, "expected": 400}),
        ):
            body = self.api(label, "POST", "/api/chat", **kwargs)
            self.require(label + " JSON error", isinstance(body, dict) and bool(body.get("error")), body)
        self.api("Unknown route", "GET", "/api/smoke-unknown", expected=404)
        marker = self.directory.name
        note = self.api("Create isolated note", "POST", "/api/notes", {"title": marker, "body": "Persistence probe only"}, expected=201)["note"]
        task = self.api("Create isolated task", "POST", "/api/tasks", {"title": marker}, expected=201)["task"]
        self.api("Set isolated task state", "PATCH", "/api/tasks/" + str(task["id"]), {"done": True})
        self.phase = "chat"
        for index in range(self.args.repeat):
            chat = self.api("Offline chat " + str(index + 1), "POST", "/api/chat", {"message": PROMPT})
            self.require("Chat nonempty " + str(index + 1), isinstance(chat.get("reply"), str) and bool(chat["reply"].strip()), chat)
        self.phase = "summarization"
        summary = self.api("Offline summary", "POST", "/api/summarize", {"text": DOCUMENT})
        self.require("Summary nonempty", isinstance(summary.get("summary"), str) and bool(summary["summary"].strip()), summary)
        before = self.api("History before restart", "GET", "/api/chat")["messages"]
        self.require("History contains generated pairs", len(before) == self.args.repeat * 2 and
                     all(row["role"] == ("user" if i % 2 == 0 else "assistant") for i, row in enumerate(before)), before)
        self.phase = "dashboard_restart"
        self.stop("dashboard")
        self.start_dashboard()
        notes = self.api("Notes after restart", "GET", "/api/notes")["notes"]
        tasks = self.api("Tasks after restart", "GET", "/api/tasks")["tasks"]
        after = self.api("History after restart", "GET", "/api/chat")["messages"]
        self.require("SQLite survives process restart", notes == [note] and len(tasks) == 1 and tasks[0]["id"] == task["id"]
                     and tasks[0]["done"] == 1 and after == before, "Exact note/history and completed task preserved in " + str(self.db))
        with sqlite3.connect(self.db.as_uri() + "?mode=ro", uri=True) as connection:
            integrity = connection.execute("PRAGMA quick_check").fetchall()
        self.require("SQLite quick_check", integrity == [("ok",)], integrity)
        self.phase = "model_unavailable"
        self.stop("llama")
        offline = self.api("Node survives model stop", "GET", "/api/status")
        self.require("Model reported offline", offline.get("model") == "offline", offline)
        for name, route, payload in (("Chat with model stopped", "/api/chat", {"message": "Short outage probe"}),
                                     ("Summary with model stopped", "/api/summarize", {"text": DOCUMENT})):
            error = self.api(name, "POST", route, payload, expected=503)
            self.require(name + " actionable error", isinstance(error.get("error"), str) and "local model server" in error["error"], error)
        self.api("Notes readable during model outage", "GET", "/api/notes")
        failed_history = self.api("History after failed chat", "GET", "/api/chat")["messages"]
        self.require("Failed-chat storage behavior", len(failed_history) == len(before) + 1 and failed_history[-1]["role"] == "user",
                     "Current node persists the user message before inference; a 503 leaves that message, with no assistant reply")
        self.start_model()
        self.phase = "recovery"
        recovery = self.api("Chat after model restart", "POST", "/api/chat", {"message": PROMPT})
        self.require("Recovered chat nonempty", isinstance(recovery.get("reply"), str) and bool(recovery["reply"].strip()), recovery)
        self.phase = "observation_idle"
        print("Browser check window: http://127.0.0.1:8090 (isolated test data). " + str(self.args.observe_seconds) + " seconds.", flush=True)
        deadline = time.monotonic() + self.args.observe_seconds
        while time.monotonic() < deadline:
            self.check_temperature()
            for name, process in list(self.children.items()):
                if process.poll() is not None:
                    self.require(name + " alive during observation", False, "pid=" + str(process.pid))
            self.stopping.wait(min(1, max(0, deadline - time.monotonic())))
        self.api("Final node available", "GET", "/api/status")
        self.report["completed"] = True

    def finish(self):
        self.stopping.set()
        if self.sampler is not None:
            self.sampler.join(timeout=5)
        try:
            self.phase = "before_shutdown"
            self.snapshot()
        except Exception as error:
            self.record("Final telemetry", "WARN", str(error))
        for name in ("dashboard", "llama"):
            try:
                self.stop(name)
            except Exception as error:
                self.record(name + " cleanup", "FAIL", str(error))
        for handle in self.logs:
            handle.close()
        self.report["ended_utc"] = datetime.now(timezone.utc).isoformat()
        self.report["telemetry_samples"] = len(self.samples)
        rss, available, temperatures = [], [], []
        for sample in self.samples:
            available_value = (sample["memory_bytes"] or {}).get("MemAvailable")
            if available_value is not None:
                available.append(available_value)
            for values in sample["process_bytes"].values():
                if values and "VmRSS" in values:
                    rss.append(values["VmRSS"])
            api = sample["battery_termux_api"]
            if isinstance(api, dict) and isinstance(api.get("temperature"), (int, float)):
                temperatures.append(api["temperature"])
        self.report["resource_summary"] = {
            "min_available_memory_bytes": min(available) if available else None,
            "max_single_process_sampled_rss_bytes": max(rss) if rss else None,
            "max_battery_api_temperature_c": max(temperatures) if temperatures else None,
            "notes": "Sampled RSS is approximate, not PSS or aggregate usage; raw battery/thermal readings and missing values are in telemetry.jsonl. No battery-life estimate.",
        }
        if self.args.mode == "run":
            self.record("Telemetry scope", "WARN", "Missing sensors are unavailable, not zero; short sampled runs cannot establish sustained stability or battery life")
        failures = [c for c in self.report["checks"] if c["state"] == "FAIL"]
        self.report["automated_result"] = "FAIL" if failures else ("PASS_WITH_MANUAL_CHECKS" if self.report["completed"] else "INCOMPLETE")
        self.save()
        print("Result: " + self.report["automated_result"] + "; hardware_verified remains false pending reviewed device evidence.\n" + str(self.directory / "report.json"), flush=True)
        return 1 if failures or not self.report["completed"] else 0


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "run"))
    parser.add_argument("--offline-confirmed", action="store_true", help="Operator has enabled airplane mode AND disabled Wi-Fi/mobile data")
    parser.add_argument("--hash-model", action="store_true", help="Compute local SHA256; does not fetch or automatically compare publisher digest")
    parser.add_argument("--expected-sha256", help="Hash and compare model with this previously obtained publisher digest; no download")
    parser.add_argument("--llama-server", default=str(Path.home() / "llama.cpp/build/bin/llama-server"))
    parser.add_argument("--model", default=str(Path.home() / "models" / MODEL_NAME))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--context", type=int, default=2048)
    parser.add_argument("--load-timeout", type=int, default=300)
    parser.add_argument("--request-timeout", type=int, default=210, help="Node's own model request timeout is fixed at 180 seconds")
    parser.add_argument("--observe-seconds", type=int, default=60, help="Idle window for browser checks; not a continuous inference benchmark")
    parser.add_argument("--sample-seconds", type=int, default=10)
    parser.add_argument("--repeat", type=int, default=1, help="Number of short node chat requests (1-5)")
    parser.add_argument("--development-only", action="store_true", help="Allow non-Android harness validation; cannot verify phone compatibility")
    args = parser.parse_args()
    if args.expected_sha256 and (len(args.expected_sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in args.expected_sha256)):
        parser.error("expected-sha256 must be exactly 64 hexadecimal characters")
    for name, low, high in (("threads", 1, 4), ("context", 512, 2048), ("load_timeout", 1, 900),
                            ("request_timeout", 1, 600), ("observe_seconds", 0, 1800), ("sample_seconds", 1, 60), ("repeat", 1, 5)):
        if not low <= getattr(args, name) <= high:
            parser.error(name + " must be between " + str(low) + " and " + str(high))
    if args.mode == "run" and not args.offline_confirmed and not args.development_only:
        parser.error("Enable airplane mode, disable Wi-Fi/mobile data, then supply --offline-confirmed. No radios are changed by this script.")
    return args


def interrupted(signum, frame):
    raise KeyboardInterrupt


def main():
    args = arguments()
    signal.signal(signal.SIGTERM, interrupted)
    test = SmokeTest(args)
    try:
        test.preflight()
        if args.mode == "run":
            test.run_stack()
        else:
            test.report["completed"] = True
    except KeyboardInterrupt:
        test.record("Interrupted", "FAIL", "Interrupted; stopping only owned children, preserving evidence")
    except Exception as error:
        test.record("Stopped at " + test.phase, "FAIL", str(error))
    finally:
        result = test.finish()
    return result


if __name__ == "__main__":
    sys.exit(main())
