import asyncio
import contextlib
import secrets
from uuid import uuid4
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.exceptions import AssistantError

router = APIRouter()


@router.websocket("/ws")
async def websocket_chat(socket: WebSocket):
    origin = socket.headers.get("origin")
    expected_origin = "http://" + socket.headers.get("host", "")
    actual = socket.headers.get("authorization", "").removeprefix("Bearer ") or socket.cookies.get("assistant_session", "")
    if (origin and origin != expected_origin) or not secrets.compare_digest(actual.encode(), socket.app.state.token.encode()):
        await socket.close(code=1008)
        return
    await socket.accept()
    assistant = socket.app.state.assistant
    session_id = socket.query_params.get("session_id")
    if session_id and session_id not in assistant.sessions:
        await socket.close(code=1008)
        return
    try:
        session_id = session_id or assistant.create_session()
    except AssistantError as exc:
        await socket.send_json({"type": "error", "message": str(exc)})
        await socket.close(code=1013)
        return
    task = None
    pending = {}
    await socket.send_json({"type": "session", "session_id": session_id})

    async def confirm(call):
        cid = uuid4().hex
        future = asyncio.get_running_loop().create_future()
        pending[cid] = future
        await socket.send_json({"type": "confirmation_required", "confirmation_id": cid, "call": call.model_dump()})
        try:
            return await asyncio.wait_for(future, 60)
        except asyncio.TimeoutError:
            await socket.send_json({"type": "confirmation_expired", "confirmation_id": cid})
            return False
        finally:
            pending.pop(cid, None)

    async def run(text):
        try:
            answer = await assistant.chat(session_id, text, confirm, socket.send_json)
            await socket.send_json({"type": "completed", "content": answer})
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                await socket.send_json({"type": "cancelled", "message": "Stopped. Already executed operations are not undone."})
            raise
        except AssistantError as exc:
            await socket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            await socket.send_json({"type": "error", "message": "Unexpected execution failure. Check activity before retrying."})

    try:
        while True:
            data = await socket.receive_json()
            if not isinstance(data, dict):
                continue
            kind = data.get("type")
            if kind == "confirmation":
                confirmation_id = data.get("confirmation_id")
                if not isinstance(confirmation_id, str) or not isinstance(data.get("approved"), bool):
                    await socket.send_json({"type": "error", "message": "Invalid confirmation event."})
                    continue
                future = pending.get(confirmation_id)
                if future and not future.done():
                    future.set_result(data.get("approved") is True)
                elif pending:
                    # Invalid IDs never authorize; deny outstanding request.
                    for f in pending.values():
                        if not f.done(): f.set_result(False)
            elif kind == "cancel":
                if task and not task.done() and not task.cancelling(): task.cancel()
            elif kind == "message" and isinstance(data.get("message"), str):
                if task and not task.done():
                    await socket.send_json({"type": "error", "message": "Request already running."})
                else:
                    task = asyncio.create_task(run(data["message"]))
            else:
                await socket.send_json({"type": "error", "message": "Invalid event."})
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        if task and not task.done() and not task.cancelling(): task.cancel()
        if task:
            with contextlib.suppress(asyncio.CancelledError, Exception): await task
