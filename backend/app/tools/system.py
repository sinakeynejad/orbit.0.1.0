import platform
from app.tools.base import Tool, ToolArguments


def get_system_info(args):
    return {"system": platform.system(), "release": platform.release(),
            "machine": platform.machine(), "python": platform.python_version()}


def system_tool():
    return Tool("get_system_info", "Read operating system and Python version.",
                ToolArguments, get_system_info)
