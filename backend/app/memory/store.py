import json
import sqlite3
import threading
import logging
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

        columns = {row[1] for row in self.db.execute("PRAGMA table_info(sessions)")}
        if "custom_title" not in columns:
            self.db.execute("ALTER TABLE sessions ADD COLUMN custom_title TEXT")
            self.db.commit()

    def save(self, session_id, conversation):
        turns = [[m.model_dump(mode="json") for m in turn] for turn in conversation.turns]
        title = conversation.title
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO sessions (id, title, turns, custom_title) VALUES (?, ?, ?, ?)",
                            (session_id, title, json.dumps(turns), conversation.custom_title))

    def load(self):
        with self.lock:
            rows = self.db.execute("SELECT id, turns, custom_title FROM sessions ORDER BY rowid DESC LIMIT 100").fetchall()
        result = {}
        for sid, raw, custom_title in rows:
            conv = Conversation()
            try:
                turns = json.loads(raw)
                if not isinstance(turns, list) or any(not isinstance(t, list) for t in turns):
                    raise ValueError("Invalid history shape")
                conv.custom_title = custom_title if isinstance(custom_title, str) else None
                conv.turns = [[Message.model_validate(m) for m in turn] for turn in turns][-conv.max_turns:]
            except (ValueError, TypeError):
                logging.getLogger(__name__).warning("Skipped an unreadable conversation; original database record preserved.")
                continue
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
