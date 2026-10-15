"""Сводка по результатам: для консоли и для сообщения в Telegram."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .schema import CATEGORIES, CATEGORY_LABELS, URGENCIES, ProcessedLead


@dataclass
class Summary:
    total: int
    ok: int
    errors: int
    by_category: dict[str, int] = field(default_factory=dict)
    by_urgency: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)
    top_services: list[tuple[str, int]] = field(default_factory=list)
    with_phone: int = 0
    urgent: list[ProcessedLead] = field(default_factory=list)
    avg_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "ok": self.ok,
            "errors": self.errors,
            "by_category": self.by_category,
            "by_urgency": self.by_urgency,
            "by_source": self.by_source,
            "top_services": self.top_services,
            "with_phone": self.with_phone,
            "urgent_ids": [r.record.id for r in self.urgent],
            "avg_ms": self.avg_ms,
        }


def summarize(results: list[ProcessedLead]) -> Summary:
    ok = [r for r in results if r.ok]
    services = Counter(r.analysis.fields.service for r in ok if r.analysis.fields.service)
    urgent = [r for r in ok if r.analysis.urgency == "высокая" and r.analysis.category != "спам"]
    return Summary(
        total=len(results),
        ok=len(ok),
        errors=len(results) - len(ok),
        by_category={c: sum(1 for r in ok if r.analysis.category == c) for c in CATEGORIES},
        by_urgency={u: sum(1 for r in ok if r.analysis.urgency == u) for u in URGENCIES},
        by_source=dict(Counter(r.record.source for r in results)),
        top_services=services.most_common(5),
        with_phone=sum(1 for r in ok if r.analysis.fields.phone),
        urgent=urgent,
        avg_ms=int(sum(r.elapsed_ms for r in results) / len(results)) if results else 0,
    )


def _bar(value: int, total: int, width: int = 20) -> str:
    filled = round(width * value / total) if total else 0
    return "█" * filled + "░" * (width - filled)


def format_console_report(results: list[ProcessedLead], provider: str, prompt_version: str, outputs: list[str]) -> str:
    """Многострочный отчёт для терминала."""
    s = summarize(results)
    lines = [
        f"Итого: {s.total} заявок, обработано {s.ok}, ошибок {s.errors} "
        f"(провайдер {provider}, промпт {prompt_version}, в среднем {s.avg_ms} мс/заявку)",
        "",
        "По категориям:",
    ]
    for category in CATEGORIES:
        n = s.by_category.get(category, 0)
        lines.append(f"  {CATEGORY_LABELS[category]:<20} {n:>3}  {_bar(n, s.ok)}")
    lines.append("")
    lines.append("По срочности:")
    for urgency in URGENCIES:
        n = s.by_urgency.get(urgency, 0)
        lines.append(f"  {urgency:<20} {n:>3}  {_bar(n, s.ok)}")
    lines.append("")
    lines.append(f"Источники: " + ", ".join(f"{k} — {v}" for k, v in sorted(s.by_source.items())))
    lines.append(f"Телефон извлечён: {s.with_phone} из {s.ok}")
    if s.top_services:
        lines.append("Популярные услуги: " + ", ".join(f"{name} ({n})" for name, n in s.top_services))
    if s.urgent:
        lines.append("")
        lines.append(f"Срочные обращения ({len(s.urgent)}) — обработать в первую очередь:")
        for r in s.urgent[:8]:
            f = r.analysis.fields
            contact = f.phone or "телефон не указан"
            lines.append(f"  ! {r.record.id} [{r.analysis.category}] {f.name or 'без имени'}, {contact}: {r.analysis.summary[:90]}")
    errors = [r for r in results if not r.ok]
    if errors:
        lines.append("")
        lines.append("Ошибки:")
        for r in errors[:5]:
            lines.append(f"  × {r.record.id}: {r.error}")
    if outputs:
        lines.append("")
        lines.append("Файлы: " + ", ".join(outputs))
    return "\n".join(lines)


def format_telegram_summary(results: list[ProcessedLead]) -> str:
    """Короткая сводка для Telegram (HTML-разметка)."""
    s = summarize(results)
    parts = [f"<b>Заявки за прогон: {s.total}</b> (ошибок: {s.errors})"]
    parts.append(", ".join(f"{CATEGORY_LABELS[c]}: {n}" for c, n in s.by_category.items() if n))
    if s.urgent:
        parts.append(f"\n<b>Срочные ({len(s.urgent)}):</b>")
        for r in s.urgent[:5]:
            f = r.analysis.fields
            parts.append(f"• {r.record.id} {f.name or ''} {f.phone or ''} — {r.analysis.summary[:80]}")
    return "\n".join(parts)
