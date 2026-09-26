import httpx
import pytest
from types import SimpleNamespace
from app.llm.providers.ollama import OllamaProvider
from app.llm.schemas import Message
from app.core.exceptions import ProviderError


def config():
    return SimpleNamespace(llm_model="test", llm_max_tokens=100, llm_temperature=None)


async def test_tool_response_parsed():
    async def handle(request):
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={"message": {"content": "", "tool_calls": [
            {"function": {"name": "get_system_info", "arguments": {}}}]}})
    async with httpx.AsyncClient(base_url="http://test/", transport=httpx.MockTransport(handle)) as client:
        result = await OllamaProvider(config(), client).generate([Message(role="user", content="hello")])
    assert result.tool_calls[0].name == "get_system_info"


@pytest.mark.parametrize("status", [401, 500])
async def test_http_error_sanitized(status):
    async with httpx.AsyncClient(base_url="http://test/", transport=httpx.MockTransport(
            lambda request: httpx.Response(status, text="secret detail"))) as client:
        with pytest.raises(ProviderError) as error:
            await OllamaProvider(config(), client).generate([])
    assert "secret detail" not in str(error.value)
