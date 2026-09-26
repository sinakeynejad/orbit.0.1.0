import httpx
import pytest
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.core.config import Settings
from app.core.exceptions import ProviderError
from app.llm.providers.ollama import OllamaProvider
from tests.test_api import TOKEN, WriteProvider, ReplyProvider


def config(tmp_path):
    return Settings(_env_file=None,llm_provider="ollama",llm_model="test",api_token=TOKEN,
                    workspace_dir=tmp_path/"workspace",data_dir=tmp_path)


def test_malformed_confirmation_keeps_socket_alive(tmp_path):
    with TestClient(create_app(config(tmp_path),WriteProvider())) as client:
        with client.websocket_connect("/ws",headers={"Authorization":"Bearer "+TOKEN}) as ws:
            ws.receive_json()
            ws.send_json({"type":"message","message":"create"})
            ws.receive_json();ws.receive_json()
            pending=ws.receive_json()
            ws.send_json({"type":"confirmation","confirmation_id":[],"approved":True})
            assert ws.receive_json()["type"]=="error"
            ws.send_json({"type":"confirmation","confirmation_id":pending["confirmation_id"],"approved":True})
            assert ws.receive_json()["type"]=="tool_result"
            ws.receive_json()
            assert ws.receive_json()["type"]=="completed"


def test_full_session_capacity_returns_controlled_error(tmp_path):
    with TestClient(create_app(config(tmp_path),ReplyProvider())) as client:
        client.app.state.assistant.max_sessions=0
        with client.websocket_connect("/ws",headers={"Authorization":"Bearer "+TOKEN}) as ws:
            event=ws.receive_json()
            assert event["type"]=="error"
            assert "limit" in event["message"].lower()


def test_settings_disk_failure_does_not_replace_provider(tmp_path,monkeypatch):
    from pathlib import Path
    original=ReplyProvider()
    with TestClient(create_app(config(tmp_path),original),raise_server_exceptions=False) as client:
        old_write=Path.write_text
        def fail(path,*args,**kwargs):
            if path.name=="settings.tmp": raise OSError("private disk detail")
            return old_write(path,*args,**kwargs)
        monkeypatch.setattr(Path,"write_text",fail)
        response=client.put("/settings",headers={"Authorization":"Bearer "+TOKEN},
            json={"llm_provider":"ollama","llm_model":"new"})
        assert response.status_code==400
        assert "private disk detail" not in response.text
        assert client.app.state.assistant.orchestrator.provider is original
        assert client.app.state.config.llm_model=="test"


def test_transcription_keeps_audio_format(tmp_path,monkeypatch):
    from app.voice.stt import OpenAISpeechToText
    received=[]
    async def transcribe(self,data,filename):
        received.append(filename)
        return "transcript"
    monkeypatch.setattr(OpenAISpeechToText,"transcribe",transcribe)
    with TestClient(create_app(config(tmp_path),ReplyProvider())) as client:
        response=client.post("/voice/transcribe",headers={"Authorization":"Bearer "+TOKEN},
            files={"file":("sample.wav",b"RIFF-sample","audio/wav")})
        assert response.status_code==200
        assert received==["recording.wav"]


async def test_incomplete_ollama_response_cannot_execute_tools(tmp_path):
    async with httpx.AsyncClient(base_url="http://test/",transport=httpx.MockTransport(
        lambda request: httpx.Response(200,json={"done":False,"message":{"content":"partial",
          "tool_calls":[{"function":{"name":"create_folder","arguments":{"path":"new"}}}]}}))) as client:
        with pytest.raises(ProviderError):
            await OllamaProvider(config(tmp_path),client).generate([])
