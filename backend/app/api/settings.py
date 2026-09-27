import json
import httpx
import asyncio
from pathlib import Path
from app.tools.factory import create_registry
from fastapi import APIRouter, Request, Response, UploadFile, File
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.core.config import Settings
from app.core.exceptions import AssistantError
from app.llm.client import create_provider
from app.llm.connection import check_connection, failure
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
            "has_voice_key": bool(c.speech_api_key),
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


class ConnectionCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    llm_provider: str
    llm_model: str = Field(max_length=200)
    llm_base_url: str = Field(default="", max_length=2000)
    llm_api_key: str | None = Field(default=None, max_length=4096)


@router.post("/settings/test-connection")
async def test_connection(body: ConnectionCheck, request: Request):
    saved = request.app.state.config
    values = saved.model_dump()
    values.update(body.model_dump(exclude_none=True))
    values["llm_timeout_seconds"] = 30
    try:
        config = Settings(_env_file=None, **values)
    except ValidationError:
        return failure("invalid_settings", "Check the provider and Base URL (use http:// or https://).")
    # Never forward a stored credential to a newly entered service endpoint.
    default_url = "https://api.openai.com/v1"
    saved_url = str(saved.llm_base_url or default_url).rstrip("/")
    test_url = str(config.llm_base_url or default_url).rstrip("/")
    if config.llm_provider == "openai" and not body.llm_api_key and (saved.llm_provider != "openai" or saved_url != test_url):
        return failure("key_required", "Enter an API key for this provider and Base URL before testing.")
    return await check_connection(config)


class OllamaModelsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    llm_base_url: str = Field(default="", max_length=2000)


@router.post("/settings/ollama-models")
async def ollama_models(body: OllamaModelsRequest):
    try:
        config = Settings(_env_file=None, llm_base_url=body.llm_base_url)
    except ValidationError:
        raise AssistantError("Enter a valid Ollama Base URL starting with http:// or https://.")
    base_url = str(config.llm_base_url or "http://127.0.0.1:11434").rstrip("/") + "/"
    try:
        async with asyncio.timeout(10):
            async with httpx.AsyncClient(base_url=base_url, timeout=10, trust_env=False) as client:
                response = await client.get("api/tags")
                response.raise_for_status()
                data = response.json()
        models = data["models"]
        if not isinstance(models, list):
            raise ValueError()
        names = []
        for model in models:
            name = model["name"]
            if not isinstance(name, str) or not name.strip() or len(name) > 200:
                raise ValueError()
            names.append(name)
        return {"models": sorted(set(names), key=str.casefold)}
    except (TimeoutError, httpx.TimeoutException):
        raise AssistantError("Ollama did not respond within 10 seconds. Check that it is running, then refresh.")
    except httpx.HTTPStatusError:
        raise AssistantError("Ollama rejected the model list request. Check its Base URL and server access.")
    except httpx.HTTPError:
        raise AssistantError("Cannot reach Ollama. Start Ollama and check the Base URL, then refresh.")
    except (KeyError, TypeError, ValueError):
        raise AssistantError("The server returned an invalid model list. Check that the Base URL points to Ollama.")


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
    saved = state.config
    saved_url = str(saved.llm_base_url or "https://api.openai.com/v1").rstrip("/")
    new_url = str(config.llm_base_url or "https://api.openai.com/v1").rstrip("/")
    if config.llm_provider == "openai" and config.llm_api_key and body.llm_api_key is None and (saved.llm_provider != "openai" or saved_url != new_url):
        raise AssistantError("Enter an API key for the new provider or Base URL before saving.")
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
