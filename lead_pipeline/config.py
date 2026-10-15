"""Настройки из переменных окружения (``.env`` в корне проекта)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"
DEFAULT_MODEL = "claude-haiku-5-5"


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    """``auto`` | ``anthropic`` | ``fake``."""

    anthropic_api_key: str | None
    anthropic_model: str
    workers: int
    """Сколько заявок обрабатывать параллельно (потоки)."""

    prompt_version: str | None
    """Версия промпта (``v1``, ``v2``...); ``None`` — последняя."""

    telegram_enabled: bool
    telegram_bot_token: str | None
    telegram_chat_id: str | None

    gsheets_enabled: bool
    gsheets_credentials: str | None
    gsheets_spreadsheet_id: str | None
    gsheets_worksheet: str


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def load_settings(env_file: str | os.PathLike[str] | None = None) -> Settings:
    load_dotenv(env_file or BASE_DIR / ".env", override=False)
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "auto").strip().lower(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        workers=max(1, int(os.getenv("WORKERS", "4"))),
        prompt_version=os.getenv("PROMPT_VERSION") or None,
        telegram_enabled=_flag("NOTIFY_TELEGRAM"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        gsheets_enabled=_flag("GSHEETS_ENABLED"),
        gsheets_credentials=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or None,
        gsheets_spreadsheet_id=os.getenv("GSHEET_ID") or None,
        gsheets_worksheet=os.getenv("GSHEET_WORKSHEET", "Заявки"),
    )
