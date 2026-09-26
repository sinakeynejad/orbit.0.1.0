from pathlib import Path
import pytest
from app.llm.schemas import ToolCall
from app.tools.files import FileTools
from app.tools.registry import ToolRegistry
from app.tools.executor import ToolExecutor


def executor(root):
    registry = ToolRegistry()
    for tool in FileTools(root).tools():
        registry.register(tool)
    return ToolExecutor(registry)


@pytest.mark.parametrize("path", ["../escape", "C:/Windows", "/etc", "file:stream"])
async def test_escape_blocked(tmp_path, path):
    result = await executor(tmp_path).execute(ToolCall(id="1", name="list_files", arguments={"path": path}))
    assert not result["ok"]


async def test_write_needs_approval(tmp_path):
    call = ToolCall(id="1", name="create_folder", arguments={"path": "new"})
    result = await executor(tmp_path).execute(call)
    assert not result["ok"]
    assert not (tmp_path / "new").exists()


async def test_approved_write(tmp_path):
    async def approve(call):
        assert call.arguments == {"path": "new"}
        return True
    result = await executor(tmp_path).execute(ToolCall(id="1", name="create_folder", arguments={"path": "new"}), approve)
    assert result["ok"] and (tmp_path / "new").is_dir()


async def test_extra_arguments_rejected(tmp_path):
    result = await executor(tmp_path).execute(ToolCall(id="1", name="list_files", arguments={"shell": "evil"}))
    assert not result["ok"]


async def test_rename_cannot_overwrite(tmp_path):
    (tmp_path / "a").write_text("original")
    (tmp_path / "b").write_text("keep")
    async def approve(call):
        return True
    result = await executor(tmp_path).execute(ToolCall(id="1", name="rename_file", arguments={"path": "a", "new_name": "b"}), approve)
    assert not result["ok"]
    assert (tmp_path / "b").read_text() == "keep"
