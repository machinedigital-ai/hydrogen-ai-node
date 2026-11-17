import tempfile
import unittest
from pathlib import Path

from hydrogen_node import Database, clean_text


class ValidationTests(unittest.TestCase):
    def test_clean_text(self):
        self.assertEqual(clean_text("  hello  ", 20), "hello")
        with self.assertRaises(ValueError):
            clean_text("   ", 20)
        with self.assertRaises(ValueError):
            clean_text("too long", 3)


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
