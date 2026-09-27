import httpx
import pytest
from fastapi.testclient import TestClient
from app.api.main import create_app
from app.core.config import Settings
from tests.test_api import TOKEN, ReplyProvider


@pytest.mark.parametrize("outcome,expected", [("models",200),("empty",200),("invalid",400),("offline",400),("timeout",400),("rejected",400)])
def test_model_list(tmp_path,monkeypatch,outcome,expected):
    requests=[]
    original=httpx.AsyncClient
    def handler(request):
        requests.append(request)
        if outcome=="offline": raise httpx.ConnectError("private detail",request=request)
        if outcome=="timeout": raise httpx.ReadTimeout("private detail",request=request)
        if outcome=="rejected":return httpx.Response(403,json={"error":"private detail"})
        data={"models":[{"name":"z:latest"},{"name":"a:7b"},{"name":"z:latest"}]}
        if outcome=="empty":data={"models":[]}
        if outcome=="invalid":data={"models":[{"name":42}]}
        return httpx.Response(200,json=data)
    def factory(**kwargs):
        assert kwargs["trust_env"] is False
        return original(**kwargs,transport=httpx.MockTransport(handler))
    monkeypatch.setattr(httpx,"AsyncClient",factory)
    config=Settings(_env_file=None,api_token=TOKEN,workspace_dir=tmp_path,data_dir=tmp_path,llm_model="saved")
    with TestClient(create_app(config,ReplyProvider())) as client:
        assert client.post("/settings/ollama-models",json={}).status_code==401
        result=client.post("/settings/ollama-models",headers={"Authorization":"Bearer "+TOKEN},json={"llm_base_url":"http://localhost:1234/prefix/"})
        assert result.status_code==expected
        assert "private detail" not in result.text
        if outcome=="models":assert result.json()=={"models":["a:7b","z:latest"]}
        if outcome=="empty":assert result.json()=={"models":[]}
        assert client.app.state.config.llm_model=="saved"
        assert not (tmp_path/"settings.json").exists()
    assert len(requests)==1
    assert str(requests[0].url)=="http://localhost:1234/prefix/api/tags"
    assert "authorization" not in requests[0].headers


def test_invalid_model_list_url(tmp_path):
    config=Settings(_env_file=None,api_token=TOKEN,workspace_dir=tmp_path,data_dir=tmp_path)
    with TestClient(create_app(config,ReplyProvider())) as client:
        result=client.post("/settings/ollama-models",headers={"Authorization":"Bearer "+TOKEN},json={"llm_base_url":"not-a-url"})
        assert result.status_code==400
        assert "valid Ollama Base URL" in result.json()["detail"]
