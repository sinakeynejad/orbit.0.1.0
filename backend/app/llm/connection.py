"""A disposable model probe; never runs tools or modifies saved configuration."""
import asyncio
from time import perf_counter
import httpx
from app.core.exceptions import ProviderError
from app.llm.client import create_provider
from app.llm.schemas import Message, MessageRole


def failure(code, message):
    return {"ok": False, "code": code, "message": message}


async def check_connection(config):
    if not config.llm_model:
        return failure("model_required", "Enter a model name before testing.")
    if config.llm_provider == "openai" and not config.llm_api_key:
        return failure("key_required", "Enter a model API key before testing.")
    provider = create_provider(config)
    started = perf_counter()
    try:
        async with asyncio.timeout(30):
            result = await provider.generate([Message(role=MessageRole.USER, content="Reply with only OK.")])
        if not result.content or not result.content.strip() or result.tool_calls:
            return failure("invalid_response", "The model did not return a plain text reply. Check that it supports chat.")
        return {"ok": True, "code": "connected", "message": "The selected model responded successfully.",
                "latency_ms": round((perf_counter() - started) * 1000)}
    except (TimeoutError, httpx.TimeoutException):
        return failure("timeout", "No response within 30 seconds. The model may still be loading; wait and retry.")
    except ProviderError as exc:
        cause = exc.__cause__
        if isinstance(cause, httpx.TimeoutException):
            return failure("timeout", "The request timed out. Check the server or wait for the model to load, then retry.")
        if isinstance(cause, httpx.HTTPStatusError):
            status = cause.response.status_code
            if status in (401, 403):
                return failure("authentication", "Access was rejected. Check the API key and permission to use this model.")
            if status == 404:
                return failure("not_found", "Model or endpoint not found. Check the model name and Base URL; for Ollama, install the model first.")
            if status == 429:
                return failure("rate_limit", "Request limit or quota reached. Check provider billing and limits, or wait and retry.")
            if status >= 500:
                return failure("service_error", "The model service failed. Check its status or server logs, then retry.")
            return failure("request_rejected", "The service rejected this chat request. Check model compatibility and Base URL.")
        if isinstance(cause, httpx.HTTPError):
            return failure("unreachable", "Cannot reach the service. Check the Base URL and network; for Ollama, make sure it is running.")
        return failure("invalid_response", "The service returned an incomplete or invalid chat response. Check the model and endpoint, then retry.")
    finally:
        await provider.aclose()
