import asyncio
from pydantic import ValidationError
from app.core.exceptions import ToolError
from app.tools.permissions import PermissionLevel


class ToolExecutor:
    def __init__(self, registry):
        self.registry = registry

    async def execute(self, call, confirm=None):
        try:
            tool = self.registry.get(call.name)
            arguments = tool.arguments_model.model_validate(call.arguments)
            if tool.permission == PermissionLevel.BLOCKED:
                return {"ok": False, "error": "Tool is blocked."}
            if tool.permission == PermissionLevel.CONFIRM:
                # Confirmation receives a copy; it cannot mutate the approved operation.
                if confirm is None or not await confirm(call.model_copy(deep=True)):
                    return {"ok": False, "error": "Permission denied; no operation performed."}
            job = asyncio.create_task(asyncio.to_thread(tool.handler, arguments))
            try:
                result = await asyncio.shield(job)
            except asyncio.CancelledError:
                # A running OS operation cannot safely be killed. Finish it before releasing
                # the session lock so another request cannot race with an unknown mutation.
                result = await job
            return {"ok": True, "result": result}
        except ValidationError:
            return {"ok": False, "error": "Invalid tool arguments."}
        except ToolError as exc:
            return {"ok": False, "error": str(exc)}
        except OSError:
            return {"ok": False, "error": "Operating system could not complete the operation."}
