from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "meta/llama-3.3-70b-instruct"
    telegram_bot_token: str | None = None
    index_alpha_api_key: str | None = None
    index_alpha_base_url: str = "https://api.indexalpha.id"


def load_settings() -> Settings:
    load_dotenv()

    api_key = os.getenv("NVIDIA_API_KEY", "").strip() or None

    return Settings(
        nvidia_api_key=api_key,
        nvidia_base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()
        or "https://integrate.api.nvidia.com/v1",
        nvidia_model=os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct").strip()
        or "meta/llama-3.3-70b-instruct",
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or None,
        index_alpha_api_key=os.getenv("INDEX_ALPHA_API_KEY", "").strip() or None,
        index_alpha_base_url=os.getenv("INDEX_ALPHA_BASE_URL", "https://api.indexalpha.id").strip()
        or "https://api.indexalpha.id",
    )


def require_telegram_token(settings: Settings) -> str:
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN belum diisi. Buat bot lewat @BotFather, lalu isi token di .env."
        )
    return settings.telegram_bot_token


def require_index_alpha_key(settings: Settings) -> str:
    if not settings.index_alpha_api_key:
        raise RuntimeError("INDEX_ALPHA_API_KEY belum diisi di .env.")
    return settings.index_alpha_api_key


def require_nvidia_key(settings: Settings) -> str:
    if not settings.nvidia_api_key:
        raise RuntimeError(
            "NVIDIA_API_KEY belum diisi. Buat API key dari NVIDIA API Catalog, lalu isi di .env."
        )
    return settings.nvidia_api_key
