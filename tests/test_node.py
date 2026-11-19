import tempfile
import unittest
from unittest import mock
from pathlib import Path

from hydrogen_node import Database, LlamaClient, clean_text, recent_history, split_text


class ValidationTests(unittest.TestCase):
    def test_clean_text(self):
        self.assertEqual(clean_text("  hello  ", 20), "hello")
        with self.assertRaises(ValueError):
            clean_text("   ", 20)
        with self.assertRaises(ValueError):
            clean_text("too long", 3)

    def test_history_budget_keeps_newest_messages(self):
        rows = [
            {"role": "user", "content": "a" * 3000},
            {"role": "assistant", "content": "b" * 3000},
            {"role": "user", "content": "latest"},
        ]
        history = recent_history(rows, char_budget=4000)
        self.assertEqual(history[-1]["content"], "latest")
        self.assertLess(sum(len(row["content"]) for row in history), 4000)

    def test_split_text_respects_size_and_preserves_content(self):
        text = ("alpha beta gamma\n" * 500).strip()
        chunks = split_text(text, size=500)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 500 for chunk in chunks))
        self.assertEqual(" ".join(" ".join(chunks).split()), " ".join(text.split()))


class RecordingLlama(LlamaClient):
    def __init__(self):
        self.calls = []

    def chat(self, messages, max_tokens=384):
        self.calls.append((messages, max_tokens))
        return "summary"


class SummaryTests(unittest.TestCase):
    def test_model_url_must_be_loopback_http(self):
        for url in (
            "file:///tmp/model",
            "https://example.com",
            "http://example.com",
            "https://127.0.0.1:8080",
            "http://127.0.0.1:bad",
            "http://127.0.0.1:8080/path",
            "http://user@127.0.0.1:8080",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                LlamaClient(url)
        LlamaClient("http://127.0.0.1:8080")
        LlamaClient("http://[::1]:8080")

    def test_long_summary_is_chunked_and_combined(self):
        client = RecordingLlama()
        result = client.summarize("word " * 2500)
        self.assertEqual(result, "summary")
        self.assertGreater(len(client.calls), 2)
        self.assertEqual(client.calls[-1][1], 360)


class ApiKeyTests(unittest.TestCase):
    def test_key_validation_and_authorization_headers(self):
        for key in ("", " leading", "two\nlines"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                LlamaClient("http://127.0.0.1:8080", api_key=key)
        client = LlamaClient("http://127.0.0.1:8080", api_key="secret")
        with mock.patch("urllib.request.urlopen") as urlopen:
            response = urlopen.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b"{\"choices\":[{\"message\":{\"content\":\"ok\"}}]}"
            self.assertEqual(client.chat([]), "ok")
            self.assertTrue(client.healthy())
            for call in urlopen.call_args_list:
                request = call.args[0]
                self.assertEqual(request.get_header("Authorization"), "Bearer secret")


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "node.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_notes_and_search(self):
        note = self.db.add_note("Offline ideas", "Build a private sensor dashboard")
        self.assertEqual(note["title"], "Offline ideas")
        self.assertEqual(len(self.db.list_notes()), 1)
        result = self.db.search("sensor")
        self.assertEqual(result["notes"][0]["id"], note["id"])
        self.assertTrue(self.db.delete_note(note["id"]))
        self.assertFalse(self.db.delete_note(note["id"]))

    def test_tasks(self):
        task = self.db.add_task("Test local inference")
        self.assertFalse(bool(task["done"]))
        changed = self.db.set_task(task["id"], True)
        self.assertEqual(changed["done"], 1)
        self.assertEqual(self.db.counts()["tasks_open"], 0)
        self.assertTrue(self.db.delete_task(task["id"]))

    def test_chat_order_and_clear(self):
        self.db.add_message("user", "first")
        self.db.add_message("assistant", "second")
        self.assertEqual([m["content"] for m in self.db.list_messages()], ["first", "second"])
        self.db.clear_messages()
        self.assertEqual(self.db.list_messages(), [])


if __name__ == "__main__":
    unittest.main()
