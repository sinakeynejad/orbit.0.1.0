import json
import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import (
    Field,
    HttpUrl,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    api_token: SecretStr = Field(default_factory=lambda: SecretStr(secrets.token_urlsafe(32)), min_length=32)
    data_dir: Path = Path(os.environ.get("LOCALAPPDATA", str(BACKEND_DIR))) / "DesktopAssistant"
    voice_api_key: SecretStr | None = None
    stt_model: str = "whisper-1"
    tts_model: str = "tts-1"
    workspace_dir: Path = Path(os.environ.get("LOCALAPPDATA", str(BACKEND_DIR))) / "DesktopAssistant" / "workspace"
    allowed_applications: dict[str, str] = Field(default_factory=dict)
    agent_max_steps: int = Field(default=8, ge=1, le=20)

    llm_provider: Literal["openai", "ollama"] = "ollama"
    llm_model: str = ""

    llm_api_key: SecretStr | None = None
    llm_base_url: HttpUrl | None = None

    llm_temperature: float | None = Field(
        default=None,
        ge=0,
        le=2,
    )
    llm_max_tokens: int = Field(default=1000, gt=0)
    llm_timeout_seconds: float = Field(
        default=60.0,
        gt=0,
        allow_inf_nan=False,
    )

    @property
    def speech_api_key(self):
        if self.voice_api_key:
            return self.voice_api_key
        endpoint = str(self.llm_base_url or "https://api.openai.com/v1").rstrip("/")
        if self.llm_provider == "openai" and endpoint == "https://api.openai.com/v1":
            return self.llm_api_key
        return None

    @field_validator("llm_model", mode="before")
    @classmethod
    def strip_model_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator(
        "llm_api_key",
        "voice_api_key",
        "llm_base_url",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    defaults = Settings()
    path = defaults.data_dir / "settings.json"
    if path.exists():
        return Settings(**json.loads(path.read_text(encoding="utf-8")))
    return defaults
