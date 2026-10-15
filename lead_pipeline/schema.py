"""Схема данных конвейера: входная заявка и результат анализа.

Результат анализа описан Pydantic-моделью ``LeadAnalysis`` — она же
превращается в JSON-схему для structured outputs Claude, так что формат
ответа модели гарантирован на уровне API, а не «по договорённости в промпте».
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Category = Literal["запись", "цена", "жалоба", "партнёрство", "спам"]
Urgency = Literal["низкая", "средняя", "высокая"]
Source = Literal["email", "form", "chat"]

CATEGORIES: tuple[str, ...] = ("запись", "цена", "жалоба", "партнёрство", "спам")
URGENCIES: tuple[str, ...] = ("низкая", "средняя", "высокая")
SOURCES: tuple[str, ...] = ("email", "form", "chat")

CATEGORY_LABELS: dict[str, str] = {
    "запись": "запись на услугу",
    "цена": "вопрос по цене",
    "жалоба": "жалоба",
    "партнёрство": "партнёрство",
    "спам": "спам",
}


@dataclass(frozen=True)
class LeadRecord:
    """Входящее обращение (строка файла ``*.jsonl``)."""

    id: str
    source: str
    text: str
    subject: str | None = None
    received_at: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LeadRecord":
        known = {"id", "source", "text", "subject", "received_at"}
        return cls(
            id=str(data["id"]),
            source=str(data.get("source", "email")),
            text=str(data["text"]),
            subject=data.get("subject"),
            received_at=data.get("received_at"),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id, "source": self.source}
        if self.received_at:
            data["received_at"] = self.received_at
        if self.subject:
            data["subject"] = self.subject
        data["text"] = self.text
        data.update(self.extra)
        return data

    def as_prompt_text(self) -> str:
        """Текст заявки для промпта: источник, тема и тело."""
        parts = [f"Источник: {self.source}"]
        if self.subject:
            parts.append(f"Тема: {self.subject}")
        parts.append(f"Текст:\n{self.text}")
        return "\n".join(parts)


class LeadFields(BaseModel):
    """Извлечённые поля. Отсутствующее значение — ``null``, ничего не выдумывается."""

    name: str | None = Field(default=None, description="Имя клиента так, как оно названо в тексте, или null")
    phone: str | None = Field(
        default=None,
        description="Телефон в формате +7XXXXXXXXXX (11 цифр, без пробелов и скобок) или null",
    )
    service: str | None = Field(
        default=None, description="Интересующая услуга коротко (например «замена масла», «шиномонтаж») или null"
    )
    desired_date: str | None = Field(
        default=None, description="Желаемая дата или время визита словами из текста (например «завтра после 18:00», «15 октября») или null"
    )
    budget: int | None = Field(default=None, description="Бюджет в рублях целым числом, если назван, иначе null")

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value) if value else None


class LeadAnalysis(BaseModel):
    """Результат классификации и извлечения для одной заявки."""

    category: Category = Field(description="Категория обращения")
    urgency: Urgency = Field(description="Срочность: высокая — жалоба/просьба ответить сегодня; низкая — партнёрство, спам, общие вопросы")
    summary: str = Field(description="Суть обращения одним предложением на русском языке")
    fields: LeadFields

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        """JSON-схема для документации и для провайдеров без Pydantic."""
        return cls.model_json_schema()


def normalize_phone(raw: str) -> str | None:
    """Привести телефон к виду ``+7XXXXXXXXXX``; вернуть ``None``, если цифр не 10–11."""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 11 and digits[0] in "78":
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    else:
        return None
    return "+" + digits


@dataclass
class ProcessedLead:
    """Заявка вместе с результатом анализа (или ошибкой)."""

    record: LeadRecord
    analysis: LeadAnalysis | None
    provider: str
    prompt_version: str
    elapsed_ms: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.analysis is not None and self.error is None

    def to_row(self) -> dict[str, Any]:
        """Плоская строка для CSV/XLSX."""
        a = self.analysis
        f = a.fields if a else LeadFields()
        return {
            "id": self.record.id,
            "source": self.record.source,
            "received_at": self.record.received_at or "",
            "category": a.category if a else "",
            "urgency": a.urgency if a else "",
            "name": f.name or "",
            "phone": f.phone or "",
            "service": f.service or "",
            "desired_date": f.desired_date or "",
            "budget": f.budget if f.budget is not None else "",
            "summary": a.summary if a else "",
            "subject": self.record.subject or "",
            "text": self.record.text,
            "provider": self.provider,
            "prompt_version": self.prompt_version,
            "elapsed_ms": self.elapsed_ms,
            "error": self.error or "",
        }


ROW_COLUMNS: tuple[str, ...] = (
    "id", "source", "received_at", "category", "urgency", "name", "phone", "service",
    "desired_date", "budget", "summary", "subject", "text", "provider", "prompt_version",
    "elapsed_ms", "error",
)

COLUMN_TITLES: dict[str, str] = {
    "id": "ID",
    "source": "Источник",
    "received_at": "Получено",
    "category": "Категория",
    "urgency": "Срочность",
    "name": "Имя",
    "phone": "Телефон",
    "service": "Услуга",
    "desired_date": "Желаемая дата",
    "budget": "Бюджет, ₽",
    "summary": "Суть",
    "subject": "Тема",
    "text": "Текст обращения",
    "provider": "Провайдер",
    "prompt_version": "Версия промпта",
    "elapsed_ms": "Время, мс",
    "error": "Ошибка",
}


def read_jsonl(path: str) -> list[LeadRecord]:
    """Прочитать заявки из файла JSON Lines."""
    records: list[LeadRecord] = []
    with open(path, encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(LeadRecord.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError) as exc:
                raise ValueError(f"{path}:{line_no}: некорректная запись ({exc})") from exc
    return records


def write_jsonl(path: str, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
