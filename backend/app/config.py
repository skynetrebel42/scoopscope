"""Application settings loaded from environment / .env file.

All configurable values have sensible defaults except GEMINI_API_KEY,
which must be set explicitly.  Missing credentials are detected at
startup and surfaced clearly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend directory (one level up from app/).
_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration."""

    gemini_api_key: str | None = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
    )
    max_input_chars: int = field(
        default_factory=lambda: int(os.getenv("MAX_INPUT_CHARS", "10000"))
    )
    llm_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("LLM_TIMEOUT_SECONDS", "90"))
    )
    llm_max_retries: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_RETRIES", "3"))
    )

    @property
    def has_credentials(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.strip())


# Module-level singleton; import this from other modules.
settings = Settings()
