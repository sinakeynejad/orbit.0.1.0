"""Explicit UI test server: fake provider, isolated temporary data, fixed test-only token."""
import tempfile
from pathlib import Path
import uvicorn
from app.api.main import create_app
from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.schemas import LLMResponse, ToolCall

class PreviewProvider(LLMProvider):
    async def generate(self, messages, tools=None):
        if messages[-1].role.value == "tool":
            return LLMResponse(content="Test completed. The tool result has been received.")
        return LLMResponse(tool_calls=[ToolCall(id="preview-call",name="create_folder",arguments={"path":"ui-test-folder"})])

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        c=Settings(_env_file=None,llm_model="UI test provider",api_token="preview-token-"+"x"*32,workspace_dir=Path(directory),data_dir=Path(directory))
        uvicorn.run(create_app(c,PreviewProvider()),host="127.0.0.1",port=8765)
