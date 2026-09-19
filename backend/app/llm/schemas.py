from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    role: MessageRole
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_role_fields(self) -> "Message":
        if self.tool_calls and self.role != MessageRole.ASSISTANT:
            raise ValueError("Only assistant messages can contain tool calls.")

        if self.role == MessageRole.TOOL:
            if self.tool_call_id is None:
                raise ValueError("Tool messages must include tool_call_id.")

            if self.content is None:
                raise ValueError("Tool messages must include content.")

        elif self.tool_call_id is not None:
            raise ValueError("Only tool messages can include tool_call_id.")

        if self.content is None and not self.tool_calls:
            raise ValueError("A message must contain content or tool calls.")

        return self


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
