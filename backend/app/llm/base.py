from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.llm.schemas import LLMResponse, Message


class LLMProvider(ABC):
    """Common contract for language model providers."""

    @abstractmethod
    async def generate(
        self,
        messages: Sequence[Message],
    ) -> LLMResponse:
        """Generate a response from the conversation history."""
        raise NotImplementedError
