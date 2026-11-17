#!/usr/bin/env python3
"""Hydrogen AI Node: local dashboard and tools, using only Python's stdlib."""

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

STARTED = time.time()
MAX_BODY = 1_000_000
SYSTEM_PROMPT = (
    "You are Hydrogen, a concise offline assistant running on the user's own phone. "
    "Be honest about uncertainty. You cannot control hardware or perform actions "
    "unless the dashboard explicitly provides that capability."
)


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value, maximum, field="text"):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field + " is required")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(field + " exceeds " + str(maximum) + " characters")
    return value


class Database:
    def __init__(self, path):
        self.path = str(Path(path).expanduser())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self):
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def rows(result):
        return [dict(row) for row in result]

    def add_note(self, title, body):
        now = utcnow()
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO notes(title, body, created_at, updated_at) VALUES(?,?,?,?)",
                (title, body, now, now),
            )
            row = db.execute("SELECT * FROM notes WHERE id=?", (cursor.lastrowid,)).fetchone()
            return dict(row)

    def list_notes(self):
        with self.connect() as db:
            return self.rows(db.execute("SELECT * FROM notes ORDER BY updated_at DESC LIMIT 200"))

    def delete_note(self, item_id):
        with self.connect() as db:
            return db.execute("DELETE FROM notes WHERE id=?", (item_id,)).rowcount > 0

    def add_task(self, title):
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO tasks(title, created_at) VALUES(?,?)", (title, utcnow())
            )
            row = db.execute("SELECT * FROM tasks WHERE id=?", (cursor.lastrowid,)).fetchone()
            return dict(row)

    def list_tasks(self):
        with self.connect() as db:
            return self.rows(db.execute("SELECT * FROM tasks ORDER BY done, id DESC LIMIT 200"))

    def set_task(self, item_id, done):
        with self.connect() as db:
            db.execute("UPDATE tasks SET done=? WHERE id=?", (1 if done else 0, item_id))
            row = db.execute("SELECT * FROM tasks WHERE id=?", (item_id,)).fetchone()
            return dict(row) if row else None

    def delete_task(self, item_id):
        with self.connect() as db:
            return db.execute("DELETE FROM tasks WHERE id=?", (item_id,)).rowcount > 0

    def add_message(self, role, content):
        with self.connect() as db:
            db.execute(
                "INSERT INTO messages(role, content, created_at) VALUES(?,?,?)",
                (role, content, utcnow()),
            )

    def list_messages(self, limit=100):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM (SELECT * FROM messages ORDER BY id DESC LIMIT ?) ORDER BY id",
                (limit,),
            )
            return self.rows(rows)

    def clear_messages(self):
        with self.connect() as db:
            db.execute("DELETE FROM messages")

    def search(self, query):
        pattern = "%" + query + "%"
        with self.connect() as db:
            notes = self.rows(db.execute(
                "SELECT id,title,body,updated_at FROM notes "
                "WHERE title LIKE ? OR body LIKE ? ORDER BY updated_at DESC LIMIT 30",
                (pattern, pattern),
            ))
            tasks = self.rows(db.execute(
                "SELECT id,title,done,created_at FROM tasks "
                "WHERE title LIKE ? ORDER BY id DESC LIMIT 30", (pattern,)
            ))
            return {"notes": notes, "tasks": tasks}

    def counts(self):
        with self.connect() as db:
            return {
                "notes": db.execute("SELECT COUNT(*) FROM notes").fetchone()[0],
                "tasks_open": db.execute("SELECT COUNT(*) FROM tasks WHERE done=0").fetchone()[0],
                "messages": db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            }


class LlamaClient:
    def __init__(self, base_url, timeout=180):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _post(self, path, payload):
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read(1000).decode("utf-8", "replace")
            raise RuntimeError("Model server returned " + str(error.code) + ": " + detail)
        except (urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError("Cannot reach the local model server: " + str(error))

    def healthy(self):
        try:
            with urllib.request.urlopen(self.base_url + "/health", timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    def chat(self, messages, max_tokens=384):
        result = self._post(
            "/v1/chat/completions",
            {
                "model": "local",
                "messages": messages,
                "stream": False,
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
        )
        try:
            return result["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("Model server returned an unexpected response")

    def summarize(self, text):
        messages = [
            {
                "role": "system",
                "content": "Summarize the supplied text accurately. Use a short overview followed by key points. Do not invent facts.",
            },
            {"role": "user", "content": text},
        ]
        return self.chat(messages, max_tokens=420)


def device_status():
    memory = {}
    try:
        values = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            parts = line.split()
            if parts[0] in ("MemTotal:", "MemAvailable:"):
                values[parts[0]] = int(parts[1]) * 1024
        if "MemTotal:" in values:
            memory = {
                "total_bytes": values["MemTotal:"],
                "available_bytes": values.get("MemAvailable:"),
            }
    except (OSError, ValueError, IndexError):
        pass
    disk = shutil.disk_usage(str(Path.home()))
    return {
        "platform": " ".join((os.uname().sysname, os.uname().release)) if hasattr(os, "uname") else sys.platform,
        "python": sys.version.split()[0],
        "uptime_seconds": int(time.time() - STARTED),
        "memory": memory,
        "storage": {"total_bytes": disk.total, "free_bytes": disk.free},
    }


class NodeHandler(BaseHTTPRequestHandler):
    server_version = "HydrogenNode/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_data(self, status, body, content_type):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, value):
        self.send_data(status, json.dumps(value), "application/json; charset=utf-8")

    def json_body(self):
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            raise ValueError("Content-Type must be application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid Content-Length")
        if length <= 0 or length > MAX_BODY:
            raise ValueError("Request body is empty or too large")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError("Invalid JSON")
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value

    def serve_dashboard(self):
        path = Path(self.server.static_dir) / "index.html"
        self.send_data(200, path.read_bytes(), "text/html; charset=utf-8")

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def do_PATCH(self):
        self.handle_request("PATCH")

    def do_DELETE(self):
        self.handle_request("DELETE")

    def handle_request(self, method):
        try:
            self.route(method)
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
        except RuntimeError as error:
            self.send_json(503, {"error": str(error)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            self.log_error("Unhandled error: %r", error)
            self.send_json(500, {"error": "Internal node error"})

    def route(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        db = self.server.db
        llama = self.server.llama

        if method == "GET" and path in ("/", "/index.html"):
            return self.serve_dashboard()
        if method == "GET" and path == "/api/status":
            return self.send_json(200, {
                "node": "online",
                "model": "online" if llama.healthy() else "offline",
                "database": db.counts(),
                "device": device_status(),
            })
        if method == "GET" and path == "/api/notes":
            return self.send_json(200, {"notes": db.list_notes()})
        if method == "POST" and path == "/api/notes":
            data = self.json_body()
            note = db.add_note(
                clean_text(data.get("title"), 200, "title"),
                clean_text(data.get("body"), 50000, "body"),
            )
            return self.send_json(201, {"note": note})
        if method == "GET" and path == "/api/tasks":
            return self.send_json(200, {"tasks": db.list_tasks()})
        if method == "POST" and path == "/api/tasks":
            data = self.json_body()
            task = db.add_task(clean_text(data.get("title"), 500, "title"))
            return self.send_json(201, {"task": task})
        if method == "GET" and path == "/api/chat":
            return self.send_json(200, {"messages": db.list_messages()})
        if method == "POST" and path == "/api/chat":
            data = self.json_body()
            message = clean_text(data.get("message"), 12000, "message")
            db.add_message("user", message)
            history = [
                {"role": row["role"], "content": row["content"]}
                for row in db.list_messages(12)
            ]
            reply = llama.chat([{"role": "system", "content": SYSTEM_PROMPT}] + history)
            db.add_message("assistant", reply)
            return self.send_json(200, {"reply": reply})
        if method == "POST" and path == "/api/chat/clear":
            db.clear_messages()
            return self.send_json(200, {"cleared": True})
        if method == "DELETE" and path == "/api/chat":
            db.clear_messages()
            return self.send_json(200, {"cleared": True})
        if method == "POST" and path == "/api/summarize":
            data = self.json_body()
            text = clean_text(data.get("text"), 60000, "text")
            return self.send_json(200, {"summary": llama.summarize(text)})
        if method == "GET" and path == "/api/search":
            query = clean_text(parse_qs(parsed.query).get("q", [""])[0], 200, "query")
            return self.send_json(200, db.search(query))

        match = re.fullmatch(r"/api/tasks/(\d+)", path)
        if match and method == "PATCH":
            data = self.json_body()
            if not isinstance(data.get("done"), bool):
                raise ValueError("done must be true or false")
            task = db.set_task(int(match.group(1)), data["done"])
            if task is None:
                return self.send_json(404, {"error": "Task not found"})
            return self.send_json(200, {"task": task})
        if match and method == "DELETE":
            if not db.delete_task(int(match.group(1))):
                return self.send_json(404, {"error": "Task not found"})
            return self.send_json(200, {"deleted": True})
        match = re.fullmatch(r"/api/notes/(\d+)", path)
        if match and method == "DELETE":
            if not db.delete_note(int(match.group(1))):
                return self.send_json(404, {"error": "Note not found"})
            return self.send_json(200, {"deleted": True})
        return self.send_json(404, {"error": "Not found"})


def main():
    parser = argparse.ArgumentParser(description="Run the Hydrogen AI Node dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--llama-url", default="http://127.0.0.1:8080")
    parser.add_argument("--db", default=str(Path.home() / ".hydrogen-ai-node" / "node.db"))
    parser.add_argument("--static", default=str(Path(__file__).resolve().parent / "static"))
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), NodeHandler)
    server.db = Database(args.db)
    server.llama = LlamaClient(args.llama_url)
    server.static_dir = args.static
    print("Hydrogen AI Node: http://%s:%d" % (args.host, args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
