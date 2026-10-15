"""Необязательные интеграции: сводка в Telegram и выгрузка в Google Sheets.

Обе выключены по умолчанию и включаются переменными окружения (см. ``.env.example``).
Без включения функции возвращают ``False`` и ничего не делают — конвейер
работает автономно.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

from .config import Settings
from .schema import COLUMN_TITLES, ROW_COLUMNS, ProcessedLead

log = logging.getLogger(__name__)


class NotifyError(RuntimeError):
    """Интеграция включена, но настроена неверно или не ответила."""


def send_telegram(text: str, settings: Settings, opener: Any = None) -> bool:
    """Отправить текст в чат через Bot API. Возвращает ``False``, если интеграция выключена."""
    if not settings.telegram_enabled:
        return False
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise NotifyError("NOTIFY_TELEGRAM=1, но TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не заданы")
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = json.dumps(
        {"chat_id": settings.telegram_chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    ).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    open_fn = opener or urllib.request.urlopen
    try:
        with open_fn(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except OSError as exc:
        raise NotifyError(f"Telegram недоступен: {exc}") from exc
    if not body.get("ok"):
        raise NotifyError(f"Telegram вернул ошибку: {body}")
    return True


def push_google_sheets(results: list[ProcessedLead], settings: Settings) -> bool:
    """Записать таблицу результатов на лист Google Sheets (нужен ``pip install gspread``)."""
    if not settings.gsheets_enabled:
        return False
    if not settings.gsheets_credentials or not settings.gsheets_spreadsheet_id:
        raise NotifyError("GSHEETS_ENABLED=1, но GOOGLE_SERVICE_ACCOUNT_JSON или GSHEET_ID не заданы")
    try:
        import gspread  # type: ignore[import-not-found]
    except ImportError as exc:
        raise NotifyError("Для выгрузки в Google Sheets установите пакет: pip install gspread") from exc

    client = gspread.service_account(filename=settings.gsheets_credentials)
    spreadsheet = client.open_by_key(settings.gsheets_spreadsheet_id)
    try:
        worksheet = spreadsheet.worksheet(settings.gsheets_worksheet)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=settings.gsheets_worksheet, rows=len(results) + 10, cols=len(ROW_COLUMNS))
    rows = [[COLUMN_TITLES[c] for c in ROW_COLUMNS]]
    for result in results:
        row = result.to_row()
        rows.append([row[c] if row[c] != "" else "" for c in ROW_COLUMNS])
    worksheet.clear()
    worksheet.update(rows, value_input_option="RAW")
    log.info("В Google Sheets записано %d строк", len(rows) - 1)
    return True
