"""Конвейер: заявки → провайдер → результаты (параллельно, с сохранением порядка)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Callable

from .llm import LLMError, Provider
from .prompts import Prompt
from .schema import LeadRecord, ProcessedLead

log = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, ProcessedLead], None]


def analyze_one(record: LeadRecord, provider: Provider, prompt: Prompt) -> ProcessedLead:
    """Обработать одну заявку; ошибки провайдера превращаются в поле ``error``, а не в исключение."""
    started = perf_counter()
    try:
        analysis = provider.analyze(record, prompt)
        error = None
    except LLMError as exc:
        analysis, error = None, str(exc)
        log.warning("Заявка %s не обработана: %s", record.id, exc)
    except Exception as exc:  # noqa: BLE001 — конвейер не должен падать из-за одной заявки
        analysis, error = None, f"неожиданная ошибка: {exc!r}"
        log.exception("Заявка %s: неожиданная ошибка", record.id)
    return ProcessedLead(
        record=record,
        analysis=analysis,
        provider=provider.name,
        prompt_version=prompt.version,
        elapsed_ms=int((perf_counter() - started) * 1000),
        error=error,
    )


def process(
    records: list[LeadRecord],
    provider: Provider,
    prompt: Prompt,
    workers: int = 4,
    progress: ProgressCallback | None = None,
) -> list[ProcessedLead]:
    """Обработать список заявок в ``workers`` потоков. Порядок результатов = порядок входа."""
    results: list[ProcessedLead | None] = [None] * len(records)
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(analyze_one, record, provider, prompt): i for i, record in enumerate(records)}
        for future in futures:
            i = futures[future]
            result = future.result()
            results[i] = result
            done += 1
            if progress:
                progress(done, len(records), result)
    return [r for r in results if r is not None]
