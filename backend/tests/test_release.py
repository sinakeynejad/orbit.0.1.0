import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.schemas import LLMResponse, Message, ToolCall
from app.llm.providers.openai import OpenAIProvider
from app.memory.store import Store
from app.memory.conversation import Conversation
from app.tools.files import FileTools, PathArguments, TransferArguments, WriteArguments
from app.core.exceptions import ToolError, ProviderError


class WaitingProvider(LLMProvider):
    async def generate(self, messages, tools=None):
        await asyncio.sleep(60)
        return LLMResponse(content="Done")


def test_browser_cookie_auth_and_cancel(tmp_path):
    config=Settings(_env_file=None,llm_model="test",api_token="x"*40,workspace_dir=tmp_path,data_dir=tmp_path)
    with TestClient(create_app(config, WaitingProvider())) as client:
        assert client.post("/auth", headers={"Authorization":"Bearer "+"x"*40,"Origin":"http://testserver"}).status_code==200
        assert client.get("/settings").status_code==200
        assert client.get("/settings",headers={"Origin":"https://evil.test"}).status_code==403
        with client.websocket_connect("/ws",headers={"Origin":"http://testserver"}) as ws:
            sid=ws.receive_json()["session_id"]
            ws.send_json({"type":"message","message":"wait"})
            assert ws.receive_json()["type"]=="thinking"
            ws.send_json({"type":"cancel"})
            assert ws.receive_json()["type"]=="cancelled"
        assert any(s["id"]==sid for s in client.get("/sessions").json())


def test_persistent_memory(tmp_path):
    store=Store(tmp_path/"db.sqlite3")
    conv=Conversation();conv.commit([Message(role="user",content="hello"),Message(role="assistant",content="hi")])
    store.save("one",conv);store.audit({"type":"tool_result","result":{"ok":True}});store.close()
    store=Store(tmp_path/"db.sqlite3")
    assert store.load()["one"].turns[0][0].content=="hello"
    assert store.recent_audit()[0]["result"]["ok"]
    store.delete("one");assert not store.load();store.close()


def test_file_lifecycle(tmp_path):
    files=FileTools(tmp_path)
    files.write_text(WriteArguments(path="a.txt",text="hello"))
    files.copy_file(TransferArguments(source="a.txt",destination="b.txt"))
    files.move_file(TransferArguments(source="b.txt",destination="c.txt"))
    assert files.read_text(PathArguments(path="c.txt"))["text"]=="hello"
    result=files.trash_file(PathArguments(path="c.txt"))
    assert (tmp_path/result["recoverable_path"]).read_text()=="hello"
    assert not (tmp_path/"c.txt").exists()
    with pytest.raises(ToolError): files.resolve("NUL.txt")
    with pytest.raises(ToolError): files.resolve(".trash/item")
    with pytest.raises(FileExistsError): files.write_text(WriteArguments(path="a.txt",text="overwrite"))


async def test_openai_tool_roundtrip():
    async def handler(request):
        payload=json.loads(request.content)
        assert payload["messages"][-1]["tool_call_id"]=="call-1"
        assert json.loads(payload["messages"][1]["tool_calls"][0]["function"]["arguments"])=={}
        return httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":"Done"}}]})
    async with httpx.AsyncClient(base_url="http://test/",transport=httpx.MockTransport(handler)) as client:
        provider=OpenAIProvider(SimpleNamespace(llm_model="test",llm_max_tokens=100,llm_temperature=None),client)
        response=await provider.generate([Message(role="user",content="info"),Message(role="assistant",tool_calls=[ToolCall(id="call-1",name="info")]),Message(role="tool",content="{}",tool_call_id="call-1")])
        assert response.content=="Done"


async def test_openai_rejects_truncated_calls():
    async with httpx.AsyncClient(base_url="http://test/",transport=httpx.MockTransport(lambda r:httpx.Response(200,json={"choices":[{"finish_reason":"length","message":{}}]}))) as client:
        provider=OpenAIProvider(SimpleNamespace(llm_model="test",llm_max_tokens=100,llm_temperature=None),client)
        with pytest.raises(ProviderError): await provider.generate([])


def test_voice_requires_key(tmp_path):
    config=Settings(_env_file=None,llm_model="test",api_token="x"*40,workspace_dir=tmp_path,data_dir=tmp_path,llm_api_key=None,voice_api_key=None)
    with TestClient(create_app(config,WaitingProvider())) as client:
        headers={"Authorization":"Bearer "+"x"*40}
        assert client.post("/voice/speak",headers=headers,json={"text":"hello"}).status_code==400
        assert client.post("/voice/transcribe",headers=headers,files={"file":("recording.webm",b"audio")}).status_code==400


def test_settings_do_not_return_secrets(tmp_path):
    config=Settings(_env_file=None,llm_model="test",api_token="x"*40,workspace_dir=tmp_path,data_dir=tmp_path,llm_api_key="private-key")
    with TestClient(create_app(config,WaitingProvider())) as client:
        headers={"Authorization":"Bearer "+"x"*40}
        response=client.get("/settings",headers=headers)
        assert response.json()["has_api_key"]
        assert "private-key" not in response.text
        response=client.put("/settings",headers=headers,json={"llm_provider":"ollama","llm_model":"new-model","workspace_dir":str(tmp_path)})
        assert response.status_code==200
        assert client.get("/settings",headers=headers).json()["llm_model"]=="new-model"


async def test_cancel_waits_for_active_tool():
    import time
    from app.tools.base import Tool, ToolArguments
    from app.tools.registry import ToolRegistry
    from app.tools.executor import ToolExecutor
    completed=[]
    def slow(args):
        time.sleep(0.08)
        completed.append(True)
        return {"done":True}
    registry=ToolRegistry();registry.register(Tool("slow","test",ToolArguments,slow))
    task=asyncio.create_task(ToolExecutor(registry).execute(ToolCall(id="a",name="slow")))
    await asyncio.sleep(0.02);task.cancel()
    result=await task
    assert result["ok"] and completed
