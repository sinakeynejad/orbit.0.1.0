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

    llm_provider: Literal["openai", "ollama"] = "openai"
    llm_model: str = Field(min_length=1)

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

    @field_validator("llm_model", mode="before")
    @classmethod
    def strip_model_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator(
        "llm_api_key",
        "llm_base_url",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def validate_provider_settings(self) -> "Settings":
        if self.llm_provider == "openai":
            if self.llm_api_key is None:
                raise ValueError(
                    "LLM_API_KEY is required for the openai provider."
                )

            if not self.llm_api_key.get_secret_value().strip():
                raise ValueError("LLM_API_KEY cannot be blank.")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
