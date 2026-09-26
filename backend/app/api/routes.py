from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, ConfigDict

router = APIRouter()


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=16000)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/sessions", status_code=201)
async def create_session(request: Request):
    return {"session_id": request.app.state.assistant.create_session()}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    request.app.state.assistant.delete_session(session_id)
    return {"deleted": True}


@router.post("/sessions/{session_id}/messages")
async def chat(session_id: str, body: ChatRequest, request: Request):
    # REST cannot approve writes. Use the interactive WebSocket for confirmation.
    answer = await request.app.state.assistant.chat(session_id, body.message)
    return {"content": answer}


@router.get("/sessions")
async def list_sessions(request: Request):
    return [{"id": sid, "title": next((m.content[:60] for t in c.turns for m in t if m.role.value == "user"), "New conversation")}
            for sid, (c, _) in request.app.state.assistant.sessions.items()]


@router.get("/sessions/{session_id}")
async def history(session_id: str, request: Request):
    from app.core.exceptions import AssistantError
    pair = request.app.state.assistant.sessions.get(session_id)
    if pair is None: raise AssistantError("Unknown session.")
    return [m.model_dump(mode="json") for m in pair[0].messages() if m.role.value != "system"]
