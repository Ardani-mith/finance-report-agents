from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str = "gpt-5.5"


def load_settings() -> Settings:
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY belum diisi. Buat file .env dari .env.example lalu isi API key."
        )

    return Settings(
        openai_api_key=api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5",
    )

