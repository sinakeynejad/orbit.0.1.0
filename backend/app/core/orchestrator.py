import json
import asyncio
from app.core.exceptions import AgentLimitError, ProviderError
from app.llm.schemas import Message, MessageRole


class Orchestrator:
    def __init__(self, provider, executor, max_steps=8):
        self.provider = provider
        self.executor = executor
        self.max_steps = max_steps

    async def run(self, conversation, text, confirm=None, emit=None):
        async def event(kind, **data):
            if emit:
                await emit({"type": kind, **data})
        turn = [Message(role=MessageRole.USER, content=text)]
        base = conversation.messages()
        try:
            for _ in range(self.max_steps):
                await event("thinking")
                response = await self.provider.generate(base + turn, self.executor.registry.schemas())
                if not response.tool_calls:
                    if not response.content or not response.content.strip():
                        raise ProviderError("Language model returned an empty answer.")
                    turn.append(Message(role=MessageRole.ASSISTANT, content=response.content))
                    conversation.commit(turn)
                    return response.content
                if len(response.tool_calls) > 8 or len({c.id for c in response.tool_calls}) != len(response.tool_calls):
                    raise ProviderError("Invalid or excessive tool calls.")
                turn.append(Message(role=MessageRole.ASSISTANT, content=response.content,
                                    tool_calls=response.tool_calls))
                for call in response.tool_calls:
                    await event("executing", tool=call.name, call_id=call.id, arguments=call.arguments)
                    result = await self.executor.execute(call, confirm)
                    turn.append(Message(role=MessageRole.TOOL, tool_call_id=call.id,
                                        content=json.dumps(result, ensure_ascii=False)))
                    await event("tool_result", call_id=call.id, result=result)
                    if asyncio.current_task().cancelling():
                        raise asyncio.CancelledError
            raise AgentLimitError("Agent step limit reached. Some tools may already have executed.")
        except BaseException:
            if len(turn) > 1:
                completed = {m.tool_call_id for m in turn if m.tool_call_id}
                for message in list(turn):
                    for call in message.tool_calls:
                        if call.id not in completed:
                            turn.append(Message(role=MessageRole.TOOL, tool_call_id=call.id,
                                content='{"ok": false, "error": "Run interrupted; execution outcome unknown. Check activity and filesystem before retrying."}'))
                turn.append(Message(role=MessageRole.ASSISTANT, content="Run interrupted. Completed operations were not undone."))
                conversation.commit(turn)
            raise
