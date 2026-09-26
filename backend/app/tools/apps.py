from pathlib import Path
import subprocess
from pydantic import Field
from app.core.exceptions import ToolError
from app.tools.base import Tool, ToolArguments
from app.tools.permissions import PermissionLevel


class ApplicationArguments(ToolArguments):
    name: str = Field(min_length=1, max_length=100)


def application_tool(allowlist):
    def open_application(args):
        executable = allowlist.get(args.name)
        if executable is None:
            raise ToolError("Application is not in the configured allowlist.")
        path = Path(executable)
        if not path.is_absolute() or not path.is_file() or path.suffix.lower() != ".exe":
            raise ToolError("Allowlist entry must point to an existing absolute .exe path.")
        subprocess.Popen([str(path)], shell=False)
        return {"application": args.name, "started": True}
    return Tool("open_application", "Open a configured application by alias (no arguments).",
                ApplicationArguments, open_application, PermissionLevel.CONFIRM)
