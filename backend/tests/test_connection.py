import json
import httpx
import pytest
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.core.config import Settings
from app.llm.providers.openai import OpenAIProvider
from app.llm.providers.ollama import OllamaProvider
from tests.test_api import TOKEN, ReplyProvider


@pytest.mark.parametrize("provider", ["ollama", "openai"])
@pytest.mark.parametrize("outcome,code", [(200,"connected"),(401,"authentication"),(403,"authentication"),(404,"not_found"),(429,"rate_limit"),(503,"service_error"),(400,"request_rejected"),("timeout","timeout"),("offline","unreachable"),("invalid","invalid_response")])
def test_connection_probe(tmp_path, monkeypatch, provider, outcome, code):
    requests=[]
    clients=[]
    def handler(request):
        requests.append(request)
        if outcome=="timeout": raise httpx.ReadTimeout("secret-detail",request=request)
        if outcome=="offline": raise httpx.ConnectError("secret-detail",request=request)
        if outcome=="invalid": return httpx.Response(200,json={})
        data=({"choices":[{"finish_reason":"stop","message":{"content":"OK"}}]} if provider=="openai" else {"done":True,"message":{"content":"OK"}})
        return httpx.Response(outcome,json=data if outcome==200 else {"error":"secret-detail"})
    def factory(config):
        client=httpx.AsyncClient(base_url="http://fake/",transport=httpx.MockTransport(handler))
        clients.append(client)
        instance=(OpenAIProvider if provider=="openai" else OllamaProvider)(config,client)
        instance.owns_client=True
        return instance
    monkeypatch.setattr("app.llm.connection.create_provider",factory)
    config=Settings(_env_file=None,api_token=TOKEN,llm_model="saved-model",workspace_dir=tmp_path/"workspace",data_dir=tmp_path)
    original=ReplyProvider()
    with TestClient(create_app(config,original)) as client:
        response=client.post("/settings/test-connection",headers={"Authorization":"Bearer "+TOKEN},json={"llm_provider":provider,"llm_model":"draft-model","llm_api_key":"test-key"})
        assert response.status_code==200
        data=response.json()
        assert data["code"]==code
        assert data["ok"] is (outcome==200)
        assert "secret-detail" not in response.text and "test-key" not in response.text
        assert client.app.state.config.llm_model=="saved-model"
        assert client.app.state.assistant.orchestrator.provider is original
        assert not client.app.state.assistant.sessions
        assert not (tmp_path/"settings.json").exists()
    assert clients[0].is_closed
    payload=json.loads(requests[0].content)
    assert payload["model"]=="draft-model" and "tools" not in payload
    assert payload["messages"]==[{"role":"user","content":"Reply with only OK."}]


@pytest.mark.parametrize("body,code", [({"llm_provider":"ollama","llm_model":" "},"model_required"),({"llm_provider":"openai","llm_model":"test"},"key_required"),({"llm_provider":"ollama","llm_model":"test","llm_base_url":"broken"},"invalid_settings")])
def test_validation_without_network(tmp_path,monkeypatch,body,code):
    def forbidden(config): raise AssertionError("No network request expected")
    monkeypatch.setattr("app.llm.connection.create_provider",forbidden)
    config=Settings(_env_file=None,api_token=TOKEN,workspace_dir=tmp_path,data_dir=tmp_path)
    with TestClient(create_app(config,ReplyProvider())) as client:
        assert client.post("/settings/test-connection",json=body).status_code==401
        assert client.post("/settings/test-connection",headers={"Authorization":"Bearer "+TOKEN},json=body).json()["code"]==code


def test_saved_key_not_sent_to_new_endpoint(tmp_path,monkeypatch):
    def forbidden(config): raise AssertionError("Saved key must not leave for a new endpoint")
    monkeypatch.setattr("app.llm.connection.create_provider",forbidden)
    config=Settings(_env_file=None,api_token=TOKEN,llm_provider="openai",llm_api_key="saved-secret",workspace_dir=tmp_path,data_dir=tmp_path)
    with TestClient(create_app(config,ReplyProvider())) as client:
        result=client.post("/settings/test-connection",headers={"Authorization":"Bearer "+TOKEN},json={"llm_provider":"openai","llm_model":"test","llm_base_url":"https://new.example/v1"})
        assert result.json()["code"]=="key_required"
        assert "saved-secret" not in result.text
