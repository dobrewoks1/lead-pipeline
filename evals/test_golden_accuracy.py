"""Тест точности на золотом наборе. По умолчанию — заглушка; Claude включается переменной окружения."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lead_pipeline.config import load_settings
from lead_pipeline.evalrun import evaluate, format_report, load_golden
from lead_pipeline.llm import FakeProvider, create_provider
from lead_pipeline.prompts import load_prompt

GOLDEN = Path(__file__).with_name("golden.jsonl")
CATEGORY_THRESHOLD = 0.9
URGENCY_THRESHOLD = 0.8


def _provider():
    choice = os.getenv("LEAD_EVAL_PROVIDER", "fake").lower()
    if choice == "fake":
        return FakeProvider()
    settings = load_settings()
    if not settings.anthropic_api_key:
        pytest.skip("LEAD_EVAL_PROVIDER=anthropic, но ANTHROPIC_API_KEY не задан")
    return create_provider(settings, choice)


def test_golden_set_is_well_formed() -> None:
    items = load_golden(GOLDEN)
    assert len(items) == 30
    assert len({i.record.id for i in items}) == 30
    categories = {i.expected["category"] for i in items}
    assert categories == {"запись", "цена", "жалоба", "партнёрство", "спам"}


def test_classification_accuracy_meets_threshold() -> None:
    provider = _provider()
    prompt = load_prompt(version=os.getenv("PROMPT_VERSION") or None)
    result = evaluate(provider, prompt, load_golden(GOLDEN), workers=4)
    report = format_report(result, provider.name, prompt.version)
    print("\n" + report)
    assert not result.errors, result.errors
    assert result.category_accuracy >= CATEGORY_THRESHOLD, report
    assert result.urgency_accuracy >= URGENCY_THRESHOLD, report
