"""CLI: ``python -m lead_pipeline run|generate|eval|prompts``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import BASE_DIR, load_settings
from .evalrun import evaluate, format_report, load_golden
from .export import write_csv, write_xlsx
from .generator import generate
from .llm import create_provider
from .notify import NotifyError, push_google_sheets, send_telegram
from .pipeline import process
from .prompts import list_prompts, load_prompt
from .report import format_console_report, format_telegram_summary, summarize
from .schema import read_jsonl, write_jsonl

log = logging.getLogger("lead_pipeline")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m lead_pipeline", description="LLM-конвейер обработки заявок")
    parser.add_argument("-v", "--verbose", action="store_true", help="подробные логи")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="обработать заявки и выгрузить CSV/XLSX")
    run.add_argument("--input", required=True, help="файл JSONL с заявками")
    run.add_argument("--out", default="out", help="папка для результатов (по умолчанию out/)")
    run.add_argument("--provider", choices=["auto", "anthropic", "fake"], help="провайдер (по умолчанию LLM_PROVIDER)")
    run.add_argument("--prompt", help="версия промпта, например v1 (по умолчанию последняя)")
    run.add_argument("--workers", type=int, help="число потоков (по умолчанию WORKERS или 4)")
    run.add_argument("--limit", type=int, help="обработать только первые N заявок")
    run.add_argument("--no-notify", action="store_true", help="не отправлять сводку и не выгружать в Sheets")

    gen = sub.add_parser("generate", help="сгенерировать синтетические заявки")
    gen.add_argument("--n", type=int, default=80, help="сколько заявок (по умолчанию 80)")
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--out", default="data/sample.jsonl", help="куда записать заявки")
    gen.add_argument("--labels", help="куда записать разметку (необязательно)")

    ev = sub.add_parser("eval", help="оценить точность на золотом наборе")
    ev.add_argument("--golden", default=str(BASE_DIR / "evals" / "golden.jsonl"))
    ev.add_argument("--provider", choices=["auto", "anthropic", "fake"])
    ev.add_argument("--prompt", help="версия промпта")
    ev.add_argument("--workers", type=int)

    sub.add_parser("prompts", help="показать версии промптов")
    return parser


def _progress(done: int, total: int, result) -> None:
    status = result.analysis.category if result.ok else "ошибка"
    print(f"\r  обработано {done}/{total} ({result.record.id}: {status})".ljust(70), end="", file=sys.stderr, flush=True)
    if done == total:
        print(file=sys.stderr)


def cmd_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    provider = create_provider(settings, args.provider)
    prompt = load_prompt(version=args.prompt or settings.prompt_version)
    records = read_jsonl(args.input)
    if args.limit:
        records = records[: args.limit]
    workers = args.workers or settings.workers
    print(f"Заявок: {len(records)}. Провайдер: {provider.name} ({provider.model}). Промпт: {prompt.version}. Потоков: {workers}.")

    results = process(records, provider, prompt, workers=workers, progress=_progress)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = write_csv(results, out_dir / "leads.csv")
    xlsx_path = write_xlsx(results, out_dir / "leads.xlsx")
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summarize(results).to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    outputs = [str(csv_path), str(xlsx_path), str(summary_path)]

    print()
    print(format_console_report(results, provider.name, prompt.version, outputs))

    if not args.no_notify:
        try:
            if send_telegram(format_telegram_summary(results), settings):
                print("Сводка отправлена в Telegram.")
            if push_google_sheets(results, settings):
                print("Таблица выгружена в Google Sheets.")
        except NotifyError as exc:
            print(f"Интеграция не выполнена: {exc}", file=sys.stderr)
            return 2
    return 0 if all(r.ok for r in results) else 1


def cmd_generate(args: argparse.Namespace) -> int:
    records, labels = generate(n=args.n, seed=args.seed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out, records)
    print(f"Записано {len(records)} заявок в {args.out}")
    if args.labels:
        write_jsonl(args.labels, labels)
        print(f"Разметка записана в {args.labels}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    settings = load_settings()
    provider = create_provider(settings, args.provider)
    prompt = load_prompt(version=args.prompt or settings.prompt_version)
    items = load_golden(args.golden)
    result = evaluate(provider, prompt, items, workers=args.workers or settings.workers)
    print(format_report(result, provider.name, prompt.version))
    return 0


def cmd_prompts(_: argparse.Namespace) -> int:
    for prompt in list_prompts():
        print(f"{prompt.version:<5} {prompt.path.name:<24} {prompt.meta.get('changelog', '')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    handlers = {"run": cmd_run, "generate": cmd_generate, "eval": cmd_eval, "prompts": cmd_prompts}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
