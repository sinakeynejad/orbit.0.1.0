from app.core.exceptions import ToolError


class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool):
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name):
        if name not in self._tools:
            raise ToolError("Unknown tool.")
        return self._tools[name]

    def schemas(self):
        return [tool.schema() for tool in self._tools.values()]
