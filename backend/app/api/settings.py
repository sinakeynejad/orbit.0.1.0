import json
from pathlib import Path
from app.tools.factory import create_registry
from fastapi import APIRouter, Request, Response, UploadFile, File
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.core.config import Settings
from app.core.exceptions import AssistantError
from app.llm.client import create_provider
from app.voice.stt import OpenAISpeechToText
from app.voice.tts import OpenAITextToSpeech

router = APIRouter()


@router.post("/auth")
async def auth(request: Request, response: Response):
    response.set_cookie("assistant_session", request.app.state.token, httponly=True, samesite="strict")
    return {"ok": True}


@router.get("/settings")
async def settings(request: Request):
    c = request.app.state.config
    return {"llm_provider": c.llm_provider, "llm_model": c.llm_model,
            "llm_base_url": str(c.llm_base_url or ""), "has_api_key": bool(c.llm_api_key),
            "has_voice_key": bool(c.voice_api_key or c.llm_api_key),
            "workspace_dir": str(c.workspace_dir), "allowed_applications": c.allowed_applications,
            "stt_model": c.stt_model, "tts_model": c.tts_model}


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    llm_provider: str
    llm_model: str = Field(max_length=200)
    llm_base_url: str = ""
    workspace_dir: str | None = None
    allowed_applications: dict[str, str] | None = None
    llm_api_key: str | None = None
    voice_api_key: str | None = None
    stt_model: str = Field(default="whisper-1", min_length=1, max_length=100)
    tts_model: str = Field(default="tts-1", min_length=1, max_length=100)


@router.put("/settings")
async def update_settings(body: SettingsUpdate, request: Request):
    state = request.app.state
    if any(lock.locked() for _, lock in state.assistant.sessions.values()):
        raise AssistantError("Wait for the current request to finish before changing settings.")
    values = state.config.model_dump()
    updates = body.model_dump(exclude_none=True)
    values.update(updates)
    try:
        config = Settings(**values)
    except ValidationError:
        raise AssistantError("Invalid settings. Check provider, model and URL.")
    if not config.workspace_dir.is_absolute():
        raise AssistantError("Workspace must be an absolute path.")
    for alias, executable in config.allowed_applications.items():
        path = Path(executable)
        if not alias.strip() or not path.is_absolute() or not path.is_file() or path.suffix.lower() != ".exe":
            raise AssistantError("Applications must have an alias and an existing absolute .exe path.")
    registry = create_registry(config)
    new_provider = create_provider(config)
    raw = config.model_dump(mode="json", exclude={"api_token"})
    for field in ("llm_api_key", "voice_api_key"):
        secret = getattr(config, field)
        raw[field] = secret.get_secret_value() if secret else None
    path = config.data_dir / "settings.json"
    temp = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        temp.replace(path)
    except OSError as exc:
        await new_provider.aclose()
        raise AssistantError("Cannot save settings. Check available disk space and folder permissions.") from exc
    old = state.assistant.orchestrator.provider
    state.assistant.orchestrator.provider = new_provider
    state.config = config
    state.assistant.orchestrator.executor.registry = registry
    await old.aclose()
    return {"saved": True}


@router.get("/audit")
async def audit(request: Request):
    return request.app.state.store.recent_audit() if request.app.state.store else []


@router.post("/voice/transcribe")
async def transcribe(request: Request, file: UploadFile = File(...)):
    data = await file.read(10 * 1024 * 1024 + 1)
    await file.close()
    if not data or len(data) > 10 * 1024 * 1024:
        raise AssistantError("Recording must be between 1 byte and 10 MB.")
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".webm", ".wav", ".mp3", ".mp4", ".m4a", ".mpeg", ".mpga", ".ogg", ".flac"}:
        raise AssistantError("Unsupported audio format.")
    return {"text": await OpenAISpeechToText(request.app.state.config).transcribe(data, "recording" + extension)}


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/voice/speak")
async def speak(body: SpeechRequest, request: Request):
    audio = await OpenAITextToSpeech(request.app.state.config).speak(body.text)
    return Response(audio, media_type="audio/mpeg")
