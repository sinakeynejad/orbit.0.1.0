import json
import sqlite3
import threading
from datetime import datetime, timezone
from app.llm.schemas import Message
from app.memory.conversation import Conversation


class Store:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT, turns TEXT);
        CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, time TEXT, event TEXT);
        """)

    def save(self, session_id, conversation):
        turns = [[m.model_dump(mode="json") for m in turn] for turn in conversation.turns]
        title = next((m.content[:60] for turn in conversation.turns for m in turn if m.role.value == "user"), "New conversation")
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?)",
                            (session_id, title, json.dumps(turns)))

    def load(self):
        with self.lock:
            rows = self.db.execute("SELECT id, turns FROM sessions ORDER BY rowid DESC LIMIT 100").fetchall()
        result = {}
        for sid, raw in rows:
            conv = Conversation()
            conv.turns = [[Message.model_validate(m) for m in turn] for turn in json.loads(raw)]
            result[sid] = conv
        return result

    def delete(self, sid):
        with self.lock, self.db:
            self.db.execute("DELETE FROM sessions WHERE id=?", (sid,))

    def audit(self, event):
        with self.lock, self.db:
            self.db.execute("INSERT INTO audit(time,event) VALUES (?,?)",
                            (datetime.now(timezone.utc).isoformat(), json.dumps(event, ensure_ascii=False)))

    def recent_audit(self):
        with self.lock:
            return [{"time": t, **json.loads(e)} for t, e in self.db.execute(
                "SELECT time,event FROM audit ORDER BY id DESC LIMIT 100")]

    def close(self):
        self.db.close()
