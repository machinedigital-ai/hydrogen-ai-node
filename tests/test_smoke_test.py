"""Harness safety/integration tests. The fake backend NEVER proves model inference."""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("phone_smoke", Path(__file__).resolve().parent.parent / "scripts/smoke_test.py")
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)

FAKE_SERVER = '''#!INTERPRETER
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
if "--version" in sys.argv:
    print("FAKE BACKEND: harness validation only")
    sys.exit(0)
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        self.send({"status": "ok"})
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.send({"choices": [{"message": {"content": "Four. Workshop: Tuesday, six people, 120 dollars, venue undecided."}}]})
    def send(self, body):
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
ThreadingHTTPServer(("127.0.0.1", int(sys.argv[sys.argv.index("--port") + 1])), Handler).serve_forever()
'''


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class SmokeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.home_patch = patch.object(smoke.Path, "home", return_value=self.home)
        self.home_patch.start()
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.binary = self.home / "fake-llama"
        self.binary.write_text(FAKE_SERVER.replace("INTERPRETER", sys.executable))
        self.binary.chmod(0o700)
        self.model = self.home / "fake.gguf"
        self.model.write_bytes(b"GGUF-not-a-real-model")
        self.args = argparse.Namespace(mode="run", development_only=True, offline_confirmed=False,
                                      model=str(self.model), llama_server=str(self.binary), hash_model=False, expected_sha256=None,
                                      threads=1, context=512, load_timeout=5, request_timeout=5,
                                      observe_seconds=0, sample_seconds=1, repeat=1)
        self.test = smoke.SmokeTest(self.args)
        self.test.model_port = free_port()
        self.test.node_port = free_port()
        while self.test.node_port == self.test.model_port:
            self.test.node_port = free_port()
        self.production = self.home / ".hydrogen-ai-node/node.db"
        self.production.write_bytes(b"production sentinel: do not read or modify")

    def tearDown(self):
        if self.test.children:
            self.test.finish()
        self.output.__exit__(None, None, None)
        self.home_patch.stop()
        self.temp.cleanup()

    def test_full_orchestration_preserves_production_and_restarts_services(self):
        self.test.preflight()
        with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "NO_PROXY": "", "no_proxy": ""}):
            self.test.run_stack()
        self.assertEqual(self.test.finish(), 0)
        report = json.loads((self.test.directory / "report.json").read_text())
        self.assertTrue(report["completed"])
        self.assertTrue(report["development_only"])
        self.assertFalse(report["hardware_verified"])
        self.assertEqual(self.production.read_bytes(), b"production sentinel: do not read or modify")
        self.assertEqual(report["responses"]["Chat with model stopped"]["status"], 503)
        self.assertEqual(report["responses"]["Summary with model stopped"]["status"], 503)
        self.assertEqual(report["responses"]["History before restart"]["body"], report["responses"]["History after restart"]["body"])
        self.assertEqual(len(report["commands"]), 4)
        for entry in report["commands"]:
            self.assertIn("127.0.0.1", entry["argv"])
        self.assertEqual(self.test.children, {})
        self.assertTrue(self.test.db.is_file())
        for port in (self.test.model_port, self.test.node_port):
            with socket.socket() as sock:
                self.assertNotEqual(sock.connect_ex(("127.0.0.1", port)), 0)

    def test_occupied_port_refuses_without_touching_existing_listener(self):
        with socket.socket() as existing:
            existing.bind(("127.0.0.1", self.test.node_port))
            existing.listen()
            with self.assertRaises(smoke.CheckFailed):
                self.test.preflight()
            self.assertEqual(self.test.children, {})
            with socket.socket() as client:
                self.assertEqual(client.connect_ex(existing.getsockname()), 0)
        self.assertEqual(self.test.finish(), 1)

    def test_model_exit_preserves_logs_and_cleanup_leaves_unrelated_listener(self):
        self.binary.write_text("#!" + sys.executable + "\nraise SystemExit(17)\n")
        with socket.socket() as unrelated:
            unrelated.bind(("127.0.0.1", 0))
            unrelated.listen()
            with self.assertRaisesRegex(smoke.CheckFailed, "exited with 17"):
                self.test.start_model()
            self.assertEqual(self.test.finish(), 1)
            with socket.socket() as client:
                self.assertEqual(client.connect_ex(unrelated.getsockname()), 0)
        self.assertTrue((self.test.directory / "llama.log").is_file())
        self.assertEqual(self.test.children, {})

    def test_model_digest_mismatch_prevents_service_start(self):
        self.args.expected_sha256 = "0" * 64
        with self.assertRaises(smoke.CheckFailed):
            self.test.preflight()
        self.assertFalse(self.test.report["installation_ready"])
        self.assertEqual(self.test.children, {})
        self.assertEqual(self.test.finish(), 1)

    def test_missing_telemetry_is_unavailable_not_zero(self):
        with patch.object(smoke, "read_text", return_value=None), patch.object(smoke.shutil, "which", return_value=None):
            self.test.snapshot()
        self.assertIsNone(self.test.samples[0]["memory_bytes"])
        self.assertIsNone(self.test.samples[0]["battery_termux_api"])
        self.assertIsNone(self.test.samples[0]["battery_sysfs_raw"]["temp"])
        self.test.finish()

    def test_listener_decode_and_restricted_visibility(self):
        tcp = "header\n0: 0100007F:1F90 00000000:0000 0A\n1: 00000000:1F9A 00000000:0000 0A"
        tcp6 = "header\n0: 00000000000000000000000001000000:1F90 0:0000 0A"
        with patch.object(smoke, "read_text", side_effect=[tcp, tcp6]):
            result = smoke.listeners({8080, 8090})
        self.assertEqual([row["host"] for row in result["listeners"]], ["127.0.0.1", "0.0.0.0", "::1"])
        with patch.object(smoke, "read_text", return_value=None):
            self.assertEqual(smoke.listeners({8080})["readable_tables"], [])


if __name__ == "__main__":
    unittest.main()
