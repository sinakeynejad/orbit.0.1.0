import asyncio
from uuid import uuid4
from app.core.exceptions import AssistantError
from app.memory.conversation import Conversation


class Assistant:
    def __init__(self, orchestrator, max_sessions=100, store=None):
        self.orchestrator = orchestrator
        self.max_sessions = max_sessions
        self.store = store
        self.sessions = {sid: (conv, asyncio.Lock()) for sid, conv in store.load().items()} if store else {}

    def create_session(self):
        if len(self.sessions) >= self.max_sessions:
            raise AssistantError("Session limit reached. Delete an unused session.")
        session_id = uuid4().hex
        conversation = Conversation()
        if self.store:
            self.store.save(session_id, conversation)
        self.sessions[session_id] = (conversation, asyncio.Lock())
        return session_id

    def delete_session(self, session_id):
        pair = self.sessions.get(session_id)
        if pair and pair[1].locked():
            raise AssistantError("Session is busy.")
        if self.store:
            self.store.delete(session_id)
        self.sessions.pop(session_id, None)

    async def chat(self, session_id, text, confirm=None, emit=None):
        if not text.strip() or len(text) > 16000:
            raise AssistantError("Message must contain 1 to 16000 characters.")
        pair = self.sessions.get(session_id)
        if pair is None:
            raise AssistantError("Unknown session.")
        conversation, lock = pair
        if lock.locked():
            raise AssistantError("Session is busy.")
        async with lock:
            async def record(event):
                if self.store and event["type"] in {"executing", "tool_result"}:
                    self.store.audit({"session_id": session_id, **event})
                if emit:
                    await emit(event)
            try:
                return await self.orchestrator.run(conversation, text, confirm, record)
            finally:
                if self.store:
                    self.store.save(session_id, conversation)
