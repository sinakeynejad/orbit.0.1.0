from pathlib import Path
import shutil
from uuid import uuid4
from itertools import islice
from pydantic import Field
from app.core.exceptions import ToolError
from app.tools.base import Tool, ToolArguments
from app.tools.permissions import PermissionLevel


class PathArguments(ToolArguments):
    path: str = Field(default=".", min_length=1, max_length=1024)


class RenameArguments(ToolArguments):
    path: str = Field(min_length=1, max_length=1024)
    new_name: str = Field(min_length=1, max_length=255)


class TransferArguments(ToolArguments):
    source: str = Field(min_length=1, max_length=1024)
    destination: str = Field(min_length=1, max_length=1024)


class WriteArguments(ToolArguments):
    path: str = Field(min_length=1, max_length=1024)
    text: str = Field(max_length=20000)


class FileTools:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, value):
        path = Path(value)
        if path.is_absolute() or path.drive or ":" in value:
            raise ToolError("Use a relative path inside the workspace.")
        if any(part.casefold() in {".trash"} or part.endswith((" ", ".")) or part.split(".")[0].upper() in
               {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1,10)], *[f"LPT{i}" for i in range(1,10)]}
               for part in path.parts if part not in {".", ".."}):
            raise ToolError("Reserved path component.")
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root):
            raise ToolError("Path escapes the workspace.")
        return target

    def list_files(self, args):
        path = self.resolve(args.path)
        if not path.is_dir():
            raise ToolError("Directory does not exist.")
        entries = list(islice(path.iterdir(), 201))
        return {"entries": [{"name": item.name, "is_directory": item.is_dir()}
                            for item in entries[:200]], "truncated": len(entries) > 200}

    def create_folder(self, args):
        path = self.resolve(args.path)
        path.mkdir(exist_ok=False)
        return {"path": str(path.relative_to(self.root))}

    def rename_file(self, args):
        source = self.resolve(args.path)
        if source == self.root or not source.is_file():
            raise ToolError("Source must be a file inside the workspace.")
        if any(c in args.new_name for c in '/\\:') or args.new_name in {".", ".."}:
            raise ToolError("New name must be a single filename.")
        target = self.resolve(str(source.relative_to(self.root).with_name(args.new_name)))
        if target.exists():
            raise ToolError("Destination already exists.")
        # Windows rename fails if destination exists; this MVP targets Windows.
        source.rename(target)
        return {"path": str(target.relative_to(self.root))}

    def read_text(self, args):
        path = self.resolve(args.path)
        if not path.is_file() or path.stat().st_size > 100000:
            raise ToolError("Choose a text file smaller than 100 KB.")
        try:
            return {"text": path.read_text(encoding="utf-8")[:20000]}
        except UnicodeError as exc:
            raise ToolError("File is not UTF-8 text.") from exc

    def write_text(self, args):
        path = self.resolve(args.path)
        with path.open("x", encoding="utf-8") as handle:
            handle.write(args.text)
        return {"path": str(path.relative_to(self.root))}

    def copy_file(self, args):
        source, target = self.resolve(args.source), self.resolve(args.destination)
        if not source.is_file() or source.stat().st_size > 20 * 1024 * 1024:
            raise ToolError("Choose a file smaller than 20 MB.")
        with source.open("rb") as reader, target.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        return {"path": str(target.relative_to(self.root))}

    def move_file(self, args):
        source, target = self.resolve(args.source), self.resolve(args.destination)
        if not source.is_file() or target.exists():
            raise ToolError("Source must be a file and destination must not exist.")
        source.rename(target)
        return {"path": str(target.relative_to(self.root))}

    def trash_file(self, args):
        source = self.resolve(args.path)
        if not source.is_file():
            raise ToolError("Only files can be moved to trash.")
        trash = self.root / ".trash"
        if trash.is_symlink() or (trash.exists() and trash.resolve() != trash):
            raise ToolError("Invalid trash directory.")
        trash.mkdir(exist_ok=True)
        target = trash / (uuid4().hex + "-" + source.name)
        source.rename(target)
        return {"recoverable_path": str(target.relative_to(self.root))}

    def tools(self):
        return [
            Tool("read_text", "Read UTF-8 text; content will be sent to the selected model.", PathArguments, self.read_text, PermissionLevel.CONFIRM),
            Tool("write_text", "Create a new text file; never overwrite.", WriteArguments, self.write_text, PermissionLevel.CONFIRM),
            Tool("copy_file", "Copy a file without replacing an existing file.", TransferArguments, self.copy_file, PermissionLevel.CONFIRM),
            Tool("move_file", "Move a file inside workspace without overwriting.", TransferArguments, self.move_file, PermissionLevel.CONFIRM),
            Tool("delete_file", "Move a file to a recoverable .trash folder; no permanent deletion.", PathArguments, self.trash_file, PermissionLevel.CONFIRM),
            Tool("list_files", "List up to 200 entries in the workspace.", PathArguments, self.list_files),
            Tool("create_folder", "Create one folder inside the workspace.", PathArguments,
                 self.create_folder, PermissionLevel.CONFIRM),
            Tool("rename_file", "Rename a file without replacing another file.", RenameArguments,
                 self.rename_file, PermissionLevel.CONFIRM),
        ]
