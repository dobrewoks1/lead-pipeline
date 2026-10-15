"""Оценка качества на «золотом» наборе ``evals/golden.jsonl``.

Считается точность классификации (категория, срочность) и доля верно извлечённых
полей. Схема оценки — по мотивам ``capabilities/classification/guide.ipynb`` из
Anthropic Cookbook (MIT): предсказания сравниваются с разметкой, строится матрица
ошибок. Внешние библиотеки (scikit-learn) не нужны.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .llm import Provider
from .pipeline import process
from .prompts import Prompt
from .schema import CATEGORIES, LeadRecord, ProcessedLead, normalize_phone

FIELD_NAMES = ("name", "phone", "service", "desired_date", "budget")
_NORMALIZE_RE = re.compile(r"[^0-9a-zа-яё]+")


@dataclass
class GoldenItem:
    record: LeadRecord
    expected: dict[str, Any]


@dataclass
class EvalResult:
    total: int
    processed: int
    category_correct: int
    urgency_correct: int
    field_correct: dict[str, int] = field(default_factory=dict)
    field_total: dict[str, int] = field(default_factory=dict)
    confusion: Counter = field(default_factory=Counter)
    mistakes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def category_accuracy(self) -> float:
        return self.category_correct / self.total if self.total else 0.0

    @property
    def urgency_accuracy(self) -> float:
        return self.urgency_correct / self.total if self.total else 0.0

    def field_accuracy(self, name: str) -> float:
        total = self.field_total.get(name, 0)
        return self.field_correct.get(name, 0) / total if total else 0.0


def load_golden(path: str | Path) -> list[GoldenItem]:
    items: list[GoldenItem] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            expected = data.pop("expected")
            items.append(GoldenItem(record=LeadRecord.from_dict(data), expected=expected))
    return items


def _norm(value: Any) -> str:
    return _NORMALIZE_RE.sub("", str(value).lower().replace("ё", "е"))


def field_matches(name: str, expected: Any, actual: Any) -> bool:
    """Мягкое сравнение полей: телефон и бюджет — точно, текстовые — по нормализованному вхождению."""
    if expected in (None, "") and actual in (None, ""):
        return True
    if expected in (None, "") or actual in (None, ""):
        return False
    if name == "phone":
        return normalize_phone(str(expected)) == normalize_phone(str(actual))
    if name == "budget":
        try:
            return int(expected) == int(actual)
        except (TypeError, ValueError):
            return False
    e, a = _norm(expected), _norm(actual)
    if name == "name":
        return e == a or e in a.split() or a in e.split() or a.startswith(e) or e.startswith(a)
    return e == a or e in a or a in e


def evaluate(provider: Provider, prompt: Prompt, items: list[GoldenItem], workers: int = 4) -> EvalResult:
    results: list[ProcessedLead] = process([item.record for item in items], provider, prompt, workers=workers)
    result = EvalResult(total=len(items), processed=0, category_correct=0, urgency_correct=0)
    for item, processed in zip(items, results):
        if not processed.ok:
            result.errors.append(f"{item.record.id}: {processed.error}")
            result.confusion[(item.expected["category"], "ошибка")] += 1
            continue
        result.processed += 1
        analysis = processed.analysis
        result.confusion[(item.expected["category"], analysis.category)] += 1
        if analysis.category == item.expected["category"]:
            result.category_correct += 1
        else:
            result.mistakes.append(
                f"{item.record.id}: ожидалось «{item.expected['category']}», получено «{analysis.category}»"
            )
        if analysis.urgency == item.expected.get("urgency"):
            result.urgency_correct += 1
        for name in FIELD_NAMES:
            if name not in item.expected:
                continue
            result.field_total[name] = result.field_total.get(name, 0) + 1
            if field_matches(name, item.expected[name], getattr(analysis.fields, name)):
                result.field_correct[name] = result.field_correct.get(name, 0) + 1
    return result


def format_report(result: EvalResult, provider: str, prompt_version: str) -> str:
    lines = [
        f"Золотой набор: {result.total} примеров, провайдер {provider}, промпт {prompt_version}",
        f"Точность категорий: {result.category_accuracy:.1%} ({result.category_correct}/{result.total})",
        f"Точность срочности: {result.urgency_accuracy:.1%} ({result.urgency_correct}/{result.total})",
        "Поля: " + ", ".join(f"{n} {result.field_accuracy(n):.0%}" for n in FIELD_NAMES if result.field_total.get(n)),
        "",
        "Матрица ошибок (строки — ожидалось, столбцы — получено):",
    ]
    columns = list(CATEGORIES) + ["ошибка"]
    header = f"{'':<14}" + "".join(f"{c[:8]:>10}" for c in columns)
    lines.append(header)
    for expected in CATEGORIES:
        row = f"{expected:<14}" + "".join(f"{result.confusion.get((expected, c), 0):>10}" for c in columns)
        lines.append(row)
    if result.mistakes:
        lines.append("")
        lines.append("Ошибки классификации:")
        lines.extend(f"  • {m}" for m in result.mistakes)
    if result.errors:
        lines.append("")
        lines.append("Не обработано:")
        lines.extend(f"  × {e}" for e in result.errors)
    return "\n".join(lines)
