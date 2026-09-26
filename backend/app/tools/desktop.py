from pathlib import Path
from uuid import uuid4
from app.tools.base import Tool, ToolArguments
from app.tools.permissions import PermissionLevel
from app.core.exceptions import ToolError
from pydantic import Field


class TextArguments(ToolArguments):
    text: str = Field(max_length=20000)


def desktop_tools(root):
    def screenshot(args):
        from PIL import ImageGrab
        path = Path(root) / ("screenshot-" + uuid4().hex[:12] + ".png")
        ImageGrab.grab().save(path)
        return {"path": path.name}

    def read_clipboard(args):
        import pyperclip
        try: return {"text": pyperclip.paste()[:20000]}
        except pyperclip.PyperclipException as exc: raise ToolError("Clipboard unavailable.") from exc

    def write_clipboard(args):
        import pyperclip
        try: pyperclip.copy(args.text)
        except pyperclip.PyperclipException as exc: raise ToolError("Clipboard unavailable.") from exc
        return {"copied": True}

    return [Tool("screenshot", "Capture the current screen to a PNG in workspace.", ToolArguments, screenshot, PermissionLevel.CONFIRM),
            Tool("read_clipboard", "Read clipboard text; it will be sent to the selected model.", ToolArguments, read_clipboard, PermissionLevel.CONFIRM),
            Tool("write_clipboard", "Replace clipboard text.", TextArguments, write_clipboard, PermissionLevel.CONFIRM)]
