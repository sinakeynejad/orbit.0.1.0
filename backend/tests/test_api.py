from fastapi.testclient import TestClient
from app.api.main import create_app
from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.schemas import LLMResponse

TOKEN = "t" * 40


class ReplyProvider(LLMProvider):
    async def generate(self, messages, tools=None):
        return LLMResponse(content="Hello")


def test_authenticated_chat(tmp_path):
    settings = Settings(_env_file=None, llm_provider="ollama", llm_model="test",
                        api_token=TOKEN, workspace_dir=tmp_path)
    with TestClient(create_app(settings, ReplyProvider())) as client:
        assert client.get("/health").status_code == 401
        headers = {"Authorization": "Bearer " + TOKEN}
        assert client.get("/health", headers={**headers, "Origin": "https://evil.test"}).status_code == 403
        session = client.post("/sessions", headers=headers).json()["session_id"]
        response = client.post(f"/sessions/{session}/messages", headers=headers, json={"message": "Hi"})
        assert response.json() == {"content": "Hello"}
        assert client.post(f"/sessions/{session}/messages", headers=headers, json={"message": " "}).status_code == 400


class WriteProvider(LLMProvider):
    async def generate(self, messages, tools=None):
        from app.llm.schemas import ToolCall
        if messages[-1].role.value == "tool":
            return LLMResponse(content="Finished")
        return LLMResponse(tool_calls=[ToolCall(id="write-1", name="create_folder", arguments={"path": "new"})])


import pytest


@pytest.mark.parametrize("approved,valid_id,exists", [(True, True, True), (False, True, False), (True, False, False)])
def test_websocket_approval_is_bound_to_operation(tmp_path, approved, valid_id, exists):
    settings = Settings(_env_file=None, llm_provider="ollama", llm_model="test",
                        api_token=TOKEN, workspace_dir=tmp_path)
    with TestClient(create_app(settings, WriteProvider())) as client:
        with client.websocket_connect("/ws", headers={"Authorization": "Bearer " + TOKEN}) as ws:
            assert ws.receive_json()["type"] == "session"
            ws.send_json({"type": "message", "message": "Create a folder"})
            assert ws.receive_json()["type"] == "thinking"
            assert ws.receive_json()["type"] == "executing"
            request = ws.receive_json()
            assert request["type"] == "confirmation_required"
            assert not (tmp_path / "new").exists()
            ws.send_json({"type": "confirmation", "approved": approved,
                          "confirmation_id": request["confirmation_id"] if valid_id else "wrong"})
            assert ws.receive_json()["type"] == "tool_result"
            assert ws.receive_json()["type"] == "thinking"
            assert ws.receive_json()["type"] == "completed"
            assert (tmp_path / "new").exists() == exists
