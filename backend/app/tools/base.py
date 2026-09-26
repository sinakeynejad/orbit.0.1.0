from dataclasses import dataclass
from typing import Callable, Any
from pydantic import BaseModel, ConfigDict
from app.tools.permissions import PermissionLevel


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments_model: type[ToolArguments]
    handler: Callable[[Any], dict]
    permission: PermissionLevel = PermissionLevel.SAFE

    def schema(self):
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.arguments_model.model_json_schema(),
        }}
