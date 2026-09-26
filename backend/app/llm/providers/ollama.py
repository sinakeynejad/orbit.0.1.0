from uuid import uuid4
import httpx
from pydantic import ValidationError
from app.core.exceptions import ProviderError
from app.llm.base import LLMProvider
from app.llm.schemas import LLMResponse, ToolCall


class OllamaProvider(LLMProvider):
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            base_url=str(settings.llm_base_url or "http://127.0.0.1:11434").rstrip("/") + "/",
            timeout=settings.llm_timeout_seconds,
            trust_env=False,
        )
        self.owns_client = client is None

    async def generate(self, messages, tools=None):
        history = []
        names = {}
        for message in messages:
            item = {"role": message.role.value, "content": message.content or ""}
            if message.tool_calls:
                item["tool_calls"] = [
                    {"function": {"name": call.name, "arguments": call.arguments}}
                    for call in message.tool_calls
                ]
                names.update({call.id: call.name for call in message.tool_calls})
            if message.tool_call_id:
                item["tool_name"] = names[message.tool_call_id]
            history.append(item)
        options = {"num_predict": self.settings.llm_max_tokens}
        if self.settings.llm_temperature is not None:
            options["temperature"] = self.settings.llm_temperature
        payload = {"model": self.settings.llm_model, "messages": history,
                   "stream": False, "options": options}
        if tools:
            payload["tools"] = tools
        try:
            response = await self.client.post("api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("done") is False:
                raise ProviderError("Language model returned an incomplete response. Please retry.")
            if data.get("done_reason") == "length":
                raise ProviderError("Model output reached its token limit; increase LLM_MAX_TOKENS.")
            message = data["message"]
            return LLMResponse(
                content=message.get("content"),
                tool_calls=[ToolCall(id=uuid4().hex, name=call["function"]["name"],
                                     arguments=call["function"]["arguments"])
                            for call in message.get("tool_calls", [])],
            )
        except httpx.TimeoutException as exc:
            raise ProviderError("Language model request timed out.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Cannot reach the language model or the request was rejected.") from exc
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise ProviderError("Language model returned an invalid response.") from exc

    async def aclose(self):
        if self.owns_client:
            await self.client.aclose()
