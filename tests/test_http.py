import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from hydrogen_node import NodeHandler


class FakeLlama:
    def healthy(self):
        return True

    def chat(self, messages, max_tokens=384):
        return "local reply"

    def summarize(self, text):
        return "local summary"


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), NodeHandler)
        from hydrogen_node import Database
        self.server.db = Database(Path(self.temp.name) / "node.db")
        self.server.llama = FakeLlama()
        self.server.static_dir = str(Path(__file__).resolve().parent.parent / "static")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.temp.cleanup()

    def request(self, method, path, payload=None, content_type="application/json"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        body = json.dumps(payload) if payload is not None else None
        headers = {"Content-Type": content_type} if body is not None else {}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        data = json.loads(raw) if response.getheader("Content-Type", "").startswith("application/json") else raw
        return response.status, data

    def test_dashboard_and_full_api_flow(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Hydrogen AI Node", body)

        status, note = self.request("POST", "/api/notes", {"title": "Pinout", "body": "USB accessory notes"})
        self.assertEqual(status, 201)
        note_id = note["note"]["id"]

        status, task = self.request("POST", "/api/tasks", {"title": "Test sensors"})
        self.assertEqual(status, 201)
        task_id = task["task"]["id"]
        status, changed = self.request("PATCH", "/api/tasks/" + str(task_id), {"done": True})
        self.assertEqual(changed["task"]["done"], 1)

        status, found = self.request("GET", "/api/search?q=USB")
        self.assertEqual(found["notes"][0]["id"], note_id)

        status, chat = self.request("POST", "/api/chat", {"message": "hello"})
        self.assertEqual(chat["reply"], "local reply")
        status, history = self.request("GET", "/api/chat")
        self.assertEqual(len(history["messages"]), 2)

        status, summary = self.request("POST", "/api/summarize", {"text": "A short document."})
        self.assertEqual(summary["summary"], "local summary")
        status, health = self.request("GET", "/api/status")
        self.assertEqual(health["model"], "online")

        self.assertEqual(self.request("DELETE", "/api/notes/" + str(note_id))[0], 200)
        self.assertEqual(self.request("DELETE", "/api/tasks/" + str(task_id))[0], 200)

    def test_rejects_invalid_requests(self):
        status, data = self.request("POST", "/api/notes", "not-json", "text/plain")
        self.assertEqual(status, 400)
        self.assertIn("Content-Type", data["error"])
        status, data = self.request("GET", "/not-found")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
