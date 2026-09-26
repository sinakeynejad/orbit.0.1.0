import json
import httpx
from app.core.exceptions import ProviderError
from app.llm.base import LLMProvider
from app.llm.schemas import LLMResponse, ToolCall


class OpenAIProvider(LLMProvider):
    def __init__(self, settings, client=None):
        self.settings = settings
        self.owns_client = client is None
        self.client = client or httpx.AsyncClient(
            base_url=str(settings.llm_base_url or "https://api.openai.com/v1").rstrip("/") + "/",
            headers={"Authorization": "Bearer " + settings.llm_api_key.get_secret_value()},
            timeout=settings.llm_timeout_seconds, trust_env=False)

    async def generate(self, messages, tools=None):
        history = []
        for message in messages:
            item = {"role": message.role.value, "content": message.content}
            if message.tool_calls:
                item["tool_calls"] = [{"id": c.id, "type": "function", "function": {
                    "name": c.name, "arguments": json.dumps(c.arguments)}} for c in message.tool_calls]
            if message.tool_call_id:
                item["tool_call_id"] = message.tool_call_id
            history.append(item)
        payload = {"model": self.settings.llm_model, "messages": history,
                   "max_completion_tokens": self.settings.llm_max_tokens}
        if tools:
            payload["tools"] = tools
        if self.settings.llm_temperature is not None:
            payload["temperature"] = self.settings.llm_temperature
        try:
            response = await self.client.post("chat/completions", json=payload)
            response.raise_for_status()
            choice = response.json()["choices"][0]
            if choice["finish_reason"] in {"length", "content_filter"}:
                raise ProviderError("Model response was truncated or filtered; no tools were executed.")
            message = choice["message"]
            return LLMResponse(content=message.get("content"), tool_calls=[
                ToolCall(id=c["id"], name=c["function"]["name"],
                         arguments=json.loads(c["function"]["arguments"]))
                for c in message.get("tool_calls") or []])
        except httpx.TimeoutException as exc:
            raise ProviderError("Model request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"Model service rejected the request (HTTP {exc.response.status_code}). Check model, quota and credentials.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Cannot connect to the model service.") from exc
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise ProviderError("Model returned an invalid response.") from exc

    async def aclose(self):
        if self.owns_client:
            await self.client.aclose()
