from abc import ABC, abstractmethod
from collections.abc import Sequence
from app.llm.schemas import LLMResponse, Message


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, messages: Sequence[Message], tools: list[dict] | None = None) -> LLMResponse:
        raise NotImplementedError

    async def aclose(self) -> None:
        """Release provider resources at application shutdown."""
