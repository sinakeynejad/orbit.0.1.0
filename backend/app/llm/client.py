from app.core.exceptions import ProviderError
from app.llm.base import LLMProvider
from app.llm.providers.ollama import OllamaProvider
from app.llm.providers.openai import OpenAIProvider


class UnconfiguredProvider(LLMProvider):
    async def generate(self, messages, tools=None):
        raise ProviderError("Choose a provider and enter a model in Settings first.")


def create_provider(settings):
    if not settings.llm_model or (settings.llm_provider == "openai" and not settings.llm_api_key):
        return UnconfiguredProvider()
    return OllamaProvider(settings) if settings.llm_provider == "ollama" else OpenAIProvider(settings)
