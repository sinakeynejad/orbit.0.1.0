from fastapi import APIRouter, Request, Query
from fastapi.responses import Response
from app.core.exceptions import AssistantError
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
async def list_sessions(request: Request, q: str = Query(default="", max_length=200)):
    needle = q.strip().casefold()
    return [{"id": sid, "title": c.title}
            for sid, (c, _) in request.app.state.assistant.sessions.items()
            if not needle or needle in c.title.casefold() or any(
                needle in (m.content or "").casefold() for t in c.turns for m in t
                if m.role.value in {"user", "assistant"})]


class RenameSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)


@router.patch("/sessions/{session_id}")
async def rename_session(session_id: str, body: RenameSession, request: Request):
    assistant = request.app.state.assistant
    pair = assistant.sessions.get(session_id)
    if pair is None:
        raise AssistantError("Unknown session.")
    if pair[1].locked():
        raise AssistantError("Wait for the conversation to finish before renaming it.")
    title = " ".join(body.title.split())
    if not title:
        raise AssistantError("Enter a conversation name.")
    conversation = pair[0]
    previous = conversation.custom_title
    conversation.custom_title = title
    try:
        if assistant.store:
            assistant.store.save(session_id, conversation)
    except Exception:
        conversation.custom_title = previous
        raise
    return {"id": session_id, "title": title}


@router.get("/sessions/{session_id}/export")
async def export_session(session_id: str, request: Request):
    pair = request.app.state.assistant.sessions.get(session_id)
    if pair is None:
        raise AssistantError("Unknown session.")
    if pair[1].locked():
        raise AssistantError("Wait for the conversation to finish before exporting it.")
    conversation = pair[0]
    parts = ["# " + conversation.title, "Export of retained conversation history (up to 20 turns)."]
    for turn in conversation.turns:
        for message in turn:
            if message.role.value in {"user", "assistant"} and message.content:
                parts.extend(["## " + ("You" if message.role.value == "user" else "Orbit"), message.content])
    return Response("\n\n".join(parts) + "\n", media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="conversation.md"'})


@router.get("/sessions/{session_id}")
async def history(session_id: str, request: Request):
    from app.core.exceptions import AssistantError
    pair = request.app.state.assistant.sessions.get(session_id)
    if pair is None: raise AssistantError("Unknown session.")
    return [m.model_dump(mode="json") for m in pair[0].messages() if m.role.value != "system"]
