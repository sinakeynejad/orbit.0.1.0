class AssistantError(Exception):
    """An expected failure safe to describe to the client."""


class ProviderError(AssistantError):
    pass


class ToolError(AssistantError):
    pass


class AgentLimitError(AssistantError):
    pass
