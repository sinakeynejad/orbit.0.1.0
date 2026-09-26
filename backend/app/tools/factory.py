from app.tools.apps import application_tool
from app.tools.files import FileTools
from app.tools.registry import ToolRegistry
from app.tools.system import system_tool
from app.tools.desktop import desktop_tools


def create_registry(config):
    registry = ToolRegistry()
    for tool in [system_tool(), application_tool(config.allowed_applications),
                 *FileTools(config.workspace_dir).tools(), *desktop_tools(config.workspace_dir)]:
        registry.register(tool)
    return registry
