import pytest
from app.core.assistant import Assistant
from app.core.orchestrator import Orchestrator
from app.core.exceptions import AgentLimitError
from app.llm.base import LLMProvider
from app.llm.schemas import LLMResponse, ToolCall
from app.memory.conversation import Conversation
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry
from app.tools.system import system_tool


class FakeProvider(LLMProvider):
    def __init__(self, loop=False):
        self.calls = 0
        self.loop = loop

    async def generate(self, messages, tools=None):
        self.calls += 1
        if self.loop or self.calls == 1:
            return LLMResponse(tool_calls=[ToolCall(id=str(self.calls), name="get_system_info")])
        assert messages[-1].role.value == "tool"
        assert '"ok": true' in messages[-1].content
        return LLMResponse(content="Done")


def orchestrator(provider, max_steps=8):
    registry = ToolRegistry()
    registry.register(system_tool())
    return Orchestrator(provider, ToolExecutor(registry), max_steps)


async def test_full_tool_roundtrip_and_memory():
    assistant = Assistant(orchestrator(FakeProvider()))
    first = assistant.create_session()
    second = assistant.create_session()
    assert await assistant.chat(first, "System info") == "Done"
    assert len(assistant.sessions[first][0].messages()) == 5
    assert len(assistant.sessions[second][0].messages()) == 1


async def test_step_limit_preserves_completed_operations():
    conversation = Conversation()
    with pytest.raises(AgentLimitError):
        await orchestrator(FakeProvider(loop=True), 2).run(conversation, "loop")
    assert conversation.turns
    assert conversation.turns[-1][-1].content.startswith("Run interrupted")
