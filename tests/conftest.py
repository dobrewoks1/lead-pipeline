"""Фикстуры. Тесты не используют сеть и ключи API."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lead_pipeline.llm import FakeProvider
from lead_pipeline.prompts import load_prompt
from lead_pipeline.schema import LeadRecord

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.delenv("NOTIFY_TELEGRAM", raising=False)
    monkeypatch.delenv("GSHEETS_ENABLED", raising=False)


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture(scope="session")
def prompt():
    return load_prompt()


@pytest.fixture
def records() -> list[LeadRecord]:
    return [
        LeadRecord(id="T-1", source="chat", text="Хочу записаться на замену масла завтра утром. Олег, +7 913 000-00-21"),
        LeadRecord(id="T-2", source="email", subject="Цена", text="Сколько стоит шиномонтаж R17? Бюджет до 3 000 руб.\n\nСпасибо, Марина"),
        LeadRecord(id="T-3", source="email", subject="Претензия", text="После вашего ремонта стук стал хуже. Верните деньги. Игорь, 89130000067"),
        LeadRecord(id="T-4", source="email", subject="Сотрудничество", text="ООО «Масло-Опт» предлагает поставки масел для вашего автосервиса. Менеджер Анна Ким, +7 913 000 00 11"),
        LeadRecord(id="T-5", source="chat", text="Кредит без справок! Одобрение за 5 минут, перейдите по ссылке http://example.invalid"),
    ]


@pytest.fixture
def project_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "LLM_PROVIDER": "fake"})
    for key in ("ANTHROPIC_API_KEY", "NOTIFY_TELEGRAM", "GSHEETS_ENABLED"):
        env.pop(key, None)
    return env
